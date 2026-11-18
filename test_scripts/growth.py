#!/usr/bin/env python3
"""growth.py RUN_DIR [RUN_NAME]: memory growth over a soak, from RUN_DIR/results.jsonl.

RUN_NAME is a column such as nova-appimage (default: every row). Prints, per lap of 13 maps, the RSS at the end of
the first and last map; the first-to-last change of the fds, threads and smaps rollup (Rss, Anonymous, ...); and the
eight mappings whose RSS grew most (device_session.py records them per map). Soak data comes from
run_full.py --maps soak.
"""
import argparse
import json
from pathlib import Path


def cats(r):
    s = r.get("stats") or {}
    return s.get("by_map", {}), s.get("rollup", {}), s.get("fds"), s.get("threads")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("run_name", nargs="?")
    a = ap.parse_args()
    rows = [json.loads(line) for line in open(Path(a.run_dir) / "results.jsonl")]
    if a.run_name:
        rows = [r for r in rows if r["run"] == a.run_name]
    if not rows:
        raise SystemExit("no rows")
    print(len(rows), "loads", "non-loaded:", [(r["map"], r["verdict"]) for r in rows if r["verdict"] != "loaded"])
    laps = [rows[i:i + 13] for i in range(0, len(rows), 13)]
    for i, lap in enumerate(laps, 1):
        ends = [r["rss_last"] // 1024 for r in lap if r["rss_last"]]
        starts = [r["rss_first"] // 1024 for r in lap if r["rss_first"]]
        print("lap%d n=%d  end-of-map first %d last %d  (start-of-map first %d last %d)"
              % (i, len(lap), ends[0], ends[-1], starts[0], starts[-1]))
    bf, rf, fdf, thf = cats(rows[0])
    bl, rl, fdl, thl = cats(rows[-1])
    print("fds %s -> %s, threads %s -> %s" % (fdf, fdl, thf, thl))
    print("rollup MB first -> last:", {k: (rf.get(k, 0) // 1024, rl.get(k, 0) // 1024) for k in (
        "Rss", "Anonymous", "Private_Dirty", "Shared_Clean", "Private_Clean", "LazyFree", "Swap")})
    keys = sorted(set(bf) | set(bl), key=lambda k: -(bl.get(k, 0) - bf.get(k, 0)))
    print("by mapping, MB first -> last (delta):")
    for k in keys[:8]:
        print("  %-26s %5d -> %5d (%+d)" % (k, bf.get(k, 0) // 1024, bl.get(k, 0) // 1024,
                                            (bl.get(k, 0) - bf.get(k, 0)) // 1024))
    for idx in (12, 25, 38, 51):     # the last load of each lap
        if idx < len(rows):
            _, ro, fd, th = cats(rows[idx])
            print("load %2d: rss %d anon %d lazyfree %d fds %s threads %s"
                  % (idx + 1, ro.get("Rss", 0) // 1024, ro.get("Anonymous", 0) // 1024,
                     ro.get("LazyFree", 0) // 1024, fd, th))


if __name__ == "__main__":
    main()
