# Parsing rules

This document is NORMATIVE, not descriptive: the rules state how
names are written and what should happen when they are parsed,
grounded in how people understand names — not in what the parser
currently does. The parser implements these rules. Where it does not
yet, the gap is a tracked deviation (`deviates:` marker below), not a
counterexample. Statements are implementation-free: no stage names,
no function names, no regexes.

Authority, scoped: `tests/v2/cases.py` pins CURRENT behavior; this
document states INTENDED behavior. A mismatch between them must be
classified, never defaulted: either the rule is wrong (fix it here)
or the parser is wrong (the example takes a `deviates:` marker and an
issue). Where this document is silent, the behavior is
pinned-but-undocumented — an extraction gap to close, not a
specification, and not license to change the behavior.

Rule IDs are stable forever: never renumbered, never reused. A
retired rule keeps its ID with a one-line tombstone pointing at
decisions.md. Cross-references use the anchor form `decisions.md#P2`
/ `mechanisms.md#SPANS`; a bare ID is never a citation. The
`interacts:` field on a pointer line is advisory — the
citation-integrity test checks the ID exists, not that the
interaction is real.

Every example line is EXECUTABLE. The grammar (its executable
definition is `tests/v2/rules_doc.py`; `tests/v2/test_rules_doc.py`
runs every line):

    "INPUT" [annotation] →  field="value"  [· boundary]
                            [deviates: #N (today: field="value")]

An `annotation` names a policy, locale (`[ru]`), or extras gate
(`[ja+segmenter]`) in the registry beside the test. `· boundary`
marks the non-firing example every rule must carry — or the rule
declares `no-boundary: <reason>` instead, so skipping the boundary is
a recorded decision. `deviates:` states the INTENDED output on the
example line while the marker records TODAY's output and the tracking
issue; the runner asserts today's output strictly, so a parser change
that closes the gap fails the suite until the marker is removed in
the same PR. `grep deviates:` on this file is the deviation backlog
(deviations from statable rules — coverage gaps are a separate,
larger category no grep can see).

## Not in scope

- **Language detection.** The parser never infers a language from
  Latin-script text: transliteration destroys the signal ("Ali",
  "Van", "Bin" each belong to several languages with conflicting
  readings). Language-specific behavior is opt-in configuration.
  Script-conditional behavior exists only where the script itself
  settles the convention (see the W section).
- **Grammatical inflection.** Names inflect in many languages
  (vocative, genitive); this library neither produces nor consumes
  inflected forms. CLDR personNames draws the same line.
- **Validation.** Deciding whether a string IS a person's name is not
  parsing; `parse()` is total over strings and never rejects input.

## Titles & honorifics (H)

## Particles & surname prefixes (P)

## Suffixes: generational & credentials (S)

## Nicknames & quoted names (N)

## Maiden names (M)

## Commas & structure (C)

## Name order (O)

## Scripts & writing systems (W)

## Tokens, initials & punctuation (T)

## Ambiguity & tie-breaking (A)

## Rendering & views (R)

## Construction & configuration diagnostics (D)
