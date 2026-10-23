"""Run the frozen field acceptance manifest without modifying any source."""
import json

from ..registry.catalogue_io import save_new
from ..validation.replay import replay, template


def add_acceptance_parser(sub):
    p = sub.add_parser('acceptance', help='replay frozen held-out field cases with independent patrol truth')
    p.add_argument('--manifest')
    p.add_argument('--template', action='store_true')
    p.add_argument('--out', required=True)
    p.set_defaults(func=cmd_acceptance)


def cmd_acceptance(args):
    if bool(args.manifest) == args.template:
        print('Choose exactly one of --manifest and --template.')
        return 2
    try:
        result = template() if args.template else replay(args.manifest)
        save_new(args.out, json.dumps(result, indent=2, allow_nan=False)+'\n')
        print('Unfilled protocol saved.' if args.template else json.dumps({k: result[k] for k in
              ('status', 'total_events', 'eligible_events', 'excluded_events', 'located_events', 'refused_events')}))
        return 0 if args.template or result['status'] == 'pass' else 2
    except (ValueError, KeyError, OSError, TypeError) as exc:
        print('Acceptance not ready: '+str(exc))
        return 2
