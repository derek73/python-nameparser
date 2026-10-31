# Parsing rules

This document is NORMATIVE, not descriptive: the rules state how names are written and what should happen when they are parsed, grounded in how people understand names — not in what the parser currently does. The parser implements these rules. Where it does not yet, the gap is a tracked deviation (`deviates:` marker below), not a counterexample. Statements are implementation-free: no stage names, no function names, no regexes.

Authority, scoped: `tests/v2/cases.py` pins CURRENT behavior; this document states INTENDED behavior. A mismatch between them must be classified, never defaulted: either the rule is wrong (fix it here) or the parser is wrong (the example takes a `deviates:` marker and an issue). Where this document is silent, the behavior is pinned-but-undocumented — an extraction gap to close, not a specification, and not license to change the behavior.

Rule IDs are stable forever: never renumbered, never reused. A retired rule's file leaves this folder, and its decisions file records the retirement on a line of its own opening `Retired:` (decisions/README.md); `tests/v2/test_design_docs.py::test_no_rule_reuses_a_retired_id` refuses a rule file carrying an ID a decisions file records that way. Cross-references use the form `decisions/P2` / `mechanisms.md#SPANS`; a bare ID is never a citation. The citation-integrity test checks that every rule ID written in a rule's quotable prose (every field, below) exists — not that the two rules really meet, and not which of them wins, which a Precedence bullet states. `implemented:` and `tracked:` are checked too: every rule carries exactly one. `implemented:` names the modules honoring the rule, checked against the modules that cite it; `tracked:` names the issues that would ship a rule nothing implements yet, so a wholly-aspirational rule cannot sit here untracked, and a shipped rule cannot keep a stale tracking pointer.

## The skeleton

