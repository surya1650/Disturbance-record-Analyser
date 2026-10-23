"""Reproduce the independent scalar phasor envelope without operational inputs."""
import argparse
import json
from pathlib import Path

from dranalyser.validation.sequence_envelope import run_envelope


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=854)
    parser.add_argument('--repetitions', type=int, default=20)
    parser.add_argument('--out', required=True)
    args = parser.parse_args(argv)
    path = Path(args.out)
    if path.exists():
        raise FileExistsError(path)
    report = run_envelope(args.seed, args.repetitions)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({k: report[k] for k in ('summary', 'by_scenario')}, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
