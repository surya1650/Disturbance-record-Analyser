"""Calculation reuses saved Setup facts and checks only actual missing evidence."""
from pathlib import Path
import shutil
import subprocess


def test_fault_setup_reuse_ui():
    node = shutil.which('node')
    assert node, 'Node is required for saved Setup reuse verification.'
    subprocess.run([node, str(Path(__file__).with_name('fault_setup_reuse.cjs'))], check=True)
