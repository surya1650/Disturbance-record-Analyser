"""Bounded waveform stress screens; not a CT/CVT transfer-function or EMT model."""
import numpy as np
import pytest

from dranalyser.dsp.pipeline import analyse
from dranalyser.dsp.stage_windows import stage_window
from dranalyser.rules.evidence import relay_evidence
from tests.staged_network_oracle import scenario


@pytest.mark.parametrize('fs',[1000,1200,2400])
@pytest.mark.parametrize('stress',['decaying voltage oscillation','current clipping','voltage drift','short','nonuniform'])
def test_guarded_interiors_refuse_waveform_stress(fs,stress):
    reference,_=scenario(fs=fs)
    stage=relay_evidence(analyse(reference))['stages']['intervals'][0]
    record,_=scenario(fs=fs)
    t=record.t
    selected=t>=.12
    if stress=='decaying voltage oscillation':
        for name in ('VA','VB','VC'):
            record.analog[name][selected]+=80000*np.exp(-(t[selected]-.12)/.15)*np.sin(2*np.pi*75*(t[selected]-.12))
    elif stress=='current clipping':
        record.analog['IA'][selected]=np.clip(record.analog['IA'][selected],-800,800)
    elif stress=='voltage drift':
        record.analog['VA'][selected]*=1+2*(t[selected]-.12)
    elif stress=='nonuniform':
        record.t[round(.2*fs)]+=.25/fs
    else:
        stage['end_s']=stage['start_s']+.03
    result=stage_window(analyse(record),stage)
    assert result['status']=='withheld',result
    assert result['reason']
