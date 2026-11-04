"""The armhf feasibility probe's ninja graph (tools/linux_armhf_build.py): it is
generated only when the solution asks for it (sln.linux_armhf).

    python -m pytest -q tools/test_linux_armhf_build.py

Needs no toolchain and no downloads.
"""

import io
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from tools import linux_armhf_build
from tools.ninja_syntax import Writer


def graph(sln: SimpleNamespace) -> str:
    """The armhf part of build.ninja for |sln|, with line continuations joined"""
    out = io.StringIO()
    linux_armhf_build.generate_linux_armhf_build(Writer(out), sln)
    return out.getvalue().replace(" $\n", " ")


def test_nothing_without_the_flag():
    assert graph(SimpleNamespace()) == ""
    assert graph(SimpleNamespace(linux_armhf=False)) == ""


def test_graph_with_the_flag():
    text = graph(SimpleNamespace(linux_armhf=True))
    assert "--target=armv7-linux-gnueabihf" in text
    assert "--sysroot=build/linux-armhf/third_party/sysroot" in text
    assert "-lSDL3" in text
    assert "port/linux-armhf/probe/armhf_probe.c" in text
    assert "build linux_armhf_sysroot: phony" in text
    assert "build linux_armhf_probe: phony" in text


def test_compiler_override():
    assert "armhf_cc = clang\n" in graph(SimpleNamespace(linux_armhf=True))
    text = graph(SimpleNamespace(linux_armhf=True, armhf_cc="clang-19"))
    assert "armhf_cc = clang-19\n" in text


def test_configure_inputs():
    assert linux_armhf_build.linux_armhf_configure_inputs() == [Path(linux_armhf_build.__file__)]
