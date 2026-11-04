#!/usr/bin/env python3
"""Report what breaks when the game's C source is compiled LP64 for macOS arm64.

The macOS build cannot run the ILP32 guest, so it compiles the game LP64 (tools/macos_lp64_longs.py keeps `long` 32
bits). This probe mirrors source/ through that rewriter into build/macos-lp64/src, syntax-checks every .c file with
the flags of the Linux build (build/linux, from `ninja -t commands`) retargeted at arm64 macOS, and writes
build/macos-lp64/probe-report: the errors per file, the failing struct layout assertions (*_size_assert and
*_offset_assert) with the header that declares them, the warnings per class, the first distinct other errors and the
totals. It reports only; it fixes nothing.

    python3 tools/macos_lp64_probe.py [--limit N] [--jobs J]       (run from the repository root)
"""

import argparse
import os
import re
import shlex
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import macos_lp64_longs

SOURCE = Path("source")
MIRROR = Path("build/macos-lp64/src")
REPORT = Path("build/macos-lp64/probe-report")
LINUX_OBJECT = "build/linux/obj/source/scenario/scenario.o"
SEMANTICS_HEADERS = ["build/linux/halo_msvc_semantics.h", "build/linux/platform_msvc_semantics.h"]
FIRST_ERRORS = 10

CLANG_FLAGS = [
    "--target=arm64-apple-macos", "-DHALO_MACOS_LP64=1", "-fms-extensions", "-fshort-wchar", "-fcommon",
    "-fno-strict-aliasing", "-fwrapv", "-std=gnu89", "-D__STRICT_ANSI__", "-DDEBUG", "-Dxbox", "-Wno-everything",
    "-Wpointer-to-int-cast", "-Wint-to-pointer-cast", "-Wincompatible-pointer-types", "-Wint-conversion",
    "-ferror-limit=0",
]
# flags of the Linux compile that carry a path (the next word, or glued on for -I and -idirafter)
PATH_FLAGS = ("-include", "-iquote")
DIAGNOSTIC = re.compile(r"^(?P<file>.+?):(?P<line>\d+):(?P<col>\d+): (?P<severity>error|warning|fatal error): "
                        r"(?P<message>.*?)(?: \[(?P<flag>-W[\w+-]+)\])?$")
ASSERT_NAME = re.compile(r"'(?P<name>\w+_(?:size|offset)_assert)' declared as an array with a negative size")


def parse_diagnostics(text: str) -> list[dict]:
    """The error and warning lines of clang's output as dicts (file, line, col, severity, message, flag)"""
    found = []
    for raw in text.splitlines():
        match = DIAGNOSTIC.match(raw.rstrip())
        if not match:
            continue
        item = match.groupdict()
        item["line"] = int(item["line"])
        item["col"] = int(item["col"])
        item["severity"] = "error" if item["severity"] != "warning" else "warning"
        found.append(item)
    return found


def summarize(results: dict[str, list[dict]]) -> dict:
    """results maps each compiled file to its parsed diagnostics. Returns the errors per file, the unique failing
    layout assertions (name -> declaring header), the warnings per class, the first distinct other errors and totals"""
    per_file: dict[str, int] = {}
    asserts: dict[str, str] = {}
    warnings: Counter = Counter()
    first_errors: list[dict] = []
    seen = set()
    error_total = 0
    for name in sorted(results):
        errors = 0
        for item in results[name]:
            if item["severity"] == "warning":
                warnings[item.get("flag") or "(unclassified)"] += 1
                continue
            errors += 1
            match = ASSERT_NAME.search(item["message"])
            if match:
                asserts.setdefault(match.group("name"), item["file"])
                continue
            key = (item["file"], item["line"], item["message"])
            if key not in seen and len(first_errors) < FIRST_ERRORS:
                seen.add(key)
                first_errors.append(item)
        per_file[name] = errors
        error_total += errors
    return {
        "files": len(results),
        "files_failing": sum(1 for count in per_file.values() if count),
        "per_file": per_file,
        "asserts": dict(sorted(asserts.items())),
        "warnings": dict(sorted(warnings.items(), key=lambda pair: (-pair[1], pair[0]))),
        "first_errors": first_errors,
        "errors": error_total,
        "warnings_total": sum(warnings.values()),
    }


