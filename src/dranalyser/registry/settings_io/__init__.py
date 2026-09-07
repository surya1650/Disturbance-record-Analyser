"""Settings importers, and the sniffing that picks between them.

`load_settings(path)` asks every registered importer how confident it is that
the file is its own format, takes the best, and records which one in the
result's provenance. **If two tie, it declines and says so.** Never guess a
format: a settings file misread as another vendor's produces zone reaches
that look plausible and are wrong.

Only this package may contain vendor-specific settings code, and
`scripts/check_architecture.py` enforces that.

Adding an importer
------------------
A module here exposes:

    FORMAT       str      short id recorded in provenance
    EXTENSIONS   tuple    hints only; sniffing is by content
    confidence(text, path) -> float in [0, 1]
    load(path) -> ProtectionSettings

then is added to `IMPORTERS` below. Do **not** write an importer against an
imagined format: there is no real .csv, .xml or .txt settings file in the
corpus yet, and one written speculatively will look finished, be wrong, and
be believed because it has tests. Ask the protection wing for one real sample
of each format first.
"""
from __future__ import annotations

import os
from typing import List, Sequence, Tuple

from ..settings import ProtectionSettings, SettingsError
from . import rio

IMPORTERS = (rio,)

# Below this, no importer is claiming the file at all.
MIN_CONFIDENCE = 0.30
# Two importers within this of each other is a tie, and a tie is refused.
TIE_MARGIN = 0.10


def _read_text(path: str, limit: int = 200_000) -> str:
    with open(path, "r", encoding="latin-1") as fh:
        return fh.read(limit)


def sniff(path: str, importers: Sequence = IMPORTERS) -> List[Tuple[float, object]]:
    """Every importer's confidence in this file, best first."""
    text = _read_text(path)
    scored = [(float(imp.confidence(text, path)), imp) for imp in importers]
    return sorted(scored, key=lambda t: -t[0])


def load_settings(path: str, importers: Sequence = IMPORTERS) -> ProtectionSettings:
    """Read a settings export of any supported format.

    Raises `SettingsError` when nothing recognises the file, and when two
    importers are too close to call.
    """
    if not os.path.exists(path):
        raise SettingsError("no such settings file: " + path)
    scored = sniff(path, importers)
    if not scored or scored[0][0] < MIN_CONFIDENCE:
        raise SettingsError(
            "no importer recognises " + os.path.basename(path)
            + " (best was " + (scored[0][1].FORMAT if scored else "none") + " at "
            + (format(scored[0][0], ".2f") if scored else "0") + ")")
    if len(scored) > 1 and (scored[0][0] - scored[1][0]) < TIE_MARGIN:
        raise SettingsError(
            "cannot tell which format " + os.path.basename(path) + " is: "
            + scored[0][1].FORMAT + " at " + format(scored[0][0], ".2f")
            + " against " + scored[1][1].FORMAT + " at "
            + format(scored[1][0], ".2f") + ". Refusing rather than guessing.")
    return scored[0][1].load(path)


__all__ = ["IMPORTERS", "load_settings", "sniff", "ProtectionSettings",
           "SettingsError"]
