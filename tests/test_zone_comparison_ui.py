"""The shared zone comparison view must preserve backend states and provenance."""
import shutil
import subprocess
from pathlib import Path


def test_zone_comparison_ui():
    node = shutil.which('node')
    assert node, 'Node is required for zone comparison presentation verification.'
    subprocess.run([node, str(Path(__file__).with_name('zone_comparison.cjs'))], check=True)
