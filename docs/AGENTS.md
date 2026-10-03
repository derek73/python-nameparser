# Writing the user docs (docs/*.rst)

This file covers the Sphinx user documentation: `usage.rst`, `customize.rst`, `locales.rst`, `migrate.rst`, `concepts.rst` and the rest of `docs/*.rst`. `docs/design/` is not user documentation and has its own `docs/design/AGENTS.md`; the mechanics of doctests (shared namespace, optional extras, which doctest runner to trust) are in the root `AGENTS.md` under Gotchas → Doctests, and are not repeated here.

The rules below were distilled from PR #588, which restructured `customize.rst` after three of its Policy table rows had grown to 24–38 source lines each (measured on master, 2026-10-02), and from the review rounds on that PR. Two rules carry lessons from earlier docs work, cited where they appear. Every rule names the failure it prevents, because each of those failures happened.

## Structure

**A table is an index.** A row states what the field does and its default, in a sentence or two, and links to a section with `:ref:`. Detail, boundary cases and examples go in the section. A description cell past about five lines is the signal that the row has stopped being an index. Rows grow by accretion — each fix adds its boundary case where the field is already described — so when you have a new case to document, add it to the section, never to the row. `customize.rst`'s Policy table is the model: every row whose field has a section links to it, and a field that needs no more than its row (`middle_as_family`) has no section at all. A row that has a section and does not link to it is a dead end — #588's first pass left five.

**One topic per paragraph; subheadings for a section with several.** A paragraph that answers more than one question gets split, and a section holding more than one task gets subheadings named for what the reader came to do ("Routing a pair to maiden names", "Teaching the splitter a surname"), not for the mechanism. Keep an existing section title when you add subheadings under it: other pages link to titles (`` `Words that are also ordinary names`_ ``), and renaming breaks them.

**List shape follows content shape.** Rules applied in order — where a later rule is reached only when an earlier one declined — are a numbered list, and prose that says "in steps" or "first … then" is a numbered list waiting to happen. Parallel options (three settings, three choices with their costs) are a bulleted list with a bold lead per item. Running prose is for an argument, not for an enumeration.

**Put background before behavior.** A section on a domain the reader may not know (East Asian naming, patronymics, post-nominals) opens with how that domain works — enough to make the rules derivable — then says what the library does automatically, then where automation stops and what the user does about it. Name the mechanism plainly ("assigned family-first", "split off the end of the token"), never gesture at it ("comes out right", "goes a step further").

**Place a note beside what it explains.** Adding subheadings moves the boundaries a block appears to belong to: a `.. note::` that closed a section reads as the last subsection's own once that section has subheadings. Move it next to the example it explains.

**Heading levels on a page run `=`, `-`, `~`, `^`, `"`.** Sphinx assigns levels by the order each underline character first appears in the file, so use them in that order. Five levels is the useful limit — the fifth renders as `<h5>` and only works for short headings; past that, promote the parent section instead of nesting further.

## Examples

**A recipe is a doctest; an edge case is a unit test.** A *recipe* — how to do the thing the reader came to do — belongs in the docs as a `.. doctest::` block, which teaches and is CI-checked at once. The line between the two is whether the prose states the behavior: a claim the section makes to the reader (`edd` repairs to `EDD`, not a mask) earns a doctest beside it, which is what keeps the claim true; an edge case the prose has no reason to mention earns one sentence at most and a unit test, never a doctest (PR #216). An example sitting as prose inside a table cell is the worst of both: it teaches from the wrong place and nothing checks it.

**An example must be non-vacuous.** Show the baseline before the customization, and check that they differ: an `add(titles={"chancellor"})` example once shipped (fixed in 0ab19fdb) where `chancellor` was already a default title, so the add was a no-op and the doctest passed demonstrating nothing. Prefer a word absent from the defaults for a teachable reason (`dean`, which is also a given name).

**An example must run warning-free.** Readers paste examples, so a warning the doctest build prints is one every reader gets. Fix the example, not the build: a `Lexicon.empty()` used only to drop titles also dropped the Korean surnames and drew the segmenterless warning, and the fix was an example that empties only the field it is about. Run the doctest build under Verifying below and expect no output at all.

**Spell examples so they type-check.** nameparser ships `py.typed`, so readers' examples run under mypy: write `()` and `frozenset()` rather than `{}` and bare set literals for `Policy` fields (the root `AGENTS.md`'s validation bullet covers the same rule for messages).

**Give doctest variables distinctive names** (`cred`, `caps_off`, `name_jr`), never `name`, `lex` or `policy` in a new block unless you mean to reuse the binding above — all blocks on a page share one namespace (root `AGENTS.md`, Gotchas → Doctests).

## Claims

**Measure every claim before you move it.** Restructuring is rewriting, and rewriting a claim is making one. Run each example and each stated behavior against the tree before the prose moves, not after. Combining sentences is where claims break: two rows each true of their own field become one intro that sounds true of both. #588's first draft did this twice — "the fork is reported either way" sounded true of both fields and was false of all-caps words (`Smith, XYZ` reports nothing), and a comparison to the listed acronym `MA` was wrong (`Jack MA` is a suffix, `Jack X.Y.Z.` is not). It was not even true of the dotted field it came from: a review found `John Smith, X.Y.Z.` takes the credential silently. Narrowing is the usual repair ("whatever pair encloses it" became "any configured pair": square brackets are not a default pair).

**Splitting breaks claims too.** Moving a sentence under one subheading makes it read as that subsection's alone. The rule for when the two-letter initials exception gives way landed under "Dotted acronyms" and stopped covering capitals, which it does (`John Smith, PhD MJ`).

**Check that nothing was dropped.** After a restructuring, list the distinct facts in each old passage (`git show master:docs/<file>`) and find each one in the new text — moved, reworded with the same meaning, or deliberately cut and said so in the commit. #588's review found version notes ("since 2.4") and two examples lost in the move.

**Check a claim end to end, through the call the reader makes.** "One `phd` key covers `Phd`" was true of the key match and false of `capitalized()`'s output, which leaves mixed case alone unless `force=True`. Verify against what the reader would observe, not an intermediate step.

**A claim about code needs the code.** "An empty `honorific_tails` stops the peel at its first guard" is checked by reading the guard, not by parsing a name. Find it through the stage headers: each stage module (the eight in `nameparser/_pipeline/__init__.py`'s `STAGES`) declares the `Policy`/`Lexicon` fields it reads on a `Reads:` line. The shared helpers `_vocab.py` and `_pieces.py` have no such line and read the lexicon too, so grep them as well.

## Linking

**Link, don't restate.** When another page already covers a topic, give one line and a `:ref:` to it; two copies drift apart. When the content is a list the code ships (the maiden markers, the delimiter pairs), link the module with `:mod:` instead of copying the list into prose, where it goes stale the next time the list changes.

**Put a label at the heading you link to**, and link with `:ref:` to the section rather than `:doc:` to the page, which lands the reader at the top of a long page. Add the label in the same commit as the first link to it.

## Verifying

Before committing a docs change, run both builds and read their output — not just their exit codes:

```bash
uv run sphinx-build -q -b doctest docs /tmp/doctest
uv run sphinx-build -q -b html docs /tmp/html
```

Both should print nothing. The HTML build prints an unresolved `:ref:` or an unknown title link (`` `Some heading`_ ``) as a WARNING and still exits 0, and CI's HTML step has no `-W`, so CI will not catch it either — reading the output is the only check. A doctest that emits a warning likewise prints and passes.
