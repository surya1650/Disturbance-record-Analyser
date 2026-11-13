"""Source catalogue browsing and explicit provisional-registry drafts."""
from fastapi import HTTPException, Query

from ..registry.catalogue import reciprocal_candidates
from ..registry.catalogue_io import review_template
from ..registry.catalogue_review import reviewed_line
from ..registry.catalogue_store import active_envelope
from .catalogue_import import install_catalogue_import


def install_catalogue(app, root):
    install_catalogue_import(app, root)

    def load():
        envelope = active_envelope(root)
        if envelope is None:
            raise HTTPException(404, 'No source catalogue imported into this workspace.')
        return envelope

    @app.get('/api/catalogue')
    def catalogue(q: str = Query('', max_length=200), offset: int = Query(0, ge=0),
                  limit: int = Query(50, ge=1, le=200), errors_only: bool = False,
                  circle: str = Query('', max_length=200), station: str = Query('', max_length=200),
                  kind: str = Query('', pattern='^(|TL|PTR)$')):
        envelope = active_envelope(root)
        if envelope is None:
            return {'available': False, 'items': [], 'total': 0,
                    'facets': {'circles': [], 'stations': [], 'kinds': []}}
        cat = envelope['catalogue']
        query = q.casefold().split()
        def row_circle(row):
            return row.get('circle', row['sheet'].removesuffix(' TL'))
        rows = [r for r in cat['rows'] if (not circle or row_circle(r) == circle)
                and (not station or r['station'] == station)
                and (not kind or r.get('kind', 'TL') == kind)
                and all(word in ' '.join(str(r.get(k, '')) for k in
                    ('station', 'feeder', 'bus_id', 'bus_number', 'reference', 'relay', 'sheet', 'kv', 'transformer_capacity')).casefold()
                    for word in query)
                and (not errors_only or any(i['severity'] == 'error' for i in r['issues']))]
        keys = ('id', 'station', 'feeder', 'kv', 'length_km', 'bus_id', 'bus_number', 'sheet', 'row',
                'url', 'reference', 'reference_date', 'relay', 'electrical_values_parseable',
                'transformer_capacity', 'inventory_only', 'source_locator')
        return {'available': True, 'source': cat['source'], 'summary': cat['summary'],
                'catalogue_hash': envelope['catalogue_hash'], 'limits': cat['limits'], 'total': len(rows),
                'facets': {'circles': sorted({row_circle(r) for r in cat['rows']}),
                           'stations': sorted({r['station'] for r in cat['rows'] if r['station']
                                               and (not circle or row_circle(r) == circle)}),
                           'kinds': sorted({r.get('kind', 'TL') for r in cat['rows']})},
                'items': [{**{k: r.get(k) for k in keys}, 'kind': r.get('kind', 'TL'),
                           'circle': row_circle(r), 'issue_count': len(r['issues'])} for r in rows[offset:offset+limit]]}

    @app.get('/api/catalogue/review-template')
    def template():
        return review_template(load())

    @app.post('/api/catalogue/registry-draft')
    def draft(review: dict):
        return reviewed_line(load()['catalogue'], review)

    @app.get('/api/catalogue/rows/{row_id}')
    def row(row_id: str):
        envelope = load()
        cat = envelope['catalogue']
        selected = next((r for r in cat['rows'] if r['id'] == row_id), None)
        if selected is None:
            raise HTTPException(404, 'Source row not found.')
        return {**selected, 'catalogue_hash': envelope['catalogue_hash'],
                'reciprocal_candidates': reciprocal_candidates(cat, row_id)}
