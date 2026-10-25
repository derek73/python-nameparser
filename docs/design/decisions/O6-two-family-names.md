# O6 — two family names

## Standing

- Two family names are an opt-in `Policy` switch, `two_family_names`, off by default, and not a locale pack: the convention is Spain's and most of Latin America's but not Argentina's, and given-first it is the same string shape as a name with a middle name, so no default can read it — 2026-10-24 #754.
- Both family names stay in `family` through 2.x; a second-surname field is the RFC's Phase 4 output model (docs/design/vocabulary-model-rfc.md, "The rules a pack can choose"), and a pack may later switch this rule on — 2026-10-24 #754.
- The family's words are counted as P1's fold counts them, a connective join and a hyphen counting as their words, so a family already holding two keeps what it has — 2026-10-24 #754.
- Under a family-first order the first two name words are the family, the remainder laid out as the positions after a family — 2026-10-24 #754.
- The switch runs before `middle_as_family` and is not refused beside it: given-first, the two together read as `middle_as_family` alone — 2026-10-24 #754.
- The switch reports nothing — 2026-10-24 #754.

Open: the readings the switch breaks may be offered as `Ambiguity.alternative` once the vocabulary model's Phase 2 lands it (its D13); #754.

## Log

- 2026-10-24 #754 — TWO FAMILY NAMES ARE AN OPT-IN SWITCH THAT TAKES THE NAME WORD BESIDE THE FAMILY. The PSC register's fielded names (`local_agreement.py psc-individuals`) put two-word surnames read as middle plus family as the largest disagreement there, 22,168 names, 72% not Iberian (the ranking on #754). Given-first, `Ana García López` is the same shape as a name with a middle name, so the default cannot change; the convention is not one country's, so it is a `Policy` field rather than `locales.ES`. Portuguese order, the mother's name first, is out of scope.
  What the rule settles, and why each way:
  - **The count.** A particle run counts with the word it attaches to (P1's reach, so `Juan Pérez de la Vega` gives family `Pérez de la Vega`); a P2 chain counts the words it chained, so `Ana María de la Vega Rodríguez` keeps family `de la Vega Rodríguez`; a connective join counts its words, so `José María Ortega y Gasset` keeps family `Ortega y Gasset`; titles, suffixes and nicknames count as nothing. The rest of the name is split as assign read it, so a P2 chain or a P5 pair moves whole or not at all.
  - **A hyphen joins two words.** Counting `García-López` as one word would take the word before it. Measured over the 34,195 scored PSC records whose name holds a hyphen, with the switch on: 31,007 agree counting the hyphen's words against 19,597 counting the token (the default reads 32,958), Spanish filers 206 against 182 of 252, British 19,807 against 10,677 of 21,797.
  - **Family-first.** The declared order says where the family stands, so the first two name words are the family and the rest is laid out as P1's family-first fold lays out its own: `García Márquez Gabriel` gives given `Gabriel`. A particle P6 attached at the far end stays family where it stands.
  - **Precedence.** `middle_as_family` folds every middle, which includes the word this rule takes, so the switch runs first and the fold takes what is left; refusing the pair would cost a working configuration for no wrong reading (AGENTS.md, "Invariants guard harm, not no-ops"). A patronymic rotation decided the family already, and the rule finds no middle standing right before that family, so it stands down. A family comma decides by itself.
  - **No report.** The caller declared the convention, as a declared order is followed without a report; the fork is real, but reported on most names of three words or more it would teach the caller to ignore the field. The other reading belongs to Phase 2's `Ambiguity.alternative` (D13), not to an existing kind: `ORDER` is about field order, and none of the others names this fork.
  Measured 2026-10-24 on this branch with the switch on, the default unchanged (the snapshot gains the rule's 19 example texts and changes no reading; every agreement record matches). PSC (`psc-individuals`, the fetch recorded on #849, 1,039,171 records scored), all boxes agreeing before → after, records fixed and broken:

  | Filers | Records | Before → after | Fixed | Broken |
  |---|---:|---|---:|---:|
  | Spanish | 6,089 | 31.8% → 80.5% | 3,875 | 910 |
  | Mexican | 402 | 25.9% → 80.1% | 274 | 56 |
  | Colombian | 377 | 29.2% → 84.4% | 261 | 53 |
  | Venezuelan | 237 | 40.5% → 77.2% | 133 | 46 |
  | Chilean | 151 | 35.1% → 77.5% | 93 | 29 |
  | Peruvian | 116 | 21.6% → 81.9% | 81 | 11 |
  | Argentine | 320 | 81.9% → 45.9% | 55 | 170 |
  | Portuguese | 5,333 | 61.1% → 56.3% | 1,238 | 1,495 |
  | Brazilian | 1,920 | 53.4% → 55.6% | 604 | 563 |
  | Everyone, as if it were the default | 1,039,171 | 96.7% → 47.0% | 23,271 | 539,579 |

  Among Spanish filers it fixes names of four name words 1,488 to 163 and of three 2,341 to 738, counted by the default reading's given, middle and family words. Of the records it breaks, 896 of 910 Spanish and 1,338 of 1,495 Portuguese filed a one-word surname. In the GND and Wikidata fielded corpora, the given-first renderings of the Spanish and Latin American double-surname strata (GND `compound-iberia` and `compound-latam`, Wikidata `surname2-es`, `-mx` and `-co`) disagree with the source on 315 of 390 by default, the RFC's count, and on 15 with the switch: 302 fixed, 2 broken. The same switch over every other given-first rendering breaks 54 of GND's 408 and 142 of Wikidata's 250, and in the native-script Wikidata corpus moves 31 three- and four-word Arabic, Cyrillic, Bengali and Devanagari names, 11 to agreeing and 20 away. Recompute: parse each corpus with `Parser()` and `Parser(policy=Policy(two_family_names=True))` and compare, for PSC, `local_agreement.read` per record grouped by `group_of`, skipping records set aside on either side; for the fielded corpora, `cldr_agreement.expected_roles` against `got_roles` per rendering with `shape` None, split by `label` and `order`. The comparator is the default parser on the same tree.
