"""The macOS LP64 long rewriter (tools/macos_lp64_longs.py): each long spelling gets its 32-bit meaning, and comments,
strings, #include lines, long double and identifiers containing "long" are left alone."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import macos_lp64_longs

rewrite = macos_lp64_longs.rewrite_long_tokens

MAPPINGS = [
    ("unsigned long long x;", "unsigned __int64 x;"),
    ("long long x;", "__int64 x;"),
    ("signed long long x;", "__int64 x;"),
    ("unsigned long int x;", "unsigned int x;"),
    ("unsigned long x;", "unsigned int x;"),
    ("long int x;", "int x;"),
    ("signed long x;", "int x;"),
    ("long x;", "int x;"),
    ("unsigned   long\n  x;", "unsigned int\n  x;"),
    ("(long)p; sizeof(long)", "(int)p; sizeof(int)"),
]

LEFT_ALONE = [
    "long double x;",
    "long  double x;",
    "unsigned int x;",
    "int a_long_name; long_t y; longer z;",
    "// long x\nint y;",
    "/* unsigned long long\n long */ int y;",
    'puts("long long");',
    "char c = 'long';",
    '#include "long/long.h"',
    "  # include <long>",
]


class RewriteTests(unittest.TestCase):
    def test_mappings(self):
        for source, expected in MAPPINGS:
            with self.subTest(source=source):
                self.assertEqual(rewrite(source), expected)

    def test_left_alone(self):
        for source in LEFT_ALONE:
            with self.subTest(source=source):
                self.assertEqual(rewrite(source), source)

    def test_mixed(self):
        self.assertEqual(
            rewrite('long a; // long\nchar *s = "long"; long double d; long b;'),
            'int a; // long\nchar *s = "long"; long double d; int b;',
        )


class MirrorTests(unittest.TestCase):
    def test_cli_mirrors_folders_with_spaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / "src"
            (src / "my folder" / "sub").mkdir(parents=True)
            (src / "a.c").write_text("long a;\n")
            (src / "my folder" / "b.h").write_text("unsigned long long b;\n")
            (src / "my folder" / "sub" / "c.inl").write_text("long double c;\n")
            (src / "d.inc").write_text("signed long d;\n")
            (src / "readme.txt").write_text("long\n")
            out = tmp_path / "out"
            run = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "macos_lp64_longs.py"), str(src), str(out)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(run.stdout.strip(), "4")
            self.assertEqual((out / "a.c").read_text(), "int a;\n")
            self.assertEqual((out / "my folder" / "b.h").read_text(), "unsigned __int64 b;\n")
            self.assertEqual((out / "my folder" / "sub" / "c.inl").read_text(), "long double c;\n")
            self.assertEqual((out / "d.inc").read_text(), "int d;\n")
            self.assertFalse((out / "readme.txt").exists())

    def test_unchanged_output_is_not_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / "src"
            src.mkdir()
            (src / "a.c").write_text("long a;\n")
            out = tmp_path / "out"
            macos_lp64_longs.mirror(src, out)
            target = out / "a.c"
            before = target.stat().st_mtime_ns
            macos_lp64_longs.mirror(src, out)
            self.assertEqual(target.stat().st_mtime_ns, before)


if __name__ == "__main__":
    unittest.main()
