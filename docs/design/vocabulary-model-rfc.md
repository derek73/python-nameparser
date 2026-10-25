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
| 2 | Ambiguity derived from clashing readings; the ambiguity gate extended to every reading kind | yes, the first phase that does | #752, design agreed 2026-10-23 |
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

Phase 2 is the first phase that changes how names are parsed. Its design was agreed on 2026-10-23 (#752); the decisions, the evidence for each and the options declined are decisions/vocabulary-model's entry of that date. What follows is the design as agreed.

### Three sources of readings

Every clash the parser decides is between readings of one token, and phase 2 puts them in one pool:

- **Vocabulary readings**, the TOML kinds: titles, suffixes, particles, conjunctions, bound given names, birth markers.
- **Declared name readings**, `given` and `family`, written by hand on a word some file claims or refuses (decision 11), with dated counts as provenance that never compute a reading (decision 12). Nobody maintains surname lists.
- **Shape readings**, which today are rules standing around the vocabulary: the initial ([rules/T4](rules/T4-bare-letter-as-an-initial.md), a bare letter as an initial; [rules/T5](rules/T5-written-shape-of-an-initial.md), the written shape of an initial), the leading abbreviation title ([rules/H2](rules/H2-leading-abbreviation-title.md)), the dotted acronym ([rules/S3](rules/S3-credentials-written-with-interior-periods.md)), the capitals acronym ([rules/S9](rules/S9-unlisted-words-that-join-the-ambiguous-class-by-shape.md), unlisted words that join the ambiguous class by shape), the roman numeral past the listed ones ([rules/S10](rules/S10-trailing-roman-numeral.md)), paired initials ([rules/C5](rules/C5-paired-initials-after-the-comma.md), paired initials after the comma), and the joined and split spellings of a credential that phase 2 adds.

Shape readings join the pool because of decision 20: a vocabulary reading can outrank a shape-derived one only if the shape's answer is a reading the gate weighs, not a verdict already written into a tag. Settling a clash by rewriting a tag also erases the word's other readings: retagging a capitals `DO` as an unambiguous credential let its particle reading take it into the family (`Doe, John DO`), which is why the case cue for credentials (#785) waits for the pool.

### Ambiguity from readings

A **clash** is a token whose readings would put it in different fields. The two markers that are clashes with a NAME become derived:

- an acronym that may be a name is a word with a credential reading and a `given` or `family` reading;
- a particle that may be a given name is a word with a particle reading and a `given` reading.

The swap is snapshot-neutral by construction once the missing name readings are written, because no word sits in one marker set while needing to stay out of the other (decisions/vocabulary-model, 2026-10-18, with the recompute). The missing readings are declared on the flagged words, a few of them without a count, which a required `note` then explains. After the swap the build refuses the flags themselves, naming the reading to write instead, and a particle with no given reading still states `may_be_given = false`, so a new particle cannot fall to the unsafe side silently.

`may_be_initial` is not derived. Its clash is with the initial, a shape reading every cased single letter has, and which letters a tradition writes both ways is a judgment about the letter, not a name anyone bears: `e` and `i` may be read as an initial in a name written in one case, `y` may not.

### One gate, four steps

Every clash is decided by one ordered question, asked at each site that reaches it today:

1. **Floor.** The name keeps a word to address: a title run gives its last word back ([rules/H3](rules/H3-title-runs-floor.md), the title run's floor), the second of two name words stays the family ([rules/S4](rules/S4-ambiguous-acronym-needs-words-to-spare.md), [rules/S10](rules/S10-trailing-roman-numeral.md)), and a bound given name keeps a family word in reserve ([rules/P5](rules/P5-bound-given-names.md)).
2. **Form.** A cue the reading's kind declares, read off the word's writing, settles the clash, and a clash settled by form is not reported.
3. **Structure.** The slot's own rule, in the order each slot reads it today: the ambiguous class at the comma ([rules/C4](rules/C4-ambiguous-credential-class-at-the-comma.md), the ambiguous credential class at the comma), the company of an unambiguous credential ([rules/S7](rules/S7-company-of-an-unambiguous-credential.md)), the credential's trailing run ([rules/S8](rules/S8-credentials-trailing-run.md)), a particle's leading position ([rules/P4](rules/P4-particle-at-the-front-of-the-name.md)), and the title phrase at the front of the name.
4. **Count.** Words to spare (S4, S10).

A clash not settled at step 2 is reported at the decision site (mechanisms.md#AMBIGUITY-AT-THE-DECISION-SITE), in the kind the slot reports today.

**Where one gate does not reproduce the six rules.** H3 and P5 weigh no second reading: they reach every member of their category and read only a count, so they stay floors, step 1, and "one gate for six" means four clashes and two floors. The ambiguous acronym is reached at nine sites, each reading its cues in its own order, and that order is behavior, so the nine sites stay; what becomes one is the predicate each asks (mechanisms.md#ONE-PREDICATE-PER-QUESTION). Everything else reproduces once the name readings are declared, except `ld`, whose name reading is moved into its credential reading's `note` so that it stays ungated.

### What each kind reads

| Reading kind | Clashes with | Form cues (step 2) | Then |
|---|---|---|---|
| credential, acronym | a name reading | its periods; capitals in a name of mixed case, asked of the whole name; Title case leans to the name; the joined (`MD/PhD`) and split (`Pharm. D.`) spellings | the comma count, the company, the run, the count |
| generation, whole word (`fils`) | a family reading | lower case in a name of mixed case settles the generation; Title case leans to the name | the count |
| generation, agnomen (`Filho`, `Neto`) | a family or given reading | none: an agnomen is written in the case of the name around it | the count |
| generation, roman numeral | the initial, for one letter; a name word | a period makes it an initial; lower case in a name of mixed case settles the generation; Title case leans to the name; an initial before it makes it a name word | the count |
| generation, initial-shaped (`H.` for *hijo*, regnal `I.`) | the initial | none: written with its period it is exactly an initial | no cue: `default = false`, for a pack |
| particle | a given reading | none: `Van` and `van` are both written | the leading position, the lone particle's fold |
| conjunction, one letter | the initial | the name's case ([rules/P8](rules/P8-single-letter-connective-against-the-initial-it-spells.md)); in one case, `may_be_initial` | — |
| title at the front | a given or family reading | none | the phrase partner, the title before it |
| bound given name | none (a floor) | — | — |

A reading whose writing offers no cue is one the gate could only guess, so it is `default = false`: recorded in the TOML, compiled to nothing by default, turned on by a pack in phase 3. Spanish `H.`, German regnal `I.` and Czech `st.` are the first.

**The numerals ask one predicate.** `i` to `v` are vocabulary and `vi` to `x` are shape, and today some rules ask only the vocabulary, so `John Smith III MD` and `John Smith VI MD` read differently (#784, #774). One predicate answers for every spelling the way the trailing numeral rule does (shape, the count for one letter, an initial in front, the period, the case), and every rule that asks either recognizer asks it. Listing `vi` to `x` instead was measured and declined: a middle initial `X` would read as a generation.

**`fils` and the agnomens show what kind-specific cues buy.** `fils` is gated by its case and the count, so `Alexandre Dumas fils` is to read suffix `fils` while `Marie Fils` keeps her family name, reported. The Brazilian agnomens are gated by the count alone: case would say nothing, and the plain generation reading breaks real surnames (`Ana Neto`) and given names.

**A credential's spelling is a form cue.** A credential joined by `-` or `/` reads as one when every chunk is listed and none is ambiguous, since a hyphen also joins names (`Smith-Jones`); an unlisted word of capitals joined that way joins the ambiguous class after a comma, gated by the name's case contrast. A credential split across a space (`Pharm. D.`, generalizing the `Ph. D.` merge) merges only where its first chunk has two or more letters, and the merged piece is a member of the ambiguous class, decided by the comma count and words to spare: an opening single letter is a middle initial (`SMITH, JOHN A. MS.` holds an initial and a salutation, not a credential `AMS`), which is also why #872 stopped reading two dotted single letters as a credential. The merged piece starts the credential's run (#827), once the numeral predicate answers the numeral before a credential.

### The front of the name

The front of a name has no words-to-spare cue: a title addresses the name after it. What it has is the contested-head rule. **A title word that also has a name reading is a title only inside a title phrase:**

- **The title before it is not a partner.** A contested word after another title is the given name (`Mr Sultan Khan`, `Ms Princess Ada Obi`, #853), unless that title is its partner; today `Mr Sultan Khan` reads title `Mr Sultan`.
- **Its partner** is a modifier or a style before it (`Her Royal Highness Princess Anne`), `of` after it (`Dean of Students`), or a head title after it that the word `attaches` to (`Major General`). A salutation is never a partner (`SMITH, DEAN MR.` is a given name and a salutation).
- **Modifiers** (decision 10, unparked) are titles only beside a head title, at the head of the name only, never in a comma part, where a lone title word is the person's role.

Which title words get a given reading is decided one word at a time (decision 16), in measured batches, and `Dean Smith` keeps reading given `Dean` (decision 13). A title that only ever stands in front stays a title (`lord`, `sir`, `lady`), and a word that opens names in one tradition but is a title class in another (`guru`, with its Devanagari twin) waits for a language pack. Where the rule reads a contested title as a name, the parse reports `title-or-name`.

**Abbreviated given names** use the same pool from the other side (#789): a `given` reading with `same_as` the full name (`chas` → Charles, Filipino `ma` → María) is to outrank the leading-abbreviation title rule's shape, so that `Ma. Cristina Santos Reyes` reads given `Ma.` where today it reads title `Ma.`.

### Brackets

A bracketed or quoted credential escapes the nickname reading where its writing settles it ([rules/S1](rules/S1-bracketed-credential-is-not-a-nickname.md), #810): with interior periods, or in capitals in a name of mixed case, the case asked of the whole name. `(Ed)` stays a nickname, and so does content standing inside the name rather than after it (`Jean 'JD' Smith`).

### Readings on the parse

A caller should be able to see the reading behind a parse. **An `Ambiguity` carries the reading the parse did not take** (`Ambiguity.alternative`: its kind, the field it would have put the token in, and whether it came from the vocabulary, a declared name or a shape), and **a token carries the reading it did** (`Token.reading`), so `Nguyen Van Do`, which forks nothing, can still expose `Đỗ` without a report nobody would act on. A word the credential's run takes by position alone is told from a word with a declared name reading by that source, so it needs no new ambiguity kind. `Ambiguity.alternative` is planned for a 2.x minor, with the pickle guard widened to accept a field added later; `Token.reading` waits for 3.0, since it needs a per-word reading index compiled for parse time.

### The phase 1 reserved names

Phase 2 gives two of them meaning: `attaches`, the phrase partner above, a property of a title reading naming the title kinds it qualifies; and `default = false`, for readings with no cue. `leading_only` and `trailing_only` are not needed, the gate's slots carrying position; `bare_only` is settled by shape already ([rules/P7](rules/P7-one-letter-particle-against-the-initial-it-spells.md), a one-letter particle against the initial it spells); `separators` belongs with `attached` and its other side, phase 4's glued words. Those four stay reserved, their messages naming the phase that needs them.

### The order of work

Each sub-phase is one PR, measured on its own base: the committed snapshot read by shape, the PSC register's fielded names scored for fixed, broken and changed records (`local_agreement.py psc-individuals`, the main measure, since its filers separated the fields), the local snapshots it reaches, and the rules it moves amended in the same diff.

| Sub-phase | What | Needs |
|---|---|---|
| 2a | the derived markers: the name readings declared, the flags refused | — (neutral) |
| 2b | one predicate per question: the split-credential merge, the numeral, paired initials in a script with capitals | — (neutral) |
| 2c | joined credentials, every chunk listed | 2b |
| 2d | joined unlisted capitals after a comma | 2b |
| 2e | split credentials, and the merged piece starting the run (#827) | 2b, 2f |
| 2f | every numeral rule asks one predicate (#784, #774, #819) | 2b |
| 2g | capitals settle a listed credential (#785), through the pool | 2a |
| 2h | generation readings gated by kind: `fils`, the agnomens, `default = false` | 2b |
| 2i | the front of the name: the phrase partner, the contested heads, #853's word after a title, modifiers at the head | 2b |
| 2j onward | titles that are names, one batch per word or group, in the agreed order | 2i |
| 2k | abbreviated given names over the leading-abbreviation title (#789) | 2b |
| 2l | the bracket escape reads the derived clash (#810) | 2a |
| 2m | surfacing, `Ambiguity.alternative` | the rest |

2a and 2b are independent of each other. Measured changes that belonged outside phase 2 shipped as 2.x PRs: bare `wm` (#873), the `;` between credentials (#871), two dotted single letters as a surname (#872) and `sa` out of the vocabulary (#879).

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
| surname span | `Gabriel García Márquez` | middle `García`, family `Márquez` by default; family `García Márquez` under the opt-in `Policy(two_family_names=True)` |
| compound given name (pt) | `Maria do Carmo Silva` | given `Maria`, family `do Carmo Silva` |
| married-name ending (hu) | `Kovács Jánosné` | given `Kovács`, family `Jánosné` |
| digraph initials (cs) | `Petr Chmelař` | initials `P. C.` |

The surname span has shipped ahead of the packs, as an opt-in `Policy` field rather than a pack, since the convention is not one language's ([rules/O6](rules/O6-two-family-names.md), two family names, #875 and #878; decisions/O6 has why it is not `locales.ES`). A pack can later switch it on in its `[rules]`, as it will a default order.

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
