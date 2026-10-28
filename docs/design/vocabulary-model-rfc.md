# RFC: the vocabulary model and language packs

Status: **design overview**, written 2026-10-19 after phase 1 shipped. It says where the vocabulary model is going and why, phase by phase. It is not the record: each decision is logged in [decisions/vocabulary-model](decisions/vocabulary-model.md) when it is made, and where the two differ, that entry is right and this document is stale. Each later phase gets its own design when it starts, under its issue; this overview is amended as they land. Work is tracked in #747.

For editing the vocabulary as it is today, read [nameparser/vocab/README.md](../../nameparser/vocab/README.md) instead.

## The short version

nameparser recognizes words by vocabulary: titles, suffixes, particles, conjunctions, bound given names, maiden markers. Until 2.6 that vocabulary was a set of base sets plus marker subsets (`particles` and `particles_ambiguous`, `suffix_acronyms` and `suffix_acronyms_ambiguous`, ...). The model replaces the sets with a description of each **word** by its **readings**: what the word can be in a name, and the properties of each reading.

```toml
[[word]]
text = "do"
family = { us_census_2010 = 30301, wikidata = 100, as_of = 2026-10-25 }
given = { us_ssa = 11, wikidata = 9, as_of = 2026-10-25, note = "male births only; Wikidata is a lower bound" }
credential = { expands = "Doctor of Osteopathic Medicine" }
[word.preposition]
expands = "of the, masc. sg."
```

`do` is a credential and a particle, and Vietnamese Đỗ makes it a surname too: its name readings, with the counts they rest on, are what mark both clashes (an entry spread over two files in the shipped data, `en.toml` and `pt.toml`). Under the sets that clash was visible only as an overlap between two of them; as readings it is written on the word. Once every word says which language's names it occurs in, choosing a language can settle the clashes that exist only because the default serves every language.

Four phases, in a fixed order:

| Phase | What | Changes parsing? | State |
|---|---|---|---|
| 1 | The per-word TOML format, compiled to today's sets | no | shipped in 2.6 (#737, #744); #749–#751 gave the words in `und.toml` their languages, leaving two particles of unrecorded origin |
| 2 | Ambiguity derived from clashing readings; the ambiguity gate extended to every reading kind | yes, the first phase that does | #752, design agreed 2026-10-23; 2a, the two name-clash markers derived, landed without moving a parse (decisions/vocabulary-model, 2026-10-25) |
| 3 | Language packs that prefer or restrict their language | yes, for callers who choose one | #753, needs 1 and 2 |
| 4 | Order and shape; the rules a pack can choose; the output model | yes | #754, 3.0 work; its output model agreed 2026-10-28, ahead of or alongside phase 3's mechanism |

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

- **The marker sets were explicit flags** (`may_be_given`, `may_be_name`, `may_be_initial`), not derived from name readings, recording past curation rather than evidence. Phase 2a (2026-10-25) derived the two that record a clash with a name, `may_be_name` and `may_be_given`, from name readings, each with dated counts or a `note` where no source counts the word (`te`, `tho` and `du`, once thought to have none, have SSA counts), keeping `may_be_initial` as a property (decisions/vocabulary-model).
- **Names a later phase will use are build errors** (phase 1 reserved `default`, `prefer`, `strict`, `bare_only`, `leading_only`, `trailing_only`, `attaches`, `separators`, and the values `addresses = "full"` or `"any"`), so nothing reads as working before it does. Phase 2h (2026-10-25) gave `default = false` its meaning, a reading recorded that compiles to nothing, and named the phase each of the others waits for; phase 2i gave `attaches` its meaning, the phrase partner below.

The reference for the format is nameparser/vocab/README.md; the decisions behind it, with what was declined and measured, are decisions/vocabulary-model's 2026-10-18 entry.

## Phase 2: derived ambiguity and a general gate

