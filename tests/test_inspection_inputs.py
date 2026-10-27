"""Actual pure UI choice parsing, without a browser dependency."""
import shutil
import subprocess
from pathlib import Path


def test_source_input_model():
    node=shutil.which('node')
    assert node
    subprocess.run([node,str(Path(__file__).with_name('inspection_inputs.cjs'))],check=True)
