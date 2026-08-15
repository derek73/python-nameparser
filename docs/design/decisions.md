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
