"""Digital abbreviations must not classify carrier indications as auto-reclose."""
import pytest

from dranalyser.rules.signals import map_signals
from dranalyser.workbench.source_events import digital_evidence, trip_ar


@pytest.mark.parametrize('name', ['CAR Fail DIST', 'CAR Fail DEF', 'CARR Fail', 'Carrier Fail'])
def test_carrier_failure_is_never_auto_reclose_failure(name):
    mapped=map_signals([name])
    assert mapped.has('CARRIER_FAIL')
    assert not any(meaning.startswith('AR_') for meaning in mapped.mapping)


@pytest.mark.parametrize('name', ['SCAR FAIL', 'CAR BLOCK', 'CAR IN PROG', 'CAR CLOSE', 'CAR INIT', 'CAR LOCKOUT'])
def test_embedded_ar_substring_never_creates_reclose_evidence(name):
    assert not any(meaning.startswith('AR_') for meaning in map_signals([name]).mapping)


@pytest.mark.parametrize('name,meaning', [
    ('AR FAIL','AR_FAIL'),('A/R FAIL','AR_FAIL'),('Reclose fail','AR_FAIL'),
    ('AR BLOCK','AR_BLOCK'),('A/R CLOSE','AR_CLOSE'),('AR IN PROG','AR_IN_PROGRESS'),
    ('A/R LOCKOUT','AR_LOCKOUT'),('AR INIT','AR_INITIATE'),
    ('Initiate 3PH A/R','AR_INITIATE'),('DI_Init 3PH A/R','AR_INITIATE'),
    ('CARR DIST RECV','CARRIER_RECV'),('CARRIER DISTANCE RECV','CARRIER_RECV')])
def test_explicit_signal_aliases_retain_their_recorded_identity(name,meaning):
    assert map_signals([name]).channel(meaning)==name


def test_carrier_alarm_cannot_produce_auto_reclose_failure_explanation():
    source={'axis':{'elapsed_s':[0,.01,.02]},'digital':[
        {'key':'D1','label':'CAR Fail DIST','states':[0,1,1]}],
        'header_inventory':[{'id':'D1','normal_state':'0'}]}
    evidence=digital_evidence(source,{})
    assert evidence[0]['meanings']==['CARRIER_FAIL']
    _,ar=trip_ar(evidence)
    assert ar['status']=='Not available' and ar['evidence_ids']==[]


def test_reviewed_meaning_and_polarity_remain_authoritative():
    assert map_signals(['CAR Fail DIST'],{'CAR Fail DIST':'AR_FAIL'}).channel('AR_FAIL')=='CAR Fail DIST'
    source={'axis':{'elapsed_s':[0,.01,.02]},'digital':[
        {'key':'D1','label':'Initiate 3PH A/R','states':[0,1,1]}],
        'header_inventory':[{'id':'D1','normal_state':'0'}]}
    evidence=digital_evidence(source,{},asserted_states={'D1':0})
    assert evidence[0]['asserted_state']==0
    assert evidence[0]['assertion_source']=='source-analysis choice'