def render_report(summary: dict) -> str:
    lines = [f"errors per file ({summary['files_failing']} of {summary['files']} files fail)"]
    for name, count in sorted(summary["per_file"].items(), key=lambda pair: (-pair[1], pair[0])):
        lines.append(f"  {count:6d}  {name}")
    lines += ["", f"failing layout assertions ({len(summary['asserts'])} unique)"]
    for name, header in summary["asserts"].items():
        lines.append(f"  {name}  {header}")
    lines += ["", "warnings per class"]
    for flag, count in summary["warnings"].items():
        lines.append(f"  {count:6d}  {flag}")
    lines += ["", f"first {FIRST_ERRORS} distinct errors that are not layout assertions"]
    for item in summary["first_errors"]:
        lines.append(f"  {item['file']}:{item['line']}: {item['message']}")
    lines += ["", "totals",
              f"  files {summary['files']}, failing {summary['files_failing']}",
              f"  errors {summary['errors']}, warnings {summary['warnings_total']}",
              f"  unique failing layout assertions {len(summary['asserts'])}"]
    return "\n".join(lines) + "\n"


def render_summary(summary: dict) -> str:
    """12 lines for the terminal"""
    top = sorted(summary["per_file"].items(), key=lambda pair: (-pair[1], pair[0]))[:3]
    warnings = list(summary["warnings"].items())[:3]
    lines = [
        f"macOS LP64 probe: {summary['files']} files, {summary['files_failing']} failing",
        f"errors {summary['errors']}, warnings {summary['warnings_total']}",
        f"unique failing layout assertions {len(summary['asserts'])}",
        f"other distinct errors listed {len(summary['first_errors'])}",
    ]
    lines += [f"  worst file {count:5d}  {name}" for name, count in top]
    lines += [f"  warning {count:6d}  {flag}" for flag, count in warnings]
    lines += [f"report: {REPORT}"]
    while len(lines) < 12:
        lines.insert(-1, "")
    return "\n".join(lines[:11] + lines[-1:])


def ensure_headers() -> None:
    missing = [header for header in SEMANTICS_HEADERS if not Path(header).is_file()]
    if not missing:
        return
    if not Path("build.ninja").is_file():
        subprocess.run([sys.executable, "configure.py"], check=True)
    subprocess.run(["ninja", *missing], check=True)


def linux_arguments() -> list[str]:
    """The -include, -I, -iquote and -idirafter arguments of the Linux compile of one object, retargeted at the mirror"""
    output = subprocess.run(["ninja", "-t", "commands", LINUX_OBJECT], capture_output=True, text=True,
                            check=True).stdout.strip().splitlines()[-1]
    words = shlex.split(output)

    def retarget(path: str) -> str:
        return str(MIRROR / path[len("source/"):]) if path.startswith("source/") else (
            str(MIRROR) if path == "source" else path)

    arguments: list[str] = []
    i = 0
    while i < len(words):
        word = words[i]
        if word in PATH_FLAGS or word == "-idirafter" or word == "-I":
            arguments += [word, retarget(words[i + 1])]
            i += 2
            continue
        if word.startswith("-I") or word.startswith("-idirafter"):
            flag = "-idirafter" if word.startswith("-idirafter") else "-I"
            arguments.append(flag + retarget(word[len(flag):]))
        i += 1
    return arguments


def check_file(path: Path, arguments: list[str]) -> tuple[str, list[dict]]:
    run = subprocess.run(["clang", "-fsyntax-only", *CLANG_FLAGS, *arguments, str(path)], capture_output=True,
                         text=True)
    return str(path), parse_diagnostics(run.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--limit", type=int, default=0, help="check only the first N .c files")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    args = parser.parse_args(argv)
    if not SOURCE.is_dir():
        print("run from the repository root (source/ not found)", file=sys.stderr)
        return 1
    ensure_headers()
    macos_lp64_longs.mirror(SOURCE, MIRROR)
    arguments = linux_arguments()
    sources = sorted(MIRROR.rglob("*.c"))
    if args.limit > 0:
        sources = sources[:args.limit]
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        results = dict(pool.map(lambda path: check_file(path, arguments), sources))
    summary = summarize(results)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(render_report(summary))
    print(render_summary(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
