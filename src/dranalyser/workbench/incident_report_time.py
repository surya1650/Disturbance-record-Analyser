"""Recorded local clock labels without inventing a DAT/CFG clock anchor."""
from datetime import datetime
import re

_STAMP = re.compile(r'^(\d{1,2})/(\d{1,2})/(\d{4}),(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d{1,9}))?$')


def _local_stamp(value):
    raw = value.strip() if isinstance(value, str) else ''
    match = _STAMP.fullmatch(raw)
    if match is None:
        return dict(raw=raw or None, display=raw or 'Not recorded', local_iso=None,
                    status='unparsed' if raw else 'unavailable')
    day, month, year, hour, minute, second = map(int, match.groups()[:6])
    fraction = match[7] or ''
    try:
        stamp = datetime(year, month, day, hour, minute, second)
    except ValueError:
        return dict(raw=raw, display=raw, local_iso=None, status='unparsed')
    suffix = '.'+fraction if fraction else ''
    local = f'{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}'
    return dict(raw=raw, display=f'{day:02d} '+stamp.strftime('%b')+f' {year:04d} {hour:02d}:{minute:02d}:{second:02d}'+suffix,
                local_iso=local+suffix,
                precision_digits=len(fraction), status='declared local clock')


def recorded_clock(recorded_times):
    """Expose the original record date/time, not the report-generation clock."""
    times = recorded_times if isinstance(recorded_times, dict) else {}
    start, trigger = _local_stamp(times.get('start')), _local_stamp(times.get('trigger'))
    return dict(start=start, trigger=trigger, start_display=start['display'],
        trigger_display=trigger['display'], start_local_iso=start['local_iso'],
        trigger_local_iso=trigger['local_iso'], timezone_label='Not declared',
        time_basis='Recorder-local CFG strings; no time zone or common clock is established.',
        cursor_time_status='unavailable',
        cursor_time_reason='Cursor uses elapsed source time; an absolute cursor-clock anchor is not established.',
        alignment_eligible=False, clock_accuracy_verified=False)
