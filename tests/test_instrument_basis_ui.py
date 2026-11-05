"""Source-safe primary/secondary choices and secondary entry shortcuts."""
from pathlib import Path
import shutil
import subprocess


def test_instrument_basis_ui():
    node = shutil.which('node')
    assert node, 'Node is required for instrument-basis UI verification.'
    subprocess.run([node, str(Path(__file__).with_name('instrument_basis.cjs'))], check=True)
