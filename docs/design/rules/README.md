# Parsing rules

This document is NORMATIVE, not descriptive: the rules state how names are written and what should happen when they are parsed, grounded in how people understand names — not in what the parser currently does. The parser implements these rules. Where it does not yet, the gap is a tracked deviation (`deviates:` marker below), not a counterexample. Statements are implementation-free: no stage names, no function names, no regexes.

Authority, scoped: `tests/v2/cases.py` pins CURRENT behavior; this document states INTENDED behavior. A mismatch between them must be classified, never defaulted: either the rule is wrong (fix it here) or the parser is wrong (the example takes a `deviates:` marker and an issue). Where this document is silent, the behavior is pinned-but-undocumented — an extraction gap to close, not a specification, and not license to change the behavior.

Rule IDs are stable forever: never renumbered, never reused. A retired rule keeps its ID with a one-line tombstone pointing at its decisions entry. Cross-references use the form `decisions/P2` / `mechanisms.md#SPANS`; a bare ID is never a citation. The `interacts:` field on a pointer line is advisory — the citation-integrity test checks the ID exists, not that the interaction is real. `implemented:` and `tracked:` are not advisory: every rule carries exactly one. `implemented:` names the modules honoring the rule, checked against the modules that cite it; `tracked:` names the issues that would ship a rule nothing implements yet, so a wholly-aspirational rule cannot sit here untracked, and a shipped rule cannot keep a stale tracking pointer.

Every example line is EXECUTABLE. The grammar (its executable definition is `tests/v2/rules_doc.py`; `tests/v2/test_rules_doc.py` runs every line):

    "INPUT" [annotation] →  field="value"  [· boundary]
                            [deviates: #N (today: field="value")]

An `annotation` names a policy, locale (`[ru]`), or extras gate (`[ja+segmenter]`) in the registry beside the test. `· boundary` marks the non-firing example every rule must carry: an input shaped like the rule's subject where its effect does NOT occur. That is usually the rule's OWN stated exception — H1's given-name title, P3's single-letter carve-out — not an input the rule never reaches, so the exception is executable rather than merely asserted. Or the rule declares `no-boundary: <reason>` instead, so skipping the boundary is a recorded decision. `deviates:` states the INTENDED output on the example line while the marker records TODAY's output and the tracking issue; the runner asserts today's output strictly, so a parser change that closes the gap fails the suite until the marker is removed in the same PR. `grep deviates:` on this file is the deviation backlog (deviations from statable rules — coverage gaps are a separate, larger category no grep can see, and contested vocabulary memberships a third, tracked as Open blocks keyed to the vocabulary set in decisions/).

One class of rule stands outside the normative reading and declares it on a `tolerated: <reason>` line beside its pointer line. Such a rule is ABOUT an input the writing systems it speaks about do not produce — a shape no convention writes, read best-effort because parsing is total over strings — and it describes what the parser does with that input instead of promising it. Its statement is still precedence-bearing and its examples are still executable and still run, but they illustrate rather than promise, and the behavior is changeable without notice. W3 is the only such rule today (the 2026-09-01 comma demotion).

The marker's unit is the whole rule, so a clause that reaches past the tolerated shape does not belong in a marked rule — say it in a normative one. The marker changes what the rule promises, not what is watched: a marked rule's examples are in `tools/differential/corpus_rules.jsonl` like any other, so the snapshot shows when their reading moves (#664).

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

## [Particles & surname prefixes (P)](P-particles-and-surname-prefixes.md)

- [P1 — lone particle fold](P1-lone-particle-fold.md)
- [P2 — particles join forward](P2-particles-join-forward.md)
- [P3 — connectives](P3-connectives.md)
- [P4 — a particle at the front of the name](P4-particle-at-the-front-of-the-name.md)
- [P5 — bound given names](P5-bound-given-names.md)
- [P6 — the trailing orphan particle](P6-trailing-orphan-particle.md)
- [P7 — a one-letter particle against the initial it spells](P7-one-letter-particle-against-the-initial-it-spells.md)

## [Suffixes: generational & credentials (S)](S-suffixes-generational-and-credentials.md)

- [S1 — a bracketed credential is not a nickname](S1-bracketed-credential-is-not-a-nickname.md)
- [S2 — the case signal at the suffix slot](S2-case-signal-at-the-suffix-slot.md)
- [S3 — credentials written with interior periods](S3-credentials-written-with-interior-periods.md)

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

## [Name order (O)](O-name-order.md)

- [O1 — East Slavic rotation](O1-east-slavic-rotation.md)
- [O2 — Turkic rotation](O2-turkic-rotation.md)
- [O3 — compound family names written unmarked](O3-compound-family-names-written-unmarked.md)
- [O4 — positional assignment and declared order](O4-positional-assignment-and-declared-order.md)
- [O5 — the lone name word's convention, and reporting it](O5-lone-name-words-convention-and-reporting-it.md)

## [Scripts & writing systems (W)](W-scripts-and-writing-systems.md)

- [W1 — unspaced CJK division](W1-unspaced-cjk-division.md)
- [W2 — the glued-honorific peel](W2-glued-honorific-peel.md)
- [W3 — the writer's divisions are respected](W3-writers-divisions-are-respected.md)
- [W4 — script-scoped order](W4-script-scoped-order.md)

## [Tokens, initials & punctuation (T)](T-tokens-initials-and-punctuation.md)

- [T1 — separators, not joiners](T1-separators-not-joiners.md)
- [T2 — the katakana middle dot divides like a space](T2-katakana-middle-dot-divides-like-a-space.md)
- [T3 — the interpunct's flank guard](T3-interpuncts-flank-guard.md)

## [Ambiguity & tie-breaking (A)](A-ambiguity-and-tie-breaking.md)

- [A1 — the ambiguity report](A1-ambiguity-report.md)
- [A2 — the empty name](A2-empty-name.md)

## [Rendering & views (R)](R-rendering-and-views.md)

- [R1 — fields are views of the parsed words](R1-fields-are-views-of-the-parsed-words.md)
- [R2 — the all-particles family_base divergence](R2-all-particles-family-base-divergence.md)
- [R3 — initials honor the fold](R3-initials-honor-the-fold.md)
- [R4 — case repair reads the unjoined mark](R4-case-repair-reads-the-unjoined-mark.md)
- [R5 — the case-repair gate](R5-case-repair-gate.md)

## [Construction & configuration diagnostics (D)](D-construction-and-configuration-diagnostics.md)

- [D1 — the segmenterless-activation warning](D1-segmenterless-activation-warning.md)
- [D2 — construction raises, parse never does](D2-construction-raises-parse-never-does.md)
