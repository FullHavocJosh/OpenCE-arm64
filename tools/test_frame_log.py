"""Check the renderer's frame time log (debug.frame_log).

Compile the production code of port/linux/src/d3d8_gl.c with a clock the test
sets: steady frames are not reported, a frame much longer than the ones before
it is, with how its time went; no more than 30 lines a second; nothing when
the setting is off.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def between(text, start, end):
    first = text.index(start)
    return text[first:text.index(end, first)]


@pytest.fixture(scope="module")
def program(tmp_path_factory):
    compiler = shutil.which(os.environ.get("CC", "clang"))
    if not compiler:
        pytest.skip("clang required")
    work = tmp_path_factory.mktemp("frame-log")
    renderer = (ROOT / "port/linux/src/d3d8_gl.c").read_text()
    block = between(renderer, "/* ---------- frame time log (debug.frame_log)", "/* ---------- end of the frame time log */")
    (work / "frame_log.inc").write_text(block)
    executable = work / "test"
    result = subprocess.run(
        [compiler, "-std=gnu89", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", "-O2", "-I", str(work),
         str(ROOT / "port/android/tests/frame_log_test.c"), "-o", str(executable)],
        capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return executable


@pytest.mark.parametrize("case", ["steady", "hitch", "rate_limit", "disabled"])
def test_frame_log(program, case):
    result = subprocess.run([str(program), case], capture_output=True, text=True, timeout=15, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
