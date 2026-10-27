"""Standalone escaped source review, with no incident-state or source-file writes."""
from pathlib import Path

from jinja2 import Environment,FileSystemLoader,select_autoescape


def render_source_report(result):
    env=Environment(loader=FileSystemLoader(Path(__file__).parent),autoescape=select_autoescape(['html']))
    review=dict(result,records=[])
    for record in result['records']:
        row=dict(record,channels=[])
        for channel in record['channels']:
            c=dict(channel,plot_points='')
            if c['trace'] and c['sample_max']>c['sample_min']:
                scale=max(abs(c['sample_max']),abs(c['sample_min']))
                low,high=c['sample_min']/scale,c['sample_max']/scale
                time=record['axis'].get('elapsed_s',[])
                origin=record.get('trace_reference_s')
                if len(time)==record['sample_count']:
                    offset=origin if origin is not None else 0
                    c['plot_axis']='Relative to local reference (source s)' if origin is not None else 'Native source elapsed (s); selected reference unavailable'
                    c['plot_range']=[time[0]-offset,time[-1]-offset]
                    positions=[500*((time[i]-time[0])/(time[-1]-time[0])) for i,_ in c['trace']]
                else:
                    c['plot_axis']='Original sample index; no supported time axis'
                    c['plot_range']=[0,max(record['sample_count']-1,1)]
                    positions=[500*i/max(record['sample_count']-1,1) for i,_ in c['trace']]
                c['plot_points']=' '.join(f'{x:.5g},{95-90*(v/scale-low)/(high-low):.5g}'
                                         for x,(_,v) in zip(positions,c['trace'],strict=True))
            row['channels'].append(c)
        review['records'].append(row)
    return env.get_template('source_analysis.html').render(review=review)
