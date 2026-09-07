"""Server-rendered HTML for the workbench.

No JavaScript framework, no CDN, no build step: a substation PC may have no
outbound internet, and PROJECT_CONTEXT.md §12 requires the deployment to be
air-gap capable. Plain forms and plain CSS.
"""
from __future__ import annotations

import html
from typing import List, Optional

from .bundle import Bundle, BundleFile
from .incident import IncidentResult

CSS = """
*{box-sizing:border-box}
body{font-family:system-ui,Segoe UI,Helvetica,Arial,sans-serif;margin:0;
background:#f4f6f8;color:#1b2733}
.wrap{max-width:1000px;margin:0 auto;padding:18px 16px 60px}
h1{font-size:20px;margin:0 0 2px} h2{font-size:15px;margin:26px 0 8px}
.sub{color:#6b7885;font-size:13px}
.card{background:#fff;border:1px solid #dde3e9;border-radius:8px;
padding:14px 16px;margin:14px 0}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid #eceff2;
vertical-align:top}
th{color:#6b7885;font-weight:600;font-size:12px;text-transform:uppercase;
letter-spacing:.03em}
code,.mono{font-family:ui-monospace,Consolas,monospace;font-size:12px}
.tag{display:inline-block;padding:1px 7px;border-radius:10px;font-size:11px;
font-weight:600}
.ok{background:#e3f5e8;color:#1d6b34} .bad{background:#fde4e4;color:#8f2020}
.warn{background:#fdf1dc;color:#8a5a10} .mute{background:#eceff2;color:#5a6773}
.flag{font-size:12px;color:#6b7885;margin:2px 0 0}
.flag.block{color:#8f2020}
button,input[type=submit]{background:#1b4f8f;color:#fff;border:0;
border-radius:6px;padding:9px 16px;font-size:14px;cursor:pointer}
select,input[type=text],input[type=file]{font-size:13px;padding:5px 6px;
border:1px solid #c7d0d9;border-radius:5px;background:#fff}
.err{background:#fdf1dc;border:1px solid #e6c98a;border-radius:6px;
padding:10px 12px;margin:10px 0;font-size:13px}
.err.hard{background:#fdeaea;border-color:#e6a3a3}
a{color:#1b4f8f}
.note{font-size:12px;color:#6b7885;margin-top:8px}
"""


def _e(v: object) -> str:
    return html.escape(str(v if v is not None else ""))


def _page(title: str, body: str) -> str:
    return ('<!DOCTYPE html><html><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            "<title>" + _e(title) + "</title><style>" + CSS + "</style></head>"
            '<body><div class="wrap">' + body + "</div></body></html>")


def upload_page(bundles: List[str], message: str = "") -> str:
    rows = "".join('<tr><td><a href="/bundle/' + _e(b) + '">' + _e(b)
                   + "</a></td></tr>" for b in bundles)
    recent = ('<div class="card"><h2>Bundles on this machine</h2><table>'
              + rows + "</table></div>") if rows else ""
    return _page("DR workbench", """
<h1>Disturbance record workbench</h1>
<div class="sub">One fault is one incident. Upload every record for the same
fault together &mdash; both ends, and Main-1 and Main-2 at each end.</div>
""" + (('<div class="err">' + _e(message) + "</div>") if message else "") + """
<div class="card">
  <form method="post" action="/upload" enctype="multipart/form-data">
    <h2>Upload</h2>
    <p class="sub">A <code>.zip</code> of the fault's folder is the easiest
    path. Otherwise select every file, and remember a COMTRADE record is a
    <code>.cfg</code> <b>and</b> its <code>.dat</code> &mdash; a .cfg on its own
    cannot be read.</p>
    <p><input type="file" name="files" multiple required></p>
    <p><label class="sub">Bundle name (optional)
       <input type="text" name="bundle_id" placeholder="e.g. 15665-grv-mrd-1"></label></p>
    <p><input type="submit" value="Upload and describe"></p>
  </form>
  <p class="note">Nothing is analysed yet. The next page lists what was read
  from each file, and you say which end each record belongs to.</p>
</div>
""" + recent)


def _state_tag(f: BundleFile) -> str:
    if f.kind == "settings":
        return '<span class="tag mute">settings</span>'
    if not f.ok:
        return '<span class="tag bad">unreadable</span>'
    if f.duplicate_of:
        return '<span class="tag warn">duplicate</span>'
    if f.blocked:
        return '<span class="tag bad">blocked</span>'
    return '<span class="tag ok">usable</span>'


def _assign_cell(f: BundleFile) -> str:
    if not f.usable:
        return '<span class="sub">&mdash;</span>'
    opts = ""
    for val, label in (("", "unassigned"), ("S", "end S"), ("R", "end R")):
        sel = " selected" if f.terminal_end == val else ""
        opts += '<option value="' + val + '"' + sel + ">" + label + "</option>"
    roles = ""
    for val, label in (("primary", "primary"), ("corroborating", "corroborating")):
        sel = " selected" if f.role == val else ""
        roles += '<option value="' + val + '"' + sel + ">" + label + "</option>"
    key = _e(f.name)
    return ('<select name="end::' + key + '">' + opts + "</select> "
            '<select name="role::' + key + '">' + roles + "</select>")


