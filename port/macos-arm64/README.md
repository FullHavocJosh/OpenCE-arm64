# macOS arm64 port

## Why the guest cannot be ILP32

The Linux and Android arm64 ports run the game as an ILP32 guest (port/guest)
next to a 64-bit host. That needs the low 4 GB of the address space.

The spike port/macos-arm64/spike/lowmap.c measured this on macOS 27.2
(arm64, SIP on):

- An arm64 executable linked with -Wl,-pagezero_size,0x4000 is killed at exec
  (exit 137, AppleSystemPolicy: 'Security policy would not allow process').
- Ad-hoc re-signing does not help, and -no_pie is ignored on arm64.
- With the default 4 GB __PAGEZERO, mmap(MAP_FIXED, 0x88000000) fails with
  ENOMEM.

So the ILP32 guest of port/guest cannot be mapped in a macOS process. A small
pagezero is refused by the kernel policy and the default one covers the
addresses the guest needs.

## Decision

The macOS build compiles the game LP64, in one executable with no guest/host
split. This follows the structure of the Linux x86 port.

The renderer plan is unchanged: OpenGL ES 3.0 through ANGLE on Metal first,
and a native Metal renderer later.
