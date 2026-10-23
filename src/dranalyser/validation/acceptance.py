"""Frozen held-out evaluation with refusals and uncertain patrol truth retained."""
from __future__ import annotations

import math
from collections import Counter
from datetime import datetime


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def percentile(values, fraction):
    if not values:
        return None
    values = sorted(values)
    index = (len(values)-1)*fraction
    low, high = math.floor(index), math.ceil(index)
    return values[low]+(values[high]-values[low])*(index-low)


def _stamp(value):
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('A timezone is required.')
    return stamp


def evaluate(protocol, cases):
    """Cases are runner-verified outcomes; declarations alone cannot verify physics."""
    problems = []
    planned = protocol.get('planned_event_ids', [])
    if not planned or len(set(planned)) != len(planned):
        problems.append('Freeze a nonempty unique planned_event_ids cohort before execution.')
    if set(planned) != {r.get('event_id') for r in cases}:
        problems.append('Executed events do not match the frozen cohort.')
    required = ('min_events', 'max_p95_error_pct', 'min_located_fraction')
    if (not isinstance(protocol.get('min_events'), int) or isinstance(protocol.get('min_events'), bool)
            or protocol['min_events'] < 1 or not finite(protocol.get('max_p95_error_pct'))
            or protocol['max_p95_error_pct'] <= 0 or not finite(protocol.get('min_located_fraction'))
            or not 0 < protocol['min_located_fraction'] <= 1):
        problems.append('Freeze valid project-specific '+', '.join(required)+' criteria.')
    try:
        frozen = _stamp(protocol.get('frozen_at', ''))
    except (ValueError, TypeError, AttributeError):
        frozen = None
        problems.append('A timezone-aware frozen_at timestamp is required.')
    counts = Counter(r.get('event_id') for r in cases)
    hashes = Counter(h for r in cases for h in set(r.get('record_hashes', [])))
    training_lines = set(protocol.get('training_line_ids', []))
    rows, located, errors, worst_errors, interval_contains_truth = [], [], [], [], []
    for case in cases:
        row = dict(case)
        reasons = list(case.get('reasons', []))
        if counts[case.get('event_id')] != 1:
            reasons.append('Duplicate physical event ID.')
        if any(hashes[h] > 1 for h in case.get('record_hashes', [])):
            reasons.append('Recording reused across acceptance events; leakage or duplicate incident.')
        if case.get('line_id') in training_lines:
            reasons.append('Held-out event is on a declared training line.')
        if not case.get('record_hashes'):
            reasons.append('No verified recording hashes.')
        if len(case.get('record_hashes', [])) != len(set(case.get('record_hashes', []))):
            reasons.append('The same recording cannot represent distinct terminals.')
        try:
            if frozen is None or _stamp(case.get('executed_at', '')) < frozen:
                reasons.append('Execution predates the frozen protocol.')
        except (ValueError, TypeError, AttributeError):
            reasons.append('Execution timestamp unavailable.')
        length, truth, uncertainty = (case.get(k) for k in ('line_km', 'truth_km', 'truth_uncertainty_km'))
        if not (finite(length) and length > 0 and finite(truth) and finite(uncertainty)
                and uncertainty >= 0 and 0 <= truth-uncertainty <= truth+uncertainty <= length):
            reasons.append('Finite in-line patrol truth and its uncertainty are required.')
        estimate = case.get('estimated_km')
        if estimate is not None and (not finite(estimate) or not finite(length) or not 0 <= estimate <= length):
            reasons.append('Invalid/external distance cannot be scored as a protected-line location.')
        if case.get('evidence_verified') is not True:
            reasons.append('Source files, approvals and independent patrol evidence are not verified by the runner.')
        row['reasons'] = reasons
        row['eligible'] = not reasons
        if reasons:
            row['status'] = 'excluded; missing or invalid acceptance evidence'
        elif estimate is None:
            row['status'] = 'refused'
        else:
            row['status'] = 'located'
            error = abs(estimate-truth)
            row.update(error_km=error, error_pct=100*error/length,
                       best_case_error_pct=100*max(0., error-uncertainty)/length,
                       worst_case_error_pct=100*(error+uncertainty)/length)
            errors.append(row['error_pct'])
            worst_errors.append(row['worst_case_error_pct'])
            located.append(row)
            interval = case.get('diagnostic_interval_km')
            if interval is not None:
                if (isinstance(interval, (list, tuple)) and len(interval) == 2 and all(finite(v) for v in interval)
                        and 0 <= interval[0] <= interval[1] <= length):
                    contains = interval[0] <= truth-uncertainty and truth+uncertainty <= interval[1]
                    row['diagnostic_interval_contains_entire_truth_band'] = contains
                    interval_contains_truth.append(contains)
                else:
                    row['diagnostic_interval_issue'] = 'Invalid interval; omitted from descriptive coverage.'
        rows.append(row)
    eligible = [r for r in rows if r['eligible']]
    excluded = len(rows)-len(eligible)
    located_fraction = len(located)/len(eligible) if eligible else None
    within = sum(e <= protocol.get('max_p95_error_pct', 0) for e in worst_errors) if finite(protocol.get('max_p95_error_pct')) else 0
    if excluded:
        problems.append('Frozen cohort contains excluded events; acceptance cannot pass by dropping them.')
    if not eligible or (isinstance(protocol.get('min_events'), int) and len(eligible) < protocol['min_events']):
        problems.append('Not enough independently confirmed held-out events.')
    status = 'not_ready' if problems else 'pass' if (
        percentile(worst_errors, .95) is not None and percentile(worst_errors, .95) <= protocol['max_p95_error_pct']
        and located_fraction >= protocol['min_located_fraction']) else 'fail'
    return {'status': status, 'protocol_issues': problems, 'total_events': len(rows),
        'eligible_events': len(eligible), 'excluded_events': excluded, 'located_events': len(located),
        'refused_events': len(eligible)-len(located), 'located_fraction': located_fraction,
        'mae_pct': sum(errors)/len(errors) if errors else None, 'p95_error_pct': percentile(errors, .95),
        'p95_worst_case_error_pct': percentile(worst_errors, .95),
        'within_threshold_fraction_all_eligible': within/len(eligible) if eligible else None,
        'diagnostic_interval_cases': len(interval_contains_truth),
        'diagnostic_interval_contains_truth_fraction': sum(interval_contains_truth)/len(interval_contains_truth) if interval_contains_truth else None,
        'limits': 'Project-specific retrospective acceptance on the frozen cohort only. Source hashes bind files; '
                  'they do not authenticate reviewers or prove correct field parameters/wiring. Diagnostic interval '
                  'coverage is descriptive on this cohort, not calibrated confidence or TB 854 certification.',
        'cases': rows}