Every rule is written in the skeleton format (#761). The block format the rules were first written in — a rule opening `ID. Rationale:`, its statement indented four spaces, its examples six, its pointer line naming `interacts:` — is retired, and the parser refuses a rule written in it rather than skip it.

A rule records an agreement about one situation: when this is in the written name, it means this and is handled this way, because of this — and handling it that way means accepting these other readings. The skeleton writes it in that order, so the head reads aloud as one sentence (When, Then, Because), each place the head stops being true is a bullet of its own carrying its own example, and the technical alignment sits in a footer. A rule file opens with its heading, `# ID — name`, and the rule runs to the next markdown heading (a `#` run and a space, so a prose line opening `#761` is not one); it holds these fields, each a bold label at the start of a line, in this order, each at most once:

- `**When:**` (required) — the situation in the written name, with one quoted example where the rule reads a name.
- `**Tolerated:**` — a tolerated rule's reason (see the tolerated rule below), standing right after When.
- `**Then:**` (required) — what results, including what the writing means where the rule interprets it. It is ONE paragraph of ONE sentence. Detail of the result — how far it reaches under each order, a hub's map — goes in a `- ` bullet list directly under it.
- `**Because:**` (required) — why, in three sentences at most.
- `**Except:**` — one bullet per place where Then stops being true, opening with a bold lead, each carrying its own fenced example: an exception without its case is a clause nobody can check. This is where the `· boundary` examples usually stand. An input outside When is no exception, even one marking the rule's boundary: it goes in the rule's main fence with its `· boundary` marker, and the sentence it proves goes where its claim belongs, in Then or Accepted.
- `**Precedence:**` — one bullet per contested input: the input, the rule that wins it, and why. Naming a rule anywhere else says only that the two meet; this says which wins.
- `**Accepted:**` — one bullet per reading taken as the rule's cost, with an example where an input string can show it.

A field that does not apply is left out, never filled for the sake of the shape. When, Tolerated, Then and Because hold prose: the text starts on the label line and is not hard-wrapped (root AGENTS.md, "Markdown line width"), and When, Tolerated and Then are one paragraph each. Except, Precedence and Accepted hold only a bullet list, nothing on the label line. A bullet is `- ` and its text at the start of a line (a `* ` or `+ ` marker, a numbered item, a hyphen glued to its text, or a bullet with no text is refused); it continues on lines indented two spaces, and a fence indented two spaces under it holds that bullet's examples. A fence at the start of a line holds examples for the rule as a whole, usually right after Because. A fence is a bare ``` line, no language tag (a ``` line carrying one, or a `~~~` fence, is refused), and holds at least one example. Every non-blank line inside a fence is an example line in the grammar below, and an example line anywhere outside a fence is refused rather than read as prose: a line, the text on a label's line or a bullet's text that opens with a quote or a bracket, or any line holding an arrow and an assertion (` →  family=`, quoted or not) outside a backtick span. So no prose may open with a quote or a bracket, and prose writing about the grammar puts an assertion in backticks. A nested list, or a heading, inside a bullet is not part of the grammar. Precedence and Accepted bullets may carry examples and need not; the rule as a whole still needs a `· boundary` example or a `no-boundary:` waiver.

A line holding exactly `---` ends the fields. Below it stand only the `**Signal:**` line, the pointer line directly under Signal with no blank line between — `**history:** decisions/<ID> · **implemented:** <path>, <path>`, or `**tracked:** #N` in place of `implemented:`, every part one of those keys with a value and none repeated — and an optional `no-boundary: <reason>` waiver, which may stand above the Signal line or below the pointer line. A Signal or `no-boundary:` line above the `---`, in any spelling, is refused: read as prose, it would leave the rule's signal or waiver unset.

What a citation may quote is every field's prose, bold markers stripped: When, Tolerated, Then and its bullets, Because, and the Except, Precedence and Accepted bullets — never a fence or the footer. Sentences are counted with quoted text and backtick spans removed, `e.g.` and `i.e.` ending none, a sentence ending at `.`, `?` or `!` followed by a space and a capital, except a period after an initial (`V. Smith`) or after Dr, Mr, Mrs, Ms, St, Prof, Jr or Sr. The count misses a sentence that opens with anything but a capital, or that ends in an initial or one of those abbreviations. The parser refuses, naming the rule and the line: a label spelled any other way than `**Label:**` (`When:`, `**When**:`), an unknown label, a field out of order or repeated, a missing or empty When, Then or Because, an empty Tolerated, a fence with a language tag or a `~~~` fence, an example line outside a fence (or any line, label text or bullet text there opening with a quote or a bracket, or holding an arrow and an assertion outside a backtick span), a When, Tolerated or Then of more than one paragraph, a Then of more than one sentence, a Because of more than three sentences, a malformed or empty bullet, a nested list (in any marker, `- `, `* `, `+ ` or a number) or a heading in a bullet's continuation lines, an Except, Precedence or Accepted label with no bullets under it, an Except bullet with no example, an empty fence, an unclosed fence, a line outside any field, a Signal or `no-boundary:` line above the `---`, `interacts:` or any unknown or repeated part on the pointer line, and below the `---` anything but those three lines. Outside a rule, only a section file's `## Name (X)` heading, each letter once, and its one `Background:` paragraph may stand, and anything else is refused: a subheading in a rule file, a fence in a section file, and either one glued to a Background paragraph, which may wrap onto further lines of prose but not onto a line opening, at its start, with a fence, a heading, a field label or a list item (of numbered items only one numbered 1, which is all CommonMark lets interrupt a paragraph). An example in a Background, glued or on its first line, is refused as anywhere outside a fence, and so is a section heading with no Background. A rule in the retired block format is refused too: a line opening `ID. ` at the start of a line, wherever it stands, inside a field included.

D2, as a skeleton:

````markdown
# D2 — construction raises, parse never does

**When:** a configuration is built from a value it cannot accept.

**Then:** configuration validation raises at construction with the offending field and value named.

- **A locale pack names itself:** applying a locale pack wraps any such error with the locale's code, so a stacked configuration names which layer broke.

**Because:** whatever a name contains, parsing answers. Only a broken configuration may raise, and it must name the field.

```
[bad-name-order]  →  raises="name_order elements must be Role members"
[bad-order-none]  →  raises="name_order must be an iterable"
```

---
no-boundary: the non-raising side is every other rule's examples; parse() itself is total (A1).
**Signal:** none in the name: the configuration's values, at construction
**history:** decisions/D2 · **implemented:** nameparser/_policy.py, nameparser/_parser.py
````

D2 has no exception. The bullet fields look like this, drawn from S10's examples:

````markdown
**Except:**

- **One letter needs a word to spare**, as a bare ambiguous acronym does (S4): as the second of two name words it is the family name.
  ```
  "John V"  →  family="V"  · boundary
  ```

**Precedence:**

- **Before a suffix comma** ("John Smith V, PhD"): the part before the comma reads as the same name written without it (C1).

**Accepted:**

- A one-letter numeral with a credential behind it is the family name, and the reading is reported.
  ```
  "John Smith V PhD"  →  family="V"
  ```
````

`tests/v2/rules_skeleton.py` is the format's executable definition, and `tests/v2/test_rules_skeleton.py` holds its refusals.

## Examples, signals and size

Every example line is EXECUTABLE. The grammar (its executable definition is `tests/v2/rules_doc.py`, which `tests/v2/rules_skeleton.py` asks for each line in a rule's fences; `tests/v2/test_rules_doc.py` runs every line):

    "INPUT" [annotation] →  field="value"  [· boundary]
                            [deviates: #N (today: field="value")]

An `annotation` names a policy, a policy with a lexicon fragment beside it (`two_family_names+es_given_names`, for a rule reading a field the default lexicon leaves empty), a locale (`[ru]`), or an extras gate (`[ja+segmenter]`) in the registry beside the test. `· boundary` marks the non-firing example every rule must carry: an input shaped like the rule's subject where its effect does NOT occur. That is usually the rule's OWN stated exception — H1's given-name title, P3's single-letter carve-out — not an input the rule never reaches, so the exception is executable rather than merely asserted. Or the rule declares `no-boundary: <reason>` instead, so skipping the boundary is a recorded decision. `deviates:` states the INTENDED output on the example line while the marker records TODAY's output and the tracking issue; the runner asserts today's output strictly, so a parser change that closes the gap fails the suite until the marker is removed in the same PR. `grep -r deviates: docs/design/rules/` is the deviation backlog (deviations from statable rules — coverage gaps are a separate, larger category no grep can see, and contested vocabulary memberships a third, tracked as Open blocks keyed to the vocabulary set in decisions/).

Every rule also states its signal — what in the written name it reads, for example a count, a case contrast, a shape, a neighbor, a position or a script, or `none in the name: <what it reads instead>` for a rule that reads configuration or the parsed words. A rule writes it in the footer as a tag, `**Signal:** shape`, optionally followed by a colon and a short description (`**Signal:** none in the name: the configuration's values, at construction`), since its When already describes the situation. The tags the rules use are shape, count, case contrast, position, neighbor, script, comma, edge full stop, character, separator and none in the name. Two kinds of rule carry none of them: A1 and C11, reading only the calls other rules make, write `none of its own`, and C7, which orders other rules' reads, writes `a sequence, not a signal of its own`. The line is one line, never wrapped, standing directly above the rule's pointer line, and the parser refuses one anywhere else, since a continuation line would be read as prose. It is metadata, not statement: a citation cannot quote it. A hub — a decision weighing several signals, each stated by a rule of its own — ends its line `hub of C3, C4, …`, after any signal it reads itself (`**Signal:** <its own>; hub of C3, C4`), and the doc tests hold the rules a hub names to its map, both ways. The map is the bullet list under Then: every rule the hub names is named by some bullet, every rule a bullet names is on the hub's list, and every bullet names at least one, so one bullet may name several. A line naming two signals joins them with ` + `: that rule is a split candidate under docs/design/AGENTS.md's one rule per piece of evidence, and `grep -lE '^\*\*Signal:\*\*.* \+ ' docs/design/rules/*.md` lists them. A condition the rule cites to the rule stating it stays off the line — S10 cites T4 for the lower-case numeral that is no initial — and a gate on the name's size (exactly three name words, a word to spare, as S10's one-letter numeral needs) is part of the signal it gates rather than a second one.

Each rule's size is recorded, as a guard rather than a cap (mechanisms.md#RECORDED-ROSTERS). `tests/v2/rules_budget.json` holds each rule's measures, read from its fields: the words of every quotable field but the Accepted bullets (When, Tolerated, Then and its bullets, Because, Except and Precedence), Then's words with its bullets, Because's sentences, the count of Except, Precedence and Accepted bullets, and the Accepted bullets' words. `tests/v2/test_rules_budget.py` fails when a rule moves against its record, shrinking included, so the record follows a rule down. A rule that has to grow re-records with `uv run python -m tests.v2.rules_budget --record`, and the PR says so: the record's diff is where a reviewer sees the growth and asks what the new words read. Only the skeleton's two sentence limits are caps.

One class of rule stands outside the normative reading and declares it, in a `**Tolerated:**` field right after When. Such a rule covers input that no writing convention produces. W3 is the case: its subject is Chinese, Japanese and Korean names, and none of those writing systems puts a comma between the family name and the given name, so `김, 민준` is a shape nobody writes. The parser accepts any string, so it still has to read such input somehow; the rule describes what it does with it, best-effort, instead of promising it. Its statement is still precedence-bearing and its examples are still executable and still run, but they illustrate rather than promise, and the behavior is changeable without notice. W3 is the only such rule today (the 2026-09-01 comma demotion).

The marker's unit is the whole rule, so a clause that reaches past the tolerated shape does not belong in a marked rule — say it in a normative one. The marker changes what the rule promises, not what is watched: a marked rule's examples are in `tools/differential/corpus_rules.jsonl` like any other, so the snapshot shows when their reading moves (#664).

## Glossary

Terms the rules use without defining them each time, each with the rule that defines or counts it.

- **name word** — a word of the person's name itself: titles, suffixes, nicknames and particles acting as particles are not name words (R3). How name words are COUNTED is each rule's own, and there is no single count: C3, counting the words before a comma, takes a particle run and the one name word it attaches to as one word (P1's reach, not P2's whole chain) and counts a connective join and a bound given-name pair as their words; S8 counts P2's whole chain as one name word; P1's family-first fold takes one unit, a particle chain (P2), a conjunction join (P3) or a bound given-name pair (P5) whole; O6 counts a family's words by P1's reach, a connective join and a hyphenated word counting as their words.
- **words to spare** — enough name words that reading one as a suffix still leaves the name its family word. As the second of two name words a bare ambiguous acronym has none to spare and stays the family name (S4); S10's one-letter numeral needs the same.
- **credential run** — a run of words read as post-nominals: a comma part made wholly of suffix words (C1, C8), or the run an unambiguous credential starts after the name core, taking every later word of its part (S8).
- **listing form** — the family name, a comma, then the given name, as in "Smith, John" (C1).
- **the fold** — P1's: a never-given particle opening the name claims the family for itself, the particles after it and the name words it attaches to (P1). O3's fold, which joins every middle word to the family under compound-family handling, is a different one; R1's folded family words, which render before the rest of the family, are O3's folded middle words and the trailing particle P6 attaches (its tussenvoegsel).

## Not in scope

- **Language detection.** The parser never infers a language from Latin-script text: transliteration destroys the signal ("Ali",
  "Van", "Bin" each belong to several languages with conflicting
  readings). Language-specific behavior is opt-in configuration. Script-conditional behavior exists only where the script itself settles the convention (see the W section).
- **Grammatical inflection.** Names inflect in many languages (vocative, genitive); this library neither produces nor consumes inflected forms. CLDR personNames draws the same line.
- **Validation.** Deciding whether a string IS a person's name is not parsing; `parse()` is total over strings and never rejects input.
- **Vocabulary completeness.** No shipped wordlist parses every name, and none is meant to. The promise is that every TYPE of vocabulary has a mechanism — markers, particles, titles, suffixes, bound given names — and that callers configure the members their data needs. A missing entry is a configuration answer, not a defect, and what the tests owe is one exercise per behavioral fork rather than one per entry (mechanisms.md#VOCABULARY-EXERCISES-FORKS).
- **Comparison.** matches()/comparison_key() are a value-API surface, not parsing; their design record is decisions/comparison-surface.

## Index

## [Titles & honorifics (H)](H-titles-and-honorifics.md)

- [H1 — a title and one name word](H1-title-and-one-name-word.md)
- [H2 — the leading-abbreviation title](H2-leading-abbreviation-title.md)
- [H3 — the title run's floor](H3-title-runs-floor.md)
- [H4 — an input that is nothing but vocabulary still has to name somebody](H4-input-that-is-nothing-but-vocabulary-still-has-to-name-somebody.md)
- [H5 — the trailing title run](H5-trailing-title-run.md)
- [H6 — a title before a family comma](H6-title-before-a-family-comma.md)
- [H7 — a joined name unit carrying title vocabulary](H7-joined-name-unit-carrying-title-vocabulary.md)
- [H8 — a salutation ending the given part](H8-salutation-ending-the-given-part.md)
- [H9 — the title phrase](H9-title-phrase.md)

## [Particles & surname prefixes (P)](P-particles-and-surname-prefixes.md)

- [P1 — lone particle fold](P1-lone-particle-fold.md)
- [P2 — particles join forward](P2-particles-join-forward.md)
- [P3 — connectives](P3-connectives.md)
- [P4 — a particle at the front of the name](P4-particle-at-the-front-of-the-name.md)
- [P5 — bound given names](P5-bound-given-names.md)
- [P6 — the trailing orphan particle](P6-trailing-orphan-particle.md)
- [P7 — a one-letter particle against the initial it spells](P7-one-letter-particle-against-the-initial-it-spells.md)
- [P8 — a single-letter connective against the initial it spells](P8-single-letter-connective-against-the-initial-it-spells.md)
- [P9 — a particle that is also a suffix word, beside a family comma](P9-particle-that-is-also-a-suffix-word-beside-a-family-comma.md)

## [Suffixes: generational & credentials (S)](S-suffixes-generational-and-credentials.md)

- [S1 — a bracketed credential is not a nickname](S1-bracketed-credential-is-not-a-nickname.md)
- [S2 — a suffix word ends a name and never opens the string](S2-suffix-word-ends-a-name-and-never-opens-the-string.md)
- [S3 — credentials written in joined chunks](S3-credentials-written-in-joined-chunks.md)
- [S4 — the ambiguous acronym needs words to spare](S4-ambiguous-acronym-needs-words-to-spare.md)
- [S5 — the given part's trailing slot after a family comma](S5-given-parts-trailing-slot-after-a-family-comma.md)
- [S6 — the case signal at the suffix slot](S6-case-signal-at-the-suffix-slot.md)
- [S7 — the company of an unambiguous credential](S7-company-of-an-unambiguous-credential.md)
- [S8 — the credential's trailing run](S8-credentials-trailing-run.md)
- [S9 — unlisted words that join the ambiguous class by shape](S9-unlisted-words-that-join-the-ambiguous-class-by-shape.md)
- [S10 — the trailing roman numeral](S10-trailing-roman-numeral.md)
- [S12 — a credential split across a space](S12-credential-split-across-a-space.md)
- [S11 — a suffix word that is also a name](S11-suffix-word-that-is-also-a-name.md)
- [S13 — a bracketed member settled by its writing](S13-bracketed-member-settled-by-its-writing.md)

## [Nicknames & quoted names (N)](N-nicknames-and-quoted-names.md)

- [N1 — the default delimiter pairs](N1-default-delimiter-pairs.md)
- [N2 — same-character quotes and shared-character conventions](N2-same-character-quotes-and-shared-character-conventions.md)
- [N3 — the lone-word nickname rule](N3-lone-word-nickname-rule.md)

## [Maiden names (M)](M-maiden-names.md)

- [M1 — delimited maiden names](M1-delimited-maiden-names.md)
- [M2 — the maiden-marker rule](M2-maiden-marker-rule.md)
- [M3 — the marker-led clause](M3-marker-led-clause.md)
- [M4 — a maiden marker makes the lone name word the family](M4-maiden-marker-makes-the-lone-name-word-the-family.md)

## [Commas & structure (C)](C-commas-and-structure.md)

- [C1 — the suffix-comma decision](C1-suffix-comma-decision.md)
- [C2 — parts past the second comma](C2-parts-past-the-second-comma.md)
- [C3 — counting the words before the comma](C3-counting-the-words-before-the-comma.md)
- [C4 — the ambiguous credential class at the comma](C4-ambiguous-credential-class-at-the-comma.md)
- [C5 — paired initials after the comma](C5-paired-initials-after-the-comma.md)
- [C6 — an unlisted all-caps word needs the name's case contrast](C6-unlisted-all-caps-word-needs-the-names-case-contrast.md)
- [C7 — a postnominal part is read before any join](C7-postnominal-part-is-read-before-any-join.md)
- [C8 — the listing form's part after the comma](C8-listing-forms-part-after-the-comma.md)
- [C9 — a one-character suffix word inside a comma part](C9-one-character-suffix-word-inside-a-comma-part.md)
- [C10 — a suffix delimiter parts a suffix run](C10-suffix-delimiter-parts-a-suffix-run.md)
- [C11 — what the comma decision reports](C11-what-the-comma-decision-reports.md)
- [C12 — a suffix word ending the name before the comma](C12-suffix-word-ending-the-name-before-the-comma.md)
- [C13 — a credential opening the part after the comma](C13-credential-opening-the-part-after-the-comma.md)
- [C14 — strict mode: a suffix word written as an initial](C14-strict-mode-a-suffix-word-written-as-an-initial.md)
- [C15 — a comma with nothing before it](C15-comma-with-nothing-before-it.md)

## [Name order (O)](O-name-order.md)

- [O1 — East Slavic rotation](O1-east-slavic-rotation.md)
- [O2 — Turkic rotation](O2-turkic-rotation.md)
- [O3 — compound family names written unmarked](O3-compound-family-names-written-unmarked.md)
- [O4 — positional assignment and declared order](O4-positional-assignment-and-declared-order.md)
- [O5 — the lone name word's convention, and reporting it](O5-lone-name-words-convention-and-reporting-it.md)
- [O6 — two family names](O6-two-family-names.md)
- [O7 — two given names](O7-two-given-names.md)

## [Scripts & writing systems (W)](W-scripts-and-writing-systems.md)

- [W1 — unspaced CJK division](W1-unspaced-cjk-division.md)
- [W2 — the glued-honorific peel](W2-glued-honorific-peel.md)
- [W3 — the writer's divisions are respected](W3-writers-divisions-are-respected.md)
- [W4 — script-scoped order](W4-script-scoped-order.md)

## [Tokens, initials & punctuation (T)](T-tokens-initials-and-punctuation.md)

- [T1 — separators, not joiners](T1-separators-not-joiners.md)
- [T2 — the katakana middle dot divides like a space](T2-katakana-middle-dot-divides-like-a-space.md)
- [T3 — the interpunct's flank guard](T3-interpuncts-flank-guard.md)
- [T4 — the bare letter as an initial](T4-bare-letter-as-an-initial.md)
- [T5 — the written shape of an initial](T5-written-shape-of-an-initial.md)

## [Ambiguity & tie-breaking (A)](A-ambiguity-and-tie-breaking.md)

- [A1 — the ambiguity report](A1-ambiguity-report.md)
- [A2 — the empty name](A2-empty-name.md)

## [Rendering & views (R)](R-rendering-and-views.md)

- [R1 — fields are views of the parsed words](R1-fields-are-views-of-the-parsed-words.md)
- [R2 — the all-particles family_base divergence](R2-all-particles-family-base-divergence.md)
- [R3 — initials honor the fold](R3-initials-honor-the-fold.md)
- [R4 — case repair reads the unjoined mark](R4-case-repair-reads-the-unjoined-mark.md)
- [R5 — the case-repair gate](R5-case-repair-gate.md)
- [R6 — the default rendering follows the written name](R6-default-rendering-follows-the-written-name.md)
- [R7 — no initials in a script that writes none](R7-no-initials-in-a-script-that-writes-none.md)
- [R8 — the generation and credentials views](R8-generation-and-credentials-views.md)
- [R9 — the patronymic view](R9-patronymic-view.md)
- [R10 — the second-surname view](R10-second-surname-view.md)

## [Construction & configuration diagnostics (D)](D-construction-and-configuration-diagnostics.md)

- [D1 — the segmenterless-activation warning](D1-segmenterless-activation-warning.md)
- [D2 — construction raises, parse never does](D2-construction-raises-parse-never-does.md)
