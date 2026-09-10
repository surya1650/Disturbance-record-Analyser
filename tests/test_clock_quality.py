"""Source-declared quality must not gain unsupported synchronization precision."""
import pytest

from dranalyser.comtrade.parser import parse_cfg, read_comtrade
from dranalyser.dsp.clock_quality import clock_quality
from tests.test_stages import staged_waveform


@pytest.mark.parametrize('code,bound', [('1', 1e-9), ('4', 1e-6), ('7', .001), ('8', .01), ('A', 1), ('b', 10)])
def test_reported_bound_is_not_verified_uncertainty_or_alignment_permission(code, bound):
    rec = staged_waveform()
    rec.notes.update(tmq_code=code, time_code='0', local_code='+5h30', leapsec='0')
    out = clock_quality(rec)
    assert out['reported_error_bound_s'] == pytest.approx(bound)
    assert out['raw']['tmq_code'] == code
    assert out['uncertainty_s'] is None
    assert not out['verified'] and not out['alignment_eligible'] and not out['applied']


@pytest.mark.parametrize('code', ['', '0', 'F', 'C', 'D', 'E', '04', 'NaN', 'locked'])
def test_missing_locked_failed_and_unsupported_codes_never_imply_zero_error(code):
    rec = staged_waveform()
    rec.notes['tmq_code'] = code
    out = clock_quality(rec)
    assert out['reported_error_bound_s'] is None and out['uncertainty_s'] is None
    assert not out['alignment_eligible']
    if code == '0':
        assert 'accuracy unspecified' in out['status']
    elif code == 'F':
        assert 'failure' in out['status']


@pytest.mark.parametrize('leap', ['', '0', '1', '2', '3', '9'])
def test_leap_state_is_preserved_without_applying_a_timestamp_correction(leap):
    rec = staged_waveform()
    rec.notes.update(tmq_code='4', leapsec=leap)
    before = (rec.start_time, rec.trigger_time)
    out = clock_quality(rec)
    assert out['raw']['leapsec'] == leap and (rec.start_time, rec.trigger_time) == before
    assert not out['applied']
    assert any('Leap-second' in r for r in out['reasons']) == (leap != '0')


def test_parser_retains_all_four_timing_fields_in_cfg_and_record(tmp_path):
    cfg = '\n'.join(['S,R,2013', '1,1A,0D', '1,IA,A,,A,1,0,0,-32768,32767,1,1,P',
                     '50', '1', '1000,2', '01/01/2026,00:00:00.000000',
                     '01/01/2026,00:00:00.001000', 'ASCII', '1', '0,+5h30', '4,2'])+'\n'
    parsed = parse_cfg(cfg)
    assert (parsed.time_code, parsed.local_code, parsed.tmq_code, parsed.leapsec) == ('0', '+5h30', '4', '2')
    path = tmp_path/'clock.cfg'
    path.write_text(cfg, encoding='utf-8')
    path.with_suffix('.dat').write_text('1,0,1\n2,1000,2\n', encoding='utf-8')
    rec = read_comtrade(str(path))
    assert clock_quality(rec)['raw'] == {'time_code': '0', 'local_code': '+5h30', 'tmq_code': '4', 'leapsec': '2'}
    assert rec.content_hash
    assert rec.trigger_offset_s() == .001
