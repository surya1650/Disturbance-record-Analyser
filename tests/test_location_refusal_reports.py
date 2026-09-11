"""Refusal contracts at the estimator boundary, rule inputs and rendered report."""
import math

import pytest

from dranalyser.faultloc import ensemble
from dranalyser.faultloc.estimators import Estimate,e5_unsynchronised
from dranalyser.report.render import build,render
from dranalyser.rules.engine import apply_rules,load_rules
from dranalyser.rules.features import incident_features
from tests.test_tb854_validation import terminal_and_line  # noqa: F401


@pytest.mark.parametrize('m',[-.5,-.1,-.001,1.001,1.1,1.5])
def test_external_result_has_no_patrol_fields_in_rules_or_report(m,monkeypatch,terminal_and_line):  # noqa: F811
    ti,line=terminal_and_line
    monkeypatch.setattr(ensemble,'_single_ended',lambda *args:[Estimate('E1',m,0,ends='single')])
    loc=ensemble.locate(line,{'S':ti})
    features=incident_features({'S':ti.analysed},location=loc,line=line)
    assert not features['location_available']
    assert loc.mode=='external' and loc.m==pytest.approx(m) and not loc.towers
    assert all(math.isnan(v) for v in (loc.km_from_S,loc.km_from_R,*loc.interval_km))
    rep=build({'S':ti.analysed},features,apply_rules(features,load_rules()),loc,line)
    html=render(rep)
    assert 'No fault location was produced.' in html and 'External indication' in html
    assert 'No protected-line chainage or tower is assigned' in html
    assert '<div class="lab">tower</div>' not in html
    assert '<td class="n">0.00</td>' not in html and '<td class="n">100.00</td>' not in html


@pytest.mark.parametrize('values',[
    ([1],[2],[1],[2]),([1,1],[2],[1,1],[2,2]),
    ([float('nan'),1],[2,2],[1,1],[2,2]),([float('inf'),1],[2,2],[1,1],[2,2])])
def test_e5_rejects_insufficient_unequal_or_nonfinite_inputs(values):
    result=e5_unsynchronised(*values,1+2j)
    assert not result.ok and math.isnan(result.m)


@pytest.mark.parametrize('rotation',[0,1.2,-2.5])
def test_e5_ambiguity_refusal_is_independent_of_clock_rotation(rotation):
    import cmath
    r=cmath.exp(1j*rotation)
    result=e5_unsynchronised([.6]*8,[2]*8,[.6*r]*8,[r]*8,1+0j)
    assert not result.ok and 'ambiguous roots' in result.reason


def test_ambiguous_two_ended_result_cannot_silently_fall_back(monkeypatch,terminal_and_line):  # noqa: F811
    ti,line=terminal_and_line
    ambiguous=e5_unsynchronised([.6]*8,[2]*8,[.6]*8,[1]*8,1+0j)
    monkeypatch.setattr(ensemble,'_single_ended',lambda *args:[Estimate('E1',.7,0,ends='single')])
    monkeypatch.setattr(ensemble,'_two_ended',lambda *args:[ambiguous])
    result=ensemble.locate(line,{'S':ti,'R':ensemble.TerminalInput(ti.analysed,'R')})
    assert not result.ok and math.isnan(result.m) and 'single-ended fallback' in ' '.join(result.caveats)
