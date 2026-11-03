"""A reviewed settings hash describes original bytes, including line endings."""
import hashlib

import pytest

from dranalyser.registry.settings_io import load_settings
from tests.test_settings import RIO_FIXTURE


@pytest.mark.parametrize('ending', ['\n', '\r\n', '\r', 'mixed'])
def test_imported_settings_keep_byte_identity_without_changing_parsed_values(tmp_path, ending):
    lines = (RIO_FIXTURE + 'FEEDER Synthetic caf\xe9\n').splitlines()
    text = ''.join(line + (('\r\n' if index % 2 else '\n') if ending == 'mixed' else ending)
                   for index, line in enumerate(lines))
    raw = text.encode('latin-1')
    path = tmp_path / 'event.rio'
    path.write_bytes(raw)
    settings = load_settings(str(path))
    assert settings.provenance.sha256 == hashlib.sha256(raw).hexdigest()
    assert settings.zone('Z1').phase.vertices == [(0., 0.), (6.034, 0.), (6.034, 3.5), (.617, 3.5)]
    assert settings.re_rl == 1.020 and settings.xe_xl == .800
    assert settings.feeder == 'Synthetic caf\xe9'
    assert path.read_bytes() == raw