Phase 2 is the first phase that changes how names are parsed. Its design was agreed on 2026-10-23 (#752); the decisions, the evidence for each and the options declined are decisions/vocabulary-model's entry of that date. What follows is the design as agreed. Every sub-phase below had landed by 2026-10-27, when #752 closed; the title words 2j did not reach are #913's.

### Three sources of readings

Every clash the parser decides is between readings of one token, and phase 2 puts them in one pool:

- **Vocabulary readings**, the TOML kinds: titles, suffixes, particles, conjunctions, bound given names, birth markers.
- **Declared name readings**, `given` and `family`, written by hand on a word some file claims or refuses (decision 11), with dated counts as provenance that never compute a reading (decision 12). Nobody maintains surname lists.
- **Shape readings**, which today are rules standing around the vocabulary: the initial ([rules/T4](rules/T4-bare-letter-as-an-initial.md), a bare letter as an initial; [rules/T5](rules/T5-written-shape-of-an-initial.md), the written shape of an initial), the leading abbreviation title ([rules/H2](rules/H2-leading-abbreviation-title.md)), the dotted acronym ([rules/S3](rules/S3-credentials-written-in-joined-chunks.md)), the capitals acronym ([rules/S9](rules/S9-unlisted-words-that-join-the-ambiguous-class-by-shape.md), unlisted words that join the ambiguous class by shape), the roman numeral past the listed ones ([rules/S10](rules/S10-trailing-roman-numeral.md)), paired initials ([rules/C5](rules/C5-paired-initials-after-the-comma.md), paired initials after the comma), and the joined and split spellings of a credential that phase 2 adds.

Shape readings join the pool because of decision 20, which lets a pack's preferred reading outrank a shape-derived one, and which phase 2 applies in the default as well (an abbreviated given name over the leading-abbreviation title, below): a reading can outrank a shape-derived one only if the shape's answer is a reading the gate weighs, not a verdict already written into a tag. Settling a clash by rewriting a tag also erases the word's other readings: retagging a capitals `DO` as an unambiguous credential let its particle reading take it into the family (`Doe, John DO`), which is why the case cue for credentials (#785) waited for the pool. Phase 2g (2026-10-25) settles it where each site chooses a reading, the word keeping its tags ([rules/S6](rules/S6-case-signal-at-the-suffix-slot.md)).

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

**The numerals ask one predicate.** `i` to `v` are vocabulary and `vi` to `x` are shape, and until 2f some rules asked only the vocabulary, so `John Smith III MD` and `John Smith VI MD` read differently (#784, #774). One predicate answers for every spelling the way the trailing numeral rule does (shape, the count for one letter, an initial in front, the period, the case), and every rule that asks either recognizer asks it. Listing `vi` to `x` instead was measured and declined: a middle initial `X` would read as a generation.

**`fils` and the agnomens show what kind-specific cues buy.** `fils` is gated by its case and the count, so `Alexandre Dumas fils` reads suffix `fils` while `Marie Fils` keeps her family name, reported. The Brazilian agnomens are gated by the count alone: case would say nothing, and the plain generation reading breaks real surnames (`Ana Neto`) and given names. Phase 2h landed both on 2026-10-25, the floor holding before the case cue (`Dumas fils` keeps its family name, Derek) ([rules/S11](rules/S11-suffix-word-that-is-also-a-name.md), a suffix word that is also a name), with `default = false` for the three readings with no cue.

**A credential's spelling is a form cue.** A credential joined by `-` or `/` is to read as one when every chunk is listed and none is ambiguous, since a hyphen also joins names (`Smith-Jones`); an unlisted word of capitals joined that way is to join the ambiguous class after a comma, gated by the name's case contrast. `John Smith, MD/PhD` read given `MD/PhD` until phase 2c (2026-10-25) read the listed half: a joined word whose every chunk counts as a suffix as written ([rules/S3](rules/S3-credentials-written-in-joined-chunks.md)). A credential split across a space (`Pharm. D.`, generalizing the `Ph. D.` merge) is to merge only where its first chunk has two or more letters, the merged piece a member of the ambiguous class, decided by the comma count and words to spare: an opening single letter is a middle initial (`SMITH, JOHN A. MS.` holds an initial and a salutation, not a credential `AMS`). #872 made the same judgment for the joined spelling (`A.B.`), in scripts with capitals and outside the slot right after a comma. The merged piece is also to start the credential's run (#827), once the numeral predicate answers the numeral before a credential; since [rules/S8](rules/S8-credentials-trailing-run.md) refuses a member of the ambiguous class as a run start, how the two combine is the split-credential PR's to state (today's `Ph. D.` merge is unambiguous, and S8 already covers it). Phase 2e (2026-10-25) did both ([rules/S12](rules/S12-credential-split-across-a-space.md)): `John Smith, Pharm D` reads suffix `Pharm D`, and the split pair is the one member of the class that starts the run, behind the two name words its own count asks for.

### The front of the name

The front of a name has no words-to-spare cue: a title addresses the name after it. What it has is the contested-head rule. **A title word that also has a name reading is a title only inside a title phrase:**

- **The title before it is not a partner.** A contested word after another title is the given name (`Mr Sultan Khan`, `Ms Princess Ada Obi`, #853), unless that title is its partner; `Mr Sultan Khan` read title `Mr Sultan` until phase 2j gave `sultan` its given reading.
- **Its partner** is a modifier or a style before it (`Her Royal Highness Princess Anne`), `of` after it (`Dean of Students`), or a head title after it that the word `attaches` to (`Major General`). A salutation is never a partner (`SMITH, DEAN MR.` is a given name and a salutation).
- **Modifiers** (decision 10, unparked) are titles only beside a head title, at the head of the name only, never in a comma part, where a lone title word is the person's role; a modifier that is also a given name (`wing`, phase 2j) is read by that test in every part.

Phase 2i carried this out as [rules/H9](rules/H9-title-phrase.md) (the title phrase), with `of` after a modifier as a partner too (`Member of Parliament`) and a modifier in a connective's object (`President of the United States`); a title that may be a given name compiles out of `titles`, so one a caller lists there is a title everywhere. Which title words get a given reading is decided one word at a time (decision 16), in measured batches, and `Dean Smith` keeps reading given `Dean` (decision 13). A title that only ever stands in front stays a title (`lord`, `sir`, `lady`), and a word that opens names in one tradition but is a title class in another (`guru`, with its Devanagari twin) waits for a language pack. Where the rule reads a contested title as a name, the parse reports `title-or-name`.

**Abbreviated given names** use the same pool from the other side (#789): a `given` reading with `same_as` the full name (`chas` → Charles, Filipino `ma` → María) is to outrank the leading-abbreviation title rule's shape, so that `Ma. Cristina Santos Reyes` reads given `Ma.` where it read title `Ma.`. Phase 2k (2026-10-26) did this: the reading compiles into `GIVEN_NAME_ABBREVIATIONS`, which [rules/H2](rules/H2-leading-abbreviation-title.md)'s shape declines, and nothing else reads it.

### Brackets

A bracketed or quoted credential is to escape the nickname reading where its writing settles it (#810): with interior periods, or in capitals in a name of mixed case, the case asked of the whole name. `(Ed)` stays a nickname, and so does content standing inside the name rather than after it (`Jean 'JD' Smith`).

Phase 2l carried this out as [rules/S13](rules/S13-bracketed-member-settled-by-its-writing.md) (a bracketed member settled by its writing) rather than as an amendment to [rules/S1](rules/S1-bracketed-credential-is-not-a-nickname.md), since the position it reads is a signal S1 does not: `John Smith (MA)` and `John Smith (M.A)` read suffix, and `JOHN SMITH (MA)` and `Jeffrey (JD) Bricken` keep the nickname. The writing is read as the rules that read it say, S3 for the periods and S6 for the capitals in a name of mixed case, and S13's own signal is the position. A settled member is the suffix, decided in one pass, rather than the word read bare, since bare, `M.A` reads as initials; where the rest of the name then reads otherwise than beside a bracketed unambiguous credential (`Jack (MA)` keeps family 'Jack' where `Jack (PhD)` reads given 'Jack'), S13 records the difference as accepted.

### Readings on the parse

A caller should be able to see the reading behind a parse. **An `Ambiguity` carries the reading the parse did not take** (`Ambiguity.alternative`: its kind, the field it would have put the token in, and whether it came from the vocabulary, a declared name or a shape), and **a token carries the reading it did** (`Token.reading`), so a word whose reading forks nothing still says what it was read as, without a report nobody would act on (phase 4's 4a; a native spelling such as `do`'s Vietnamese `Đỗ` is not part of it). A word the credential's run takes by position alone is told from a word with a declared name reading by that source, so it needs no new ambiguity kind. `Ambiguity.alternative` shipped in 2.7 (decisions/A1, 2026-10-26 #752): a `Reading` of a kind, the field the word would land in with every other word read as the parse read it, and a source, which is `vocabulary`, `declared`, `shape` or `position`, the fourth being the reading of an ordinary word nothing lists, which is what a word the credential's run took by position alone has. The pickle guard was widened to accept a field added later. A `languages` field, naming the files that hold a reading, was weighed and left out: it needs the per-word reading index, which costs about 0.4 ms of a 19.5 ms import and could not describe a pack's or a caller's lexicon, so it waits with `Token.reading` for 3.0.

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
| 2g | capitals settle a listed credential (#785), through the pool | 2a, 2b |
| 2h | generation readings gated by kind: `fils`, the agnomens, `default = false` | 2b |
| 2i | the front of the name: the phrase partner, the contested heads, #853's word after a title, modifiers at the head | 2b |
| 2j onward | titles that are names, one batch per word or group, in the agreed order; the words left are #913's | 2i |
| 2k | abbreviated given names over the leading-abbreviation title (#789) | 2b |
| 2l | the bracket escape reads the derived clash (#810) | 2a, 2b |
| 2m | surfacing, `Ambiguity.alternative` | the rest |

2a and 2b are independent of each other. The sub-phase that gives a reserved name its meaning updates nameparser/vocab/README.md's reserved-names table with it: 2h for `default`, 2i for `attaches`. Measured changes that belonged outside phase 2 shipped as 2.x PRs: bare `wm` (#873), the `;` between credentials (#871), two dotted single letters as a surname (#872) and `sa` out of the vocabulary (#879).

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

**A pack can outrank a shape rule, not only a vocabulary reading** (decision 20). Shape rules (period abbreviation, initials, capitals) emit readings into the same pool as vocabulary from phase 2 on, rather than final answers, so a pack's preference can act on them. Phase 2 is to settle one such clash in the default, since every language loads there: Filipino `Ma.`, which abbreviates María, is to get a `given` reading in `fil.toml` that outranks the leading period-abbreviation rule (`Ma. Cristina Santos Reyes`, title `Ma.` until phase 2k gave it that reading on 2026-10-26); a pack's part is to prefer such readings where the default leaves both standing.

**What moves in phase 3:** the locale packs' vocabulary, still in Python today, becomes language files; `default = false`, given its meaning in phase 2, marks the readings a pack turns on, for words too risky even gated; and the reserved names `prefer` and `strict` gain their meaning. How a tag filters (does `pt` match `pt-BR`?) and how a third-party language file joins the pool and the snapshot are open under #753.

## Phase 4: order, shape and the output model

Status: **the output model is agreed** (2026-10-28, #754). The record is decisions/vocabulary-model's 2026-10-28 #754 entry; the output-model and work-order subsections below are the design its items describe. The first two subsections, order and shape and the rules a pack can choose, are as written before and are amended only where the design reaches them. Phase 4 is 3.0 work. The core API (`parse`, `Parser`, `Lexicon`, `Policy`, `Locale`, `ParsedName`) is frozen for 3.0 except for additions (decisions/3-0-reevaluations, 2026-10-28 #925, THE CORE API), so every change below says whether it is an addition.

### Order is not shape

Decision 14 separates two things a "language" was going to carry:

- **Order** says which position holds which role. It is a small closed set (`GIVEN_FIRST`, `FAMILY_FIRST`, `FAMILY_FIRST_GIVEN_LAST`, plus the order a script implies) and a claim about how the data was written. A language supplies only a default (Hungarian and Vietnamese are family-first in Latin script), and the caller overrides it.
- **Shape** says where the non-name parts sit around the name: titles, suffixes, particles, commas. Shapes belong to an order, not to a language, so they live in the core.

CLDR's person-name data shows why. Its surname-first renderings put the title between the family and the given name more often than in any other position (counted 2026-10-16 in the CLDR corpus, across about fifty locales including `en`, `de` and `pt`), so it is a shape of `FAMILY_FIRST` everywhere, not a convention of some language. Today it is misread (measured 2026-10-19):

| Input under `FAMILY_FIRST` | Today |
|---|---|
| `Brühl Dr. Ada` | family `Brühl`, given `Dr.` |
| `Brühl Prof. Dr. Ada Cornelia` | family `Brühl`, given `Prof.`, middle `Dr. Ada Cornelia` |

The plan is to keep order a few permutations and make shapes first-class, each order accepting a listed set of them. The shape inventory (#469) is the start, and it doubles as the test grid that nameparser/AGENTS.md's comma-shape and `name_order` sweeps describe. The related comma bug, a title before a family comma, was fixed in 2.x ([rules/H6](rules/H6-title-before-a-family-comma.md), a title before a family comma).

### The rules a pack can choose

A language file will hold a `[rules]` table that turns on rules implemented in the core: a default order, patronymic and married-name endings, a surname span, a compound given name. A new rule kind is a core change with a mechanisms.md entry, never code in a pack; the one code hook stays the segmenter. The existing packs fit: ZH and JA turn on segmentation, and RU and TR_AZ become ending rules, whose deviations could then be computed rather than hand-copied. Measured gaps each rule would close (2026-10-19):

| Rule | Input | Today |
|---|---|---|
| surname span | `Gabriel García Márquez` | middle `García`, family `Márquez` by default; family `García Márquez` under the opt-in `Policy(two_family_names=True)` |
| compound given name (pt) | `Maria do Carmo Silva` | given `Maria`, family `do Carmo Silva` |
| married-name ending (hu) | `Kovács Jánosné` | given `Kovács`, family `Jánosné` |
| digraph initials (cs) | `Petr Chmelař` | initials `P. C.` |

The surname span has shipped ahead of the packs, as an opt-in `Policy` field rather than a pack, since the convention is not one language's ([rules/O6](rules/O6-two-family-names.md), two family names, #875 and #878; decisions/O6 has why it is not `locales.ES`). A pack can later switch it on in its `[rules]`, as it will a default order.

**A language file's `[rules]` compiles into its shipped `Locale`'s `policy` patch**, at build time as the vocabulary does, so a rule a pack turns on is a `Policy` field (`two_family_names`, `patronymic_rules`, and the new rule kinds as new fields) and `Locale` gains no field for rules. RU and TR_AZ become that: their `PolicyPatch` written by the build from `ru.toml`'s and `tr.toml`'s `[rules]` instead of by hand. The compound given name is measured in the fielded corpora: in ORCID and PatentsView records from Brazil, Portugal, Spain, Mexico, Argentina, Colombia, Chile and Italy whose given-names box holds three or more words with a particle inside (the `Maria do Carmo` shape) and whose family box is filled, 1,812 of 1,923 ORCID records and 1,165 of 1,219 PatentsView records read with the given box's words pulled into the family (2026-10-28, master `c8357e74`). Like the surname span, it is a rule a caller or a pack turns on, since `Juan de la Vega` is the same string shape with the opposite answer.

The real-name corpora agree on the priority. In the GND and Wikidata corpora, Spanish and Latin American double surnames written given-first disagreed with the source on 315 of 390 names, while the same kind of names in index form, where the comma settles it, disagreed on 0 of 60 (counted 2026-10-16 on master `4375b01b`, from `gnd_agreement.json` and `wikidata_agreement.json`): the gap is order and span, not vocabulary. The PSC register ranks it (#754's comment of 2026-10-23): 22,168 of its 1,040,708 filed names read a two-word surname's first word as a middle name, the largest disagreement shape in its score.

### The output model

Phase 4 also decides what a parse returns, aligned with CLDR's person-name fields, which gives ground truth for free. Five things were asked for: a second surname (`surname2`), a patronymic (decision 8), credentials apart from generations (#326), a meaning for `middle` when a given name is several words (#704), and the reading each token took (`Token.reading`, phase 2's item 13). The first four are fields, and the design answers them with one shape; the fifth is what most of them are read from.

**The seven roles stay, and every new field is a view.** A `Role` partitions the tokens: each word is in exactly one of title, given, middle, family, suffix, nickname and maiden. Each field asked for subdivides a role that exists, not to add a part a name has outside them: a second surname is part of the family, generation and credentials are parts of the suffix, a second given name is the middle, and a patronymic is a word the parse already puts in the family (Icelandic, Arabic and Malay names) or in the middle (East Slavic names). So each is a view computed from the tokens, as `family_base`, `family_particles`, `surnames` and `given_names` are today (rules/R1, rules/R2), except the second given name, which is the `middle` that exists (below): a property and a render key, with `as_dict()`, `comparison_key()` and the seven role properties unchanged. Every view is an addition under the 3.0 freeze. A new `Role` member would not be: `as_dict()` would gain a key, `comparison_key()` a component (a stored key would stop matching), `for role in Role` a member, and the role a token moves out of would return less text than it does in 2.x, a change in what `family` or `suffix` means that no 2.x warning has announced.

What decides a view is the reading each token took, so `Token.reading` comes first; `surname2` alone is read from a tag O6 writes, a rule rather than a word deciding it:

- **`Token.reading`**: a `Token` field holding the `Reading` the parse took, the same type `Ambiguity.alternative` holds the reading not taken in (decisions/A1), `None` for a token `replace()` builds. Its `kind` says what the word was read as, its `source` why, and a `languages` field, added to `Reading`, names the language files holding that reading, filled from phase 3's reading index (3a) and left empty for a reading no file holds (a caller's own vocabulary, a shape, position alone). The field takes `ADDED_IN` metadata, so a 2.x pickle loads with `None` (the pickle guard as widened in 2.7), and is left out of comparison (`compare=False`), so `==` between two `ParsedName`s means what it means in 2.x. `ReadingKind` gains `PATRONYMIC`, its docstring already allowing new kinds.
- **Generation and credentials** (#326): `generation`, the suffix tokens whose reading is a generation or an agnomen (`Jr.`, `III`, `Filho`), and `credentials`, the rest of the suffix (`PhD`, `Esq.`, the honorifics after a name), so the two partition `suffix` and `suffix` is unchanged. CLDR has only these two buckets; the post-nominals that are neither (`Esq.`, the CJK and Hebrew honorifics, `Rinpoche`) fall in `credentials`, CLDR's catch-all, and a caller who wants them apart reads `Token.reading.kind`, which says `post-nominal`. Measured 2026-10-28 on `c8357e74`, over the committed corpus's 6,533 distinct entries (`snapshot.corpus_entries()`) each parsed under its declared order: of the 1,054 with a suffix, 33 hold a generation (or agnomen) and a listed credential together, 77 a generation beside any other suffix word, and 64 only listed post-nominals of other kinds. Of the 615 CLDR renderings with a generation or credentials field, 75 parse with exactly CLDR's suffix words, and in all 75 a split by the vocabulary's reading kind gives CLDR's `generation` and `credentials` both; the other 540 differ in which words the suffix holds, a parse question the split cannot fix. Recompute: classify each suffix word (a token tagged `joined` merged into the one before it) by the kinds of its suffix readings in nameparser/vocab/, matched lowercased with its periods and spaces removed, skipping `default = false` readings, a generation or agnomen reading winning over a credential and a credential over the other kinds, an unlisted roman numeral `i` to `x` a generation and any other unlisted word unlisted; over the corpus entries above, and over `cldr_fields.jsonl` for CLDR.
- **A patronymic** (decision 8): `patronymic`, the tokens whose reading is `PATRONYMIC`, in whichever role the parse put them, with `family` and `middle` unchanged. What fills it is a word or a rule that says patronymic, never a guess from position: the vocabulary's `patronymic` particles (`bin`, `binti`, `ibn`, `bint`, Hebrew `bar` and `bat` and the native-script forms) with the name after them, in the default, so `Mahathir bin Mohamad` reads family `bin Mohamad` as today and patronymic `bin Mohamad` beside it; the East Slavic and Turkic rules where RU or TR_AZ turns them on, so `Ivan Ivanovich Ivanov` under RU keeps middle `Ivanovich` and adds patronymic `Ivanovich`; and an Icelandic ending rule an `is` pack would turn on, the default unable to tell `Karlsdóttir` from the Swedish surname `Johansson`. The name `patronymic` is kept for a matronymic too, which is written the same way and cannot be told from one. **`family` is not emptied** by recognizing a patronymic, revising what this section said before: the people filling in the fielded corpora put the patronymic in the family box (below), as CLDR's samples put an Icelandic patronymic in `surname` or `surname-core` (CLDR's `is` file's 3 Icelandic samples, in all 9 of their renderings; its one foreign sample puts a `-dóttir` word in `surname2`) and a Russian one in `given2` (its 2 `ru` samples, in all 6 renderings), our `middle`, while Wikidata records an Icelandic name as a patronymic with no family name; a `family` that keeps it and a `patronymic` that names it satisfy both. A caller writing "Mr. {family}" reads `patronymic` to see that the family is one.
- **A second surname**: `surname2`, the family's second name unit where a rule has read the family as two (rules/O6, which a caller or an `es` pack turns on), and empty otherwise, `family` keeping both units as O6 makes it today. O6 already knows which unit it took, so it marks where the second one starts with a new stable tag; a family comma alone marks nothing, since `Lloyd Webber, Andrew` is not two surnames, and a hyphenated family is one token and stays whole. Whether the first unit gets a view of its own, and its name (`surname` sits close to the `surnames` that exists), is a value question below. `surnames` keeps its meaning, `middle` and `family` joined, the reading of a double surname the default splits.
- **`middle`** (#704): keeps its meaning, every word of the given part after the given name, and the given name is one name unit unless a rule joins words into it, as rules/P5 already does (`Abdul Aziz Tariq` → given `Abdul Aziz`). A compound given name (`Maria do Carmo`, `María José`) is the `[rules]` rule above, turned on by a caller or a pack, moving its words into `given` only under that rule. CLDR's `given2` is `middle`, so no view is added. A Sikh `Kaur` and an English name beside a Chinese one (`Lim Mei Ling Jessica`) stay in `middle`, an accepted cost.

**Measured in the fielded corpora** (2026-10-28, master `c8357e74`, counts only; recompute by counting each record's boxes by word count and word ending with `local_corpora.read_records`, grouped by the record's country or nationality, and the parse's role for the counted word with `parse()`. The ending tests, case-insensitive on the box's last word: an Icelandic patronymic a one-word family box ending `dóttir`, `dottir`, `sson` or `son` (the role count, `dóttir`, `dottir` or `sson`); an East Slavic patronymic `ovich`, `ovna`, `evich`, `evna`, `ichna` or their Cyrillic forms, in a given box of two or more words; nasab `bin`, `binti`, `bint`, `bte`, `bt`, `b.`, `ibn` or `ben` anywhere in the box. Other tests give other counts by a few percent):

| Question | Where | Count |
|---|---|---|
| patronymic in the family box | Icelandic records whose family box ends in `-son` or `-dóttir` | ORCID 1,647 of 2,583 (63.8%), PatentsView 535 of 722, PSC 101 of 125; the parse reads every one checked as the family (ORCID 1,509 of 1,509 ending `-sson` or `-dóttir`) |
| patronymic with no family | Wikidata's `patronymic-is` and `patronymic-my` strata, a patronymic and no surname stated | 108 rows, of which the parse puts the patronymic in `family` 107 times |
| patronymic in the given part | PatentsView records from Russia whose given box ends in an East Slavic patronymic | 8,423 of 20,000 (42.1%); across PatentsView the parse reads such a word as the middle 10,902 times of 10,962; in PSC, 90 of the 112 Russian nationals who filled the middle-name box wrote a patronymic there |
| nasab, filer's box | Malaysian records holding `bin`, `binti` and their spellings | ORCID: 319 in the family box, 335 in the given box; PatentsView: 106 and 269 |
| a second surname | family box of two words | ORCID Spain 48.0%, Mexico 64.7%, Colombia 72.8%, Chile 50.5%, Argentina 16.7%, United States 3.9% |
| a second given name | PSC, which has a middle-name box | 2,499 of 1,040,708 forename boxes hold two or more words; of 6,101 Spanish nationals, 25 do and 2,621 (43.0%) fill the middle box |
| no family name | ORCID records with an empty family box | 68,006 of 1,831,533 (3.7%); India 17.5%, Pakistan 16.4%, Bangladesh 18.7%, Indonesia 15.9%; of those with two or more given-box words, the parse fills `family` in 51,367 of 51,415 |

ORCID's and PatentsView's given box holds the middle names too, so a two-word given box there cannot tell a compound given name from a middle name; PSC's middle box can, though its form steers what goes in it. The last row is a separate question from the patronymic: a name of given names only, written by people who have no family name, which no output field fixes and only a rule could read (an open question below).

**Render defaults** (decisions/3-0-reevaluations' clean slate). The default `str()` reads every name given-first and joins its words with spaces, so a name read family-first is turned round and a written separator is lost: `str(parse("김민준"))` is `'민준 김'`, `str(parse("王 小明"))` is `'小明 王'` and `str(parse("威廉·莎士比亚"))` is `'威廉 莎士比亚'`. Over the committed corpus's distinct entries, each under its declared order (2026-10-28, `c8357e74`), 728 without a comma read family-first (the family's first word written before the given name's), `str()` renders every one differently from the text, and in 150 of them the family's last word touches the given name's first, written unspaced; of 41 holding the U+00B7 interpunct, `str()` drops it from 36. So:

- `ParsedName` gains `order`, the order the name was read under (its script's or the declared `name_order`, a family comma aside), an addition with `ADDED_IN` metadata whose missing value, in a 2.x pickle, renders as today, and left out of comparison as `Token.reading` is, so a loaded 2.x pickle still equals a fresh parse of its text. The cost, accepted 2026-10-28: two equal names can render differently, where today every rendering is derived from what `==` compares (a 2.x pickle of `김민준` renders `'민준 김'` and a fresh parse `'김민준'`, and a set keeps one of them); the views read from `Token.reading` share it.
- `str()` and `render()`'s default spec put the family first where `order` does, and two words that stand one directly after the other, in the same order, in the original and in the rendering take the spec's own joiner where the spec decorates a field between them (the nickname's quotes, the `) ` after the maiden name, so `Jane Smith née Jones, PhD` keeps `'Jane Smith (Jones) PhD'`; 38 committed entries put a suffix directly after an undelimited maiden name) or where the original separates them by a delimiter, a marker word the parse consumed or a doubled comma; otherwise they are joined by what separated them in the original, nothing, whitespace, an interpunct, a nakaguro or one comma with whatever whitespace stands beside it, a comma being ASCII or full-width (U+FF0C), as the parse reads either, so `John Smith，Jr.` keeps its comma unspaced as written, so `John (Jack) Smith` keeps today's quoted nickname and `str(parse("김민준"))` is `'김민준'` and `str(parse("威廉·莎士比亚"))` keeps the dot. A name with a family comma or written given-first keeps today's word order, and its separators are kept by the same rule (a comma before a suffix alone does not make a family-first name given-first: `Wang Xiaoming, Jr.` under FAMILY_FIRST renders `'Wang Xiaoming, Jr.'`), so the given-first transcription `威廉·莎士比亚` keeps its dot too (20 of the 36 names whose interpunct `str()` drops are read given-first, one of them with a comma). A family comma is never kept, since the rendering reverses the pair it stands between (`Smith, John` → `'John Smith'`), while a comma directly between the family and its suffix is (`John Smith, Jr.` → `'John Smith, Jr.'`, where `str()` gives `'John Smith Jr.'` today): of the 1,003 committed corpus entries whose suffix starts after the family's last word ends, 214 have nothing between the two but one comma and whitespace (2026-10-28, `c8357e74`, each entry under its declared order; these counts read the ASCII comma, and 7 more write a full-width one there, while 5 of the 728 family-first names above hold a full-width family comma, and so keep today's word order under the rule); 456 hold a comma somewhere between, most with a given name or title standing there too. Pairs the rendering separates, as `John` and `Jr.` in `Smith, John, Jr.`, take the spec's own joiner, as today, so `Smith, John, Jr.` keeps rendering `'John Smith Jr.'` while `John Smith, Jr.` becomes `'John Smith, Jr.'`: two writings of one name rendering differently, a consequence of following the text accepted with the choice.
- `initials()` gives nothing for a word in a script with no initials (Han, Hangul, kana, `_policy._NO_INITIALS`), where today it gives the first character with a period (`'王.'`).

These change no signature but change `str()`'s output for every name read family-first, every name whose written separator is not a space, and every name written with one comma directly between its family and its suffix, which no 2.x release can warn about; Derek took them as an improvement for 3.0's release notes rather than a break (item 6 of the entry).

**What changes in the API**, by the 3.0 freeze:

| Change | Kind |
|---|---|
| `Token.reading`, `Reading.languages`, `ReadingKind.PATRONYMIC` | additions; old pickles load |
| `generation`, `credentials`, `patronymic`, `surname2` properties and render keys | additions |
| a stable tag marking the second surname's start, joining `STABLE_TAGS` | addition |
| `ParsedName.order` | addition; old pickles load |
| new `Policy` fields for rules, and `Locale.languages` (phase 3) | additions |
| `Role`, `as_dict()`, `comparison_key()`, the seven role properties | unchanged |
| the default `str()`, `render()` spec and `initials()` output | behavior change, accepted for 3.0 |
| a `Role` member for any of these views | a break, declined |

**Phase 3's open API dependency answered**: phase 3's draft (branch `feat/vocabulary-phase3-design`, not yet merged) carries a choice of languages on `Locale.languages` and notes it assumes `Locale` and `Policy` keep their 2.x shape once the facade is gone; the 2026-10-28 freeze answers that, both keeping it with additions. The rest of that item, strict as an argument of the whole choice included, is phase 3's to decide, and its entry is to say the dependency is answered when it lands. With the `[rules]` proposal above, a shipped language pack is a `Locale` whose `languages` choose its vocabulary and whose `policy` carries its rules, so `Locale` needs no third field.

**Render patterns a pack may carry** (a shape agreed 2026-10-28; the feature is later work and an addition, in 3.0 if time allows and in 3.x otherwise). A `Locale` is a code, a `Lexicon` and a `PolicyPatch`; it may also carry named render patterns in CLDR's person-name shape (Unicode TR35 part 8, https://www.unicode.org/reports/tr35/tr35-personNames.html), a given-first and a surname-first display pattern and a sorting pattern, so a caller gets a region's standard forms without knowing its convention. CLDR is where a pattern starts, not its authority. In `tools/differential/cldr_fields.jsonl` (CLDR release 48), `pt`'s sorting pattern files its native sample under the FIRST surname, its particle after the given names, and leaves `surname2` out (`Silva, José Pedro Eduardo da`, `surname2` 'Silveira'), which is CLDR's two-surname model and not ABNT's last-surname entry (decisions/R2's 2026-10-28 #754 entry); `es`'s sorting pattern keeps its foreign sample's `von` in front (`von Miller Jones, …`), where RAE's rule (a) sets a Spanish preposition after the given name, and its native sample holds no particle, so it cannot show rule (a) either way.

| CLDR field | Phase 4 view | filled |
|---|---|---|
| `title`, `given`, `given2` | `title`, `given`, `middle` | today |
| `given-informal` | `nickname`, loosely | today |
| `surname-prefix`, `surname-core` | `family_particles`, `family_base` | today, but over the whole family |
| `surname`, of a family read as one unit | `family` | today |
| `surname` and `surname2`, of a family read as two | the first unit's view, `surname2` | the first unit's view has no sub-phase (Left open); `surname2` is 4d, where rules/O6 reads two units |
| `generation`, `credentials` | `generation`, `credentials` | 4b |

What a pattern needs from this phase is the one gap the table shows: CLDR's prefix and core belong to the FIRST surname, while `family_particles` and `family_base` read the whole family, so filling them per surname needs the units told apart, each with its own particles and base. That is the first unit's view and the per-surname units the sort-key question under Left open reads, so they are one piece of work; CLDR has no prefix field for `surname2`.

A sorting rendering is not a sort key: it is a string, and a string sorts by code point, so accents, `ñ` and case fall out of order. Proposed, not decided: a key method beside `comparison_key()` returning a convention's fields in its sort order, each casefolded, which a caller hands to real collation (ICU, `locale.strxfrm`) for anything past code-point order.

How a call reaches a pack's pattern is open, and each answer costs something: `ParsedName` does not know the locale it was parsed under. (a) The parse records the convention on the name, as it records `order`, so a call on the name alone finds it: one more `ADDED_IN` field, and a new method or argument to ask for a pattern by, since `render()` takes a format spec today and `render("sorting")` returns `'sorting'`, so giving that argument a pattern's name would change behavior rather than add it; the field is missing on a 2.x pickle and kept out of `==` as `order` is, with the cost accepted for `order` (two equal names rendering differently). (b) Pattern rendering goes through the parser, `Parser.render(name, "sorting")` or the like, as `Parser.capitalized` does for a convenience that depends on configuration: no field and no pickle question, but a name alone cannot give its convention's forms. The render default decided above forecloses neither: `str()` follows `order` and reads no pattern, and under both answers a pattern is something a caller asks for.

**Gender**, recorded only where a word gives a definitive clue (decision 9), is not part of this design: the vocabulary records it on readings (`bint`'s `gender = "f"`), and `Token.reading` could carry it later as one more addition.

### The order of work

Each sub-phase is one PR, measured on its own base as phase 2's and phase 3's are. The views and the reading move no field of any parse, so the committed snapshot holds still through 4a to 4d; the snapshot records the new views where they are non-empty, as it records the case views, so a reviewer sees what each fills.

| Sub-phase | What | Needs |
|---|---|---|
| 4a | `Token.reading` and `ReadingKind.PATRONYMIC`, kind and source filled at the sites that decide today; `Reading.languages` once 3a's index exists | — (neutral); 3a for `languages` |
| 4b | `generation` and `credentials` (#326) | 4a (neutral) |
| 4c | `patronymic`: the vocabulary's patronymic particles, and the RU and TR_AZ rules writing the reading | 4a (neutral) |
| 4d | `surname2`: O6's stable tag | — (neutral) |
| 4e | the render defaults and `ParsedName.order` | — |
| 4f | `[rules]` compiled into a `Locale`'s policy patch; RU and TR_AZ rebuilt from their files | 3b |
| 4g | the compound given name, a rule kind (#704) | 4f |
| 4h | the shape inventory per order (#469), starting with the title between a family and a given name under `FAMILY_FIRST` | — |

**Interleaved with phase 3** (its sub-phases 3a to 3h are the draft's on `feat/vocabulary-phase3-design`): 4a can start beside 3a, its `languages` waiting for 3a's index; 4b to 4d need nothing of phase 3 and unblock its packs, `cs`'s generations (3f) and `pt-BR`'s agnomens (3h) on 4b, `es` and `pt` (3g) on 4d and 4g; 4f lands with or after 3b, since both decide what a shipped `Locale` holds; an `is` pack, which no phase 3 sub-phase lists, needs 3b, 4c and 4f. 4e and 4h stand apart from both. So the order is 3a and 4a, then 4b to 4d with 3b and 3c, then 4f, then the packs with 4g, with 4e at any point.

**Left open.** With no sub-phase yet: phase 1's four reserved names said to be phase 4's (`separators` with phase 4's glued words, and `bare_only`, `leading_only` and `trailing_only`, which this RFC's phase 2 section found not needed), whose build messages still name this phase.

A shape question, to settle before the 3.0 freeze makes every field permanent:

- **Whether `Lexicon` keeps a public field for each compiled set**, or answers word, kind and property queries from phase 3's reading index and keeps its sets internal. `dataclasses.fields(Lexicon)` gives 22 public fields on 2026-10-28, 11 of them added since 2.0.0's 11 (`surnames`, `honorific_tails`, `conjunctions_ambiguous`, `after_given_titles`, `suffix_words_ambiguous`, `agnomens`, `given_name_abbreviations`, `titles_ambiguous`, `title_modifiers`, `title_styles`, `title_phrases`), each a new parse behavior's set, and a rule keyed on a title kind or on one language's reading of a kind (phase 3's draft, "a property a language's own reading should take only under its pack") would add more. Keeping the fields: each is frozen API, shown in the bounded repr (`Lexicon(default + titles: +1)`), and pickled, where `Lexicon`'s own `__setstate__`, unlike the `ADDED_IN` guard the other types share, refuses any pickle whose fields differ, so every new field breaks every older `Lexicon` pickle, and with it every pickled `Parser` and locale pack, until that guard learns the marker. Turning them internal: a break that has to land in 3.0, where a query added beside the fields is an addition that can come later; a caller who configures vocabulary by the field today (`Lexicon.add(titles=...)`, `dataclasses.replace`) needs another way in, for words that carry no kind and no language; and phase 3's draft loads the reading index only when a caller chooses a language (about 11 ms to execute), so a `Lexicon` answering from it loads it for every caller. The parser need not pay either way: a frozenset test per word costs no frame and an internal cache keeps that path, while a query method called per word would add one per token, the cost the frame budget counts as scaling with the input.

Value questions inside the shapes above:

- The first surname's view and its name, with its own particles and base (the gap the render-pattern table shows).
- How a pack's render pattern is reached, and the key method (Render patterns, above).
- Whether a language pack supplies a convention's entry element or sort key, built from the per-surname units this phase reads, `family_base` being the family without its working particles under every convention (an all-particle part's words staying, rules/R2's Except; decisions/R2's 2026-10-28 #754 entry). A `pt` or `pt-BR` pack would give the last surname's base first, keeping `Filho`, `Neto` and `Júnior` with it and a compound surname whole, and an `es` pack the first surname without its particle, then the second with its own (RAE's rules (a) and (e)).
- Whether a token's title kind reaches callers. A title token's tags name only behaviors (`Dr. Mr. Sir John Smith` gives `Dr.` `vocab:title`, `Mr.` `vocab:after-given-title` and `vocab:title`, `Sir` `vocab:given-title` and `vocab:title`); `Lexicon` splits the titles into `titles` and `titles_ambiguous` by whether a word is also a name, not by kind, and only `title_modifiers` and `title_styles` are sets of a kind; the salutation, academic, religious, nobility, military, office, occupation and kinship kinds live only in the TOML; and `ReadingKind`, being "the parse's, not the vocabulary's", would read every one as `TITLE` in the planned `Token.reading` (today these tokens carry no reading), where the suffix readings split four ways. Phase 3's draft already gives its reading index "its kind" per row ("Where the provenance lives at runtime", on `feat/vocabulary-phase3-design`), so what stays open is whether that is the vocabulary's kind and whether `Reading` gains an optional field exposing it, filled only where the reading's source is the vocabulary: a title read by its shape (`Insp.`) or a word a caller added by `Lexicon.add` has none, so its absence means unknown, not that the word has none. It is an addition and blocks nothing in 3.0, and it would let a view name the salutation alone (`Dear Mr. Smith`), which CLDR's one `title` field does not model. Whether it holds one kind or a set is part of the question: of the 816 title words in nameparser/vocab/ on 2026-10-28 none carries two title kinds, `father` being `religious` only, the README's "kinship word used as one".
- Whether `credentials` should leave the honorifics out, CLDR having no third bucket.
- Which ending rules beside Icelandic a pack may name (Hungarian `-né` is a married name, not a patronymic).
- The names of given names only (the last table row), whose reading needs a rule that tells a mononym from a given name and a family name, not an output field.

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
