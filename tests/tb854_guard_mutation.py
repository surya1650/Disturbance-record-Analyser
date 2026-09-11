"""Manual process-local mutation checks; never modify production files.

Run with PYTHONPATH=src, OPENBLAS_NUM_THREADS=1:
    python tests/tb854_guard_mutation.py distance
    python tests/tb854_guard_mutation.py branch
Exit 0 means pytest detected the bypass (the selected tests failed).
"""
import argparse
import inspect

import pytest

from dranalyser.faultloc import ensemble, estimators


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mutation", choices=("distance", "branch", "ambiguity", "external", "domain"))
    args = parser.parse_args()
    original_locate, original_std = ensemble.locate, estimators._circ_std
    original_e5, original_domain = estimators.e5_unsynchronised, ensemble.scalar_model_reasons
    try:
        if args.mutation == "distance":
            source = inspect.getsource(original_locate)
            guard = "if not (-0.5 <= m <= 1.5):"
            assert source.count(guard) == 1
            exec(compile(source.replace(guard, "if False:"), "<bypassed distance guard>", "exec"),
                 ensemble.__dict__)
            path, selected = "tests/test_stagea.py", "ensemble_refuses"
        elif args.mutation == 'ambiguity':
            source = inspect.getsource(original_e5)
            assert source.count('if tied:') == 1
            exec(compile(source.replace('if tied:', 'if False:'), '<bypassed ambiguity guard>', 'exec'), estimators.__dict__)
            path, selected = 'tests/test_tb854_validation.py', 'refuses_distinct_roots'
        elif args.mutation == 'external':
            source = inspect.getsource(original_locate)
            assert source.count('if not 0 <= m <= 1:') == 1
            exec(compile(source.replace('if not 0 <= m <= 1:', 'if False:'), '<bypassed external guard>', 'exec'), ensemble.__dict__)
            path, selected = 'tests/test_location_refusal_reports.py', 'external_result'
        elif args.mutation == 'domain':
            ensemble.scalar_model_reasons = lambda line: []
            path, selected = 'tests/test_model_domain.py', 'both_entrypoints'
        else:
            estimators._circ_std = lambda angles: 0.0
            path, selected = "tests/test_tb854_validation.py", "selects_stable_angle"
        code = pytest.main(["-q", path, "-k", selected, "--tb=short"])
        assert code == pytest.ExitCode.TESTS_FAILED, code
    finally:
        ensemble.locate, estimators._circ_std = original_locate, original_std
        estimators.e5_unsynchronised, ensemble.scalar_model_reasons = original_e5, original_domain
    print("Mutation detected; original functions restored; no production file was modified.")


if __name__ == "__main__":
    main()
