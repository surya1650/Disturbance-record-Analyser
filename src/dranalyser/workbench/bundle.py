"""Assemble a set of uploaded files into one incident, and describe it.

The domain object is the incident, never the file (PROJECT_CONTEXT.md §2.4).
A `Bundle` is what the operator hands over -- a folder or a zip -- resolved
into the records and settings exports inside it, each carrying its own parse
result and conformance verdict.

Two rules from real defects are enforced here rather than left to the caller:

* **Nothing is dropped silently** (§2.5). A file that will not parse, a
  record the conformance gate blocks, and a byte-identical duplicate all stay
  in the bundle with the reason attached. The analysis excludes them; the
  bundle still lists them.

* **Nothing infers which end a record belongs to.** The assignment is the
  operator's declaration, recorded with `source: operator`, which is rank 1
  of §6's evidence hierarchy -- above the CFG header, which on this fleet is
  demonstrably unreliable (one Garividi record names its station `MARADAM 2`,
  another names `BRAHMANAKOTKUR`). When the AssetResolver lands it fills the
  same field with `source: resolver` and the operator confirms it.
"""
from __future__ import annotations

import datetime as _dt
import os
import zipfile
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple

import yaml

from ..comtrade.conformance import check
from ..comtrade.parser import read_cff, read_comtrade

MANIFEST_NAME = "_asset.yaml"

# Recognised extensions, lower-cased. A settings export is carried in the
# bundle because the report needs it for the R-X diagram; it is never parsed
# here, only located.
COMTRADE_CFG = (".cfg",)
COMTRADE_CFF = (".cff",)
COMTRADE_DAT = (".dat",)
SETTINGS_EXT = (".rio", ".xml", ".txt", ".csv")


