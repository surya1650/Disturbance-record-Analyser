"""Primary calculation must preserve physical choices and immutable revision guards."""
from pathlib import Path
import shutil
import subprocess


def test_fault_calculation_ui():
    node = shutil.which('node')
    assert node, 'Node is required to exercise calculation flow.'
    subprocess.run([node, str(Path(__file__).with_name('fault_calculation.cjs'))], check=True)
