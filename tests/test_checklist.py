"""Source-table coverage, honest missing evidence and per-record settings association."""
import datetime as dt
import hashlib

import numpy as np
import pytest

from dranalyser.registry.settings_io.rio import parse_rio
from dranalyser.standards.audit import audit_record, audit_settings
from dranalyser.standards.checklist import reference_pack, relay_checklist
from dranalyser.standards.recording import recording_points
from dranalyser.workbench.audits import audit_bundle
from dranalyser.workbench.bundle import Bundle, BundleFile
from dranalyser.workbench.settings import settings_by_record, settings_for
from tests.test_settings import RIO_FIXTURE
from tests.test_standards import _record


@pytest.mark.parametrize('profile,count,last', [('wg3-132-distance', 32, 'WG3-T5-32'),
                                               ('wg3-132-backup', 14, 'WG3-T8-14'),
                                               ('wg3-220plus-distance', 42, 'WG3-T11-42')])
def test_full_base_table_row_counts_and_source_locators(profile, count, last):
    out = recording_points(_record(), profile)
    assert len(out['points']) == count
    assert out['points'][-1]['id'] == last
    assert all(p['source_id'] == 'fold-wg3-final-report' and 'row ' in p['source'] for p in out['points'])
    if count == 42:
        assert out['points'][30]['title'] == 'Earth fault operated'
        assert out['points'][31]['title'] == 'CB R phase close'
        assert out['points'][17]['title'] == 'AR switch in/out'
    if count == 14:
        assert not any('Zone' in p['title'] for p in out['points'])


def test_general_trip_and_carrier_send_do_not_complete_phase_zone_or_receive_points():
    rec = _record()
    rec.digital = {'Any Trip': np.zeros(rec.n), 'Carrier Send': np.zeros(rec.n)}
    out = recording_points(rec, 'wg3-220plus-distance')['points']
    assert all(p['status'] == 'gap' for p in out[:3])
    assert next(p for p in out if p['title'] == 'Zone 1 trip')['status'] != 'pass'
    assert next(p for p in out if p['title'] == 'Carrier send')['status'] == 'pass'
    assert next(p for p in out if p['title'] == 'Carrier receive')['status'] == 'gap'
    assert next(p for p in out if p['title'] == 'Carrier unhealthy/fail')['status'] == 'gap'


def test_trip_qualified_point_is_not_a_pickup_and_other_relay_health_is_not_guessed():
    rec = _record()
    rec.digital = {'Zone 1 Trip': np.zeros(rec.n), 'Main1 Relay Fail': np.zeros(rec.n)}
    rows = recording_points(rec, 'wg3-132-distance')['points']
    assert rows[0]['status'] == 'gap'
    assert rows[4]['status'] == 'pass'  # exact standardized label
    assert rows[29]['status'] == 'not_evaluable'  # table asks for the other relay/BCU


@pytest.mark.parametrize('bad', ['multiple', 'length', 'nonboolean'])
def test_ambiguous_or_invalid_digital_evidence_does_not_pass(bad):
    rec = _record()
    rec.digital = {'Carrier Send': np.zeros(rec.n)}
    if bad == 'multiple':
        rec.digital['Carrier Send Ch2'] = np.zeros(rec.n)
    elif bad == 'length':
        rec.digital['Carrier Send'] = np.zeros(3)
    else:
        rec.digital['Carrier Send'][10] = 2
    rows = recording_points(rec, 'wg3-220plus-distance')['points']
    assert next(p for p in rows if p['title'] == 'Carrier send')['status'] == 'not_evaluable'


@pytest.mark.parametrize('offset', [-1, 9, None])
def test_invalid_trigger_produces_unknown_duration_not_an_apparent_pass(offset):
    rec = _record()
    rec.trigger_time = rec.start_time + dt.timedelta(seconds=offset) if offset is not None else None
    checks = {c.id: c for c in audit_record(rec).checks}
    assert checks['DR-PRE'].status == checks['DR-POST'].status == 'not_evaluable'


def test_pre_capture_counts_from_first_sample_not_an_uncaptured_time_origin():
    rec = _record()
    rec.t += .2
    check = next(c for c in audit_record(rec).checks if c.id == 'DR-PRE')
    assert check.status == 'gap' and check.actual == '300.0 ms'


@pytest.mark.parametrize('zone_name', ['Z2', 'z2', 'Z2 '])
def test_omitted_timer_and_reverse_characteristic_are_unknown_not_default_zero_or_disabled(zone_name):
    settings = parse_rio(f'DEVICE test\nBEGIN ZONE\nNAME {zone_name}\nEND ZONE\n')
    assert 'zone.' + zone_name.strip() + '.time1' in settings.unknown
    checks = {c.id: c for c in audit_settings(settings).checks}
    assert checks['SET-Z2-TIME'].status == checks['SET-REVERSE'].status == 'not_evaluable'
    explicit = parse_rio('DEVICE test\nBEGIN ZONE\nNAME Z2\nTIME1 0.0\nEND ZONE\n')
    assert next(c for c in audit_settings(explicit).checks if c.id == 'SET-Z2-TIME').status == 'gap'


