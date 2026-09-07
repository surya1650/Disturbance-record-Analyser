"""The local workbench server.

Standard library only, single user, bound to the loopback interface by
default. This tool serves live protection data and has no authentication, so
exposing it on a substation LAN is a deliberate decision, not a default.

Routes:
    GET  /                          upload form
    POST /upload                    store files, open the bundle
    GET  /bundle/<id>               what was read, and the assignment form
    POST /bundle/<id>/assign        apply the declaration, analyse, redirect
    GET  /incident/<id>             the incident, with the report embedded
    GET  /report/<id>               the generated report itself
"""
from __future__ import annotations

import email.parser
import email.policy
import os
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Optional, Tuple

from .bundle import MANIFEST_NAME, Bundle, assign, open_bundle, read_manifest, write_manifest
from .incident import analyse_bundle, default_line_files
from .pages import bundle_page, incident_page, upload_page

# An uploaded record is a waveform file; a few hundred MB of binary DAT is
# plausible for a long recording, a gigabyte is someone's mistake.
MAX_UPLOAD_BYTES = 400 * 1024 * 1024
SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


def _safe_id(raw: str) -> str:
    """Bundle ids become directory names, so they are constrained, not trusted."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", (raw or "").strip()).strip("-.")
    return cleaned[:80] or ""


class Workbench:
    """Everything the handler needs, kept out of the handler class."""

    def __init__(self, root: str, registry_dir: str = "data/registry") -> None:
        self.root = os.path.abspath(root)
        self.registry_dir = registry_dir
        os.makedirs(self.root, exist_ok=True)

    def dir_for(self, bundle_id: str) -> str:
        return os.path.join(self.root, bundle_id)

    def list_bundles(self) -> List[str]:
        if not os.path.isdir(self.root):
            return []
        return sorted(n for n in os.listdir(self.root)
                      if os.path.isdir(os.path.join(self.root, n)))

    def load(self, bundle_id: str) -> Optional[Bundle]:
        d = self.dir_for(bundle_id)
        if not os.path.isdir(d):
            return None
        manifest = os.path.join(d, MANIFEST_NAME)
        if os.path.exists(manifest):
            b = read_manifest(manifest)
            b.bundle_id = bundle_id
            b.root = d
            return b
        return open_bundle(d, bundle_id=bundle_id)


def _parse_multipart(ctype: str, body: bytes) -> Tuple[Dict[str, str],
                                                       List[Tuple[str, bytes]]]:
    """Split a multipart body into fields and (filename, bytes) uploads.

    `cgi.FieldStorage` is deprecated and gone in 3.13; `email` is the
    documented replacement and is already in the standard library.
    """
    head = b"Content-Type: " + ctype.encode("latin-1") + b"\r\nMIME-Version: 1.0\r\n\r\n"
    msg = email.parser.BytesParser(policy=email.policy.default).parsebytes(head + body)
    fields: Dict[str, str] = {}
    files: List[Tuple[str, bytes]] = []
    if not msg.is_multipart():
        return fields, files
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition") or ""
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename:
            files.append((os.path.basename(filename), payload))
        else:
            fields[name] = payload.decode("utf-8", "replace").strip()
    return fields, files


class Handler(BaseHTTPRequestHandler):
    server_version = "dranalyse-workbench"
    wb: Workbench = None                       # set on the server instance

    # ---------------------------------------------------------------- helpers
    def _send(self, body: str, status: int = 200,
              ctype: str = "text/html; charset=utf-8") -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, to: str) -> None:
        self.send_response(303)
        self.send_header("Location", to)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, fmt: str, *args) -> None:      # quieter console
        pass

    # -------------------------------------------------------------------- GET
    def do_GET(self) -> None:                  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        parts = [p for p in path.split("/") if p]

        if not parts:
            self._send(upload_page(self.wb.list_bundles()))
            return
        if parts[0] == "bundle" and len(parts) == 2:
            self._bundle_view(parts[1])
            return
        if parts[0] == "incident" and len(parts) == 2:
            self._incident_view(parts[1])
            return
        if parts[0] == "report" and len(parts) == 2:
            self._report_file(parts[1])
            return
        self._send(upload_page(self.wb.list_bundles(), "no such page"), 404)

    def _bundle_view(self, bundle_id: str, refusals: Optional[List[str]] = None,
                     status: int = 200) -> None:
        if not SAFE_ID.match(bundle_id):
            self._send(upload_page(self.wb.list_bundles(), "bad bundle id"), 400)
            return
        b = self.wb.load(bundle_id)
        if b is None:
            self._send(upload_page(self.wb.list_bundles(),
                                   "no bundle called " + bundle_id), 404)
            return
        self._send(bundle_page(b, default_line_files(self.wb.registry_dir),
                               refusals or []), status)

    def _incident_view(self, bundle_id: str) -> None:
        b = self.wb.load(bundle_id)
        if b is None:
            self._send(upload_page(self.wb.list_bundles(), "no such bundle"), 404)
            return
        res = analyse_bundle(b, line_path=b.line_path,
                             out_dir=self.wb.dir_for(bundle_id))
        url = "/report/" + bundle_id if res.report_path else None
        self._send(incident_page(b, res, url))

    def _report_file(self, bundle_id: str) -> None:
        d = self.wb.dir_for(bundle_id)
        found = [n for n in sorted(os.listdir(d))] if os.path.isdir(d) else []
        html_files = [n for n in found if n.lower().endswith(".html")]
        if not html_files:
            self._send("<p>no report has been generated for this bundle</p>", 404)
            return
        with open(os.path.join(d, html_files[-1]), encoding="utf-8") as fh:
            self._send(fh.read())

    # ------------------------------------------------------------------- POST
    def do_POST(self) -> None:                 # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        parts = [p for p in path.split("/") if p]
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_UPLOAD_BYTES:
            self._send(upload_page(self.wb.list_bundles(),
                                   "upload is larger than the "
                                   + str(MAX_UPLOAD_BYTES // (1024 * 1024))
                                   + " MB limit"), 413)
            return
        body = self.rfile.read(length)

        if parts == ["upload"]:
            self._do_upload(body)
            return
        if len(parts) == 3 and parts[0] == "bundle" and parts[2] == "assign":
            self._do_assign(parts[1], body)
            return
        self._send(upload_page(self.wb.list_bundles(), "no such action"), 404)

    def _do_upload(self, body: bytes) -> None:
        fields, files = _parse_multipart(self.headers.get("Content-Type") or "", body)
        files = [(n, d) for n, d in files if n and d]
        if not files:
            self._send(upload_page(self.wb.list_bundles(), "no files were uploaded"),
                       400)
            return

        bundle_id = _safe_id(fields.get("bundle_id", "")) or _safe_id(
            os.path.splitext(files[0][0])[0]) or "bundle"
        base = bundle_id
        n = 1
        while os.path.isdir(self.wb.dir_for(bundle_id)):
            n += 1
            bundle_id = base + "-" + str(n)
        dest = self.wb.dir_for(bundle_id)
        os.makedirs(dest, exist_ok=True)

        zips = []
        for name, data in files:
            safe = os.path.basename(name)
            with open(os.path.join(dest, safe), "wb") as fh:
                fh.write(data)
            if safe.lower().endswith(".zip"):
                zips.append(os.path.join(dest, safe))

        try:
            for z in zips:
                # unpack in place so the .cfg finds its .dat
                open_bundle(z, workdir=dest, bundle_id=bundle_id)
            b = open_bundle(dest, bundle_id=bundle_id)
        except ValueError as exc:              # a zip member tried to escape
            self._send(upload_page(self.wb.list_bundles(), str(exc)), 400)
            return
        write_manifest(b)
        self._redirect("/bundle/" + bundle_id)

    def _do_assign(self, bundle_id: str, body: bytes) -> None:
        b = self.wb.load(bundle_id)
        if b is None:
            self._send(upload_page(self.wb.list_bundles(), "no such bundle"), 404)
            return
        form = urllib.parse.parse_qs(body.decode("utf-8", "replace"))

        def one(k: str) -> str:
            return (form.get(k) or [""])[0].strip()

        choices: Dict[str, Tuple[str, str]] = {}
        for key, vals in form.items():
            if not key.startswith("end::"):
                continue
            name = key[len("end::"):]
            end = (vals or [""])[0].strip()
            role = (form.get("role::" + name) or ["primary"])[0].strip()
            choices[name] = (end, role)

        refusals = assign(b, choices, line_id=one("line_id"))
        if refusals:
            self._bundle_view(bundle_id, refusals, status=400)
            return
        b.line_path = one("line_path")
        write_manifest(b)

        res = analyse_bundle(b, line_path=b.line_path,
                             out_dir=self.wb.dir_for(bundle_id))
        url = "/report/" + bundle_id if res.report_path else None
        self._send(incident_page(b, res, url))


def make_server(root: str = "out/bundles", host: str = "127.0.0.1",
                port: int = 8090,
                registry_dir: str = "data/registry") -> ThreadingHTTPServer:
    """Build the server without starting it, so tests can drive it."""
    handler = type("BoundHandler", (Handler,),
                   {"wb": Workbench(root, registry_dir)})
    return ThreadingHTTPServer((host, port), handler)


def serve(root: str = "out/bundles", host: str = "127.0.0.1", port: int = 8090,
          registry_dir: str = "data/registry") -> None:
    httpd = make_server(root, host, port, registry_dir)
    where = "http://" + ("127.0.0.1" if host in ("0.0.0.0", "") else host) \
        + ":" + str(port) + "/"
    print("workbench serving " + os.path.abspath(root))
    print("open " + where)
    if host not in ("127.0.0.1", "localhost"):
        print("WARNING: bound to " + host + ". This tool has no authentication "
              "and serves live protection data.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
