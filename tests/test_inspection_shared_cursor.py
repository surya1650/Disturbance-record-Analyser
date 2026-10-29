"""Exercise shared analog/digital/Fourier cursor transport and lock behavior."""
from pathlib import Path
import shutil
import subprocess


def test_shared_cursor_observations():
    node = shutil.which('node')
    assert node, 'Node is required for shared-cursor verification.'
    subprocess.run([node, str(Path(__file__).with_name('inspection_shared_cursor.cjs'))], check=True)
