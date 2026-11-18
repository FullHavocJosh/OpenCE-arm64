# On-device validation scripts

Scripts that drive a real game session on the Steam Deck (x86_64), the NovaDeck (aarch64) and a reference PC (the
G14) to check the AppImage and Flatpak builds: map after map in one continuous, real-time session, a screenshot and
RSS samples per map, a result page, side-by-side contact sheets, and soaks for memory growth. They are not part of
the build or CI; run them by hand from a Mac or Linux workstation that can ssh to the devices.

The full how-to (device access, the Steam shortcut route, what not to touch on the devices, per-device facts,
pitfalls) is `PACKAGE_TESTING.md` in the ai-info repo: `~/ai-info/OpenCE-arm64/PACKAGE_TESTING.md`. It is in review
(ai-info PR 7) and not merged yet. `vdf_list.py`, `vdf_edit.py` and `xkeys.py` are the same helpers as in that PR.

Needs Python 3 on the workstation (`compare.py` also needs `numpy` and `Pillow`), `ssh` and `scp` with key login to
each device, and only `python3` on the device.

## Scripts

| Script              | Where it runs                               | What it does                                                                                                                                                                                                                   |
| ------------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `run_full.py`       | workstation                                 | Runs one session on one device and package: starts `device_session.py` over ssh, pulls each map's screenshot and log, appends `results.jsonl`, rewrites `index.html`, restarts the session at the next map when the game dies. |
| `device_session.py` | device (sent by `run_full.py`)              | The session itself: starts the game, loads each map through the loader, waits for the load line in `debug.txt`, samples RSS and process stats for 30 s, takes a screenshot at 25 s, emits one JSON line per map.               |
| `devices.py`        | workstation                                 | Host names, loaders and game ids, all overridable by environment variables (below). `python3 devices.py` prints the table in effect.                                                                                           |
| `soak.sh`           | workstation                                 | Four laps of the 13 multiplayer maps on the Deck and the Nova, AppImage then Flatpak, both devices in parallel.                                                                                                                |
| `soak_report.py`    | workstation                                 | Per column and lap: RSS at the first and last map and the lap maximum, and the maps that did not load.                                                                                                                         |
| `growth.py`         | workstation                                 | Where a soak's memory went: per-lap RSS, fds, threads, smaps rollup, the mappings that grew most.                                                                                                                              |
| `compare.py`        | workstation                                 | Contact sheets per map across devices and an automatic difference check against the G14 shots (mean difference, block SSIM, black, pink and flat flags). The user judges the images; the flags only point at maps to look at.  |
| `vdf_list.py`       | device                                      | Lists the non-Steam shortcuts in `shortcuts.vdf`, their appids, game ids and art files. Read only.                                                                                                                             |
| `vdf_edit.py`       | device                                      | Removes and adds non-Steam shortcuts in `shortcuts.vdf` (write `shortcuts.vdf.new` while Steam runs, swap it in only after Steam has exited).                                                                                  |
| `xkeys.py`          | device (sent by `run_full.py` for the Nova) | Types a console line into the game through XTEST.                                                                                                                                                                              |

Every script prints its usage with `--help`.

## Settings

| Variable                                                  | Meaning                                                                                                                                                                                        |
| --------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `OPENCE_VALIDATE_DIR`                                     | where runs are written (default `~/opence-validate`)                                                                                                                                           |
| `OPENCE_HOST_DECK`, `OPENCE_HOST_NOVA`, `OPENCE_HOST_G14` | ssh target `user@host` of each device (defaults in `devices.py`)                                                                                                                               |
| `OPENCE_GID_<DEVICE>_<PACKAGE>`                           | 64-bit Steam game id of the `OpenCE` shortcut, for example `OPENCE_GID_NOVA_FLATPAK`; `OPENCE_GID_<DEVICE>` covers both packages. No default: ids differ per device. `vdf_list.py` prints them |
| `OPENCE_G14_BINARY`                                       | the reference build the G14 starts directly (default `~/opence-test/ref387/halo`)                                                                                                              |
| `NO_FRAMES`                                               | drop `HALO_SCREENSHOT_EVERY` from the G14 launch                                                                                                                                               |

