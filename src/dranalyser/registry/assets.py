"""Resolve a record to a line, a terminal and a relay -- from evidence.

**Nothing here infers a terminal from the operator's argument order.** Today
`--S` and `--R` decide it, which means the operator can silently swap the ends
and get a confident, mirrored answer. The end is derived by matching a
resolved substation against the line's two terminals, and ambiguity is
refused rather than broken by ordering.

Evidence, in decreasing authority (`PROJECT_CONTEXT.md` §6):

1. **A sidecar manifest** -- explicit, and what the edge collector will emit.
   The workbench already writes one, so an operator's declaration enters here
   as rank-1 evidence rather than as a special case.
2. **Path rules**, configured per line in the registry YAML rather than coded.
3. **The CFG header.** `DHONE(SWS)` names a station; `220KV DHN-NNR 18-3-2026
   Folder 7SA522 V4.7 Var` names the station, the line and the relay model.
4. **A sibling settings export**, which carries SUBSTATION and FEEDER.
5. **Electrical corroboration**: nominal voltage from the pre-fault reading,
   and CT/VT ratios matching a registered terminal.

Why the header is only rank 3: on the Sphoorthi records one Garividi relay
names its station `MARADAM 2` (the bay is named for the remote end) and
another names `BRAHMANAKOTKUR` (a configuration cloned from another station
and never renamed). Both are electrically at Garividi. A resolver that
trusted the header would assign both to the wrong end.

The weights below are **project policy, not standards-derived**. No standard
says how to identify which line a file belongs to.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple, Union

from .model import Line

# Project policy. Rank 1 alone decides; nothing else does on its own.
W_MANIFEST = 1.00
W_PATH_RULE = 0.60
W_HEADER = 0.50
W_SETTINGS = 0.50
W_ELECTRICAL = 0.30

# A candidate must reach this, and beat the runner-up by this margin.
MIN_SCORE = 0.50
MIN_MARGIN = 0.20
# Nominal voltage agrees within this fraction before it counts as evidence.
KV_TOLERANCE = 0.15


def norm(s: str) -> str:
    """Upper-case, letters and digits only. `220KV DHN-NNR` -> `220KVDHNNNR`."""
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


@dataclass
class RecordFacts:
    """What the caller read out of a record, as primitives.

    `registry/` imports nothing from the rest of the package on purpose, so
    the resolver never sees a `Record`. The caller extracts these; that also
    means a manifest alone can be resolved with no record present at all.
    """

    path: str = ""
    station: str = ""
    device_id: str = ""
    kv_nominal: Optional[float] = None      # from the pre-fault voltage
    ct_ratio: Optional[float] = None
    vt_ratio: Optional[float] = None
    settings_substation: str = ""
    settings_feeder: str = ""


@dataclass
class AssetHint:
    """One piece of evidence, and what it points at."""

    source: str                             # manifest | path | header | settings | electrical
    confidence: float = 0.0
    line_id: str = ""
    terminal_end: str = ""
    relay_id: str = ""
    substation: str = ""
    detail: str = ""

    def __str__(self) -> str:
        bits = [b for b in (self.line_id, self.terminal_end, self.relay_id) if b]
        return ("[" + self.source + " " + format(self.confidence, ".2f") + "] "
                + "/".join(bits) + (" -- " + self.detail if self.detail else ""))


@dataclass
class Assignment:
    line_id: str = ""
    terminal_end: str = ""
    relay_id: str = ""
    confidence: float = 0.0
    evidence: List[AssetHint] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.line_id and self.terminal_end)


@dataclass
class Ambiguous:
    """Refusal. A wrongly assigned record gives a confident answer for the
    wrong line, which is worse than no answer at all."""

    reason: str = ""
    candidates: List[Assignment] = field(default_factory=list)
    evidence: List[AssetHint] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return False


Resolution = Union[Assignment, Ambiguous]


def _names_of_terminal(line: Line, end: str) -> List[str]:
    t = line.terminals.get(end)
    if t is None:
        return []
    return [t.substation] + list(t.aliases)


def _line_names(line: Line) -> List[str]:
    return [line.id, line.name] + list(line.aliases)


def _match_any(haystack: str, names: Sequence[str]) -> str:
    """The first name that appears in the normalised haystack."""
    h = norm(haystack)
    if not h:
        return ""
    for n in names:
        nn = norm(n)
        if nn and nn in h:
            return n
    return ""


class AssetResolver:
    """Resolve one record against a loaded registry of lines."""

    def __init__(self, lines: Sequence[Line]) -> None:
        self.lines = list(lines)

    # ---- evidence gatherers ---------------------------------------------
    def _from_manifest(self, manifest: Optional[Dict[str, str]]) -> List[AssetHint]:
        if not manifest:
            return []
        lid = manifest.get("line_id") or ""
        end = (manifest.get("terminal_end") or "").upper()
        if not (lid or end):
            return []
        return [AssetHint(source="manifest", confidence=W_MANIFEST, line_id=lid,
                          terminal_end=end, relay_id=manifest.get("relay_id") or "",
                          detail="declared by " + (manifest.get("source") or "manifest"))]

    def _from_path(self, path: str) -> List[AssetHint]:
        out: List[AssetHint] = []
        if not path:
            return out
        norm_path = path.replace("\\", "/")
        for line in self.lines:
            for pattern in line.path_rules:
                m = re.search(pattern, norm_path)
                if not m:
                    continue
                g = m.groupdict()
                end = self._end_for_substation(line, g.get("substation") or "")
                out.append(AssetHint(
                    source="path", confidence=W_PATH_RULE, line_id=line.id,
                    terminal_end=(g.get("end") or end or "").upper(),
                    relay_id=g.get("relay") or "",
                    substation=g.get("substation") or "",
                    detail="path rule " + pattern))
        # A line named in the path itself, with no rule configured.
        for line in self.lines:
            hit = _match_any(norm_path, _line_names(line))
            if hit and not any(h.line_id == line.id for h in out):
                out.append(AssetHint(
                    source="path", confidence=W_PATH_RULE, line_id=line.id,
                    detail="path contains " + hit))
        return out

    def _from_text(self, text: str, source: str, weight: float) -> List[AssetHint]:
        """A free-text field that may name a substation, a line or a relay."""
        out: List[AssetHint] = []
        if not norm(text):
            return out
        for line in self.lines:
            line_hit = _match_any(text, _line_names(line))
            for end in sorted(line.terminals):
                sub_hit = _match_any(text, _names_of_terminal(line, end))
                # Deliberately NOT the relay model. A model number is not an
                # identifier: half this fleet is 7SA522, so matching one would
                # be a confident end signal that means nothing. Only the
                # relay's id and the aliases someone chose for it count.
                relay_hit = ""
                for r in line.terminals[end].relays:
                    relay_hit = _match_any(text, [r.id] + list(r.aliases))
                    if relay_hit:
                        relay_hit = r.id
                        break
                if sub_hit or (line_hit and relay_hit):
                    # A relay named here sits at exactly one terminal, so it
                    # is end evidence too. When both ends carry a relay that
                    # matches, the two hints are equal and the tie is refused
                    # -- which is the wanted behaviour, not a failure.
                    out.append(AssetHint(
                        source=source, confidence=weight, line_id=line.id,
                        terminal_end=end, relay_id=relay_hit,
                        substation=sub_hit,
                        detail=source + " names "
                               + (sub_hit or relay_hit or line_hit)))
            # The line name is evidence in its own right, and is emitted even
            # when a substation also matched. On a double-circuit corridor
            # the substation cannot tell 205 from 206 and the circuit name is
            # the only thing that can, so it must not be swallowed.
            if line_hit:
                out.append(AssetHint(source=source, confidence=weight,
                                     line_id=line.id,
                                     detail=source + " names " + line_hit))
        return out

    def _from_electrical(self, facts: RecordFacts) -> List[AssetHint]:
        out: List[AssetHint] = []
        for line in self.lines:
            if facts.kv_nominal and line.kv > 0:
                if abs(facts.kv_nominal - line.kv) / line.kv > KV_TOLERANCE:
                    continue
            for end in sorted(line.terminals):
                it = line.terminals[end].it
                ct_ok = (facts.ct_ratio is not None and it.ct_ratio > 0
                         and abs(facts.ct_ratio - it.ct_ratio) < 1e-6)
                vt_ok = (facts.vt_ratio is not None and it.vt_ratio > 0
                         and abs(facts.vt_ratio - it.vt_ratio) / it.vt_ratio < 0.01)
                if ct_ok and vt_ok:
                    out.append(AssetHint(
                        source="electrical", confidence=W_ELECTRICAL,
                        line_id=line.id, terminal_end=end,
                        detail="CT " + format(it.ct_ratio, ".0f") + " and VT "
                               + format(it.vt_ratio, ".0f") + " match this terminal"))
        return out

    def _end_for_substation(self, line: Line, substation: str) -> str:
        """The end whose substation this names. Never file order."""
        if not norm(substation):
            return ""
        for end in sorted(line.terminals):
            if _match_any(substation, _names_of_terminal(line, end)):
                return end
        return ""

    # ---- resolution -----------------------------------------------------
    def resolve(self, facts: RecordFacts,
                manifest: Optional[Dict[str, str]] = None) -> Resolution:
        ev: List[AssetHint] = []
        ev += self._from_manifest(manifest)
        ev += self._from_path(facts.path)
        ev += self._from_text(facts.station, "header", W_HEADER)
        ev += self._from_text(facts.settings_substation + " "
                              + facts.settings_feeder, "settings", W_SETTINGS)
        ev += self._from_electrical(facts)

        if not ev:
            return Ambiguous(reason="no evidence identifies this record: the path, "
                                    "the CFG header and the instrument ratios match "
                                    "no registered line", evidence=[])

        # A manifest is decisive on its own; it is the operator or the
        # collector stating the answer, not the analyser guessing it.
        decisive = [h for h in ev if h.source == "manifest" and h.line_id
                    and h.terminal_end]
        if decisive:
            h = decisive[0]
            return Assignment(line_id=h.line_id, terminal_end=h.terminal_end,
                              relay_id=h.relay_id, confidence=h.confidence,
                              evidence=ev)

        scores: Dict[Tuple[str, str], float] = {}
        relays: Dict[Tuple[str, str], str] = {}
        for h in ev:
            if not h.line_id:
                continue
            key = (h.line_id, h.terminal_end)
            scores[key] = scores.get(key, 0.0) + h.confidence
            if h.relay_id:
                relays.setdefault(key, h.relay_id)

        # Evidence that names the line but not the end lifts every end of that
        # line equally, so it can never decide which end -- only which line.
        for (lid, end), val in list(scores.items()):
            if end:
                continue
            for line in self.lines:
                if line.id != lid:
                    continue
                for other in line.terminals:
                    scores[(lid, other)] = scores.get((lid, other), 0.0) + val
            del scores[(lid, end)]

        if not scores:
            return Ambiguous(reason="evidence names a line but never a terminal; "
                                    "the end cannot be derived and is not guessed",
                             evidence=ev)

        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        best_key, best = ranked[0]
        runner = ranked[1][1] if len(ranked) > 1 else 0.0

        cands = [Assignment(line_id=k[0], terminal_end=k[1], relay_id=relays.get(k, ""),
                            confidence=round(v, 3), evidence=ev)
                 for k, v in ranked[:4]]

        if best < MIN_SCORE:
            return Ambiguous(
                reason="strongest evidence scores " + format(best, ".2f")
                       + ", below the " + format(MIN_SCORE, ".2f")
                       + " a record needs to be assigned",
                candidates=cands, evidence=ev)
        if (best - runner) < MIN_MARGIN:
            return Ambiguous(
                reason="two candidates are too close to call ("
                       + "/".join(x for x in best_key if x) + " at "
                       + format(best, ".2f") + " against "
                       + "/".join(x for x in ranked[1][0] if x) + " at "
                       + format(runner, ".2f") + "); refusing rather than guessing",
                candidates=cands, evidence=ev)

        return Assignment(line_id=best_key[0], terminal_end=best_key[1],
                          relay_id=relays.get(best_key, ""),
                          confidence=round(best, 3), evidence=ev)


def load_registry(directory: str = "data/registry") -> List[Line]:
    """Every line definition in a registry directory."""
    from .loader import load_line

    if not os.path.isdir(directory):
        return []
    out = []
    for name in sorted(os.listdir(directory)):
        if name.lower().endswith((".yaml", ".yml")):
            try:
                out.append(load_line(os.path.join(directory, name)))
            except Exception:                   # noqa: BLE001 - a bad file is skipped
                continue
    return out
