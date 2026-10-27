"""Render the actual report templates in Node with missing and untrusted data."""
import shutil
import subprocess
from pathlib import Path


def test_inspection_report_templates():
    node=shutil.which('node')
    assert node
    subprocess.run([node,str(Path(__file__).with_name('inspection_report.cjs'))],check=True)
