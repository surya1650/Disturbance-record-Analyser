"""Feature guidance must describe scoped prerequisites without authorizing analysis."""
import shutil
import subprocess
from pathlib import Path


def test_feature_guide():
    node = shutil.which('node')
    assert node, 'Node is required for feature guidance verification.'
    subprocess.run([node, str(Path(__file__).with_name('feature_guide.cjs'))], check=True)
