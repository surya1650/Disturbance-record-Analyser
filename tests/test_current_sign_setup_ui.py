"""Current sign is an explicit recording convention, reused rather than guessed."""
from pathlib import Path
import shutil
import subprocess


def test_current_sign_setup_ui():
    node = shutil.which('node')
    assert node, 'Node is required for current-sign setup verification.'
    subprocess.run([node, str(Path(__file__).with_name('current_sign_setup.cjs'))], check=True)