A run goes to `--run DIR` (default `$OPENCE_VALIDATE_DIR/<date>-run`): `results.jsonl`, `index.html`,
`logs/<device>-<package>/<map>.txt`, `screenshots/<device>-<package>/<map>.png`.

## A validation run

The devices need the game and the maps installed and a non-Steam shortcut named `OpenCE` for each package (the
Deck and the Nova start the game through it, so gamescope presents it on the screen). The G14 starts a reference
build directly. Then, for each device and package:

    export OPENCE_GID_DECK_APPIMAGE=<game id from vdf_list.py>
    python3 run_full.py --device deck --package appimage --run ~/opence-validate/my-run

`--maps all` (the default) is the 10 single-player maps first, then the 13 multiplayer maps, in ONE session per
device and package. Keep that order and that single session: a campaign map loaded after a multiplayer map leaves
multiplayer mode (`NETGAME MAP FAILURE`) and the cutscene cameras jump. Multiplayer maps get `game_variant slayer`
before the map. The game runs real time (no fixed step, windowed or null renderer). Each map is 30 s after its load
line (`structure culling:` in `debug.txt`) with RSS every 3 s and a screenshot at 25 s.

Run the same on the G14 with `--device g14 --package ref` (the reference), then
`python3 compare.py ~/opence-validate/my-run` after copying or running every column into one run directory
(columns: `g14-ref`, `deck-appimage`, `nova-appimage`, `deck-flatpak`, `nova-flatpak`).

## A soak

Four laps of the 13 multiplayer maps, 12 s each (so each map is loaded 4 times, 52 loads), RSS every 2 s:

    export OPENCE_GID_DECK_APPIMAGE=... OPENCE_GID_DECK_FLATPAK=... OPENCE_GID_NOVA_APPIMAGE=... OPENCE_GID_NOVA_FLATPAK=...
    ./soak.sh ~/opence-validate/my-soak
    python3 run_full.py --device g14 --package ref --maps soak --seconds 12 --rss-every 2 --run ~/opence-validate/my-soak
    python3 soak_report.py ~/opence-validate/my-soak
    python3 growth.py ~/opence-validate/my-soak nova-appimage

For a 30 s soak use `--maps soak` with the default `--seconds 30`. A column that is flat from lap 2 does not leak. On
the Nova the process grows about 1.4 MB per map load on both packages, host side (above 4 GB), in Mesa objects made
per presented frame; `display.interpolation = false` (30 fps instead of 120) cuts it about fourfold. `growth.py`
shows the split by mapping; the smaps, fdinfo and chunk-walking analysis behind that finding was done with one-off
commands on the device, not with scripts in this directory.

## The loaders

The session needs to send `game_variant slayer` and `map_name levels\test\<map>\<map>` (campaign maps use
`levels\<map>\<map>`) to the running game.

- **telnet** (Deck, G14): the game runs a console on `127.0.0.1:2323` when `HALO_TELNET_CONSOLE=true` and
  `HALO_TELNET_CONSOLE_PORT` is set in the launch options. `device_session.py` connects on the device and types the
  lines. See `port/linux/README.md` for the console and the other `HALO_*` settings.
- **key injection** (Nova): the aarch64 guest has no sockets, so no telnet console. `xkeys.py` opens the developer
  console with the grave key and types the line through XTEST on the X display of the game (`:1`). It needs
  `libX11.so.6` and `libXtst.so.6` and the game window focused, which is why the game must start from the Steam
  shortcut. `run_full.py` copies `xkeys.py` to `/tmp/opence-xkeys.py` on the device and removes it at the end.
  Characters: letters, digits, space, backslash, underscore, period, minus.

## Steam shortcuts

`vdf_list.py ~/.steam/steam/userdata/<id>/config` lists the shortcuts and the game id to export as
`OPENCE_GID_*`. To change shortcuts, back up `shortcuts.vdf`, write the result of `vdf_edit.py` as
`shortcuts.vdf.new`, close Steam with `steam -shutdown`, and only then copy it over `shortcuts.vdf`; Steam rewrites
the file on exit and would drop a change made while it runs. The exe path is part of the appid.
