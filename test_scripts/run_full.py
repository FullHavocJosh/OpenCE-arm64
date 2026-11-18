#!/usr/bin/env python3
"""Mac side of the on-device validation: run one continuous game session on a device, map after map.

  run_full.py --device deck|nova|g14 --package appimage|flatpak|ref [--maps all|sp|mp|soak|a10,a30,...]

Runs device_session.py on the device over ssh, pulls each map's screenshot and log as it finishes, appends
results.jsonl and rewrites index.html after every map, and restarts the session at the next map when the game
dies. Prints one line per map and a status line every --status-every maps.

--maps all is the 10 single-player maps, then the 13 multiplayer maps, in ONE session. soak is four laps of the 13
multiplayer maps. The Deck and the Nova start the game through their "OpenCE" Steam shortcut (needs its game id:
--gid or OPENCE_GID_<DEVICE>_<PACKAGE>); the G14 starts the reference build directly.

Output goes to --run (default $OPENCE_VALIDATE_DIR/<date>-run, $OPENCE_VALIDATE_DIR default ~/opence-validate):
results.jsonl, index.html, logs/<device>-<package>/<map>.txt, screenshots/<device>-<package>/<map>.png.
Hosts, game ids and the reference binary come from devices.py and its OPENCE_* environment variables.
The environment variable NO_FRAMES drops HALO_SCREENSHOT_EVERY from the G14 launch.
"""
import argparse
import base64
import html
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import devices

HERE = Path(__file__).resolve().parent
MAPS = {"all": devices.ALL, "sp": devices.SP, "mp": devices.MP, "soak": devices.MP * 4}
XKEYS_REMOTE = "/tmp/opence-xkeys.py"


