"""Runs ON the device, started by run_full.py: ssh HOST python3 -u - BASE64_JSON < device_session.py

One continuous game session, map after map. The argument is the base64 of a JSON config (root, maps, loader,
proc, gid or launch_cmd, seconds, rss_every, shot_at, ...); see run_full.py for how it is built.

Per map: send the loader command, wait for the load line in debug.txt, then 30 s wall clock from the moment the
load line is seen: RSS of the game process every 3 s, a gamescope screenshot at 25 s. One JSON line per map.
Exit 3 when the game process dies (the host restarts the session at the next map), 4 when the game never starts.
The game starts through its Steam shortcut (steam -ifrunning steam://rungameid/GID) so gamescope presents it, or
directly when the config says launch=direct (the G14). The loader is the game's telnet console on 127.0.0.1 or,
for the Nova, xkeys.py typing into the console through XTEST. Needs only python3 and the standard tools.
"""
import base64
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time

cfg = {}
ROOT = LOG = SHOTS = ""
NOISE = ("no DirectSound for bink", "failed to open bink file", "Couldn't read map file 'd:\\cachebeta.map'",
         "file_open('z:\\last_language.dat')", "file_open('z:\\lastprof.txt')", "failed to open 'z:\\lastprof.txt'",
         "connection lost to telnet client")
GAMESCOPE_SHOT = "/tmp/gamescope.png"   # where gamescope writes a requested screenshot
BAD = re.compile(r"### ERROR|fatal|backtrace|Segmentation|assert|crash|couldn't|could not|failed|unable to",
                 re.IGNORECASE)
MEM = re.compile(r"memory|alloc|texture cache|cache|heap|out of|budget", re.IGNORECASE)
CAMPAIGN = ("a10", "a30", "a50", "b30", "b40", "c10", "c20", "c40", "d20", "d40")


def emit(kind, **kw):
    print(json.dumps(dict(kind=kind, t=time.time(), **kw)), flush=True)


def game_pid():
    r = subprocess.run(["pgrep", "-u", str(os.getuid()), "-x", cfg["proc"]], capture_output=True, text=True)
    p = r.stdout.split()
    return int(p[0]) if p else None


def rss_kb(pid):
    try:
        for line in open("/proc/%d/status" % pid):
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except OSError:
        return None


def proc_stats(pid):
    """RSS by mapping (smaps), the rollup, open fds and threads: what grows from load to load."""
    out = {"fds": None, "threads": None, "by_map": {}, "rollup": {}}
    try:
        out["fds"] = len(os.listdir("/proc/%d/fd" % pid))
        out["threads"] = len(os.listdir("/proc/%d/task" % pid))
        drm = {}
        for fd in os.listdir("/proc/%d/fd" % pid):
            try:
                if "/dev/dri/" not in os.readlink("/proc/%d/fd/%s" % (pid, fd)):
                    continue
                for line in open("/proc/%d/fdinfo/%s" % (pid, fd)):
                    if line.startswith("drm-") and ":" in line:
                        k, v = line.split(":", 1)
                        v = v.split()
                        if v and v[0].isdigit() and k not in drm:
                            unit = 1 if len(v) < 2 else {"KiB": 1, "MiB": 1024, "B": 1 / 1024}.get(v[1], 1)
                            drm[k] = int(v[0]) * unit
            except OSError:
                continue
        out["drm"] = drm
        for line in open("/proc/%d/smaps_rollup" % pid):
            p = line.split()
            if len(p) >= 3 and p[2] == "kB":
                out["rollup"][p[0].rstrip(":")] = int(p[1])
        name = None
        for line in open("/proc/%d/smaps" % pid):
            p = line.split()
            if len(p) >= 5 and "-" in p[0] and ":" not in p[0]:
                path = p[5] if len(p) > 5 else "[anon]"
                name = path if path.startswith("[") else path.split("/")[-1] if "/" in path else path
                if name == "[anon]":
                    name = "[anon-low]" if int(p[0].split("-")[0], 16) < 0x100000000 else "[anon-high]"
                if path.startswith("/memfd") or "(deleted)" in line:
                    name = "memfd:" + name
            elif line.startswith("Rss:") and name:
                out["by_map"][name] = out["by_map"].get(name, 0) + int(p[1])
        top = sorted(out["by_map"].items(), key=lambda kv: -kv[1])[:14]
        out["by_map"] = dict(top)
    except OSError:
        pass
    return out


