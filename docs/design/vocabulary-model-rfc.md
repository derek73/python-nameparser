# RFC: the vocabulary model and language packs

Status: **design overview**, written 2026-10-19 after phase 1 shipped. It says where the vocabulary model is going and why, phase by phase. It is not the record: each decision is logged in [decisions/vocabulary-model](decisions/vocabulary-model.md) when it is made, and where the two differ, that entry is right and this document is stale. Each later phase gets its own design when it starts, under its issue; this overview is amended as they land. Work is tracked in #747.

For editing the vocabulary as it is today, read [nameparser/vocab/README.md](../../nameparser/vocab/README.md) instead.

## The short version

nameparser recognizes words by vocabulary: titles, suffixes, particles, conjunctions, bound given names, maiden markers. Until 2.6 that vocabulary was a set of base sets plus marker subsets (`particles` and `particles_ambiguous`, `suffix_acronyms` and `suffix_acronyms_ambiguous`, ...). The model replaces the sets with a description of each **word** by its **readings**: what the word can be in a name, and the properties of each reading.

```toml
[[word]]
text = "do"
credential = { may_be_name = true, expands = "Doctor of Osteopathic Medicine" }
[word.particle]
may_be_given = true
```

`do` is a credential and a particle, and Vietnamese Đỗ makes it a surname too. Under the sets that clash was visible only as an overlap between two of them; as readings it is written on the word. Once every word says which language's names it occurs in, choosing a language can settle the clashes that exist only because the default serves every language.

Four phases, in a fixed order:

| Phase | What | Changes parsing? | State |
|---|---|---|---|
| 1 | The per-word TOML format, compiled to today's sets | no | shipped in 2.6 (#737, #744); #749–#751 gave the words in `und.toml` their languages, leaving two particles of unrecorded origin |
| 2 | Ambiguity derived from clashing readings; the ambiguity gate extended to every reading kind | yes, the first phase that does | #752 |
| 3 | Language packs that prefer or restrict their language | yes, for callers who choose one | #753, needs 1 and 2 |
| 4 | Order and shape; the rules a pack can choose; the output model | yes | #754, mostly independent of 2 and 3 |

