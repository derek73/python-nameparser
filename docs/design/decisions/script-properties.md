# script-properties — one private table of what a script's writing does (#1256)

## Standing

- Whether a script has case for the name-case contrast, whether it writes initials, whether it writes period abbreviations and whether a bare run of its letters with a period is a spelled Latin initial are answered by one private table, `_policy._SCRIPT_PROPERTIES`, one row per script with its reason and source, and every rule that asks reads it — 2026-11-12 #1256.
- The rows are keyed by a private name, never by the public `Script` enum, whose membership says what a caller can key a setting on and settles nothing about case or initials — 2026-11-12 #1256.
- "Writes initials" (rules/T5's veto, rules/R7's `initials()`, the name match) and "writes period abbreviations" (rules/H2's shape) are two columns, which the four East Asian rows answer alike — 2026-11-12 #1256.
- Whether a script writes initials is decided by its convention, read where CLDR states one from the locale-authored name patterns that produce an initial, after checking that the locale's block is not a copy of `en`'s — 2026-11-12 #1256.
- The answers the fixes for #1191 (the Brahmic title-shape veto), #1214, #1223 and #1224 (case repair) gave are rows, not reopened; the Dutch `IJ` (#1242) is a language question and has no row — 2026-11-12 #1256.

Open: none in this file.

## Log

- 2026-11-12 #1256 — ONE TABLE, READ BY EVERY RULE THAT ASKS. Decided on the issue that day; this entry records the build. Before it the answers were scattered: `_policy._NO_INITIALS` (a tuple of `Script` members, read through `_script_matcher` by `_vocab.is_initial`, `_vocab.is_title_shaped`, `_pieces.is_leading_title`, `_render.initials` and `_match`), `_vocab._INDIC_BRAHMIC` (U+0900–0DFF, H2's veto), `_render._capitalize`'s Mtavruli test (R4, #1223) and Python's own case properties at every contrast. The table (`_policy._ScriptRow`: ranges, `has_case`, `writes_initials`, `period_abbreviations`, `spells_initials`, reason, source) is read through spans selected by column (`_policy._ranges_where`), from which the readers' matchers are built once at import: `_NO_INITIAL_RANGES` (T5, R7, the name match, and the byline order report in assign), `_NO_ABBREVIATION_RANGES` (H2's shape, `_pieces.is_leading_title`'s copy of it, and S3's joined `Ph. D.` split, whose comment had asked "a script that writes no abbreviations" of the initials set), `_SPELLED_INITIAL_RANGES` (H2's Brahmic Except, compiled for a C-level search as `_vocab._SPELLED_INITIAL`), and `_CASELESS_LETTERS`, a `str.translate` table dropping a caseless row's letters at the three sites that read the name-case contrast (`_vocab.is_one_case`, `_vocab.ambiguous_lean`, `_render._in_one_case`). The first commit moved the readers onto the table with no reading moved: `tools/differential/snapshot.jsonl` byte-identical, the frame band in `tests/v2/test_benchmark.py` unmoved. Rows at that commit: han, hangul, hiragana, katakana (each reusing its `_SCRIPT_RANGES` spans, so the two cannot drift) and brahmic (U+0900–0DFF). `tests/v2/test_script_properties.py` checks each row through every reader of its column on a letter of its own ranges, a Latin letter as the control, and refuses a module other than `_policy` that names the replaced constants or opens a character range at a row's first codepoint.
  - THE SPLIT. `_NO_INITIALS` answered two questions, whether a letter and a period can stand in for a name and whether a word with a period can be an abbreviation; CJK answers both no, and #323 had read the second off the first. Thai answers them apart (no initials by CLDR, but `ดร.` and `ร.ต.อ.` are titles written short), so each is a column.
  - The has-case column holds `None` where Unicode's case properties answer and `False` where the contrast reads none in a script Unicode gives case. Only a False row's letters that Unicode cases are listed in `_CASELESS_LETTERS`, the others being caseless to the comparison already; Word-level tests (whether a word is written in capitals, `is_capitals_word`, `written_as_a_name`, the caps-suffix shape) stay on Unicode's properties.

Recompute recipe for the CLDR column, as run 2026-11-12 on unicode-org/cldr main c0b65ae3: fetch `common/main/<locale>.xml` for the locale and for `en`; in `personNames`, take every `namePattern` whose text is not the inheritance marker `↑↑↑` (authored) and count those holding `-initial`; then, keyed by the enclosing `personName`'s order, length, usage and formality, compare each authored pattern with `en`'s after writing `en`'s comma as the locale's and removing spaces: a block equal to `en`'s throughout is a copy and states nothing about the locale.

| locale | authored | with an initial | a copy of `en`'s |
|---|---|---|---|
| ja | 29 | 0 | no |
| ko | 32 | 0 | no |
| th | 20 | 0 | no |
| ru | 42 | 7 | no |
| ka | 15 | 1 | no |
| my | 42 | 8 | yes: 36 identical once the comma is `၊`, the other 6 differing only by a space between initials; it holds `{surname-prefix}`, and Burmese names have no surname |

(2026-08-02's counts, #320, were ja 29, ko 32, th 20 and ru 7 of 39; ru has since authored more patterns.)
