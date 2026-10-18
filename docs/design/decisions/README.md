# Decisions

The why behind the rules: a lightweight ADR log, keyed by rule ID (`P2 — <short name>`), by mechanism slug, or by a short slug for cross-cutting and tooling decisions. Each key is one file, named for its key and name and listed in the index below, so every `decisions/P2` reference in code or in the rules resolves to one file. A new entry under an existing key goes in that key's file; a new key is a new file and an index line.

The gitignored planning specs are the working medium and die with their branches; this folder is the record. A landing design PR distills its spec's durable residue into its entry files (the checklist is AGENTS.md's "Landing a design").

Entry conventions:

- **Dated decision entries**, append-only in spirit: a reversed decision is not edited, a later entry supersedes it. Each entry cites its issue or PR. The date is the DECISION's, never the release's (add "shipped in X" alongside if useful), and git author dates outrank remembered ones — two review rounds corrected exactly these two errors.
- **Harvested entries** (content landed from a session's report) keep their provenance: a "measurements are that session's, spot-checked at landing" framing line, the contributor's measured-vs-remembered markings where they matter, and — the hard-won one — a flagged uncertainty is resolved by reading the source artifact, never by inference from the neighboring argument.
- **`Declined:`** — proposals rejected WITH the evidence that killed them. Resolved-as-no is a decision; without a home for it, the next person re-derives the rejected proposal and its measurement.
- **`Excluded:`** — standing prohibitions with indefinite lifetime, keyed by vocabulary set: entries that must stay OUT of a wordlist, each with its reason. Distinct from Declined because the failure mode differs — nobody re-derives a rejected proposal, but someone sweeping a wordlist ships the excluded entry as a bug.
- **`Open:`** — unresolved questions as issue links with one-line handles. The ISSUE is canonical; this block never restates it. Two keyings: under a rule ID for questions about the rule, and — like `Excluded:` — keyed to a VOCABULARY SET for contested memberships, the category neither `deviates:` nor `Excluded:` covers: the rule is right and a word's set membership is the question (the shape: `rai` in the suffix acronyms and `swami` absent from the given-name titles, both since answered — see decisions/suffix-acronym-collisions and decisions/indic-honorifics). Both vocabulary-keyed kinds live in decisions/vocabulary-exclusions, one block per set, so a wordlist editor meets a set's `Excluded:` and `Open:` blocks together; add a new set's block there.
- **Weighing entries** for contested questions: the options considered, each option's intended effect, and the accepted costs of the option chosen. The costs accepted here are the artifacts the rule lists under its `Accepted:` consequences; the two link by rule ID.

## Index

## Titles & honorifics (H)

- [H1 — a title and one name word](H1-title-and-one-name-word.md)
- [H2 — the leading-abbreviation title](H2-leading-abbreviation-title.md)
- [H3 — the title run's floor](H3-title-runs-floor.md)
- [H4 — an input that is nothing but vocabulary still has to name somebody](H4-input-that-is-nothing-but-vocabulary-still-has-to-name-somebody.md)
- [H5 — the trailing title run](H5-trailing-title-run.md)
- [H6 — a title before a family comma](H6-title-before-a-family-comma.md)

## Particles & surname prefixes (P)

- [P1 — lone particle fold](P1-lone-particle-fold.md)
- [P2 — particles join forward](P2-particles-join-forward.md)
- [P3 — connectives](P3-connectives.md)
- [P5 — bound given names](P5-bound-given-names.md)
- [P6 — the trailing orphan particle](P6-trailing-orphan-particle.md)
- [P7 — a one-letter particle against the initial it spells](P7-one-letter-particle-against-the-initial-it-spells.md)

## Suffixes: generational & credentials (S)

- [S2 — the case signal at the suffix slot](S2-case-signal-at-the-suffix-slot.md)

## Nicknames & quoted names (N)

- [N1 — the default delimiter pairs](N1-default-delimiter-pairs.md)
- [N2 — same-character quotes and shared-character conventions](N2-same-character-quotes-and-shared-character-conventions.md)
- [N3 — the lone-word nickname rule](N3-lone-word-nickname-rule.md)

## Maiden names (M)

- [M1 — delimited maiden names](M1-delimited-maiden-names.md)
- [M2 — the maiden-marker rule](M2-maiden-marker-rule.md)
- [M3 — the marker-led clause](M3-marker-led-clause.md)
- [M4 — a maiden marker makes the lone name word the family](M4-maiden-marker-makes-the-lone-name-word-the-family.md)

## Commas & structure (C)

- [C1 — the suffix-comma decision](C1-suffix-comma-decision.md)

## Name order (O)

- [O1 — East Slavic rotation](O1-east-slavic-rotation.md)
- [O2 — Turkic rotation](O2-turkic-rotation.md)
- [O4 — positional assignment and declared order](O4-positional-assignment-and-declared-order.md)
- [O5 — the lone name word's convention, and reporting it](O5-lone-name-words-convention-and-reporting-it.md)

## Scripts & writing systems (W)

- [W1 — unspaced CJK division](W1-unspaced-cjk-division.md)
- [W2 — the glued-honorific peel](W2-glued-honorific-peel.md)
- [W3 — the writer's divisions are respected](W3-writers-divisions-are-respected.md)
- [W4 — script-scoped order](W4-script-scoped-order.md)

## Tokens, initials & punctuation (T)

- [T1 — separators, not joiners](T1-separators-not-joiners.md)
- [T3 — the interpunct's flank guard](T3-interpuncts-flank-guard.md)

## Ambiguity & tie-breaking (A)

- [A1 — the ambiguity report](A1-ambiguity-report.md)
- [A2 — the empty name](A2-empty-name.md)

## Rendering & views (R)

- [R2 — the all-particles family_base divergence](R2-all-particles-family-base-divergence.md)
- [R3 — initials honor the fold](R3-initials-honor-the-fold.md)
- [R4 — case repair reads the unjoined mark](R4-case-repair-reads-the-unjoined-mark.md)
- [R5 — the case-repair gate](R5-case-repair-gate.md)

## Construction & configuration diagnostics (D)

- [D1 — the segmenterless-activation warning](D1-segmenterless-activation-warning.md)
- [D2 — construction raises, parse never does](D2-construction-raises-parse-never-does.md)

## Named topics

- [3-0-reevaluations — decisions shaped by the v1 shim](3-0-reevaluations.md)
- [api-churn-declines — do not re-propose without new cause](api-churn-declines.md)
- [cjk-comma-demotion — the script shapes are pure, the wrappers are tolerated (2026-09-01, #469)](cjk-comma-demotion.md)
- [cjk-full-stops — which characters are a period on CJK text (2026-09-10, #322/#323)](cjk-full-stops.md)
- [comma-suffix-arc — #291/#296/#316 (2026-07-26 → 2026-08-01)](comma-suffix-arc.md)
- [comparison-surface — why value equality died, and what replaced it](comparison-surface.md)
- [deviates-registry — packs stay pure data (option C)](deviates-registry.md)
- [differential-ledger — the differential ledger's arcs](differential-ledger.md)
- [generational-words — junior and senior in other languages (2026-10-14, #661)](generational-words.md)
- [given-name-titles — deliberately unvalidated](given-name-titles.md)
- [indic-honorifics — the renunciate class and the Indic honorific vocabulary (2026-09-06, #346/#344/#343)](indic-honorifics.md)
- [initials-repertoire — is_initial across scripts (#320)](initials-repertoire.md)
- [legacy-rule-numbers — the old docstring numbering](legacy-rule-numbers.md)
- [ma-do — ambiguous acronyms by decision](ma-do.md)
- [nfd-shapes — shape tests read letters, and a decomposed letter is one letter](nfd-shapes.md)
- [normalization-fold — lower(), not casefold(); comparison folds harder](normalization-fold.md)
- [parse-cost — what a parse is allowed to cost](parse-cost.md)
- [phd-merge — the "Ph. D." split](phd-merge.md)
- [removed-v1-surface](removed-v1-surface.md)
- [render-default — the default view's format](render-default.md)
- [review-agent-single-source — the review axes live in one file](review-agent-single-source.md)
- [salutation-titles — salutations, offices and ranks for the languages TITLES had none for (2026-10-04, #606)](salutation-titles.md)
- [script-table-placement — a recorded reversal](script-table-placement.md)
- [suffix-acronym-collisions — the trailing-position collision class, decided (2026-09-07, #342/#454)](suffix-acronym-collisions.md)
- [suffix-field-composition — three kinds of thing in one field](suffix-field-composition.md)
- [two-input-invariants — checking a rule against something that is not the code](two-input-invariants.md)
- [v1-xfail-triage — the eight inherited aspirations, four retired and four kept (three of those eight since fixed, 2026-09-08 and 2026-09-23)](v1-xfail-triage.md)
- [vocabulary-collisions — when a word earns the ambiguous marking](vocabulary-collisions.md)
- [vocabulary-exclusions — words kept out of a vocabulary set, and contested memberships](vocabulary-exclusions.md)
