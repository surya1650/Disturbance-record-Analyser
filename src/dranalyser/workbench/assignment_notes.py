"""Actionable operational refusals; inspection remains independent of assignment."""


def assignment_reason(record):
    if record.error:
        return record.error
    if not record.blocked:
        return 'duplicate of ' + record.duplicate_of
    blocks = [str(flag) for flag in record.flags if str(flag).startswith('[BLOCK')]
    detail = '; '.join(blocks[:5]) or 'The recording failed an operational input check.'
    if len(blocks) > 5:
        detail += f'; {len(blocks)-5} additional blocking findings in Input details'
    if any(('RATIO-P/S' in flag or 'RATIO-PS' in flag) for flag in blocks):
        action = 'Open Inputs & help, enter the actual missing CT/VT ratings and create a reviewed copy.'
    elif any('CH-MISSING' in flag or 'CH-COLLISION' in flag for flag in blocks):
        action = 'Review the channel meanings for this recording in Inputs & help.'
    elif any('TIME-' in flag for flag in blocks):
        action = 'Review timing evidence; source waveforms and actual-time source analysis remain available.'
    else:
        action = 'Open Input details for this recording and review the affected calculation prerequisites.'
    return 'blocked by the conformance gate: ' + detail + ' ' + action + ' Original waveforms remain viewable.'
