"""Independent circuit/geometry oracles for conditional exported-boundary counts."""
import copy
import json

import numpy as np
import pytest

from dranalyser.dsp.core import PhasorStream
from dranalyser.dsp.detect import AnalysisWindow, Saturation
from dranalyser.dsp.pipeline import Analysed, analyse
from dranalyser.registry.settings import MhoChar, PolygonChar, ProtectionSettings, Provenance, Zone
from dranalyser.report.zone_comparison import compare_zones
from dranalyser.signals import AnalogMeta, Record


def circuit(fault='AG', rotation=0., scale=2.5, mutual=5+6j):
    """Independent phase-domain network: Zself=Z1+Zm, Z0=Z1+3Zm.

    Every compensated phase/phase-pair sees Z1=5+j12 primary ohm. Its
    settings-base point is (5+j12)/scale. A neutral recorder is unrelated.
    """
    t = np.arange(300)/1000
    currents = np.array([10+2j, -1+3j, 4-1j])*np.exp(1j*rotation)
    z1, z0 = 5+12j, 5+12j+3*mutual
    voltages = np.array([(z1+mutual)*current+mutual*sum(currents[j] for j in range(3) if j != i)
                         for i, current in enumerate(currents)])
    phasors = {prefix+phase: np.full(len(t), value, dtype=complex)
               for prefix, values in (('I', currents), ('V', voltages))
               for phase, value in zip('ABC', values, strict=True)}
    analog = {name: np.sqrt(2)*np.real(values*np.exp(2j*np.pi*50*t)) for name, values in phasors.items()}
    meta = {name: AnalogMeta(name, 'A' if name.startswith('I') else 'V', 1, 0, 1, 1, 'P',
                            -1e9, 1e9, normalised=True) for name in analog}
    analog['IN'] = np.full(len(t), -9999.)
    rec = Record('circuit', 'Synthetic station', 'Synthetic relay', '2013', None, None, 1000, 50,
                 t, analog, {}, analog_meta=meta, content_hash='a'*64)
    ps = PhasorStream(t, 50, 1000, 20, phasors, valid_from=19)
    an = Analysed(rec, 50, ps, {}, None, fault, {}, Saturation(False), [],
                  AnalysisWindow(.08, .16, 4., 'full'), None, None, .04, notes={'inception_t': .05})
    def rect():
        return PolygonChar(vertices=[(1/scale, 10/scale), (7/scale, 10/scale),
                                     (7/scale, 14/scale), (1/scale, 14/scale)])
    settings = ProtectionSettings(k0_convention='impedances',
        k0_params=dict(r1=z1.real, x1=z1.imag, r0=z0.real, x0=z0.imag),
        provenance=Provenance(sha256='b'*64), zones=[Zone('Inside rectangle', phase=rect(), earth=rect()),
        Zone('Outside rectangle', phase=PolygonChar(vertices=[(50, 50), (60, 50), (60, 60), (50, 60)]),
             earth=PolygonChar(vertices=[(50, 50), (60, 50), (60, 60), (50, 60)]))])
    binding = dict(status='associated export', file='synthetic.rio', sha256='b'*64)
    review = dict(record_hash='a'*64, settings_hash='b'*64, channel_mapping={}, reviewer='Synthetic oracle',
                  reason='Known independent network and geometry; no site claim.', ct_ratio=1000., vt_ratio=1000*scale,
                  settings_identity=True, effective_at_event=True, phase_scaling_polarity=True, zero_sequence_voltage=True)
    return an, settings, binding, review


