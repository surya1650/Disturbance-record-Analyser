"""Invalid acquisition stays blocked and inspectable with hostile nominal f."""
from types import SimpleNamespace

import numpy as np
import pytest

from dranalyser.comtrade.parser import read_comtrade
from dranalyser.comtrade.timestamps import recover_time
from dranalyser.dsp.clock_quality import clock_quality
from tests.test_timestamp_recovery import write_timing

FREQUENCIES = [1e308, 1e-320, 1e-308, float('nan'), float('inf'), -50, 0, 50]


@pytest.mark.parametrize('freq', FREQUENCIES)
def test_invalid_dat_without_fit_has_finite_strictly_increasing_inspection_grid(freq):
    cfg = SimpleNamespace(line_freq=freq, nrates=0, rates=[(0, 100)], timemult=1)
    t, fs, warnings, info = recover_time(cfg, np.zeros(100), 100)
    assert np.isfinite(fs) and fs > 0
    assert np.all(np.isfinite(t)) and np.all(np.diff(t) > 0)
    np.testing.assert_allclose(t, np.arange(100)/1000)
    assert warnings and info['status'] == 'invalid'
    assert not info['alignment_eligible']


@pytest.mark.parametrize('freq', FREQUENCIES)
def test_public_parser_retains_invalid_block_with_finite_inspection_time(tmp_path, freq):
    write_timing(tmp_path, np.zeros(100))
    path = tmp_path/'timing.cfg'
    lines = path.read_text().splitlines()
    lines[8] = str(freq)
    path.write_text('\n'.join(lines)+'\n')
    rec = read_comtrade(str(path))
    assert rec.blocked() and 'TIME-DAT' in rec.flag_codes()
    assert rec.notes['timestamp_recovery']['status'] == 'invalid'
    assert np.isfinite(rec.fs) and rec.fs > 0
    assert np.all(np.isfinite(rec.t)) and np.all(np.diff(rec.t) > 0)
    quality = clock_quality(rec)
    assert quality['verified'] is quality['alignment_eligible'] is quality['applied'] is False
