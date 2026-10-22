# two-input-invariants — checking a rule against something that is not the code

## Standing

- A rule is checked against an invariant relating two DIFFERENT inputs, which consults no rule statement, so it can find a rule that is wrong (docs/design/AGENTS.md's axis 11) — 2026-08-31 #473.
- The worked invariant: `Family, Given Particle` under the default order and `Family Given Particle` under FAMILY_FIRST parse alike for every particle but `do`, `mc` and `vd`, the particle-and-suffix words, the families and givens being drawn from outside the particle vocabulary; `tests/v2/test_order_correspondence.py` holds it, asserting the disagreeing set is exactly those three — 2026-08-31 #473.

Elsewhere: why #473's "0 of 216 → 216 of 216" figure cannot be trusted is decisions/P6's.

Open: none in this file.

## Log

- 2026-08-31 (#473; earned by #461 and #466) — AGENTS.md axis 11. Axes 1–10 compare a document to another document, to its own examples, or to the implementation, so all ten can only find code that disagrees with a rule; none can find a rule that is wrong. #461 was backed out and #466 closed unmerged for exactly that reason, a month apart, each after a review round that found real defects and missed the premise beneath them. An invariant relating two DIFFERENT inputs consults no rule statement and is not blind that way.

- The worked invariant: for a name written `Family Given Particle`, the family-comma writing under the default order and the comma-less writing under FAMILY_FIRST must parse alike. Measured 2026-08-31 on 9f1d46e, comparing the non-empty role fields over `nameparser.config.particles.PARTICLES` × six families × six givens: it holds on all 36 pairs for 67 of the 70 particles, and fails on all 36 for `do`, `mc` and `vd` — precisely the words that are also suffix vocabulary, which rules/P6's Accepted consequence already names as the contested memberships. The invariant found that set from behavior alone, having read no rule.

- Recompute: for each P in PARTICLES compare the non-empty role fields of `Parser().parse(f"{F}, {G} {P}")` against `Parser(policy=Policy(name_order=FAMILY_FIRST)).parse(f"{F} {G} {P}")` across any spread of families and givens that are not THEMSELVES particle vocabulary. That restriction is load-bearing, not hygiene: with F or G drawn from PARTICLES the correspondence fails for every particle, because the spread word joins the particle run and the invariant is then measuring a different shape (`Doe, Van de` gives given "Van" middle "de"; `Doe Van de` under FAMILY_FIRST gives given "Van de"). Measured, that is 0 of 70 rather than 67 of 70, so a reviewer who picks a particle word as a family — a natural choice when probing particle behavior — would report P6 broken. The argument survives the digits moving: what carries it is that the failures partition onto the particle-and-suffix words, not how many pairs there are.

Declined: #473's "0 of 216 → 216 of 216" framing — but not re-argued here, because decisions/P6 already records that number's provenance (a script slicing `sorted(particles)[:14]`, which excluded exactly do, mc and vd), already names it axis 2 in its purest form, and already closes "Recompute over the WHOLE vocabulary, never a sample." Cite that entry for why the figure cannot be trusted; a second account of it in this file is the duplication decisions/review-agent-single-source was written to stop. #473's companion "72 of 216 — the ambiguous-particle half" measures a DIFFERENT partition of the vocabulary from the one above and must not be read as agreeing with it: the ambiguous particles are the 37 that are not never-given, and decisions/P6 records that #466 failed because a never-given test at the new site would have excluded all 37, `van` among them — not because of the three particle-and-suffix words. Two partitions, two different failures.

Resolved: #469's invariant landed as `tests/v2/test_order_correspondence.py` — a generated parametrized sweep over a small deliberately-forked vocabulary (never-given/ambiguous/multi-token particles, an ASCII and a non-ASCII family, doubled middles), plus a second, non-parametrized test sweeping the entire shipped particle vocabulary (`nameparser.config.particles.PARTICLES`) in the minimal pair and asserting the disagreeing set is exactly `{do, mc, vd}` — the negative control this entry's Recompute bullet describes, now executable rather than a recipe to rerun by hand.

