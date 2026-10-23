"""Immutable hash blobs survive a stale check concurrent with a reader."""
import io
from contextlib import ExitStack
from pathlib import Path

from dranalyser.application.intake import Intake
from tests import test_application as fixtures

environment = fixtures.environment


def test_duplicate_delivery_never_replaces_published_blob_after_stale_existence_check(environment, monkeypatch):
    _, app, source, _ = environment
    intake = Intake(app.state.store)

    def streams():
        return [(f'S/event.{ext}', io.BytesIO((source/'S'/f'event.{ext}').read_bytes())) for ext in ('cfg', 'dat')]

    first, duplicate = intake.ingest(streams())
    assert not duplicate
    blobs = list(intake.blobs.iterdir())
    identities = {p: p.stat().st_ino for p in blobs}
    contents = {p: p.read_bytes() for p in blobs}
    exists = Path.exists
    # Model the stale answer from before a competing writer published the blob.
    monkeypatch.setattr(Path, 'exists', lambda p: False if p in identities else exists(p))
    with ExitStack() as readers:
        for path in blobs:
            readers.enter_context(path.open('rb'))
        second, duplicate = intake.ingest(streams())
    assert duplicate and second['incident_id'] == first['incident_id']
    assert {p: p.stat().st_ino for p in blobs} == identities
    assert {p: p.read_bytes() for p in blobs} == contents
