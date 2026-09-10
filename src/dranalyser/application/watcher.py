"""Store-and-forward adapter: completed event folders and ZIPs share Intake."""
from __future__ import annotations

import hashlib
from contextlib import ExitStack
from pathlib import Path

from .intake import MAX_BYTES, MAX_FILES, Intake


class Watcher:
    def __init__(self, intake: Intake, inbox):
        self.intake, self.inbox = intake, Path(inbox).resolve()
        self.inbox.mkdir(parents=True, exist_ok=True)

    def scan(self):
        """A .ready marker is the producer's declaration that one incident is complete.

        event.zip.ready accompanies event.zip; event/.ready completes a folder.
        Sources are never moved or deleted. Receipt fingerprints survive restarts.
        """
        count = 0
        for candidate in sorted(self.inbox.iterdir()):
            if candidate.is_symlink():
                continue
            if candidate.is_dir() and (candidate / ".ready").is_file():
                paths = sorted(p for p in candidate.rglob('*') if p.is_file() and p.name != '.ready')
                names = [p.relative_to(candidate).as_posix() for p in paths]
                marker = candidate / '.ready'
            elif candidate.suffix.lower() == '.zip' and Path(str(candidate) + '.ready').is_file():
                paths, names = [candidate], [candidate.name]
                marker = Path(str(candidate) + '.ready')
            else:
                continue
            fingerprint = ""
            try:
                if any(p.is_symlink() or not p.resolve().is_relative_to(self.inbox) for p in paths):
                    raise ValueError("Collector folders cannot contain links outside the inbox.")
                stats = [(n, p.stat().st_size, p.stat().st_mtime_ns) for n, p in zip(names, paths, strict=True)]
                fingerprint = hashlib.sha256(repr((stats, marker.stat().st_mtime_ns)).encode()).hexdigest()
                if self.intake.store.received(candidate, fingerprint):
                    continue
                if len(paths) > MAX_FILES or sum(s[1] for s in stats) > MAX_BYTES:
                    raise ValueError('Collector event exceeds the intake size or file-count limit.')
                with ExitStack() as stack:
                    streams = [(n, stack.enter_context(p.open('rb'))) for n, p in zip(names, paths, strict=True)]
                    row, duplicate = self.intake.ingest(streams, name=candidate.stem, source="folder")
                self.intake.store.receipt(candidate, fingerprint, "duplicate" if duplicate else "received",
                                          f"{row['incident_id']} revision {row['number']}")
                count += 1
            except Exception as exc:
                self.intake.store.receipt(candidate, fingerprint, "error", f"{type(exc).__name__}: {str(exc)[:400]}")
        return count

    def run(self, stop):
        while not stop.is_set():
            try:
                self.scan()
            except OSError as exc:
                self.intake.store.receipt(self.inbox, "", "error", str(exc)[:400])
            stop.wait(3)
