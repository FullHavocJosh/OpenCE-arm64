"""vdf_list.py CONFIG_DIR: list the shortcuts of CONFIG_DIR/shortcuts.vdf and the grid files of each; read only.

CONFIG_DIR is ~/.steam/steam/userdata/<id>/config. Prints, per shortcut, the 32-bit appid (also the grid art
prefix), its signed form and the 64-bit game id for steam://rungameid/ ((appid << 32) | 0x02000000).
"""

import os
import struct
import sys

if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
    print(__doc__)
    sys.exit(0 if len(sys.argv) == 2 else 2)


def pm(b, i):
    out = []
    while True:
        t = b[i]
        i += 1
        if t == 8:
            return out, i
        j = b.index(b"\0", i)
        k = b[i:j].decode("utf8", "replace")
        i = j + 1
        if t == 0:
            v, i = pm(b, i)
        elif t == 1:
            j = b.index(b"\0", i)
            v = b[i:j].decode("utf8", "replace")
            i = j + 1
        else:
            v = struct.unpack("<I", b[i : i + 4])[0]
            i += 4
        out.append((k, v))


cfg = sys.argv[1]
data = open(os.path.join(cfg, "shortcuts.vdf"), "rb").read()
top, _ = pm(data, 0)
entries = [dict((k.lower(), v) for k, v in e) for k, e in dict((k.lower(), v) for k, v in top)["shortcuts"]]
grid = os.listdir(os.path.join(cfg, "grid")) if os.path.isdir(os.path.join(cfg, "grid")) else []
for idx, e in enumerate(entries):
    appid = e.get("appid")
    name = e.get("appname")
    a32 = appid & 0xFFFFFFFF if appid is not None else None
    signed = a32 - (1 << 32) if a32 is not None and a32 >= (1 << 31) else a32
    g64 = ((a32 << 32) | 0x02000000) if a32 is not None else None
    files = sorted(
        f
        for f in grid
        if a32 is not None and (f.startswith(str(a32)) or f.startswith(str(g64)) or f.startswith(str(abs(signed))))
    )
    print("[%d] %r appid %s (signed %s) grid64 %s" % (idx, name, a32, signed, g64))
    print(
        "     exe %r opts %r startdir %r icon %r"
        % (e.get("exe"), e.get("launchoptions"), e.get("startdir"), e.get("icon"))
    )
    print("     grid files: %s" % (files or "-"))
