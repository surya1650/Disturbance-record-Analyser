"""Inventory remains read-only and never upgrades synthetic evidence to field truth."""
import hashlib
import sqlite3

from scripts.create_demo import create_demo
from scripts.field_evidence_inventory import inventory


def test_synthetic_inventory_reports_evidence_without_accepting_field_accuracy(tmp_path):
    source=create_demo(tmp_path/'synthetic')
    paths=list(source.rglob('*'))
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
    result=inventory([source],source)
    assert result['summary']==dict(records=2,analysed=2,registry_files=1,accepted_field_cases=0)
    assert result['registry'][0]['approval_status']=='unverified'
    assert all(r['record_hash'] and r['clock_quality']['alignment_eligible'] is False for r in result['records'])
    assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
    assert len(result['missing_acceptance_evidence'])==6


def test_bad_records_and_missing_truth_database_are_visible_without_creating_database(tmp_path):
    (tmp_path/'bad.cfg').write_text('invalid recording')
    absent=tmp_path/'missing.db'
    result=inventory([tmp_path],tmp_path,[absent])
    assert result['records'][0]['status']=='unavailable' and result['records'][0]['error']
    assert result['stored_truth'][0]['error'] and not absent.exists()


def test_stored_confirmations_are_counted_but_not_authenticated(tmp_path):
    path=tmp_path/'truth.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE incident (id TEXT)')
        db.execute('CREATE TABLE ground_truth (id TEXT)')
        db.execute("INSERT INTO ground_truth VALUES ('synthetic')")
    result=inventory([],tmp_path,[path])
    assert result['stored_truth'][0]['confirmation_rows']==1
    assert result['summary']['accepted_field_cases']==0
