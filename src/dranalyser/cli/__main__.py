"""Allows `python -m dranalyser.cli ...` as well as the `dranalyse` script."""
from __future__ import annotations

import sys

from . import main

if __name__ == "__main__":
    sys.exit(main())
