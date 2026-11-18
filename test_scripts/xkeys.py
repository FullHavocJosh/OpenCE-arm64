"""Type a console line into the game through XTEST: xkeys.py DISPLAY 'line'. Opens the console with grave first.

For the Nova, whose arm64 guest has no telnet console. Needs libX11.so.6 and libXtst.so.6 and the game window
focused (start it from a Steam shortcut). Example: xkeys.py :1 'map_name levels\\test\\carousel\\carousel'
Supported characters: letters, digits, space, backslash, underscore, period, minus.
"""

import ctypes
import sys
import time

if len(sys.argv) != 3 or sys.argv[1] in ("-h", "--help"):
    print(__doc__)
    sys.exit(0 if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help") else 2)
x11 = ctypes.CDLL("libX11.so.6")
xt = ctypes.CDLL("libXtst.so.6")
x11.XOpenDisplay.restype = ctypes.c_void_p
x11.XStringToKeysym.restype = ctypes.c_ulong
x11.XKeysymToKeycode.restype = ctypes.c_ubyte
x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
x11.XFlush.argtypes = [ctypes.c_void_p]
xt.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
d = x11.XOpenDisplay(sys.argv[1].encode())
if not d:
    raise SystemExit("no display")
NAMES = {" ": "space", "\\": "backslash", "_": "underscore", "`": "grave", "\n": "Return", ".": "period", "-": "minus"}
SHIFT = set("_ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def code(ch):
    name = NAMES.get(ch, ch)
    base = "underscore" if ch == "_" else name
    ks = x11.XStringToKeysym(base.encode())
    kc = x11.XKeysymToKeycode(d, ks)
    if not kc:
        raise SystemExit("no keycode for %r" % ch)
    return kc


def press(kc, shift=False, hold=0.03):
    sh = x11.XKeysymToKeycode(d, x11.XStringToKeysym(b"Shift_L"))
    if shift:
        xt.XTestFakeKeyEvent(d, sh, 1, 0)
    xt.XTestFakeKeyEvent(d, kc, 1, 0)
    x11.XFlush(d)
    time.sleep(hold)
    xt.XTestFakeKeyEvent(d, kc, 0, 0)
    if shift:
        xt.XTestFakeKeyEvent(d, sh, 0, 0)
    x11.XFlush(d)
    time.sleep(hold)


press(code("`"))
time.sleep(0.5)
for ch in sys.argv[2]:
    press(code(ch), ch in SHIFT)
press(code("\n"))
time.sleep(0.3)
press(code("`"))
