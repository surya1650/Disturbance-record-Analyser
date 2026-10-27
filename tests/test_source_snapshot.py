"""One source/options-bound snapshot feeds the app, exports and schematic."""
import copy
import hashlib
import json

import pytest

from tests import test_source_inspection as fixtures
from dranalyser.workbench.source_diagnostics import diagnose_source

revision=fixtures.revision


def snapshot_api():
    from dranalyser.workbench.source_snapshot import compose_snapshot
    return compose_snapshot


def test_missing_line_and_recorded_time_do_not_become_inferred_event_times(revision):
    root,row,_=revision
    result=diagnose_source(root,row,'event.cfg',{})
    snapshot=snapshot_api()(root,row,'event.cfg',result)
    assert snapshot['line']['length_km'] is None
    assert snapshot['line']['terminals']=={'S':'Not available','R':'Not available'}
    assert snapshot['line']['location']['status']=='Not available'
    assert snapshot['recorded_times']['start']=='01/01/2020,00:00:00.000000'
    assert snapshot['recorded_times']['trigger']=='01/01/2020,00:00:00.000000'
    assert snapshot['inferred_inception']=='Not available'
    assert snapshot['job_id']==result['job_id'] and snapshot['options']==result['options']
    assert snapshot['sections']['cannot_conclude'] and snapshot['methods']['rx']['reason']
    json.dumps(snapshot,allow_nan=False)


def test_frozen_supplied_line_facts_keep_explicit_units_provenance_and_location(revision):
    root,row,folder=revision
    path=folder.parent/'line.yaml'
    path.write_text('id: EXPLICIT\nname: Declared line\nkv: 132\nterminals:\n  S: {substation: Near}\n  R: {substation: Far}\nsections:\n- {from_km: 0, to_km: 10, r1: 0.1, x1: 0.4, r0: 0.3, x0: 1.2}\n')
    row['result']={'line_snapshot':str(path),'parameter_status':'unverified','location_text':'3.000 km from Near by example (conditional)'}
    result=diagnose_source(root,row,'event.cfg',{})
    snapshot=snapshot_api()(root,row,'event.cfg',result)
    assert snapshot['line']['length_km']==10
    assert snapshot['line']['terminals']=={'S':'Near','R':'Far'}
    assert snapshot['line']['sections'][0]['x1_ohm_per_km']==.4
    assert snapshot['line']['sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    assert snapshot['line']['location']['text'].startswith('3.000 km')
    first=result['job_id']
    path.write_text(path.read_text().replace('to_km: 10','to_km: 12'))
    assert diagnose_source(root,row,'event.cfg',{})['job_id']!=first


def test_snapshot_rejects_foreign_source_or_option_binding(revision):
    root,row,_=revision
    result=diagnose_source(root,row,'event.cfg',{})
    for key,value in [('file','foreign.cfg'),('source_sha256',{}),('options',{'voltage_kv':220,'mappings':{}})]:
        wrong=copy.deepcopy(result)
        wrong[key]=value
        with pytest.raises(ValueError):
            snapshot_api()(root,row,'event.cfg',wrong)


def test_existing_location_refusal_is_an_explanation_not_an_estimate(revision):
    from dranalyser.workbench.source_snapshot import line_facts
    root,row,folder=revision
    path=folder.parent/'line.yaml'
    path.write_text('id: X\nsections: []\n')
    row['result']={'line_snapshot':str(path),'location_text':'refused - no usable estimate'}
    line=line_facts(root,row)
    assert line['location']['status']=='Not available'
    assert 'no usable estimate' in line['location']['text']
