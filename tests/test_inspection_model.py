"""Run pure inspection UI semantics in Node, independently of a DOM."""
import shutil
import subprocess
from pathlib import Path


def test_inspection_model():
    node = shutil.which('node')
    assert node, 'Node is required for UI model verification.'
    subprocess.run([node, str(Path(__file__).with_name('inspection_model.cjs'))], check=True)
