"""Tests that configure.py exposes the armhf probe options."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_help_lists_armhf_options() -> None:
    """configure.py --help lists --linux-armhf and --armhf-cc."""
    result = subprocess.run(
        [sys.executable, "configure.py", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--linux-armhf" in result.stdout
    assert "--armhf-cc" in result.stdout


def test_configure_generates_armhf_build() -> None:
    """configure.py calls generate_linux_armhf_build."""
    text = (ROOT / "configure.py").read_text()
    assert "generate_linux_armhf_build(n, sln)" in text
