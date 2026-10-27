"""Analytic breaks: wrong sign, lost roots/boxes, optimistic circles and bad caps."""
from dataclasses import replace
import importlib
import json

import numpy as np
import pytest


def api():
    return importlib.import_module('dranalyser.faultloc.error_sets')


def observation(vs=.9, is_=2/(1+1j), vr=.7, ir=1/(1+1j), radius=0):
    a = api()
    return a.PairedObservation(a.BoundedTerminal(vs, is_, radius, radius, 'synthetic exact'),
                              a.BoundedTerminal(vr, ir, radius, radius, 'synthetic exact'))


def run(obs=None, sections=None, **kwargs):
    a = api()
    result = a.e5_error_feasible([observation()] if obs is None else obs,
        sections=[a.SeriesSection(1, 1+1j)] if sections is None else sections,
        model_provenance=kwargs.pop('model_provenance', 'explicit exact series model'), **kwargs)
    json.dumps(result, allow_nan=False)
    assert result['authorizes_location'] is False
    assert result['research_only'] is True
    return result


def contains(result, point):
    return any(lo <= point <= hi for lo, hi in result['intervals_pu'])


def test_both_analytic_roots_retained_without_selecting_one():
    result = run()
    assert result['status'] == 'ambiguous'
    assert len(result['intervals_pu']) == 2
    assert contains(result, .4) and contains(result, .6)
    assert not contains(result, .5)
    assert result['total_width_pu'] < .01


def test_every_support_constrains_the_set():
    # Common fault -.5+.7j at m=.4; second equation has other root -.2.
    result = run([observation(), observation(.7+.7j, 3/(1+1j), .1+.7j)])
    assert contains(result, .4) and not contains(result, .6)
    assert result['status'] == 'outer_set'


@pytest.mark.parametrize('m', [0, .23, .61, 1])
@pytest.mark.parametrize('rotation', [0, 1.9])
def test_section_endpoints_junctions_and_local_rotation(m, rotation):
    z = [1+8j, 7+12j, 2+19j]
    edges = [0, .23, .61, 1]
    p = sum(zi*max(0, min(1, (m-lo)/(hi-lo)))
            for zi, lo, hi in zip(z, edges[:-1], edges[1:], strict=True))
    f, is_, ir = .7+1.1j, 2-.3j, -.4+1.6j
    rotate = np.exp(1j*rotation)
    obs = observation(f+p*is_, is_, (f+(sum(z)-p)*ir)*rotate, ir*rotate)
    result = run([obs], [api().SeriesSection(e, zi) for e, zi in zip(edges[1:], z, strict=True)])
    assert contains(result, m)


@pytest.mark.parametrize('scale', [1e-120, 1, 1e120])
def test_phasor_and_cap_units_scale_together(scale):
    o = observation(radius=.001)
    o = api().PairedObservation(*[replace(t, voltage=t.voltage*scale, current=t.current*scale,
        voltage_radius=t.voltage_radius*scale, current_radius=t.current_radius*scale) for t in (o.s, o.r)])
    result = run([o])
    assert contains(result, .4) and contains(result, .6)
    assert result['intervals_pu'] == run([observation(radius=.001)])['intervals_pu']


def test_no_information_and_large_circles_cover_entire_line():
    for o in [observation(0, 0, 0, 0), observation(radius=100),
              observation(1, 1e-12, 1, 1e-12, radius=.001)]:
        result = run([o])
        assert result['status'] == 'uninformative'
        assert result['intervals_pu'] == [[0, 1]]


def test_inconsistent_exact_voltage_data_is_distinguished_from_missing_caps():
    result = run([observation(1, 0, 2, 0)])
    assert result['status'] == 'inconsistent'
    assert result['intervals_pu'] == []


@pytest.mark.parametrize('budget', [1, 2, 3, 5])
def test_resource_exhaustion_retains_all_pending_regions(budget):
    result = run(max_boxes=budget)
    assert result['status'] == 'resource_limited'
    assert result['boxes_evaluated'] <= budget
    assert contains(result, .4) and contains(result, .6)


@pytest.mark.parametrize('field,value', [('voltage_radius', None), ('current_radius', -1),
    ('current_radius', True), ('voltage_radius', np.nan), ('voltage', np.inf),
    ('current', complex(0, np.nan)), ('provenance', ''), ('provenance', None),
    ('provenance', False), ('voltage', True)])
def test_unknown_or_malformed_terminal_input_withholds(field, value):
    o = observation()
    result = run([replace(o, s=replace(o.s, **{field: value}))])
    assert result['status'] == 'withheld'
    assert result['intervals_pu'] == []


@pytest.mark.parametrize('kwargs', [dict(resolution=0), dict(resolution=True), dict(resolution=1e-9),
    dict(resolution=np.nan), dict(max_boxes=True), dict(max_boxes=0), dict(max_boxes=200001),
    dict(max_boxes=1.5), dict(model_provenance='')])
def test_bad_controls_do_not_produce_an_empty_physical_set(kwargs):
    assert run(**kwargs)['status'] == 'withheld'


@pytest.mark.parametrize('parts', [[(0, 1j)], [(.5, 1j)], [(1, -1j)], [(1, -1+1j)],
    [(.5, 1j), (.5, 1j), (1, 1j)], [(True, 1j)], [(1, np.nan)]])
def test_invalid_or_incomplete_section_models_withhold(parts):
    result = run(sections=[api().SeriesSection(*s) for s in parts])
    assert result['status'] == 'withheld'


def test_shape_and_capacity_errors_withhold():
    for obs in [[], None, {}, [object()], [observation()]*257]:
        if obs is None:
            result = api().e5_error_feasible(None, sections=[], model_provenance='test')
            assert result['status'] == 'withheld'
        else:
            assert run(obs)['status'] == 'withheld'
    assert run(sections=[api().SeriesSection((k+1)/65, 1j) for k in range(65)])['status'] == 'withheld'


@pytest.mark.parametrize('value,z', [(1e308, 1e308j), (1e-300, 1e-300j)])
def test_unrepresentable_propagated_scale_refuses(value, z):
    assert run([observation(is_=value)], [api().SeriesSection(1, z)])['status'] == 'withheld'
