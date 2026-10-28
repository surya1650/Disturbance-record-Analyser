"""Vendor-independent joining preserves provenance and checks derived export."""
import copy
import io
import json
import zipfile

import pytest

from dranalyser.comtrade.source_decode import decode_source
from dranalyser.workbench.source_export import export_join
from dranalyser.workbench.source_join import join_sources
from dranalyser.workbench.source_rms import sample_rms


def capture(name, start='00:00:00.000000', values=None):
    cfg = (f'STATION,RELAY,1999\n2,1A,1D\n1,VA,A,,V,2,3,0,-32768,32767,1,1,P\n'
           f'1,Trip,,,0\n50\n0\n0,40\n01/01/2026,{start}\n01/01/2026,{start}\nASCII\n1\n').encode()
    values = values if values is not None else list(range(40))
    dat = ''.join(f'{i+1},{i*1000},{v},{int(i>=20)}\n' for i, v in enumerate(values)).encode()
    source = decode_source(cfg, dat, cfg_name=name+'.cfg', dat_name=name+'.dat')
    assert source['status'] == 'observed'
    return name+'.cfg', source


def unpack(blob):
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        return (decode_source(archive.read('joined.cfg'), archive.read('joined.dat'),
                              cfg_name='joined.cfg', dat_name='joined.dat'),
                json.loads(archive.read('provenance.json')))


def test_successive_captures_round_trip_all_samples_states_and_triggers():
    a, b = capture('a'), capture('b', '00:00:00.040000')
    before = copy.deepcopy([a, b])
    joined = join_sources([b, a])
    assert joined['sample_count'] == 80
    assert joined['channels'][0]['values'] == a[1]['channels'][0]['values']+b[1]['channels'][0]['values']
    assert joined['join']['sources'][0]['file'] == 'a.cfg'
    assert joined['break_indices'] == [40]
    assert joined['_origins'][40] == ['b.cfg', 0]
    assert joined['authorizes_location'] is False
    assert joined['join']['sources'][0]['recorded_times'] == a[1]['recorded_times']
    decoded, manifest = unpack(export_join(joined))
    assert decoded['channels'][0]['values'] == joined['channels'][0]['values']
    assert 'DERIVED JOIN' in decoded['device']
    assert decoded['digital'][0]['states'] == joined['digital'][0]['states']
    assert len(manifest['source_samples']) == 80
    assert manifest['source_names'][manifest['source_samples'][40][0]] == 'b.cfg'
    assert manifest['source_samples'][40][1] == 0
    assert manifest['amplitude_max_absolute_error']['A1'] == 0
    assert [a, b] == before


def test_source_boundaries_split_high_spans_without_inventing_transition_edges():
    from dranalyser.workbench.source_display import digital_activity
    result = digital_activity([1, 1, 1, 1], [0, .001, .1, .101], break_indices=[2])
    assert result['transition_count'] == 0
    assert len(result['high_intervals']) == 2
    assert result['high_intervals'][0]['end_open']
    assert result['high_intervals'][1]['start_open']
    assert result['high_intervals'][1]['observed_span_s'] == pytest.approx(.001)


def test_overlap_is_retained_and_ordered_without_silent_deduplication():
    joined = join_sources([capture('a'), capture('b', '00:00:00.038500')])
    assert joined['sample_count'] == 80
    assert joined['join']['sources'][1]['boundary_delta_s'] == pytest.approx(-.0005)
    assert len(joined['break_indices']) == 3
    times = joined['axis']['elapsed_s']
    assert all(b > a for a, b in zip(times, times[1:], strict=False))
    decoded, manifest = unpack(export_join(joined))
    assert decoded['axis']['elapsed_s'] == pytest.approx(times, abs=1e-9)
    assert len(manifest['source_samples']) == len({tuple(v) for v in manifest['source_samples']}) == 80


def test_gaps_remain_in_time_and_rms_never_crosses_capture_boundaries():
    joined = join_sources([capture('a'), capture('b', '00:00:00.060000')])
    assert joined['join']['sources'][1]['boundary_delta_s'] == pytest.approx(.021)
    rms = sample_rms(joined, joined['channels'][0])['values']
    assert rms[40:60] == [None]*20
    assert rms[60] is not None
    decoded, _ = unpack(export_join(joined))
    assert decoded['axis']['elapsed_s'][40] == pytest.approx(.06)


@pytest.mark.parametrize('difference', ['identity', 'channels', 'timing', 'duplicate_time'])
def test_incompatible_or_ambiguous_sources_are_not_guessed(difference):
    a, b = capture('a'), capture('b', '00:00:00.040000')
    if difference == 'identity':
        b[1]['device'] = 'OTHER'
    elif difference == 'channels':
        b[1]['header_inventory'][0]['a'] = '4'
    elif difference == 'timing':
        b[1]['axis']['status'] = 'withheld'
    else:
        b = capture('b', '00:00:00.039000')
    with pytest.raises(ValueError):
        join_sources([a, b])


def test_unknown_values_refuse_export_and_fractional_raw_counts_report_quantization():
    joined = join_sources([capture('a'), capture('b', '00:00:00.040000', [i/7 for i in range(40)])])
    decoded, manifest = unpack(export_join(joined))
    error = manifest['amplitude_max_absolute_error']['A1']
    assert error > 0
    assert decoded['channels'][0]['values'] == pytest.approx(joined['channels'][0]['values'], abs=error+1e-12)
    joined['channels'][0]['values'][1] = None
    with pytest.raises(ValueError, match='unknown'):
        export_join(joined)
