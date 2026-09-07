"""Bundle assembly: one incident, every file accounted for.

These build their own COMTRADE files rather than leaning on the corpus, so
they run on a clone that has no real records.
"""
from __future__ import annotations

import math
import os
import zipfile

import pytest

from dranalyser.workbench import (assign, open_bundle, read_manifest,
                                  write_manifest)

FS = 1000.0
N = 200
CHANS_FULL = ("IA", "IB", "IC", "VA", "VB", "VC")
CHANS_SHORT = ("IA", "VA")


def _write_record(folder, stem: str, chans=CHANS_FULL, seed: float = 0.0) -> str:
    """A minimal but genuinely valid 1999 ASCII COMTRADE pair."""
    os.makedirs(folder, exist_ok=True)
    lines = ["TESTSTN,1,1999", "%d,%dA,0D" % (len(chans), len(chans))]
    for i, ch in enumerate(chans, start=1):
        unit = "A" if ch.startswith("I") else "V"
        lines.append("%d,%s,,,%s,1.0,0,0,-32767,32767,1,1,P" % (i, ch, unit))
    lines += ["50", "1", "%d,%d" % (int(FS), N),
              "01/01/2026,00:00:00.000000", "01/01/2026,00:00:00.100000",
              "ASCII", "1"]
    cfg = os.path.join(folder, stem + ".cfg")
    with open(cfg, "w", encoding="ascii") as fh:
        fh.write("\r\n".join(lines) + "\r\n")

    rows = []
    for n in range(N):
        t = n / FS
        vals = []
        for i, ch in enumerate(chans):
            amp = 1000.0 if ch.startswith("I") else 120000.0
            ph = 2.0 * math.pi * (i % 3) / 3.0
            vals.append("%d" % int(amp * math.sin(2 * math.pi * 50.0 * t - ph) / 10.0
                                   + seed))
        rows.append("%d,%d,%s" % (n + 1, int(round(t * 1e6)), ",".join(vals)))
    with open(os.path.join(folder, stem + ".dat"), "w", encoding="ascii") as fh:
        fh.write("\r\n".join(rows) + "\r\n")
    return cfg


def test_every_file_is_accounted_for_including_the_ones_that_fail(tmp_path):
    """Nothing is dropped silently -- PROJECT_CONTEXT.md 2.5."""
    root = tmp_path / "inc"
    _write_record(str(root / "main1"), "a")
    (root / "orphan.cfg").write_text("TESTSTN,1,1999\r\n", encoding="ascii")
    (root / "notes.txt").write_text("operator notes", encoding="ascii")

    b = open_bundle(str(root))
    names = {f.name: f for f in b.files}
    assert "main1/a.cfg" in names and names["main1/a.cfg"].usable
    orphan = names["orphan.cfg"]
    assert orphan.kind == "comtrade" and not orphan.ok
    assert "no .dat" in orphan.error
    # a settings-shaped file is carried, not analysed
    assert names["notes.txt"].kind == "settings"


def test_a_byte_identical_copy_is_marked_duplicate_not_dropped(tmp_path):
    """The corpus already contains one record filed under two relays."""
    root = tmp_path / "inc"
    _write_record(str(root / "main1"), "a")
    _write_record(str(root / "main2"), "a")      # identical content

    b = open_bundle(str(root))
    recs = sorted(b.records(), key=lambda f: f.name)
    assert len(recs) == 2
    assert recs[0].content_hash == recs[1].content_hash
    assert recs[0].duplicate_of == "" and recs[1].duplicate_of == recs[0].name
    assert not recs[1].usable and recs[1].ok      # listed, parsed, excluded


def test_zip_and_folder_describe_the_same_records(tmp_path):
    root = tmp_path / "inc"
    _write_record(str(root / "main1"), "a")
    _write_record(str(root / "main2"), "b", seed=3.0)

    archive = tmp_path / "inc.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for dirpath, _d, files in os.walk(root):
            for fn in files:
                full = os.path.join(dirpath, fn)
                zf.write(full, os.path.relpath(full, root))

    from_dir = open_bundle(str(root))
    from_zip = open_bundle(str(archive), workdir=str(tmp_path / "unpacked"))
    assert ([f.content_hash for f in from_dir.records()]
            == [f.content_hash for f in from_zip.records()])


