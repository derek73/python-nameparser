# D1 — the segmenterless-activation warning

## Standing

- `parser_for(locales.JA)` without a segmenter warns and does not raise: the inert registration is itself a pinned property, and a warning is filterable by the caller who wants it; the Japanese install hint appears only when a Japanese script is among the dead ones, a hangul-only gap getting the generic remedies — 2026-08 #337, WARN rather than raise
- The warning re-emits from `parser_for`'s frame, so the location reported is the caller's own call — 2026-08 #337, the warning exists because
- The message offers code that type-checks, `Policy(segment_scripts=frozenset())`, pinned by a test, with the bare tuple literal in the denylist test — 2026-08-07 #339.
- `python -m nameparser --locale ja` attaches `ja_segmenter()` when the extra is installed and warns as the library does when it is not; `parser_for(locales.JA)` stays explicit — 2026-10-31, the CLI attaches the installed segmenter

Open: none in this file.

## Log

- 2026-08 #337 — WARN rather than raise, deliberately: registering the JA pack without the extra must stay safe (the inert registration is itself a pinned property), and a warning is filterable by the caller who wants exactly that inertness. The Japanese install hint is conditional — it appears only when a Japanese script is among the dead scripts; a hangul-only gap gets the generic remedies.
- 2026-08 #337 — the warning exists because parser_for(locales.JA) without segmenter= used to build a parser that silently behaved like a working one minus the feature; it re-emits from the parser_for frame so the reported location is the caller's own call.
- 2026-08-07 #339 — diagnostics that hand the reader code must hand code that type-checks: the message's offered deactivation used a bare tuple literal for segment_scripts — an arg-type error under mypy in a py.typed package — and became frozenset(), pinned by a test asserting the offered spelling. The known-bad spelling is in the denylist test. The structural fact behind the recurrence: autodoc renders docstrings into the API reference, so docs/*.rst is NOT the boundary of "the docs" — a guide and the reference can teach different spellings on the same rendered page, invisibly to any .rst-only sweep.
- 2026-10-31 — the CLI attaches the installed segmenter: `python -m nameparser --locale ja` calls `locales.ja_segmenter()` and passes it to `parser_for`, falling back to the segmenterless parser, and so to this warning, when the factory raises `ImportError`. The CLI is a debug tool with no other way to attach one, and its reading may depend on the environment it runs in. **Declined:** doing the same in `parser_for(locales.JA)`, because the same code would parse `高橋一郎` differently with and without the extra installed, a pickled `Parser` would carry the third-party segmenter, and the pack-and-segmenter pairing is explicit by design (`locales/ja.py`'s docstring); the inert registration this file's first entry pins stays the library's behavior.
