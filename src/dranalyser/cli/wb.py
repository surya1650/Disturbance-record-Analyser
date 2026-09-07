"""Workbench subcommands.

Kept out of `commands.py` so that file stays inside its growth budget and the
workbench can grow without dragging the rest of the CLI with it.
"""
from __future__ import annotations

import os
from typing import Dict, Tuple

from ..workbench import assign, open_bundle, write_manifest

BAR = "=" * 78


def _end_choices(args) -> Dict[str, Tuple[str, str]]:
    """`--S name --R name` on the command line, for scripted use.

    The browser form is the intended way in; these flags exist so a bundle
    can be assembled without one, and they name a FILE inside the bundle
    rather than a path, so argument order still decides nothing.
    """
    out: Dict[str, Tuple[str, str]] = {}
    for end in ("S", "R"):
        for name in (getattr(args, end) or []):
            out[name] = (end, "primary" if name == (getattr(args, end) or [""])[0]
                         else "corroborating")
    return out


def cmd_bundle(args) -> int:
    """Resolve a folder or zip into one incident and describe every file."""
    bundle = open_bundle(args.path, bundle_id=args.id or "")
    choices = _end_choices(args)
    refusals = assign(bundle, choices, line_id=args.line_id or "") if choices \
        else ([] if not args.line_id else assign(bundle, {}, args.line_id))

    print(BAR)
    print("BUNDLE  " + bundle.bundle_id
          + ("   line " + bundle.line_id if bundle.line_id else "   line not declared"))
    print("        " + bundle.root)

    recs = bundle.records()
    print(BAR)
    print("RECORDS  " + str(len(recs)) + " found, " + str(len(bundle.usable()))
          + " usable")
    for f in recs:
        state = ("OK      " if f.usable else
                 "DUPLICATE" if f.duplicate_of else
                 "BLOCKED " if f.blocked else "UNREADABLE")
        where = (f.terminal_end + "/" + f.role) if f.terminal_end else "-"
        print("  " + state + "  " + f.name)
        if f.ok:
            print("            " + (f.station or "(no station)")
                  + "   fs=" + format(f.fs_hz, ".1f") + " Hz   "
                  + str(f.samples) + " smp   trigger " + (f.trigger_time or "-"))
            print("            end: " + where + "   hash " + f.content_hash[:12])
        if f.error:
            print("            " + f.error)
        if f.duplicate_of:
            print("            byte-identical to " + f.duplicate_of)
        for fl in f.flags:
            if fl.startswith("[BLOCK"):
                print("            " + fl)

    setts = bundle.settings()
    if setts:
        print(BAR)
        print("SETTINGS  " + str(len(setts)) + " export(s)")
        for f in setts:
            print("  " + f.name)

    if refusals:
        print(BAR)
        print("REFUSED:")
        for r in refusals:
            print("  " + r)

    out = args.out or os.path.join(bundle.root, "_asset.yaml")
    write_manifest(bundle, out)
    print(BAR)
    print("wrote " + out)
    return 2 if refusals else 0


def cmd_workbench(args) -> int:
    """Serve the upload-and-analyse workbench on this machine."""
    from ..workbench.server import serve

    serve(root=args.root, host=args.host, port=args.port,
          registry_dir=args.registry)
    return 0
