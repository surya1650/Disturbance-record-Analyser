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
                c['plot_points']=' '.join(f'{500*i/max(record["sample_count"]-1,1):.5g},{95-90*(v/scale-low)/(high-low):.5g}'
                                         for i,v in c['trace'])
            row['channels'].append(c)
        review['records'].append(row)
    return env.get_template('source_analysis.html').render(review=review)
