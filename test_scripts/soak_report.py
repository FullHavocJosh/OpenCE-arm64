#!/usr/bin/env python3
"""soak_report.py [RUN_DIR]: one summary per column of a soak run, from RUN_DIR/results.jsonl.

RUN_DIR defaults to the newest *-soak* directory under $OPENCE_VALIDATE_DIR (default ~/opence-validate).
For each column (g14-ref, deck-appimage, deck-flatpak, nova-appimage, nova-flatpak): the number of loads, the maps
that did not load, and per lap of 13 maps the RSS at the end of the first and last map and the lap maximum, in MB.
A column that is flat from lap 2 has no leak; one that climbs every lap does (see growth.py for where).
"""
import argparse
import json
from pathlib import Path

import devices

COLUMNS = ("g14-ref", "deck-appimage", "deck-flatpak", "nova-appimage", "nova-flatpak")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", nargs="?")
    a = ap.parse_args()
    if a.run_dir:
        d = Path(a.run_dir)
    else:
        found = sorted(devices.validate_dir().glob("*soak*"))
        if not found:
            raise SystemExit("no *soak* run under %s" % devices.validate_dir())
        d = found[-1]
    rows = [json.loads(line) for line in open(d / "results.jsonl")]
    for run in COLUMNS:
        r = [x for x in rows if x["run"] == run]
        if not r:
            continue
        laps = [r[i:i + 13] for i in range(0, len(r), 13)]
        bad = [(x["map"], x["verdict"]) for x in r if x["verdict"] != "loaded"]
        line = []
        for i, lap in enumerate(laps, 1):
            ends = [x["rss_last"] // 1024 for x in lap if x["rss_last"]]
            line.append("lap%d n=%d first %d last %d max %d" % (i, len(lap), ends[0], ends[-1], max(ends)))
        print(run, "loads", len(r), "non-loaded", bad)
        print("  " + " | ".join(line))


if __name__ == "__main__":
    main()
