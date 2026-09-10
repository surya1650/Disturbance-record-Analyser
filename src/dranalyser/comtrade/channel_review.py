"""Apply explicit channel identities before assembly, retaining original CFG labels."""
from collections import Counter


def channel_plan(cfg, naming, mapper, review):
    analog = review.get('analog', {})
    digital = review.get('digital', {})
    valid_ids = {f'A{i+1}' for i in range(cfg.n_analog)} | {f'D{i+1}' for i in range(cfg.n_digital)}
    if (set(analog) | set(digital)) - valid_ids:
        raise ValueError('Reviewed mapping names a channel position absent from this record.')
    targets, inventory, used = [], [], set()
    for i, ch in enumerate(cfg.analogs, 1):
        key = f'A{i}'
        automatic = mapper(ch.ch_id, ch.uu, ch.ph, naming)
        target = analog.get(key, automatic)
        if target == 'ignore':
            target = None
        if key in analog and target:
            if target not in ('IA', 'IB', 'IC', 'IN', 'VA', 'VB', 'VC', 'VN'):
                raise ValueError('Unknown reviewed analog target: '+str(target))
            units = ('A', 'KA') if target.startswith('I') else ('V', 'KV')
            if ch.uu.strip().upper() not in units:
                raise ValueError(key+': declared units do not establish the requested quantity; unit/ratio repair is unsupported.')
        if target and target in used:
            if analog:
                raise ValueError('Reviewed analog mapping collides at '+target+'; remap or explicitly ignore the other channel.')
            target = None
        if target:
            used.add(target)
        targets.append(target)
        inventory.append({'id': key, 'kind': 'analog', 'label': ch.ch_id.strip(),
                          'cfg_index': ch.index, 'unit': ch.uu, 'declared_phase': ch.ph,
                          'ps': ch.ps, 'primary': ch.primary, 'secondary': ch.secondary,
                          'automatic': automatic or '', 'selected': target or '', 'reviewed': key in analog})
    labels = [n.strip() for n in cfg.digitals]
    counts, reserved, keys, overrides = Counter(labels), set(labels), [], {}
    for i, label in enumerate(labels, 1):
        key = label if label and counts[label] == 1 else f'[D{i}] {label or "unnamed"}'
        if key != label:
            while key in reserved:
                key = '_'+key
        reserved.add(key)
        keys.append(key)
        source = f'D{i}'
        if source in digital:
            overrides[key] = digital[source]
        inventory.append({'id': source, 'kind': 'digital', 'label': label, 'key': key,
                          'selected': digital.get(source, ''), 'reviewed': source in digital})
    return targets, keys, inventory, overrides