def render_index(run_dir, rows):
    runs = sorted({r["run"] for r in rows})
    by = {(r["run"], r["map"]): r for r in rows}
    css = ("body{font:13px system-ui;background:#111;color:#ddd;margin:12px}table{border-collapse:collapse}"
           "td,th{border:1px solid #333;padding:4px;text-align:center;vertical-align:top}img{width:320px;display:block}"
           ".loaded{color:#6c6}.crashed,.load-failed{color:#f66}.log-errors{color:#fc6}small{color:#999}")
    out = ["<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=10><title>OpenCE validation</title>"
           "<style>%s</style><h3>%s: %d maps done</h3><table><tr><th>map</th>%s</tr>"
           % (css, html.escape(run_dir.name), len(rows), "".join("<th>%s</th>" % html.escape(r) for r in runs))]
    for name in devices.ALL:
        cells = []
        for run in runs:
            r = by.get((run, name))
            if not r:
                cells.append("<td><small>-</small></td>")
                continue
            img = ('<a href="screenshots/%s/%s.png"><img loading=lazy src="screenshots/%s/%s.png"></a>'
                   % (run, name, run, name)) if r.get("shot") else ""
            grow = ""
            if r.get("rss_first") and r.get("rss_last"):
                grow = "RSS %d to %d MB (max %d)" % (r["rss_first"] // 1024, r["rss_last"] // 1024,
                                                      r["rss_max"] // 1024)
            bad = html.escape("\n".join(r["bad"][:4]))
            cells.append('<td><b class="%s">%s</b> <small>load %ss<br>%s</small>%s<small title="%s">%s</small></td>'
                         % (r["verdict"].replace(" ", "-"), r["verdict"], r.get("load_s"), grow, img, bad,
                            html.escape(r["bad"][0][:90]) if r["bad"] else ""))
        out.append("<tr><th>%s</th>%s</tr>" % (name, "".join(cells)))
    (run_dir / "index.html").write_text("".join(out) + "</table>")


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--device", required=True, choices=sorted(devices.DEVICES))
    ap.add_argument("--package", required=True, help="appimage, flatpak or ref; names the run and its folders")
    ap.add_argument("--run", help="output directory (default $OPENCE_VALIDATE_DIR/<date>-run)")
    ap.add_argument("--maps", default="all", help="all, sp, mp, soak or a comma list of map names")
    ap.add_argument("--seconds", type=int, default=30, help="seconds in each map after its load line (30)")
    ap.add_argument("--rss-every", type=float, default=3, help="RSS sample interval in seconds (3)")
    ap.add_argument("--shot-at", type=float, default=25, help="second of the screenshot in each map (25)")
    ap.add_argument("--status-every", type=int, default=5, help="print a STATUS line every N maps (5)")
    ap.add_argument("--root", help="game data root on the device (default ~/.local/share/halo/opence-test/<run>-live)")
    ap.add_argument("--config-text", default="", help="text written to the run's config.toml, \\n for newline")
    ap.add_argument("--proc", help="process name to watch (default per device)")
    ap.add_argument("--gid", help="64-bit Steam game id of the shortcut to start (default OPENCE_GID_*)")
    return ap.parse_args()


def deploy_xkeys(host):
    subprocess.run(["scp", "-q", str(HERE / "xkeys.py"), "%s:%s" % (host, XKEYS_REMOTE)], check=True)


def remove_xkeys(host):
    subprocess.run(["ssh", "-o", "BatchMode=yes", host, "rm", "-f", XKEYS_REMOTE])


def fetch_shot(host, remote_dir, dest, ext):
    subprocess.run(["scp", "-q", "%s:%s/%s" % (host, remote_dir, dest.name), str(dest)])
    if ext == "bmp":
        from PIL import Image
        Image.open(dest).convert("RGB").save(dest.with_suffix(".png"))
        dest.unlink()


def main():
    a = parse_args()
    dev = devices.device_config(a.device)
    if os.environ.get("NO_FRAMES") and "launch_env" in dev:
        dev["launch_env"] = {k: v for k, v in dev["launch_env"].items() if k != "HALO_SCREENSHOT_EVERY"}
    if a.proc:
        dev["proc"] = a.proc
    gid = a.gid or devices.gid(a.device, a.package)
    if dev.get("launch") != "direct":
        if not gid:
            sys.exit("no Steam game id: pass --gid or set OPENCE_GID_%s_%s (vdf_list.py prints it)"
                     % (a.device.upper(), a.package.upper()))
        dev["gid"] = gid
    run_dir = Path(a.run) if a.run else devices.validate_dir() / (time.strftime("%Y%m%d") + "-run")
    key = "%s-%s" % (a.device, a.package)
    (run_dir / "screenshots" / key).mkdir(parents=True, exist_ok=True)
    (run_dir / "logs" / key).mkdir(parents=True, exist_ok=True)
    maps = MAPS.get(a.maps) or a.maps.split(",")
    root = a.root or "~/.local/share/halo/opence-test/%s-live" % key
    host = devices.host(a.device)
    jsonl = run_dir / "results.jsonl"
    if dev["loader"] == "xtest":
        deploy_xkeys(host)
        dev["xkeys"] = XKEYS_REMOTE
    done_count = 0
    start = 0
    print("%s: starting %d maps, %s loader" % (key, len(maps), dev["loader"]), flush=True)
    while start < len(maps):
        cfg = dict(dev, root=root, maps=maps[start:], seconds=a.seconds, rss_every=a.rss_every, shot_at=a.shot_at,
                   config_text=a.config_text.replace("\\n", "\n"))
        shots_remote = root + "/shots"
        with open(HERE / "device_session.py") as script:
            p = subprocess.Popen(["ssh", "-o", "BatchMode=yes", "-o", "ServerAliveInterval=15", host, "python3", "-u",
                                  "-", base64.b64encode(json.dumps(cfg).encode()).decode()],
                                 stdin=script, stdout=subprocess.PIPE, text=True)
            died = None
            for line in p.stdout:
                try:
                    ev = json.loads(line)
                except ValueError:
                    print("%s: %s" % (key, line.strip()), flush=True)
                    continue
                if ev["kind"] == "map":
                    name = ev["map"]
                    if ev["shot"]:
                        ext = "bmp" if dev.get("shot") == "frames" else "png"
                        fetch_shot(host, shots_remote, run_dir / "screenshots" / key / (name + "." + ext), ext)
                    (run_dir / "logs" / key / (name + ".txt")).write_text(ev.pop("log"))
                    ev.update(run=key, device=a.device, package=a.package, map=name)
                    with open(jsonl, "a") as f:
                        f.write(json.dumps(ev) + "\n")
                    rows = [json.loads(row) for row in jsonl.read_text().splitlines()]
                    render_index(run_dir, rows)
                    done_count += 1
                    note = ""
                    if ev["verdict"] != "loaded":
                        note = " | " + (ev["bad"][0][:120] if ev["bad"] else "no load line")
                    print("%s: %s %s load %ss rss %s->%s MB%s" % (key, name, ev["verdict"], ev["load_s"],
                          (ev["rss_first"] or 0) // 1024, (ev["rss_last"] or 0) // 1024, note), flush=True)
                    if done_count % a.status_every == 0:
                        print("%s STATUS: %d of %d maps done" % (key, done_count, len(maps)), flush=True)
                elif ev["kind"] == "session_died":
                    died = ev["next"]
                else:
                    print("%s: %s" % (key, json.dumps(ev)[:300]), flush=True)
            p.wait()
        if died is not None:
            start += died
            print("%s: game died on a map, restarting the session at map index %d" % (key, start), flush=True)
            continue
        if p.returncode != 0:
            print("%s: session ended with code %s, stopping" % (key, p.returncode), flush=True)
        break
    if dev["loader"] == "xtest":
        remove_xkeys(host)
    print("%s: finished, %d maps" % (key, done_count), flush=True)


if __name__ == "__main__":
    main()
