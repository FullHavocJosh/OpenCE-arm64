"""vdf_edit.py IN OUT --remove NAME... [--add APPNAME EXE STARTDIR LAUNCHOPTIONS ICONPATH]

Binary shortcuts.vdf editor: parses to an ordered tree, drops shortcuts by appname, appends one, renumbers the
entries 0..n-1, writes OUT. Prints the appid of the added shortcut (crc32(exe + name) | 0x80000000).

Run it with Steam closed, on a backup, and write OUT as shortcuts.vdf.new; swap it in only after Steam has exited
(Steam rewrites the file on exit). Quote EXE as Steam stores it, for example '"/home/deck/opence-test/x.AppImage"'.
The exe is part of the appid, so a different exe path gives a different appid. In ICONPATH, {id} becomes the appid.
Steam may renumber an appid on start (read ~/.steam/steam/logs/gameprocess_log.txt for "sanitize shortcut app id").
Example:
  vdf_edit.py shortcuts.vdf shortcuts.vdf.new --remove "OpenCE test" --add "OpenCE test" '"/usr/bin/flatpak"' \\
      '"/usr/bin/"' 'run io.github.opencommunityedition.OpenCE' ''
"""

import struct
import sys
import zlib


def parse_map(b, i):
    items = []
    while True:
        t = b[i]
        i += 1
        if t == 8:
            return items, i
        j = b.index(b"\0", i)
        key = b[i:j].decode("utf8", "replace")
        i = j + 1
        if t == 0:
            val, i = parse_map(b, i)
        elif t == 1:
            j = b.index(b"\0", i)
            val = b[i:j].decode("utf8", "replace")
            i = j + 1
        elif t == 2:
            val = struct.unpack("<I", b[i : i + 4])[0]
            i += 4
        else:
            raise SystemExit("unknown type %d at %d" % (t, i - 1))
        items.append((t, key, val))


def dump_map(items):
    out = b""
    for t, key, val in items:
        out += bytes([t]) + key.encode() + b"\0"
        if t == 0:
            out += dump_map(val)
        elif t == 1:
            out += val.encode() + b"\0"
        else:
            out += struct.pack("<I", val)
    return out + b"\x08"


def get(entry, key):
    for t, k, v in entry:
        if k.lower() == key.lower():
            return v
    return None


def main():
    a = sys.argv[1:]
    if len(a) < 2 or a[0] in ("-h", "--help"):
        print(__doc__)
        raise SystemExit(0 if a and a[0] in ("-h", "--help") else 2)
    src, dst = a[0], a[1]
    remove, add = [], None
    i = 2
    while i < len(a):
        if a[i] == "--remove":
            i += 1
            while i < len(a) and not a[i].startswith("--"):
                remove.append(a[i])
                i += 1
        elif a[i] == "--add":
            add = a[i + 1 : i + 6]
            i += 6
        else:
            raise SystemExit("bad argument " + a[i])
    data = open(src, "rb").read()
    top, end = parse_map(data, 0)
    assert end == len(data), "trailing bytes"
    root = [(t, k, v) for t, k, v in top if k.lower() == "shortcuts"]
    assert len(root) == 1
    entries = [v for t, k, v in root[0][2]]
    names = [get(e, "appname") for e in entries]
    kept = [e for e in entries if get(e, "appname") not in remove]
    print("removed", [n for n in names if n in remove], "kept", len(kept))
    appid = None
    if add:
        name, exe, startdir, opts, icon = add
        if name in [get(e, "appname") for e in kept]:
            raise SystemExit("a shortcut called %r already exists" % name)
        appid = zlib.crc32((exe + name).encode()) | 0x80000000

        def s(k, v):
            return (1, k, v)

        def n(k, v):
            return (2, k, v)

        kept.append(
            [
                n("appid", appid),
                s("appname", name),
                s("exe", exe),
                s("StartDir", startdir),
                s("icon", icon.replace("{id}", str(appid))),
                s("ShortcutPath", ""),
                s("LaunchOptions", opts),
                n("IsHidden", 0),
                n("AllowDesktopConfig", 1),
                n("AllowOverlay", 1),
                n("OpenVR", 0),
                n("Devkit", 0),
                s("DevkitGameID", ""),
                n("DevkitOverrideAppID", 0),
                n("LastPlayTime", 0),
                s("FlatpakAppID", ""),
                (0, "tags", []),
            ]
        )
    new_root = (0, root[0][1], [(0, str(idx), e) for idx, e in enumerate(kept)])
    new_top = [new_root if k.lower() == "shortcuts" else (t, k, v) for t, k, v in top]
    out = dump_map(new_top)
    parse_map(out, 0)
    open(dst, "wb").write(out)
    print("appid", appid, "entries", len(kept), "wrote", dst)


main()
