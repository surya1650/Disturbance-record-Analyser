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
