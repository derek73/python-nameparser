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
| 3 | Language packs that prefer or restrict their language | yes, for callers who choose one | #753, for 3.0; design proposed 2026-10-27, not agreed |
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

A caller should be able to see the reading behind a parse. **An `Ambiguity` carries the reading the parse did not take** (`Ambiguity.alternative`: its kind, the field it would have put the token in, and whether it came from the vocabulary, a declared name or a shape), and **a token carries the reading it did** (`Token.reading`), so `Nguyen Van Do`, which forks nothing, can still expose `Đỗ` without a report nobody would act on. A word the credential's run takes by position alone is told from a word with a declared name reading by that source, so it needs no new ambiguity kind. `Ambiguity.alternative` shipped in 2.7 (decisions/A1, 2026-10-26 #752): a `Reading` of a kind, the field the word would land in with every other word read as the parse read it, and a source, which is `vocabulary`, `declared`, `shape` or `position`, the fourth being the reading of an ordinary word nothing lists, which is what a word the credential's run took by position alone has. The pickle guard was widened to accept a field added later. A `languages` field, naming the files that hold a reading, was weighed and left out: it needs the per-word reading index, which costs about 0.4 ms of a 19.5 ms import and could not describe a pack's or a caller's lexicon, so it waits with `Token.reading` for 3.0.

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