def test_a_zip_member_escaping_the_bundle_is_refused(tmp_path):
    """An uploaded archive is untrusted input."""
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escaped.cfg", "TESTSTN,1,1999\r\n")
    with pytest.raises(ValueError, match="outside the bundle"):
        open_bundle(str(archive), workdir=str(tmp_path / "unpacked"))
    assert not (tmp_path / "escaped.cfg").exists()


def test_a_blocked_record_cannot_be_assigned_to_an_end(tmp_path):
    """Refuse, and say why. Never quietly analyse it anyway."""
    root = tmp_path / "inc"
    _write_record(str(root), "short", chans=CHANS_SHORT)
    b = open_bundle(str(root))
    rec = b.records()[0]
    assert rec.ok and rec.blocked

    refusals = assign(b, {"short.cfg": ("S", "primary")})
    assert refusals and "blocked by the conformance gate" in refusals[0]
    assert rec.terminal_end == ""


def test_two_primary_records_at_one_end_is_refused(tmp_path):
    """Main-1 and Main-2 at one terminal is normal; two primaries is not."""
    root = tmp_path / "inc"
    _write_record(str(root / "m1"), "a")
    _write_record(str(root / "m2"), "b", seed=5.0)

    b = open_bundle(str(root))
    refusals = assign(b, {"m1/a.cfg": ("S", "primary"),
                          "m2/b.cfg": ("S", "primary")})
    assert any("primary records" in r for r in refusals)

    ok = assign(b, {"m1/a.cfg": ("S", "primary"),
                    "m2/b.cfg": ("S", "corroborating")})
    assert ok == []
    assert [f.name for f in b.by_end("S")] == ["m1/a.cfg", "m2/b.cfg"]
    assert b.primary("S").name == "m1/a.cfg"


def test_the_manifest_round_trips_and_keeps_the_declaration(tmp_path):
    root = tmp_path / "inc"
    _write_record(str(root / "m1"), "a")
    _write_record(str(root / "m2"), "b", seed=7.0)

    b = open_bundle(str(root))
    assign(b, {"m1/a.cfg": ("S", "primary"), "m2/b.cfg": ("R", "primary")},
           line_id="GRV-MRD-1")
    path = write_manifest(b)
    assert os.path.basename(path) == "_asset.yaml"

    back = read_manifest(path)
    assert back.line_id == "GRV-MRD-1"
    assert back.primary("S").name == "m1/a.cfg"
    assert back.primary("R").name == "m2/b.cfg"
    # the declaration records WHO said so -- 6 evidence rank 1, not inference
    assert back.primary("S").assignment_source == "operator"


# --------------------------------------------------------------------------
# the local server
# --------------------------------------------------------------------------
def _http_bundle(tmp_path, port):
    """A running workbench with two records, uploaded through the form."""
    import threading

    from dranalyser.workbench.server import make_server

    src = tmp_path / "src"
    _write_record(str(src / "m1"), "a")
    _write_record(str(src / "m2"), "b", seed=9.0)
    archive = tmp_path / "inc.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for dirpath, _d, fns in os.walk(src):
            for fn in fns:
                full = os.path.join(dirpath, fn)
                zf.write(full, os.path.relpath(full, src))

    httpd = make_server(root=str(tmp_path / "bundles"), host="127.0.0.1",
                        port=port, registry_dir=str(tmp_path / "registry"))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, archive