def test_unknown_profile_settings_dates_and_catalogued_guidance_never_become_compliance():
    row = relay_checklist(_record(), None, {'reason': 'not supplied'})
    assert row['digital_profile']['points'] == []
    assert any(c['id'] == 'DR-PROFILE' and c['status'] == 'not_evaluable' for c in row['recording_checks'])
    assert all(c['status'] == 'not_evaluable' for c in row['settings_checks'] + row['guidance'])
    assert row['recording_summary']['status'] == row['settings_summary']['status'] == 'INCOMPLETE'
    assert all(s['id'] != 'cigre-tb854' for s in reference_pack())
    assert len(reference_pack()) == 4


@pytest.mark.parametrize('replacement', ['', 'LINEANGLE\n', 'LINEANGLE unavailable\n'])
def test_missing_line_angle_cannot_pass_compensation_parameter_check(replacement):
    settings = parse_rio(RIO_FIXTURE.replace('LINEANGLE 80.0\n', replacement))
    assert 'line_angle_deg' in settings.unknown
    assert next(c for c in audit_settings(settings).checks if c.id == 'SET-K0').status == 'not_evaluable'


def test_multirate_representative_rate_does_not_prove_all_segments_meet_minimum():
    rec = _record()
    rec.nrates = 2
    assert rec.fs >= 1000
    assert next(c for c in audit_record(rec).checks if c.id == 'DR-SAMPLE').status == 'not_evaluable'


def make_bundle(tmp_path, names, exports):
    files = [BundleFile(n, 'comtrade', True) for n in names]
    for name in exports:
        path = tmp_path/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(RIO_FIXTURE.replace('\n', '\r\n').encode())
        files.append(BundleFile(name, 'settings', True))
    return Bundle('test', str(tmp_path), files=files)


def test_four_settings_exports_stay_with_own_relays_and_original_file_hash(tmp_path):
    names = [f'{e}/{s}/event.cfg' for e in ('S', 'R') for s in ('Main-1', 'Main-2')]
    bundle = make_bundle(tmp_path, names, [n.replace('.cfg', '.rio') for n in names])
    found, info, errors = settings_by_record(bundle, names[::-1])
    assert not errors and set(found) == set(names)
    for n in names:
        source = n.replace('.cfg', '.rio')
        assert info[n]['file'] == source
        assert info[n]['sha256'] == hashlib.sha256((tmp_path/source).read_bytes()).hexdigest()
        assert info[n]['effective_at_event'] == 'unconfirmed'
    primaries, errors = settings_for(bundle, {'S': names[1], 'R': names[3]})
    assert not errors and all('Main-2' in s.source_path for s in primaries.values())


def test_shared_folder_export_is_not_lent_to_two_relays_but_explicit_stems_work(tmp_path):
    names = ['S/a.cfg', 'S/b.cfg']
    bundle = make_bundle(tmp_path, names, ['S/shared.rio'])
    found, info, errors = settings_by_record(bundle, names)
    assert not found and errors and all(s['status'] == 'ambiguous' for s in info.values())
    bundle = make_bundle(tmp_path, names, ['S/a.rio', 'S/b.rio'])
    found, info, errors = settings_by_record(bundle, names)
    assert not errors and info['S/a.cfg']['file'] == 'S/a.rio' and info['S/b.cfg']['file'] == 'S/b.rio'


def test_multiple_versions_and_unsupported_exports_stay_visible(tmp_path):
    names = ['S/a.cfg']
    bundle = make_bundle(tmp_path, names, ['S/v1.rio', 'S/v2.rio'])
    found, info, _ = settings_by_record(bundle, names)
    assert not found and info[names[0]]['status'] == 'ambiguous'
    bundle = make_bundle(tmp_path, names, ['S/settings.xml'])
    found, info, _ = settings_by_record(bundle, names)
    assert not found and info[names[0]]['status'] == 'unsupported format'
    assert info[names[0]]['unsupported_files'] == ['S/settings.xml']


def test_blocked_record_is_audited_without_clearing_block(tmp_path):
    bundle = make_bundle(tmp_path, ['S/a.cfg'], [])
    bundle.files[0].blocked = True
    bundle.files[0].flags = ['[BLOCK test] original block']
    _, info, _ = settings_by_record(bundle, ['S/a.cfg'])
    out = audit_bundle(bundle, {'S/a.cfg': _record()}, {}, info)[0]
    assert out['blocked'] and out['quality_flags'] == bundle.files[0].flags
    assert out['recording_checks'] and bundle.files[0].blocked
