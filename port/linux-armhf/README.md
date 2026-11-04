# Linux armhf probe

`ninja linux_armhf_probe` builds a small 32-bit ARM program that opens an
SDL3 window, draws a red triangle with OpenGL ES and exits.

## What it is

An experiment: can the game run as 32-bit ARM (AArch32) code natively on
Linux arm64, the way the x86 Linux build runs as 32-bit code with `-m32`?
This is a feasibility probe only. It builds no game code. The Linux arm64
guest and host port in [port/linux-arm64](../linux-arm64/README.md) stays
the supported route.

## Why

AArch32 at EL0 exists only on some cores. On the NovaDeck (Snapdragon 8
Gen 2) it is cpu0-2 and cpu5-6, as `/sys/devices/system/cpu/aarch32_el0`
lists them, and the kernel keeps 32-bit tasks on those cores. Fedora ships
no armhf libraries, so the runtime (libc, SDL3, Mesa and their
dependencies) comes from Debian 13 armhf.

## Building

1. Go to the root folder of the repository.
2. Enter `python3 configure.py --linux-armhf`. `--armhf-cc` selects a
   clang other than `clang`.
3. Enter `ninja linux_armhf_probe`.
4. Enter `python3 tools/linux_armhf_sysroot.py SYSROOT` to fetch the
   Debian 13 armhf system root into the folder `SYSROOT`.
5. Enter `python3 tools/linux_armhf_bundle.py SYSROOT PROBE OUT`, with
   `PROBE` the probe binary and `OUT` the output folder, for example
   `build/linux-armhf/bundle`.

The bundle holds the armhf libraries, the bundled loader, the probe and a
`launch` script. The device needs none of them installed.

## Running

Copy `build/linux-armhf/bundle` to the device and enter `./launch`. The
launcher runs the bundled loader, because the device has no armhf one.

The probe prints one line per fact: the SDL video driver, the GL vendor,
renderer and version, the pointer size (4 on a 32-bit build), the frames
drawn with the time they took, and the color of the center pixel. Exit
status 0 means a red triangle was drawn.

`HALO_PROBE_FRAMES` sets how many frames are drawn. The default is 120.

## Tests

Run these with pytest from the `tools` folder:

- `test_linux_armhf_build.py`: the build graph of the probe.
- `test_linux_armhf_configure.py`: the `--linux-armhf` options.
- `test_linux_armhf_sysroot.py`: the system root download.
- `test_linux_armhf_bundle.py`: the bundle layout and launcher.