def _post_multipart(url, filename, payload, fields):
    import urllib.request
    boundary = "----dranalysetest"
    body = b""
    for k, v in fields.items():
        body += ("--" + boundary + "\r\nContent-Disposition: form-data; name=\""
                 + k + "\"\r\n\r\n" + v + "\r\n").encode()
    body += ("--" + boundary + "\r\nContent-Disposition: form-data; "
             "name=\"files\"; filename=\"" + filename + "\"\r\n"
             "Content-Type: application/octet-stream\r\n\r\n").encode()
    body += payload + ("\r\n--" + boundary + "--\r\n").encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    return urllib.request.urlopen(req, timeout=10)


def test_upload_describes_every_record_and_analyses_once(tmp_path):
    """The whole loop: upload a zip, declare the ends, get ONE incident."""
    import urllib.parse
    import urllib.request

    httpd, archive = _http_bundle(tmp_path, 8241)
    base = "http://127.0.0.1:8241"
    try:
        assert "Upload" in urllib.request.urlopen(base + "/", timeout=10).read().decode()

        resp = _post_multipart(base + "/upload", "inc.zip",
                               archive.read_bytes(), {"bundle_id": "inc"})
        page = resp.read().decode()
        assert "m1/a.cfg" in page and "m2/b.cfg" in page
        assert "usable" in page

        data = urllib.parse.urlencode({
            "line_id": "TEST-LINE",
            "end::m1/a.cfg": "S", "role::m1/a.cfg": "primary",
            "end::m2/b.cfg": "R", "role::m2/b.cfg": "primary"}).encode()
        out = urllib.request.urlopen(base + "/bundle/inc/assign", data=data,
                                     timeout=20).read().decode()
        assert "Incident" in out
        assert "end S" in out and "end R" in out
        # the declaration survived into the manifest
        b = read_manifest(str(tmp_path / "bundles" / "inc" / "_asset.yaml"))
        assert b.line_id == "TEST-LINE"
        assert b.primary("S").name == "m1/a.cfg"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_the_server_refuses_two_primaries_rather_than_picking_one(tmp_path):
    import urllib.error
    import urllib.parse
    import urllib.request

    httpd, archive = _http_bundle(tmp_path, 8242)
    base = "http://127.0.0.1:8242"
    try:
        _post_multipart(base + "/upload", "inc.zip", archive.read_bytes(),
                        {"bundle_id": "inc"}).read()
        data = urllib.parse.urlencode({
            "end::m1/a.cfg": "S", "role::m1/a.cfg": "primary",
            "end::m2/b.cfg": "S", "role::m2/b.cfg": "primary"}).encode()
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(base + "/bundle/inc/assign", data=data, timeout=10)
        assert exc.value.code == 400
        assert "primary records" in exc.value.read().decode()
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_a_zip_bomb_path_cannot_escape_the_bundle_directory(tmp_path):
    import urllib.request

    httpd, _archive = _http_bundle(tmp_path, 8243)
    base = "http://127.0.0.1:8243"
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("../../pwned.cfg", "TESTSTN,1,1999\r\n")
    try:
        import urllib.error
        with pytest.raises(urllib.error.HTTPError) as exc:
            _post_multipart(base + "/upload", "evil.zip", evil.read_bytes(),
                            {"bundle_id": "evil"})
        assert exc.value.code == 400
        assert "outside the bundle" in exc.value.read().decode()
        assert not (tmp_path / "pwned.cfg").exists()
    finally:
        httpd.shutdown()
        httpd.server_close()


# --------------------------------------------------------------------------
# cross-checking two relays on one bus (P3)
# --------------------------------------------------------------------------
from dranalyser.workbench.corroborate import Measure, compare   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPH = os.path.join(ROOT, "drs sphoorthi")
needs_sphoorthi = pytest.mark.skipif(
    not os.path.isdir(SPH), reason="Sphoorthi records not present")


def _m(name, ftype="CG", ipre=700.0, iflt=1500.0, zs2=complex(2.0, 10.0),
       scatter=0.01):
    return Measure(file=name, ok=True, fault_type=ftype, i_prefault_a=ipre,
                   i_fault_a=iflt, zs2=zs2, zs2_scatter=scatter)


