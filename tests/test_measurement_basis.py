"""Independent synthetic scale evidence never supplies or applies CT/VT facts."""
from copy import deepcopy
import json
import math

import numpy as np
import pytest

from dranalyser.comtrade.source_decode import decode_source
from dranalyser.workbench.measurement_basis import measurement_basis_hint


def capture(voltage=75000., current=500., *, ps='S', ratio=(1, 1), a=1., b=0., kilo=False,
            times=None, rates=None, nrates=None, review=None):
    times = np.arange(121)/1000 if times is None else np.asarray(times)
    rates = ['1000,'+str(len(times))] if rates is None else rates
    header = ['Synthetic,Recorder,2013', '6,6A,0D']
    signals = []
    for index, name in enumerate(('VA', 'VB', 'VC', 'IA', 'IB', 'IC')):
        unit = ('V' if index < 3 else 'A')
        unit = 'K'+unit if kilo else unit
        primary, secondary = ratio if not isinstance(ratio, list) else ratio[index]
        header.append(f'{index+1},{name},{"ABC"[index%3]},,{unit},{a},{b},0,-1000000,1000000,{primary},{secondary},{ps}')
        engineering = math.sqrt(2)*(voltage if index < 3 else current)*np.cos(2*np.pi*50*times-index%3*2*np.pi/3)
        signals.append((engineering/(1000 if kilo else 1)-b)/a if a else engineering)
    header += ['50', str(len(rates) if nrates is None else nrates), *rates, '01/01/2020,00:00:00.000000',
               '01/01/2020,00:00:00.080000', 'ASCII', '1']
    dat = '\n'.join(','.join(map(str, [i+1, round(float(t)*1e6), *(s[i] for s in signals)]))
                    for i, t in enumerate(times)).encode()
    source = decode_source(('\n'.join(header)+'\n').encode(), dat, cfg_name='synthetic.cfg', dat_name='synthetic.dat')
    if review:
        source = decode_source(('\n'.join(header)+'\n').encode(), dat, cfg_name='synthetic.cfg', dat_name='synthetic.dat',
                               instrument_review=review(source['content_hash']))
    return source


def test_primary_sized_s_unity_is_a_supported_hint_and_never_changes_source():
    source = capture()
    before = deepcopy(source)
    result = measurement_basis_hint(source)
    assert result['status'] == 'primary_sized_hint'
    assert result['message'] == result['reason']
    assert 'inconsistent' in result['reason']
    assert result['support']['start_s'] == pytest.approx(0)
    assert result['support']['end_s'] == pytest.approx(.02)
    assert result['support']['sample_count'] == 20
    assert result['support']['first_sample_index'] == 1
    assert result['support']['observation'] == 'first complete source cycle'
    assert result['support']['prefault_established'] is False
    assert [c['rms'] for c in result['channels']] == pytest.approx([75000]*3+[500]*3)
    assert source == before
    assert not result['applies_automatically'] and not result['scaling_verified'] and not result['authorizes_location']
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize('voltage', [110, 110/math.sqrt(3)])
def test_secondary_sized_joint_evidence_is_a_hint_without_inferred_ratings(voltage):
    result = measurement_basis_hint(capture(voltage=voltage, current=1))
    assert result['status'] == 'secondary_sized_hint'
    assert 'hint only' in result['reason'] and 'no ratio is inferred' in result['reason']
    assert 'ratios' not in result
    assert [c['rms'] for c in result['channels']] == pytest.approx([voltage]*3+[1]*3)


def test_primary_voltage_and_light_current_do_not_suggest_secondary_ratings():
    assert measurement_basis_hint(capture(current=1))['status'] == 'primary_sized_hint'
    for voltage in (110, 110/math.sqrt(3), 10, 0):
        result = measurement_basis_hint(capture(voltage=voltage, current=.01))
        assert result['status'] == 'ambiguous'
        assert 'Low load' in result['reason']


def test_sag_or_collapsed_voltage_does_not_establish_a_secondary_basis():
    for voltage in (0, 5, 500, 3000):
        assert measurement_basis_hint(capture(voltage=voltage, current=1))['status'] == 'ambiguous'
    source = capture(voltage=110, current=1)
    for channel in source['channels'][:3]:
        channel['values'] = [110.]*len(channel['values'])
    assert measurement_basis_hint(source)['status'] == 'ambiguous'


