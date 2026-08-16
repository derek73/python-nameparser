# Decisions

The why behind the rules: a lightweight ADR log, keyed by rule ID
(`### P2 — <short name>`), by mechanism slug, or by a short slug for
cross-cutting and tooling decisions. Section headings carry the key,
so every `decisions.md#P2` reference in code or rules.md is a live
anchor.

Entry conventions:

- **Dated decision entries**, append-only in spirit: a reversed
  decision is not edited, a later entry supersedes it. Each entry
  cites its issue or PR. The date is the DECISION's, never the
  release's (add "shipped in X" alongside if useful), and git
  author dates outrank remembered ones — two review rounds
  corrected exactly these two errors.
- **Harvested entries** (content landed from a session's report)
  keep their provenance: a "measurements are that session's,
  spot-checked at landing" framing line, the contributor's
  measured-vs-remembered markings where they matter, and — the
  hard-won one — a flagged uncertainty is resolved by reading the
  source artifact, never by inference from the neighboring
  argument.
- **`Declined:`** — proposals rejected WITH the evidence that killed
  them. Resolved-as-no is a decision; without a home for it, the next
  person re-derives the rejected proposal and its measurement.
- **`Excluded:`** — standing prohibitions with indefinite lifetime,
  keyed by vocabulary set: entries that must stay OUT of a wordlist,
  each with its reason. Distinct from Declined because the failure
  mode differs — nobody re-derives a rejected proposal, but someone
  sweeping a wordlist ships the excluded entry as a bug.
- **`Open:`** — unresolved questions as issue links with one-line
  handles. The ISSUE is canonical; this block never restates it.
  Two keyings: under a rule ID for questions about the rule, and —
  like `Excluded:` — keyed to a VOCABULARY SET for contested
  memberships, the category neither `deviates:` nor `Excluded:`
  covers: the rule is right and a word's set membership is the
  question (rai in the suffix acronyms, swami absent from the
  given-name titles). Place the block beside the set's `Excluded:`
  entries so a wordlist editor meets both.
- **Weighing entries** for contested questions: the options
  considered, each option's intended effect, and the accepted costs
  of the option chosen. The costs accepted here are the artifacts
  rules.md lists under the rule's `Accepted:` consequences; the two
  link by rule ID.

### legacy-rule-numbers — the old docstring numbering

Before rules.md, the post_rules stage docstring numbered its rules
locally, and historical issue comments (#359, #364, #365, #367) use
those numbers. The mapping: rule 1 → H1, rule 1b → P1, rule 2 → O1,
rule 3 → O2, rule 4 → O3.

### P1 — lone particle fold

A lone PIECE is the whole test — deliberately narrower than "a
never-given particle is never reported as the given name," which
would be false (the over-broad invariant shipped to five sites
before #361's review falsified it with three counter-examples).
The counter-example set has since shrunk, and its shrinkage is the
section's history: "Sir de Mesnil" fell to #367 (titles became
transparent); "Juan de la Vega" under family-first — the whole
chain in the given position — was called working-as-intended by
#359, but #368 SUPERSEDES that sentence: the recorded decision is
that the particle wins and a chain becomes the family name
whatever order was declared, so that case is now P1's tracked
deviation, not its boundary. The survivor is the degenerate bare
"de". The MIDDLE position is deliberately not a fold site — and
not merely unimplemented: the two family-first orders disagree
there ("Mesnil Garcia de" strands middle="de" under FAMILY_FIRST
and folds under FAMILY_FIRST_GIVEN_LAST, 464 measured inputs),
which is what makes #365 a decision rather than a gap.

- 2026-08 #359 — the opening site is read from joining structure
  (pieces), not from assigned roles, so the fold holds under every
  name_order. Before this, the role-only read let "de Mesnil" split
  under a family-first order.
- 2026-08 #367 — titles are transparent to the fold: "Sir de
  Mesnil" now reads like "de Mesnil". Fixed by removing the
  title→particle chain in grouping, not by touching this rule.

Declined:

- A strict xfail asserting "de Mesnil" → family under FAMILY_FIRST
  (#359 review) — #359 deliberately left those semantics open, and
  a strict xfail decides the question by the back door.
- Keying the leading-particle exception on "the first piece that is
  not a title" — the obvious implementation, and wrong: st, do and
  freiherr are titles AND ambiguous particles, so it collapsed
  "St John Smith" into one given name and broke test_add_title
  (which adds "te", also a particle). The shipped predicate is
  "not a title or a prefix".

Open: [#364](https://github.com/derek73/python-nameparser/issues/364)
how much the fold takes ·
[#365](https://github.com/derek73/python-nameparser/issues/365)
should the middle position be a third site ·
[#360](https://github.com/derek73/python-nameparser/issues/360)
which particles count as never-given.

### P2 — particles join forward

- 2026-08 #367 — REMOVED a chain, it did not create one: before,
  the title displaced the particle out of the leading position, so
  "Sir de Mesnil" grouped [Sir][de Mesnil] — a chain — and
  reported given="de Mesnil" with no family at all. After, "de" is
  the leading name piece, and a leading particle chains nothing
  (rule P4): the family reading comes from P1's fold, which is why
  P1's fold needed no change (its interacts: points here). Grouped
  today: [Sir] [de] [Mesnil].

### M2 — the maiden-marker rule

- 2026-07-03 #274 (v2 core, PR #288) — the marker takes everything
  after it up to a trailing suffix, greedily: "née Jones Smith" is
  a two-word maiden name, matching how the marker is actually used
  in running text. The marker itself is dropped as structural, like
  a delimiter character.

Open (M2):
[#317](https://github.com/derek73/python-nameparser/issues/317)
the fullwidth-colon marker (旧姓：佐藤 arrives as one word; the
head-peel question).

### N3 — the lone-word nickname rule

- 2026-07 (v2 core, PR #288; recorded plan deviation #2 of the core
  plan) — v1's rule counted pieces before grouping; the v2 port
  counts one non-title piece plus a nonempty nickname. The rule
  lives in assignment rather than grouping because that is where
  the piece count is settled.

### phd-merge — the "Ph. D." split

- 2026-07 (v2 core, PR #288; recorded plan deviation #1 of the core
  plan) — "Ph. D." tokenizes as two words and is merged back by
  vocabulary (v1 fix_phd), so the spaced and unspaced spellings
  read alike.

### O4 — positional assignment and declared order

- 2026-08-07 #83 — romanized Chinese order is answered by
  DECLARATION, not detection: pinyin carries no signal and diaspora
  makes locale no guide (the issue's own 2019/2021 conclusions);
  Policy(name_order=FAMILY_FIRST) is the answer the thread wanted.
- 2026-08-07 #146 — Vietnamese needs the THIRD order constant:
  measured on "Nguyễn Thị Minh Khai", FAMILY_FIRST strands
  given="Thị" while FAMILY_FIRST_GIVEN_LAST reads
  given="Khai", middle="Thị Minh", family="Nguyễn". This is why
  three order constants exist rather than two.

Declined:

- middle_as_family as the way to suppress the middle slot for
  Vietnamese (2026-08-07 #146) — measured: it merges the middles
  into the family, giving family="Thị Minh Nguyễn" for "Nguyễn Thị
  Minh Khai" under family-first-given-last — a plausible-looking
  wrong answer. There is no policy field that suppresses middle,
  and name_order rejects a two-role tuple ("name_order must be one
  of the exported orders"); given_names (given + middle) is the
  view that stays correct wherever the internal boundary falls.

### W4 — script-scoped order

- 2026-07-27 (script-scoped order amendment) — the family-first
  override is keyed to the SCRIPT of the written name, never to a
  guessed language: wholly-Han, wholly-Hangul, and kana-licensed
  Japanese read family-first because zh, ko and ja all write
  family-first in native script; wholly-katakana names are
  predominantly transcriptions and keep the declared order. Latin
  transliterations are never touched.
- 2026-07-29 #272 — the kana license: Han∪kana with at least one
  kana cannot be Chinese and is not a transcription, so 高橋みなみ
  reads family-first though it is written in two scripts.

### D1 — the segmenterless-activation warning

- 2026-08 #337 — WARN rather than raise, deliberately: registering
  the JA pack without the extra must stay safe (the inert
  registration is itself a pinned property), and a warning is
  filterable by the caller who wants exactly that inertness. The
  Japanese install hint is conditional — it appears only when a
  Japanese script is among the dead scripts; a hangul-only gap gets
  the generic remedies.
- 2026-08 #337 — the warning exists because parser_for(locales.JA)
  without segmenter= used to build a parser that silently behaved
  like a working one minus the feature; it re-emits from the
  parser_for frame so the reported location is the caller's own
  call.
- 2026-08-07 #339 — diagnostics that hand the reader code must hand
  code that type-checks: the message's offered deactivation used a
  bare tuple literal for segment_scripts — an arg-type error under
  mypy in a py.typed package — and became frozenset(), pinned by a test
  asserting the offered spelling. The known-bad spelling is in the
  denylist test. The structural fact behind the recurrence: autodoc
  renders docstrings into the API reference, so docs/*.rst is NOT
  the boundary of "the docs" — a guide and the reference can teach
  different spellings on the same rendered page, invisibly to any
  .rst-only sweep.

### D2 — construction raises, parse never does

- 2026-07 (v2 core, PR #288) — every raise in the locale-apply path
  is a plain TypeError/ValueError so the wrap-with-locale-code
  rewrap cannot break on exotic exception signatures.

### H2 — the leading-abbreviation title

- 2026-06-30 (leading-period-title design; v2 core, PR #288) — the
  shape test is v1 parity (period_abbreviation): two-plus letters
  then a period, bare initials exempt. Its site is the head of the
  part CARRYING THE GIVEN NAME — the whole name, or the post-comma
  part under a family comma — not "the head of the name"; that
  scope correction is PR #315 (2026-08-01, docs-only), verified
  against 1.4.0 from PyPI, so the parity claim is real and the
  narrower description never was. The
  extraction litmus (2026-08-15): the spec drafted this rule as
  "recognized by vocabulary, not by written shape" and the live
  parser falsified that framing — the shape heuristic is real, and
  what the abugida gap (#343/#344) shows is its LIMIT, not its
  absence. Recorded as the rule's Accepted consequence — and the
  2026-08-15 landing initially re-narrowed the scope to "name-
  opening", correcting one error while preserving another; the
  eighth review round fixed it.

Open: [#316](https://github.com/derek73/python-nameparser/issues/316)
what a trailing title-vocabulary word should do (the comma paths
disagree today).

### W1 — unspaced CJK division

- 2026-07-27 #271 (decision; shipped in 2.1.0 via PR #294) — Korean
  division ships as a default: the
  census surname list is closed, hangul is self-selecting (a hangul
  entry can only match hangul text), and being unsplit is
  recoverable while a wrong split is not — which is also why an
  unrecognized name stays whole.
- 2026-07-29 #272 (the ja amendment; shipped in 2.1.0 via PR #297) —
  Han division is opt-in per
  language pack because Han text does not identify its language
  (高橋一郎 under a Chinese list divides wrongly); a pluggable
  segmenter takes what the vocabulary declines, so pack + segmenter
  compose mechanically: a listed surname is a dictionary certainty
  and wins.

- 2026-08 — zh and ja packs are corpus ALTERNATIVES, one per
  corpus; stacking them (parser_for(ZH, JA, segmenter=...)) is for
  genuinely mixed data that accepts the trade: a listed Chinese
  surname wins before the segmenter is consulted, so 高橋一郎 still
  divides 高 + 橋一郎 under ZH+JA exactly as under ZH alone. Kana
  gating resolves through the same script function order uses, so
  kana-licensed composites (高橋みなみ) gate in under JA while
  pure-katakana tokens never do (amendment 2026-07-27: activation
  is per script because the ambiguity is per script).

### W3 — the writer's divisions are respected

- 2026-08 (segmenter amendment 2026-07-29) — a segmenter answers
  where an UNDIVIDED name divides, so it is consulted only when the
  gated token is the name part's only script-written one: "山田
  太郎" was divided by its writer and must not have its family
  divided again. The peeled tail is exempt (that boundary was
  manufactured, not written); a SPACED honorific is not — at that
  position it cannot be told from a spaced name element. The trade
  was measured before deciding: counting spaced honorifics keeps
  four real surnames whole (佐藤 氏, 田中 様, 鈴木 先生, 中村 教授)
  and costs the one division 山田太郎 様.
- 2026-08 #312 — under FAMILY_COMMA the whole stage stood down
  until the peel moved in front of the gate: the comma doctrine is
  about the input's structure, not the split's source, so it covers
  vocabulary and segmenter identically, while an honorific is no
  part of the name whichever side of the comma it glues to.
- 2026-07 — the stage runs AFTER comma segmentation on purpose:
  running before would make the comma structure depend on the
  split ("김민준, Jr." pre-split would read suffix-comma on
  vocabulary alone; as written it stays the listing form).

### W2 — the glued-honorific peel

- 2026-08 #308 — an entry peels only where it can never end a name:
  씨/님/さん/様/先生 peel; 양/군/氏/博士/殿 stay spaced-only; 君 is
  in neither set while its kana spelling くん peels. The vocabulary
  carries the license, so no structural or per-script gate stands
  over the peel.
- 2026-08 #312 — the peel crosses the family comma and the 间隔号:
  both answer where a name DIVIDES into surname and given, a
  question the peel never asks. Provenance matters here: neither
  gate was argued for the peel specifically — both came with the
  placement (#312's own framing) — so the crossing was a repair of
  inherited gates, not a designed-in property.
- 2026-08 #319 — a wholly suffix-shaped second run is declined as a
  peel site (the "田中さん, V." shape), but only when the name's own
  run offers a site, since a glued honorific is itself part of what
  makes a run read as suffix-shaped.

Excluded (the never-given / ambiguous particle line,
nameparser/config/particles.py — #360 owns the vocabulary
question):

- Only 9 of the 39 ambiguous members were ever individually
  justified; the rest sit there by the conservative default
  (ambiguous unless argued never-given).
- mc, ste — measured misparses ("Mc Donald" → given "Mc"), tracked
  in #360; st is inert at the head because TITLES claims it first;
  mac must stay ambiguous because Mac is a real given name.
- Encoding rationale (#293, predating #360's membership questions):
  the data layer stores the NEVER-GIVEN set and derives the
  ambiguous one, because that is safe-by-default for new particles
  — a one-place addition — and the v1 shim translates by
  one-directional complement. And the constants are FROZEN
  specifically to kill the cached-Lexicon.default()-vs-fresh-
  Constants desync that runtime module-constant mutation caused.
- Load-bearing dependency: TITLES ∩ ambiguous == {do, freiherr,
  st} is what keeps the particle-or-given ambiguity emitter
  reachable at all; moving all three would make it dead code,
  which is why test_the_chained_emitter_is_still_reachable
  distinguishes "pick another word" from "delete the emitter".

Open (contested vocabulary memberships — the rule is right, the
word's set is questioned; the issue is canonical):
[#342](https://github.com/derek73/python-nameparser/issues/342)
rai in SUFFIX_ACRONYMS vs. the South Asian surname ·
[#346](https://github.com/derek73/python-nameparser/issues/346)
swami and the renunciate titles absent from the given-name-title
set ·
[#343](https://github.com/derek73/python-nameparser/issues/343) /
[#344](https://github.com/derek73/python-nameparser/issues/344)
Bengali and Devanagari honorific vocabulary.

Excluded (SUFFIX_ACRONYMS / SUFFIX_WORDS — the esq dual
membership, deliberate; AGENTS.md's gotcha carries the full
algebra):

- esq is in BOTH sets and must not be "deduplicated". The
  load-bearing membership is the acronym one (it carries the
  multi-dot spellings: removing it costs "John Smith E.S.Q." its
  family name); the word membership is inert as shipped but is
  what keeps "Esq" matching for a caller who edits suffix_acronyms
  themselves. esq is the ONLY member of SUFFIX_ACRONYMS ∩
  SUFFIX_WORDS — that singleton is why the two sets cannot carry a
  disjointness assert, which is the standing cost this entry
  defends. Deliberately no changed-parse count — the count is a
  property of the measuring grid, not of the code.

Excluded (multi-word vocabulary entries — every set matches one
written word, so a multi-word entry is silently inert and now warns
at configuration):

- Eight entries shipped unmatchable from 2013 to 2.0. chargé
  d'affaires was SPLIT into the chainable chargé + d'affaires, plus
  unaccented charge (the attaché/attache precedent, Derek's call);
  leed ap, nicet i–iv and psm i/ii were REMOVED rather than split,
  on the name-swallowing measurements recorded in #291 (see the
  comma-suffix-arc Declined entry). The multi-word UserWarning is
  this story's enforcement.

Excluded (Lexicon.honorific_tails — a glued tail peels only if it
could never end a name; per-entry reasons live in
nameparser/config/suffixes.py's vetting block):

- 양, 군 — 김지양 and 김지군 are given names ending in these
  syllables, and 양 is a top-tier surname (Yang) besides. (The
  surname-LEADS argument is a different job: it is why both are
  safe in the SPACED set — a leading surname never meets the
  trailing-only suffix gate, so 양 미선 keeps family 양.)
- 氏 — 王氏 is a historical name form ("the Wang woman").
- 博士 — 田中博士 is Tanaka Hiroshi as readily as Doctor Tanaka.
- 殿 — Japanese surnames end in it (鵜殿, 真殿, four-figure
  populations); peeling it would cut a real family name in two.
- 君 — 王君 is a complete Chinese name; its kana spelling くん does
  peel.
- जी (standing prohibition for #344's implementation) — Banerjee,
  Mukherjee and Chatterjee end in the substring
  (बनर्जी/मुखर्जी/चटर्जी), and glued peeling strands a fragment on
  a bare virama (बनर् + जी). The 殿 criterion, in a non-CJK script
  — which also shows the criterion is not CJK-specific.

Excluded (TITLES):

- ঠাকুর — a genuine Bengali honorific (lord/master) that is also
  Tagore, the surname (#343 records it so a wordlist sweep does not
  ship it).
- The trailing-position rule that must NOT be adopted: TITLES holds
  hundreds of words in no suffix set, at least nineteen of them
  ordinary English surnames (king, judge, bishop, baron, sheriff,
  ...), so a blanket "vocabulary outranks position in the trailing
  slot" reading would turn "Mary Jane King" into title="King" with
  the family name gone. The leading half of this argument is
  AGENTS.md's "Dean is deliberately absent" gotcha; this is the
  trailing half, and it shadows the family name rather than the
  given (#316).

Excluded (Policy.script_orders defaults): Script.KATAKANA is
deliberately absent — a pure-katakana token is predominantly a
transcribed foreign name kept in its source order, so nothing
defaults on it (rule W4's boundary). Noted 2026-08-15: of the three
Script-keyed axes, this is the one with no force-a-decision guard
(mechanisms.md#FORCE-A-DECISION-TABLE), so a new Script member
silently gets no order.

Excluded (MAIDEN_MARKERS, per nameparser/config/maiden_markers.py):

- Polish "z domu" — a two-token marker; pending the multi-token
  matching decision, tracked in #291 since 2026-07-27.
- "born" — never shipped: a release-log drafting invention, caught
  by the 2.0 milestone audit and corrected (5ccf9f3). Recorded so
  nobody "restores" it; if ever proposed for real, Max Born is the
  counterexample to analyze.
- Scandinavian "f." — collides with the initial F.; only the full
  participles (født/fødd/född) are safe. Czech masculine "rozený"
  awaits the same vetting.

### C1 — the suffix-comma decision

- 2026-07 (v2 core, PR #288) — v1 parity: only the second segment
  decides (v1 parser.py:1318), and ">1 word before the first comma"
  is v1's guard, which is why "Smith, PhD" keeps the listing form.
- 2026-07 (plan deviation #3, recorded) — the decision is
  definitionally vocabulary-dependent: there is no way to recognize
  a credential run without consulting the suffix word lists, so the
  structural stage reads vocabulary through one predicate.
- 2026-07-12/13 (v2 Policy work, PR #288) — the lenient token test
  is the default and `lenient_comma_suffixes=False` restores the
  strict one. (An earlier entry here credited #291/#296 — git
  author dates place both the field and its wiring in the Policy
  commits, and the #291/#296 design doc never mentions the knob.)
- 2026-08 #319 — the wholly-suffix predicate was lifted into the
  vocabulary layer so the comma decision and the honorific peel's
  segment test cannot drift apart.

### T1 — separators, not joiners

- 2026-07 (v2 core, PR #288) — v1's squash_emoji/squash_bidi
  REMOVED the character and joined its neighbors ('A😀B' → 'AB');
  v2 makes an ignorable character a separator ('A😀B' → 'A', 'B').
  The unavoidable consequence of every part being an exact
  positioned piece of the input: with no rewriting stage, nothing
  can splice two half-words together.

### T3 — the interpunct's flank guard

- 2026-07-30 #298 — codepoint scope, chosen over a blanket
  "dot = transcription" rule that would have flipped 高橋・一郎, a
  correct and deliberately pinned #272 reading: U+00B7 records the
  transcription fact and suppresses division; U+30FB/U+FF65 stay
  pure separators whose pieces the script license reads (rule W4's
  Accepted pair demonstrates both). Cross-convention input reads by
  the codepoint it was actually typed with — a chosen limitation,
  recorded in #298's comments.

Declined:

- Ambiguity emission on a half-flanked interpunct ("王·Smith") —
  proposed in the 2.1 PR review, declined because the dot decides
  silently under the no-emission decision; the
  undivided-dot-stays-in-the-word behavior went to docs instead.


- 2026-07-30 #298 — U+00B7 divides only between classified-script
  characters because it is also the Catalan punt volat, interior to
  legitimate names (Gal·la). The nakaguro (T2) needs no such guard:
  its codepoints are CJK-only and appear in no other script's
  names, which is what licenses an unconditional rule.

### M1 — delimited maiden names

- 2026-07-03 (maiden-bucket design, landed via the v2 core, PR
  #288) — the maiden reading of a delimiter pair is opt-in because
  enclosure conventions genuinely vary; there is no default pair.
- 2026-07 — bucket overlap is canonicalized before parsing: a pair
  listed for maiden is dropped from the effective nickname set
  (maiden wins). The v1 facade restores v1's nickname-wins reading
  by pre-subtracting on its side.
- 2026-08-04 #329 (PR #331) — the marker word inside a delimited
  clause is dropped from a multi-word clause during grouping; the
  extraction itself keeps the whole enclosed span, so nothing is
  lost when there is no marker. Three decisions argued separately:
  the clause-size guard exists because Nee is an attested surname
  (Irish Ní/Nee, a Chinese romanization) — load-bearing, not
  defensive, and mutation-proven; clauses are independent — "(Nee)
  (Jones)" reads maiden "Nee Jones", each clause dropping or
  keeping its own marker (the first implementation leaked across
  clauses, a real defect); and the contentless "(née —)" alone now
  parses to every field empty and bool() False (an explicit
  alternative keeping maiden "née —" was rejected; pinned by the
  maiden_marker_delimited_content_free case).
- M1 and M2 are disjoint by construction, which is the no-conflict
  guarantee: M2's walk covers joining structure that role-bearing
  words never enter, while M1's drop reaches only extracted
  content. Verified independently at review over 7,775 records:
  967 diffs, every one in the maiden field.

Declined:

- Neighbour-scoping the drop (drop a marker whose next word also
  reads maiden) — implemented, reviewed and rejected: it also fires
  on the bare-marker path, eating the surname out of "Jane Smith
  nee Nee Jones" (maiden "Jones" instead of "Nee Jones"), and it
  leaks across adjacent clauses. It is the obvious implementation,
  which is why this entry exists.

- 2026-08-05 #329/#335 — marker auto-detection inside a
  nickname-delimited clause was deferred to #335 on a corpus
  measurement: 山田 花子（旧姓 佐藤） is in the CJK differential
  corpus so the #329 change was gate-visible, while "Jane Smith
  (née Jones)" is in no corpus — shipping auto-detection in 2.1
  would have let a real Latin-affecting change ride under a "0
  Latin-only" gate report.

Open: [#335](https://github.com/derek73/python-nameparser/issues/335)
should a marker inside a NICKNAME-delimited clause flip it to maiden
without configuration.

### O1 — East Slavic rotation

- 2026-07-12 (landed in the v2 core, PR #288) — v1 parity pinned
  live: the rotation reconstructs token position from assigned
  roles, which is faithful to v1 only under the default given-first
  order.

Open: [#270](https://github.com/derek73/python-nameparser/issues/270)
how the rotations interact with non-default name_order values.

### O2 — Turkic rotation

- 2026-07-02 (landed in the v2 core, PR #288) — shape fixed at
  exactly four name words (1 given + 2 middle + 1 marker), v1
  parity; other shapes keep their positional reading even when that
  leaves the marker in a name field (see the rule's Accepted
  consequence).

Open: [#270](https://github.com/derek73/python-nameparser/issues/270)
same rotation/name_order interaction as O1.

### differential-ledger — tooling decisions (2.1.0 release arc)

Harvested 2026-08-15 from the release-arc session; measurements are
that session's, spot-checked at landing.

- 2026-08-05 #332 — ledger field vocabulary is Role's names, not the
  facade's: canonicalizing to first/last would have put an eighth
  place naming roles differently from Role inside the durable
  record, and the facade vocabulary is removed at 3.0.

Declined:

- Policy annotations widened to input unions (2026-08-05 #334) —
  five documented spellings fail mypy and every one has a
  type-clean equivalent; widening would make every READER see a
  union, and reading is the commoner operation. A .pyi stub typing
  __init__ wide and attributes narrow was deferred as a 3.0
  candidate (needs a parallel signature list with its own sync
  test).
- Closing the differential gate's default-policy ceiling
  (2026-08-04 #332) — a per-row policy in the corpus needs defined
  behavior for baselines that cannot construct newer policy fields;
  tests/v2/cases.py already covers opt-in paths per row, so the
  ceiling is documented instead.
- `_check_tree` as is_relative_to(REPO_ROOT) (2026-08-05 #332) —
  accepts .venv/, build/ and dist/ copies inside the repo; the
  invariant is "is the source package", so the predicate is
  is_relative_to(REPO_ROOT / "nameparser").
- Empty-string probe as the ledger over-match guard (2026-08-05
  #332) — `.`, `.+`, `\b`, `[\s\S]` all decline "" and still match
  every corpus name; replaced by the sentinel set
  (mechanisms.md#SENTINEL-SET-OVER-MATCH-CHECK).
- "Lists every role" checked against all eight fields entries
  (2026-08-05 #332) — a seven-role list passed while omitting
  _ambiguities, which below baseline 2.0 cannot enter a diff at
  all; the check is against V2_FIELDS.
- A seed ledger rule with name_regex and no fields (2026-08-05
  #332) — it matched every CJK-bearing name and would have
  classified all 89 diffs on the first pass, exiting 0 having
  distinguished nothing.
- The B7 sanctioned-extra span (pre-#332 arc) — added, then removed
  as a pure loss when review measured that every B7-divided name
  already matches through its guaranteed classified flanks, so the
  span's only effect was absorbing punt-volat Latin regressions
  ("Gal·la Marcet" probes on both sides, recorded in PR #305's
  history). The cleanest "sanctioned extras must be earned"
  precedent the ledger has.
- An issue for rotating DEFAULT_BASELINE (2026-08-07) — it recurs
  every release; it lives in the AGENTS.md release checklist beside
  the VERSION bump instead (#333 must land first).

Excluded (ledger name_regex patterns — one over-matching rule
shadows the whole ledger, since name_regex rules sort first): "",
"(?:)", ".", ".+", "\b", "[\s\S]". Enforced by the sentinel-set
check.

### differential-ledger, the dormancy arc (2026-08, #328–#376)

The second ledger arc; measurements are that session's, the
machinery verified present at landing.

Decisions that landed:

- 2026-08 #328 — `[[never]]` exclusions: ledger vocabulary for
  "this shape must never be explained". classify() consults
  exclusions before rules, which makes them MONOTONE — an entry
  only ever removes a name, never moves one between rules — so an
  exclusion's blast radius is exactly the names it captures,
  independent of rule order.
- 2026-08-12 #373 — `dormant = "<reason>"`: a rule explaining
  nothing fails the run in both directions, with three diagnoses
  (reverted / shadowed by X / refused by a [[never]] entry). Always
  on, not behind --strict: a check nobody passes a flag to is a
  check that doesn't exist.
- 2026-08 #373 — `--baseline 2.0.0` joined the release checklist:
  that ledger's rules had no dynamic coverage at all; measured
  clean at 90/0, so the gap was closed rather than documented.

Declined:

- Ambiguity reporting on multi-matching rules (#372/#373) —
  measured: 28% of claimed name×role pairs already have ≥2
  matching rules (732 of 2619; 432 are one pair of rules alone). A
  report firing on 28% of what it inspects is wallpaper. The
  actionable slice shipped as the "shadowed by <issue>" diagnosis,
  which speaks only on FULL shadowing.
- A specificity floor for fields-only rules (#372/#373) — exactly
  one fields-only rule exists in any ledger, naming 3 of 7 roles;
  a six-of-seven floor matches nothing, and nothing would reveal
  it vacuous.
- Specificity reordering of the rule sort (#328) — measured across
  all 751 names: width-then-regex-length moves five rule
  populations and sends 17 names into the generic fields-only
  rule, draining the CJK-specific ones. No reading of the sort
  produces the "exactly one label changes" originally claimed;
  that figure was corrected on the PR.
- Unanchoring the honorific-suffix rule to reach glued forms
  (#376) — it would make a future suffix regression on 김지양
  classify as a recognized honorific. A confidently wrong label is
  worse than a catch-all's honest breadth, and the gate reads the
  same either way.

### comma-suffix-arc — #291/#296/#316 (2026-07-26 → 2026-08-01)

#291 was filed 2026-07-26 out of the 2.0 vocabulary cleanup, with
its decline-by-measurement evidence in the issue body; "z domu"
folded into it 2026-07-27 (see Excluded, MAIDEN_MARKERS). Intent
for #291 and #296 is settled by the approved bundle spec but
UNSHIPPED — rules.md carries both as deviates: markers on C1. The
arc's bookkeeping: #291/#296 moved milestone v2.1 → v2.2 on
2026-08-01 (with #289/#293); the 2026-07-30 design doc was amended
in place 2026-08-01 with an A1–A6 amendments section, and citations
should be to the amended form; #316 (trailing titles) was filed the
same day, carrying the esq cleanup as a Related section.

Declined:

- Splitting the dead multi-word suffix entries into single-word
  entries (2026-07-26, the evidence in #291's body) — measured:
  "Smith, A.P." has the suffix steal the given initials; "John
  Leed" and "Mary Nicet" lose family names; and the period-gate
  escape is equivalent to removal because nobody writes "L.E.E.D.".
  This decline is why the seven removable entries were REMOVED in
  2.0 rather than split, and it is the missing history behind C1's
  #291 marker.
- The trailing-abbreviation structural fallback — with a
  measurement LIMIT rather than a measurement: the differential
  corpora structurally cannot evidence it, because they hold only
  names someone wrote down, and an unrecognized abbreviation is by
  definition outside the vocabulary. A green run there proves
  nothing (the reusable harness fact is in mechanisms.md's field
  notes).
- SUFFIX_PHRASES matching in assignment — measured cost: it
  renders suffix="LEED, AP", because the suffix view comma-joins
  suffix words unless they carry the stable "joined" tag, which
  only grouping applies. The general form: multi-word vocabulary
  must merge where the render tag is applied, not where the role
  is assigned.

### 3-0-reevaluations — decisions shaped by the v1 shim

Promoted 2026-08-15 from session memory (Derek's 2026-07-30 ask;
promotion approved 2026-08-15). Discipline when appending: mark each
entry (A) "would decide differently without the shim" — real 3.0
work — or (B) "cited 1.4 parity but stands on its own", recorded so
nobody re-litigates it. Append here whenever a design choice cites
1.4 parity or the shim as a load-bearing reason.

- (A) v1 field vocabulary at the facade boundary: CJK semantics
  squeeze into first/last through HumanName while the core speaks
  given/family. 3.0 could drop the aliasing entirely.
- (A) Render's v1-inherited string_format defaults, including
  space-joined output for interpunct transcriptions (#298:
  str(HumanName("威廉·莎士比亚")) == "威廉 莎士比亚"; users
  reinstate the dot via custom format). 3.0 render defaults are a
  clean slate.
- (A) The differential harness baseline is 1.4-on-PyPI: post-shim,
  the migration promise it verifies dissolves; the successor
  baseline is presumably last-2.x. Machinery survives; corpus
  contracts change.
- (A) empty_attribute_default left untyped (PR #250): cascades into
  the v1-shaped public API. Typeable in 3.0.
- (A) A .pyi stub for Policy (wide __init__, narrow attributes) —
  deferred from #334, see the differential-ledger Declined entry.
- (A) nameparser.config removal scope: the 3.0 schedule says
  "nameparser.config in its entirety" while actually enumerating
  only the five shim exports; whether the DATA modules keep the
  package as their home or move under the core is open, and
  Lexicon's public field docs cross-reference
  nameparser.config.particles et al. (see the maintainer note in
  nameparser/config/__init__.py).
- (B) Pickle-guard layout breaks landing in minors (2.1's
  __setstate__ breaks): the guarded-raise design is right
  regardless; only the in-a-minor friction is shim-era.
- (B) Positional-read-when-unlicensed as the safe direction
  (script_orders fallbacks, #298 dot-suppression granularity):
  coincides with 1.4 parity but stands alone — family-first is the
  marked case needing affirmative evidence.
- (B) The deprecation-bridge shape (#293/#354) is the template for
  every remaining 2.x→3.0 shim: PEP 562 module __getattr__ PLUS
  __all__ (star imports never reach __getattr__ — measured: `from
  ...prefixes import *` bound nothing and leaked the helper); warn
  per read-location rather than per process (a write-back let a
  vendored dependency's first read consume the only warning); and
  the TYPE_CHECKING split, because a module __getattr__ silently
  disables mypy's attr-defined checking for the whole module
  (measured on a py.typed package).
- (B) The FAMILY_COMMA doctrine (rule W3): inherited from v1's
  lastname-comma but correct on its own terms — an explicit comma
  is stronger evidence than script.
