"""Explicit PRIMARY basis corrects S metadata before the one normalization step."""
import hashlib
from pathlib import Path

import numpy as np
import pytest

from dranalyser.application.worker import Worker
from dranalyser.comtrade.conformance import check
from dranalyser.comtrade.instrument_review import clean_instrument_review, review_digest
from dranalyser.comtrade.parser import read_cff, read_comtrade
from dranalyser.comtrade.source_observations import load_source
from dranalyser.workbench.ratio_inputs import required_ratios
from dranalyser.workbench.source_inspection import _source
from tests.test_application import environment as environment, payload
from scripts.create_demo import create_demo


@pytest.fixture
def synthetic(tmp_path):
    return create_demo(tmp_path/'synthetic')


def primary_review(path, channels):
    raw = path.read_bytes()
    identity = hashlib.sha256(raw if path.suffix == '.cff' else raw+path.with_suffix('.dat').read_bytes()).hexdigest()
    return dict(record_hash=identity, reviewer='Synthetic basis reviewer',
                evidence='Explicit declaration: the recorded gains produce primary quantities in the declared physical units.',
                basis='PRIMARY', confirmed_primary=True, primary_channels=channels)


def change_headers(path, transform):
    lines = path.read_text().splitlines()
    count = int(lines[1].split(',')[1][:-1])
    for i in range(2, 2+count):
        fields = lines[i].split(',')
        transform(fields, i-1)
        lines[i] = ','.join(fields)
    path.write_text('\n'.join(lines)+'\n')
    return count


@pytest.mark.parametrize(('cff', 'kilo', 'ratio'), [(False, False, 1), (True, False, 1), (False, True, 800)])
def test_explicit_primary_preserves_primary_values_and_original_declarations(synthetic, cff, kilo, ratio):
    path = synthetic/'S/event.cfg'
    oracle = read_comtrade(str(path))

    def misleading(fields, _):
        fields[10:13] = [str(ratio), '1', 'S']
        if kilo:
            fields[4] = 'K'+fields[4]
            fields[5] = str(float(fields[5])/1000)
    count = change_headers(path, misleading)
    if cff:
        combined = path.with_suffix('.cff')
        combined.write_bytes(b'--- file type: CFG ---\n'+path.read_bytes()+b'--- file type: DAT ASCII ---\n'+path.with_suffix('.dat').read_bytes())
        path = combined
    before = path.read_bytes()
    original = load_source(path)
    review = primary_review(path, [f'A{i}' for i in range(1, count+1)])
    effective = read_cff(str(path), instrument_review=review) if cff else read_comtrade(str(path), instrument_review=review)
    observed = load_source(path, instrument_review=review)
    check(effective, nominal_kv=220)
    assert not effective.blocked(), effective.flags
    assert effective.content_hash == review['record_hash'] == observed['content_hash']
    assert observed['recorded_header_inventory'] == original['header_inventory']
    assert path.read_bytes() == before
    assert not required_ratios(observed)
    assert observed['instrument_review'] == clean_instrument_review(review)
    assert observed['instrument_review_sha256'] == effective.notes['instrument_review_sha256']
    for key, values in oracle.analog.items():
        np.testing.assert_allclose(effective.analog[key], values, rtol=1e-12, atol=1e-8)
        channel = next(c for c in observed['channels'] if c['label'] == key)
        np.testing.assert_allclose(channel['values'], values, rtol=1e-12, atol=1e-8)
        assert 'PRIMARY-declared, unverified' in channel['units']
        assert effective.analog_meta[key].ps == 'P'
    for row in effective.notes['channel_inventory']:
        if row['kind'] == 'analog':
            assert row['ps'] == 'P' and row['recorded_ps'] == 'S'
            assert row['recorded_primary'] == ratio and row['recorded_secondary'] == 1
            assert row['measurement_basis'] == 'PRIMARY'
    assert any('overrides original CFG S' in str(flag) for flag in effective.flags)


@pytest.mark.parametrize(('unit', 'a', 'b', 'factor'), [('A', '-2', '7', 1), ('KV', '.5', '-3', 1000), ('KA', '2', '0', 1000)])
def test_signed_gains_and_offsets_apply_once_before_primary_units(synthetic, unit, a, b, factor):
    path = synthetic/'S/event.cfg'
    def change(fields, index):
        if index == 1:
            fields[4:7] = [unit, a, b]
            fields[10:13] = ['800', '1', 'S']
    change_headers(path, change)
    review = primary_review(path, ['A1'])
    native = read_comtrade(str(path), instrument_review=review)
    decoded = load_source(path, instrument_review=review)
    expected = (native.raw_analog['VA' if unit.endswith('V') else 'IA']*float(a)+float(b))*factor
    np.testing.assert_allclose(decoded['channels'][0]['values'], expected)
    # The changed physical unit may cause a native mapping collision; source A1
    # still retains an exact, independently decoded primary observation.
    selected = next(row for row in native.notes['channel_inventory'] if row['id'] == 'A1')['selected']
    if selected:
        np.testing.assert_allclose(native.analog[selected], expected)


