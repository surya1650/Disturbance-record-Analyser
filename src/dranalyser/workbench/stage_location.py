"""Stage estimates from current source-bound reviews at selected S/R primaries."""
from ..faultloc.stage_location import stage_e5


def stage_locations(line, analyses, evidence, used):
    selected = {end: next((r for r in evidence if r['file'] == name), {}) for end, name in used.items()}
    group_maps = {end: r.get('stages', {}).get('reviewed_groups', {}) for end, r in selected.items()}
    groups = sorted({g for mapping in group_maps.values() for g in mapping.values()})
    results = []
    for group in groups:
        out = {'group': group, 'status': 'withheld', 'method': 'E5', 'm': None, 'km_from_S': None,
               'reason': '', 'windows': {}, 'sources': {}, 'clock_shift_applied': False, 'caveats': []}
        for end, r in selected.items():
            stages = r.get('stages', {})
            out['sources'][end] = {'file': r['file'], 'record_hash': r.get('record_hash'),
                                   'inventory_hash': stages.get('inventory_hash'),
                                   'reviewer': stages.get('review', {}).get('reviewer'),
                                   'stage_id': next((s for s, g in group_maps[end].items() if g == group), None)}
        results.append(out)
        if line is None:
            out['reason'] = 'Line definition unavailable; no electrical distance computed.'
        elif set(analyses) != {'S', 'R'} or any(group not in group_maps.get(e, {}).values() for e in ('S', 'R')):
            out['reason'] = 'Matching reviewed group required at both selected terminal primaries.'
        elif any(selected[e]['stages'].get('review_status') != 'valid reviewer declaration' for e in ('S', 'R')):
            out['reason'] = 'A current source-bound stage review is unavailable.'
        elif any(not selected[e]['stages'].get('review', {}).get('location_requested') for e in ('S', 'R')):
            out['reason'] = 'Explicit stage-location permission is required at both terminal primaries.'
        else:
            stages = {e: next(s for s in selected[e]['stages']['intervals'] if s['id'] == out['sources'][e]['stage_id'])
                      for e in ('S', 'R')}
            out.update(stage_e5(line, analyses['S'], analyses['R'], stages['S'], stages['R'],
                                line.terminals['S'].i_polarity, line.terminals['R'].i_polarity))
    return results
