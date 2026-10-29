import shutil
import subprocess
from pathlib import Path


def test_specific_block_guidance_is_source_safe():
    subprocess.run([shutil.which('node'), str(Path(__file__).with_name('input_guidance.cjs'))], check=True)
