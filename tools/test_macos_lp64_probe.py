"""The macOS LP64 probe (tools/macos_lp64_probe.py): its diagnostics parser and summary, on fixture text (no clang)."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import macos_lp64_probe

CLANG_OUTPUT = """\
build/macos-lp64/src/scenario/scenario_definitions.h:126:14: error: 'player_starting_location_size_assert' declared as an array with a negative size
  126 | typedef char player_starting_location_size_assert[
      |              ^
build/macos-lp64/src/sound/sound_definitions.h:194:14: error: 'looping_sound_definition_tracks_offset_assert' declared as an array with a negative size
build/macos-lp64/src/game/game.c:10:5: error: unknown type name 'foo_t'
build/macos-lp64/src/game/game.c:20:9: warning: cast to 'void *' from smaller integer type 'int' [-Wint-to-pointer-cast]
build/macos-lp64/src/game/game.c:21:9: warning: cast to 'void *' from smaller integer type 'int' [-Wint-to-pointer-cast]
build/macos-lp64/src/game/game.c:30:9: warning: incompatible pointer types [-Wincompatible-pointer-types]
5 errors generated.
"""


class ProbeTests(unittest.TestCase):
    def test_parse_diagnostics(self):
        found = macos_lp64_probe.parse_diagnostics(CLANG_OUTPUT)
        self.assertEqual(len(found), 6)
        self.assertEqual(found[0]["file"], "build/macos-lp64/src/scenario/scenario_definitions.h")
        self.assertEqual((found[0]["line"], found[0]["col"], found[0]["severity"]), (126, 14, "error"))
        self.assertIsNone(found[2]["flag"])
        self.assertEqual(found[3]["severity"], "warning")
        self.assertEqual(found[3]["flag"], "-Wint-to-pointer-cast")
        self.assertEqual(found[3]["message"], "cast to 'void *' from smaller integer type 'int'")

    def test_summarize(self):
        results = {
            "build/macos-lp64/src/game/game.c": macos_lp64_probe.parse_diagnostics(CLANG_OUTPUT),
            "build/macos-lp64/src/game/other.c": macos_lp64_probe.parse_diagnostics(CLANG_OUTPUT.split("\n", 1)[0]),
            "build/macos-lp64/src/game/clean.c": [],
        }
        summary = macos_lp64_probe.summarize(results)
        self.assertEqual(summary["files"], 3)
        self.assertEqual(summary["files_failing"], 2)
        self.assertEqual(summary["per_file"]["build/macos-lp64/src/game/game.c"], 3)
        self.assertEqual(summary["per_file"]["build/macos-lp64/src/game/clean.c"], 0)
        self.assertEqual(summary["asserts"], {
            "looping_sound_definition_tracks_offset_assert": "build/macos-lp64/src/sound/sound_definitions.h",
            "player_starting_location_size_assert": "build/macos-lp64/src/scenario/scenario_definitions.h",
        })
        self.assertEqual(summary["warnings"], {"-Wint-to-pointer-cast": 2, "-Wincompatible-pointer-types": 1})
        self.assertEqual([item["message"] for item in summary["first_errors"]], ["unknown type name 'foo_t'"])
        self.assertEqual(summary["errors"], 4)
        report = macos_lp64_probe.render_report(summary)
        self.assertIn("player_starting_location_size_assert  build/macos-lp64/src/scenario/scenario_definitions.h", report)
        self.assertEqual(len(macos_lp64_probe.render_summary(summary).splitlines()), 12)


if __name__ == "__main__":
    unittest.main()
