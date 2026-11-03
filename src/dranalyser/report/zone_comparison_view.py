"""Escaped presentation of stored zone geometry; never recompute a comparison."""
from .graphics import esc
from .rx_context import finite_number

RELATIONS = {'inside': 'Inside', 'outside': 'Outside', 'mixed': 'Mixed', 'not_evaluable': 'Not evaluable'}
NOTE = ('Exported boundary containment does not establish zone enablement, pickup, timer expiry, '
        'scheme behavior or correct protection operation. Counts are overlapping phasor supports, '
        'not independent measurements or confidence coverage.')


def render_zone_comparison(model, expected_hash=None):
    """Legacy or mismatched evidence remains unavailable, never an outside result."""
    heading = '<section class="zone-comparison" data-zone-comparison-version="1"><h3>Reviewed zone-boundary comparison</h3>'
    if not isinstance(model, dict) or type(model.get('version')) is not int or model['version'] != 1:
        return heading+'<p>Not evaluated in this stored revision. No boundary relation is inferred.</p></section>'
    if expected_hash and model.get('record_hash') != expected_hash:
        return heading+'<p>Not evaluable: the stored comparison does not match this recording.</p></section>'
    def number(value):
        return format(value, '.6g') if finite_number(value) else 'unavailable'

    def count(value):
        return str(value) if type(value) is int and value >= 0 else 'unavailable'

    def listing(values):
        return '<ul>'+''.join('<li>'+esc(value)+'</li>' for value in values)+'</ul>' if values else ''

    window = model.get('window') or {}
    html = (heading+'<p><strong>Fixed operational model window</strong> · classified loop '+esc(model.get('loop') or 'unavailable')+
            ' · '+esc(model.get('characteristic_kind') or 'kind unavailable')+' characteristic. Local '+
            number(window.get('t_start_s'))+' to '+number(window.get('t_end_s'))+' s; '+
            count(window.get('evaluated_count'))+' of '+count(window.get('support_count'))+
            ' complete phasor supports evaluated. Cursor, zoom and thinned display points do not change this comparison.</p>')
    rows = model.get('zones') or []
    if rows:
        html += '<table><thead><tr><th>Exported boundary</th><th>Geometric relation</th><th>Inside / outside / evaluated</th><th>Reason</th></tr></thead><tbody>'
        for row in rows:
            status = row.get('status') if model.get('status') == 'available' else 'not_evaluable'
            html += ('<tr><td>'+esc(row.get('name') or 'Unnamed boundary')+' · '+esc(row.get('kind') or 'unknown')+
                     '</td><td>'+RELATIONS.get(status, 'Not evaluable')+'</td><td>'+count(row.get('inside_count'))+' / '+
                     count(row.get('outside_count'))+' / '+count(row.get('evaluated_count'))+'</td><td>'+
                     esc('; '.join(str(reason) for reason in row.get('reasons', [])))+'</td></tr>')
        html += '</tbody></table>'
    else:
        html += '<p>Not evaluable: no supported exported boundary comparison is stored.</p>'
    html += listing(model.get('reasons', []))+listing(model.get('notes', []))
    html += ('<details><summary>Comparison source and input evidence</summary><p>Recording SHA-256 '+
             esc(model.get('record_hash') or 'unavailable')+'<br>Settings SHA-256 '+
             esc(model.get('settings_hash') or 'unavailable')+'</p></details><p>'+NOTE+'</p></section>')
    return html