def test_two_relays_that_agree_raise_nothing():
    assert compare("S", [_m("main1.cfg"), _m("main2.cfg", ipre=712.0,
                                             iflt=1530.0,
                                             zs2=complex(2.2, 10.4))]) == []


def test_one_record_at_a_terminal_is_never_compared_with_itself():
    assert compare("S", [_m("only.cfg")]) == []


def test_disagreement_on_fault_type_is_raised():
    out = compare("S", [_m("a.cfg", ftype="CG"), _m("b.cfg", ftype="AG")])
    assert [d.code for d in out] == ["XR-01"]


def test_disagreement_on_current_is_raised_separately_for_load_and_fault():
    pre = compare("S", [_m("a.cfg", ipre=700.0), _m("b.cfg", ipre=300.0)])
    assert "XR-02" in [d.code for d in pre]
    flt = compare("S", [_m("a.cfg", iflt=1500.0), _m("b.cfg", iflt=6000.0)])
    assert "XR-03" in [d.code for d in flt]


def test_a_source_impedance_that_differs_by_a_factor_is_raised():
    out = compare("R", [_m("a.cfg", zs2=complex(154.0, 26.0)),
                        _m("b.cfg", zs2=complex(2.0, 21.5))])
    codes = [d.code for d in out]
    assert "XR-04" in codes
    assert "suspect the voltage input" in [d for d in out
                                           if d.code == "XR-04"][0].text


def test_a_noisy_source_impedance_is_not_compared_at_all():
    """A measurement too scattered to trust must not manufacture a finding."""
    out = compare("R", [_m("a.cfg", zs2=complex(154.0, 26.0), scatter=0.9),
                        _m("b.cfg", zs2=complex(2.0, 21.5), scatter=0.01)])
    assert "XR-04" not in [d.code for d in out]


@needs_sphoorthi
def test_the_two_garividi_relays_disagree_on_event_15665(tmp_path):
    """The real case P3 exists for: same bus, same fault, different Zs2."""
    import shutil

    from dranalyser.workbench.incident import analyse_bundle

    dest = tmp_path / "15665"
    for folder, label in (("garividi-maradam-1", "garividi"),
                          ("maradam-garividi-1", "maradam")):
        src = os.path.join(SPH, folder)
        for dp, _d, fns in os.walk(src):
            for fn in fns:
                if fn.lower().endswith((".cfg", ".dat")):
                    rel = os.path.join(label,
                                       os.path.relpath(os.path.join(dp, fn), src))
                    os.makedirs(os.path.dirname(str(dest / rel)), exist_ok=True)
                    shutil.copy2(os.path.join(dp, fn), str(dest / rel))

    b = open_bundle(str(dest), bundle_id="e15665")
    assert assign(b, {
        "maradam/Main-1/15665_Main-1_dr.cfg": ("S", "primary"),
        "garividi/Main-1 D60/15665_Main-1 D60_dr.cfg": ("R", "primary"),
        "garividi/Main-2 P444/15665_Main-2 P444_dr.cfg": ("R", "corroborating"),
    }) == []

    res = analyse_bundle(b, out_dir=str(dest))
    # both Garividi relays were measured, not just the primary
    assert len(res.measures["R"]) == 2
    # they agree on the current -- so the disagreement is in the voltage
    ipre = [m.i_prefault_a for m in res.measures["R"]]
    assert abs(ipre[0] - ipre[1]) / max(ipre) < 0.05
    codes = [d.code for d in res.disagreements]
    assert codes == ["XR-04"]


# --------------------------------------------------------------------------
# the resolver pre-filling the form (P4)
# --------------------------------------------------------------------------
from dranalyser.registry.model import (InstrumentTransformer,  # noqa: E402
                                       Relay, Terminal, uniform_line)
from dranalyser.workbench.resolve import suggest  # noqa: E402