def bundle_page(b: Bundle, line_files: List[str], refusals: List[str],
                message: str = "") -> str:
    rows = ""
    for f in b.files:
        detail = ""
        if f.ok and f.kind == "comtrade":
            detail = ('<div class="sub">' + _e(f.station or "(no station name)")
                      + " &middot; " + format(f.fs_hz, ".1f") + " Hz &middot; "
                      + _e(f.samples) + " samples &middot; trigger "
                      + _e(f.trigger_time or "-") + "</div>")
        if f.error:
            detail += '<div class="flag block">' + _e(f.error) + "</div>"
        if f.duplicate_of:
            detail += ('<div class="flag">byte-identical to '
                       + _e(f.duplicate_of) + "</div>")
        for fl in f.flags:
            cls = "flag block" if fl.startswith("[BLOCK") else "flag"
            detail += '<div class="' + cls + '">' + _e(fl) + "</div>"
        rows += ("<tr><td>" + _state_tag(f) + "</td><td><span class='mono'>"
                 + _e(f.name) + "</span>" + detail + "</td><td>"
                 + _assign_cell(f) + "</td></tr>")

    lines = '<option value="">no line definition (no distance)</option>'
    for p in line_files:
        sel = " selected" if b.line_id and b.line_id in p else ""
        lines += '<option value="' + _e(p) + '"' + sel + ">" + _e(p) + "</option>"

    refused = ""
    if refusals:
        refused = ('<div class="err hard"><b>Refused, nothing was changed:</b><ul>'
                   + "".join("<li>" + _e(r) + "</li>" for r in refusals)
                   + "</ul></div>")

    return _page("Bundle " + b.bundle_id, """
<h1>Bundle """ + _e(b.bundle_id) + """</h1>
<div class="sub mono">""" + _e(b.root) + """</div>
""" + (('<div class="err">' + _e(message) + "</div>") if message else "") + refused + """
<div class="card">
<form method="post" action="/bundle/""" + _e(b.bundle_id) + """/assign">
  <h2>What was read from each file</h2>
  <table><tr><th>state</th><th>file</th><th>terminal</th></tr>
  """ + rows + """</table>
  <p class="note">Nothing here is inferred. The station name in a CFG header is
  evidence, not authority &mdash; on this fleet one Garividi record names its
  station <code>MARADAM 2</code> and another names <code>BRAHMANAKOTKUR</code>.
  You decide which end each record is, and that decision is recorded as yours.</p>

  <h2>Incident</h2>
  <p><label class="sub">Line id
     <input type="text" name="line_id" value=\"""" + _e(b.line_id) + """\"
     placeholder="e.g. GRV-MRD-1"></label></p>
  <p><label class="sub">Line definition (needed for a distance in km)<br>
     <select name="line_path">""" + lines + """</select></label></p>
  <p><input type="submit" value="Analyse as one incident"></p>
</form>
</div>
<p><a href="/">&larr; upload another</a></p>
""")


def incident_page(b: Bundle, res: IncidentResult,
                  report_url: Optional[str]) -> str:
    used = "".join("<tr><td>end " + _e(e) + "</td><td class='mono'>" + _e(n)
                   + "</td></tr>" for e, n in sorted(res.used.items()))
    excluded = "".join("<li>" + _e(x) + "</li>" for x in res.excluded)
    errors = "".join('<div class="err hard">' + _e(x) + "</div>"
                     for x in res.errors)
    embed = ('<div class="card"><h2>The report</h2>'
             '<p><a href="' + _e(report_url) + '" target="_blank">'
             "open the two-page incident report</a> &middot; "
             '<span class="mono">' + _e(res.report_path) + "</span></p>"
             '<iframe src="' + _e(report_url) + '" style="width:100%;height:70vh;'
             'border:1px solid #dde3e9;border-radius:6px;background:#fff">'
             "</iframe></div>") if report_url else ""

    return _page("Incident " + (res.incident_id or b.bundle_id), """
<h1>Incident """ + _e(res.incident_id or b.bundle_id) + """</h1>
<div class="sub">One fault, """ + _e(len(b.records())) + """ record(s) attached,
""" + _e(len(res.used)) + """ used for the estimate.</div>
""" + errors + """
<div class="card">
  <h2>Outcome</h2>
  <table>
    <tr><td>verdict</td><td><b>""" + _e(res.verdict) + """</b></td></tr>
    <tr><td>location</td><td>""" + _e(res.location_text) + """</td></tr>
  </table>
  <h2>Records that drove the estimate</h2>
  <table>""" + (used or "<tr><td class='sub'>none</td></tr>") + """</table>
""" + ("<h2>Attached but not used</h2><ul class='sub'>" + excluded + "</ul>"
       if excluded else "") + """
  <p class="note">Every file you uploaded is listed somewhere on this page.
  Nothing was dropped silently.</p>
</div>
""" + embed + """
<p><a href="/bundle/""" + _e(b.bundle_id) + """">&larr; change the assignment</a>
&middot; <a href="/">upload another</a></p>
""")
