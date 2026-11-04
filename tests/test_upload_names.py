"""Upload names describe captures while preserving an operator's explicit label."""
from pathlib import Path
import shutil
import subprocess


def test_upload_names():
    node = shutil.which('node')
    assert node, 'Node is required for upload naming checks.'
    subprocess.run([node, str(Path(__file__).with_name('upload_names.cjs'))], check=True)