Status: **proposed, not agreed** (2026-10-27, #753). The record is decisions/vocabulary-model's 2026-10-27 #753 entry, whose items are each marked proposed until Derek decides them; this section is the proposal those items describe. Phase 3 is 3.0 work (re-planned 2026-10-28): 2.8 is the last 2.x feature release, and 3.0 ships phases 3 and 4 with the facade's removal. Packs stay opt-in, so a caller who chooses no language parses as the default does, and nothing in this phase moves the default's parses. One standing text would be amended with it: mechanisms.md#LOCALE-PACKS-PURE-DATA's contract that a pack is add-only and declares its deviations in its docstring (a pack would add, and select among the default's readings by language, its deviations derived for a vocabulary pack). decisions/3-0-reevaluations' line that removing base vocabulary through a pack is part of 3.0's pack design is carried out rather than moved.

**Phase 4's shape questions come first, or alongside.** The output model decides what a pack can express: a patronymic field, a second surname, credentials apart from generation suffixes (#326), and what `middle` means (#704). A pack reading of a kind with no field to land in is a reading nothing can surface, so those questions are to be settled before or with phase 3's mechanism, by the same shape-before-value rule. Of the work order below, 3a (the reading index and the shared compiler) and 3c (the pack-shaped exclusions converted) are independent of the output model: the index carries whatever kinds the files hold, and 3c moves data between two encodings that compile alike. 3b's selection semantics are independent too, but its API is not: whether a choice rides on `Locale.languages` depends on what `Locale` and `Policy` look like once the facade is gone, so Q1 below is an open dependency. The packs depend on the output model in part: `cs`'s generations and `pt-BR`'s agnomens on #326, `es` and `pt` on a second surname; `ne`'s readings do not.

The semantics were fixed in 2026-10-15/16, and phase 3 keeps them. A pack is a choice of languages, in two strengths (decision 6):

- **prefer** settles a clash where the chosen language has a vocabulary reading: the word keeps that language's readings and loses other languages' vocabulary readings. Under Portuguese, `do` is a particle only.
- **strict** also drops other languages' name readings. It is for single-origin data.

The asymmetry is deliberate (decision 15): **vocabulary readings settle a clash; name readings only keep the gate on.** `do` shows why. Its Vietnamese reading is a name only (Đỗ). If name readings settled clashes, preferring Vietnamese would drop the credential reading, and `John Smith DO`, a suffix today, would read `DO` as the family name. Under the rule, Vietnamese holds no vocabulary reading of `do`, so preferring it settles nothing: the credential and particle readings stay, gated as in the default.

Consequences that follow from the definitions:

- **Order does not matter.** A choice is a set of languages, so combining packs is commutative. Proposed below: strictness belongs to the whole choice rather than to one pack, reshaping decision 6's "strict variant", and strict waits until name readings say whose names they are.
- **Two chosen languages that each hold a vocabulary reading both keep it**, and the word stays gated, as in the default.
- **Non-Latin vocabulary stays on under any choice**, because it selects itself by script (`씨`, `さん`, Cyrillic titles). Almost every clash between languages is within one script: `do`, `e`, `van` are all Latin.
- **Whether a word needs a pack depends on where its clash is.** `do` clashes between languages, so a pack settles it. `fils` clashes within French, a generation word and a French surname, so no pack settles it and the phase 2 gate does the work, reversing the premise of #684.
- **A pack can outrank a shape rule, not only a vocabulary reading** (decision 20). Shape rules emit readings into the pool rather than final answers, so a pack's preference can act on them; phase 2k applied this in the default, a declared `given` reading of `Ma.` outranking the leading-abbreviation title.

What the inventory of the kept-out words found (#753's comments of 2026-10-27, 411 candidate readings) changes the emphasis rather than the semantics. Only 9 words clash between languages (`de`, `do`, `i`, `st`, `sr`, `ra`, `mc`, `vd`, `abd`), so prefer alone settles little; most pack candidates are readings the default leaves out entirely, which a pack turns ON. Phase 3's main work is therefore turning readings on, with prefer and strict settling what turning them on collides with.

### One mechanism: a choice selects the pool

Everything a pack does is one operation: **the chosen languages select which readings of the pool are compiled**, by the same compiler that builds the default. The default is that compiler run with every language and no choice. Nothing is written per pack beyond the readings in its language's file, and every effect below is derived from the file a reading sits in:

| Effect | Which readings | Example |
|---|---|---|
| turn on | a chosen language's `default = false` readings join the pool | cs `ml` (*mladší*, once 3c makes it a reading): `Jan Novák ml.` reads family `ml.` today; under `cs`, suffix `ml.` |
| prefer | on a word where a chosen language holds a vocabulary reading, other languages' vocabulary readings leave; `mul.toml`'s readings never do, being every language's | `Haddad, Abd` reads suffix `Abd` and no given name today; under `ar` the bound given reading stays and the en credential leaves; cs `st`: `Jiří Dienstbier st.` reads title `st.` today (rules/H5), and under `cs` its generation reading joins and the Saint readings leave, suffix `st.`, reported as suffix-or-name since en's `given` reading of `st` still gates it |
| prefer, against a shape | a clash a property records with a SHAPE reading is settled for the chosen language's own reading, by decision 20: `may_be_initial` does not hold on it | `ANA SILVA E SOUZA` reads middle `SILVA E` with a conjunction-or-initial report today; under `pt` the conjunction holds, family `SILVA E SOUZA` |
| strict, deferred (below) | other languages' name readings leave, and with them the markers they derive | an `nl` `in` turned on, with Korean In declared as a `given` reading, is a particle that may be given under `nl` and never-given under strict `nl` |

The third row answers decisions/3-0-reevaluations' "a pack cannot remove `e`": `may_be_initial` records a clash between a conjunction and the initial a letter spells, and the initial is a shape reading, so a pack that prefers Portuguese settles it, as decision 7 says choosing a language does and decision 20 permits. It reaches every reading the property stands on, pt and it `e` and ca and pl `i`, the Italian one unjudged by the inventory; and it forecloses the other direction of the 2026-08-18 bullet there, an `nl` pack marking `y` as an initial, which waits with the `fru` question below. Two parts of the mechanism are new beside decision 6: the exemption of `mul.toml` from prefer (under `ca`, `i` keeps its mul generation), and strictness as a property of the whole choice. No property is toggled per pack, and no reading is written twice.

Properties ride on their readings, so a choice that keeps a reading keeps its properties. The one shape this cannot express is a property a language's own reading should take only under its pack: Swedish `fru` and Icelandic `frú` as after-given salutations (rules/H8), refused in the default because Fru is also a Cameroonian surname. The inventory found two readings needing it (2026-10-27), so the proposal builds nothing for them and leaves them open.

### Name readings in a pack

`default = false` is allowed on `given` and `family` readings. A name reading turned on by a pack derives the markers any name reading derives, so it turns the gate on and never settles anything: decision 15 holds unchanged inside a pack. Measured on nepal-candidates (2026-10-27, `cfe8bf92`), comparing each candidate's Devanagari and romanized spellings by the role of every word:

| Reading turned on | Effect | Pairs reading alike, of 126,981 |
|---|---|---|
| none (the default) | | 123,440 |
| `given` on `श्री`, `guru` and `गुरु` | each becomes a title only inside a title phrase (rules/H9), so it reads given at the head: `श्री कृष्ण श्रेष्ठ` → given `श्री` | 123,636 (198 fixed, 2 broken) |
| and `family` on `dc` | the family reading only makes the credential ambiguous: `Ram Bahadur DC` still reads suffix `DC`, the count leaving it one | 123,639 (3 more fixed) |
| `dc`'s credential dropped, as settling would do | `Ram Bahadur DC` → family `DC` | 123,658 (19 more fixed) |

The 2 broken are pairs whose romanization opens with a listed title, which reads the `श्री` as a salutation (#870 counted `Mr` written for it twice). So the gate route delivers the `श्री` and `guru` fix without amending decision 15, and the 19 `dc` pairs it leaves are the price of keeping it. `bk`, `kc`, `gc` and `bc` need nothing: they read as the family in every shape tried (`Ram Bahadur BK`, `Ram Bahadur Kc`, `BK, Ram Bahadur`, `KC Sita` under `FAMILY_FIRST`), so a reading would move nothing.

**Strict cannot be built on today's files.** A name reading sits in the file whose source counted it, not the file of the language whose names carry it: 113 of the 211 name readings are in en.toml (2026-10-27), `do`'s Vietnamese Đỗ readings among them, and vi.toml holds no `do`. A strict `vi` choice built on the files would drop exactly those readings, and with them the gate: simulated, `Minh Do` reads suffix `Do` and `Do Van Minh` family `Do Van Minh`, the harm decision 15 is there to prevent. Nor does a census count belong to one language. So strict is proposed to wait, out of the first packs, until name readings say whose names they are, and the candidates that need it wait with it. The `nl` prepositions show they would need more than strict: turned on as possibly-given particles, `in` and `to` already read `Park In Hwan` family `In Hwan` and `Nguyen To Nga` family `To Nga`, the marker acting at the head only, and check 11 lets their author write `may_be_given = false` instead of declaring the Korean and Vietnamese readings.

**Open: nothing in the work order says whose names a name reading's are.** Strict waits on it, and none of 3a–3h does it. Moving readings between files would not: a census count belongs to no one language, and a word is borne in several, `do` as a Vietnamese and a Korean name, `kim` as a Korean surname and a Scandinavian given name. What it points at is an attribute on each name reading naming the languages of its bearers (`do`'s family reading `vi` and `ko`; the key's name still to choose), compiling to nothing until strict reads it. The counts to fill it exist, but none fills it mechanically. Of the 211 name readings, 172 count a US source and 21 none, and what per-country evidence they carry is prose in a `note`, as `do`'s nam_dict bands are (Korea 8, Vietnam 6, the Netherlands 1), in 40 of them by a text search. `name_usage.py --boxes` gives `orcid-researchers`' and `patentsview-inventors`' counts by box and country, and a box count says where a word was typed, not whose name it is: `do`'s family box in ORCID is led by Brazil, 7,227 holders against Vietnam's 876, and none of Brazil's is `do` alone (2,629 open with it, 4,598 hold it inside), the particle of a Brazilian surname, where Vietnam has 618 boxes of `do` alone and Korea 151. A share of each country's holders ranks them the other way (Vietnam 1.90%, Brazil 0.81%; PatentsView 1.78% and 0.64%), and `kim` reads cleanly either way, its family box 17.67% of ORCID's Korean holders and 13.30% of PatentsView's, its given box 0.93% of PatentsView's Danish inventors (2026-10-28, master `c8357e74`). So the fill is a person reading each of the 157 words with name readings, by share and by whole box, not a script. Two further consequences: the attribute names languages, filled from countries by that reader, since a country-to-language table read at run time is the macrolanguage table the tag matching below refuses; and it is the first provenance anything computes a reading from, where counts today are evidence nothing reads. Proposed: a sub-phase of its own, 3i, after 3a, independent of the output model and moving no default parse, with strict and the candidates waiting on it after it. Recompute: count the name readings per file and per count key with `tomllib` over `nameparser/vocab/*.toml`; `name_usage.py do kim --no-wikidata --boxes`; the whole-box split by reading the cached ORCID extract's `family` and `country` keys.

### Where the provenance lives at runtime

The compiled module holds sets, and a set has forgotten which file each word came from. The proposal compiles a second module beside it: a **reading index**, one row per reading (its text, its file's tag, its kind and its behavioral properties), loaded only when a caller chooses a language. The compiler moves from tools/vocab/build.py into the package so that the build and a pack share one implementation, and a test holds the invariant that compiling the index with no choice reproduces `nameparser/config/_compiled.py` exactly. The same index is what item 13 of decisions/vocabulary-model's 2026-10-23 #752 entry says `Token.reading` needs in 3.0.

Measured 2026-10-27 on `cfe8bf92`: the pool holds 2,140 readings over 1,797 words, 106 of them in more than one file. An index of their behavioral properties is about 93 KB of generated source, executing in about 11 ms with no bytecode cache, and compiling the pool takes about 9 ms, both paid once per choice and only by a caller who makes one. Reading the TOML instead costs about 39 ms. Recompute: the build's `read_dir`, `load` and `compile_pool`, timed.

Two cheaper-looking forms do not work. Per-language deltas compiled at build time do not compose: under prefer `{pt, en}`, `do` keeps both its particle and its credential, but Portuguese's delta removes the credential and English's removes the particle. And precompiling every combination of languages is combinatorial.

A choice is applied as a delta against the default's compile, so it composes with a caller's own `Lexicon`: `parser_for(locales.NE, base=Parser(lexicon=custom))` keeps a title the caller added, and a `Locale`'s own `lexicon` fragment is still unioned on after the choice.

### The API and tags

Open dependency: this assumes `Locale` and `Policy` keep their 2.x shape after the facade's removal, which is undecided. A choice is carried by `Locale`, which gains a `languages` field, a set of BCP 47 tags. `parser_for` unions the `languages` of the packs it is given, so the choice is order-independent while their policy patches still fold in order. Strict, once it can be built, is a property of the whole choice, not of one pack, and an argument: `parser_for(locales.NE, locales.HI, strict=True)`. The shipped language packs are `Locale` constants like the four today (`locales.NE`, `locales.get("ne")`), each with an empty lexicon fragment; a code keeps `Locale`'s `[a-z0-9_]+`, so `pt-BR` is `locales.PT_BR`.

A chosen tag selects its own file and its ancestors', never its descendants': `pt-BR` selects `pt-BR.toml` and `pt.toml`, and `pt` selects only `pt.toml`, so a caller in Portugal does not turn on the Brazilian agnomens (#843 left the single-letter `F` and `N` to a `pt-BR` pack). No macrolanguage table is read: Malay and Indonesian are separate tags, though BCP 47 counts Indonesian within the Malay macrolanguage, and a caller with names in both chooses both. The Czech, Slovak, Slovenian and Croatian files each hold the words they share, so each language is a pack of its own. Script subtags need no matching rule yet, since no file carries one.

The TOML names `prefer` and `strict`, reserved for phase 3 since phase 1, stay refused, with a message saying that a strength is the caller's choice and never data.

### Measuring a pack

The snapshot and `compare.py` parse under the default, so neither can see a pack (decisions/3-0-reevaluations). Three measures, the first two in CI:

- **The default does not move.** The committed snapshot holds it, as for any change, and so does the index invariant above.
- **A pack moves only names holding a word it changes.** The words whose compiled readings a choice changes are computable from the index, so a vocabulary pack's deviation surface is derived rather than hand-copied, and the non-interference gate in tests/v2/test_locales.py runs every corpus name without such a word under the pack and requires the default's reading. The packs whose behavior is policy or segmentation (JA, RU, TR_AZ, ZH) keep their hand-written `DEVIATES`.
- **What a pack does, read by shape.** `snapshot.py` and `snapshot.py --local … --base <checkout>` take a choice of languages and print the names it moves, grouped by changed field, as they do for the default; each pack PR reads its own ground truth beside that: nepal-candidates' script pairs for `ne` (mechanisms.md#PAIRED-SPELLINGS-PER-CHANGE), the CLDR agreement per pack where CLDR has the language, the PSC register's nationality slice where filers of that language are many.

### What stays out of phase 3

- **Third-party language files.** A file joining the pool at run time would skip the checks that run across files, an exclusion in one file refusing a reading in any other (check 6) and check 11's particle statement. A third-party `nl` file adding the preposition `in` without a `given` reading or `may_be_given = false` is refused by the build and would ship on the unsafe side at run time. `Locale(lexicon=…)`, or its successor once the facade is gone, stays the way to add vocabulary; a public file format is a later question.
- **The Python packs' rule data.** ZH's surnames (556 on 2026-10-27) are a segmentation list, outside the per-word model, and the RU and TR_AZ markers are endings inside rules (`-ovich`, `oğlu`); both wait for phase 4's `[rules]`. A pack gets a `languages` field only where measuring it shows what it moves.
- **Candidates that wait on a rule, not a word:** Turkish `Bey` and `Hanım` after the given name, Hungarian `úr` after the name, Thai `นาย` glued at the head, French `M.` against the initial it spells. Each is a position rule, phase 4's.
- **Same-language clashes.** No pack settles one (the `fils` argument): the Indic and Arabic titles that are names in their own language (`kumari`, `sayyid`) take phase 2j's route, a given reading and the title phrase, as default work.

### The order of work

Shape first, then the packs, each one PR measured on its own base, as phase 2's were. The first three move no default parse, and no pack exists until 3d. Strict is not in this order (above); 3i, the bearers' languages it would read, is.

| Sub-phase | What | Needs |
|---|---|---|
| 3a | the reading index and the shared compiler; `default = false` allowed on name readings; the no-choice invariant | — (neutral) |
| 3b | the choice: `Locale.languages`, tag selection, turning on and prefer, the shape clash of `may_be_initial`; the derived deviation surface; `snapshot.py` taking a choice; mechanisms.md#LOCALE-PACKS-PURE-DATA amended | 3a (neutral) |
| 3c | the eight exclusions whose reason opens "pack-shaped" become `default = false` readings: cs `ml`, hr, sk and sl `st` and `ml`, fr `père`; every other exclusion a pack turns on (`pan`, `roz`, `nic`, `shri`, `sig`, `jaun`, `bt`, `bay`, `sb`) converts in the pack's own PR, so that after the packs an exclusion means wrong everywhere | — (neutral) |
| 3d | `ne`: `given` on `श्री`, `guru` and `गुरु`, measured on nepal-candidates' script pairs | 3b |
| 3e | `hi` and `bn`, the Latin forms (`smt`, `shrimati`, `sushri`, `shriyut`, `shri`, `adhyapak`), the ones whose collisions prefer cannot settle left for strict (#345) | 3b |
| 3f | `cs`, `sk`, `sl`, `hr`: the generations of 3c, `pan`, `roz` and the academic abbreviations #848 left | 3b, 3c |
| 3g | `es` and `pt`: the occupational titles and `Don`/`Doña`/`Dona`, with a connective that counts only inside a title run, its own rule; `pt` also settles the one-case `e` | 3b |
| 3h | `ga` and `gd` (`nic`, `mhic`, `mic`, `uí`), `pt-BR` (`F`, `N`, `sb`); `nl`'s prepositions wait with strict | 3b |
| 3i | the languages of each name reading's bearers, an attribute compiling to nothing, filled word by word from per-country shares and whole-box counts (above); strict and its candidates after it | 3a (neutral) |

3g's connective needs a design of its own, because the pair that separates it is a count: `Profesora de Historia Ana López` should read title `Profesora de Historia`, while `Doctora de la Vega`, the same title, preposition and following word, has no name behind it and must keep family `de la Vega`. With `profesora` added and no rule, the first reads family `de Historia Ana López` (the rules/P1 fold), and `Ministro da Fazenda Carlos Souza` reads given `da`. The rule must reach only readings a pack turns on, so the default's parses stay where they are.

Languages with one to three candidates (`tr` `bay`, `it` `sig`, `lt` `jaun`, `ms` `bt`, `cy` `ab`/`ap`, `ber` `aït`) are a file each once 3b exists and need no sub-phase; `nb` and `sv`'s farm-name words wait for a measurement nobody has taken.

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

The real-name corpora agree on the priority. In the GND and Wikidata corpora, Spanish and Latin American double surnames written given-first disagreed with the source on 315 of 390 names, while the same kind of names in index form, where the comma settles it, disagreed on 0 of 60 (counted 2026-10-16 on master `4375b01b`, from `gnd_agreement.json` and `wikidata_agreement.json`): the gap is order and span, not vocabulary.

### The output model

Phase 4 also decides what a parse returns, aligned with CLDR's person-name fields, which gives ground truth for free:

- **A second surname** (`surname2`) for Spanish, Catalan and Galician names, which CLDR's samples carry and nameparser has no field for.
- **A patronymic field** (decision 8), holding only a living patronymic. Its main value to callers is that `family` can be empty for the cultures that have no family name: `Soffía Karlsdóttir` reads family `Karlsdóttir` and `Mahathir bin Mohamad` family `bin Mohamad` today, where a letter addressed to "Mr. {family}" is wrong. Whether the field is `patronymic` or a neutral list of parent names, which a matronymic also fits, is open under #754.
- **Credentials separate from generation suffixes** (#326), and a decision on whether honorifics after a name get a field or stay a reading kind inside `suffix`.
- **What `middle` means** when a given name is several words (#704).
- **Gender**, recorded only where a word gives a definitive clue (decision 9): reported with its evidence, never inferred from given names.

## The first packs

The proposed order is phase 3's work order above (3d onward), led by `ne`, where the evidence is strongest; #747 tracks it. The surname-span measurement above is one input, but it was taken over corpora built to hold second surnames, so it shows that the gap exists, not how it ranks against the others.

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
