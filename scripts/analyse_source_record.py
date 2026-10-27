"""Read-only independent DR analysis, without a line model or common clock."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dranalyser.comtrade.source_observations import load_source  # noqa: E402
from dranalyser.dsp.source_analysis import analyse_source  # noqa: E402
from dranalyser.dsp.source_compare import compare_sources  # noqa: E402
from dranalyser.report.source_analysis import render_source_report  # noqa: E402


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cfg',type=Path,nargs='+',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reference',help='Explicit per-record digital rising-edge display reference; never clock evidence.')
    args=parser.parse_args()
    if args.output.exists():
        parser.error('Preserve existing evidence: output directory must be new.')
    if len(args.cfg)>32:
        parser.error('At most32 supplied record paths per review.')
    records=[]
    for path in args.cfg:
        obs=load_source(path)
        result=analyse_source(obs)
        result['display_name']=path.name
        records.append(result)
    review=compare_sources(records,reference=args.reference)
    payload=json.dumps(review,indent=2,allow_nan=False)+'\n'
    html=render_source_report(review)
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'analysis.json').write_text(payload,encoding='utf-8')
    (args.output/'index.html').write_text(html,encoding='utf-8')
    print(json.dumps(dict(records=len(records),distinct_payloads=review['distinct_payloads'],output=str(args.output))))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
