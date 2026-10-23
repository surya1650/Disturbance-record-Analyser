"""CLI entry points for source evidence and field-acceptance readiness."""
import json
import yaml

from ..registry.catalogue_io import export_registry, import_snapshot, read_catalogue, read_json, review_template, save_new
from ..registry.catalogue_review import source_candidate


def add_catalogue_parser(sub):
    parser = sub.add_parser('catalogue', help='stage spreadsheet evidence without changing active line definitions')
    action = parser.add_subparsers(dest='catalogue_action', required=True)
    p = action.add_parser('import', help='import a connector-acquired JSON snapshot')
    p.add_argument('snapshot')
    p.add_argument('--out', required=True)
    p = action.add_parser('review-template', help='write an unfilled, source-bound review form')
    p.add_argument('catalogue')
    p.add_argument('--out', required=True)
    p = action.add_parser('export', help='export a separately reviewed provisional line YAML')
    p.add_argument('catalogue')
    p.add_argument('--review', required=True)
    p.add_argument('--out', required=True)
    p = action.add_parser('candidate', help='use explicitly identified source rows with mandatory model-review refusal')
    p.add_argument('catalogue')
    p.add_argument('--selection', required=True)
    p.add_argument('--prior', help='preserve existing relay metadata; not an approval of its settings/model')
    p.add_argument('--out', required=True)
    parser.set_defaults(func=cmd_catalogue)


def cmd_catalogue(args):
    try:
        if args.catalogue_action == 'import':
            result = import_snapshot(args.snapshot, args.out)
            print(json.dumps({'catalogue_hash': result['catalogue_hash'], **result['catalogue']['summary']}))
        elif args.catalogue_action == 'review-template':
            save_new(args.out, json.dumps(review_template(read_catalogue(args.catalogue)), indent=2)+'\n')
            print('Unfilled review template saved. Source declarations do not establish field verification.')
        elif args.catalogue_action == 'candidate':
            from pathlib import Path
            prior = yaml.safe_load(Path(args.prior).read_text(encoding='utf-8')) if args.prior else None
            result = source_candidate(read_catalogue(args.catalogue)['catalogue'], read_json(args.selection), prior)
            save_new(args.out, yaml.safe_dump(result, allow_unicode=True, sort_keys=False))
            print(result['id']+': source candidate saved; distance remains withheld pending model review.')
        else:
            result = export_registry(args.catalogue, args.review, args.out)
            print(result['id']+': separate provisional registry written; active definitions were not replaced.')
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print('Catalogue refused: '+str(exc))
        return 2
