# Decisions

The why behind the rules: a lightweight ADR log, keyed by rule ID (`P2 — <short name>`), by mechanism slug, or by a short slug for cross-cutting and tooling decisions. Each key is one file, named for its key and name and listed in the index below, so every `decisions/P2` reference in code or in the rules resolves to one file. A new entry under an existing key goes in that key's file; a new key is a new file and an index line, and the file opens with `## Standing` and `## Log` (below).

The gitignored planning specs are the working medium and die with their branches; this folder is the record. A landing design PR distills its spec's durable residue into its entry files (the checklist is AGENTS.md's "Landing a design").

Entry conventions:

- **Dated decision entries**, append-only for DECISIONS, not for text. Each entry cites its issue or PR. A new entry opens with its verdict — a capitalized headline sentence (`C1 IS DECIDED ONCE, AFTER CLASSIFY, …`) ahead of the evidence, so a reader skimming the file reads the verdicts; older entries that open otherwise are left as written, rewording them being none of the edits below. The date is the DECISION's, never the release's (add "shipped in X" alongside if useful), and git author dates outrank remembered ones — two review rounds corrected exactly these two errors. Four kinds of edit to an existing entry, and no others:
  1. **A changed or reversed decision is a new entry.** The old entry's verdict and reasons are never edited; the new one names it on a `SUPERSEDES:` line, and the old one gains, right after its head, `SUPERSEDED by <date> #N —`. Reversed IN PART, the old entry's head names the part instead, as decisions/C3's #575 head does (`(where the count runs superseded by #613, decisions/C1)`). Older entries that announce what they replace by opening `SUPERSEDED:` or `SUPERSEDED IN PART:` (decisions/M2's #549, decisions/R4's 2026-09-24) are live, the marker of a superseded entry being `SUPERSEDED by`. This is the part that keeps a reason from being rewritten to fit a later outcome.
  2. **A factual error is corrected in place**, with a note saying what was wrong — a date, an attribution, a measurement or a pointer. decisions/C1's 2026-07-12/13 entry, whose parenthetical moved a misdated credit, is the shape.
  3. **Compaction, on a stated trigger.** A superseded entry is cut to a tombstone: its date, issue, verdict line and `SUPERSEDED by`, plus whatever it recorded that the superseding entry did not replace — a gap it found standing before its change, or an option it declined that the reversal does not answer, stays beneath the tombstone (decisions/T4's #731); a superseded passage inside a live entry is cut to its decision and what replaced it. A measurement paragraph (what moves, cost, blast radius) is cut to one line naming its population, counts, baseline and PR once its change has shipped in a release. The full text stays in git and in the PR the entry cites. #728 is the worked compaction. A harvested entry (below) keeps its framing line through compaction, a tombstone included, and its measured-vs-remembered markings wherever its measurements survive. A trap #759's review found: a one-line replacement carries each count with the classification the old text gave that count and no other (decisions/S2's #614 line had given a whole grid the classification measured on one slice of it).
  4. **A per-word fact that moves into the vocabulary's TOML is REPLACED by a query that finds it** (`uv run python tools/vocab/query.py --issue 661`, `--excluded generation`), not left beside a dated "moved" note, which would keep two copies to drift. Only the per-word sentences go; the decision, its criterion and its measurement stay as written. Sanctioned since 2026-10-18 (decisions/vocabulary-model).
- **`## Standing`**, at the head of a file: the one part edited freely. One line per decision in force, in the present tense, ending with the entry that decided it by its exact date and the first issue its head names (`— 2026-10-06 #613`), or by its date alone where the head names none; where several entries share that date and issue, the pointer goes on with the words its entry's head continues with (`— 2026-09-14 (Derek)`, `— 2026-10-18 #718 review`), the longest such continuation winning and a date inside those words being part of them; a pointer with no words names the entry whose head ends there, and one whose words continue no head there fails, since nothing tells a typo from prose, so prose after such a pointer goes after a `.` or `;` (the words end there, or where the next pointer's date begins); where two heads are the same words, the pointer goes on with the words its entry's text opens with (`— 2026-09-13 #383/#479, AMENDS`), a key rather than prose, and so it does where another head of that date and issue continues past those words (decisions/M3's `— 2026-08-26 #335, the MECHANISM`, beside its `#335 (M3, …)` head); and a pointer still naming more than one entry fails as ambiguous (a parenthesized supersession note in a head is not read), plus a `Not standing:` line for entries whose plan was carried out or whose schedule events overtook, its pointers read and failing as a Standing line's do except that they may name a superseded entry — a decision reversed by a later DECISION is marked under 1 instead and an `Open:` line for each open question. It indexes the log and is never a decision itself: a Standing line with no entry behind it, or only a superseded one, fails `tests/v2/test_design_docs.py::test_every_standing_line_points_at_a_live_entry`, and changing a decision is still a new entry, which updates Standing in the same diff. The entries follow under `## Log`. An entry is a log bullet opening with its date, bare or in bold (`- **2026-10-14 #679 — …**`); a file's title founds no entry, so a bundle recorded as undated bullets under a dated title gains, when its block is written, one dated line opening its Log and naming the bundle, its verdict the title's words (`- 2026-09-10 #322/#323 — WHICH CHARACTERS ARE A PERIOD ON CJK TEXT: the bullets below.`). It dates what the title already dates, so it adds no decision and edits no entry. A file with no dated title dates its bundle line by the date its preamble gives the bullets. A bullet the bundle line's date does not fit, because its own text dates its decision otherwise (`- (A) 2026-08-17 — …`, `Amended 2026-08-23`; a date it gives for something else, such as when a code change landed, is not one) or, where its text dates none, because it was added later from a source outside the bundle's (decisions/3-0-reevaluations' legacy-pickle bullet, promoted from session memory the day after its bundle; a bullet harvested later from the bundle's own session, as two of decisions/comma-suffix-arc's Declined bullets were, keeps the bundle's date), gains a dated line of its own beside the bundle line, dated by that decision date or by the author date of the commit that added it, naming the bullet by the words it opens with, since a pointer reads only a bullet that opens with its date (decisions/3-0-reevaluations and decisions/comma-suffix-arc, 2026-10-22). Where a later decision reversed part of the bundle, its head says which, under edit kind 1. That note is for the reader: a pointer never reads a parenthesized note containing "superseded" (edit kind 1's wording), so a Standing line resting on a bundle is checked by hand against what the bundle's later entries and other files reversed, as for any entry superseded in part. Every decisions file created after C1's block landed (2026-10-19) opens with one, the cheap moment to write it being the file's first entry; the older files are listed in `tests/v2/decisions_without_standing.json`, decisions/C12 and decisions/vocabulary-model among them though they too were created that day, before the rule. `test_a_decisions_file_off_the_list_opens_with_standing` fails on a file off that list with no block (the heading on a line of its own; the words quoted in prose do not count), on a listed file that has gained one, on a listed key no file carries, and on a listed key the list did not hold when the rule landed (a fixed set in `tests/v2/design_docs.py`, its size asserted), so the list never holds a key it did not start with: a new file can join it neither alone nor in exchange for one that leaves. The block stands ahead of every `## Log` heading; a `## Log` before it is a finding, and so is a heading that misspells `## Standing` (a trailing space, a different level), which would otherwise switch the pointer checks off. A decision of another rule's that this log is the record of stays a bullet naming its rule (decisions/C13's line for rules/C2, decisions/P9's for rules/S5); one recorded under another key is an `Elsewhere:` line pointing at that entry, not a bullet. Whether the older files get one is #762. A file of Declined, Excluded, Open, removal or mapping lines is a reference list instead, indexed under the Reference lists heading at the end of the index: it carries no block. A listed file carrying a block, taking a log's shape (a dated entry, a bullet opening with a tag and a date as `- (A) 2026-08-17 — …`, or a dated title) or sitting on the exempt list is a finding, as is a listed key the exempt list did not hold when the rule landed (2026-10-21, #762). Whether a file in none of those shapes is a list or a log is a judgment the check cannot make, made in review. 3-0-reevaluations is not one: other files amend its lines without its saying so (decisions/cjk-comma-demotion scopes its FAMILY_COMMA line), the shape a Standing block's `Not standing:` and `Elsewhere:` lines are for. Five files split out on 2026-10-19 (C13, C14, P8, P9, T5) showed the rule was needed: none had a block, though C1's had landed the same day. **Before writing a line, look for what reversed it elsewhere.** A decision can be overturned by an entry in another file, which the log it stands in never mentions; #776 found two lines wrong that way, one while writing and one in review (P9's #578 note, reversed by decisions/S8's #602; P8's subset, widened by decisions/P3's #397), and #762's first batch (2026-10-21) found five entries whose heads did not say what had replaced part of them (decisions/S6's accepted `abdul Smith Jr Ma`, reversed by decisions/S7's #544; decisions/S4's `Doe, Jane nee Smith MA`, by decisions/M2's #601; decisions/H3's `Dr Smith V`, by decisions/S10's #718, caught only in that batch's PR review; decisions/P5's view comparison and decisions/S10's one-case `v`, by their own files' #614 and #721). So grep the whole folder for each issue and example a line cites, parse each example on the tree, and where a later decision reversed part of an entry mark that entry's head under 1, so the log says what Standing says.
- **`Retired:`**, for a rule taken out of rules/: a line of its own in the rule's decisions file, opening `Retired:` and naming the date, the issue and what replaced the rule (`Retired: 2026-11-02 #800 — folded into C1.`), in the Standing block where the file has one, beside the dated entry that decided it. The ID is then never reused: `tests/v2/test_design_docs.py::test_no_rule_reuses_a_retired_id` refuses a rule file carrying it, a `Retired:` line in a file keyed by no rule ID, and a line that misspells `Retired:` (bold, a list marker or number, lowercase), which would switch the refusal off for its ID. No rule had been retired when the check landed (2026-10-20), so it guarded nothing on the tree until the first one is; its synthetic case is what shows it bites.
- **Harvested entries** (content landed from a session's report) keep their provenance: a "measurements are that session's, spot-checked at landing" framing line, the contributor's measured-vs-remembered markings where they matter, and — the hard-won one — a flagged uncertainty is resolved by reading the source artifact, never by inference from the neighboring argument.
- **`Declined:`** — proposals rejected WITH the evidence that killed them. Resolved-as-no is a decision; without a home for it, the next person re-derives the rejected proposal and its measurement.
- **`Excluded:`** — standing prohibitions with indefinite lifetime, keyed by vocabulary set: entries that must stay OUT of a wordlist, each with its reason. Distinct from Declined because the failure mode differs — nobody re-derives a rejected proposal, but someone sweeping a wordlist ships the excluded entry as a bug. **A word-level refusal is better as data**: an `excluded` key on the word's TOML entry makes adding the refused reading a build error that quotes the reason, which prose cannot do. So these blocks narrow to CLASS-level prohibitions (a criterion that keeps a whole kind of word out) as their words move, under the exception above; a block whose words have not moved yet stays as it is.
- **`Open:`** — unresolved questions as issue links with one-line handles. The ISSUE is canonical; this block never restates it. Two keyings: under a rule ID for questions about the rule, and — like `Excluded:` — keyed to a VOCABULARY SET for contested memberships, the category neither `deviates:` nor `Excluded:` covers: the rule is right and a word's set membership is the question (the shape: `rai` in the suffix acronyms and `swami` absent from the given-name titles, both since answered — see decisions/suffix-acronym-collisions and decisions/indic-honorifics). The blocks keyed by vocabulary rather than by a rule live in decisions/vocabulary-exclusions, headed by the set (or sets) they bind, so a wordlist editor meets the `Excluded:` and `Open:` blocks together; add a new block there, beside any block for the same set. An entry may still record its own keep-outs inline (decisions/generational-words lists SUFFIX_WORDS ones), so search the folder for the set's name too.
- **Weighing entries** for contested questions: the options considered, each option's intended effect, and the accepted costs of the option chosen. The costs accepted here are the artifacts the rule lists under its `Accepted:` consequences; the two link by rule ID.

## Index

## Titles & honorifics (H)

- [H1 — a title and one name word](H1-title-and-one-name-word.md)
- [H2 — the leading-abbreviation title](H2-leading-abbreviation-title.md)
- [H3 — the title run's floor](H3-title-runs-floor.md)
- [H4 — an input that is nothing but vocabulary still has to name somebody](H4-input-that-is-nothing-but-vocabulary-still-has-to-name-somebody.md)
- [H5 — the trailing title run](H5-trailing-title-run.md)
- [H6 — a title before a family comma](H6-title-before-a-family-comma.md)
- [H7 — a joined name unit carrying title vocabulary](H7-joined-name-unit-carrying-title-vocabulary.md)

## Particles & surname prefixes (P)

- [P1 — lone particle fold](P1-lone-particle-fold.md)
- [P2 — particles join forward](P2-particles-join-forward.md)
- [P3 — connectives](P3-connectives.md)
- [P5 — bound given names](P5-bound-given-names.md)
- [P6 — the trailing orphan particle](P6-trailing-orphan-particle.md)
- [P7 — a one-letter particle against the initial it spells](P7-one-letter-particle-against-the-initial-it-spells.md)
- [P8 — a single-letter connective against the initial it spells](P8-single-letter-connective-against-the-initial-it-spells.md)
- [P9 — a particle that is also a suffix word, beside a family comma](P9-particle-that-is-also-a-suffix-word-beside-a-family-comma.md)

## Suffixes: generational & credentials (S)

- [S1 — a bracketed credential is not a nickname](S1-bracketed-credential-is-not-a-nickname.md)
- [S2 — a suffix word ends a name and never opens the string](S2-suffix-word-ends-a-name-and-never-opens-the-string.md)
- [S3 — credentials written with interior periods](S3-credentials-written-with-interior-periods.md)
- [S4 — the ambiguous acronym needs words to spare](S4-ambiguous-acronym-needs-words-to-spare.md)
- [S5 — the given part's trailing slot after a family comma](S5-given-parts-trailing-slot-after-a-family-comma.md)
- [S6 — the case signal at the suffix slot](S6-case-signal-at-the-suffix-slot.md)
- [S7 — the company of an unambiguous credential](S7-company-of-an-unambiguous-credential.md)
- [S8 — the credential's trailing run](S8-credentials-trailing-run.md)
- [S9 — unlisted words that join the ambiguous class by shape](S9-unlisted-words-that-join-the-ambiguous-class-by-shape.md)
- [S10 — the trailing roman numeral](S10-trailing-roman-numeral.md)

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
- [C3 — counting the words before the comma](C3-counting-the-words-before-the-comma.md)
- [C4 — the ambiguous credential class at the comma](C4-ambiguous-credential-class-at-the-comma.md)
- [C5 — paired initials after the comma](C5-paired-initials-after-the-comma.md)
- [C6 — an unlisted all-caps word needs the name's case contrast](C6-unlisted-all-caps-word-needs-the-names-case-contrast.md)
- [C7 — a postnominal part is read before any join](C7-postnominal-part-is-read-before-any-join.md)
- [C8 — the listing form's part after the comma](C8-listing-forms-part-after-the-comma.md)
- [C9 — a one-character suffix word inside a comma part](C9-one-character-suffix-word-inside-a-comma-part.md)
- [C10 — a declared delimiter parts a trailing suffix part](C10-declared-delimiter-parts-a-trailing-suffix-part.md)
- [C11 — what the comma decision reports](C11-what-the-comma-decision-reports.md)
- [C12 — a suffix word ending the name before the comma](C12-suffix-word-ending-the-name-before-the-comma.md)
- [C13 — a credential opening the part after the comma](C13-credential-opening-the-part-after-the-comma.md)
- [C14 — strict mode: a suffix word written as an initial](C14-strict-mode-a-suffix-word-written-as-an-initial.md)

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
- [T4 — the bare letter as an initial](T4-bare-letter-as-an-initial.md)
- [T5 — the written shape of an initial](T5-written-shape-of-an-initial.md)

## Ambiguity & tie-breaking (A)

- [A1 — the ambiguity report](A1-ambiguity-report.md)
- [A2 — the empty name](A2-empty-name.md)

## Rendering & views (R)

- [R1 — fields are views of the parsed words](R1-fields-are-views-of-the-parsed-words.md)
- [R2 — the all-particles family_base divergence](R2-all-particles-family-base-divergence.md)
- [R3 — initials honor the fold](R3-initials-honor-the-fold.md)
- [R4 — case repair reads the unjoined mark](R4-case-repair-reads-the-unjoined-mark.md)
- [R5 — the case-repair gate](R5-case-repair-gate.md)

## Construction & configuration diagnostics (D)

- [D1 — the segmenterless-activation warning](D1-segmenterless-activation-warning.md)
- [D2 — construction raises, parse never does](D2-construction-raises-parse-never-does.md)

## Named topics

- [3-0-reevaluations — decisions shaped by the v1 shim](3-0-reevaluations.md)
- [cjk-comma-demotion — the script shapes are pure, the wrappers are tolerated (2026-09-01, #469)](cjk-comma-demotion.md)
- [cjk-full-stops — which characters are a period on CJK text (2026-09-10, #322/#323)](cjk-full-stops.md)
- [comma-suffix-arc — #291/#296/#316 (2026-07-26 → 2026-08-01)](comma-suffix-arc.md)
- [comparison-surface — why value equality died, and what replaced it](comparison-surface.md)
- [deviates-registry — packs stay pure data (option C)](deviates-registry.md)
- [differential-ledger — the differential ledger's arcs](differential-ledger.md)
- [generational-words — junior and senior in other languages (2026-10-14, #661)](generational-words.md)
- [indic-honorifics — the renunciate class and the Indic honorific vocabulary (2026-09-06, #346/#344/#343)](indic-honorifics.md)
- [initials-repertoire — is_initial across scripts (#320)](initials-repertoire.md)
- [ma-do — ambiguous acronyms by decision](ma-do.md)
- [nfd-shapes — shape tests read letters, and a decomposed letter is one letter](nfd-shapes.md)
- [normalization-fold — lower(), not casefold(); comparison folds harder](normalization-fold.md)
- [parse-cost — what a parse is allowed to cost](parse-cost.md)
- [phd-merge — the "Ph. D." split](phd-merge.md)
- [render-default — the default view's format](render-default.md)
- [review-agent-single-source — the review axes live in one file](review-agent-single-source.md)
- [salutation-titles — salutations, offices and ranks for the languages TITLES had none for (2026-10-04, #606)](salutation-titles.md)
- [script-table-placement — a recorded reversal](script-table-placement.md)
- [suffix-acronym-collisions — the trailing-position collision class, decided (2026-09-07, #342/#454)](suffix-acronym-collisions.md)
- [suffix-field-composition — three kinds of thing in one field](suffix-field-composition.md)
- [two-input-invariants — checking a rule against something that is not the code](two-input-invariants.md)
- [v1-xfail-triage — the eight inherited aspirations, four retired and four kept (three of those eight since fixed, 2026-09-08 and 2026-09-23)](v1-xfail-triage.md)
- [vocabulary-collisions — when a word earns the ambiguous marking](vocabulary-collisions.md)
- [vocabulary-model — each word described by its readings (2026-10-15 → 2026-10-18)](vocabulary-model.md)

## Reference lists

Files of Declined, Excluded, Open, removal or mapping lines rather than a dated log, none of whose lines a later decision reverses without saying so on that line. Each line already says what stands, so they carry no Standing block (the entry conventions above). A file listed here takes no log's shape — no dated entry (a bullet opening with its date; a date inside a Declined or Excluded line is not one), no bullet opening with a tag and a date, no dated title — and only a file created before the Standing rule may be listed: a new decisions file opens with `## Standing` whatever it holds.

- [api-churn-declines — do not re-propose without new cause](api-churn-declines.md)
- [given-name-titles — deliberately unvalidated](given-name-titles.md)
- [legacy-rule-numbers — the old docstring numbering](legacy-rule-numbers.md)
- [removed-v1-surface](removed-v1-surface.md)
- [vocabulary-exclusions — words kept out of a vocabulary set, and contested memberships](vocabulary-exclusions.md)
