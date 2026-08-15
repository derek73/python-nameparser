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
