"""Download a Debian 13 armhf system root for the armhf feasibility probe.

    python tools/linux_armhf_sysroot.py <folder>

The package index is fetched live over HTTPS (feasibility only, not pinned).
Each package is checked against the SHA256 field of that index, and the
extracted tree is <folder>/sysroot. <folder>/stamp records the packages, so a
second run with an unchanged index downloads nothing.
"""

from __future__ import annotations

import lzma
import os
import shutil
import sys
import urllib.request
from pathlib import Path

try:
    from tools.linux_sysroot import deb_data, download, extract
except ImportError:
    from linux_sysroot import deb_data, download, extract


INDEX_URL = "https://deb.debian.org/debian/dists/trixie/main/binary-armhf/Packages.xz"
MIRROR = "https://deb.debian.org/debian/"

RUNTIME_ROOTS = [
    "libc6",
    "libgcc-s1",
    "libsdl3-0",
    "libegl1",
    "libgles2",
    "libegl-mesa0",
    "libgl1-mesa-dri",
    "mesa-libgallium",
    "libgbm1",
    "libdrm2",
    "libdrm-freedreno1",
    "libwayland-client0",
    "libwayland-egl1",
    "libwayland-cursor0",
    "libxkbcommon0",
]

DEV_ROOTS = [
    "libc6-dev",
    "linux-libc-dev",
    "libgcc-14-dev",
    "libsdl3-dev",
    "libegl-dev",
    "libgles-dev",
    "libgl-dev",
    "libwayland-dev",
    "libffi-dev",
    "libxkbcommon-dev",
    "libdrm-dev",
    "libgbm-dev",
    "libpulse-dev",
    "libasound2-dev",
    "libudev-dev",
    "libdbus-1-dev",
    "libdecor-0-dev",
]

SKIP_NAMES = {
    "debconf",
    "tzdata",
    "sed",
    "lsb-base",
    "netbase",
    "media-types",
    "sysvinit-utils",
    "native-architecture",
}


def is_skipped(name: str) -> bool:
    """Return True if a package name should be skipped."""
    return name in SKIP_NAMES or name.startswith(("python3", "libpython"))


def parse_index(text: str) -> dict[str, dict[str, str]]:
    """Parse a Debian Packages index into a dict keyed by Package name."""
    result: dict[str, dict[str, str]] = {}
    if not text:
        return result

    # Split stanzas by blank lines
    # Blank line can be \n\n or \r\n\r\n
    stanzas = []
    current = []
    for line in text.splitlines(True):  # keepends
        # Check if line is blank (just whitespace/newline)
        stripped_line = line.strip()
        if stripped_line == "":
            if current:
                stanzas.append("".join(current))
                current = []
            else:
                continue  # skip empty stanzas
        else:
            current.append(line)
    if current:
        stanzas.append("".join(current))

    for stanza in stanzas:
        fields: dict[str, str] = {}
        current_key = None
        current_value_lines = []
        for line in stanza.splitlines():
            # Continuation lines start with space or tab - ignore per task
            if line and (line[0] == " " or line[0] == "\t"):
                continue  # ignore continuation lines
            if ":" in line:
                # Save previous field if exists
                if current_key is not None:
                    fields[current_key] = "\n".join(current_value_lines).strip()
                # Parse new field
                key, value = line.split(":", 1)
                current_key = key.strip()
                current_value_lines = [value.strip()]
            else:
                # No colon, might be empty line - ignore
                continue
        if current_key is not None:
            fields[current_key] = "\n".join(current_value_lines).strip()

        if "Package" in fields:
            pkg_name = fields["Package"]
            result[pkg_name] = fields

    return result


def dependency_names(depends: str) -> list[str]:
    """Extract dependency names from a Depends field."""
    if not depends or not depends.strip():
        return []

    deps = []
    # Split on comma
    for dep_group in depends.split(","):
        dep_group = dep_group.strip()
        if not dep_group:
            continue
        # Take first alternative before |
        if "|" in dep_group:
            dep_group = dep_group.split("|")[0].strip()
        # Drop version constraints in parentheses
        if "(" in dep_group:
            # Remove everything from ( to )
            # Handle nested parens simply by taking up to first )
            paren_start = dep_group.find("(")
            dep_group = dep_group[:paren_start].strip()
        # Drop :any
        if ":" in dep_group:
            # Check if it's :any
            if ":any" in dep_group:
                dep_group = dep_group.replace(":any", "").strip()
            else:
                # Other architecture qualifiers - for this task just take before :
                dep_group = dep_group.split(":")[0].strip()
        if dep_group and dep_group.strip():
            deps.append(dep_group.strip())

    return deps


def resolve(
    index: dict[str, dict[str, str]],
    runtime_roots: list[str],
    dev_roots: list[str],
    skip=is_skipped,
) -> list[str]:
    """Resolve package dependencies."""
    result_set = set()

    # Runtime roots plus transitive Depends
    to_process = []
    # Add runtime roots
    for root in runtime_roots:
        if root in index and not skip(root):
            to_process.append(root)
            result_set.add(root)

    # Process transitively
    i = 0
    while i < len(to_process):
        current = to_process[i]
        i += 1
        if current not in index:
            continue
        fields = index[current]
        if "Depends" in fields:
            deps = dependency_names(fields["Depends"])
            for dep in deps:
                if dep in index and not skip(dep) and dep not in result_set:
                    result_set.add(dep)
                    to_process.append(dep)

    # Dev roots alone (no Depends)
    for root in dev_roots:
        if root in index and not skip(root):
            result_set.add(root)

    return sorted(result_set)


def fetch_index() -> str:
    """Download and decompress the live armhf Packages index."""
    with urllib.request.urlopen(INDEX_URL) as response:
        return lzma.decompress(response.read()).decode("utf-8")


def stamp_text(entries: list[dict[str, str]]) -> str:
    """Return one line per package (name, Version, SHA256), sorted."""
    lines = sorted(f"{e['Package']} {e['Version']} {e['SHA256']}" for e in entries)
    return "".join(line + "\n" for line in lines)


def make(folder: Path) -> None:
    """Create folder/sysroot from the armhf packages, unless folder/stamp is current."""
    index = parse_index(fetch_index())
    entries = [index[name] for name in resolve(index, RUNTIME_ROOTS, DEV_ROOTS)]
    text = stamp_text(entries)
    stamp = folder / "stamp"
    sysroot = folder / "sysroot"
    if stamp.is_file() and stamp.read_text() == text:
        return
    stamp.unlink(missing_ok=True)
    shutil.rmtree(sysroot, ignore_errors=True)
    sysroot.mkdir(parents=True)
    for entry in entries:
        filename = entry["Filename"]
        print(f"Downloading {filename}")
        deb = download([MIRROR + filename], entry["SHA256"])
        extract(deb_data(deb), sysroot)
    # The packages are usr-merged; linker scripts use absolute /lib paths.
    for name in ("lib", "bin", "sbin"):
        link = sysroot / name
        if not link.is_symlink() and not link.exists():
            os.symlink(f"usr/{name}", link)
    stamp.write_text(text)


def main(argv: list[str]) -> int:
    """Run make for one folder argument; print the usage otherwise."""
    if len(argv) != 2:
        print(__doc__)
        return 1
    make(Path(argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
