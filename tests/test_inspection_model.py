"""Run pure inspection UI semantics in Node, independently of a DOM."""
import shutil
import subprocess
from pathlib import Path


def test_inspection_model():
    node = shutil.which('node')
    assert node, 'Node is required for UI model verification.'
    subprocess.run([node, str(Path(__file__).with_name('inspection_model.cjs'))], check=True)


def test_inspection_cursor_transport():
    node = shutil.which('node')
    assert node, 'Node is required for UI transport verification.'
    subprocess.run([node, str(Path(__file__).with_name('inspection_transport.cjs'))], check=True)


def test_inspection_electrical_readings():
    node = shutil.which('node')
    assert node, 'Node is required for operator-reading verification.'
    subprocess.run([node, str(Path(__file__).with_name('inspection_readings.cjs'))], check=True)


def test_inspection_operator_conditions():
    node = shutil.which('node')
    assert node, 'Node is required for operator-condition verification.'
    subprocess.run([node, str(Path(__file__).with_name('inspection_conditions.cjs'))], check=True)
