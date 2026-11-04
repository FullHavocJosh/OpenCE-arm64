"""Bundle the armhf runtime, the probe and a launcher for a Linux aarch64 device.

    python tools/linux_armhf_bundle.py <sysroot> <probe> <out> [<sdl_lib>]

An optional <sdl_lib> directory supplies libSDL3.so* in place of the sysroot's.
<out> gets lib (the armhf libraries and loader), share/glvnd, armhf_probe and
launch. The launcher runs the bundled loader, because the device has no
/lib/ld-linux-armhf.so.3.
"""
from __future__ import annotations

import os
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


def bundle(sysroot: Path, probe: Path, out: Path, sdl_lib: Path | None = None) -> None:
    """Lay out lib, share/glvnd, the probe and a launcher under out.

    With sdl_lib, its libSDL3.so* entries replace the sysroot's in out/lib.
    """
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
    if sdl_lib is not None:
        for old in (out / 'lib').glob('libSDL3.so*'):
            old.unlink()
        for entry in sorted(Path(sdl_lib).glob('libSDL3.so*')):
            target = out / 'lib' / entry.name
            if entry.is_symlink():
                target.symlink_to(os.readlink(entry))
            else:
                shutil.copy2(entry, target)
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
    """Command line entry: sysroot probe out [sdl_lib]."""
    if len(sys.argv) not in (4, 5):
        sys.exit(__doc__)
    sdl_lib = Path(sys.argv[4]) if len(sys.argv) == 5 else None
    bundle(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sdl_lib)


if __name__ == '__main__':
    main()
