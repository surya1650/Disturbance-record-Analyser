"""Read-only source catalogue and explicit provisional-registry draft endpoint."""
from pathlib import Path

from fastapi import HTTPException, Query

from ..registry.catalogue import reciprocal_candidates
from ..registry.catalogue_io import read_catalogue, review_template
from ..registry.catalogue_review import reviewed_line


def install_catalogue(app, root):
    path = Path(root)/'source-catalogue.json'

    def load():
        if not path.is_file():
            raise HTTPException(404, 'No source catalogue imported into this workspace.')
        return read_catalogue(path)

    @app.get('/api/catalogue')
    def catalogue(q: str = Query('', max_length=200), offset: int = Query(0, ge=0),
                  limit: int = Query(50, ge=1, le=200), errors_only: bool = False):
        if not path.is_file():
            return {'available': False, 'items': [], 'total': 0}
        envelope = load()
        cat = envelope['catalogue']
        query = q.casefold().split()
        rows = [r for r in cat['rows'] if all(word in ' '.join(str(r.get(k, '')) for k in
                ('station', 'feeder', 'bus_id', 'bus_number', 'reference', 'relay', 'sheet', 'kv')).casefold()
                for word in query) and (not errors_only or not r['electrical_values_parseable'])]
        keys = ('id', 'station', 'feeder', 'kv', 'length_km', 'bus_id', 'bus_number', 'sheet', 'row',
                'url', 'reference', 'reference_date', 'relay', 'electrical_values_parseable')
        return {'available': True, 'source': cat['source'], 'summary': cat['summary'],
                'catalogue_hash': envelope['catalogue_hash'], 'limits': cat['limits'], 'total': len(rows),
                'items': [{**{k: r[k] for k in keys}, 'issue_count': len(r['issues'])} for r in rows[offset:offset+limit]]}

    @app.get('/api/catalogue/review-template')
    def template():
        return review_template(load())

    @app.post('/api/catalogue/registry-draft')
    def draft(review: dict):
        return reviewed_line(load()['catalogue'], review)

    @app.get('/api/catalogue/rows/{row_id}')
    def row(row_id: str):
        cat = load()['catalogue']
        selected = next((r for r in cat['rows'] if r['id'] == row_id), None)
        if selected is None:
            raise HTTPException(404, 'Source row not found.')
        return {**selected, 'reciprocal_candidates': reciprocal_candidates(cat, row_id)}
