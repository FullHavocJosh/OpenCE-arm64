"""Device table shared by the Mac-side scripts (run_full.py, soak.sh).

Nothing here is a secret. Every value can be overridden by an environment variable:

  OPENCE_VALIDATE_DIR          where runs are written (default ~/opence-validate)
  OPENCE_HOST_DECK / _NOVA / _G14
                               ssh target (user@host) of each device; no default. Instead of exporting them, put
                               lines like "deck=user@host" in $OPENCE_VALIDATE_DIR/hosts (the documented names are
                               in PACKAGE_TESTING.md of the ai-info repo)
  OPENCE_GID_<DEVICE>_<PACKAGE>
                               the 64-bit Steam game id of the "OpenCE" non-Steam shortcut that starts that package,
                               for example OPENCE_GID_DECK_APPIMAGE; OPENCE_GID_<DEVICE> is the fallback for both
                               packages. vdf_list.py prints the id of each shortcut. There is no default: shortcut
                               ids differ per device and change when the shortcut is recreated.
  OPENCE_G14_BINARY            path on the G14 of the reference build that run_full.py starts directly
                               (default ~/opence-test/ref387/halo)

Run `python3 devices.py` to print the table in effect.
"""
import os
import sys
from pathlib import Path

# Maps, in the order they are loaded. Single-player first, then multiplayer: a campaign map loaded after a
# multiplayer one leaves multiplayer mode and the cutscene cameras jump, so SP goes first in one session.
MP = ["beavercreek", "bloodgulch", "boardingaction", "carousel", "chillout", "damnation", "hangemhigh",
      "longest", "prisoner", "putput", "ratrace", "sidewinder", "wizard"]
SP = ["a10", "a30", "a50", "b30", "b40", "c10", "c20", "c40", "d20", "d40"]
ALL = SP + MP

# loader: "telnet" (the game's console on 127.0.0.1:2323) or "xtest" (typed into the console through X11, for the
# arm64 guest, which has no sockets). proc: the process name to watch. "~" is expanded on the device.
DEVICES = {
    "deck": dict(proc="halo", loader="telnet"),
    "nova": dict(proc="halo_host", loader="xtest", xdisplay=":1"),
    "g14": dict(proc="halo", loader="telnet", launch="direct", shot="frames", kill_at_end=True,
                launch_env={"WAYLAND_DISPLAY": "wayland-0", "XDG_RUNTIME_DIR": "/run/user/{uid}",
                            "DISPLAY": ":0", "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/{uid}/bus",
                            "SDL_AUDIODRIVER": "dummy", "HALO_TELNET_CONSOLE": "true",
                            "HALO_TELNET_CONSOLE_PORT": "2323", "HALO_DISPLAY_MODE": "fullscreen",
                            "HALO_RESOLUTION": "1280x800", "HALO_SCREENSHOT_EVERY": "90"}),
}


def validate_dir():
    return Path(os.environ.get("OPENCE_VALIDATE_DIR", "~/opence-validate")).expanduser()


def host(device):
    """ssh target of a device: OPENCE_HOST_<DEVICE>, else its line in $OPENCE_VALIDATE_DIR/hosts."""
    value = os.environ.get("OPENCE_HOST_" + device.upper())
    hosts_file = validate_dir() / "hosts"
    if not value and hosts_file.exists():
        for line in hosts_file.read_text().splitlines():
            name, _, target = line.partition("=")
            if name.strip() == device and target.strip():
                value = target.strip()
    if not value:
        sys.exit("no ssh target for %s: set OPENCE_HOST_%s=user@host or add %s=user@host to %s"
                 % (device, device.upper(), device, hosts_file))
    return value


def gid(device, package):
    key = "OPENCE_GID_%s" % device.upper()
    return os.environ.get("%s_%s" % (key, package.upper())) or os.environ.get(key)


def device_config(device):
    cfg = dict(DEVICES[device])
    if device == "g14":
        binary = os.environ.get("OPENCE_G14_BINARY", "~/opence-test/ref387/halo")
        cfg["launch_cmd"] = [binary]
    return cfg


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(__doc__)
        sys.exit(0 if sys.argv[1] in ("-h", "--help") else 2)
    print("validate dir:", validate_dir())
    for name in DEVICES:
        print("%-5s host %s  gid appimage %s  flatpak %s" % (name, host(name), gid(name, "appimage"),
                                                              gid(name, "flatpak")))
