"""Declared record dates stay independent of generation clock and time-zone guesses."""
import pytest

from dranalyser.workbench.incident_report_time import recorded_clock


def test_cfg_dates_and_fractional_precision_are_preserved_without_timezone_or_sync_claim():
    clock = recorded_clock(dict(start='05/11/2026,23:59:59.123456789', trigger='06/11/2026,00:00:00.000000001'))
    assert clock['start_display'] == '05 Nov 2026 23:59:59.123456789'
    assert clock['trigger_local_iso'] == '2026-11-06T00:00:00.000000001'
    assert clock['start']['precision_digits'] == 9
    assert clock['timezone_label'] == 'Not declared'
    assert clock['cursor_time_status'] == 'unavailable'
    assert not clock['alignment_eligible'] and not clock['clock_accuracy_verified']


@pytest.mark.parametrize('stamp', ['31/02/2026,12:00:00', '2026-11-05T12:00:00Z',
    '11/05/26,12:00:00', '05/11/2026,25:00:00', '05/11/2026,12:00:00.1234567890', '<script>bad</script>'])
def test_invalid_or_unsupported_clock_strings_are_retained_not_repaired(stamp):
    clock = recorded_clock({'start': stamp})
    assert clock['start']['raw'] == stamp and clock['start_display'] == stamp
    assert clock['start_local_iso'] is None
    assert clock['start']['status'] == 'unparsed'


def test_missing_clock_is_named_unknown_and_never_uses_report_generation_time():
    clock = recorded_clock(None)
    assert clock['start_display'] == clock['trigger_display'] == 'Not recorded'
    assert clock['start_local_iso'] is None
