"""Verify display matching without a DOM or operational assumptions."""
import shutil
import subprocess
from pathlib import Path


def test_channel_comparison_model():
    node = shutil.which('node')
    assert node, 'Node is required for channel-comparison model verification.'
    subprocess.run([node, str(Path(__file__).with_name('channel_comparison_model.cjs'))], check=True)


def test_channel_comparison_view():
    node = shutil.which('node')
    assert node, 'Node is required for channel-comparison view verification.'
    subprocess.run([node, str(Path(__file__).with_name('channel_comparison_view.cjs'))], check=True)
