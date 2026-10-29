"""Pure UI requirements and review payloads remain strict without DOM/network access."""
import shutil
import subprocess
from pathlib import Path


def test_instrument_review_inputs():
    node = shutil.which('node')
    assert node, 'Node is required for instrument-review UI checks.'
    subprocess.run([node, str(Path(__file__).with_name('instrument_review.cjs'))], check=True)
