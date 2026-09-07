"""A capture form for the tower number, served from the standard library.

The QR code on page 1 of the report has to point somewhere. This is that
somewhere: no framework, no database server, no internet, so it can run on a
laptop in a substation office on day one. The brief targets FastAPI and
PostgreSQL for the production service, and the storage schema is written to
lift across unchanged; this exists so that confirmations start accumulating
now rather than after that service is built.

The form is deliberately short. Everything it asks for is something a patrol
engineer knows standing at the tower, and every field except the tower number
is optional, because a confirmation with a tower and nothing else is still
the most valuable row in the system.
"""
from __future__ import annotations

import html
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional, Tuple

from .store import CAUSES, CONFIDENCE, Confirmation, Store

PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>
body{{font-family:system-ui,Segoe UI,Helvetica,Arial,sans-serif;margin:0;
background:#f4f6f8;color:#1b2733}}
.wrap{{max-width:560px;margin:0 auto;padding:18px 16px 40px}}
h1{{font-size:19px;margin:0 0 2px}} .sub{{color:#7a8894;font-size:13px}}
.card{{background:#fff;border:1px solid #dfe3e6;border-radius:6px;padding:14px 16px;
margin:14px 0}}
label{{display:block;font-size:12px;text-transform:uppercase;letter-spacing:.05em;
color:#45535f;margin:12px 0 4px}}
input,select,textarea{{width:100%;padding:9px 10px;font-size:16px;border:1px solid #c6ced4;
border-radius:4px;background:#fff}}
button{{margin-top:16px;width:100%;padding:12px;font-size:16px;font-weight:600;color:#fff;
background:#1f6feb;border:0;border-radius:4px}}
.est{{background:#eef4ff;border:1px solid #b9d0f5;border-radius:4px;padding:10px 12px;
font-size:14px}}
.ok{{background:#e6f4ea;border:1px solid #9ed3ad;padding:12px;border-radius:4px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
td,th{{text-align:left;padding:5px 6px;border-bottom:1px solid #eceff1}}
a{{color:#1f6feb}} .muted{{color:#7a8894;font-size:12px}}
</style></head><body><div class="wrap">{body}</div></body></html>"""


def _esc(v: object) -> str:
    return html.escape("" if v is None else str(v))


def _form(store: Store, incident_id: str, message: str = "") -> str:
    inc = store.incident(incident_id)
    if inc is None:
        body = ("<h1>Unknown incident</h1><p class='sub'>" + _esc(incident_id)
                + " is not in the store.</p><p><a href='/'>All incidents</a></p>")
        return PAGE.format(title="Unknown incident", body=body)

    est = ""
    if inc["km_from_S"] is not None:
        est = ("<div class='est'><b>Analyser estimate:</b> "
               + format(inc["km_from_S"], ".2f") + " km from the S terminal"
               + (" (" + _esc(inc["mode"]) + ", " + _esc(inc["method"]) + ")"
                  if inc["mode"] else "")
               + "<div class='muted'>Record what you actually found, not what "
                 "this says. A confirmation that agrees because it was copied "
                 "teaches the system nothing.</div></div>")

    prior = store.latest_confirmation(incident_id)
    prior_html = ""
    if prior is not None:
        prior_html = ("<p class='muted'>Already confirmed on "
                      + _esc(prior["confirmed_at"]) + " by "
                      + _esc(prior["confirmed_by"] or "unknown")
                      + " as tower " + _esc(prior["tower_no"])
                      + ". Submitting again records a correction; nothing is "
                        "overwritten.</p>")

    causes = "".join("<option>" + _esc(c) + "</option>" for c in CAUSES)
    conf = "".join("<option>" + _esc(c) + "</option>" for c in CONFIDENCE)
    body = (
        "<h1>Confirm the fault location</h1>"
        "<div class='sub'>" + _esc(inc["line_id"]) + " &middot; "
        + _esc(inc["fault_time"] or "time unknown") + "</div>"
        "<div class='sub'>" + _esc(incident_id) + "</div>"
        + (("<div class='card ok'>" + _esc(message) + "</div>") if message else "")
        + "<div class='card'>" + est + prior_html
        + "<form method='post'>"
        "<label>Tower number where the fault was found</label>"
        "<input name='tower_no' inputmode='numeric' autofocus>"
        "<label>Chainage from the S terminal, km (if known)</label>"
        "<input name='chainage_km' inputmode='decimal'>"
        "<label>Cause</label><select name='cause'>" + causes + "</select>"
        "<label>How certain</label><select name='confidence'>" + conf + "</select>"
        "<label>Confirmed by</label><input name='confirmed_by'>"
        "<label>Notes</label><textarea name='notes' rows='3'></textarea>"
        "<button type='submit'>Record confirmation</button></form></div>"
        "<p><a href='/'>All incidents</a></p>")
    return PAGE.format(title="Confirm " + _esc(incident_id), body=body)


def _index(store: Store) -> str:
    pend = store.pending()
    rows = "".join(
        "<tr><td><a href='/confirm/" + _esc(r["incident_id"]) + "'>"
        + _esc(r["incident_id"]) + "</a></td><td>" + _esc(r["line_id"])
        + "</td><td>" + _esc(r["fault_time"] or "") + "</td><td>"
        + (format(r["km_from_S"], ".2f") + " km" if r["km_from_S"] is not None else "-")
        + "</td></tr>" for r in pend)
    body = ("<h1>Awaiting confirmation</h1>"
            "<div class='sub'>" + str(len(pend)) + " incident(s) with no patrol result"
            "</div><div class='card'><table><tr><th>Incident</th><th>Line</th>"
            "<th>Fault time</th><th>Estimate</th></tr>"
            + (rows or "<tr><td colspan='4' class='muted'>Nothing pending.</td></tr>")
            + "</table></div><div class='card'><pre class='muted'>"
            + _esc(store.accuracy_report()) + "</pre></div>")
    return PAGE.format(title="Ground truth capture", body=body)


class Handler(BaseHTTPRequestHandler):
    store: Store = None                     # type: ignore[assignment]
    server_version = "dranalyser-capture"

    def log_message(self, fmt, *args):      # keep the console usable
        pass

    def _send(self, body: str, status: int = 200) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _incident_from_path(self) -> Optional[str]:
        path = urllib.parse.urlparse(self.path).path.rstrip("/")
        if path.startswith("/confirm/"):
            return urllib.parse.unquote(path[len("/confirm/"):])
        return None

    def do_GET(self) -> None:               # noqa: N802
        iid = self._incident_from_path()
        if iid:
            self._send(_form(self.store, iid))
        else:
            self._send(_index(self.store))

    def do_POST(self) -> None:              # noqa: N802
        iid = self._incident_from_path()
        if not iid:
            self._send(_index(self.store), 404)
            return
        n = int(self.headers.get("Content-Length") or 0)
        form = urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8"))

        def one(k: str) -> str:
            return (form.get(k) or [""])[0].strip()

        km: Optional[float]
        try:
            km = float(one("chainage_km")) if one("chainage_km") else None
        except ValueError:
            km = None
        c = Confirmation(
            incident_id=iid, tower_no=one("tower_no") or None, chainage_km=km,
            cause=one("cause"), confirmed_by=one("confirmed_by"),
            confidence=one("confidence"), notes=one("notes"))
        try:
            self.store.confirm(c)
            msg = "Recorded. Thank you -- this is what makes the accuracy figures real."
        except ValueError as exc:
            msg = "Not recorded: " + str(exc)
        self._send(_form(self.store, iid, msg))


def serve(store: Store, host: str = "0.0.0.0", port: int = 8080) -> ThreadingHTTPServer:
    """Threading server: a patrol engineer on a slow link must not block
    the next one. The store serialises its own access."""
    Handler.store = store
    return ThreadingHTTPServer((host, port), Handler)


def run(store: Store, host: str = "0.0.0.0", port: int = 8080) -> None:
    httpd = serve(store, host, port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
