# Decisions

The why behind the rules: a lightweight ADR log, keyed by rule ID
(`### P2 — <short name>`), by mechanism slug, or by a short slug for
cross-cutting and tooling decisions. Section headings carry the key,
so every `decisions.md#P2` reference in code or rules.md is a live
anchor.

Entry conventions:

- **Dated decision entries**, append-only in spirit: a reversed
  decision is not edited, a later entry supersedes it. Each entry
  cites its issue or PR.
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
would be false. Under a family-first order, "Juan de la Vega" holds
the entire chained group in the given position — three words, not a
lone particle — so P1 declines and given="de la Vega" stands; #359
records that case as working as intended. The MIDDLE position is
deliberately not a fold site.

- 2026-08 #359 — the opening site is read from joining structure
  (pieces), not from assigned roles, so the fold holds under every
  name_order. Before this, the role-only read let "de Mesnil" split
  under a family-first order.
- 2026-08 #367 — titles are transparent to the fold: "Sir de
  Mesnil" now reads like "de Mesnil". Fixed by removing the
  title→particle chain in grouping, not by touching this rule.

Open: [#364](https://github.com/derek73/python-nameparser/issues/364)
how much the fold takes ·
[#365](https://github.com/derek73/python-nameparser/issues/365)
should the middle position be a third site ·
[#360](https://github.com/derek73/python-nameparser/issues/360)
which particles count as never-given.

### P2 — particles join forward

- 2026-08 #367 — a title is transparent to the chain's start:
  "Sir de Mesnil" chains de→Mesnil exactly as the untitled form
  does. Before, the title displaced the particle out of the leading
  position and "Sir de Mesnil" reported given="de Mesnil" with no
  family at all — a limit the rule never meant to draw. Fixed in
  grouping, which is why P1's fold needed no change (its interacts:
  points here).

### M2 — the maiden-marker rule

- 2026-07-03 #274 (v2 core, PR #288) — the marker takes everything
  after it up to a trailing suffix, greedily: "née Jones Smith" is
  a two-word maiden name, matching how the marker is actually used
  in running text. The marker itself is dropped as structural, like
  a delimiter character.

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

### W4 — script-scoped order

- 2026-07-27 (script-scoped order amendment) — the family-first
  override is keyed to the SCRIPT of the written name, never to a
  guessed language: wholly-Han, wholly-Hangul, and kana-licensed
  Japanese read family-first because zh, ko and ja all write
  family-first in native script; wholly-katakana names are
  predominantly transcriptions and keep the declared order. Latin
  transliterations are never touched.
- 2026-08-07 #272 — the kana license: Han∪kana with at least one
  kana cannot be Chinese and is not a transcription, so 高橋みなみ
  reads family-first though it is written in two scripts.

### D1 — the segmenterless-activation warning

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
  denylist test.

### D2 — construction raises, parse never does

- 2026-07 (v2 core, PR #288) — every raise in the locale-apply path
  is a plain TypeError/ValueError so the wrap-with-locale-code
  rewrap cannot break on exotic exception signatures.

### H2 — the leading-abbreviation title

- 2026-06-30 (leading-period-title design; v2 core, PR #288) — the
  shape test is v1 parity (period_abbreviation): two-plus letters
  then a period, leading position only, bare initials exempt. The
  extraction litmus (2026-08-15): the spec drafted this rule as
  "recognized by vocabulary, not by written shape" and the live
  parser falsified that framing — the shape heuristic is real, and
  what the abugida gap (#342-#345) shows is its LIMIT, not its
  absence. Recorded as the rule's Accepted consequence.

### W1 — unspaced CJK division

- 2026-08-07 #271 (2.1.0) — Korean division ships as a default: the
  census surname list is closed, hangul is self-selecting (a hangul
  entry can only match hangul text), and being unsplit is
  recoverable while a wrong split is not — which is also why an
  unrecognized name stays whole.
- 2026-08-07 #272/amendment 2026-07-29 — Han division is opt-in per
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
  question the peel never asks.
- 2026-08 #319 — a wholly suffix-shaped second run is declined as a
  peel site (the "田中さん, V." shape), but only when the name's own
  run offers a site, since a glued honorific is itself part of what
  makes a run read as suffix-shaped.

### C1 — the suffix-comma decision

- 2026-07 (v2 core, PR #288) — v1 parity: only the second segment
  decides (v1 parser.py:1318), and ">1 word before the first comma"
  is v1's guard, which is why "Smith, PhD" keeps the listing form.
- 2026-07 (plan deviation #3, recorded) — the decision is
  definitionally vocabulary-dependent: there is no way to recognize
  a credential run without consulting the suffix word lists, so the
  structural stage reads vocabulary through one predicate.
- 2026-07-30 #291/#296 — the lenient token test is the default and
  `lenient_comma_suffixes=False` restores the strict one.
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

- 2026-08 #298 — U+00B7 divides only between classified-script
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
- 2026-08 #329 — the marker word inside a delimited clause is
  dropped from a multi-token clause during grouping; the extraction
  itself keeps the whole enclosed span, so nothing is lost when
  there is no marker.

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