@pytest.mark.parametrize('fault', ['AG', 'BG', 'CG', 'AB', 'BC', 'CA', 'ABG', 'BCG', 'CAG', 'ABC', 'ABCG'])
@pytest.mark.parametrize('rotation,scale', [(0., .5), (.73, 2.5)])
def test_independent_network_geometry_uses_exact_loop_kind_and_settings_base(fault, rotation, scale):
    args = circuit(fault, rotation, scale)
    before = copy.deepcopy(args[0].ps.phasors)
    result = compare_zones(*args)
    assert result['status'] == 'available', result['reasons']
    expected_loop = fault if fault in ('AG', 'BG', 'CG') else fault[:2]
    assert result['loop'] == expected_loop
    assert result['characteristic_kind'] == ('earth' if fault in ('AG', 'BG', 'CG') else 'phase')
    count = len(args[0].indices())
    assert result['window']['evaluated_count'] == result['window']['support_count'] == count
    assert [(row['status'], row['inside_count'], row['outside_count']) for row in result['zones']] == [
        ('inside', count, 0), ('outside', 0, count)]
    assert result['record_hash'] == 'a'*64 and result['settings_hash'] == 'b'*64
    assert result['review'] == result['binding']['review']
    assert result['window']['raw_support_indexing'] == '[start, stop)'
    assert result['authorizes_operation'] is False
    json.dumps(result, allow_nan=False)
    for name in before:
        np.testing.assert_equal(args[0].ps.phasors[name], before[name])


def test_zone_counts_require_the_current_instrument_input_confirmation():
    an, settings, binding, review = circuit()
    an.record.notes['instrument_review_sha256'] = 'c'*64
    assert compare_zones(an, settings, binding, review)['status'] == 'not_evaluable'
    review['instrument_review_sha256'] = 'c'*64
    current = compare_zones(an, settings, binding, review)
    assert current['status'] == 'available', current['reasons']
    assert current['binding']['instrument_review_sha256'] == 'c'*64
    assert current['zones'][0]['inside_count'] == len(an.indices())
    an.record.notes['instrument_review_sha256'] = 'd'*64
    changed = compare_zones(an, settings, binding, review)
    assert changed['status'] == 'not_evaluable'
    assert any('instrument inputs' in reason for reason in changed['reasons'])


def test_exact_native_mho_not_its_display_polygon_decides_membership():
    an, settings, binding, review = circuit('AB', scale=1.)
    # Circle centre (5,0), radius5. At angle pi/48 it is inside the circle but
    # beyond the chord of the 48-point displayed outline.
    angle = np.pi/48
    point = 5+4.999*np.exp(1j*angle)
    for phase in 'ABC':
        an.ps.phasors['V'+phase][:] = point*an.ps.phasors['I'+phase]
    mho = MhoChar(diameter=10+0j)
    assert not PolygonChar(vertices=mho.outline()).contains(point)
    settings.zones = [Zone('Exact mho', phase=mho)]
    result = compare_zones(an, settings, binding, review)
    assert result['zones'][0]['status'] == 'inside'
    assert result['zones'][0]['inside_count'] == len(an.indices())


