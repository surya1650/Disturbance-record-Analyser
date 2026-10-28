"""Bounded display facts from exact observations, without electrical assumptions."""
from datetime import datetime
from bisect import bisect_left


def _recorded(value):
    try:
        return datetime.strptime(value.strip(), '%d/%m/%Y,%H:%M:%S.%f')
    except (ValueError, AttributeError):
        try:
            return datetime.strptime(value.strip(), '%d/%m/%Y,%H:%M:%S')
        except (ValueError, AttributeError):
            return None


def timeline(source):
    times = source['axis'].get('elapsed_s', [])
    recorded = source.get('recorded_times', {})
    start, trigger = (_recorded(recorded.get(k)) for k in ('start', 'trigger'))
    offset = (trigger-start).total_seconds() if start and trigger else None
    n = len(times)
    trigger_index = None
    if n and offset is not None and times[0] <= offset <= times[-1]:
        right = bisect_left(times, offset)
        trigger_index = right if right == 0 or times[right] == offset else right-1+(offset-times[right-1])/(times[right]-times[right-1])
    indices = sorted({round(i*(n-1)/min(512, n-1)) for i in range(min(512, n-1)+1)}) if n > 1 else list(range(n))
    return dict(trigger_offset_s=offset, trigger_index=trigger_index,
                start_local=start.isoformat(timespec='microseconds') if start else None,
                trigger_local=trigger.isoformat(timespec='microseconds') if trigger else None,
                ticks=[[i, times[i]] for i in indices],
                basis='Recorded relay-local time; timezone and clock accuracy unverified. Zero is the recorded trigger, not inferred fault inception.')


def digital_activity(states, times, *, limit=32):
    intervals, changes, omitted = [], 0, 0
    start = None
    for i, state in enumerate([*states, None]):
        if i and i < len(states) and state in (0, 1) and states[i-1] in (0, 1) and state != states[i-1]:
            changes += 1
        if state == 1 and start is None:
            start = i
        if state != 1 and start is not None:
            last = i-1
            if len(intervals) < limit:
                intervals.append(dict(start_index=start, last_index=last,
                    start_s=times[start] if times else None, last_s=times[last] if times else None,
                    observed_span_s=times[last]-times[start] if times else None,
                    start_open=start == 0 or states[start-1] is None,
                    end_open=i == len(states) or state is None))
            else:
                omitted += 1
            start = None
    return dict(transition_count=changes, high_intervals=intervals, omitted_intervals=omitted,
                high_samples=sum(v == 1 for v in states), unknown_samples=sum(v is None for v in states),
                basis='Recorded state 1 spans, not verified assertion polarity or physical relay operating time. Edges lie between adjacent samples.')