Two commitments hold through all four. **The default loads every language and keeps working for names of any language, as today**; choosing a language narrows it (decision 5 in decisions/vocabulary-model). And **languages own vocabulary and defaults, the core owns structure**: a pack configures rules the core implements, and never ships code (mechanisms.md#LOCALE-PACKS-PURE-DATA).

## Why readings, not sets

The sets failed as a model in five ways (decisions/vocabulary-model's preamble has the detail):

- "Ambiguous" meant three things by field: may be a given name (particles), may be a surname (acronyms), may be an initial (conjunctions). Two other marker sets (`honorific_tails`, `given_name_titles`) were not ambiguities at all.
- The direction flipped between layers: `config/` listed the never-given particles, `Lexicon` the may-be-given ones.
- Every marked word was written twice, and the checks on the pairs were uneven.
- A clash between categories was recorded nowhere, and nothing told an author whether an overlap they created was intended (`titles ∩ particles` holds `freiherr` and `st` on purpose) or forbidden (a post-nominal both an acronym and a word).
- A set cannot say which language a word belongs to, which is what a language pack needs.

A reading fixes each of these by construction: a property cannot exist without its reading, so the subset checks disappear; a clash is a word with two readings; and the file a word sits in is its language.

## Phase 1: the format (shipped)

Phase 1 re-encoded the vocabulary and changed no parse. One TOML file per BCP 47 tag holds the words found in names written in that language (`und` for words not yet assigned one, `mul` for words shared on purpose); each `[[word]]` lists its readings keyed by kind; `tools/vocab/build.py` compiles the files into today's sets, and the parser never reads the TOML. The suffix category is classified into six kinds (generation, credential, honorific, professional honorific, status, courtesy); every other category carries its generic kind until its classification issue lands. Exclusions are data: a refused reading is recorded on the word with its reason, and the build refuses it in any file, quoting that reason.

Two choices in phase 1 set up phase 2 and are worth knowing before reading it:

- **The marker sets are explicit flags** (`may_be_given`, `may_be_name`, `may_be_initial`), not derived from name readings. Deriving them in phase 1 would have meant declaring a given reading for particles like `te`, `tho` and `du` that no bearer count supports. The flags record past curation, not evidence.
- **Names a later phase will use are build errors now** (`default`, `prefer`, `strict`, `bare_only`, `leading_only`, `trailing_only`, `attaches`, `separators`, and the values `addresses = "full"` or `"any"`), so nothing reads as working before it does.

The reference for the format is nameparser/vocab/README.md; the decisions behind it, with what was declined and measured, are decisions/vocabulary-model's 2026-10-18 entry.

## Phase 2: derived ambiguity and a general gate

Phase 2 is the first phase that changes how names are parsed, and it gets its own design (#752). What follows is the shape that design starts from.

### Ambiguity from readings

A word whose readings clash is ambiguous, so the markers can be derived instead of curated:

- a particle that may be a given name is a word with a particle reading and a `given` reading;
- an acronym that may be a name is a word with a credential reading and a `given` or `family` reading.

Name readings are declared by hand, and only for words some file claims as vocabulary or refuses (decision 11, widened 2026-10-19): `fils`'s `family` reading is the evidence for its refused generation reading. Nobody maintains surname lists. Each carries its bearer counts as dated provenance (source, count, date), and **counts never compute a reading** (decision 12): two data sets deciding one reading would make the decision unreadable. Counts are evidence for the person who declares a reading, can be cited in an ambiguity report, and flag a word for review when a new census changes its count.

The swap is measured to be safe as a starting point: deriving both markers from name readings reproduces today's sets exactly if the readings are declared on exactly the flagged words, because no word sits in one marker set while needing to stay out of the other (decisions/vocabulary-model, 2026-10-18, with the recompute). After the swap, the counts are what expose the weak flags.

Not every marker derives. `e` and `i` may be read as an initial in a name written in one case, and `y` may not, though all three are single-letter conjunctions; `may_be_initial` stays an explicit property.

### The gate, for every reading kind

Today the gates are separate rules, each written for one class of word and each reading its own evidence:

- an acronym that is also a name (`ma`, `do`): its periods, its capitals and the words left beside it ([rules/S3](rules/S3-credentials-written-with-interior-periods.md), credentials written with interior periods; [rules/S4](rules/S4-ambiguous-acronym-needs-words-to-spare.md), the ambiguous acronym needs words to spare; [rules/S6](rules/S6-case-signal-at-the-suffix-slot.md), the case signal at the suffix slot);
- a one-letter roman numeral ending a name: a word to spare, so `John V` reads family `V` and `John Smith V` suffix `V`, both reported ([rules/S10](rules/S10-trailing-roman-numeral.md), the trailing roman numeral);
- a title that may be the name: a title run with nothing but post-nominals behind it gives its last word back, so `Dr King Jr` reads family `King` and reports `title-or-name` ([rules/H3](rules/H3-title-runs-floor.md), the title run's floor);
- a particle that may be a given name: its position, so `Van Johnson` keeps `Van` as the given name and reports the fork ([rules/P4](rules/P4-particle-at-the-front-of-the-name.md), a particle at the front of the name);
- a bound given name: a name word to spare, so `abdul rahman` stays two names and `abdul rahman khan` joins them ([rules/P5](rules/P5-bound-given-names.md), bound given names);
- a single-letter conjunction that may be an initial: the name's case, so `JOHN E SMITH` reads `E` as a middle initial and reports it ([rules/P8](rules/P8-single-letter-connective-against-the-initial-it-spells.md), a single-letter connective against the initial it spells).

A listed word that none of these reaches is read wherever its position allows, and a word too risky for that is kept out. That is why `fils`, a whole-word generation word that S10's count does not reach, is excluded rather than marked. Phase 2 makes the gate a property of a reading, so that any reading that can clash with a name is gated by the evidence its form offers, rather than a rule written for each class of word; the rules above are the evidence it starts from.

`fils` shows what that buys. Emulated by adding it as an ambiguous acronym (measured 2026-10-19, master `e9855df0`):

| Input | Today (`fils` excluded) | Gated |
|---|---|---|
| `Alexandre Dumas fils` | middle `Dumas`, family `fils` | family `Dumas`, suffix `fils`, reported |
| `ALEXANDRE DUMAS FILS` | middle `DUMAS`, family `FILS` | family `DUMAS`, suffix `FILS`, reported |
| `Marie Fils` | family `Fils` | family `Fils`, reported |
| `Jean Pierre Fils` | family `Fils` | family `Fils`, reported |
| `Dumas, Alexandre, fils` | suffix `fils` | suffix `fils` |

Every row is right or unchanged, and the forks are reported. But the emulation borrows the acronym gate's cues, and capitals are an acronym's cue, not a generation word's: it suits `fils` because French writes the word in lowercase. What evidence each kind's gate reads is phase 2's central question:

- a lowercase word after the name (`fils`) has its case;
- an initial-shaped one (Spanish `H.` for *hijo*, German regnal `I.`) has the count S10 already gives a bare one-letter numeral, against a period, which marks a one-letter word as an initial ([rules/T5](rules/T5-written-shape-of-an-initial.md), the written shape of an initial);
- a reading with no reliable cue at all may need to be pack-only (`default = false`, phase 3).

**A gate at the front of the name** is the same question for titles. `dean`, `justice` and `major` are title words borne as given names, left out of `titles` today. The candidate rule is that such a word is a title only inside a title phrase: after a modifier or another title (`Chief Justice`), before a phrase link (`Dean of Students`), or with a head title after it (`Major General`). Today all three of those read the word as a given name (measured 2026-10-19), while `Dean Martin` correctly does. Two decisions bound it: `Dean Smith` keeps reading given `Dean` (decision 13), and the rule covers only words outside `titles` today, so a title that is also a given name (`prince`, `sir`) is decided one word at a time and never re-decided silently by recording a given reading (decision 16). Title-phrase modifiers (`vice`, `rear`, `grand`) are the same rule from the other side: a title only next to a head title (decision 10, parked).

### Readings on the parse

A caller should be able to see the reading behind a parse: its language, kind, native spelling (`do` → `Đỗ`) and counts. The intended split is that **an `Ambiguity` carries the reading the parse did not take**, and **a token carries the reading it did**, so `Nguyen Van Do`, which forks nothing, still exposes `Đỗ` without a report nobody would act on. The API shape is open (#752).

## Phase 3: packs that prefer or restrict

A pack is a choice of languages. Two strengths (decision 6):

- **prefer** settles a clash where the chosen language has a vocabulary reading: the word keeps that language's readings and loses other languages' vocabulary readings. Under Portuguese, `do` is a particle only.
- **strict** also drops other languages' name readings. It is for single-origin data.

The asymmetry is deliberate (decision 15): **vocabulary readings settle a clash; name readings only keep the gate on.** `do` shows why. Its Vietnamese reading is a name only (Đỗ). If name readings settled clashes, preferring Vietnamese would drop the credential reading, and `John Smith DO`, a suffix today, would read `DO` as the family name. Under the rule, Vietnamese holds no vocabulary reading of `do`, so preferring it settles nothing: the credential and particle readings stay, gated as in the default.

Consequences that follow from the definitions:

- **Order does not matter.** Prefer and strict are sets of languages, so combining packs is commutative.
- **Two chosen languages that each hold a vocabulary reading both keep it**, and the word stays gated, as in the default.
- **Non-Latin vocabulary stays on under any choice**, because it selects itself by script (`씨`, `さん`, Cyrillic titles). Almost every clash between languages is within one script: `do`, `e`, `van` are all Latin.
- **Whether a word needs a pack depends on where its clash is.** `do` clashes between languages (a Portuguese particle, an English credential, a Vietnamese surname), so a pack settles it. `fils` clashes within French, a generation word and a French surname, so no pack settles it and the phase 2 gate does the work. This reverses the premise of #684, which proposes a French pack to read `fils` as a suffix: under decisions 6 and 15, a French pack keeps both of French's readings, and `Marie Fils` would still need the gate to keep her family name.

**A pack can outrank a shape rule, not only a vocabulary reading** (decision 20). `Ma. Cristina Santos Reyes` reads title `Ma.` today because the leading period-abbreviation rule claims the word before any vocabulary is consulted; in Filipino names `Ma.` abbreviates María. So shape rules (period abbreviation, initials, capitals) must emit readings into the same pool as vocabulary, where a pack's preference can act on them, rather than final answers.

**What moves in phase 3:** the locale packs' vocabulary, still in Python today, becomes language files; `default = false` marks a reading for pack-only words too risky even gated; and the reserved names `prefer`, `strict` and `default` gain their meaning. How a tag filters (does `pt` match `pt-BR`?) and how a third-party language file joins the pool and the snapshot are open under #753.

## Phase 4: order, shape and the output model

### Order is not shape

Decision 14 separates two things a "language" was going to carry:

- **Order** says which position holds which role. It is a small closed set (`GIVEN_FIRST`, `FAMILY_FIRST`, `FAMILY_FIRST_GIVEN_LAST`, plus the order a script implies) and a claim about how the data was written. A language supplies only a default (Hungarian and Vietnamese are family-first in Latin script), and the caller overrides it.
- **Shape** says where the non-name parts sit around the name: titles, suffixes, particles, commas. Shapes belong to an order, not to a language, so they live in the core.

CLDR's person-name data shows why. Its surname-first renderings put the title between the family and the given name more often than in any other position (counted 2026-10-16 in the CLDR corpus, across about fifty locales including `en`, `de` and `pt`), so it is a shape of `FAMILY_FIRST` everywhere, not a convention of some language. Today it is misread (measured 2026-10-19):

| Input under `FAMILY_FIRST` | Today |
|---|---|
| `Brühl Dr. Ada` | family `Brühl`, given `Dr.` |
| `Brühl Prof. Dr. Ada Cornelia` | family `Brühl`, given `Prof.`, middle `Dr. Ada Cornelia` |

The plan is to keep order a few permutations and make shapes first-class, each order accepting a listed set of them. The shape inventory (#469) is the start, and it doubles as the test grid that AGENTS.md's comma-shape and `name_order` sweeps describe. The related comma bug, a title before a family comma, was fixed in 2.x ([rules/H6](rules/H6-title-before-a-family-comma.md), a title before a family comma).

### The rules a pack can choose

A language file will hold a `[rules]` table that turns on rules implemented in the core: a default order, patronymic and married-name endings, a surname span, a compound given name. A new rule kind is a core change with a mechanisms.md entry, never code in a pack; the one code hook stays the segmenter. The existing packs fit: ZH and JA turn on segmentation, and RU and TR_AZ become ending rules, whose deviations could then be computed rather than hand-copied. Measured gaps each rule would close (2026-10-19):

| Rule | Input | Today |
|---|---|---|
| surname span (es, pt) | `Gabriel García Márquez` | middle `García`, family `Márquez` |
| compound given name (pt) | `Maria do Carmo Silva` | given `Maria`, family `do Carmo Silva` |
| married-name ending (hu) | `Kovács Jánosné` | given `Kovács`, family `Jánosné` |
| digraph initials (cs) | `Petr Chmelař` | initials `P. C.` |

The real-name corpora agree on the priority. In the GND and Wikidata corpora, Spanish and Latin American double surnames written given-first disagreed with the source on 315 of 390 names, while the same kind of names in index form, where the comma settles it, disagreed on 0 of 60 (counted 2026-10-16 on master `4375b01b`, from `gnd_agreement.json` and `wikidata_agreement.json`): the gap is order and span, not vocabulary.

### The output model

Phase 4 also decides what a parse returns, aligned with CLDR's person-name fields, which gives ground truth for free:

- **A second surname** (`surname2`) for Spanish, Catalan and Galician names, which CLDR's samples carry and nameparser has no field for.
- **A patronymic field** (decision 8), holding only a living patronymic. Its main value to callers is that `family` can be empty for the cultures that have no family name: `Soffía Karlsdóttir` reads family `Karlsdóttir` and `Mahathir bin Mohamad` family `bin Mohamad` today, where a letter addressed to "Mr. {family}" is wrong. Whether the field is `patronymic` or a neutral list of parent names, which a matronymic also fits, is open under #754.
- **Credentials separate from generation suffixes** (#326), and a decision on whether honorifics after a name get a field or stay a reading kind inside `suffix`.
- **What `middle` means** when a given name is several words (#704).
- **Gender**, recorded only where a word gives a definitive clue (decision 9): reported with its evidence, never inferred from given names.

## The first packs

Which packs come first once phase 3 exists is tracked in #747, not here. The surname-span measurement above is one input, but it was taken over corpora built to hold second surnames, so it shows that the gap exists, not how it ranks against the others.

## Where each fact lives

The design notes these phases came from are working notes and are not kept. What lasts goes to one home each:

| Fact | Home |
|---|---|
| A single word: what it stands for, its counts, a refused reading | its TOML entry |
| When any word may join a class (the collision criterion) | decisions/vocabulary-collisions and its neighbours |
| A decision about the model, when it is made | decisions/vocabulary-model |
| How the parser reads a shape the design settles | rules/, with `tracked:` or `deviates:` until it ships |
| A language's conventions | that language's file and `[rules]`, plus a rule for each rule kind a pack adds |
| An open question | its issue, linked from a decisions entry, never restated |
| Where the model is going | this document |