@pytest.mark.parametrize(('field', 'value'), [(5, '0'), (5, '-0'), (5, 'nan'), (5, 'inf'), (5, ''), (5, 'unknown'),
                                           (6, ''), (6, 'unknown'), (6, 'nan'), (4, 'counts')])
def test_primary_does_not_invent_physical_units_or_gains(synthetic, field, value):
    path = synthetic/'S/event.cfg'
    def invalid(fields, index):
        if index == 1:
            fields[10:13] = ['1', '1', 'S']
            fields[field] = value
    change_headers(path, invalid)
    review = primary_review(path, ['A1'])
    with pytest.raises(ValueError, match='original S physical channels'):
        read_comtrade(str(path), instrument_review=review)
    decoded = load_source(path, instrument_review=review)
    assert decoded['status'] == 'unsupported' and not decoded['channels']


def test_primary_selection_rejects_declared_p_and_source_hash_mismatch(synthetic):
    path = synthetic/'S/event.cfg'
    original = read_comtrade(str(path))
    review = primary_review(path, ['A1'])
    with pytest.raises(ValueError, match='original S physical channels'):
        read_comtrade(str(path), instrument_review=review)
    # All already-primary values retain their original scale without a review.
    for key, values in original.analog.items():
        np.testing.assert_array_equal(read_comtrade(str(path)).analog[key], values)
    change_headers(path, lambda fields, _: fields.__setitem__(12, 'S'))
    with pytest.raises(ValueError, match='different original recording'):
        read_comtrade(str(path), instrument_review=review)
    review = primary_review(path, ['A999'])
    with pytest.raises(ValueError, match='original S physical channels'):
        read_comtrade(str(path), instrument_review=review)


def test_primary_review_keeps_unselected_ratio_and_independent_voltage_timing_gates(synthetic):
    path = synthetic/'S/event.cfg'
    change_headers(path, lambda fields, _: fields.__setitem__(slice(10, 13), ['1', '1', 'S']))
    partial = read_comtrade(str(path), instrument_review=primary_review(path, ['A1']))
    check(partial, nominal_kv=220)
    ratio_blocks = [flag for flag in partial.flags if flag.code == 'RATIO-PS']
    assert ratio_blocks and all('IA is flagged' not in str(flag) for flag in ratio_blocks)

    def voltage_error(fields, _):
        if fields[4] == 'V':
            fields[5] = str(float(fields[5])/2)
    count = change_headers(path, voltage_error)
    lines = path.read_text().splitlines()
    analogs, digitals = lines[1].split(',')[1:]
    rates = 2+int(analogs[:-1])+int(digitals[:-1])+1
    lines[rates] = '0'
    path.write_text('\n'.join(lines)+'\n')
    dat = path.with_suffix('.dat')
    rows = dat.read_text().splitlines()
    fields = rows[30].split(',')
    fields[1] = rows[29].split(',')[1]
    rows[30] = ','.join(fields)
    dat.write_text('\n'.join(rows)+'\n')
    reviewed = read_comtrade(str(path), instrument_review=primary_review(path, [f'A{i}' for i in range(1, count+1)]))
    check(reviewed, nominal_kv=220)
    assert reviewed.blocked()
    assert any(flag.code == 'TIME-DAT' and flag.severity == 'block' for flag in reviewed.flags)
    assert any(flag.code == 'RATIO-V' and flag.severity == 'block' for flag in reviewed.flags)
    assert not any(flag.code == 'RATIO-PS' for flag in reviewed.flags)


@pytest.mark.parametrize('problem', ['confirmation', 'basis', 'duplicate', 'empty', 'ratio', 'reviewer', 'evidence', 'extra'])
def test_primary_review_schema_is_explicit_and_bounded(problem):
    review = dict(record_hash='a'*64, reviewer='Synthetic reviewer', evidence='Explicit primary declaration.',
                  basis='PRIMARY', confirmed_primary=True, primary_channels=['A1'])
    if problem == 'confirmation':
        review['confirmed_primary'] = False
    elif problem == 'basis':
        review['basis'] = 'AUTO'
    elif problem == 'duplicate':
        review['primary_channels'].append('A1')
    elif problem == 'empty':
        review['primary_channels'] = []
    elif problem == 'ratio':
        review['ratios'] = {'A1': {'primary': 800, 'secondary': 1}}
    elif problem in ('reviewer', 'evidence'):
        review[problem] = ''
    else:
        review['confirmed_secondary'] = True
    with pytest.raises(ValueError):
        clean_instrument_review(review)


