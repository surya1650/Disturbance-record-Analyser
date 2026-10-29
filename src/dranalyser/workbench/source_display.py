"""Bounded display facts from exact source observations, without relay assumptions."""
from bisect import bisect_left
from datetime import datetime
from decimal import Decimal
import re


def _recorded(value):
    if not isinstance(value, str) or len(value) > 64:
        return None
    match = re.fullmatch(r'(\d{1,2}/\d{1,2}/\d{4},\d{1,2}:\d{2}:\d{2})(?:\.(\d{1,9}))?', value.strip())
    if not match:
        return None
    try:
        base = datetime.strptime(match[1], '%d/%m/%Y,%H:%M:%S')
    except ValueError:
        return None
    fraction = match[2] or '0'
    return base, Decimal('0.' + fraction), base.isoformat() + '.' + fraction.ljust(6, '0')


def timeline(source):
    times = source['axis'].get('elapsed_s', [])
    recorded = source.get('recorded_times', {})
    start, trigger = (_recorded(recorded.get(k)) for k in ('start', 'trigger'))
    offset = None
    if start and trigger:
        offset = float(Decimal(int((trigger[0] - start[0]).total_seconds())) + trigger[1] - start[1])
    n, trigger_index = len(times), None
    if n and offset is not None and times[0] <= offset <= times[-1]:
        right = bisect_left(times, offset)
        trigger_index = right if right == 0 or times[right] == offset else (
            right - 1 + (offset - times[right - 1]) / (times[right] - times[right - 1]))
    indices = sorted({round(i * (n - 1) / min(512, n - 1)) for i in range(min(512, n - 1) + 1)}) if n > 1 else list(range(n))
    return dict(trigger_offset_s=offset, trigger_index=trigger_index,
        start_local=start[2] if start else None, trigger_local=trigger[2] if trigger else None,
        ticks=[[i, times[i]] for i in indices],
        basis='Recorded relay-local time; timezone and clock accuracy unverified. Zero is the recorded trigger, '
              'not inferred fault inception. Fractional trigger index is a display coordinate only.')


def digital_activity(states, times, *, limit=32, break_indices=()):
    """Summarize state 1 with sampled-span lower bounds; never infer asserted polarity."""
    timed = len(times) == len(states) and bool(times)
    boundaries = set(break_indices)
    intervals, omitted, rises, falls, unknown, high = [], 0, 0, 0, 0, 0
    first_transition, start, span = None, None, 0.0

    def finish(last, end_open):
        nonlocal omitted
        if len(intervals) < limit:
            intervals.append(dict(start_index=start, last_index=last,
                start_s=times[start] if timed else None, last_s=times[last] if timed else None,
                observed_span_s=times[last] - times[start] if timed else None,
                start_open=start == 0 or start in boundaries or states[start - 1] not in (0, 1),
                end_open=end_open))
        else:
            omitted += 1

    for i, state in enumerate(states):
        previous = states[i - 1] if i else None
        if i in boundaries and start is not None:
            finish(i - 1, True)
            start = None
        if state not in (0, 1):
            unknown += 1
        elif state == 1:
            high += 1
        if i and i not in boundaries and state in (0, 1) and previous in (0, 1):
            if state != previous:
                rises += state == 1
                falls += state == 0
                if first_transition is None:
                    first_transition = i
            elif state == 1 and timed:
                span += times[i] - times[i - 1]
        if state == 1 and start is None:
            start = i
        elif state != 1 and start is not None:
            finish(i - 1, state not in (0, 1))
            start = None
    if start is not None:
        finish(len(states) - 1, True)
    return dict(transition_count=rises + falls, rising_count=rises, falling_count=falls,
        first_transition_index=first_transition, high_intervals=intervals, omitted_intervals=omitted,
        high_samples=high, active_samples=high, unknown_samples=unknown,
        active_duration_s=span if timed else None,
        basis='Recorded state 1 sampled spans only, not verified assertion polarity or physical relay operating time. '
              'Duration sums adjacent known high samples; unobserved edges and gaps are excluded. '
              'Source boundaries remain open; single high samples have zero observed span, not zero pulse duration.')


def display_facts(source):
    """Call once within the owning two-source cache; details stay within 512 intervals."""
    times = source['axis'].get('elapsed_s', [])
    boundaries = set(source.get('break_indices', []))
    if len(times) > 1:
        minimum = min(b - a for a, b in zip(times, times[1:], strict=False))
        boundaries.update(i for i in range(1, len(times)) if times[i] - times[i - 1] > minimum * 8)
    activities, remaining = {}, 512
    for channel in source['digital']:
        activity = digital_activity(channel['states'], times, limit=min(32, remaining), break_indices=boundaries)
        activities[channel['key']] = activity
        remaining -= len(activity['high_intervals'])
    ordered = sorted(boundaries)
    return dict(timeline=timeline(source), activities=activities, break_indices=ordered[:512],
        omitted_break_indices=max(0, len(ordered) - 512),
        gap_policy='Display-only discontinuity at explicit breaks or intervals over eight times the minimum source period.')
