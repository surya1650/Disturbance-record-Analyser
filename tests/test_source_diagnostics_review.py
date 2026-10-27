"""Regressions from the single fresh supported-analysis whole-branch review."""
import copy
import threading
import time

import pytest

from dranalyser.application import source_jobs
from dranalyser.workbench.source_diagnostics import diagnose_source, diagnostic_identity
from dranalyser.workbench.source_snapshot import compose_snapshot
from tests import test_source_inspection as fixtures

revision=fixtures.revision


def wait_ready(jobs,row):
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        body=jobs.request(row,'event.cfg',{})
        if body['status']!='pending':
            assert body['status']=='ready',body
            return body
        time.sleep(.01)
    pytest.fail('Source diagnostics did not complete within the test budget')


def test_inherited_reviewed_ignore_cannot_reestablish_trip_or_ar(revision):
    root,row,_=revision
    row['bundle']['files'][0]['channel_inventory']=[{'id':'D1','kind':'digital','selected':'ignore','reviewed':True}]
    out=diagnose_source(root,row,'event.cfg',{})
    assert out['digital_evidence'][0]['meanings']==[]
    assert out['trip']['status']=='Not available'
    assert out['ar']['status']=='Not available'
    override=diagnose_source(root,row,'event.cfg',{'mappings':{'D1':'AR_BLOCK'}})
    assert override['digital_evidence'][0]['meanings']==['AR_BLOCK']


def test_inherited_analog_empty_reviewed_selection_remains_ignored(revision):
    root,row,_=revision
    row['bundle']['files'][0]['channel_inventory']=[{'id':'A1','kind':'analog','selected':'','automatic':'IA','reviewed':True}]
    out=diagnose_source(root,row,'event.cfg',{})
    assert out['channels'][0]['meaning']=='ignore'


def test_completed_job_and_snapshot_bind_inherited_meanings(revision):
    root,row,_=revision
    item=row['bundle']['files'][0]
    item['channel_inventory']=[{'id':'D1','kind':'digital','selected':'TRIP','reviewed':True}]
    jobs=source_jobs.SourceJobs(root)
    try:
        first=wait_ready(jobs,row)
        assert first['result']['trip']['status']=='Observed indication'
        item['channel_inventory'][0]['selected']='AR_BLOCK'
        second=wait_ready(jobs,row)
        assert second['job_id']!=first['job_id']
        assert second['result']['digital_evidence'][0]['meanings']==['AR_BLOCK']
        assert second['result']['trip']['status']=='Not available'
        with pytest.raises(ValueError,match='binding'):
            compose_snapshot(root,row,'event.cfg',first['result'])
    finally:
        jobs.close()


def test_pending_jobs_freeze_their_own_revision_meanings(revision,monkeypatch):
    root,row,_=revision
    row['bundle']['files'][0]['channel_inventory']=[{'id':'D1','kind':'digital','selected':'TRIP','reviewed':True}]
    before=copy.deepcopy(row)
    gate=threading.Event()
    original=source_jobs.diagnose_source
    def held(*args,**kwargs):
        assert gate.wait(10)
        return original(*args,**kwargs)
    monkeypatch.setattr(source_jobs,'diagnose_source',held)
    jobs=source_jobs.SourceJobs(root)
    try:
        first=jobs.request(row,'event.cfg',{})
        row['bundle']['files'][0]['channel_inventory'][0]['selected']='AR_BLOCK'
        second=jobs.request(row,'event.cfg',{})
        assert first['job_id']!=second['job_id']
        gate.set()
        assert wait_ready(jobs,before)['result']['digital_evidence'][0]['meanings']==['TRIP']
        assert wait_ready(jobs,row)['result']['digital_evidence'][0]['meanings']==['AR_BLOCK']
    finally:
        gate.set()
        jobs.close()


def test_operational_snapshot_metadata_is_part_of_job_identity(revision):
    root,row,folder=revision
    line=folder.parent/'line.yaml'
    line.write_text('id: X\nsections: []\n')
    row['result']={'line_snapshot':str(line),'location_text':'3.000 km from Near by example (conditional)','parameter_status':'unverified'}
    first=diagnostic_identity(root,row,'event.cfg',{})
    row['result']['location_text']='4.000 km from Near by example (conditional)'
    second=diagnostic_identity(root,row,'event.cfg',{})
    assert first['line_sha256']==second['line_sha256']
    assert first['job_id']!=second['job_id']


@pytest.mark.parametrize('inventory,options,expected',[
    ({'selected':'','automatic':'TRIP','reviewed':False},{},'label suggestion'),
    ({'selected':'TRIP','reviewed':True},{},'reviewed revision choice'),
    ({'selected':'TRIP','reviewed':True},{'mappings':{'D1':'AR_BLOCK'}},'source-analysis choice')])
def test_mapping_provenance_distinguishes_suggestions_from_explicit_choices(revision,inventory,options,expected):
    root,row,_=revision
    row['bundle']['files'][0]['channel_inventory']=[{'id':'D1','kind':'digital',**inventory}]
    out=diagnose_source(root,row,'event.cfg',options)
    assert out['digital_evidence'][0]['mapping_source']==expected