def _registry_line():
    ln = uniform_line("TST-LINE", "Alpha - Beta", 220.0, 50.0,
                      complex(0.03, 0.4), complex(0.25, 1.2))
    ln.path_rules = [r"(?i)(?:^|/)(?P<substation>alpha|beta)(?:/|$)"]
    ln.terminals["S"] = Terminal(end="S", substation="ALPHA",
                                 it=InstrumentTransformer(800.0, 2000.0),
                                 relays=[Relay(id="ALPHA-M1")])
    ln.terminals["R"] = Terminal(end="R", substation="BETA",
                                 it=InstrumentTransformer(800.0, 2000.0),
                                 relays=[Relay(id="BETA-M1")])
    return ln


def test_the_resolver_proposes_but_never_decides(tmp_path):
    """A suggestion is not an assignment. assign() still has to be called."""
    root = tmp_path / "inc"
    _write_record(str(root / "alpha"), "a")
    b = open_bundle(str(root))
    n = suggest(b, lines=[_registry_line()])

    f = b.records()[0]
    assert n == 1
    assert (f.suggested_line_id, f.suggested_end) == ("TST-LINE", "S")
    assert f.suggested_evidence
    # nothing was applied
    assert f.terminal_end == "" and f.assignment_source == ""
    assert b.primary("S") is None


def test_an_unresolvable_record_gets_a_reason_not_a_guess(tmp_path):
    root = tmp_path / "inc"
    _write_record(str(root / "somewhere"), "a")     # no path or header match
    b = open_bundle(str(root))
    suggest(b, lines=[_registry_line()])
    f = b.records()[0]
    assert f.suggested_end == ""
    assert f.suggested_reason


def test_an_earlier_operator_declaration_is_kept_not_argued_with(tmp_path):
    """Reopening a bundle must not overwrite what a human already decided."""
    root = tmp_path / "inc"
    _write_record(str(root / "alpha"), "a")
    b = open_bundle(str(root))
    assign(b, {"alpha/a.cfg": ("R", "primary")}, line_id="TST-LINE")

    suggest(b, lines=[_registry_line()])
    f = b.records()[0]
    assert f.terminal_end == "R"                 # the operator's choice stands
    assert f.suggested_end == "R"                # and the manifest is rank 1
    assert any("manifest" in e for e in f.suggested_evidence)


def test_with_no_line_definitions_nothing_is_suggested_and_it_says_why(tmp_path):
    root = tmp_path / "inc"
    _write_record(str(root / "alpha"), "a")
    b = open_bundle(str(root))
    assert suggest(b, registry_dir=str(tmp_path / "empty")) == 0
    assert "nothing can be resolved against" in b.records()[0].suggested_reason


@needs_sphoorthi
def test_the_real_folder_tree_resolves_all_three_usable_records(tmp_path):
    """Including the D60, whose CFG station name is the useless 'Relay-1'."""
    import shutil

    from dranalyser.registry.assets import load_registry

    registry = load_registry("data/registry")
    if not any(ln.id == "GRV-MRD-1" for ln in registry):
        pytest.skip("Garividi-Maradam registry entries not present")

    dest = tmp_path / "tree"
    for folder in ("garividi-maradam-1", "maradam-garividi-1"):
        src = os.path.join(SPH, folder)
        for dp, _d, fns in os.walk(src):
            for fn in fns:
                if fn.lower().endswith((".cfg", ".dat")):
                    rel = os.path.join(folder,
                                       os.path.relpath(os.path.join(dp, fn), src))
                    os.makedirs(os.path.dirname(str(dest / rel)), exist_ok=True)
                    shutil.copy2(os.path.join(dp, fn), str(dest / rel))

    b = open_bundle(str(dest), bundle_id="tree")
    assert suggest(b, lines=registry) == 3
    got = {f.name.split("/")[0] + "/" + f.name.split("/")[1]:
           (f.suggested_line_id, f.suggested_end)
           for f in b.records() if f.suggested_end}
    assert got["garividi-maradam-1/Main-1 D60"] == ("GRV-MRD-1", "R")
    assert got["garividi-maradam-1/Main-2 P444"] == ("GRV-MRD-1", "R")
    assert got["maradam-garividi-1/Main-1"] == ("GRV-MRD-1", "S")
