"""Frozen synthetic source-time inspection; rational oracle, no field authority."""
import argparse
from fractions import Fraction
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT)]
from dranalyser.comtrade.source_time import digital_source_intervals  # noqa: E402


def case_grid():
    return [dict(seed=s, n=n, scale=m, origin=o, schedule=c) for s,n,m,o,c in itertools.product(
        (103811,104729),(17,257,2049),(.1,1,10),(0,10**12),('constant','piecewise','smooth'))]


def evaluate(config):
    n = config['n']
    rng = np.random.default_rng(config['seed'])
    if config['schedule'] == 'constant':
        steps = np.full(n-1,997,dtype=np.int64)
    elif config['schedule'] == 'piecewise':
        steps = np.repeat(rng.integers(980,1021,(n+7)//8),8)[:n-1]
    else:
        steps = 997+np.rint(12*np.sin(np.arange(n-1)*2*np.pi/n)).astype(np.int64)
    stamps = config['origin']+np.r_[0,np.cumsum(steps)]
    lo, hi = n//3, 2*n//3
    states = np.zeros(n,dtype=int)
    states[lo:hi] = 1
    out = digital_source_intervals(np.arange(1,n+1),stamps,states,nrates=0,timemult=config['scale'])
    assert out['status'] == 'source_time_inspection'
    unit = Fraction(str(config['scale']))/1000000
    exact = [float(int(v-stamps[0])*unit) for v in stamps]
    error = max(abs(a-b) for a,b in zip(exact,out['elapsed_s'],strict=True))
    segment = out['intervals'][0]
    truth = [float(int(stamps[hi-1]-stamps[lo])*unit),float(int(stamps[hi]-stamps[lo-1])*unit)]
    bracket_error = max(abs(a-b) for a,b in zip(truth,segment['duration_sample_bracket_s'],strict=True))
    assert error < 1e-12 and bracket_error < 1e-12
    assert segment['start_index'] == lo and segment['end_index'] == hi
    assert out['authorizes_dsp'] is out['authorizes_location'] is out['alignment_eligible'] is False
    return dict(status='evaluated',max_time_error_s=error,max_bracket_error_s=bracket_error,
                source_span_s=segment['source_span_s'],bracket_s=segment['duration_sample_bracket_s'])


def run(*,grid=None):
    grid = case_grid() if grid is None else grid
    rows = []
    for config in grid:
        try:
            row = dict(config=config,**evaluate(config))
        except Exception as exc:
            row = dict(config=config,status='failed',error_type=type(exc).__name__,reason=str(exc))
        rows.append(row)
    failed = sum(r['status']=='failed' for r in rows)
    sources = ['src/dranalyser/comtrade/source_time.py','src/dranalyser/comtrade/timestamps.py',
        'src/dranalyser/comtrade/parser.py','scripts/source_time_validation.py','tests/test_source_time.py',
        'tests/test_source_time_validation.py','tests/full_record_signals.py',
        'docs/superpowers/specs/2026-10-27-dhone-source-time.md']
    dirty = subprocess.check_output(['git','status','--porcelain','--',*sources],cwd=ROOT,text=True).strip()
    return dict(planned=len(grid),evaluated=len(grid)-failed,failed=failed,cases=rows,
        study_gate='passed_conditional_inspection' if grid==case_grid() and not failed and not dirty else 'failed',
        authorizes_dsp=False,authorizes_location=False,source_git_revision=subprocess.check_output(
            ['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sources_clean=not bool(dirty),
        source_sha256_utf8_lf={p:hashlib.sha256((ROOT/p).read_text(encoding='utf-8-sig').encode()).hexdigest() for p in sources})


def publish(result,path):
    content = json.dumps(result,indent=2,allow_nan=False)+'\n'
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(content)
    return 0 if result['study_gate']=='passed_conditional_inspection' else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Preserve existing evidence; choose another output.')
    result = run()
    status = publish(result,args.output)
    print(json.dumps({k:result[k] for k in ('planned','evaluated','failed','study_gate')}))
    return status


if __name__=='__main__':
    raise SystemExit(main())
