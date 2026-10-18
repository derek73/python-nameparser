# suffix-field-composition — three kinds of thing in one field

- 2026-08-16 (suffix keystone; #326) — measured composition of suffix_words (40 entries): 11 generational (i, ii, iii, iv, v, jr, jnr, sr, snr, junior, 2), 5 neither (dr, esq, esquire, ret, vet), and 24 POSTNOMINAL HONORIFICS — 20 CJK (さん, さま, くん, ちゃん, 様, 殿, 氏, 先生, 博士, 教授, 女士, 小姐, 씨, 양, 군, 님, 박사, 박사님, 교수님, 선생님) and 4 Hebrew (ז"ל, ז״ל, שליט"א, שליט״א). The honorifics are the LARGEST group.
- Decision: do NOT split the field. Record the composition; #296,
  #291, #325 and #289 proceed on their own terms rather than
  waiting on it.
- Why #326 cannot be taken at face value: it argues the split is tractable because "the vocabulary is already split — suffix_acronyms is credentials, entirely; suffix_words is generational plus a handful". That was true when written (2026-08-02); the 2.1.0 East Asian work landed 2026-08-07 and put the 24 honorifics in the same set. CLDR's two buckets do not cover what the set now holds, so "adopt CLDR's model" is not available as the cheap answer. The issue's table is corrected on the issue.
- The unexamined question this leaves: whether the honorific bucket belongs in `suffix` at all. rules/W3 already argues an honorific is "no part of the name on either side" — the same language the H section uses for prenominal titles — so the conflation with PhD may be worse than the generation/credentials one #326 was filed about. Deliberately not decided here.
- Recorded as a documentation failure mode, not just a fact: `suffix` started generational, absorbed credentials, then absorbed postnominal honorifics, each step locally reasonable and none recorded as a widening of the field's MEANING. rules/S2's Background still calls it "two different things", which was accurate when written. The rules doc pinned the behavior faithfully; what slipped is the field's definition, which no rule states because no rule owns it. Field definitions need the same discipline rule statements get.
- The 11/5/24 split above is this entry's own version of the hazard it describes: a quoted vocabulary composition, dated, exactly as
  #326 quoted one. A date does not stop rot — #326 carried one too
  — so before relying on the split, check the set still looks like it:

      uv run python -c "from nameparser import Parser; print(sorted(Parser().lexicon.suffix_words))"

  What is durable here is the SHAPE of the finding — three kinds of thing, the honorifics the largest — not the three integers. A test asserting the counts is deliberately not the answer: that is the constant-content pattern, and it would fail on every legitimate vocabulary addition.

