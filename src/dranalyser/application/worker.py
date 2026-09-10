"""Lease-based jobs around the existing parser, resolver and incident analyser."""
from __future__ import annotations

import dataclasses
import math
import threading
from pathlib import Path

from ..registry.loader import load_line
from ..workbench.bundle import assign, open_bundle
from ..workbench.incident import analyse_bundle, default_line_files
from ..workbench.resolve import suggest
from ..workbench.settings import settings_by_record
from .intake import Intake, metadata_value
from .store import Store


def registry_entries(directory):
    entries = []
    for filename in default_line_files(str(directory)):
        try:
            line = load_line(filename)
            text = Path(filename).read_text(encoding="utf-8")
            entries.append({"id": line.id, "name": line.name, "kv": line.kv,
                            "path": str(Path(filename).resolve()),
                            "parameter_status": "provisional" if "PROVISIONAL" in text.upper() else "unverified",
                            "terminals": {e: t.substation for e, t in line.terminals.items()}})
        except Exception as exc:
            entries.append({"id": "", "name": Path(filename).name, "error": str(exc)[:250]})
    return entries


def validate_assignments(bundle, raw, registry):
    from ..workbench.channel_mapping import prepare_mappings
    meta = metadata_value(raw)
    prepare_mappings(bundle, meta['assignments'])
    paths = [x["path"] for x in registry_entries(registry) if x["id"] == meta["line_id"]]
    if meta["line_id"] and len(paths) != 1:
        raise ValueError("Selected line must resolve to exactly one registry definition.")
    choices = {n: (v["end"], v["role"]) for n, v in meta["assignments"].items()}
    refusals = assign(bundle, choices, line_id=meta["line_id"])
    for f in bundle.records():
        f.protection_system = meta["assignments"].get(f.name, {}).get("protection_system", "unknown")
        f.recording_profile = meta["assignments"].get(f.name, {}).get("recording_profile", "unconfirmed")
        f.rx_review = meta['assignments'].get(f.name, {}).get('rx_review', {})
        f.stage_review = meta['assignments'].get(f.name, {}).get('stage_review', {})
    for f in bundle.usable():
        if f.name not in choices:
            refusals.append(f"Choose an end or explicitly exclude {f.name}.")
    selected = [f for f in bundle.usable() if f.terminal_end]
    if not selected:
        refusals.append("Select at least one usable primary record.")
    for end in ("S", "R"):
        at_end = [f for f in selected if f.terminal_end == end]
        if at_end and sum(f.role == "primary" for f in at_end) != 1:
            refusals.append(f"End {end} requires exactly one primary; other records may corroborate it.")
    if refusals:
        raise ValueError(" ".join(refusals))
    bundle.line_path = paths[0] if paths else ""
    return meta


def finite(value):
    if isinstance(value, complex):
        return {'real': finite(value.real), 'imag': finite(value.imag)}
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: finite(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite(v) for v in value]
    return value


class Worker:
    def __init__(self, store: Store, registry):
        self.store, self.registry = store, Path(registry).resolve()

    def once(self):
        job = self.store.claim()
        if not job:
            return False
        done = threading.Event()

        def keep_alive():
            while not done.wait(10):
                if not self.store.heartbeat(job):
                    return

        beat = threading.Thread(target=keep_alive, daemon=True)
        beat.start()
        try:
            run, records = Intake(self.store).materialize(job)
            bundle = open_bundle(str(records), bundle_id=job["incident_id"])
            suggest(bundle, str(self.registry))
            _, bindings, _ = settings_by_record(bundle, [f.name for f in bundle.records()])
            for f in bundle.records():
                f.settings_source = bindings[f.name]
            if job["stage"] == "inspect" and not job["metadata"].get("auto_analyse"):
                self.store.finish(job, "needs_review", bundle=dataclasses.asdict(bundle))
                return True
            try:
                validate_assignments(bundle, job["metadata"], self.registry)
            except ValueError as exc:
                self.store.finish(job, "needs_review", bundle=dataclasses.asdict(bundle), error=str(exc))
                return True
            for record in bundle.records():
                if record.terminal_end:
                    record.assignment_source = 'collector manifest' if job['stage'] == 'inspect' else 'operator'
            # Freeze the exact registry definition used by this attempt.
            line_path = bundle.line_path
            if line_path:
                snapshot = run / "line.yaml"
                snapshot.write_bytes(Path(line_path).read_bytes())
                line_path = str(snapshot)
            res = analyse_bundle(bundle, line_path=line_path, out_dir=str(run / "report"))
            result = finite(dataclasses.asdict(res))
            result["line_snapshot"] = line_path
            result["parameter_status"] = next((x["parameter_status"] for x in registry_entries(self.registry)
                                                if x["id"] == bundle.line_id), "not supplied")
            self.store.finish(job, "completed" if res.report_path and not res.errors else "attention",
                              bundle=dataclasses.asdict(bundle), result=result,
                              error="; ".join(res.errors))
        except Exception as exc:
            self.store.finish(job, "failed", error=f"{type(exc).__name__}: {str(exc)[:600]}")
        finally:
            done.set()
            beat.join(timeout=2)
        return True

    def run(self, stop):
        while not stop.is_set():
            if not self.once():
                stop.wait(0.5)
