"""The parse-first setup preserves declared scaling and source-bound reviews."""
import shutil
import subprocess
from pathlib import Path


def test_recording_setup_inputs():
    node = shutil.which('node')
    assert node, 'Node is required for recording setup UI verification.'
    subprocess.run([node, str(Path(__file__).with_name('recording_setup.cjs'))], check=True)


def test_recording_setup_routes():
    node = shutil.which('node')
    assert node, 'Node is required for recording setup route verification.'
    subprocess.run([node, str(Path(__file__).with_name('recording_setup_routes.cjs'))], check=True)
