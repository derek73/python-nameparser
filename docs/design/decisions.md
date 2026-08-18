# Decisions

The why behind the rules: a lightweight ADR log, keyed by rule ID (`### P2 — <short name>`), by mechanism slug, or by a short slug for cross-cutting and tooling decisions. Section headings carry the key, so every `decisions.md#P2` reference in code or rules.md is a live anchor.

The gitignored planning specs are the working medium and die with their branches; this file is the record. A landing design PR distills its spec's durable residue here (the checklist is AGENTS.md's "Landing a design").

Entry conventions:

- **Dated decision entries**, append-only in spirit: a reversed decision is not edited, a later entry supersedes it. Each entry cites its issue or PR. The date is the DECISION's, never the release's (add "shipped in X" alongside if useful), and git author dates outrank remembered ones — two review rounds corrected exactly these two errors.
- **Harvested entries** (content landed from a session's report) keep their provenance: a "measurements are that session's, spot-checked at landing" framing line, the contributor's measured-vs-remembered markings where they matter, and — the hard-won one — a flagged uncertainty is resolved by reading the source artifact, never by inference from the neighboring argument.
- **`Declined:`** — proposals rejected WITH the evidence that killed them. Resolved-as-no is a decision; without a home for it, the next person re-derives the rejected proposal and its measurement.
- **`Excluded:`** — standing prohibitions with indefinite lifetime, keyed by vocabulary set: entries that must stay OUT of a wordlist, each with its reason. Distinct from Declined because the failure mode differs — nobody re-derives a rejected proposal, but someone sweeping a wordlist ships the excluded entry as a bug.
- **`Open:`** — unresolved questions as issue links with one-line handles. The ISSUE is canonical; this block never restates it. Two keyings: under a rule ID for questions about the rule, and — like `Excluded:` — keyed to a VOCABULARY SET for contested memberships, the category neither `deviates:` nor `Excluded:` covers: the rule is right and a word's set membership is the question (rai in the suffix acronyms, swami absent from the given-name titles). Place the block beside the set's `Excluded:` entries so a wordlist editor meets both.
- **Weighing entries** for contested questions: the options considered, each option's intended effect, and the accepted costs of the option chosen. The costs accepted here are the artifacts rules.md lists under the rule's `Accepted:` consequences; the two link by rule ID.

### A2 — the empty name

- 2026-07 (v2 core, PR #288) — v1 kept parse(".") as first="."; 2.0 empties content-free input instead. The born-empty-ambiguity survival was a review fix in the rc1 arc: an unbalanced-delimiter report must outlive the emptying, or malformed input becomes indistinguishable from blank input.

### legacy-rule-numbers — the old docstring numbering

Before rules.md, the post_rules stage docstring numbered its rules locally, and historical issue comments (#359, #364, #365, #367) use those numbers. The mapping: rule 1 → H1, rule 1b → P1, rule 2 → O1, rule 3 → O2, rule 4 → O3. Older still: bare "#11"-style citations from v1 comments live in the GOOGLE CODE namespace, not GitHub — GC issue 11 is decisions.md#P3's provenance — so a v1-era number that doesn't fit its GitHub issue is probably a GC number.

### P1 — lone particle fold

A lone PIECE is the whole test — deliberately narrower than "a never-given particle is never reported as the given name," which would be false (the over-broad invariant shipped to five sites before #361's review falsified it with three counter-examples). The counter-example set has since shrunk, and its shrinkage is the section's history: "Sir de Mesnil" fell to #367 (titles became transparent); "Juan de la Vega" under family-first — the whole chain in the given position — was called working-as-intended by
#359, contested by #368, and is working-as-intended again as of
the 2026-08-16 entries below. The survivor is the degenerate bare
"de".

- 2026-08 #359 — the opening site is read from joining structure (pieces), not from assigned roles, so the fold holds under every name_order. Before this, the role-only read let "de Mesnil" split under a family-first order.
- 2026-08 #367 — titles are transparent to the fold: "Sir de Mesnil" now reads like "de Mesnil". Fixed by removing the title→particle chain in grouping, not by touching this rule.
- 2026-08-16 (order-precedence keystone; #364, #365, #368) — the stage split is the decision, and the three issues are one question seen from three angles. GROUPING is vocabulary's job and is order-independent: a particle joins forward through consecutive particles and stops at the first non-particle, and no name_order moves that stopping point. ASSIGNMENT is name_order's job: groups take roles by the declared order. The bugs existed because the implementation runs the two in the opposite dependency — `assign` hands out positions from `_effective_order` and `post_rules` then inspects a fixed list of ROLES, so P1's fold sites and P2's chain had coverage that varied with the declared order by accident. Consequences, each recorded in its own right below: the fold takes only the particle's own group (#364); the middle position needs no third site once grouping is order-independent (#365); and #368 reverses.
- 2026-08-16 #364 — the fold takes the particle RUN and the ONE name word it attaches to, not every remaining word.
  "de Mesnil Juan" is family="de Mesnil" plus given="Juan". Run,
  not particle: "de la Vega" is two particles onto one word, and an earlier wording here said "the particle", which its own example contradicted (rule-vs-decision-record review). Nothing ever argued for
  "takes everything"; it was the shape of v1's
  handle_non_first_name_prefix, not a decision. Measured before deciding, over every name in the three differential corpora with NO string prefilter: exactly ONE family holds words beyond its particle's group — "de Mesnil Garcia".
  #364's own body warns the change "breaks the v1 parity
  tools/differential protects" and that "each ledger would need re-examining"; measured, it is one name and one ledger entry. A shape filter (no comma, leading never-given particle, three or more words) returns THREE candidates, of which two do not move:
  "de la Vega" is one group start to finish, and "de Mesnil Jr."
  has only two name words because Jr. is a suffix. The pre-merge fact-check caught this stated as "the filter gives one name", which it does not. Measurement trap, recorded because the fact-check fell into it twice: the particle group runs through ANY particle, not only the never-given ones — "de la Vega" chains never-given "de" through AMBIGUOUS "la" onto "Vega". A detector that walks only the never-given run splits the group after "de la" and reports 50 false movers.
- 2026-08-16 #368 REVERSED — shipped behavior is correct.
  "Juan de la Vega" under FAMILY_FIRST groups [Juan][de la Vega]
  and assigns family="Juan", given="de la Vega". The earlier decision ("the particle wins ... whatever order was declared") was made before the grouping/assignment split was stated and cannot survive it: a mid-name chain HAS a head word and is positioned like any other group. What NON_GIVEN_NAME_PARTICLES guarantees is that the bare word never reads as a given name, not that no name part may begin with one. The asymmetry with the leading case is P4's, not an exception invented here: a leading particle chains nothing, so without the fold pure position makes the BARE particle the given name. That is measurable today on the ambiguous half, where no fold fires —
  "van Mesnil Juan" gives given="van", middle="Mesnil",
  family="Juan". given="de" is the reading the vocabulary exists to forbid, and the fold is what prevents it. The all-orders agreement in P1 is deliberate and is W4's shape: a wholly-hangul name reads family="김" under every declared order because the script carries a signal the order does not override, and a leading never-given particle is the Latin-script analogue. decisions.md#O4 already draws the line — "Words no vocabulary has claimed read by position" — so name_order governs the unclaimed remainder, which is most inputs.

- 2026-08-17 #390 (retry; the first attempt is PR #391, closed unmerged) — the claim moved into GROUPING, and that is what the first attempt could not do from assign. Three routes violated P1 there: a chained piece could not be split ("de la Vega Juan" groups as [de][la Vega Juan], so taking two pieces takes the whole name), the FAMILY_COMMA branch was never reached, and "de los Santos" regressed to given="Santos" because the particle vocabulary had gaps. #360 fixed the third by landing first. P4 is AMENDED rather than worked around: a never-given particle leading the name now chains, through its run onto one word, while an ambiguous one still chains nothing so "Van Johnson" survives. A run INSIDE the name still joins greedily (P2 unchanged), and the asymmetry is the two positions meaning different things -- "pennie von bergen wessels" is a US politician whose surname is all three words, while "de la Vega Juan" is a surname plus a given name. Identical shape; only position tells them apart. The comma path changed too, deliberately: "Smith, de Mesnil" was family="Smith de Mesnil" in v1 and is now family="Smith", given="de Mesnil". Nobody writes a comma to mean "all of this is the family name", so the comma stays the primary order signal and the post-comma run reads as given text. A v1 parity break, recorded. Guard shape, twice wrong before it was right: the head-token test must assert the token IS a never-given particle, not merely that it lacks the ambiguous tag. A conjunction merge makes "and van" one prefix-tagged piece headed by "and", which carries no particle tag at all, so the negative test passed vacuously and swallowed "and van Buren"; and a both-vocabulary word (st, do, freiherr) led the chain until `not title` was added, which is the same trap this section already records under Declined.

Declined:

- A strict xfail asserting "de Mesnil" → family under FAMILY_FIRST (#359 review) — #359 deliberately left those semantics open, and a strict xfail decides the question by the back door.
- Keying the leading-particle exception on "the first piece that is not a title" — the obvious implementation, and wrong: st, do and freiherr are titles AND ambiguous particles, so it collapsed
  "St John Smith" into one given name and broke test_add_title
  (which adds "te", also a particle). The shipped predicate is
  "not a title or a prefix".
- 2026-08-16 — deleting P4 so a leading particle chains and is then positioned, which is the only way to make "de Mesnil Juan" vary by declared order. It avoids given="de" (the group would be
  [de Mesnil]) but breaks "de la Vega": measured, a single group is
  positioned by the declared order — "Cher" reads given under GIVEN_FIRST — so "de la Vega" would read given="de la Vega" unless a further rule forced a particle-headed group into the family. Add that rule and [de Mesnil][Juan] yields the #364 reading anyway, so the deletion buys nothing and costs P4.

Open: [#360](https://github.com/derek73/python-nameparser/issues/360) which particles count as never-given (the criterion is settled at decisions.md#vocabulary-collisions; the 39-member application is not).

### P2 — particles join forward

- 2026-08 #367 — REMOVED a chain, it did not create one: before, the title displaced the particle out of the leading position, so
  "Sir de Mesnil" grouped [Sir][de Mesnil] — a chain — and
  reported given="de Mesnil" with no family at all. After, "de" is the leading name piece, and a leading particle chains nothing (rule P4): the family reading comes from P1's fold, which is why P1's fold needed no change (its interacts: points here). Grouped today: [Sir] [de] [Mesnil].

- Group distribution is load-bearing, not incidental: the v1 Portuguese tests (test_portuguese_dos, test_portuguese_prefixes) require multiple particle groups to land across middle and family, while #132 wanted the combined double-surname reading — the same shape with opposing wants, which is why the combined reading lives in the surnames VIEW and the split in the fields.

### P6 — the trailing orphan particle

- 2026-08-16 (order-precedence keystone; #379, #380, #365) — a particle ending the name has nothing to link forward to, and no particle is a name by itself, so it attaches to the family name standing beside it and renders BEFORE it. The distinction from a chain is what makes this a rule rather than an exception: a chained group has a head word and can be positioned; an orphan has no head, so position has nothing to work with.
- Scope: the COMMA form only, deliberately. "Jong, Anke de" is unambiguous — the comma has already named the family. Without the comma the written shape is not settled: "Jong Anke de" may be a misformatted listing (arguably a missing comma under a declared family-first order) and "Jong de" may be a given name beside a particle. Those keep their positional reading and are not tracked as deviations.
- The words-to-spare guard is load-bearing, not incidental. #379's own subject is "van", which is in the AMBIGUOUS half — so a rule keyed to never-given particles alone would not fix the issue it was filed for, while a rule with no guard breaks Vietnamese
  "Nguyen, Van" (given="Van") by eating the only given word. The
  guard is S2's shape, reused: consume only when the name has words to spare.
- Rendering before the family has precedent in rules.md#R1 — folded family words under O3 already "render before the rest of the family wherever they stood in the string". The surnames view renders backwards today ("Vega de la", "Jong de") and flips with this rule.
- Measured under this rule's OWN comma scope, over 782 corpus names (245 of them comma-bearing): exactly one moves,
  "Vega, Juan de la" → family="de la Vega". A pre-merge fact-check
  corrected an earlier count of three here — "Smith van der" and
  "Sander van" have no comma, so the rule as scoped does not reach
  them; they were measured before the comma scoping was chosen and carried forward unfiltered.
- What that number means is the opposite of reassuring. The corpus holds 245 comma names, TWO of which end in a particle and one of which clears the words-to-spare guard ("Nguyen, Van" is the other, and the guard is what keeps it a given name), so it is very nearly blind to the shape this rule governs — Dutch and Flemish listings are barely represented. Treat the one as evidence about the corpus, not about the blast radius, and run tools/differential at all three baselines in the implementing PR regardless of how small this looks.
- 2026-08-16 (pre-merge coherence pass) — P6 and S2 CONTEST
  "Berg, Jan vd": today S2 wins and reports suffix="vd", while
  P6's marker asserts family="vd Berg". P6 wins, and the rule says so in its statement rather than leaving the pair to file order. The reason is C-ii's, not a new judgement: vd as the British Volunteer Decoration is rarer than vd as van der, and a trailing abbreviation AFTER A FAMILY COMMA is the tussenvoegsel position specifically. Scope check on the precedence, so it cannot creep: it reaches only words that are both particle and suffix vocabulary, in the trailing-orphan position, under a family comma, with a given word to spare. "John Smith, PhD" and "Smith, Jr." are untouched (not particles), and "Jong, vd" is untouched (no given word remains), which is why that row stays out of scope rather than becoming a counter-example. Recorded because the pair was declared in `interacts:` and left unresolved — `interacts:` is advisory by design and pins nothing, so a declared interaction is a prompt to state the outcome, not a substitute for stating it.
- 2026-08-16 — P6 is the first rule in rules.md that nothing implements. Legitimate per the preamble (the document is normative, and a gap is a tracked deviation), but it left the rule pointing at nothing, so the shape got a pointer rather than an exception: `tracked: #379, #380` in place of `implemented:`, with exactly one of the two required of every rule. An unimplemented rule can no longer sit here untracked, and a shipped rule cannot keep a stale tracking pointer after its issues close. Mutation-tested three ways before being believed (drop the pointer, carry both, malformed refs); each fails.
- The RATIONALE first shipped here was wrong and is corrected: it read "no particle is a name by itself", which is true only of the never-given half — decisions.md#vocabulary-collisions says the opposite in as many words ("most particles are short words that double as names"). The error mattered rather than merely reading badly: the words-to-spare guard exists BECAUSE the rule reaches ambiguous particles (#379's own subject is "van"), so the rationale undercut its own guard. Caught in review, after a coherence pass that interrogated rule-vs-rule pairs and never checked rule-vs-decision-record — which is the gap to close next time, not a one-off.

Open: [#380](https://github.com/derek73/python-nameparser/issues/380) covers "Berg, Jan vd" under this rule, but the vd reading itself is decisions.md#vocabulary-collisions (C-ii); and the no-given-word case "Jong, vd" is deliberately unresolved — see the scope note.

### M2 — the maiden-marker rule

- 2026-07-03 (maiden-bucket design; #274 filed 2026-07-07, landed in the v2 core, PR #288) — the marker takes everything after it up to a trailing suffix, greedily: "née Jones Smith" is a two-word maiden name, matching how the marker is actually used in running text. The marker itself is dropped as structural, like a delimiter character.

Open (M2):
[#317](https://github.com/derek73/python-nameparser/issues/317)
the fullwidth-colon marker (旧姓：佐藤 arrives as one word; the head-peel question).

### N3 — the lone-word nickname rule

- 2026-07 (v2 core, PR #288; recorded plan deviation #2 of the core plan) — v1's rule counted pieces before grouping; the v2 port fires only when the nickname accompanies exactly ONE piece in total — a title counts against it, which is why "'Smitty' Dr. Jones" reads given="Jones" with the family empty (rules.md#N3's Accepted consequence) rather than family="Jones". The rule lives in assignment because that is where the piece count is settled. (An earlier wording here said "one non-title piece", predicting the opposite output; the coherence review measured the truth.)

### N2 — same-character quotes and shared-character conventions

- 2026-07-18 #273 (7ee6e3a) — the typographic delimiter pairs shipped with a per-pair full-text scan; three independent review agents broke it the same day: with two shared-character conventions genuinely present, the earlier-sorted pair stole the close and the legitimate match dropped silently, zero ambiguity.
- 2026-07-18 (05fe693, the same day) — the interleaved leftmost-match restructure replaced it (an altitude review called it the right depth); the author's own first fix — post-hoc offset filtering of unbalanced candidates alone — was superseded within the day and survives only as the bulk-recorded dangler filter rules.md#N2 now names. The word-internal carve-out covers ONLY the straight apostrophe because it is the one delimiter character that occurs mid- and end-of-word in real names; Derek's distinguishing test: with double quotes the same shape ("Mari\" Aube\"") is genuinely ambiguous, while Mari' Aube' is not. A cached delimiter-charset prescreen landed in the same commit, measured: no-delimiter names parse faster than the pre-#273 baseline.

Declined:

- The offset-filter as the whole fix — it repaired the reported symptom (spurious unbalanced flags) while leaving the stolen- close mis-extraction in place.

### ma-do — ambiguous acronyms by decision

- 2026-07-17 (M12, Derek-approved) — ma and do joined the ambiguous acronym set because both are common surnames; the two-word "Jack Ma" is kept intact by S2's words-to-spare guard, while the periods gate governs the dotted spellings ("M.A." counts unambiguously). Documented side effect: parenthesized bare
  "(MA)"/"(DO)" no longer escape to suffix as in 1.x.

### vocabulary-collisions — when a word earns the ambiguous marking

The mechanism shipped twice before anyone wrote down its criterion. Sizes as of 2.2.0dev: particles 67 with 39 ambiguous (58%, PARTICLE_OR_GIVEN); suffix_acronyms 613 with 4 ambiguous (0.65%, SUFFIX_OR_NAME); titles 711 with no ambiguous subset and no AmbiguityKind at all. Those counts are evidence from the decision date, not live facts — they drift with every vocabulary addition. The argument does not depend on the digits (it depends on the two shares differing by orders of magnitude), but recompute before quoting them:

    uv run python -c "from nameparser import Parser; L=Parser().lexicon; print({s: len(getattr(L,s)) for s in ('particles','particles_ambiguous','suffix_words','suffix_acronyms','suffix_acronyms_ambiguous','titles')})"

- 2026-08-16 (collision keystone; #348, #360, #342, #385) — the 58%-vs-0.65% gap is BASE RATE, not disagreement. Both sets apply the same test; most particles are short words that double as names (van, bin, le, do, bar, mac) while most credential acronyms are not (abpp, acp). Recorded because the gap reads as an inconsistency and is not one — a reviewer who "harmonizes" the two shares will break one of them.
- **C-i, vocabulary vs. name.** A word belongs in its set's ambiguous subset iff it is borne as an ordinary name IN THE POSITION THE VOCABULARY CLAIM ACTS ON. Existence of a bearer anywhere is not the test, and the first draft of this criterion (recorded 2026-08-16, corrected 2026-08-17) got that wrong. Under uncertainty, default to AMBIGUOUS. This generalizes the evidence standard already stated in NON_GIVEN_NAME_PARTICLES' docstring — a wrong unambiguous claim misparses a real person, a wrong ambiguous marking only adds a flag — from "which set" to "which subset". Applies uniformly to particles, suffix_acronyms and titles.
- **C-ii, vocabulary vs. vocabulary.** Where two sets claim a word and NEITHER reading is a name, precedence is a frequency judgment recorded per word. vd is the live case: never-given particle AND credential acronym (the British Volunteer Decoration), neither of them a name. Decision: the Dutch van der reading, as the more common. That is what unblocks #380, whose trailing-orphan half is a separate decision recorded under its own rule.
- 2026-08-17 — C-i CORRECTED: the position qualifier. Writing the
  per-word records for the never-given particles falsified the first
  draft on the set's most load-bearing member. "De" is a borne Bengali
  and Odia surname (parse("Bimal De").family == "De"), so C-i as first
  written said mark `de` AMBIGUOUS -- which would break "de la Vega"
  and every leading-particle reading. Nothing had tested the criterion
  against `de`, and the error pointed at the safe side, so it would
  never have announced itself as a misparse.
  The qualifier the existing set was already obeying: P1 acts on the
  LEADING position or a lone particle in the GIVEN role, so what
  matters is whether the naming use occupies THAT position.
    van   Vietnamese Văn in given position     collides   ambiguous
    bar   Bar Refaeli, given position          collides   ambiguous
    do    Đỗ leads a surname                   collides   ambiguous
    de    "De" is a TRAILING surname           no clash   never-given
  Consequence, and the reason this is not merely tidier: `das` was
  called ambiguous on #360 under the old reading because Das is a
  borne Bengali surname. Measured, "Anjali Das" and "Bimal Das" are
  unchanged by never-given `das` (the surname is trailing, the rule
  acts leading) while "Maria das Neves" GAINS its particle --
  family="Neves" today, family="das Neves" with it. The old reading
  would have declined a fix. `lo` and `el` need re-judging on the same
  axis; `Lo` does lead in romanized Chinese ("Lo Wei"), so it may
  genuinely collide where `das` does not.
  Corrected on #360, which carried the wrong table publicly.
- The concrete demonstration is "do", which three vocabularies claim — titles, particles/ambiguous, suffix_acronyms/ambiguous. Two mark it ambiguous; the third, TITLES, is the one that actually decides "Do Quang Minh" (title="Do", given="Quang") and reports nothing. Same word behind #385's "Anh Do".
- Applications, each still its own work: #360 (mc, ste — neither is a borne given name, so both leave the ambiguous half); #342 (rai — Rai IS a borne surname, so it earns the marking rather than moving); #385 (do — resolved at decisions.md#R2).
- C-ii's per-word framing versus a rule stated for a SHAPE: measured 2026-08-16, the words that are both particle and suffix vocabulary are vd, do and mc — three, not the one this criterion adjudicated. rules.md#P6 states its precedence for the shape, so do and mc inherit vd's answer without being weighed. Recorded rather than papered over: stating a per-word judgement as a general clause is how an unexamined word acquires a decision, and the two are named here so the next reader knows which one was actually argued.
- Caution when applying C-i to the particle set: TITLES ∩ ambiguous == {do, freiherr, st} is load-bearing, per the Excluded note in the W2 section. Emptying it makes the particle-or-given emitter dead code.

Open: [#348](https://github.com/derek73/python-nameparser/issues/348) applying C-i to the 711 title entries, then titles_ambiguous plus a TITLE_OR_GIVEN kind. Blocked on data, not on judgement — the census needs a given-name frequency corpus this repo does not have, which is why the criterion is recorded here and the census is not attempted.

### suffix-field-composition — three kinds of thing in one field

- 2026-08-16 (suffix keystone; #326) — measured composition of suffix_words (40 entries): 11 generational (i, ii, iii, iv, v, jr, jnr, sr, snr, junior, 2), 5 neither (dr, esq, esquire, ret, vet), and 24 POSTNOMINAL HONORIFICS — 20 CJK (さん, さま, くん, ちゃん, 様, 殿, 氏, 先生, 博士, 教授, 女士, 小姐, 씨, 양, 군, 님, 박사, 박사님, 교수님, 선생님) and 4 Hebrew (ז"ל, ז״ל, שליט"א, שליט״א). The honorifics are the LARGEST group.
- Decision: do NOT split the field. Record the composition; #296,
  #291, #325 and #289 proceed on their own terms rather than
  waiting on it.
- Why #326 cannot be taken at face value: it argues the split is tractable because "the vocabulary is already split — suffix_acronyms is credentials, entirely; suffix_words is generational plus a handful". That was true when written (2026-08-02); the 2.1.0 East Asian work landed 2026-08-07 and put the 24 honorifics in the same set. CLDR's two buckets do not cover what the set now holds, so "adopt CLDR's model" is not available as the cheap answer. The issue's table is corrected on the issue.
- The unexamined question this leaves: whether the honorific bucket belongs in `suffix` at all. rules.md#W3 already argues an honorific is "no part of the name on either side" — the same language the H section uses for prenominal titles — so the conflation with PhD may be worse than the generation/credentials one #326 was filed about. Deliberately not decided here.
- Recorded as a documentation failure mode, not just a fact: `suffix` started generational, absorbed credentials, then absorbed postnominal honorifics, each step locally reasonable and none recorded as a widening of the field's MEANING. rules.md#S2's Background still calls it "two different things", which was accurate when written. The rules doc pinned the behavior faithfully; what slipped is the field's definition, which no rule states because no rule owns it. Field definitions need the same discipline rule statements get.
- The 11/5/24 split above is this entry's own version of the hazard it describes: a quoted vocabulary composition, dated, exactly as
  #326 quoted one. A date does not stop rot — #326 carried one too
  — so before relying on the split, check the set still looks like it:

      uv run python -c "from nameparser import Parser; print(sorted(Parser().lexicon.suffix_words))"

  What is durable here is the SHAPE of the finding — three kinds of thing, the honorifics the largest — not the three integers. A test asserting the counts is deliberately not the answer: that is the constant-content pattern, and it would fail on every legitimate vocabulary addition.

### deviates-registry — packs stay pure data (option C)

- 2026-07-18 (d4aaafa; the DEVIATES design note) — a `deviates` field ON Locale was rejected: callables break value equality and pickle-by-reference, and DEVIATES is acceptance metadata, not runtime behavior (revisit only if a runtime consumer like explain() appears). The REGISTRY became the contract instead: test_registry_is_the_pack_contract fails structurally unless every registered pack ships DEVIATES and its rotator list. This is why LOCALE-PACKS-PURE-DATA can promise "no code paths of their own" and mean it.

### normalization-fold — lower(), not casefold(); comparison folds harder

- 2026-07-17/19 — vocabulary storage normalizes with lower(), NOT casefold(): casefold mutated stored spellings (κος→κοσ, großfürst→grossfürst) while lower() keeps authored forms; the accepted cost, pinned deliberately, is that ASCII-SS GROSSFÜRST no longer matches. The paired half: comparison_key()/matches() use casefold() ON PURPOSE — comparison is the one surface that wants aggressive folding; this is a release-log-classified 2.0 CHANGE from 1.4's lower() (ß and final-sigma forms compare equal only since the v2 core; v1.4 has no casefold anywhere). The 1.x line was symmetric BY DESIGN — lower() everywhere, chosen for symmetry with the parser's lc() convention — so the storage-vs-comparison split is a v2 decision moving away from a real, deliberate alternative, not a fix of an oversight. Do not
  "fix" it symmetric: symmetric is what 1.x was.
- 2026-07 (rc1 arc) — the fold must reach a FIXED POINT, and anything built on it must converge too: _title_key joined per-word folds and kept empty slots, so given_name_titles with a foldable word stored a key match-time could never rebuild — silently inert, and pickle round-trips then rejected the state. Shipped in the rc, caught in review, fixed by dropping words that fold away.

### render-default — the default view's format

- 2026-07-18 (bf1141c) — the default spec is '{title} {given} "{nickname}" {middle} {family} ({maiden}) {suffix}'. Declined the same day: a née-template maiden ('née {maiden}') that round-tripped LOSSLESSLY (née is a maiden marker), rejected on presentation grounds. Accepted cost of the shipped form: a parenthesized maiden re-parses as a nickname.

### P3 — connectives

- 2026-07-30 #267 — the four-word single-letter asymmetry: a bare Latin capital connective is vetoed as an initial while a Cyrillic capital joins. #267's closure ("v2.0 behaves this way by default … verify it was the right call") showed only the Cyrillic half; the Latin-capital veto was never separately adjudicated, which rules.md#P3 records as an Accepted consequence.

Open:
[#383](https://github.com/derek73/python-nameparser/issues/383)
should the Latin-capital veto stand (bless / drop / extend).
- Provenance: the single-letter-connective guard is v1's fix for Google Code issue 11 ("john e smith", 2013, commit 33676c9) — the "#11" citations that circulated pointed at a GitHub accident, not the real source. Recorded so the archaeology stays done.

### given-name-titles — deliberately unvalidated

Declined (rc1 arc; the full argument is AGENTS.md's gotcha):

- Validating given_name_titles against titles, twice: the whole-entry check rejected legitimate multi-word entries; the per-word check rejected "sir and dame" (a conjunction inside a title run is itself a TITLE token, so the key is matchable while its middle word lives in conjunctions). No static relation over the vocabulary sets decides reachability, and an unreachable entry is inert — each guard cost a working configuration to forbid a condition that costs nothing.

### phd-merge — the "Ph. D." split

- 2026-07 (v2 core, PR #288; recorded plan deviation #1 of the core plan) — "Ph. D." tokenizes as two words and is merged back by vocabulary (v1 fix_phd), so the spaced and unspaced spellings read alike.

### O4 — positional assignment and declared order

- 2026-08-07 #83 — romanized Chinese order is answered by DECLARATION, not detection: pinyin carries no signal and diaspora makes locale no guide (the issue's own 2019/2021 conclusions); Policy(name_order=FAMILY_FIRST) is the answer the thread wanted.
- 2026-08-07 #146 — Vietnamese needs the THIRD order constant: measured on "Nguyễn Thị Minh Khai", FAMILY_FIRST strands given="Thị" while FAMILY_FIRST_GIVEN_LAST reads given="Khai", middle="Thị Minh", family="Nguyễn". This is why three order constants exist rather than two.

- Provenance: the three-constants argument originates in #270's own body (2026-07-07): "A boolean family_name_first flag was considered and rejected: Vietnamese order is
  [family][middle][given]." The 2026-08-07 #146 measurement below
  is the verification; #270 is the origin.

Declined:

- Free-form order tuples (('last','middle','first')-style, #270's original draft shape) — the shipped design is exported order constants with tuple rejection at construction (rule D2's
  [bad-name-order] example is the pinned message).
- middle_as_family as the way to suppress the middle slot for Vietnamese (2026-08-07 #146) — measured: it merges the middles into the family, giving family="Thị Minh Nguyễn" for "Nguyễn Thị Minh Khai" under family-first-given-last — a plausible-looking wrong answer. There is no policy field that suppresses middle, and name_order rejects a two-role tuple ("name_order must be one of the exported orders"); given_names (given + middle) is the view that stays correct wherever the internal boundary falls.

### W4 — script-scoped order

- 2026-07-27 (script-scoped order amendment) — the family-first override is keyed to the SCRIPT of the written name, never to a guessed language: wholly-Han, wholly-Hangul, and kana-licensed Japanese read family-first because zh, ko and ja all write family-first in native script; wholly-katakana names are predominantly transcriptions and keep the declared order. Latin transliterations are never touched.
- 2026-07-29 #272 — the kana license: Han∪kana with at least one kana cannot be Chinese and is not a transcription, so 高橋みなみ reads family-first though it is written in two scripts.

### D1 — the segmenterless-activation warning

- 2026-08 #337 — WARN rather than raise, deliberately: registering the JA pack without the extra must stay safe (the inert registration is itself a pinned property), and a warning is filterable by the caller who wants exactly that inertness. The Japanese install hint is conditional — it appears only when a Japanese script is among the dead scripts; a hangul-only gap gets the generic remedies.
- 2026-08 #337 — the warning exists because parser_for(locales.JA) without segmenter= used to build a parser that silently behaved like a working one minus the feature; it re-emits from the parser_for frame so the reported location is the caller's own call.
- 2026-08-07 #339 — diagnostics that hand the reader code must hand code that type-checks: the message's offered deactivation used a bare tuple literal for segment_scripts — an arg-type error under mypy in a py.typed package — and became frozenset(), pinned by a test asserting the offered spelling. The known-bad spelling is in the denylist test. The structural fact behind the recurrence: autodoc renders docstrings into the API reference, so docs/*.rst is NOT the boundary of "the docs" — a guide and the reference can teach different spellings on the same rendered page, invisibly to any .rst-only sweep.

### D2 — construction raises, parse never does

- 2026-07 (v2 core, PR #288) — every raise in the locale-apply path is a plain TypeError/ValueError so the wrap-with-locale-code rewrap cannot break on exotic exception signatures.

Declined (ambiguity kinds for script-resolved names, 2026-07-27):

- A "han-script" zh-vs-ja kind — applying the ZH pack IS the disambiguation; per-name flags after an explicit opt-in are noise.
- ORDER emission for script-resolved names — native-script order is convention, not a guess; the reserved kind stays unemitted. SEGMENTATION fires only on a genuine multi-split vocabulary fork (夏侯惇, 남궁민수).

### H2 — the leading-abbreviation title

- 2026-06-30 (leading-period-title design; v2 core, PR #288) — the shape test is v1 parity (period_abbreviation): two-plus letters then a period, bare initials exempt. Its site is the head of the part CARRYING THE GIVEN NAME — the whole name, or the post-comma part under a family comma — not "the head of the name"; that scope correction is PR #315 (2026-08-01, docs-only), verified against 1.4.0 from PyPI, so the parity claim is real and the narrower description never was. The extraction litmus (2026-08-15): the spec drafted this rule as
  "recognized by vocabulary, not by written shape" and the live
  parser falsified that framing — the shape heuristic is real, and what the abugida gap (#343/#344) shows is its LIMIT, not its absence. Recorded as the rule's Accepted consequence — and the 2026-08-15 landing initially re-narrowed the scope to "name- opening", correcting one error while preserving another; the eighth review round fixed it.

Open: [#316](https://github.com/derek73/python-nameparser/issues/316) what a trailing title-vocabulary word should do (the comma paths disagree today).

### W1 — unspaced CJK division

- 2026-07-27 #271 (decision; shipped in 2.1.0 via PR #294) — Korean division ships as a default: the census surname list is closed, hangul is self-selecting (a hangul entry can only match hangul text), and being unsplit is recoverable while a wrong split is not — which is also why an unrecognized name stays whole. The filed proposal (#271, 2026-07-07) asked for OPT-IN segmentation for Korean too, "like all localization"; default-on is the later refinement, and the census/self-selecting argument above is what justified promoting Korean past the blanket opt-in stance.
- 2026-07-29 #272 (the ja amendment; shipped in 2.1.0 via PR #297) — Han division is opt-in per language pack because Han text does not identify its language (高橋一郎 under a Chinese list divides wrongly); a pluggable segmenter takes what the vocabulary declines, so pack + segmenter compose mechanically: a listed surname is a dictionary certainty and wins.

- 2026-07-29 (ja amendment §1a) — script CLASSIFICATION NFC-normalizes its input (NFD katakana carries combining marks outside the block; NFD hangul decomposes to jamo, which would miss the order rule for macOS-origin names) while segmentation MATCHING stays raw — chosen over offset-mapping complexity because NFD then degrades to no-split, never to a wrong split. The read-only fold is the one deliberate exception to "nothing rewrites the text" (rules.md T Background), and it never enters a token.

Declined:

- JMnedict as bundled segmentation data (#272's body, 2026-07-07) — the pip packaging (jamdict-data) was last compiled 2021-04; JMnedict carries no frequency data, so it cannot resolve the ambiguous 2+2/3+1 splits that motivate a segmenter at all; and bundling raised licensing questions the core avoids by delegating to namedivider — whose code and GBDT model are MIT, whose surname data carries Myoji-Yurai terms permitting exactly this name-dividing use, and whose CC-BY-SA BERT model is unused (the 2026-07-29 amendment corrected an earlier flat-"MIT" description; so does this entry). The kind of decline someone re-proposes in two years.

- 2026-08 — zh and ja packs are corpus ALTERNATIVES, one per corpus; stacking them (parser_for(ZH, JA, segmenter=...)) is for genuinely mixed data that accepts the trade: a listed Chinese surname wins before the segmenter is consulted, so 高橋一郎 still divides 高 + 橋一郎 under ZH+JA exactly as under ZH alone. Kana gating resolves through the same script function order uses, so kana-licensed composites (高橋みなみ) gate in under JA while pure-katakana tokens never do (amendment 2026-07-27: activation is per script because the ambiguity is per script).

### W3 — the writer's divisions are respected

- 2026-08 (segmenter amendment 2026-07-29) — a segmenter answers where an UNDIVIDED name divides, so it is consulted only when the gated token is the name part's only script-written one: "山田 太郎" was divided by its writer and must not have its family divided again. The peeled tail is exempt (that boundary was manufactured, not written); a SPACED honorific is not — at that position it cannot be told from a spaced name element. The trade was measured before deciding: counting spaced honorifics keeps four real surnames whole (佐藤 氏, 田中 様, 鈴木 先生, 中村 教授) and costs the one division 山田太郎 様.
- 2026-08 #312 — under FAMILY_COMMA the whole stage stood down until the peel moved in front of the gate: the comma doctrine is about the input's structure, not the split's source, so it covers vocabulary and segmenter identically, while an honorific is no part of the name whichever side of the comma it glues to.
- 2026-07 — the stage runs AFTER comma segmentation on purpose: running before would make the comma structure depend on the split ("김민준, Jr." pre-split would read suffix-comma on vocabulary alone; as written it stays the listing form).

### W2 — the glued-honorific peel

- 2026-08 #308 — an entry peels only where it can never end a name: 씨/님/さん/様/先生 peel; 양/군/氏/博士/殿 stay spaced-only; 君 is in neither set while its kana spelling くん peels. The vocabulary carries the license, so no structural or per-script gate stands over the peel.
- 2026-08 #312 — the peel crosses the family comma and the 间隔号: both answer where a name DIVIDES into surname and given, a question the peel never asks. Provenance matters here: neither gate was argued for the peel specifically — both came with the placement (#312's own framing) — so the crossing was a repair of inherited gates, not a designed-in property.
- 2026-08 #319 — a wholly suffix-shaped second run is declined as a peel site (the "田中さん, V." shape), but only when the name's own run offers a site, since a glued honorific is itself part of what makes a run read as suffix-shaped.

Excluded (the never-given / ambiguous particle line, nameparser/config/particles.py — #360 owns the vocabulary question):

- Only 9 of the 39 ambiguous members were ever individually justified; the rest sit there by the conservative default (ambiguous unless argued never-given).
- mc, ste — measured misparses ("Mc Donald" → given "Mc"), tracked in #360; st is inert at the head because TITLES claims it first; mac must stay ambiguous because Mac is a real given name.
- Encoding rationale (#293, predating #360's membership questions): the data layer stores the NEVER-GIVEN set and derives the ambiguous one, because that is safe-by-default for new particles — a one-place addition — and the v1 shim translates by one-directional complement. And the constants are FROZEN specifically to kill the cached-Lexicon.default()-vs-fresh- Constants desync that runtime module-constant mutation caused.
- Load-bearing dependency: TITLES ∩ ambiguous == {do, freiherr, st} is what keeps the particle-or-given ambiguity emitter reachable at all; moving all three would make it dead code, which is why test_the_chained_emitter_is_still_reachable distinguishes "pick another word" from "delete the emitter".

Open (contested vocabulary memberships — the rule is right, the word's set is questioned; the issue is canonical):
[#342](https://github.com/derek73/python-nameparser/issues/342)
rai in SUFFIX_ACRONYMS vs. the South Asian surname ·
[#346](https://github.com/derek73/python-nameparser/issues/346)
swami and the renunciate titles absent from the given-name-title set ·
[#343](https://github.com/derek73/python-nameparser/issues/343) /
[#344](https://github.com/derek73/python-nameparser/issues/344)
Bengali and Devanagari honorific vocabulary.

Excluded (SUFFIX_ACRONYMS / SUFFIX_WORDS — the esq dual membership, deliberate; AGENTS.md's gotcha carries the full algebra):

- esq is in BOTH sets and must not be "deduplicated". The load-bearing membership is the acronym one (it carries the multi-dot spellings: removing it costs "John Smith E.S.Q." its family name); the word membership is inert as shipped but is what keeps "Esq" matching for a caller who edits suffix_acronyms themselves. esq is the ONLY member of SUFFIX_ACRONYMS ∩ SUFFIX_WORDS — that singleton is why the two sets cannot carry a disjointness assert, which is the standing cost this entry defends. Deliberately no changed-parse count — the count is a property of the measuring grid, not of the code.

### P5 — bound given names

- 2026-06-30 (first-name-prefix-join design; v1-era, carried into the v2 port) — the join is vocabulary-driven and deliberately tiny.

Excluded (BOUND_GIVEN_NAMES):

- mohamad — a standalone given name in its own right; binding it would eat the middle name.
- abd — collides with the academic post-nominal "ABD", and the real form is the deferred multi-token "abd al rahman".

Excluded (DEFAULT_NICKNAME_DELIMITERS):

- Curly single quotes ('‘','’') are deliberately absent from the default pairs: U+2019 is the typographic apostrophe (O'Connor in curly type), so shipping the pair would eat real names. #273's own proposal excluded them; pinned by the curly_apostrophe_stays_literal case. A sweeper "completing the typographic set" ships the regression.

Excluded (given-name titles and post-nominals — the 2026-07-19 transliteration deferrals, each living in a data-module comment until now):

- Arabic bare سيد/شيخ/أمير/سلطان — given-name collisions (Sayyid, Shaikha, Amir, Sultan); the honorific forms with the article (الدكتور, الشيخ) ship instead.
- The abbreviation د. — edge-period normalization leaves bare د, the single-letter trap; Greek bare κ deferred on the same grounds.
- Ottoman post-nominals باشا/بك/أفندي — surname collisions.
- Hebrew bare רב (an ordinary word, "many") and בר (Bar is a common modern Israeli given name) — deferred, #269's territory.
- Latin sri/shri deliberately absent while Devanagari श्री ships: the transliteration collides (Sri Mulyani), the native script cannot.

Excluded (multi-word vocabulary entries — every set matches one written word, so a multi-word entry is silently inert and now warns at configuration):

- Eight entries shipped unmatchable from 2013 to 2.0. chargé d'affaires was SPLIT into the chainable chargé + d'affaires, plus unaccented charge (the attaché/attache precedent, Derek's call); leed ap, nicet i–iv and psm i/ii were REMOVED rather than split, on the name-swallowing measurements recorded in #291 (see the comma-suffix-arc Declined entry). The multi-word UserWarning is this story's enforcement.

Excluded (Lexicon.honorific_tails — a glued tail peels only if it could never end a name; per-entry reasons live in nameparser/config/suffixes.py's vetting block):

- 양, 군 — 김지양 and 김지군 are given names ending in these syllables, and 양 is a top-tier surname (Yang) besides. (The surname-LEADS argument is a different job: it is why both are safe in the SPACED set — a leading surname never meets the trailing-only suffix gate, so 양 미선 keeps family 양.)
- 氏 — 王氏 is a historical name form ("the Wang woman").
- 博士 — 田中博士 is Tanaka Hiroshi as readily as Doctor Tanaka.
- 殿 — Japanese surnames end in it (鵜殿, 真殿, four-figure populations); peeling it would cut a real family name in two.
- 君 — 王君 is a complete Chinese name; its kana spelling くん does peel.
- जी (standing prohibition for #344's implementation) — Banerjee, Mukherjee and Chatterjee end in the substring (बनर्जी/मुखर्जी/चटर्जी), and glued peeling strands a fragment on a bare virama (बनर् + जी). The 殿 criterion, in a non-CJK script — which also shows the criterion is not CJK-specific.

Excluded (TITLES):

- ঠাকুর — a genuine Bengali honorific (lord/master) that is also Tagore, the surname (#343 records it so a wordlist sweep does not ship it).
- The trailing-position rule that must NOT be adopted: TITLES holds hundreds of words in no suffix set, at least nineteen of them ordinary English surnames (king, judge, bishop, baron, sheriff, ...), so a blanket "vocabulary outranks position in the trailing slot" reading would turn "Mary Jane King" into title="King" with the family name gone. The leading half of this argument is AGENTS.md's "Dean is deliberately absent" gotcha; this is the trailing half, and it shadows the family name rather than the given (#316).

Excluded (Policy.script_orders defaults): Script.KATAKANA is deliberately absent — a pure-katakana token is predominantly a transcribed foreign name kept in its source order, so nothing defaults on it (rule W4's boundary). Noted 2026-08-15: of the three Script-keyed axes, this is the one with no force-a-decision guard (mechanisms.md#FORCE-A-DECISION-TABLE), so a new Script member silently gets no order.

Excluded (MAIDEN_MARKERS, per nameparser/config/maiden_markers.py):

- Polish "z domu" — a two-token marker; pending the multi-token matching decision, tracked in #291 since 2026-07-27.
- Contrast entry — unaccented "nee" SHIPS as a marker despite
  #274 flagging "is nee safe as a default (it's also a rare
  surname)" as open; the question resolved silently with the shipped set. Recorded here because the included risky member deserves its analysis as much as the excluded ones; M1's (Nee) boundary covers only the enclosure path, not this marker path.
- "born" — never shipped: a release-log drafting invention, caught by the 2.0 milestone audit and corrected (5ccf9f3). Recorded so nobody "restores" it; if ever proposed for real, Max Born is the counterexample to analyze.
- Scandinavian "f." — collides with the initial F.; only the full participles (født/fødd/född) are safe. Czech masculine "rozený" awaits the same vetting.

### C1 — the suffix-comma decision

- 2026-07 (v2 core, PR #288) — v1 parity: only the second segment decides (v1 parser.py:1318), and ">1 word before the first comma" is v1's guard, which is why "Smith, PhD" keeps the listing form. The strict/lenient knob's blast radius on default vocabulary is exactly the single-letter Roman numerals i and v — the only initial-shaped members of the shipped suffix words — which is what makes rules.md#C1's "V." examples the canonical pair.
- 2026-07 (plan deviation #3, recorded) — the decision is definitionally vocabulary-dependent: there is no way to recognize a credential run without consulting the suffix word lists, so the structural stage reads vocabulary through one predicate.
- 2026-07-12/13 (v2 Policy work, PR #288) — the lenient token test is the default and `lenient_comma_suffixes=False` restores the strict one. (An earlier entry here credited #291/#296 — git author dates place both the field and its wiring in the Policy commits, and the #291/#296 design doc never mentions the knob.)
- 2026-08 #319 — the wholly-suffix predicate was lifted into the vocabulary layer so the comma decision and the honorific peel's segment test cannot drift apart.

### T1 — separators, not joiners

- 2026-07 (v2 core, PR #288) — v1's squash_emoji/squash_bidi REMOVED the character and joined its neighbors. (v1.3.0 had no bidi handling at all: squash_bidi entered late v1 via #266, 2026-07-07, on the emoji precedent's shape.) ('A😀B' → 'AB'); v2 makes an ignorable character a separator ('A😀B' → 'A', 'B'). The unavoidable consequence of every part being an exact positioned piece of the input: with no rewriting stage, nothing can splice two half-words together.

### T3 — the interpunct's flank guard

- 2026-07-30 #298 — codepoint scope, chosen over a blanket
  "dot = transcription" rule that would have flipped 高橋・一郎, a
  correct and deliberately pinned #272 reading: U+00B7 records the transcription fact and suppresses division; U+30FB/U+FF65 stay pure separators whose pieces the script license reads (rule W4's Accepted pair demonstrates both). Cross-convention input reads by the codepoint it was actually typed with — a chosen limitation, recorded in #298's comments.

Declined:

- Ambiguity emission on a half-flanked interpunct ("王·Smith") — proposed in the 2.1 PR review, declined because the dot decides silently under the no-emission decision; the undivided-dot-stays-in-the-word behavior went to docs instead.


- 2026-07-30 #298 — U+00B7 divides only between classified-script characters because it is also the Catalan punt volat, interior to legitimate names (Gal·la). The nakaguro (T2) needs no such guard: its codepoints are CJK-only and appear in no other script's names, which is what licenses an unconditional rule.

### M1 — delimited maiden names

- 2026-07-03 (maiden-bucket design, landed via the v2 core, PR
  #288) — the maiden reading of a delimiter pair is opt-in because
  enclosure conventions genuinely vary; there is no default pair.
- 2026-07-18 (cc7063f; Derek's proposal out of a docs-review pain point — routing parens to maiden used to require editing both buckets in tandem, and the nickname default's contents were not discoverable) — bucket overlap is canonicalized before parsing: a pair listed for maiden is dropped from the effective nickname set (maiden wins), and the public DEFAULT_NICKNAME_DELIMITERS constant landed with it. The v1 facade restores v1's nickname-wins reading by pre-subtracting on its side. Weighed and ruled the same day: maiden-wins applies THROUGH apply_patch too — a pack's maiden pair silently removes a user's unrelated explicit nickname pair; warn-on-removal was considered (a silent-failure review flagged the site) and rejected, the silence ruled intended.
- 2026-08-04 #329 (PR #331) — the marker word inside a delimited clause is dropped from a multi-word clause during grouping; the extraction itself keeps the whole enclosed span, so nothing is lost when there is no marker. Three decisions argued separately: the clause-size guard exists because Nee is an attested surname (Irish Ní/Nee, a Chinese romanization) — load-bearing, not defensive, and mutation-proven; clauses are independent — "(Nee) (Jones)" reads maiden "Nee Jones", each clause dropping or keeping its own marker (the first implementation leaked across clauses, a real defect); and the contentless "(née —)" alone now parses to every field empty and bool() False (an explicit alternative keeping maiden "née —" was rejected; pinned by the maiden_marker_delimited_content_free case).
- M1 and M2 are disjoint by construction, which is the no-conflict guarantee: M2's walk covers joining structure that role-bearing words never enter, while M1's drop reaches only extracted content. Verified independently at review over 7,775 records: 967 diffs, every one in the maiden field.

Declined:

- Neighbour-scoping the drop (drop a marker whose next word also reads maiden) — implemented, reviewed and rejected: it also fires on the bare-marker path, eating the surname out of "Jane Smith nee Nee Jones" (maiden "Jones" instead of "Nee Jones"), and it leaks across adjacent clauses. It is the obvious implementation, which is why this entry exists.

- 2026-08-05 #329/#335 — marker auto-detection inside a nickname-delimited clause was deferred to #335 on a corpus measurement: 山田 花子（旧姓 佐藤） is in the CJK differential corpus so the #329 change was gate-visible, while "Jane Smith (née Jones)" is in no corpus — shipping auto-detection in 2.1 would have let a real Latin-affecting change ride under a "0 Latin-only" gate report.

Open: [#335](https://github.com/derek73/python-nameparser/issues/335) should a marker inside a NICKNAME-delimited clause flip it to maiden without configuration.

### O1 — East Slavic rotation

- (v1 era, PR #154) — why patronymic handling is OPT-IN at all: unconditional detection breaks ordinary Latin names whose endings collide (Martin, Franklin, Benjamin), the finding that forced v1's Russian work behind a flag and set the opt-in shape v2 inherited.
- 2026-07-12 (landed in the v2 core, PR #288) — v1 parity pinned live: the rotation reconstructs token position from assigned roles, which is faithful to v1 only under the default given-first order.

- 2026-08-15 — the rotation × non-default name_order interaction question rode #270, which closed 2026-07-28 with the order constants and no recorded answer for the rotations.

Open:
[#384](https://github.com/derek73/python-nameparser/issues/384)
what the rotations should do under a non-default name_order (the divergent measurement is in the issue).

### O2 — Turkic rotation

- 2026-07-02 (Turkic design; landed in the v2 core, PR #288) — shape fixed at exactly four name words (1 given + 2 middle + 1 marker), v1 parity; other shapes keep their positional reading even when that leaves the marker in a name field (see the rule's Accepted consequence).

- 2026-07-02 (design, orthography coverage) — dotless ı does not case-fold to i, so qızı is a literal alternative in the pattern (re.I cannot bridge it; all-caps QIZI falls to the ASCII alternative); the patterns are NFC literals and NFD input does not match. Scoping decline: suffix-attached Kazakh/Uzbek patronymics (Әбішұлы) are bound-suffix morphology, not a standalone marker, and deliberately out.
- 2026-08-15 — same rotation/name_order interaction status as O1.

Open:
[#384](https://github.com/derek73/python-nameparser/issues/384)
same question as O1.

### differential-ledger — tooling decisions (2.1.0 release arc)

Harvested 2026-08-15 from the release-arc session; measurements are that session's, spot-checked at landing.

- 2026-07-24 (rc1 arc, predating this section's window) — the TWO-CORPUS design: corpus_issues.jsonl (198 tracker-harvested names, 166 absent from the v1-test-bank corpus) exists because v1 test banks are structurally blind to anything 2.0 added; compare.py globs corpus*.jsonl and fails loudly on none. Its first catch was the leading-credential case ("Ph. D. John Smith" → suffix).

- 2026-08-05 #332 — ledger field vocabulary is Role's names, not the facade's: canonicalizing to first/last would have put an eighth place naming roles differently from Role inside the durable record, and the facade vocabulary is removed at 3.0.

Declined:

- Policy annotations widened to input unions (2026-08-05 #334) — five documented spellings fail mypy and every one has a type-clean equivalent; widening would make every READER see a union, and reading is the commoner operation. A .pyi stub typing __init__ wide and attributes narrow was deferred as a 3.0 candidate (needs a parallel signature list with its own sync test).
- Closing the differential gate's default-policy ceiling (2026-08-04 #332) — a per-row policy in the corpus needs defined behavior for baselines that cannot construct newer policy fields; tests/v2/cases.py already covers opt-in paths per row, so the ceiling is documented instead.
- `_check_tree` as is_relative_to(REPO_ROOT) (2026-08-05 #332) — accepts .venv/, build/ and dist/ copies inside the repo; the invariant is "is the source package", so the predicate is is_relative_to(REPO_ROOT / "nameparser").
- Empty-string probe as the ledger over-match guard (2026-08-05
  #332) — `.`, `.+`, `\b`, `[\s\S]` all decline "" and still match
  every corpus name; replaced by the sentinel set (mechanisms.md#SENTINEL-SET-OVER-MATCH-CHECK).
- "Lists every role" checked against all eight fields entries (2026-08-05 #332) — a seven-role list passed while omitting _ambiguities, which below baseline 2.0 cannot enter a diff at all; the check is against V2_FIELDS.
- A seed ledger rule with name_regex and no fields (2026-08-05
  #332) — it matched every CJK-bearing name and would have
  classified all 89 diffs on the first pass, exiting 0 having distinguished nothing.
- 2026-08-07 #333 — the canonical-rule selector (keyed on literal
  #271/#272 slug substrings) was deleted rather than repaired,
  option A of three: split "every hand copy equals the table" (the sweep's job) from "the table did not change shape without a decision" (the span-bearing test's job), so a selector break can never take the decision gate out as collateral. This retired the slug taboo an earlier mechanisms.md entry carried.
- The B7 sanctioned-extra span (pre-#332 arc) — added, then removed as a pure loss when review measured that every B7-divided name already matches through its guaranteed classified flanks, so the span's only effect was absorbing punt-volat Latin regressions ("Gal·la Marcet" probes on both sides, recorded in PR #305's history). The cleanest "sanctioned extras must be earned" precedent the ledger has.
- An issue for rotating DEFAULT_BASELINE (2026-08-07) — it recurs every release; it lives in the AGENTS.md release checklist beside the VERSION bump instead (#333 must land first).

Excluded (ledger name_regex patterns — one over-matching rule shadows the whole ledger, since name_regex rules sort first): "",
"(?:)", ".", ".+", "\b", "[\s\S]". Enforced by the sentinel-set
check.

### differential-ledger, the dormancy arc (2026-08, #328–#376)

The second ledger arc; measurements are that session's, the machinery verified present at landing.

Decisions that landed:

- 2026-08 #328 — `[[never]]` exclusions: ledger vocabulary for
  "this shape must never be explained". classify() consults
  exclusions before rules, which makes them MONOTONE — an entry only ever removes a name, never moves one between rules — so an exclusion's blast radius is exactly the names it captures, independent of rule order.
- 2026-08-12 #373 — `dormant = "<reason>"`: a rule explaining nothing fails the run in both directions, with three diagnoses (reverted / shadowed by X / refused by a [[never]] entry). Always on, not behind --strict: a check nobody passes a flag to is a check that doesn't exist.
- 2026-08 #373 — `--baseline 2.0.0` joined the release checklist: that ledger's rules had no dynamic coverage at all; measured clean at 90/0, so the gap was closed rather than documented.

Declined:

- Ambiguity reporting on multi-matching rules (#372/#373) — measured: 28% of claimed name×role pairs already have ≥2 matching rules (732 of 2619; 432 are one pair of rules alone). A report firing on 28% of what it inspects is wallpaper. The actionable slice shipped as the "shadowed by <issue>" diagnosis, which speaks only on FULL shadowing.
- A specificity floor for fields-only rules (#372/#373) — exactly one fields-only rule exists in any ledger, naming 3 of 7 roles; a six-of-seven floor matches nothing, and nothing would reveal it vacuous.
- Specificity reordering of the rule sort (#328) — measured across all 751 names: width-then-regex-length moves five rule populations and sends 17 names into the generic fields-only rule, draining the CJK-specific ones. No reading of the sort produces the "exactly one label changes" originally claimed; that figure was corrected on the PR.
- Unanchoring the honorific-suffix rule to reach glued forms (#376) — it would make a future suffix regression on 김지양 classify as a recognized honorific. A confidently wrong label is worse than a catch-all's honest breadth, and the gate reads the same either way.

### comma-suffix-arc — #291/#296/#316 (2026-07-26 → 2026-08-01)

#291 was filed 2026-07-26 out of the 2.0 vocabulary cleanup, with
its decline-by-measurement evidence in the issue body; "z domu" folded into it 2026-07-27 (see Excluded, MAIDEN_MARKERS). Intent for #291 and #296 is settled by the approved bundle spec but UNSHIPPED — rules.md carries both as deviates: markers on C1. The arc's bookkeeping: #291/#296 moved milestone v2.1 → v2.2 on 2026-08-01 (with #289/#293); the 2026-07-30 design doc was amended in place 2026-08-01 (A1–A6); its durable content is HERE rather than in the gitignored doc; #316 (trailing titles) was filed the same day, carrying the esq cleanup as a Related section.

The approved 19-word TITLES∩suffix audit table (2026-07-30/08-01, intent for the unshipped bundle): jr, junior, phd, md, do and se DROP from TITLES (se: Structural Engineer is the PE/SE post-nominal pair, no prenominal convention — v1 residue); dr drops from SUFFIX_WORDS and sra from the suffix sets (v1 residue); sr, lt, cpl, cpt, cpo, csm, sgm, ra and vc KEEP dual membership (position decides); ms and sa keep dual membership AND join the ambiguous set (the periods gate). Derek's framing thesis for the whole table: v1's sets encoded where the v1 PARSER needed words to be, not where words can occur. Amendment A6: once SUFFIX_PHRASES ships, the glued peel's token-level post-nominal test cannot step over a phrase segment ("김민준씨, LEED AP" will not peel) — #291 owns deciding that, with a case row either way.

- 2026-08-01 (plan amendment 1, Derek's call: "ship + repair the merge") — dropping dr/ms from the suffix vocabulary flips segment() to FAMILY_COMMA and degrades "John Smith, Dr." to family="John Smith" (mechanisms.md#VOCABULARY-FEEDS-STRUCTURE is this shape); the approved repair, ordered FIRST in the bundle so no commit introduces a regression a later one heals: assign segment 0 positionally when segment 1 is nothing but titles.

Declined:

- Splitting the dead multi-word suffix entries into single-word entries (2026-07-26, the evidence in #291's body) — measured:
  "Smith, A.P." has the suffix steal the given initials; "John
  Leed" and "Mary Nicet" lose family names; and the period-gate escape is equivalent to removal because nobody writes "L.E.E.D.". This decline is why the seven removable entries were REMOVED in 2.0 rather than split, and it is the missing history behind C1's
  #291 marker.
- The trailing-abbreviation structural fallback — with a measurement LIMIT rather than a measurement: the differential corpora structurally cannot evidence it, because they hold only names someone wrote down, and an unrecognized abbreviation is by definition outside the vocabulary. A green run there proves nothing (the reusable harness fact is in mechanisms.md's field notes).
- SUFFIX_PHRASES matching in assignment — measured cost: it renders suffix="LEED, AP", because the suffix view comma-joins suffix words unless they carry the stable "joined" tag, which only grouping applies. The general form: multi-word vocabulary must merge where the render tag is applied, not where the role is assigned.

### api-churn-declines — do not re-propose without new cause

Declined (2026-07-06, the post-1.3.0 modernization sweep; each on churn-outweighs-benefit grounds): the hn.C → constants rename; capitalization-knob consolidation; the logger rename. (Lenient matching, declined in the same sweep, is recorded under comparison-surface.)

### initials-repertoire — is_initial across scripts (#320)

- The principle: alphabetic-vs-CJK, not Latin-vs-non-Latin — Han, kana and hangul characters are morphemes or syllables, so a single one cannot stand in for a name word, while any alphabet's single letter can. _NO_INITIALS is ENUMERATED per script rather than derived from the script ranges, so a new Script member forces a decision instead of silently deciding Thai has no initials.

Declined:

- Narrowing is_initial to [A-Za-z] — measured: "Й." regresses to the #267 Ukrainian-conjunction misreading (the exact regression 2.1.0's release log claims to prevent), and the stable "initial" tag silently strips from every Cyrillic, Greek, Arabic and Hebrew initial, invisibly to the fields.

### comparison-surface — why value equality died, and what replaced it

- 2026-07 (1.3.0 arc, #223/#224; executed in the v2 core — measured: HumanName == HumanName is False, matches() and comparison_key() live, the facade cites #223) — the trilemma: case-insensitive equality, equality-with-plain-strings, and hashability are mutually inconsistent (a hash cannot equal both hash("John Smith") and hash("john smith")), so 1.2.0's design was unfixable in place, not merely disliked. Additional costs of the old surface: equality ran through str(self) and so depended on mutable string_format, and maiden was invisible to == (absent from the default format).
- 2026-07-06 — the cross-constants asymmetry, pinned: a str operand is reparsed with self.C; a HumanName operand is compared as already parsed.

Declined:

- Component-based __eq__/__hash__ — workable, considered, rejected: it still privileged one equality semantic for a domain that has none, and kept the mutate-while-hashed hazard.
- Lenient matching (initials-compatible, Bob/Robert) — declined WITHOUT an issue, deliberately: matches() is exact-components by design. Someone will propose could_match() within a year; this entry is the resolved-as-no they should find.

### R2 — the all-particles family_base divergence

- Recorded 2026-08-16, intent UNVERIFIED: the v1-era design held that a family name cannot be only particles ("Anh Do" — Do is a surname AND a particle), so last_base was guarded non-empty. The facade still guards (HumanName("Anh Do").last_base == "Do"); the v2 core does not (parse("Anh Do").family_base == "", family_particles == "Do"), and the surname vanishes from initials (parse("Anh Do").initials() == "A.").
- 2026-08-16 #385 RESOLVED by the collision criterion, not on its own terms: the issue's option 3 ("guard the view only when a word is vocabulary-ambiguous") is what decisions.md#vocabulary-collisions produces when applied here.
  "Do" is borne as an ordinary surname, so it is ambiguous
  vocabulary and anchors the base; "van der" is never anyone's name, so an all-particle family there genuinely has no base. The two rows of the issue's table were never one case. This is the keystone's clearest payoff: #385 was filed as a leaf with three options and no way to choose between them, and the criterion picks one without arguing about family_base at all.
- Still open inside the resolution: whether "Do" remains in family_particles once it is also the base. Recorded here rather than left to the implementing PR to decide by accident.
- 2026-08-16 (pre-merge coherence pass) — the resolution moves R3 too, and R3 now carries its own marker. Initials read the BASE family word, so anchoring "Do" changes parse("Anh Do").initials() from "A." to "A. D." while
  "Juan van der" stays "J." (no borne name, no base, and initials
  of a bare particle run would be nonsense). The general lesson, worth more than this instance: a deviates: marker gets written on the rule whose STATEMENT changed, but a rule can change another rule's OUTPUT without touching its statement, and nothing looks for that — the runner asserts per example line, so an unmarked downstream rule stays green precisely because its own examples avoid the affected input. When adding a marker, walk the changed rule's `interacts:` targets and ask whether any of THEIR examples move.

### removed-v1-surface

- empty_attribute_default: removed in 2.0 (#255; deprecated in 1.4 per the bridge discipline). Origin #44 (2016): a DB-NULL convenience whose first answer — `name.title or None` — became the migration path. The in-band-signaling bug that sealed it (#254): the 2016 `.replace('None','')` scrub could not tell interpolated None from name text, so "Nonez Smith" rendered
  "z Smith" — the fix shape, worth keeping as a one-liner, is
  SUBSTITUTE BEFORE FORMAT, never scrub after. Two removal cautions shaped the implementation: tombstone-not-deletion (a plain deleted attribute would make assignment silently accepted-and-ignored, the #241 failure family) and readers-not-just-writers (#44's own thread advised asserting against the attribute, so reads existed downstream). The tombstone and pickle-tolerant load die with the shim. (An earlier 3-0-reevaluations bullet said "left untyped, typeable in 3.0" — promoted from a memory that was already three days stale when written; nothing is left to type.)
- bytes input: removed in 2.0 (#245; decode-first DeprecationWarnings shipped 1.3.0 per the bridge discipline); the shipped TypeError carries the decode hint.
- no_vowels: removed in 2.0 (#268, filed 2026-07-07, closed 2026-07-28) — never consulted by any parser version, ASCII-only; the facade carries no replacement because there was nothing to replace.

### script-table-placement — a recorded reversal

- 2026-07-29 (script-ranges relocation) — REVERSES #271's documented choice ("tables deliberately live in _vocab"): the tables moved to _policy because packs cannot import the pipeline, evidenced by two hand copies with sync tests and a blocked 16–30× compiled-regex optimization (a module-level re.Pattern in a pack would flip its classification, hence the closure-held-pattern convention). Rider: U+3006 〆 joined the HAN span on a justification deliberately beyond UAX #24 — it is Script=Common but appears solely in Japanese surnames (〆木, 〆谷, 〆野).

### 3-0-reevaluations — decisions shaped by the v1 shim

Promoted 2026-08-15 from session memory (Derek's 2026-07-30 ask; promotion approved 2026-08-15). Discipline when appending: mark each entry (A) "would decide differently without the shim" — real 3.0 work — or (B) "cited 1.4 parity but stands on its own", recorded so nobody re-litigates it. Append here whenever a design choice cites 1.4 parity or the shim as a load-bearing reason. Standing discipline for the removals themselves: every removal warns in a RELEASED version first — the rule established by the 1.3.0 eq/hash work (#223/#224), the reason the v1.4 milestone existed, and the reason FACADE-CONTRACT's "warning-free on 1.4" anchor works at all. 3.0's shim removals follow the same bridge. The CONVERSE rule, declined-with-reasoning twice in the migration design (2026-07-11): a bridge warning must WAIT when the replacement does not yet exist — 1.4 warned on neither shared-CONSTANTS mutation nor the subclass hooks, because users had no actionable response until 2.0, and #262's contract docs shipped in the same release (warn-while-documenting is a mixed message).

- (A) v1 field vocabulary at the facade boundary: CJK semantics squeeze into first/last through HumanName while the core speaks given/family. 3.0 could drop the aliasing entirely.
- (A) Render's v1-inherited string_format defaults, including space-joined output for interpunct transcriptions (#298: str(HumanName("威廉·莎士比亚")) == "威廉 莎士比亚"; users reinstate the dot via custom format). 3.0 render defaults are a clean slate.
- (A) The differential harness baseline is 1.4-on-PyPI: post-shim, the migration promise it verifies dissolves; the successor baseline is presumably last-2.x. Machinery survives; corpus contracts change.
- (A) A .pyi stub for Policy (wide __init__, narrow attributes) — deferred from #334, see the differential-ledger Declined entry.
- (A) nameparser.config removal scope: the 3.0 schedule says
  "nameparser.config in its entirety" while actually enumerating
  only the five shim exports; whether the DATA modules keep the package as their home or move under the core is open, and Lexicon's public field docs cross-reference nameparser.config.particles et al. (see the maintainer note in nameparser/config/__init__.py).
- (B) Pickle-guard layout breaks landing in minors (2.1's __setstate__ breaks): the guarded-raise design is right regardless; only the in-a-minor friction is shim-era.
- (B) Positional-read-when-unlicensed as the safe direction (script_orders fallbacks, #298 dot-suppression granularity): coincides with 1.4 parity but stands alone — family-first is the marked case needing affirmative evidence.
- (B) The deprecation-bridge shape (#293/#354) is the template for every remaining 2.x→3.0 shim (the bridge DISCIPLINE — warn in a released version first — predates it, from #223/#224; this entry is the module-__getattr__ mechanics): PEP 562 module __getattr__ PLUS __all__ (star imports never reach __getattr__ — measured: `from ...prefixes import *` bound nothing and leaked the helper); warn per read-location rather than per process (a write-back let a vendored dependency's first read consume the only warning); and the TYPE_CHECKING split, because a module __getattr__ silently disables mypy's attr-defined checking for the whole module (measured on a py.typed package).
- (A) Parking lot from the 2026-07-06 config-model discussion, 3.0-shaped by design: scoped config override via contextvars (`with nameparser.config.use(c):`, the decimal.localcontext pattern — fixes test pollution and config wars while keeping the shared default), and a requests-Session-style Parser(constants) API (rejected then as a full rewrite; the shared CONSTANTS survives 2.x because it is the only config channel that reaches parses inside code users don't own — #262's contract framing).
- (B) The 1.3.0-era legacy-pickle property-key skip (suffixes_prefixes_titles in old blobs) rides in the shim's __setstate__ and dies with it.
- (B) The FAMILY_COMMA doctrine (rule W3): inherited from v1's lastname-comma but correct on its own terms — an explicit comma is stronger evidence than script.
