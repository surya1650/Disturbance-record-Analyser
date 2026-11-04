"""Saved source-bound instrument inputs remain editable without duplicate captures."""
from pathlib import Path
import shutil
import subprocess


def test_instrument_review_editing_ui():
    node = shutil.which('node')
    assert node, 'Node is required for saved instrument-input UI checks.'
    subprocess.run([node, str(Path(__file__).with_name('instrument_review_editing.cjs'))], check=True)