def level_of(name):
    return "levels\\%s\\%s" % (name, name) if name in CAMPAIGN else "levels\\test\\%s\\%s" % (name, name)


def commands(name):
    cmds = []
    if name not in CAMPAIGN:
        cmds.append("game_variant slayer")
    cmds.append("map_name " + level_of(name))
    return cmds


def send(lines):
    if cfg["loader"] == "telnet":
        s = socket.create_connection(("127.0.0.1", cfg.get("telnet_port", 2323)), timeout=5)
        time.sleep(0.3)
        s.recv(200)
        for line in lines:
            s.sendall(line.encode() + b"\r\n")
            time.sleep(0.5)
        s.close()
    else:
        for line in lines:
            subprocess.run(["python3", cfg["xkeys"], cfg["xdisplay"], line], timeout=30)
            time.sleep(0.8)


def read_log(offset):
    try:
        with open(LOG, "rb") as f:
            f.seek(offset)
            data = f.read()
        return data.decode("utf8", "replace"), offset + len(data)
    except OSError:
        return "", offset


def screenshot(dest):
    if cfg.get("shot") == "frames":
        raw = ROOT + "/rawshots"
        files = sorted((os.path.getmtime(os.path.join(raw, f)), f) for f in os.listdir(raw) if f.endswith(".bmp"))
        if len(files) < 2:
            return False
        shutil.copy(os.path.join(raw, files[-2][1]), dest.replace(".png", ".bmp"))   # (the newest may be half written)
        for _, f in files:
            os.remove(os.path.join(raw, f))
        return True
    try:
        os.remove(GAMESCOPE_SHOT)
    except OSError:
        pass
    subprocess.run(["xprop", "-display", ":0", "-root", "-f", "GAMESCOPECTRL_REQUEST_SCREENSHOT", "32c", "-set",
                    "GAMESCOPECTRL_REQUEST_SCREENSHOT", "3"], timeout=10)
    for _ in range(30):
        time.sleep(0.4)
        try:
            a = os.path.getsize(GAMESCOPE_SHOT)
            time.sleep(0.4)
            if a > 0 and a == os.path.getsize(GAMESCOPE_SHOT):
                shutil.copy(GAMESCOPE_SHOT, dest)
                return True
        except OSError:
            continue
    return False