@dataclass
class BundleFile:
    """One file the operator handed over, and what became of it."""

    name: str                       # path relative to the bundle root
    kind: str                       # comtrade | settings | unusable
    ok: bool = False
    error: str = ""

    data_file: str = ""             # the .dat that goes with a .cfg
    record_id: str = ""
    station: str = ""
    device_id: str = ""
    fs_hz: float = 0.0
    samples: int = 0
    start_time: str = ""
    trigger_time: str = ""
    content_hash: str = ""
    flags: List[str] = field(default_factory=list)
    blocked: bool = False
    duplicate_of: str = ""
    # Facts the AssetResolver needs, captured while the record is open so it
    # is never re-read. kv is measured from the pre-fault voltage, which is
    # what PROJECT_CONTEXT.md 6 rank 5 asks for.
    ct_ratio: float = 0.0
    vt_ratio: float = 0.0
    kv_nominal: float = 0.0

    # The operator's declaration. Empty until assigned; never guessed.
    line_id: str = ""
    terminal_end: str = ""
    relay_id: str = ""
    protection_system: str = "unknown"  # operator-declared, independent of primary role
    recording_profile: str = "unconfirmed"  # declared reference-table applicability
    channel_inventory: List[dict] = field(default_factory=list)
    channel_mapping: dict = field(default_factory=dict)
    mapping_original_flags: List[str] = field(default_factory=list)
    rx_review: dict = field(default_factory=dict)
    stage_review: dict = field(default_factory=dict)
    settings_source: dict = field(default_factory=dict)
    role: str = ""                  # primary | corroborating | excluded
    assignment_source: str = ""

    # What the AssetResolver proposes, kept separate from what the operator
    # declared so both survive. The form pre-fills from these; submitting
    # replaces `assignment_source` with "operator".
    suggested_line_id: str = ""
    suggested_end: str = ""
    suggested_relay_id: str = ""
    suggested_confidence: float = 0.0
    suggested_reason: str = ""
    suggested_evidence: List[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        """Can this record reach the estimators at all?"""
        return self.kind == "comtrade" and self.ok and not self.blocked \
            and not self.duplicate_of


@dataclass
class Bundle:
    """A set of files declared to be one incident."""

    bundle_id: str
    root: str
    source: str = ""
    created_at: str = ""
    line_id: str = ""
    # The registry file the operator picked, if any. Kept in the manifest so
    # reopening an incident reproduces the same answer rather than a
    # distance-free one.
    line_path: str = ""
    files: List[BundleFile] = field(default_factory=list)

    def records(self) -> List[BundleFile]:
        return [f for f in self.files if f.kind == "comtrade"]

    def settings(self) -> List[BundleFile]:
        return [f for f in self.files if f.kind == "settings"]

    def usable(self) -> List[BundleFile]:
        return [f for f in self.files if f.usable]

    def by_end(self, end: str) -> List[BundleFile]:
        """Usable records the operator put at one end, primary first."""
        got = [f for f in self.usable() if f.terminal_end == end]
        return sorted(got, key=lambda f: 0 if f.role == "primary" else 1)

    def primary(self, end: str) -> Optional[BundleFile]:
        got = self.by_end(end)
        return got[0] if got else None


# --------------------------------------------------------------------------
# opening
# --------------------------------------------------------------------------
def _safe_extract(zip_path: str, dest: str) -> None:
    """Extract a zip, refusing any member that escapes the destination.

    An uploaded archive is untrusted input. A member named `../../x` would
    otherwise write outside the bundle directory.
    """
    dest_abs = os.path.abspath(dest)
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            target = os.path.abspath(os.path.join(dest_abs, member.filename))
            if target != dest_abs and not target.startswith(dest_abs + os.sep):
                raise ValueError("refusing zip member outside the bundle: "
                                 + member.filename)
        zf.extractall(dest_abs)


def _walk(root: str) -> List[str]:
    out = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            out.append(os.path.relpath(full, root).replace("\\", "/"))
    return sorted(out)


def _partner_dat(root: str, rel_cfg: str, names: List[str]) -> str:
    """The .dat belonging to a .cfg. Case and extension case both vary."""
    stem = os.path.splitext(rel_cfg)[0].lower()
    for cand in names:
        if os.path.splitext(cand)[1].lower() in COMTRADE_DAT \
                and os.path.splitext(cand)[0].lower() == stem:
            return cand
    return ""


def _instrument_facts(rec) -> Tuple[float, float, float]:
    """CT ratio, VT ratio and measured nominal kV, or zeros when unavailable.

    Ratios come from the CFG channel definitions; the voltage is MEASURED from
    the pre-fault window rather than taken from the CFG, because vendors
    disagree on whether the primary field is phase-ground or phase-phase.
    """
    ct = vt = kv = 0.0
    for name in ("IA", "IB", "IC"):
        m = rec.analog_meta.get(name)
        if m and m.secondary:
            ct = float(m.primary) / float(m.secondary)
            break
    for name in ("VA", "VB", "VC"):
        m = rec.analog_meta.get(name)
        if m and m.secondary:
            vt = float(m.primary) / float(m.secondary)
            break
    va = rec.analog.get("VA")
    if va is not None and len(va) > 20:
        pre = va[: max(20, len(va) // 5)]
        rms = float((pre.astype(float) ** 2).mean() ** 0.5)
        kv = rms * (3.0 ** 0.5) / 1000.0
    return ct, vt, kv


def open_bundle(path: str, workdir: Optional[str] = None,
                bundle_id: str = "") -> Bundle:
    """Resolve a folder or a zip into a bundle.

    `workdir` is where a zip is unpacked; it defaults to a sibling of the
    archive so the extracted records stay next to what the operator uploaded.
    """
    src = os.path.abspath(path)
    if not os.path.exists(src):
        raise FileNotFoundError(src)

    if os.path.isfile(src) and src.lower().endswith(".zip"):
        dest = workdir or os.path.join(os.path.dirname(src),
                                       os.path.splitext(os.path.basename(src))[0])
        os.makedirs(dest, exist_ok=True)
        _safe_extract(src, dest)
        root = dest
    elif os.path.isdir(src):
        root = src
    else:
        # A single file: treat its directory as the root so a .cfg finds its
        # .dat, but keep only what the operator named.
        root = os.path.dirname(src)

    bid = bundle_id or (os.path.basename(root.rstrip("/\\")) or "bundle")
    bundle = Bundle(bundle_id=bid, root=root, source=src,
                    created_at=_dt.datetime.now().isoformat(timespec="seconds"))

    names = _walk(root)
    if os.path.isfile(src) and not src.lower().endswith(".zip"):
        keep = os.path.relpath(src, root).replace("\\", "/")
        names = [n for n in names
                 if n == keep or os.path.splitext(n)[0].lower()
                 == os.path.splitext(keep)[0].lower()]

    seen_hash: Dict[str, str] = {}
    for rel in names:
        ext = os.path.splitext(rel)[1].lower()
        if ext in COMTRADE_DAT:
            continue                        # described through its .cfg
        if ext in SETTINGS_EXT:
            bundle.files.append(BundleFile(name=rel, kind="settings", ok=True))
            continue
        if ext not in COMTRADE_CFG + COMTRADE_CFF:
            continue                        # not ours; the zip may hold anything

        bf = BundleFile(name=rel, kind="comtrade")
        full = os.path.join(root, rel.replace("/", os.sep))
        if ext in COMTRADE_CFG:
            bf.data_file = _partner_dat(root, rel, names)
            if not bf.data_file:
                bf.error = "no .dat file accompanies this .cfg"
                bundle.files.append(bf)
                continue
        try:
            rec = (read_cff(full) if ext in COMTRADE_CFF else read_comtrade(full))
            check(rec)
        except Exception as exc:            # noqa: BLE001 - reported, not raised
            bf.error = type(exc).__name__ + ": " + str(exc)[:200]
            bundle.files.append(bf)
            continue

        bf.ok = True
        bf.record_id = rec.record_id
        bf.station = rec.station
        bf.device_id = rec.device_id
        bf.fs_hz = round(float(rec.fs), 1)
        bf.samples = int(len(rec.t))
        bf.start_time = str(rec.start_time or "")
        bf.trigger_time = str(rec.trigger_time or "")
        bf.content_hash = rec.content_hash
        from .channel_mapping import inventory_for
        bf.channel_inventory = inventory_for(rec)
        bf.flags = [str(f) for f in rec.flags]
        bf.blocked = rec.blocked()
        bf.ct_ratio, bf.vt_ratio, bf.kv_nominal = _instrument_facts(rec)
        if rec.content_hash and rec.content_hash in seen_hash:
            bf.duplicate_of = seen_hash[rec.content_hash]
        else:
            seen_hash[rec.content_hash] = rel
        bundle.files.append(bf)

    return bundle


# --------------------------------------------------------------------------
# the operator's declaration
# --------------------------------------------------------------------------
def assign(bundle: Bundle, choices: Dict[str, Tuple[str, str]],
           line_id: str = "") -> List[str]:
    """Apply the operator's end assignment. Returns refusals, never repairs.

    `choices` maps a file name to `(terminal_end, role)`. An end may hold
    several records -- Main-1 and Main-2 at one terminal is the normal case
    (§5.3) -- but exactly one of them is primary, because the estimators take
    one measurement per terminal. Two primaries at one end is an operator
    error and is refused rather than resolved by ordering.
    """
    refusals: List[str] = []
    by_name = {f.name: f for f in bundle.files}
    for name, (end, role) in choices.items():
        f = by_name.get(name)
        if f is None:
            refusals.append("no such file in the bundle: " + name)
            continue
        if end not in ("", "S", "R"):
            refusals.append(name + ": terminal must be S, R or unassigned")
            continue
        if end and not f.usable:
            why = (f.error or ("blocked by the conformance gate" if f.blocked
                               else "duplicate of " + f.duplicate_of))
            refusals.append(name + ": cannot be assigned to an end -- " + why)
            continue
        f.terminal_end = end
        f.role = role or ("primary" if end else "")
        f.assignment_source = "operator" if end else ""

    for end in ("S", "R"):
        primaries = [f for f in bundle.usable()
                     if f.terminal_end == end and f.role == "primary"]
        if len(primaries) > 1:
            refusals.append(
                "end " + end + " has " + str(len(primaries)) + " primary records ("
                + ", ".join(f.name for f in primaries)
                + "); exactly one record per end drives the estimate")

    if line_id:
        bundle.line_id = line_id
        for f in bundle.files:
            if f.terminal_end:
                f.line_id = line_id
    return refusals


# --------------------------------------------------------------------------
# manifest
# --------------------------------------------------------------------------
def write_manifest(bundle: Bundle, path: str = "") -> str:
    """Write the bundle as a sidecar manifest.

    The shape is §6's `_asset.yaml` on purpose: the edge collector is
    specified manifest-first, so what it emits later is what this reads.
    """
    out = path or os.path.join(bundle.root, MANIFEST_NAME)
    doc = {
        "bundle_id": bundle.bundle_id,
        "created_at": bundle.created_at,
        "source": bundle.source,
        "line_id": bundle.line_id,
        "line_path": bundle.line_path,
        "files": [asdict(f) for f in bundle.files],
    }
    with open(out, "w", encoding="utf-8") as fh:
        yaml.safe_dump(doc, fh, sort_keys=False, allow_unicode=True)
    return out


def read_manifest(path: str) -> Bundle:
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}
    b = Bundle(bundle_id=doc.get("bundle_id", ""),
               root=os.path.dirname(os.path.abspath(path)),
               source=doc.get("source", ""),
               created_at=doc.get("created_at", ""),
               line_id=doc.get("line_id", ""),
               line_path=doc.get("line_path", ""))
    for raw in doc.get("files") or []:
        known = {k: v for k, v in raw.items()
                 if k in BundleFile.__dataclass_fields__}
        b.files.append(BundleFile(**known))
    return b
