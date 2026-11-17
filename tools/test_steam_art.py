"""tools/steam_art.py: the app ID of a shortcut and where its art goes.

    python -m pytest -q tools/test_steam_art.py
"""

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import steam_art


def entry(index, name, appid):
    return (
        b"\0" + str(index).encode() + b"\0"
        + b"\2appid\0" + struct.pack("<I", appid)
        + b"\1AppName\0" + name.encode() + b"\0"
        + b"\1Exe\0/usr/bin/flatpak\0"
        + b"\x08"
    )


def vdf(*entries):
    return b"\0shortcuts\0" + b"".join(entry(i, n, a) for i, (n, a) in enumerate(entries)) + b"\x08\x08"


def test_shortcut_ids_finds_the_named_shortcut():
    data = vdf(("Other", 1), ("OpenCE", 0xDEADBEEF))
    assert steam_art.shortcut_ids(data, "OpenCE") == [0xDEADBEEF]


def test_install_names_files_by_app_id(tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "shortcuts.vdf").write_bytes(vdf(("OpenCE", 123)))
    art = tmp_path / "art"
    art.mkdir()
    (art / "portrait.png").write_bytes(b"p")
    (art / "hero.png").write_bytes(b"h")
    written = steam_art.install(config, art, "OpenCE")
    assert sorted(path.name for path in written) == ["123_hero.png", "123p.png"]
    assert (config / "grid" / "123p.png").read_bytes() == b"p"


def test_install_refuses_zero_or_two_shortcuts(tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "shortcuts.vdf").write_bytes(vdf(("OpenCE", 1), ("OpenCE", 2)))
    with pytest.raises(SystemExit):
        steam_art.install(config, tmp_path, "OpenCE")
