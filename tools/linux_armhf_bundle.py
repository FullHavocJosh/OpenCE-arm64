"""Bundle the armhf runtime, the probe and a launcher for a Linux aarch64 device.

    python tools/linux_armhf_bundle.py <sysroot> <probe> <out>

<out> gets lib (the armhf libraries and loader), share/glvnd, armhf_probe and
launch. The launcher runs the bundled loader, because the device has no
/lib/ld-linux-armhf.so.3.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

LOADER = 'ld-linux-armhf.so.3'

LAUNCHER = """#!/bin/sh
d=$(cd "$(dirname "$0")" && pwd)
export LIBGL_DRIVERS_PATH="$d/lib/dri"
export GBM_BACKENDS_PATH="$d/lib/gbm"
export __EGL_VENDOR_LIBRARY_DIRS="$d/share/glvnd/egl_vendor.d"
exec "$d/lib/ld-linux-armhf.so.3" --library-path "$d/lib:$d/lib/pulseaudio" "$d/armhf_probe" "$@"
"""


def bundle(sysroot: Path, probe: Path, out: Path) -> None:
    """Lay out lib, share/glvnd, the probe and a launcher under out."""
    sysroot = Path(sysroot)
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    shutil.copytree(
        sysroot / 'usr' / 'lib' / 'arm-linux-gnueabihf',
        out / 'lib',
        symlinks=True,
        ignore=shutil.ignore_patterns('*.a', 'pkgconfig', 'gcc'),
    )
    glvnd = sysroot / 'usr' / 'share' / 'glvnd'
    if glvnd.exists():
        shutil.copytree(glvnd, out / 'share' / 'glvnd', symlinks=True)
    shutil.copy2(probe, out / 'armhf_probe')

    if not any((out / 'lib').rglob(LOADER)):
        raise FileNotFoundError(f'{LOADER} not found under {out / "lib"}')

    launch = out / 'launch'
    launch.write_text(LAUNCHER)
    launch.chmod(0o755)


def main() -> None:
    """Command line entry: sysroot probe out."""
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    bundle(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))


if __name__ == '__main__':
    main()