def test_legacy_secondary_normalization_and_digest_remain_unchanged():
    review = dict(record_hash='b'*64, reviewer='Synthetic reviewer', evidence='Actual transformer evidence.',
                  confirmed_secondary=True, ratios={'A2': dict(primary=220000, secondary=110), 'A1': dict(primary=800, secondary=1)})
    assert clean_instrument_review(review) == review
    assert review_digest(clean_instrument_review(review)) == review_digest(review)


def test_same_record_primary_edit_to_secondary_preserves_history_and_normalizes_original_source(environment):
    from dranalyser.workbench.source_models import SourceModelCache
    from dranalyser.workbench.source_diagnostics import diagnose_source
    client, app, source, registry = environment
    path = source/'S/event.cfg'
    oracle = read_comtrade(str(path))
    count = change_headers(path, lambda fields, _: fields.__setitem__(slice(10, 13), ['1', '1', 'S']))
    raw = path.read_bytes()
    response = client.post('/api/intake', files=payload(source), data={'name': 'Synthetic explicit primary basis'})
    assert response.status_code == 202, response.text
    identity = response.json()['incident_id']
    assert Worker(app.state.store, registry).once()
    before = app.state.store.get(identity)
    name, url = 'S/event.cfg', f'/api/incidents/{identity}/instrument-review'
    review = primary_review(path, [f'A{i}' for i in range(1, count+1)])
    request = dict(record=name, revision=1, review=review, save=True)
    requirements = client.get(url, params=dict(record=name, revision=1)).json()
    assert {h['id'] for h in requirements['primary_reviewable_channels']} == set(review['primary_channels'])
    assert requirements['applied_review_basis'] is None
    response = client.post(url, json=request)
    assert response.status_code == 200, response.text
    assert response.json()['reviewed_record'] == name and response.json()['revision'] == 2
    assert response.json()['applied_review_basis'] == 'PRIMARY'
    assert not response.json()['blocked']
    assert Worker(app.state.store, registry).once()
    after = app.state.store.get(identity)
    decoded, item = _source(app.state.store.root, after, name)
    assert not item['blocked'] and after['files'] == before['files']
    assert (Path(after['bundle']['root'])/name).read_bytes() == raw
    assert app.state.store.get(identity, 1) == before
    current = client.get(url, params=dict(record=name, revision=2)).json()
    assert not current['required_ratios']
    assert {h['id'] for h in current['reviewable_ratios']} == {h['id'] for h in requirements['reviewable_ratios']}
    assert current['applied_review_basis'] == 'PRIMARY'
    assert current['primary_reviewable_channels'] == requirements['primary_reviewable_channels']
    # Explicit copy/export is refused coherently; the same-source review is saved.
    assert client.post(url+'/export', json=dict(record=name, revision=2, review=review)).status_code == 400
    assert client.post(url, json=dict(record=name, revision=2, review=review, mode='copy')).status_code == 400
    stale = client.post(url, json=dict(record=name, revision=1, review=review, save=True))
    assert stale.status_code == 409
    # Switching mode reads original declarations, never composes with primary gains.
    secondary = dict(record_hash=review['record_hash'], reviewer=review['reviewer'], evidence='Explicit secondary reinterpretation for edit test.',
                     confirmed_secondary=True, ratios={key: dict(primary=2, secondary=1) for key in review['primary_channels']})
    response = client.post(url, json=dict(record=name, revision=2, review=secondary, save=True))
    assert response.status_code == 200, response.text
    assert Worker(app.state.store, registry).once()
    latest = app.state.store.get(identity)
    edited, _ = _source(app.state.store.root, latest, name)
    assert latest['files'] == before['files'] and app.state.store.get(identity, 2) == after
    for channel in edited['channels']:
        np.testing.assert_allclose(channel['values'], oracle.analog[channel['label']]*2)
    cache = SourceModelCache()
    first = diagnose_source(app.state.store.root, after, name, model_cache=cache)
    second = diagnose_source(app.state.store.root, latest, name, model_cache=cache)
    assert first['job_id'] != second['job_id']
    assert first['instrument_review_sha256'] != second['instrument_review_sha256']
    assert decoded['instrument_review']['confirmed_primary']
    assert client.get(url, params=dict(record=name, revision=3)).json()['applied_review_basis'] == 'SECONDARY'
    response = client.post(url, json=dict(record=name, revision=3, review=review, save=True))
    assert response.status_code == 200, response.text
    assert Worker(app.state.store, registry).once()
    restored, _ = _source(app.state.store.root, app.state.store.get(identity), name)
    assert restored['channels'] == decoded['channels']
    assert app.state.store.get(identity, 3) == latest
