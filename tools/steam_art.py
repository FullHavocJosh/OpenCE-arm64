#!/usr/bin/env python3
"""Gives the OpenCE shortcut in Steam its artwork.

    python3 tools/steam_art.py [--name OpenCE] [--art port/assets/steam]

Steam keeps the pictures of a non-Steam shortcut in userdata/<user>/config/grid
under the shortcut's app ID, which differs from one computer to the next, so a
package cannot carry them. This reads the app ID from shortcuts.vdf and copies
the files of the art folder to the names Steam looks for:

    portrait.png -> <id>p.png        wide.png -> <id>.png
    hero.png     -> <id>_hero.png    logo.png -> <id>_logo.png
    icon.png     -> <id>_icon.png

A file the art folder lacks is skipped. Run it with the shortcut already in
Steam; the pictures show after Steam restarts.
"""

import argparse
import shutil
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "port" / "assets" / "steam"
NAMES = {
    "portrait.png": "{id}p.png",
    "wide.png": "{id}.png",
    "hero.png": "{id}_hero.png",
    "logo.png": "{id}_logo.png",
    "icon.png": "{id}_icon.png",
}


def parse(data):
    """The binary VDF in data as nested dicts; keys are lower case."""
    pos = 0

    def cstr():
        nonlocal pos
        end = data.index(b"\0", pos)
        text = data[pos:end].decode("utf-8", "replace")
        pos = end + 1
        return text

    def read_map():
        nonlocal pos
        out = {}
        while pos < len(data):
            kind = data[pos]
            pos += 1
            if kind == 8:
                return out
            key = cstr().lower()
            if kind == 0:
                out[key] = read_map()
            elif kind == 1:
                out[key] = cstr()
            elif kind == 2:
                out[key] = struct.unpack_from("<I", data, pos)[0]
                pos += 4
            else:
                raise ValueError(f"unknown VDF type {kind} at {pos - 1}")
        return out

    return read_map()


def shortcut_ids(data, name):
    """The app IDs of the shortcuts called name."""
    entries = parse(data).get("shortcuts", {})
    return [entry["appid"] for entry in entries.values() if entry.get("appname") == name and "appid" in entry]


def install(config_dir, art, name):
    """Copies the art into config_dir/grid; returns the paths written."""
    ids = shortcut_ids((config_dir / "shortcuts.vdf").read_bytes(), name)
    if len(ids) != 1:
        raise SystemExit(f"{config_dir}: {len(ids)} shortcuts called {name!r}, expected 1")
    grid = config_dir / "grid"
    grid.mkdir(exist_ok=True)
    written = []
    for source, target in NAMES.items():
        if (art / source).is_file():
            dest = grid / target.format(id=ids[0])
            shutil.copyfile(art / source, dest)
            written.append(dest)
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--name", default="OpenCE", help="the shortcut's name in Steam")
    parser.add_argument("--art", type=Path, default=ART, help="folder with the picture files")
    parser.add_argument("--steam", type=Path, default=Path.home() / ".local/share/Steam", help="Steam's folder")
    args = parser.parse_args(argv)
    configs = sorted(args.steam.glob("userdata/*/config/shortcuts.vdf"))
    if not configs:
        print(f"no shortcuts.vdf under {args.steam}/userdata", file=sys.stderr)
        return 1
    for config in configs:
        for path in install(config.parent, args.art, args.name):
            print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
