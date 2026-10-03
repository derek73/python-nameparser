# Writing the user docs (docs/*.rst)

This file covers the Sphinx user documentation: `usage.rst`, `customize.rst`, `locales.rst`, `migrate.rst`, `concepts.rst` and the rest of `docs/*.rst`. `docs/design/` is not user documentation and has its own `docs/design/AGENTS.md`; the mechanics of doctests (shared namespace, optional extras, which doctest runner to trust) are in the root `AGENTS.md` under Gotchas → Doctests, and are not repeated here.

The rules below were distilled from PR #588, which restructured `customize.rst` after its Policy table rows had grown to 25–35 lines each. Every rule names the failure it prevents, because each of those failures happened.

## Structure

**A table is an index.** A row states what the field does and its default, in a sentence or two, and links to a section with `:ref:`. Detail, boundary cases and examples go in the section. A row past about five lines is the signal that it has stopped being an index. Rows grow by accretion — each fix adds its boundary case where the field is already described — so when you have a new case to document, add it to the section, never to the row. `customize.rst`'s Policy table is the model: its longer-reaching fields (`name_order`, the delimiters, the `unlisted_*` pair) are short rows that link to sections, while a field that needs no more than its row (`middle_as_family`) has no section at all.

**One topic per paragraph; subheadings for a section with several.** A paragraph that answers more than one question gets split, and a section holding more than one task gets subheadings named for what the reader came to do ("Routing a pair to maiden names", "Teaching the splitter a surname"), not for the mechanism. Keep an existing section title when you add subheadings under it: other pages link to titles (`` `Words that are also ordinary names`_ ``), and renaming breaks them.

**List shape follows content shape.** Rules applied in order — where a later rule is reached only when an earlier one declined — are a numbered list, and prose that says "in steps" or "first … then" is a numbered list waiting to happen. Parallel options (three settings, three choices with their costs) are a bulleted list with a bold lead per item. Running prose is for an argument, not for an enumeration.

**Put background before behavior.** A section on a domain the reader may not know (East Asian naming, patronymics, post-nominals) opens with how that domain works — enough to make the rules derivable — then says what the library does automatically, then where automation stops and what the user does about it. Name the mechanism plainly ("assigned family-first", "split off the end of the token"), never gesture at it ("comes out right", "goes a step further").

**Place a note beside what it explains.** Adding subheadings moves the boundaries a block appears to belong to: a `.. note::` that closed a section reads as the last subsection's own once that section has subheadings. Move it next to the example it explains.

**Heading levels on a page run `=`, `-`, `~`, `^`, `"`.** Sphinx assigns levels by the order each underline character first appears in the file, so use them in that order. Five levels is the useful limit — the fifth renders as `<h5>` and only works for short headings; past that, promote the parent section instead of nesting further.

## Examples

**A recipe is a doctest; an edge case is a unit test.** A *recipe* — how to do the thing the reader came to do — belongs in the docs as a `.. doctest::` block, which teaches and is CI-checked at once. An example that only *pins* edge-case behavior teaches nothing and costs maintenance; state the behavior in one sentence and pin it in a unit test. An example sitting as prose inside a table cell is the worst of both: it teaches from the wrong place and nothing checks it.

**An example must be non-vacuous.** Show the baseline before the customization, and check that they differ: an `add(titles={"chancellor"})` example once shipped where `chancellor` was already a default title, so the add was a no-op and the doctest passed demonstrating nothing. Prefer a word absent from the defaults for a teachable reason (`dean`, which is also a given name).

**An example must run warning-free.** Readers paste examples, so a warning the doctest build prints is one every reader gets. Fix the example, not the build: a `Lexicon.empty()` used only to drop titles also dropped the Korean surnames and drew the segmenterless warning, and the fix was an example that empties only the field it is about. Run `uv run sphinx-build -q -b doctest docs <tmp>` and expect no output at all.

**Give doctest variables distinctive names** (`cred`, `caps_off`, `name_jr`), never `name`, `lex` or `policy` in a new block unless you mean to reuse the binding above — all blocks on a page share one namespace (root `AGENTS.md`, Gotchas → Doctests).

## Claims

**Measure every claim before you move it.** Restructuring is rewriting, and rewriting a claim is making one. Run each example and each stated behavior against the tree before the prose moves, not after. Combining sentences is where claims break: two rows each true of their own field become one intro that sounds true of both. #588's first draft did this twice — "the fork is reported either way" was true of dotted acronyms and false of all-caps words (`Smith, XYZ` reports nothing), and a comparison to the listed acronym `MA` was wrong (`Jack MA` is a suffix, `Jack X.Y.Z.` is not).

**Check a claim end to end, through the call the reader makes.** "One `phd` key covers `Phd`" was true of the key match and false of `capitalized()`'s output, which leaves mixed case alone unless `force=True`. Verify against what the reader would observe, not an intermediate step.

**A claim about code needs the code.** "An empty `honorific_tails` stops the peel at its first guard" is checked by reading the guard, not by parsing a name.

## Linking

**Link, don't restate.** When another page already covers a topic, give one line and a `:ref:` to it; two copies drift apart. When the content is a list the code ships (the maiden markers, the delimiter pairs), link the module with `:mod:` instead of copying the list into prose, where it goes stale the next time the list changes.

**Put a label at the heading you link to**, and link with `:ref:` to the section rather than `:doc:` to the page, which lands the reader at the top of a long page. Add the label in the same commit as the first link to it.

## Verifying

Before committing a docs change, run both builds and read their output — not just their exit codes:

```bash
uv run sphinx-build -q -b doctest docs /tmp/doctest
uv run sphinx-build -q -b html docs /tmp/html
```

Both should print nothing. The HTML build reports an unresolved `:ref:` as a warning there, which is how a renamed heading or a missing label shows up.
