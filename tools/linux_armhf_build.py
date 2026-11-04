"""Ninja rules for the 32-bit ARM (armhf, AArch32) feasibility probe.

An opt-in build path next to the Linux arm64 port: a Debian 13 armhf system
root (tools/linux_armhf_sysroot.py) and a small SDL3 and OpenGL ES probe,
built with the machine's own clang and ld.lld. It measures whether an armhf
game build is viable on a Linux aarch64 device with AArch32 support before any
game code is built that way. ``ninja linux_armhf_probe``.
"""

from pathlib import Path
from typing import Any

from .ninja_syntax import Writer

BUILD = Path("build/linux-armhf")
THIRD_PARTY = BUILD / "third_party"
SYSROOT = THIRD_PARTY / "sysroot"
PROBE = Path("port/linux-armhf/probe/armhf_probe.c")
SYSROOT_TOOL = Path("tools/linux_armhf_sysroot.py")


def linux_armhf_configure_inputs() -> list[Path]:
    """The files whose change makes configure.py run again."""
    return [Path(__file__)]


def generate_linux_armhf_build(n: Writer, sln: Any) -> None:
    """Write the armhf probe's rules and targets, only when sln.linux_armhf is set."""
    if not getattr(sln, "linux_armhf", False):
        return
    compiler = getattr(sln, "armhf_cc", None) or "clang"

    n.comment("Linux armhf (AArch32) feasibility probe")
    n.variable(key="armhf_cc", value=compiler)
    n.newline()

    n.rule(
        name="linux_armhf_sysroot",
        command=f"python3 {SYSROOT_TOOL.as_posix()} {THIRD_PARTY.as_posix()}",
        description="Debian armhf system root",
    )
    n.rule(
        name="linux_armhf_cc",
        command=(
            "$cc --target=armv7-linux-gnueabihf -mfloat-abi=hard -mfpu=neon "
            f"--sysroot={SYSROOT.as_posix()} -O2 -std=gnu11 -MMD -MF $out.d -c $in -o $out"
        ),
        description="CC $out",
        depfile="$out.d",
        deps="gcc",
    )
    n.rule(
        name="linux_armhf_link",
        command=(
            "$cc --target=armv7-linux-gnueabihf -mfloat-abi=hard "
            f"--sysroot={SYSROOT.as_posix()} -fuse-ld=lld -Wl,--allow-shlib-undefined "
            "$in -o $out -lSDL3 -lGLESv2 -lm"
        ),
        description="LINK $out",
    )
    n.newline()

    stamp = THIRD_PARTY / "stamp"
    n.build(
        outputs=[str(stamp)],
        rule="linux_armhf_sysroot",
        inputs=[],
        implicit=[str(SYSROOT_TOOL)],
    )

    obj = BUILD / "armhf_probe.o"
    n.build(
        outputs=[str(obj)],
        rule="linux_armhf_cc",
        inputs=[str(PROBE)],
        implicit=[str(stamp)],
        variables={"cc": "$armhf_cc"},
    )

    exe = BUILD / "armhf_probe"
    n.build(
        outputs=[str(exe)],
        rule="linux_armhf_link",
        inputs=[str(obj)],
        variables={"cc": "$armhf_cc"},
    )
    n.newline()

    n.build(outputs=["linux_armhf_sysroot"], rule="phony", inputs=[str(stamp)])
    n.build(outputs=["linux_armhf_probe"], rule="phony", inputs=[str(exe)])
    n.newline()
