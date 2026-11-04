"""Tests for tools/linux_armhf_sdl.py: the armhf SDL3 cross build's helpers,
with fixed temporary paths. Needs no toolchain and no downloads."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import linux_armhf_sdl
from tools.linux_armhf_sdl import (
    WAYLAND_SHA256,
    WAYLAND_VERSION,
    cmake_args,
    main,
    make,
    make_scanner,
    pkg_config_env,
    scanner_args,
    stamp_text,
    toolchain_text,
)
from tools.linux_sysroot import SDL_SHA256, SDL_VERSION


def test_toolchain_text():
    sysroot = Path("/tmp/sys")
    text = toolchain_text(sysroot, "clang")
    assert "set(CMAKE_SYSTEM_NAME Linux)\n" in text
    assert "set(CMAKE_SYSTEM_PROCESSOR arm)\n" in text
    assert "set(CMAKE_C_COMPILER clang)\n" in text
    assert "set(CMAKE_C_COMPILER_TARGET armv7-linux-gnueabihf)\n" in text
    assert 'set(CMAKE_C_FLAGS "-mfloat-abi=hard -mfpu=neon")\n' in text
    assert 'set(CMAKE_SYSROOT "/tmp/sys")\n' in text
    assert 'set(CMAKE_EXE_LINKER_FLAGS "-fuse-ld=lld")\n' in text
    assert 'set(CMAKE_SHARED_LINKER_FLAGS "-fuse-ld=lld")\n' in text
    assert 'set(CMAKE_FIND_ROOT_PATH "/tmp/sys")\n' in text
    assert "set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)\n" in text
    assert "set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)\n" in text
    assert "set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)\n" in text
    assert "set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)\n" in text
    assert text == (
        "set(CMAKE_SYSTEM_NAME Linux)\n"
        "set(CMAKE_SYSTEM_PROCESSOR arm)\n"
        "set(CMAKE_C_COMPILER clang)\n"
        "set(CMAKE_C_COMPILER_TARGET armv7-linux-gnueabihf)\n"
        'set(CMAKE_C_FLAGS "-mfloat-abi=hard -mfpu=neon")\n'
        'set(CMAKE_SYSROOT "/tmp/sys")\n'
        'set(CMAKE_EXE_LINKER_FLAGS "-fuse-ld=lld")\n'
        'set(CMAKE_SHARED_LINKER_FLAGS "-fuse-ld=lld")\n'
        'set(CMAKE_FIND_ROOT_PATH "/tmp/sys")\n'
        "set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)\n"
        "set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)\n"
        "set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)\n"
        "set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)\n"
    )


def test_cmake_args():
    source = Path("/tmp/src")
    build = Path("/tmp/build")
    install = Path("/tmp/install")
    toolchain = Path("/tmp/toolchain.cmake")
    assert cmake_args(source, build, install, toolchain) == [
        "cmake",
        "-S",
        "/tmp/src",
        "-B",
        "/tmp/build",
        "-G",
        "Ninja",
        "-DCMAKE_TOOLCHAIN_FILE=/tmp/toolchain.cmake",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DCMAKE_INSTALL_PREFIX=/tmp/install",
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


def test_cmake_args_with_scanner():
    source = Path("/tmp/src")
    build = Path("/tmp/build")
    install = Path("/tmp/install")
    toolchain = Path("/tmp/toolchain.cmake")
    scanner = Path("/tmp/prefix/bin/wayland-scanner")
    base = cmake_args(source, build, install, toolchain)
    assert not any(arg.startswith("-DWAYLAND_SCANNER") for arg in base)
    with_scanner = cmake_args(source, build, install, toolchain, scanner=scanner)
    assert with_scanner == base + ["-DWAYLAND_SCANNER=/tmp/prefix/bin/wayland-scanner"]


def test_scanner_args():
    source = Path("/tmp/src")
    build = Path("/tmp/build")
    prefix = Path("/tmp/prefix")
    assert scanner_args(source, build, prefix) == [
        "meson",
        "setup",
        "/tmp/build",
        "-Dlibraries=false",
        "-Dscanner=true",
        "-Dtests=false",
        "-Ddocumentation=false",
        "-Ddtd_validation=false",
        "--prefix=/tmp/prefix",
    ]


def test_pkg_config_env():
    sysroot = Path("/tmp/sys")
    assert pkg_config_env(sysroot) == {
        "PKG_CONFIG_SYSROOT_DIR": "/tmp/sys",
        "PKG_CONFIG_LIBDIR": (
            "/tmp/sys/usr/lib/arm-linux-gnueabihf/pkgconfig:"
            "/tmp/sys/usr/lib/pkgconfig:"
            "/tmp/sys/usr/share/pkgconfig"
        ),
    }


def test_stamp_text():
    assert (
        stamp_text("clang")
        == f"{SDL_VERSION} {SDL_SHA256} {WAYLAND_VERSION} {WAYLAND_SHA256} clang\n"
    )
    assert stamp_text("clang-19").count("\n") == 1


def _patch(monkeypatch, folder, calls):
    def fake_extract(archive, dest, strip=0):
        calls.append("extract")
        dest.mkdir(parents=True)

    def fake_run(cmd, **kwargs):
        stamp = folder / "stamp"
        calls.append((cmd[0], cmd[1], stamp.exists()))
        assert kwargs["check"] is True
        assert kwargs["env"]["PKG_CONFIG_SYSROOT_DIR"]

    monkeypatch.setattr(linux_armhf_sdl, "download", lambda urls, digest: _tarball())
    monkeypatch.setattr(linux_armhf_sdl, "extract", fake_extract)
    monkeypatch.setattr(linux_armhf_sdl.subprocess, "run", fake_run)
    monkeypatch.setattr(
        linux_armhf_sdl,
        "make_scanner",
        lambda folder: folder / "wayland-host" / "bin" / "wayland-scanner",
    )


def _tarball():
    import io
    import tarfile

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz"):
        pass
    return buffer.getvalue()


def test_make_order_and_stamp_last(tmp_path, monkeypatch):
    folder = tmp_path / "sdl"
    sysroot = tmp_path / "sys"
    sysroot.mkdir()
    calls = []
    _patch(monkeypatch, folder, calls)
    make(folder, sysroot, "clang")
    assert calls[0] == "extract"
    assert [c[:2] for c in calls[1:]] == [
        ("cmake", "-S"),
        ("cmake", "--build"),
        ("cmake", "--install"),
    ]
    assert all(c[2] is False for c in calls[1:])
    assert (folder / "stamp").read_text() == stamp_text("clang")
    assert (folder / "toolchain.cmake").read_text() == toolchain_text(
        sysroot.resolve(), "clang"
    )


def test_make_cmake_paths_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sysroot = tmp_path / "sys"
    sysroot.mkdir()
    argv = []
    _patch(monkeypatch, tmp_path / "sdl", [])
    inner = linux_armhf_sdl.subprocess.run

    def record(cmd, **kwargs):
        argv.append(cmd)
        return inner(cmd, **kwargs)

    monkeypatch.setattr(linux_armhf_sdl.subprocess, "run", record)
    make(Path("sdl"), sysroot, "clang")
    configure = argv[0]
    for index in (configure.index("-S") + 1, configure.index("-B") + 1):
        assert Path(configure[index]).is_absolute()
    for arg in configure:
        if arg.startswith(("-DCMAKE_TOOLCHAIN_FILE=", "-DCMAKE_INSTALL_PREFIX=")):
            assert Path(arg.split("=", 1)[1]).is_absolute()
    assert Path(argv[1][-1]).is_absolute()
    assert Path(argv[2][-1]).is_absolute()


def test_make_passes_scanner(tmp_path, monkeypatch):
    folder = tmp_path / "sdl"
    sysroot = tmp_path / "sys"
    sysroot.mkdir()
    argv = []
    _patch(monkeypatch, folder, [])
    inner = linux_armhf_sdl.subprocess.run

    def record(cmd, **kwargs):
        argv.append(cmd)
        return inner(cmd, **kwargs)

    monkeypatch.setattr(linux_armhf_sdl.subprocess, "run", record)
    make(folder, sysroot, "clang")
    scanner = folder.resolve() / "wayland-host" / "bin" / "wayland-scanner"
    assert f"-DWAYLAND_SCANNER={scanner.as_posix()}" in argv[0]


def test_make_scanner_builds_once(tmp_path, monkeypatch):
    calls = []

    def fake_extract(archive, dest, strip=0):
        calls.append(("extract", dest.name, strip))
        dest.mkdir(parents=True)

    def fake_run(cmd, **kwargs):
        calls.append((cmd[0], cmd[1], kwargs.get("cwd")))
        assert kwargs["check"] is True

    monkeypatch.setattr(linux_armhf_sdl, "download", lambda urls, digest: b"")
    monkeypatch.setattr(linux_armhf_sdl, "extract", fake_extract)
    monkeypatch.setattr(linux_armhf_sdl.subprocess, "run", fake_run)
    monkeypatch.setattr(linux_armhf_sdl.tarfile, "open", lambda **kwargs: _Archive())
    scanner = make_scanner(tmp_path)
    assert scanner == tmp_path / "wayland-host" / "bin" / "wayland-scanner"
    assert calls == [
        ("extract", "wayland-src", 1),
        ("meson", "setup", tmp_path / "wayland-src"),
        ("meson", "install", None),
    ]


def test_make_scanner_reuses_existing(tmp_path, monkeypatch):
    scanner = tmp_path / "wayland-host" / "bin" / "wayland-scanner"
    scanner.parent.mkdir(parents=True)
    scanner.write_text("")
    calls = []
    monkeypatch.setattr(linux_armhf_sdl, "download", lambda *a: calls.append("dl"))
    monkeypatch.setattr(linux_armhf_sdl.subprocess, "run", lambda *a, **k: calls.append("run"))
    assert make_scanner(tmp_path) == scanner
    assert calls == []


class _Archive:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_make_matching_stamp_skips(tmp_path, monkeypatch):
    folder = tmp_path / "sdl"
    folder.mkdir()
    (folder / "stamp").write_text(stamp_text("clang"))
    calls = []
    _patch(monkeypatch, folder, calls)
    make(folder, tmp_path / "sys", "clang")
    assert calls == []


def test_main_usage(capsys):
    assert main(["only-one"]) == 1
    assert "usage" in capsys.readouterr().out