def setup_and_launch(first):
    old = game_pid()
    if old:
        os.kill(old, signal.SIGTERM)
        for _ in range(20):
            time.sleep(0.5)
            if not game_pid():
                break
        else:
            os.kill(old, signal.SIGKILL)
    os.makedirs(ROOT, exist_ok=True)
    if not os.path.exists(ROOT + "/maps"):
        os.symlink(os.path.expanduser("~/.local/share/halo/maps"), ROOT + "/maps")
    shutil.rmtree(SHOTS, ignore_errors=True)
    os.makedirs(SHOTS)
    shutil.rmtree(ROOT + "/rawshots", ignore_errors=True)
    os.makedirs(ROOT + "/rawshots")
    for name in ("debug.txt", "config.toml"):
        try:
            os.remove(os.path.join(ROOT, name))
        except OSError:
            pass
    if cfg.get("config_text"):
        with open(ROOT + "/config.toml", "w") as f:
            f.write(cfg["config_text"])
    with open(ROOT + "/init.txt", "w") as f:
        f.write("".join(c + "\n" for c in commands(first)))
    emit("launch", map=first)
    if cfg.get("launch") == "direct":
        launch_env = {k: v.replace("{uid}", str(os.getuid())) for k, v in cfg["launch_env"].items()}
        env = dict(os.environ, **launch_env, HALO_DATA_ROOT=ROOT, HALO_CONFIG_FILE=ROOT + "/config.toml",
                   HALO_SCREENSHOT_DIR=ROOT + "/rawshots")
        cmd = [os.path.expanduser(c) for c in cfg["launch_cmd"]]
        subprocess.Popen(cmd, env=env, cwd="/tmp", stdout=open(ROOT + "/stdout.txt", "w"),
                         stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
    else:
        subprocess.Popen(["steam", "-ifrunning", "steam://rungameid/" + cfg["gid"]], env=dict(os.environ, DISPLAY=":0"),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                         start_new_session=True)
    for _ in range(120):
        time.sleep(0.5)
        if game_pid():
            return True
    return False


def main():
    global cfg, ROOT, LOG, SHOTS
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if len(sys.argv) == 2 else 2)
    cfg = json.loads(base64.b64decode(sys.argv[1]))
    ROOT = os.path.expanduser(cfg["root"])
    LOG = ROOT + "/debug.txt"
    SHOTS = ROOT + "/shots"
    maps = cfg["maps"]
    if not setup_and_launch(maps[0]):
        emit("fatal", why="the game process did not appear")
        sys.exit(4)
    offset = 0
    for i, name in enumerate(maps):
        if i:
            _, offset = read_log(offset)
            try:
                send(commands(name))
            except Exception as e:  # loader failure is a finding, the map just will not load
                emit("loader_error", map=name, error=repr(e))
        t_cmd = time.time()
        pid = game_pid()
        text, loaded_at = "", None
        want = "starting precaching of map '%s'" % name
        deadline = t_cmd + cfg.get("load_timeout", 60)
        while time.time() < deadline:
            time.sleep(0.5)
            new, _ = read_log(offset)
            text = new
            if want in text or "structure culling:" in text:
                loaded_at = time.time()
                break
            if not game_pid():
                break
        rss = []
        shot_ok = None
        alive = bool(game_pid())
        if loaded_at:
            base = loaded_at
            next_sample = base
            while time.time() - base < cfg.get("seconds", 30):
                now = time.time()
                if now >= next_sample:
                    pid = game_pid()
                    if not pid:
                        alive = False
                        break
                    rss.append([round(now - base, 1), rss_kb(pid)])
                    next_sample += cfg.get("rss_every", 3)
                if shot_ok is None and now - base >= cfg.get("shot_at", 25):
                    shot_ok = screenshot("%s/%s.png" % (SHOTS, name))
                time.sleep(0.25)
        stats = proc_stats(game_pid()) if game_pid() else {}
        text, offset = read_log(offset)
        lines = text.splitlines()
        bad = [ln for ln in lines if BAD.search(ln) and not any(n in ln for n in NOISE)]
        mem = [ln for ln in lines if MEM.search(ln)]
        vals = [r[1] for r in rss if r[1]]
        verdict = "crashed" if not alive else "load failed" if not loaded_at else "log errors" if bad else "loaded"
        emit("map", map=name, index=i, verdict=verdict, load_s=round(loaded_at - t_cmd, 1) if loaded_at else None,
             rss=rss, rss_first=vals[0] if vals else None, rss_max=max(vals) if vals else None,
             rss_last=vals[-1] if vals else None, shot=bool(shot_ok), bad=bad[:10], mem=mem[:8],
             log_lines=len(lines), stats=stats, log="\n".join(lines[-60:]))
        if not alive:
            emit("session_died", map=name, next=i + 1)
            sys.exit(3)
    emit("done")
    if cfg.get("kill_at_end") and game_pid():
        os.kill(game_pid(), signal.SIGTERM)


if __name__ == "__main__":
    main()
