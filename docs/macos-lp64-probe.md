# macOS LP64 probe results

Produced by `python3 tools/macos_lp64_probe.py` (no limit) from the repository
root. The full report is `build/macos-lp64/probe-report`. The probe compiled
every .c file under `source/` with the macOS LP64 prefix header.

## Totals

| Item                                          | Count |
| --------------------------------------------- | ----- |
| .c files probed                               | 477   |
| files with errors                             | 400   |
| errors                                        | 25527 |
| warnings                                      | 180   |
| unique failing layout assertions              | 425   |
| of which size asserts                         | 161   |
| of which offset asserts                       | 264   |
| failing assertions located in headers         | 125   |
| failing assertions reported against a .c file | 300   |

The three files with the most errors are `objects/objects.c` (173),
`interface/ui_widget.c` (147) and `units/units.c` (143). Error counts per file
are inflated by the same header failing in every includer, so the assertion
counts below are the better size measure.

Each unique assertion is reported once, against the first file that hit it.
A .c file in the lists below usually means the struct is declared in a header
it includes, not that the struct lives in the .c file.

## Top 15 files by failing layout assertions

| Assertions | File                                                   |
| ---------- | ------------------------------------------------------ |
| 25         | main/main.c                                            |
| 23         | interface/hud_messaging.c                              |
| 17         | ai/actor_perception.c                                  |
| 17         | rasterizer/xbox/rasterizer_xbox_transparent_geometry.c |
| 16         | effects/particle_system_definitions.h                  |
| 15         | cseries/profile.h                                      |
| 14         | interface/unit_hud_interface_definition.h              |
| 14         | networking/network_client_manager.c                    |
| 12         | ai/path.h                                              |
| 11         | ai/ai_debug.h                                          |
| 10         | objects/damage.c                                       |
| 10         | rasterizer/rasterizer_cinematics.c                     |
| 9          | effects/effects.c                                      |
| 8          | tool/connected_geometry.c                              |
| 8          | interface/interface.c                                  |

## Error categories

| Category                       | Count                                                                                                                                                                                                                                                                                                                                                     | Likely fix                                                                                                                                                                                                                                                        |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Struct size and offset asserts | 425 unique (161 size, 264 offset)                                                                                                                                                                                                                                                                                                                         | Structs holding pointers or `long`/`unsigned long` fields grow under LP64; keep 32-bit fields via the `long` token rewriter, and give pointer members fixed-width storage (or LP64-specific expected sizes) where the layout is an on-disk or in-memory contract. |
| Conflicting libc builtins      | 10 listed (`_stdio.h`, `math.h`, `port/linux/include/stdio.h:13-14` `__builtin___snprintf_chk` / `__builtin___vsnprintf_chk`)                                                                                                                                                                                                                             | The Linux prefix header and `port/linux/include/stdio.h` redeclare libc functions that the macOS SDK already declares as checked builtins; guard those declarations out for `__APPLE__` and use the SDK headers.                                                  |
| Pointer casts                  | 79 pointer/integer cast warnings (28 `-Wpointer-to-int-cast`, 26 `-Wint-to-pointer-cast`, 21 `-Wvoid-pointer-to-int-cast`, 4 `-Wint-to-void-pointer-cast`); also 98 pointer-type warnings (68 `-Wincompatible-pointer-types`, 17 `-Wincompatible-pointer-types-discards-qualifiers`, 13 `-Wincompatible-function-pointer-types`) and 3 `-Wint-conversion` | Replace casts of pointers through 32-bit ints with `intptr_t`/`uintptr_t`, and fix the `long*` versus `int*` mismatches by keeping those values as the 32-bit typedef.                                                                                            |
| Undeclared identifiers         | Not counted by the probe (the report lists only the first 10 non-layout errors)                                                                                                                                                                                                                                                                           | Most come from the same missing or conflicting prefix-header declarations as the libc builtins; rerun the probe after the prefix header is fixed and count what remains.                                                                                          |

The 25527 error total is dominated by the first and second categories: a
single bad header is re-reported by every .c file that includes it.

## Proposed work packages

Failing assertions grouped by top-level directory of `source/`, with the
number of files in that directory that carry at least one. Ordered by
dependency: the base libraries every other directory includes come first.

| Order | Directory               | Assertions | Files | Notes                                                                                                    |
| ----- | ----------------------- | ---------- | ----- | -------------------------------------------------------------------------------------------------------- |
| 1     | cseries                 | 15         | 1     | `profile.h`; base types and macros, fix first. Also covers the prefix-header and libc builtin conflicts. |
| 2     | memory                  | 7          | 5     | Allocators and pools used by every other directory.                                                      |
| 3     | tag_files               | 1          | 1     | Tag layout contract.                                                                                     |
| 4     | bitmaps                 | 4          | 3     | Tag data consumed by render and rasterizer.                                                              |
| 5     | shaders                 | 7          | 1     | Tag data consumed by rasterizer.                                                                         |
| 6     | physics                 | 8          | 2     | Collision and point physics.                                                                             |
| 7     | structures              | 11         | 4     | BSP and visibility.                                                                                      |
| 8     | scenario                | 7          | 4     | Scenario tag layout.                                                                                     |
| 9     | objects                 | 28         | 8     | Object headers are included by most gameplay code.                                                       |
| 10    | units                   | 1          | 1     | Depends on objects.                                                                                      |
| 11    | devices                 | 6          | 1     | Depends on objects.                                                                                      |
| 12    | effects                 | 41         | 7     | Particle and effect definitions.                                                                         |
| 13    | models                  | 0          | 0     | No unique assertions; errors are inherited.                                                              |
| 14    | game                    | 6          | 4     | Depends on objects and units.                                                                            |
| 15    | ai                      | 76         | 13    | Largest gameplay package; depends on game, objects, units.                                               |
| 16    | hs                      | 1          | 1     | Script engine.                                                                                           |
| 17    | camera                  | 9          | 3     |                                                                                                          |
| 18    | render                  | 8          | 3     |                                                                                                          |
| 19    | sound                   | 11         | 2     |                                                                                                          |
| 20    | bink                    | 5          | 1     |                                                                                                          |
| 21    | rasterizer (incl. xbox) | 61         | 12    | Depends on render, bitmaps and shaders.                                                                  |
| 22    | interface               | 60         | 7     | HUD and widgets; depends on most of the above.                                                           |
| 23    | networking              | 19         | 3     |                                                                                                          |
| 24    | main                    | 25         | 1     | `main.c`; last, since it includes everything.                                                            |
| 25    | tool                    | 8          | 1     | `connected_geometry.c`; tool only, can be skipped for the game build.                                    |

The order is a reasoned dependency guess from directory purpose, not from an
include graph. Assertion counts total 425 across the directories above.
