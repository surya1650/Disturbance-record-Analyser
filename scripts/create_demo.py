"""Create explicitly synthetic records for local application smoke tests and demos."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import yaml

from dranalyser.synth.generator import SynthSpec, TerminalSpec, generate


def create_demo(destination):
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    spec = SynthSpec(m=0.42, fault='AG', rf=5,
        S=TerminalSpec(fs=1000, prefault_s=.12, post_s=.25, breaker_time_s=.06, adc_bits=16),
        R=TerminalSpec(fs=1200, prefault_s=.16, post_s=.25, breaker_time_s=.06,
                       clock_offset_s=1418, sample_phase=.37, adc_bits=16))
    case = generate(spec)
    for end, rec in case.records.items():
        folder = root / end
        folder.mkdir(exist_ok=True)
        analog, digital = list(rec.analog), list(rec.digital)
        lines = [f'SYNTHETIC-{end},DEMO-{end},1999',
                 f'{len(analog)+len(digital)},{len(analog)}A,{len(digital)}D']
        scales = []
        for i, name in enumerate(analog, 1):
            scale = max(float(np.max(np.abs(rec.analog[name]))) / 30000, .001)
            scales.append(scale)
            unit = 'V' if name.startswith('V') else 'A'
            lines.append(f'{i},{name},,,{unit},{scale},0,0,-32767,32767,1,1,P')
        for i, name in enumerate(digital, 1):
            lines.append(f'{i},{name},,,0')
        lines += ['50','1',f'{rec.fs},{len(rec.t)}',
                  rec.start_time.strftime('%d/%m/%Y,%H:%M:%S.%f'),
                  rec.trigger_time.strftime('%d/%m/%Y,%H:%M:%S.%f'),'ASCII','1']
        (folder / 'event.cfg').write_text('\n'.join(lines)+'\n', encoding='ascii')
        data=[]
        for i in range(len(rec.t)):
            values=[str(round(rec.analog[n][i]/s)) for n,s in zip(analog,scales,strict=True)]
            values += [str(int(rec.digital[n][i])) for n in digital]
            data.append(','.join([str(i+1),str(round(i/rec.fs*1e6)),*values]))
        (folder / 'event.dat').write_text('\n'.join(data)+'\n',encoding='ascii')
    definition = {'id':'SYNTHETIC-DEMO','name':'Synthetic demonstration line','kv':spec.kv,
                  'sections':[{'from_km':0,'to_km':spec.line_km,'r1':spec.z1_per_km.real,
                               'x1':spec.z1_per_km.imag,'r0':spec.z0_per_km.real,'x0':spec.z0_per_km.imag}],
                  'terminals':{e:{'substation':f'Synthetic {e}','vt_type':'CVT',
                                  'zs1':[getattr(spec,'zs1_'+e).real,getattr(spec,'zs1_'+e).imag],
                                  'zs0':[getattr(spec,'zs0_'+e).real,getattr(spec,'zs0_'+e).imag]}
                               for e in ('S','R')}}
    (root / 'synthetic-line.yaml').write_text('# SYNTHETIC DEMONSTRATION ONLY\n'+yaml.safe_dump(definition),encoding='utf-8')
    metadata={'line_id':'SYNTHETIC-DEMO','auto_analyse':True,
              'assignments':{f'{e}/event.cfg':{'end':e,'role':'primary'} for e in ('S','R')}}
    (root / 'intake.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    return root


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('destination',nargs='?',default='out/synthetic-demo')
    args=parser.parse_args()
    print(create_demo(args.destination).resolve())
