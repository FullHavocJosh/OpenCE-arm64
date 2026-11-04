"""Pure helpers for the armhf SDL3 source build.

    python -m pytest -q tools/test_linux_armhf_sdl.py

Cross-builds SDL3 3.4.16 for armhf against the Debian trixie armhf sysroot
at build/linux-armhf/third_party/sysroot, with the machine's clang and lld.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

try:
    from tools.linux_sysroot import SDL_SHA256, SDL_URLS, SDL_VERSION, download, extract
except ImportError:
    from linux_sysroot import SDL_SHA256, SDL_URLS, SDL_VERSION, download, extract

__all__ = [
    "SDL_SHA256",
    "SDL_URLS",
    "SDL_VERSION",
    "WAYLAND_SHA256",
    "WAYLAND_URLS",
    "WAYLAND_VERSION",
    "cmake_args",
    "main",
    "make",
    "make_scanner",
    "pkg_config_env",
    "scanner_args",
    "stamp_text",
    "toolchain_text",
]


WAYLAND_VERSION = "1.26.0"
WAYLAND_URLS = [
    "https://gitlab.freedesktop.org/wayland/wayland/-/releases/1.26.0/downloads/wayland-1.26.0.tar.xz"
]
WAYLAND_SHA256 = "64176eaa46e4969903e286f8e5ef8331affc17fdf03ac9b58381d2b23162b7a3"


def toolchain_text(sysroot: Path, cc: str) -> str:
    """CMake toolchain file for the armhf cross build."""
    return (
        "set(CMAKE_SYSTEM_NAME Linux)\n"
        "set(CMAKE_SYSTEM_PROCESSOR arm)\n"
        f"set(CMAKE_C_COMPILER {cc})\n"
        "set(CMAKE_C_COMPILER_TARGET armv7-linux-gnueabihf)\n"
        'set(CMAKE_C_FLAGS "-mfloat-abi=hard -mfpu=neon")\n'
        f'set(CMAKE_SYSROOT "{sysroot.as_posix()}")\n'
        'set(CMAKE_EXE_LINKER_FLAGS "-fuse-ld=lld")\n'
        'set(CMAKE_SHARED_LINKER_FLAGS "-fuse-ld=lld")\n'
        f'set(CMAKE_FIND_ROOT_PATH "{sysroot.as_posix()}")\n'
        "set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)\n"
        "set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)\n"
        "set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)\n"
        "set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)\n"
    )


def cmake_args(
    source: Path,
    build: Path,
    install: Path,
    toolchain: Path,
    scanner: Path | None = None,
) -> list[str]:
    """CMake configure arguments for the armhf SDL3 build."""
    args = [
        "cmake",
        "-S",
        source.as_posix(),
        "-B",
        build.as_posix(),
        "-G",
        "Ninja",
        f"-DCMAKE_TOOLCHAIN_FILE={toolchain.as_posix()}",
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_INSTALL_PREFIX={install.as_posix()}",
        "-DSDL_SHARED=ON",
        "-DSDL_STATIC=OFF",
        "-DSDL_TESTS=OFF",
        "-DSDL_EXAMPLES=OFF",
        "-DSDL_X11=OFF",
        "-DSDL_KMSDRM=OFF",
        "-DSDL_WAYLAND=ON",
        "-DSDL_OPENGLES=ON",
        "-DSDL_INSTALL_TESTS=OFF",
    ]
    if scanner is not None:
        args.append(f"-DWAYLAND_SCANNER={scanner.as_posix()}")
    return args


def pkg_config_env(sysroot: Path) -> dict[str, str]:
    """pkg-config environment pointing at the sysroot's pkgconfig dirs."""
    root = sysroot.as_posix()
    return {
        "PKG_CONFIG_SYSROOT_DIR": root,
        "PKG_CONFIG_LIBDIR": (
            f"{root}/usr/lib/arm-linux-gnueabihf/pkgconfig:"
            f"{root}/usr/lib/pkgconfig:"
            f"{root}/usr/share/pkgconfig"
        ),
    }


def scanner_args(source: Path, build: Path, prefix: Path) -> list[str]:
    """Meson setup arguments for the host wayland-scanner build.

    Run from the source dir, so the first positional after setup is the
    build dir; the source dir is not passed.
    """
    return [
        "meson",
        "setup",
        build.as_posix(),
        "-Dlibraries=false",
        "-Dscanner=true",
        "-Dtests=false",
        "-Ddocumentation=false",
        "-Ddtd_validation=false",
        f"--prefix={prefix.as_posix()}",
    ]


def stamp_text(cc: str) -> str:
    """One line recording the SDL and Wayland versions, digests and compiler."""
    return f"{SDL_VERSION} {SDL_SHA256} {WAYLAND_VERSION} {WAYLAND_SHA256} {cc}\n"


def make_scanner(folder: Path) -> Path:
    """Build the host wayland-scanner into folder/wayland-host, once."""
    wayland_src = folder / "wayland-src"
    wayland_build = folder / "wayland-build"
    prefix = folder / "wayland-host"
    scanner = prefix / "bin" / "wayland-scanner"
    if scanner.is_file():
        return scanner
    for path in (wayland_src, wayland_build, prefix):
        if path.is_dir():
            shutil.rmtree(path)
    print(f"Downloading wayland-{WAYLAND_VERSION}.tar.xz", flush=True)
    with tarfile.open(
        fileobj=io.BytesIO(download(WAYLAND_URLS, WAYLAND_SHA256)), mode="r:xz"
    ) as archive:
        extract(archive, wayland_src, strip=1)
    subprocess.run(
        scanner_args(wayland_src, wayland_build, prefix), check=True, cwd=wayland_src
    )
    subprocess.run(["meson", "install", "-C", wayland_build.as_posix()], check=True)
    return scanner


def make(folder: Path, sysroot: Path, cc: str) -> None:
    """Download, configure, build and install SDL3 into folder/install."""
    folder = folder.resolve()
    stamp = folder / "stamp"
    if stamp.is_file() and stamp.read_text() == stamp_text(cc):
        return
    source = folder / "src"
    build = folder / "build"
    install = folder / "install"
    for path in (source, build, install):
        if path.is_dir():
            shutil.rmtree(path)
    if stamp.exists():
        stamp.unlink()
    folder.mkdir(parents=True, exist_ok=True)
    scanner = make_scanner(folder)
    print(f"Downloading SDL3-{SDL_VERSION}.tar.gz", flush=True)
    with tarfile.open(
        fileobj=io.BytesIO(download(SDL_URLS, SDL_SHA256)), mode="r:gz"
    ) as archive:
        extract(archive, source, strip=1)
    toolchain = folder / "toolchain.cmake"
    toolchain.write_text(toolchain_text(sysroot.resolve(), cc))
    env = {**os.environ, **pkg_config_env(sysroot.resolve())}
    subprocess.run(
        cmake_args(source, build, install, toolchain, scanner=scanner),
        check=True,
        env=env,
    )
    subprocess.run(["cmake", "--build", build.as_posix()], check=True, env=env)
    subprocess.run(["cmake", "--install", build.as_posix()], check=True, env=env)
    stamp.write_text(stamp_text(cc))


def main(argv: list[str]) -> int:
    """Build SDL3 for armhf: <folder> <sysroot> <cc>."""
    if len(argv) != 3:
        print("usage: linux_armhf_sdl.py <folder> <sysroot> <cc>")
        return 1
    make(Path(argv[0]), Path(argv[1]), argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
