#!/usr/bin/env python3
"""Rewrite the game's C source so `long` keeps the 32-bit meaning it has under MSVC.

The game was written for MSVC/ILP32, where long is 32 bits (about 15,600 uses in source/). The macOS arm64 build
compiles it LP64, where long is 64 bits and every struct layout assertion on a long-bearing type would break. This
tool mirrors a source tree into another directory with the long spellings replaced, leaving the repository files
alone:

    unsigned long long            -> unsigned __int64
    long long, signed long long   -> __int64
    unsigned long [int]           -> unsigned int
    long [int], signed long       -> int

`long double`, identifiers that merely contain "long", comments, string and character literals and #include lines
are left as written. The prefix header must define __int64 as a typedef of long long.

    python3 tools/macos_lp64_longs.py SRC_DIR OUT_DIR
"""

import re
import sys
from pathlib import Path

SOURCE_SUFFIXES = {".c", ".h", ".inl", ".inc"}

TOKEN = re.compile(
    r"(?P<include>^[ \t]*#[ \t]*include[^\n]*)"
    r"|(?P<comment>/\*.*?\*/|//[^\n]*)"
    r'|(?P<string>"(?:\\.|[^"\\\n])*")'
    r"|(?P<char>'(?:\\.|[^'\\\n])*')"
    r"|(?P<word>[A-Za-z_]\w*)"
    r"|(?P<space>\s+)"
    r"|(?P<other>.)",
    re.DOTALL | re.MULTILINE,
)
INTEGER_WORDS = {"unsigned", "signed", "long", "int"}


def _replacement(words: list[str]) -> str:
    unsigned = "unsigned" in words
    if words.count("long") >= 2:
        return "unsigned __int64" if unsigned else "__int64"
    return "unsigned int" if unsigned else "int"


def rewrite_long_tokens(text: str) -> str:
    tokens = [(m.lastgroup, m.group()) for m in TOKEN.finditer(text)]
    out: list[str] = []
    i = 0
    while i < len(tokens):
        kind, value = tokens[i]
        if kind != "word" or value not in INTEGER_WORDS:
            out.append(value)
            i += 1
            continue
        # A run of integer keywords separated by whitespace only.
        words = [value]
        end = i + 1
        j = i + 1
        while j + 1 < len(tokens) and tokens[j][0] == "space" and tokens[j + 1][0] == "word" and tokens[j + 1][1] in INTEGER_WORDS:
            words.append(tokens[j + 1][1])
            end = j + 2
            j += 2
        if "long" not in words:
            out.extend(t[1] for t in tokens[i:end])
            i = end
            continue
        if words.count("long") == 1 and len(words) == 1:
            k = end
            if k < len(tokens) and tokens[k][0] == "space":
                k += 1
            if k < len(tokens) and tokens[k] == ("word", "double"):
                out.append(value)
                i = end
                continue
        out.append(_replacement(words))
        i = end
    return "".join(out)


def mirror(src_dir: Path, out_dir: Path) -> int:
    count = 0
    for path in sorted(src_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        target = out_dir / path.relative_to(src_dir)
        data = rewrite_long_tokens(path.read_bytes().decode("latin-1")).encode("latin-1")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file() or target.read_bytes() != data:
            target.write_bytes(data)
        count += 1
    return count


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    src_dir, out_dir = Path(argv[0]), Path(argv[1])
    if not src_dir.is_dir():
        print(f"{src_dir} is not a directory", file=sys.stderr)
        return 1
    print(mirror(src_dir, out_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
