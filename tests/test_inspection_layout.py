"""Regression coverage for mandatory analogs and nonpaginated digital/cursor layout."""
import shutil
import subprocess
from pathlib import Path


def test_inspection_layout_and_bounded_transport():
    node = shutil.which('node')
    assert node, 'Node is required for waveform layout verification.'
    subprocess.run([node, str(Path(__file__).with_name('inspection_layout.cjs'))], check=True)
