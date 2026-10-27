"""Frozen independent analytic/non-observability cases for source-time diagnostics."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import platform
import subprocess
import sys

import numpy as np
import scipy

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from dranalyser.dsp.source_analysis import analyse_source  # noqa: E402


def case_grid():
    return [dict(seed=s,cycles=n,schedule=c,frequency=f,cohort=k) for s,n,c,f,k in itertools.product(
        (190081,190111),(4,6),('uniform','piecewise','smooth'),(47.3,50.2,53.1),('clean','harmonic_dc','noise','step'))]


def controls():
    return [dict(seed=190133,cycles=n,schedule='uniform',frequency=f,cohort=k)
        for n,f,k in itertools.product((4,6),(47.3,53.1),('gain','alias'))]


def evaluate(config):
    rng=np.random.default_rng(config['seed'])
    n=config['cycles']*24+1
    count=np.arange(n-1)
    steps=np.ones(n-1)
    if config['schedule']=='piecewise':
        steps+=np.where(count<len(count)//2,-.018,.018)
    elif config['schedule']=='smooth':
        steps+=.02*np.sin(2*np.pi*count/len(count))
    t=np.r_[0,np.round(np.cumsum(steps)/sum(steps)*config['cycles']/50*1e6)]*1e-6
    if config['cohort']=='alias':
        t=np.arange(n)/1200
    f=config['frequency']
    actual_f=1200-f if config['cohort']=='alias' else f
    values=np.sqrt(2)*100*np.cos(2*np.pi*actual_f*t+.3)
    if config['cohort']=='harmonic_dc':
        values+=20+300*t+15*np.cos(4*np.pi*f*t+.7)+7*np.sin(6*np.pi*f*t)
    elif config['cohort']=='noise':
        values+=rng.normal(0,.5,n)
    elif config['cohort']=='step':
        values*=np.where(t>=t[-1]/2,2,1)
    elif config['cohort']=='gain':
        values*=1.2
    obs=dict(status='observed',station='Independent analytic source',device='synthetic',
        content_hash='',sample_count=n,issues=[],nominal_frequency_hz=50,
        axis=dict(status='source_time_inspection',elapsed_s=t.tolist()),digital=[],
        channels=[dict(key='A1',label='VA',units='synthetic units',values=values.tolist(),frequency_reference=True,skew_us=0)])
    out=analyse_source(obs)
    assert out['coverage_complete'] and out['windows_evaluated']>0
    assert out['authorizes_location'] is out['alignment_eligible'] is out['authorizes_production_dsp'] is False
    fits=[w['channels']['A1'] for w in out['windows']]
    if config['cohort']=='step':
        assert all(p['status']=='withheld' for p in fits),'Stationary model accepted an amplitude step.'
        return dict(status='evaluated',windows=len(fits),consistent=0)
    assert all(p['status']=='model_consistent' for p in fits),'Analytic signal model unexpectedly unavailable.'
    if config['cohort'] in ('gain','alias'):
        return dict(status='evaluated',windows=len(fits),consistent=len(fits),
            harmful_unobservable_control=config['cohort'],location_authorized=False,
            apparent_rms=[p['rms'] for p in fits],physical_low_frequency_rms=100 if config['cohort']=='gain' else 0)
    freqerr=max(abs(w['frequency']['frequency_hz']-f) for w in out['windows'])
    amperr=max(abs(p['rms']/100-1) for p in fits)
    phaseerr=max(abs(np.angle(complex(*p['phasor'])/np.exp(1j*(2*np.pi*f*p['centre_s']+.3)),deg=True)) for p in fits)
    noisy=config['cohort']=='noise'
    assert freqerr<(.1 if noisy else .001),f'frequency error {freqerr}'
    assert amperr<(.02 if noisy else .001),f'RMS relative error {amperr}'
    assert phaseerr<(1 if noisy else .02),f'local phase error {phaseerr}'
    return dict(status='evaluated',windows=len(fits),consistent=len(fits),frequency_error_hz=freqerr,
                rms_relative_error=amperr,local_phase_error_deg=phaseerr)


def run(*,grid=None):
    expected=case_grid()+controls()
    grid=expected if grid is None else grid
    rows=[]
    for config in grid:
        try:
            rows.append(dict(config=config,**evaluate(config)))
        except Exception as exc:
            rows.append(dict(config=config,status='failed',error_type=type(exc).__name__,reason=str(exc)))
    sources=['src/dranalyser/comtrade/source_observations.py','src/dranalyser/comtrade/source_time.py',
        'src/dranalyser/comtrade/parser.py','src/dranalyser/signals.py','src/dranalyser/dsp/nonuniform.py',
        'src/dranalyser/dsp/source_analysis.py','src/dranalyser/dsp/source_compare.py',
        'src/dranalyser/report/source_analysis.py','src/dranalyser/report/source_analysis.html',
        'scripts/analyse_source_record.py','scripts/nonuniform_validation.py','tests/test_nonuniform_source.py',
        'tests/test_source_analysis_delivery.py','tests/test_source_analysis_review.py','tests/full_record_signals.py',
        'docs/superpowers/specs/2026-10-27-nonuniform-analysis.md']
    dirty=subprocess.check_output(['git','status','--porcelain','--',*sources],cwd=ROOT,text=True).strip()
    failures=sum(r['status']=='failed' for r in rows)
    return dict(planned=len(grid),evaluated=len(grid)-failures,failed=failures,cases=rows,
        study_gate='passed_conditional_diagnostics' if grid==expected and not failures and not dirty else 'failed',
        authorizes_location=False,authorizes_production_dsp=False,alignment_eligible=False,
        source_git_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_sha256_utf8_lf={p:hashlib.sha256((ROOT/p).read_text(encoding='utf-8-sig').encode()).hexdigest() for p in sources},
        versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        parser.error('Preserve existing evidence: output must be new.')
    result=run()
    with args.output.open('x',encoding='utf-8') as stream:
        stream.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ('planned','evaluated','failed','study_gate')}))
    return 0 if result['study_gate']=='passed_conditional_diagnostics' else 2


if __name__=='__main__':
    raise SystemExit(main())
