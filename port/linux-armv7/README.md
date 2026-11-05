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

## Floating point

The game sets and reads the rounding mode and the exception flags through
`_controlfp`, `_statusfp` and `_clearfp` (`port/linux/src/msvc_crt.c`). On
armv7 these are the VFP unit's: the rounding mode is RMode in FPSCR, the
flags are its sticky exception bits. Precision control and exception
unmasking have no equivalent on ARM; the rest of the MSVC control word is only
remembered. AArch64 has the same bits in FPCR and FPSR and shares the code.

## Custom Edition tag cache

Custom Edition maps need 23 MB at the fixed address 0x40440000. On 32-bit ARM
Linux the dynamic loader maps the shared libraries from 0x40000000 upwards in
the legacy memory layout (and qemu-user always does), on top of that window,
so a reservation at start-up fails. The armv7 executable therefore carries the
window as a segment of its own, which the kernel maps before the loader runs
(`tools/linux_armv7_tag_cache.ld`; `port/linux/src/xbox_memory.c` uses it).

## Packages

`halo-linux-armv7.AppImage` is built by the Linux packages workflow, in the
releases. There is no Flatpak: its runtime has no 32-bit ARM version. The
AppImage needs glibc 2.38 or later and a CPU with the 32-bit (AArch32) mode;
refer to [port/linux/README.md](../linux/README.md#appimage-and-flatpak-packages).

## Limits

- No `--portable` build.
- No PGO profile yet, so use `--pgo=off`.
- Not tested on armv7 hardware. It starts under qemu-user (an armhf Debian
  container, software OpenGL ES 3.2) to the menus. A 64-bit ARM CPU may lack
  the 32-bit mode (the Cortex-A510, A710, A715 and X3 cores do).
- The game needs a GPU with OpenGL ES 3.0 or later.
- Custom Edition maps are not tested on this build.

## Tests

Run this with pytest from the `tools` folder:

- `test_linux_armv7_build.py`: the build graph of the armv7 target.

`port/linux-armv7/tests/fenv_test.c` checks the floating-point control (the
rounding modes and the exception flags) on the VFP unit. The `linux-armv7`
job of the workflow links it with the build's `msvc_crt.o` and runs it with
`qemu-arm-static`. To run it yourself, build `msvc_crt.o` with `ninja`, then
link the test statically with it
(`-static -Wl,-z,muldefs -Wl,--unresolved-symbols=ignore-all`) and run it on
an armv7 machine or with `qemu-arm-static`.
