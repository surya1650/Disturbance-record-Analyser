"""Line declarations must not silently select a missing-CT display assumption."""
import shutil
import subprocess
from pathlib import Path


def test_line_selection_keeps_ratio_choice_explicit():
    node = shutil.which('node')
    assert node, 'Node is required for source input binding verification.'
    subprocess.run([node, str(Path(__file__).with_name('analysis_guidance_mount.cjs'))], check=True)
