from types import SimpleNamespace

from dranalyser.workbench.assignment_notes import assignment_reason


def test_ratio_refusal_identifies_fix_without_suppressing_other_blocks():
    file = SimpleNamespace(error='', blocked=True, duplicate_of='', flags=[
        '[BLOCK RATIO-PS] IA secondary with primary=1, secondary=0',
        '[BLOCK TIME-DAT] Timestamp intervals need review'])
    reason = assignment_reason(file)
    assert 'RATIO-PS' in reason and 'TIME-DAT' in reason
    assert 'actual missing CT/VT ratings' in reason
    assert 'Original waveforms remain viewable' in reason
    assert file.flags[0].endswith('secondary=0')


def test_bounded_error_duplicate_and_timing_refusals():
    file = SimpleNamespace(error='Missing data file', blocked=True, duplicate_of='', flags=[])
    assert assignment_reason(file) == 'Missing data file'
    file.error, file.blocked, file.duplicate_of = '', False, 'source.cfg'
    assert assignment_reason(file) == 'duplicate of source.cfg'
    file.blocked, file.flags = True, ['[BLOCK TIME-DAT] gap'] * 9
    reason = assignment_reason(file)
    assert '4 additional blocking findings' in reason
    assert 'actual-time source analysis remain available' in reason