def test_mixed_counts_use_every_operational_support_without_sampling_or_median():
    args = circuit('AB')
    an = args[0]
    ids = an.indices()
    for phase in 'ABC':
        an.ps.phasors['V'+phase][ids[len(ids)//2]] *= 20
    result = compare_zones(*args)
    row = result['zones'][0]
    assert row['status'] == 'mixed'
    assert row['inside_count'] == len(ids)-1 and row['outside_count'] == 1
    assert row['evaluated_count'] == len(ids)


@pytest.mark.parametrize('problem', ['settings', 'binding', 'actual_hash', 'record', 'settings_hash', 'mapping',
                                     'review', 'reviewer', 'extra', 'identity', 'effective', 'polarity',
                                     'ct_ratio', 'huge_ratio', 'zero_ratio'])
def test_missing_stale_unclean_or_unverified_inputs_are_named_refusals(problem):
    args = list(circuit())
    if problem == 'settings':
        args[1] = None
    elif problem == 'binding':
        args[2]['status'] = 'ambiguous'
    elif problem == 'actual_hash':
        args[1].provenance.sha256 = 'c'*64
    elif problem in ('record', 'settings_hash'):
        args[3]['record_hash' if problem == 'record' else problem] = 'c'*64
    elif problem == 'mapping':
        args[0].record.notes['channel_mapping'] = dict(record_hash='a'*64, reason='Changed source meaning', analog={'A1': 'IB'})
    elif problem == 'review':
        args[3] = None
    elif problem == 'reviewer':
        args[3]['reviewer'] = ''
    elif problem == 'extra':
        args[3]['k0'] = .8
    elif problem in ('identity', 'effective', 'polarity'):
        args[3][dict(identity='settings_identity', effective='effective_at_event', polarity='phase_scaling_polarity')[problem]] = False
    else:
        args[3]['ct_ratio'] = None if problem == 'ct_ratio' else 10**1000 if problem == 'huge_ratio' else 0
    result = compare_zones(*args)
    assert result['status'] == 'not_evaluable' and result['reasons']
    assert not any(row['evaluated_count'] for row in result['zones'])
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize('problem', ['compensation', 'direct_k0', 'nonfinite_k0', 'voltage_review', 'vt_evidence'])
def test_ground_requirements_never_become_zero_or_block_phase_methods(problem):
    args = circuit()
    if problem == 'compensation':
        args[1].k0_params = {}
    elif problem == 'direct_k0':
        args[1].k0_convention = 'complex_k0'
    elif problem == 'nonfinite_k0':
        args[1].k0_params['r0'] = float('inf')
    elif problem == 'voltage_review':
        args[3]['zero_sequence_voltage'] = False
    else:
        args[0].zero_seq_voltage = False
    assert compare_zones(*args)['status'] == 'not_evaluable'
    args[0].fault_type = 'AB'
    assert compare_zones(*args)['status'] == 'available'


def test_actual_zero_native_compensation_is_supported():
    result = compare_zones(*circuit(mutual=0j))
    assert result['status'] == 'available' and result['zones'][0]['status'] == 'inside'


@pytest.mark.parametrize('problem', ['gap', 'multirate', 'nonfinite_times', 'scaling', 'short', 'half', 'empty',
                                     'nonfinite_phasor', 'nonfinite_raw', 'current', 'saturation', 'clipping',
                                     'blocked', 'classification', 'transition', 'oversized'])
def test_unsupported_model_support_never_yields_geometry_counts(problem, monkeypatch):
    args = circuit('AB')
    an = args[0]
    if problem == 'gap':
        an.record.t[120:] += .01
    elif problem == 'multirate':
        an.record.nrates = 2
    elif problem == 'nonfinite_times':
        an.record.t[120] = np.nan
    elif problem == 'scaling':
        an.record.analog_meta['IA'].normalised = False
    elif problem == 'short':
        an.window = AnalysisWindow(.08, .09, .5, 'half')
    elif problem == 'half':
        an.ps.half_cycle = True
    elif problem == 'empty':
        an.window = AnalysisWindow(10., 11., 50., 'full')
    elif problem == 'nonfinite_phasor':
        an.ps.phasors['VA'][an.indices()[10]] = complex(np.nan)
    elif problem == 'nonfinite_raw':
        an.record.analog['IA'][an.indices()[10]] = np.nan
    elif problem == 'current':
        an.ps.phasors['IB'][:] = an.ps.phasors['IA']
    elif problem == 'saturation':
        an.saturation.detected = True
    elif problem == 'clipping':
        an.clipping = ['IA']
    elif problem == 'blocked':
        an.record.add_flag('BAD', 'block', 'Synthetic block')
    elif problem == 'classification':
        an.fault_type = 'NONE'
    elif problem == 'transition':
        monkeypatch.setattr('dranalyser.report.zone_comparison.window_transition',
                            lambda an: dict(status='transition detected', reason='Distinct plateaus.'))
    else:
        monkeypatch.setattr('dranalyser.report.zone_comparison.MAX_SUPPORTS', len(an.indices())-1)
    result = compare_zones(*args)
    assert result['status'] == 'not_evaluable' and result['reasons']
    assert not any(row['evaluated_count'] for row in result['zones'])
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize('problem', ['kind', 'collinear', 'self_intersect', 'nonfinite', 'zero_mho',
                                     'overflow_mho', 'unknown', 'no_zones', 'too_many_zones'])
def test_invalid_or_wrong_kind_characteristics_are_unavailable_not_outside(problem):
    args = circuit('AB')
    if problem == 'kind':
        args[1].zones = [Zone('Earth only', earth=args[1].zones[0].earth)]
    elif problem == 'no_zones':
        args[1].zones = []
    elif problem == 'too_many_zones':
        args[1].zones = [copy.deepcopy(args[1].zones[0]) for _ in range(33)]
    else:
        bad = {'collinear': PolygonChar(vertices=[(0, 0), (1, 1), (2, 2)]),
               'self_intersect': PolygonChar(vertices=[(0, 0), (4, 4), (0, 4), (3, 0)]),
               'nonfinite': PolygonChar(vertices=[(0, 0), (np.inf, 1), (2, 2)]),
               'zero_mho': MhoChar(diameter=0j), 'overflow_mho': MhoChar(diameter=1.7e308+1.7e308j),
               'unknown': object()}[problem]
        args[1].zones = [Zone('Invalid shape', phase=bad)]
    result = compare_zones(*args)
    assert result['status'] == 'not_evaluable'
    assert all(row['status'] == 'not_evaluable' and row['evaluated_count'] == 0 for row in result['zones'])
    assert result['reasons']
    if result['zones']:
        assert result['zones'][0]['reasons']
    json.dumps(result, allow_nan=False)


def test_invalid_zone_does_not_hide_valid_zone_and_duplicate_names_keep_indices():
    args = circuit('AB')
    args[1].zones.insert(1, Zone(args[1].zones[0].name, earth=args[1].zones[0].earth))
    result = compare_zones(*args)
    assert result['status'] == 'available'
    assert [row['index'] for row in result['zones']] == [0, 1, 2]
    assert [row['status'] for row in result['zones']] == ['inside', 'not_evaluable', 'outside']


def test_initialized_prefix_is_excluded_and_fixed_window_is_serialized():
    args = circuit('AB')
    args[0].window = AnalysisWindow(0., .08, 4., 'full')
    result = compare_zones(*args)
    assert result['status'] == 'available'
    assert result['window']['first_index'] == args[0].ps.n_window
    assert result['window']['evaluated_count'] == result['window']['support_count']-1
    assert result['window']['raw_support_start_index'] == 1
    assert result['window']['raw_support_end_index'] == result['window']['last_index']+1
    assert any('inconclusive' in note for note in result['notes'])


def test_no_review_leaves_candidate_support_unknown_rather_than_claiming_zero():
    an, settings, binding, _ = circuit()
    result = compare_zones(an, settings, binding)
    assert result['status'] == 'not_evaluable'
    assert result['window']['support_count'] is None
    assert result['window']['evaluated_count'] == 0
    assert len(an.indices()) > 0


@pytest.mark.parametrize('bounds', [(-.01, .16), (.08, .35)])
def test_out_of_record_window_never_becomes_a_partially_supported_comparison(bounds):
    args = circuit('AB')
    args[0].window = AnalysisWindow(*bounds, (bounds[1]-bounds[0])*50, 'full')
    assert len(args[0].indices()) > 0  # The old range selector alone would return partial data.
    result = compare_zones(*args)
    assert result['status'] == 'not_evaluable'
    assert any('outside the source recording' in reason for reason in result['reasons'])
    assert not any(row['evaluated_count'] for row in result['zones'])


@pytest.mark.parametrize('fault', ['AG', 'BG', 'CG', 'AB', 'BC', 'CA'])
def test_generated_fault_window_uses_supported_native_models_without_moving_location(fault):
    from dranalyser.faultloc.ensemble import TerminalInput, locate
    from dranalyser.registry.model import uniform_line
    from dranalyser.synth.generator import SynthSpec, TerminalSpec, generate
    spec = SynthSpec(m=.42, rf=0, fault=fault, S=TerminalSpec(fs=1000., prefault_s=.12, post_s=.25, breaker_time_s=.09),
                     R=TerminalSpec(fs=1200., prefault_s=.16, post_s=.25, breaker_time_s=.09, sample_phase=.37))
    generated = generate(spec)
    analyses = {end: analyse(rec) for end, rec in generated.records.items()}
    line = uniform_line('Synthetic', 'Known network', spec.kv, spec.line_km, spec.z1_per_km,
                        spec.z0_per_km, spec.zs1_S, spec.zs0_S, spec.zs1_R, spec.zs0_R)
    terms = {end: TerminalInput(an, end, line.terminals[end].zs1, line.terminals[end].zs0) for end, an in analyses.items()}
    before = locate(line, terms)
    an = analyses['S']
    _, settings, binding, review = circuit(fault)
    an.record.content_hash = review['record_hash']
    settings.k0_params = dict(r1=line.z1.real, x1=line.z1.imag, r0=line.z0.real, x0=line.z0.imag)
    settings.zones = [Zone('Known solid-fault reach', phase=PolygonChar(vertices=[(-10, -10), (1e3, -10), (1e3, 1e3), (-10, 1e3)]),
                          earth=PolygonChar(vertices=[(-10, -10), (1e3, -10), (1e3, 1e3), (-10, 1e3)]))]
    result = compare_zones(an, settings, binding, review)
    assert result['status'] == 'available', result['reasons']
    assert result['zones'][0]['status'] == 'inside'
    after = locate(line, terms)
    assert before.ok and after.ok and before.method == after.method == 'E5'
    assert after.km_from_S == before.km_from_S


def test_actual_aliased_source_passes_existing_pipeline_but_cannot_support_zone_comparison():
    from dranalyser.comtrade.conformance import check
    old, settings, binding, review = circuit('AB')
    rec = old.record
    rec.fs = 80.
    rec.t = np.arange(160)/rec.fs
    rec.analog = {}
    for phase, angle in zip('ABC', (0, -2*np.pi/3, 2*np.pi/3), strict=True):
        wave = np.cos(2*np.pi*50*rec.t+angle)
        rec.analog['I'+phase] = np.where(rec.t < .5, 10., 500.)*wave
        rec.analog['V'+phase] = 100*wave
    check(rec)
    an = analyse(rec)
    assert not rec.blocked() and an.fault_type == 'AB'
    assert an.freq == 50 and an.ps.n_window == 2 and len(an.indices()) == 117
    result = compare_zones(an, settings, binding, review)
    assert result['status'] == 'not_evaluable'
    assert any('nyquist' in reason.lower() for reason in result['reasons'])
    assert not any(row['evaluated_count'] for row in result['zones'])


def test_exact_nyquist_frequency_is_refused_without_changing_the_supplied_model():
    args = circuit('AB')
    an = args[0]
    an.record.fs = an.ps.fs = 100.
    an.record.t = an.ps.t = np.arange(an.record.n)/an.record.fs
    an.ps.n_window, an.ps.valid_from = 2, 1
    for name in an.ps.phasors:
        an.record.analog[name] = np.sqrt(2)*np.real(an.ps.phasors[name]*np.exp(2j*np.pi*50*an.record.t))
    before = copy.deepcopy(an.ps.phasors)
    assert an.freq == an.record.fs/2 and len(an.indices()) > 0
    result = compare_zones(*args)
    assert result['status'] == 'not_evaluable'
    assert any('nyquist' in reason.lower() for reason in result['reasons'])
    assert not any(row['evaluated_count'] for row in result['zones'])
    for name in before:
        np.testing.assert_equal(an.ps.phasors[name], before[name])
