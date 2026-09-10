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
    parser.add_argument("mutation", choices=("distance", "branch"))
    args = parser.parse_args()
    original_locate, original_std = ensemble.locate, estimators._circ_std
    try:
        if args.mutation == "distance":
            source = inspect.getsource(original_locate)
            guard = "if not (-0.5 <= m <= 1.5):"
            assert source.count(guard) == 1
            exec(compile(source.replace(guard, "if False:"), "<bypassed distance guard>", "exec"),
                 ensemble.__dict__)
            path, selected = "tests/test_stagea.py", "ensemble_refuses"
        else:
            estimators._circ_std = lambda angles: 0.0
            path, selected = "tests/test_tb854_validation.py", "selects_stable_angle"
        code = pytest.main(["-q", path, "-k", selected, "--tb=short"])
        assert code == pytest.ExitCode.TESTS_FAILED, code
    finally:
        ensemble.locate, estimators._circ_std = original_locate, original_std
    print("Mutation detected; original functions restored; no production file was modified.")


if __name__ == "__main__":
    main()