@pytest.mark.parametrize('ps,ratio,expected', [('P', (132000, 110), 'cfg_primary'),
                                            ('P', (1, 0), 'cfg_primary'),
                                            ('S', (1200, 1), 'cfg_secondary')])
def test_existing_p_and_valid_nonunity_s_preserve_decoded_values_without_second_multiplication(ps, ratio, expected):
    source = capture(voltage=60, current=1, ps=ps, ratio=ratio)
    before = deepcopy(source)
    result = measurement_basis_hint(source)
    assert result['status'] == expected
    factor = ratio[0]/ratio[1] if ps == 'S' else 1
    assert [c['rms'] for c in result['channels']] == pytest.approx([60*factor]*3+[factor]*3)
    assert source == before


@pytest.mark.parametrize('kilo', [False, True])
def test_after_gain_and_unit_evidence_for_missing_s_ratio_is_not_raw_amplitude(kilo):
    source = capture(a=2, b=3, kilo=kilo, ratio=(1, 0))
    assert all(c['units'] == 'raw counts' for c in source['channels'])
    before = deepcopy(source)
    result = measurement_basis_hint(source)
    assert result['status'] == 'primary_sized_hint'
    assert [c['rms'] for c in result['channels']] == pytest.approx([75000]*3+[500]*3)
    assert source == before


def test_unknown_counts_or_malformed_gains_cannot_be_basis_evidence():
    for column, invalid in [('declared_units', 'counts'), ('a', '0'), ('a', 'nan'), ('a', '1e-999'), ('b', 'inf')]:
        source = capture(ratio=(1, 0))
        source['header_inventory'][0][column] = invalid
        result = measurement_basis_hint(source)
        assert result['status'] == 'ambiguous'
        assert result['channels'][0]['rms'] is None
    assert measurement_basis_hint({})['status'] == 'ambiguous'


@pytest.mark.parametrize('defect', ['unknown', 'gap', 'break', 'duplicate', 'frequency', 'axis', 'short', 'few'])
def test_incomplete_or_invalid_time_support_is_explicit_and_never_filled(defect):
    source = capture(voltage=110, current=1)
    times = source['axis']['elapsed_s']
    if defect == 'unknown':
        source['channels'][0]['values'][10] = None
    elif defect == 'gap':
        source['axis']['elapsed_s'] = [t+(1 if i >= 10 else 0) for i, t in enumerate(times)]
    elif defect == 'break':
        source['break_indices'] = [10]
    elif defect == 'duplicate':
        times[10] = times[9]
    elif defect == 'frequency':
        source['nominal_frequency_hz'] = True
    elif defect == 'axis':
        source['axis']['status'] = 'withheld'
    elif defect == 'short':
        source['axis']['elapsed_s'] = times[:10]
    else:
        source['axis']['elapsed_s'] = [0, .01, .02]
        for channel in source['channels']:
            channel['values'] = [110., 110., 110.]
    result = measurement_basis_hint(source)
    assert result['status'] == 'ambiguous'
    assert result['reason']


def test_multirate_actual_time_support_uses_native_samples_and_not_a_sample_count_cycle():
    times = np.r_[np.arange(11)/1000, .010+np.arange(1, 100)/1600]
    source = capture(voltage=110, current=1, times=times, rates=['0,110'], nrates=0)
    result = measurement_basis_hint(source)
    assert result['status'] == 'secondary_sized_hint'
    support = result['support']
    assert support['sample_count'] == 26
    assert support['end_s'] == pytest.approx(.02)
    for channel, row in zip(source['channels'], result['channels'], strict=True):
        values = [x for t, x in zip(times, channel['values'], strict=True) if .02-.02+1e-12 < t <= .02]
        assert row['rms'] == pytest.approx(math.hypot(*values)/math.sqrt(len(values)))


