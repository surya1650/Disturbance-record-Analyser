"""Read-only inspection must survive operational refusal without inventing data."""
import copy
import hashlib
import importlib
import json

import pytest


def adapter(name):
    module = importlib.import_module('dranalyser.workbench.source_inspection')
    return getattr(module, name)


@pytest.fixture
def revision(tmp_path):
    folder = tmp_path/'runs'/'blocked'/'1'/'owner'/'records'
    folder.mkdir(parents=True)
    cfg = folder/'event.cfg'
    cfg.write_text('STATION,DEVICE,2013\n3,2A,1D\n1,DUP,A,,A,2,1,0,-32767,32767,1,1,P\n'
                   '2,DUP,B,,V,1,0,0,-32767,32767,1,1,P\n1,TRIP,,,0\n50\n0\n0,4\n'
                   '01/01/2020,00:00:00.000000\n01/01/2020,00:00:00.000000\nASCII\n1\n')
    cfg.with_suffix('.dat').write_text('1,0,10,20,0\n2,800,11,21,1\n3,1700,,22,\n4,2600,13,23,0\n')
    files = [{'name': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'size': p.stat().st_size}
             for p in folder.iterdir()]
    row = dict(incident_id='blocked', number=1, state='needs_review', result=None, files=files,
               bundle=dict(root=str(folder), files=[dict(name='event.cfg',kind='comtrade',data_file='event.dat',
                   blocked=True,ok=False,content_hash='')]))
    return tmp_path, row, folder


def test_blocked_no_result_duplicate_labels_exact_nullable_observations(revision):
    root,row,_ = revision
    before = copy.deepcopy(row)
    out = adapter('inspection_record')(root,row,'event.cfg')
    assert out['sample_count'] == 4 and out['status'] == 'partial'
    assert [c['id'] for c in out['channels']] == ['A1','A2','D1']
    assert [c['label'] for c in out['channels']][:2] == ['DUP','DUP']
    assert out['authorizes_location'] is out['alignment_eligible'] is False
    a = adapter('inspection_samples')(root,row,'event.cfg','A1',1,4)
    assert [s[0] for s in a['samples']] == [1,2,3]
    assert [s[1] for s in a['samples']] == pytest.approx([.0008,.0017,.0026])
    assert [s[2] for s in a['samples']] == [23.0,None,27.0]
    d = adapter('inspection_samples')(root,row,'event.cfg','D1',0,4)
    assert [s[2] for s in d['samples']] == [0,1,None,0]
    assert row == before
    json.dumps(out,allow_nan=False)


def test_bad_time_retains_indices_without_seconds(revision):
    root,row,folder = revision
    dat = folder/'event.dat'
    dat.write_text(dat.read_text().replace('3,1700','3,800'))
    row['files'][0:0] = []
    for entry in row['files']:
        entry['sha256'] = hashlib.sha256((folder/entry['name']).read_bytes()).hexdigest()
    out = adapter('inspection_samples')(root,row,'event.cfg','A2',0,4)
    assert [s[1] for s in out['samples']] == [None]*4
    assert [s[2] for s in out['samples']] == [20,21,22,23]
    assert out['time_basis']['status'] == 'withheld'


def test_missing_dat_and_unsupported_container_are_explicit(revision):
    root,row,folder = revision
    (folder/'event.dat').unlink()
    row['files'] = [e for e in row['files'] if e['name'].endswith('.cfg')]
    row['bundle']['files'][0]['data_file'] = ''
    out = adapter('inspection_record')(root,row,'event.cfg')
    assert out['status'] == 'cfg_only' and out['issues'] and out['sample_count'] == 0


@pytest.mark.parametrize('start,stop', [(-1,1),(2,1),(0,5),(0,20001),(True,2),(0,1.5)])
def test_invalid_intervals_refuse(revision,start,stop):
    root,row,_ = revision
    with pytest.raises(ValueError):
        adapter('inspection_samples')(root,row,'event.cfg','A1',start,stop)


@pytest.mark.parametrize('kind', ['filename','dat_path','root','changed','missing','channel'])
def test_foreign_paths_changed_bytes_and_unknown_identity_refuse(revision,kind):
    root,row,folder = revision
    name,channel = 'event.cfg','A1'
    if kind == 'filename':
        name = '../event.cfg'
    if kind == 'dat_path':
        row['bundle']['files'][0]['data_file'] = '../../../event.dat'
    if kind == 'root':
        row['bundle']['root'] = str(root)
    if kind == 'changed':
        (folder/'event.dat').write_text('changed')
    if kind == 'missing':
        (folder/'event.dat').unlink()
    if kind == 'channel':
        channel = 'DUP'
    with pytest.raises(ValueError):
        adapter('inspection_samples')(root,row,name,channel,0,1)


def test_cached_source_rechecks_hashes(revision):
    root,row,folder = revision
    adapter('inspection_record')(root,row,'event.cfg')
    (folder/'event.dat').write_text('changed')
    with pytest.raises(ValueError,match='checksum'):
        adapter('inspection_record')(root,row,'event.cfg')


def test_symlink_outside_revision_refuses(revision,tmp_path):
    root,row,folder = revision
    external = tmp_path/'outside.dat'
    external.write_bytes((folder/'event.dat').read_bytes())
    (folder/'event.dat').unlink()
    try:
        (folder/'event.dat').symlink_to(external)
    except OSError:
        pytest.skip('OS does not permit symlink creation')
    with pytest.raises(ValueError,match='path'):
        adapter('inspection_record')(root,row,'event.cfg')
