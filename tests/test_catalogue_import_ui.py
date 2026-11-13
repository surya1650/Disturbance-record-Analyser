"""Source catalogue upload remains staged and source-labelled in the browser UI."""
import shutil
import subprocess
from pathlib import Path


def test_catalogue_import_ui():
    node = shutil.which('node')
    assert node, 'Node is required for catalogue upload presentation verification.'
    subprocess.run([node, str(Path(__file__).with_name('catalogue_import.cjs'))], check=True)