def test_declared_multirate_table_with_withheld_source_axis_remains_ambiguous():
    times = np.r_[np.arange(11)/1000, .010+np.arange(1, 100)/1600]
    source = capture(voltage=110, current=1, times=times, rates=['1000,11', '1600,110'])
    assert source['axis']['status'] == 'withheld'
    assert measurement_basis_hint(source)['status'] == 'ambiguous'


def test_reviewed_primary_records_original_s_and_suppresses_all_ratio_multiplication():
    def review(record_hash):
        return dict(record_hash=record_hash, reviewer='Synthetic engineer', evidence='Synthetic declared engineering units.',
                    basis='PRIMARY', confirmed_primary=True, primary_channels=['A'+str(i) for i in range(1, 7)])
    source = capture(ratio=(2000, 1), review=review)
    result = measurement_basis_hint(source)
    assert result['status'] == 'reviewed_primary'
    assert [c['rms'] for c in result['channels']] == pytest.approx([75000]*3+[500]*3)
    assert all(c['original_ps'] == 'S' and c['effective_ps'] == 'P' for c in result['channels'])


def test_reviewed_secondary_and_duplicate_phase_identity_do_not_get_amplitude_override():
    def review(record_hash):
        return dict(record_hash=record_hash, reviewer='Synthetic engineer', evidence='Synthetic actual ratings.',
                    confirmed_secondary=True, ratios={'A'+str(i): dict(primary=1200, secondary=1) for i in range(1, 7)})
    source = capture(voltage=60, current=1, ratio=(1, 0), review=review)
    result = measurement_basis_hint(source)
    assert result['status'] == 'reviewed_secondary'
    assert [c['rms'] for c in result['channels']] == pytest.approx([72000]*3+[1200]*3)
    source = capture()
    source['channels'][1]['meaning'] = 'VA'
    assert measurement_basis_hint(source)['status'] == 'ambiguous'


def test_first_cycle_is_not_renamed_prefault_without_supported_recorded_trigger():
    source = capture()
    source['recorded_times']['trigger'] = '01/01/2020,00:00:00.010000'
    result = measurement_basis_hint(source)
    assert result['support']['observation'] == 'first complete source cycle'
    assert result['support']['prefault_established'] is False


@pytest.mark.parametrize('skew', [None, 100, float('nan')])
def test_unknown_or_nonzero_channel_skew_is_not_joint_phase_support(skew):
    source = capture()
    source['channels'][0]['skew_us'] = skew
    result = measurement_basis_hint(source)
    assert result['status'] == 'ambiguous'
    assert result['channels'][0]['rms'] is None


@pytest.mark.parametrize('origin,observation', [(.03, 'before recorded trigger'),
                                              (.06, 'first complete source cycle'),
                                              (.10, 'first complete source cycle')])
def test_recorded_trigger_label_uses_original_dat_origin_before_comparing_cycle(origin, observation):
    source = capture(times=np.arange(121)/1000+origin, nrates=0)
    before = deepcopy(source)
    assert source['axis']['declared_origin']['first_offset_s'] == pytest.approx(origin)
    result = measurement_basis_hint(source)
    assert result['support']['start_s'] == pytest.approx(0)
    assert result['support']['end_s'] == pytest.approx(.02)
    assert result['support']['observation'] == observation
    assert result['support']['prefault_established'] is False
    assert source == before


@pytest.mark.parametrize('defect', ['missing', 'wrong_basis', 'unknown', 'synthetic_rate_axis'])
def test_unproven_dat_origin_cannot_label_the_cycle_before_recorded_trigger(defect):
    source = capture(nrates=0)
    if defect == 'missing':
        source['axis'].pop('declared_origin')
    elif defect == 'wrong_basis':
        source['axis']['declared_origin']['basis'] = 'Unproven zero origin'
    elif defect == 'unknown':
        source['axis']['declared_origin']['first_offset_s'] = None
    else:
        source = capture(times=np.arange(121)/1000+.1)
        assert source['axis']['declared_origin']['first_offset_s'] == 0
        assert source['axis']['basis'].startswith('Explicit single CFG sample rate;')
    result = measurement_basis_hint(source)
    assert result['support']['observation'] == 'first complete source cycle'
    assert result['support']['prefault_established'] is False
