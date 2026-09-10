"""Shared immutable file intake for browser, API and folder collectors."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from .store import Conflict, Store
from ..workbench.channel_mapping import clean_mapping
from ..workbench.rx_review import clean_rx_review
from ..workbench.stage_review import clean_stage_review

MAX_BYTES = 400 * 1024 * 1024
MAX_FILES = 2000
BLOCKED_NAMES = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", re.I)


def safe_name(name):
    name = str(name).replace("\\", "/")
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or any(p in ("", ".", "..") for p in name.split('/'))
            or any(':' in p or p.endswith((' ', '.')) or BLOCKED_NAMES.match(p) for p in path.parts)
            or any(ord(c) < 32 for c in name) or len(name) > 220):
        raise ValueError(f"Unsafe file path: {name[:100]}")
    return path.as_posix()


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def metadata_value(raw):
    if not isinstance(raw, dict) or set(raw) - {"line_id", "assignments", "auto_analyse", "incident_id"}:
        raise ValueError("Metadata accepts line_id, assignments, auto_analyse and incident_id only.")
    line_id = raw.get("line_id", "")
    choices = raw.get("assignments", {})
    if not isinstance(line_id, str) or len(line_id) > 200 or not isinstance(choices, dict):
        raise ValueError("Invalid line_id or assignments.")
    cleaned = {}
    for name, value in choices.items():
        name = safe_name(name)
        if not isinstance(value, dict) or set(value) - {"end", "role", "protection_system", "recording_profile", "channel_mapping", "rx_review", "stage_review"}:
            raise ValueError(f"Invalid assignment: {name}")
        end, role = value.get("end", ""), value.get("role", "excluded")
        if end not in ("", "S", "R") or role not in ("primary", "corroborating", "excluded"):
            raise ValueError(f"Invalid end or role for {name}")
        if (role == "excluded" and end) or (role != "excluded" and not end):
            raise ValueError("Excluded records have no end; selected records require S or R.")
        cleaned[name] = {"end": end, "role": role}
        system = value.get("protection_system", "unknown")
        if system not in ("unknown", "Main-1", "Main-2", "other"):
            raise ValueError(f"Invalid protection system for {name}")
        if system != "unknown":
            cleaned[name]["protection_system"] = system
        profile = value.get('recording_profile', 'unconfirmed')
        if profile not in ('unconfirmed', 'wg3-132-distance', 'wg3-132-backup', 'wg3-220plus-distance'):
            raise ValueError(f'Invalid recording profile for {name}')
        if profile != 'unconfirmed':
            cleaned[name]['recording_profile'] = profile
        mapping = clean_mapping(value.get('channel_mapping'))
        if mapping:
            cleaned[name]['channel_mapping'] = mapping
        review = clean_rx_review(value.get('rx_review'))
        if review:
            cleaned[name]['rx_review'] = review
        stage_review = clean_stage_review(value.get('stage_review'))
        if stage_review:
            cleaned[name]['stage_review'] = stage_review
    auto = raw.get("auto_analyse", False)
    target = raw.get("incident_id")
    if not isinstance(auto, bool) or (target is not None and not re.fullmatch(r"[0-9a-f]{32}", str(target))):
        raise ValueError("Invalid auto_analyse or incident_id.")
    return {"line_id": line_id, "assignments": cleaned, "auto_analyse": auto, "incident_id": target}


class Intake:
    def __init__(self, store: Store):
        self.store = store
        self.blobs = store.root / "blobs"
        self.blobs.mkdir(exist_ok=True)

    def ingest(self, streams, *, name="Uploaded incident", source="manual", metadata=None,
               incident_id=None, expected=None):
        """streams contains (relative name, binary file object); callers retain ownership."""
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise ValueError("Incident name must contain 1 to 200 characters.")
        inventory, total = {}, 0
        with tempfile.TemporaryDirectory(prefix="dr-intake-", dir=self.store.root) as tmp:
            stage = Path(tmp)

            def save(filename, stream):
                nonlocal total
                filename = safe_name(filename)
                if len(inventory) >= MAX_FILES:
                    raise ValueError(f"Intake exceeds {MAX_FILES} files.")
                if filename.casefold() in {n.casefold() for n in inventory}:
                    raise ValueError(f"Duplicate filename in upload: {filename}; use terminal subfolders.")
                target = stage / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as out:
                    while chunk := stream.read(1024 * 1024):
                        total += len(chunk)
                        if total > MAX_BYTES:
                            raise ValueError("Upload or expanded archive exceeds 400 MB.")
                        out.write(chunk)
                inventory[filename] = {"name": filename, "sha256": digest(target), "size": target.stat().st_size}

            for filename, stream in streams:
                filename = safe_name(filename)
                if filename.lower().endswith(".zip"):
                    # Keep compressed input outside the expanded namespace.
                    with tempfile.TemporaryFile() as archive:
                        compressed = 0
                        while chunk := stream.read(1024 * 1024):
                            compressed += len(chunk)
                            if compressed > MAX_BYTES:
                                raise ValueError("Archive exceeds 400 MB.")
                            archive.write(chunk)
                        archive.seek(0)
                        with zipfile.ZipFile(archive) as zf:
                            if len(zf.infolist()) > MAX_FILES:
                                raise ValueError("Archive contains too many entries.")
                            for member in zf.infolist():
                                safe_name(member.filename.rstrip('/'))
                                if member.is_dir():
                                    continue
                                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                                    raise ValueError("Archive symbolic links are not supported.")
                                if member.file_size + total > MAX_BYTES or member.flag_bits & 1:
                                    raise ValueError("Archive is encrypted or exceeds the expanded size limit.")
                                with zf.open(member) as content:
                                    save(member.filename, content)
                else:
                    save(filename, stream)
            if not inventory:
                raise ValueError("No files supplied.")
            embedded = {}
            if "intake.json" in inventory:
                if inventory["intake.json"]["size"] > 1024 * 1024:
                    raise ValueError("intake.json exceeds 1 MB.")
                embedded = json.loads((stage / "intake.json").read_text(encoding="utf-8"))
            meta = metadata_value(metadata if metadata is not None else embedded)
            target_id = incident_id or meta.pop("incident_id", None)
            meta.pop("incident_id", None)
            previous = self.store.get(target_id) if target_id else None
            if target_id and previous is None:
                raise KeyError(target_id)
            files = {f["name"]: f for f in previous["files"]} if previous else {}
            for filename, entry in inventory.items():
                if filename == "intake.json":
                    continue
                match = next((n for n in files if n.casefold() == filename.casefold()), None)
                if match and files[match]["sha256"] != entry["sha256"]:
                    raise Conflict(f"{filename} already exists with different content. Use a distinct terminal folder.")
                files[filename] = entry
            if not any(n.lower().endswith((".cfg", ".cff")) for n in files):
                raise ValueError("Supply a COMTRADE CFG/DAT pair or CFF, optionally inside a ZIP.")
            if previous:
                old = previous["metadata"]
                meta["line_id"] = meta["line_id"] or old.get("line_id", "")
                meta["assignments"] = {**old.get("assignments", {}), **meta["assignments"]}
            fingerprint = hashlib.sha256(json.dumps(
                {"target": target_id, "files": sorted(files.values(), key=lambda f: f["name"]), "metadata": meta},
                sort_keys=True).encode()).hexdigest()
            for filename, entry in inventory.items():
                dest = self.blobs / entry["sha256"]
                if not dest.exists():
                    # Atomic replacement is harmless for identical hash content.
                    os.replace(stage / filename, dest)
            return self.store.submit(name=name.strip(), source=source, files=list(files.values()),
                                     metadata=meta, fingerprint=fingerprint, incident_id=target_id,
                                     expected=expected if expected is not None else
                                     (previous["number"] if previous else None))

    def materialize(self, job):
        path = self.store.root / "runs" / job["incident_id"] / str(job["number"]) / job["owner"]
        records = path / "records"
        records.mkdir(parents=True)
        for entry in job["files"]:
            target = records / safe_name(entry["name"])
            target.parent.mkdir(parents=True, exist_ok=True)
            blob = self.blobs / entry["sha256"]
            if digest(blob) != entry["sha256"]:
                raise ValueError(f"Stored content failed checksum: {entry['name']}")
            shutil.copyfile(blob, target)
        return path, records
