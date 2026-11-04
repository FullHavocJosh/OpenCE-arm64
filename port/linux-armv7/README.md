# Linux armv7

`ninja linux_armv7` builds the game for 32-bit ARM Linux and
`build/linux-armv7/halo` runs it.

## What it is

The game is the same native 32-bit game as the x86 Linux build, compiled for
armv7-linux-gnueabihf (hard float) with clang and lld. It uses the OpenGL ES
renderer path (`HALO_GLES`) that the Android and web builds already use:
OpenGL ES 3.2, with a fallback to 3.0, requested from the platform layer.
SDL3 comes from the system root.

The game's sources and the platform layer (`port/linux/src`) are shared with
the other Linux builds; refer to [port/linux/README.md](../linux/README.md).
The crash report records the ARM registers.

## Building

It needs clang, lld, ninja, Python and a root of armhf libraries.

1. Go to the root folder of the repository.
2. Enter `python3 configure.py --linux-arch armv7 --linux-sysroot DIR --lto=off --pgo=off`.
3. Enter `ninja linux_armv7`.

The build writes `build/linux-armv7/halo`.

`DIR` is an armhf Debian root with `libc6-dev`, `libgcc-14-dev`,
`libgles-dev`, and the headers and libraries of SDL 3.4. SDL 3.2 from Debian
trixie may lack calls the game uses. Without `--linux-sysroot` the build
uses the machine's own libraries, which suits an armhf machine.

`tools/linux_armv7.cmake` is a toolchain file for building SDL3 for this
target.

## Limits

- No `--portable` build.
- No PGO profile yet, so use `--pgo=off`.
- Not tested on hardware.
- The game needs a GPU with OpenGL ES 3.0 or later.

## Tests

Run this with pytest from the `tools` folder:

- `test_linux_armv7_build.py`: the build graph of the armv7 target.
