"""Local analysis workbench.

A bundle is a set of files an operator has declared to be ONE incident.
PROJECT_CONTEXT.md §2.4 rules out emitting a report per file, so nothing in
here has a "analyse this file" entry point: the unit of work is the bundle.

This package sits above the analysis stack and below the CLI. Nothing
analytical may import it, so a change here can never move a number.
"""
from .bundle import (Bundle, BundleFile, assign, open_bundle, read_manifest,
                     write_manifest)

__all__ = ["Bundle", "BundleFile", "open_bundle", "read_manifest",
           "write_manifest", "assign"]
