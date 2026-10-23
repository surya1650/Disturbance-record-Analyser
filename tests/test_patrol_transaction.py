"""Real competing SQLite connections must not separate truth validation from writes."""

import threading

import pytest

from dranalyser.groundtruth import Confirmation, Store


@pytest.mark.parametrize("separate_connection", [False, True])
def test_confirmation_validation_and_rebind_are_one_transaction(tmp_path, separate_connection):
    path = str(tmp_path / "truth.db")
    capture = Store(path)
    update = Store(path) if separate_connection else capture
    capture.record_incident("A", "original", line_km=100, km_from_S=42)
    validated, release, rebind_done = threading.Event(), threading.Event(), threading.Event()
    failures, rebind_errors = [], []
    original_incident = capture.incident
    capturing_thread = None

    def pause_after_identity_read(identity):
        result = original_incident(identity)
        if threading.current_thread() is capturing_thread:
            validated.set()
            if not release.wait(5):
                raise AssertionError("Test failed to release paused capture.")
        return result

    capture.incident = pause_after_identity_read

    def confirm():
        try:
            capture.confirm(Confirmation("A", chainage_km=43))
        except Exception as exc:
            failures.append(exc)

    def rebind():
        try:
            update.record_incident("A", "different", line_km=200, km_from_S=5)
        except ValueError as exc:
            rebind_errors.append(exc)
        except Exception as exc:
            failures.append(exc)
        finally:
            rebind_done.set()

    capturing_thread = threading.Thread(target=confirm)
    updating_thread = threading.Thread(target=rebind)
    try:
        capturing_thread.start()
        assert validated.wait(5), "Capture did not reach the identity validation boundary."
        updating_thread.start()
        # Before the fix the rebind completes in this window. With a write
        # transaction it waits, then must see the newly committed patrol row.
        rebind_done.wait(0.3)
        release.set()
        capturing_thread.join(5)
        updating_thread.join(5)
        assert not capturing_thread.is_alive() and not updating_thread.is_alive()
        assert not failures
        assert capture.incident("A")["line_id"] == "original"
        assert capture.latest_confirmation("A")["chainage_km"] == 43
        assert len(rebind_errors) == 1
    finally:
        release.set()
        capturing_thread.join(5)
        if updating_thread.ident is not None:
            updating_thread.join(5)
        if separate_connection:
            update.close()
        capture.close()
