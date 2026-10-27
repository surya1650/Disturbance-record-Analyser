"""Actual DSP supports and adversarial gaps in scalar observability evidence."""
import copy
import importlib
import json

import numpy as np
import pytest

from dranalyser.dsp.pipeline import analyse
from dranalyser.faultloc.ensemble import TerminalInput
from tests.source_fault_records import records


@pytest.fixture
def terms():
    pair = records([(120, .055+.33j, .22+.91j)], 37, 'AG', resistance=3, rotation=.79)
    return {end: TerminalInput(analyse(rec), end) for end, rec in pair.items()}


def assess(terms, fault='AG'):
    result = importlib.import_module('dranalyser.faultloc.scalar_quality').scalar_observability(terms, fault=fault)
    assert result['authorizes_location'] is False
    json.dumps(result, allow_nan=False)
    return result


def test_actual_independent_clean_dsp_can_pass_necessary_screen_without_authority(terms):
    before = copy.deepcopy(terms['S'].analysed.ps.phasors['I2'])
    result = assess(terms)
    assert result['status'] == 'candidate_pass'
    assert set(result['terminals']) == {'S', 'R'}
    assert result['terminals']['S']['support_count'] > 24
    np.testing.assert_array_equal(terms['S'].analysed.ps.phasors['I2'], before)


@pytest.mark.parametrize('fault', ['ABC', 'ABCG', 'NONE', 'invalid', None, ['AG']])
def test_balanced_or_unknown_fault_does_not_acquire_negative_sequence_authority(terms, fault):
    assert assess(terms, fault)['status'] == 'withheld'


@pytest.mark.parametrize('polarity', [True, False, 0, 2, .5, float('nan')])
def test_invalid_polarity_is_not_an_implicit_measurement_correction(terms, polarity):
    terms['S'].polarity = polarity
    assert assess(terms)['status'] == 'withheld'


@pytest.mark.parametrize('problem', ['saturation', 'unknown_saturation', 'clipping', 'blocked',
    'multirate', 'nan_time', 'nonuniform', 'nyquist', 'missing_stream', 'short_stream',
    'missing_metadata', 'unnormalized', 'nonfinite_between_picks', 'weak_between_picks', 'no_window'])
def test_bad_or_unobserved_support_never_disappears_in_downsampling(terms, problem):
    an = terms['S'].analysed
    ids = an.indices()
    skipped = ids[1]
    if problem == 'saturation':
        an.saturation.detected = True
    elif problem == 'unknown_saturation':
        an.saturation.detected = None
    elif problem == 'clipping':
        an.clipping = ['IA']
    elif problem == 'blocked':
        an.record.add_flag('TEST', 'block', 'Invalid acquisition')
    elif problem == 'multirate':
        an.record.nrates = 2
    elif problem == 'nan_time':
        an.record.t[0] = np.nan
    elif problem == 'nonuniform':
        an.record.t[4] += .2/an.record.fs
    elif problem == 'nyquist':
        an.freq = an.record.fs/2
    elif problem == 'missing_stream':
        del an.ps.phasors['IC']
    elif problem == 'short_stream':
        an.ps.phasors['I2'] = an.ps.phasors['I2'][:-1]
    elif problem == 'missing_metadata':
        del an.record.analog_meta['IA']
    elif problem == 'unnormalized':
        an.record.analog_meta['IA'].normalised = False
    elif problem == 'nonfinite_between_picks':
        an.ps.phasors['I2'][skipped] = np.nan
    elif problem == 'weak_between_picks':
        an.ps.phasors['I2'][skipped] = 0
    else:
        an.window.mode = 'none'
    assert assess(terms)['status'] == 'withheld'


def test_section_floor_is_applied_to_every_support_at_both_terminals(terms):
    for ti in terms.values():
        ti.analysed.ps.phasors['I1'][:] = 1000
        ti.analysed.ps.phasors['I2'][:] = 10
    assert assess(terms)['status'] == 'candidate_pass'
    terms['R'].analysed.ps.phasors['I2'][terms['R'].analysed.indices()[1]] = 9.999
    assert assess(terms)['status'] == 'withheld'


@pytest.mark.parametrize('mapping', [None, {}, {'S': None}, []])
def test_missing_pair_withholds_without_nonfinite_json(mapping):
    assert assess(mapping)['status'] == 'withheld'


@pytest.mark.parametrize('problem', ['hidden_nonfinite', 'hidden_weak', 'short_phasor_time',
                                    'nan_valid_from', 'fractional_window'])
def test_malformed_phasor_timeline_cannot_hide_selected_evidence(terms, problem):
    an = terms['S'].analysed
    k = an.indices()[5]
    an.ps.t = an.ps.t.copy()
    if problem == 'hidden_nonfinite':
        an.ps.t[k] = np.nan
        an.ps.phasors['I2'][k] = np.nan
    elif problem == 'hidden_weak':
        an.ps.t[k] = an.window.t_end+1
        an.ps.phasors['I2'][k] = 0
    elif problem == 'short_phasor_time':
        an.ps.t = an.ps.t[:-1]
    elif problem == 'nan_valid_from':
        an.ps.valid_from = np.nan
    else:
        an.ps.n_window = float(an.ps.n_window)
    assert assess(terms)['status'] == 'withheld'


@pytest.mark.parametrize('clipping', [None, False, 0, {}, ''])
def test_unknown_clipping_assessment_is_not_clean_evidence(terms, clipping):
    terms['S'].analysed.clipping = clipping
    assert assess(terms)['status'] == 'withheld'
