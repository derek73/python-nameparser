# The vocabulary files

This folder holds the parser's default vocabulary: the titles, suffixes, particles, conjunctions, bound given names and maiden markers it recognizes, and the case of the words it capitalizes specially, written one word at a time. It is the place to edit when a word should be recognized, should stop being recognized, or should be recognized differently.

The parser never reads these files. `tools/vocab/build.py` compiles them into `nameparser/config/_compiled.py`, a committed module of sorted `frozenset` literals and one `dict` (`CAPITALIZATION_EXCEPTIONS`), which `Lexicon` reads; since 3.0 they are private (#1007), a caller listing a kind's words with `Lexicon.words(kind=...)`. Beside it the build writes a second committed module from the same readings, the reading index `nameparser/config/_index.py`, which keeps every reading with the tag of the file it is in and the properties the compiler reads, which a choice of languages (`Locale.languages`, 3.0's phase 3) compiles from, and a third, `nameparser/config/_rules.py`, holds the files' [rules](#rules) tables. So an edit here does nothing until you rebuild, and the tests fail, naming the command, when a committed module and the files disagree.

Why the model looks this way, and what each decision cost, is recorded in [decisions/vocabulary-model](../../docs/design/decisions/vocabulary-model.md). The plan it was built to, phase by phase (phases 2 to 4, each section saying what has landed), is in [the vocabulary model RFC](../../docs/design/vocabulary-model-rfc.md).

## What a file means

A file is named for a BCP 47 language tag in canonical case: `fr.toml`, `pt-BR.toml`, `zh-Hant.toml`. It holds **the words the parser might meet in names written in that language**, which is what occurs in names and records written in it, including particles common there through immigration. It is not a list of words of that language's etymology.

Two tags are not languages:

- **`und`** (undetermined) holds the words no language file fits: `bon` and `dí`, particles of unrecorded origin until #766 refused their particle readings, now name readings and those exclusions (since 2026-10-20, when #751 finished what #749 and #750 began, giving every other word its languages). The comment at the top of the file says why they are there; a word whose language is found moves to that language's file.
- **`mul`** (multiple) holds words shared on purpose, such as the Roman numerals: a word that harms no language, read in names of any language, and would otherwise be copied into every language's file (`dr`, `phd`, `mr`). A strict choice reads it with the chosen files, so a word whose name reading stands in another language's file, or that is written as a name's abbreviation (`md`, Muhammad), stays in its language's file. A word with two readings moves with both or stays: `ms`'s salutation alone in `mul.toml` read its degree as a title under a strict choice without `en`.

The script is read from the word, not from the file: `sr.toml` holds `mlađi` and `млађи` side by side. A script subtag (`zh-Hant`) is for a difference the text cannot show.

The default vocabulary loads every file, so which file a word is in changes nothing about how a name is parsed today. A word may be in more than one file; check 5 of the build makes each category of it read the same in every file, every behavioral property agreeing whatever kind each file gives it.

## How an entry is built

Each file has `schema = 1` at the top, then a [`[rules]`](#rules) table if a shipped pack reads one from it, then one `[[word]]` table per word. An entry has a `text` and its **readings**: what the word can be read as, each keyed by its kind and each a table, even when empty.

```toml
[[word]]
text = "van"
given = { us_ssa = 31194, wikidata = 282, as_of = 2026-10-25, note = "US SSA births summed over both sexes; Wikidata is a lower bound; nam_dict band 13 in Vietnam, 2 in U.S.A." }
[word.preposition]
expands = "of, from"
note = "Vietnamese Văn, and Van Johnson -- the canonical particle-or-given ambiguity this whole marker exists for"
```

`van`, in `nl.toml`, has two readings: a particle of the kind `preposition`, with two descriptive properties (`expands` and `note`, compiled to nothing), and a `given` name reading with the counts it was declared on. The two together make `van` a particle that may be a given name, a [derived marker](#derived-markers): `van Gogh` keeps `van` as the given name and reports the fork.

```toml
[[word]]
text = "do"
family = { us_census_2010 = 30301, wikidata = 100, as_of = 2026-10-25 }
given = { us_ssa = 11, wikidata = 9, as_of = 2026-10-25, note = "male births only; Wikidata is a lower bound; nam_dict band 8 in Korea, 6 in Vietnam, 1 in the Netherlands" }
credential = { expands = "Doctor of Osteopathic Medicine" }
```

```toml
[[word]]
text = "do"
[word.preposition]
expands = "of the, masc. sg."
note = "Vietnamese Đỗ leads a great many surnames"
```

`do` has readings in three categories: a credential (an American degree, in `en.toml`), a particle (a Portuguese preposition, in `pt.toml`) and two name readings, so it is in both `SUFFIX_ACRONYMS` and `PARTICLES`; which one applies is decided by where the word stands. A word's readings are where clashes between categories are recorded: before this format, such a clash was visible only as two sets that happened to overlap. Its name readings make both clashes with a name: the credential may be a name and the particle may be given, each a [derived marker](#derived-markers), though the name readings sit in only one of its files.

```toml
[[word]]
text = "duke"
given = { us_ssa = 11595, wikidata = 151, as_of = 2026-10-19, note = "male births only" }
family = { us_census_2010 = 35053, wikidata = 315, as_of = 2026-10-19 }
excluded = { nobility = "a common given name (Duke Kahanamoku), and a surname besides" }
```

`duke` is deliberately not a title. It has no vocabulary reading at all, only its two name readings and an exclusion refusing the `nobility` reading with the reason. Anyone who adds `nobility = {}` to `duke` in any file gets a build error that quotes that reason. An exclusion means the reading is wrong wherever it is read. A reading that is right in its own language and wrong only as a default is written `default = false` instead ([Properties](#properties)), as `ml` ("mladší", the Younger, a pair of initials in other languages) is in `cs.toml`, so that choosing Czech turns it on. `père` ("father", the French word for the Elder) was an exclusion until 3.0's phase 3c and such a reading until 2026-11-03 (#684), and its son, `fils`, an exclusion until 2026-10-25; both are now on by default: each one's `generation` reading stands beside its `family` reading, which gates it by the name around it ([derived markers](#derived-markers)), so `Marie Fils` keeps her family name.

```toml
[[word]]
text = "殿"
[word.honorific]
issue = [307, 308]
note = "formal, official/rank-flavored; spaced is safe because a 殿-surnamed person's name LEADS and the suffix gate is trailing-only"
[word.honorific.excluded]
attached = "some ninety Japanese surnames end in it, 鵜殿 (Udono) and 真殿 (Madono) with four-figure populations, so a peel would cut a family name in two"
```

`殿` is an honorific read when written apart from the name, and an exclusion on the reading refuses one property, `attached`: it is never split off the end of a name it is glued to.

Two rules about the `text`:

- It is written already normalized: lowercase, NFC, no edge periods, single-spaced. The build refuses any other spelling and prints the one to write.
- It is one word, except for a `birth_marker` or a title with `addresses = "given"`, the two readings matched as a whole run (`z domu`).

## Word order

Every file but `und.toml` lists its words in one order, and the build refuses a file that does not (check 10), naming the entry to move and where it belongs:

1. **By kind**, in the order of the table under [Kinds](#kinds), which lists the categories in turn and each category's kinds together. A word with several readings sorts under its first kind in that order. A word whose only vocabulary reading is a refusal (`duke`) sorts under the kind it refuses, a refused category counting as its first kind, and a name reading places a word only when it has nothing else.
2. **Then by the word it is a spelling of**: a reading's `same_as`, or the word's own text when it has none. A head comes first and its spellings follow it, so `jr` is followed by `jnr` and `junior`, and `sr` by `snr`. A spelling that has spellings of its own heads a group inside its head's: in `ar.toml`, `el-` follows the `a…-` spellings of `al-` with its own assimilated forms after it, and `ul-` comes last. Only the file's own entries are followed, so a word that is a head in one file and a spelling in another is placed in each file by that file alone.
3. **Then by the word's text.**

Text is compared by codepoint. The texts are already normalized, so this is the order of the normalized text, whatever the script: Latin before Cyrillic before Arabic, and within a script an accented letter after `z` (`aḍ-` follows `az-` and `aš-`). It is defined for every script and the same on every machine, and it is no one language's collation. A traditional and a simplified spelling with no `same_as` between them sort apart. In `zh.toml` each pair is linked with the Simplified spelling as the `same_as` of the Traditional one, so the Traditional form heads the group (`课长` is `same_as = "課長"`): the Traditional form is the base orthography, and the Simplified one is its derived twin.

The build checks the order and never rewrites a file, because a comment above an entry belongs to it and must move with it, which a TOML reader cannot see. When the build says an entry belongs somewhere else, move it with its comment. The order is checked last, so any other refusal (an exclusion's reason, a `same_as` naming no word) is reported first. The same check refuses a `same_as` chain that loops, in every file.

`und.toml` is exempt, holding no language's words; a word leaving it for a language file takes its place in that file's order.

## Kinds

A reading's key is its **kind**. The table lists the kinds in their canonical order, which is the [word order](#word-order)'s first key and `CATEGORY`'s order in `nameparser/_reading_index.py`, the compiler the build shares with the package. Each kind belongs to one **category**, and the category decides which compiled set the reading feeds. For title, suffix, particle and conjunction the category's own name is also a kind (`title = {}`: a title not yet classified), so classifying a word later is a data edit that moves no compiled set. The one exception: a generic `suffix = {}` classified as `credential` moves from `SUFFIX_WORDS` to `SUFFIX_ACRONYMS`, because a credential's `acronym` is true unwritten; write `acronym = false` to keep it where it was. The suffix and particle categories are classified (two particles of unrecorded origin, `bon` and `dí`, keep the generic kind in `und.toml`); so are the titles (#750); the others carry their generic kind.

| Kind | Category | Compiled into |
|---|---|---|
| `title` | `title` | `TITLES` |
| `salutation` | `title` | `TITLES` |
| `style` | `title` | `TITLES`, `TITLE_STYLES` |
| `academic` | `title` | `TITLES` |
| `religious` | `title` | `TITLES` |
| `nobility` | `title` | `TITLES` |
| `military` | `title` | `TITLES` |
| `office` | `title` | `TITLES` |
| `occupation` | `title` | `TITLES` |
| `kinship` | `title` | `TITLES` |
| `modifier` | `title` | `TITLES`, `TITLE_MODIFIERS` |
| `suffix` | `suffix` | `SUFFIX_WORDS` |
| `generation` | `suffix` | `SUFFIX_WORDS`, `GENERATION_WORDS` |
| `agnomen` | `suffix` | `SUFFIX_WORDS`, `SUFFIX_WORDS_AMBIGUOUS`, `AGNOMENS` |
| `credential` | `suffix` | `SUFFIX_ACRONYMS` |
| `honorific` | `suffix` | `SUFFIX_WORDS`, `HONORIFIC_WORDS` |
| `professional_honorific` | `suffix` | `SUFFIX_WORDS`, `HONORIFIC_WORDS` |
| `status` | `suffix` | `SUFFIX_WORDS` |
| `courtesy` | `suffix` | `SUFFIX_WORDS` |
| `particle` | `particle` | `PARTICLES` |
| `preposition` | `particle` | `PARTICLES` |
| `article` | `particle` | `PARTICLES` |
| `patronymic` | `particle` | `PARTICLES`, `PATRONYMIC_PARTICLES` |
| `teknonymic` | `particle` | `PARTICLES` |
| `clan` | `particle` | `PARTICLES` |
| `rank` | `particle` | `PARTICLES`, `CAPITALIZED_PARTICLES` |
| `saint` | `particle` | `PARTICLES`, `SAINT_PARTICLES`, `CAPITALIZED_PARTICLES` |
| `alias` | `particle` | `PARTICLES` |
| `conjunction` | `conjunction` | `CONJUNCTIONS` |
| `bound_given` | `bound_given` | `BOUND_GIVEN_NAMES` |
| `birth_marker` | `relation` | `MAIDEN_MARKERS` |
| `given` | `name` | nothing |
| `family` | `name` | nothing |
| `familiar` | `familiar` | `FAMILIAR` |
| `spelling` | `spelling` | `ALTERNATE_SPELLINGS` |

`familiar` is a short given name that stands for longer ones without being a spelling of them (`max` for Maximilian and Maxwell, `bill` for William, `peggy` for Margaret), its `short_for` listing them. It compiles into `FAMILIAR` alone, which only the name match reads, as the opt-in outcome `familiar-form` ([decisions/name-matching](../../docs/design/decisions/name-matching.md), 2026-11-08): no parse reads it, a choice of languages neither prefers nor drops a word by it, and a word gaining one keeps its place in the [word order](#word-order), a familiar reading placing a word, as a name reading does, only when it has nothing else. It is not a `given` reading because a `given` reading moves parses wherever the word is also a title, a particle or a suffix (the [derived markers](#derived-markers)). The shipped ones are written by `tools/vocab/familiar.py` from `tools/vocab/familiar_reviewed.tsv` alone, the pairs `tools/vocab/familiar_candidates.py` finds in ORCID's public data file (CC0) and a few familiar forms that US public records evidence, each as two readers reviewed it, in the file of each language its holders' countries write ([decisions/name-matching](../../docs/design/decisions/name-matching.md), 2026-11-12 ALTERNATE SPELLINGS ARE OPT-IN and 2026-11-13 THE FAMILIAR FORMS FROM DATA ALONE); the same review gives the `spelling` readings. No list of familiar forms is copied, so none of them carries a licence of its own ([decisions/shipped-data-licences](../../docs/design/decisions/shipped-data-licences.md), 2026-11-13 THE NICKNAMES LIST LEAVES). Words already holding an entry gain a `familiar` line and the rest an entry each in a generated block at the file's end. The tool owns every `familiar` and `spelling` reading whose note is `found in CC0 or public-domain data and reviewed, tools/vocab/familiar_reviewed.tsv` and nothing else. Edit the tool, not those lines, and write any other one by hand with a note of its own.

`spelling` is a given name written another way, by the person or by a romanization, the same name in the same language community (`olha` of `olga`, `yuliya` of `iuliia`), its `spelling_of` listing the spellings. It compiles into `ALTERNATE_SPELLINGS` alone, which only the name match reads, as the opt-in outcome `alternate-spelling`: people sometimes spell a name differently on purpose, to be told apart, so a chosen spelling is never matched by default. It is a kind of its own rather than a `given` reading's `same_as`, which means a name written short (`chas` of Charles) and moves parses (`GIVEN_NAME_ABBREVIATIONS`, rules/H2); a spelling moves none, and a choice of languages neither prefers nor drops a word by it ([decisions/name-matching](../../docs/design/decisions/name-matching.md), 2026-11-12 ALTERNATE SPELLINGS ARE OPT-IN).

A suffix reading goes to `SUFFIX_ACRONYMS` when its `acronym` property is true and to `SUFFIX_WORDS` otherwise; the column shows where each kind goes with `acronym` unwritten. `GENERATION_WORDS`, `CREDENTIAL_WORDS` (a credential written as a word), `HONORIFIC_WORDS` (an `honorific` or `professional_honorific`) and `PATRONYMIC_PARTICLES` record the kinds the other sets do not, which the `generation`, `credentials`, `honorifics` and `patronymic` views read ([rules/R8](../../docs/design/rules/R8-generation-credentials-and-honorifics-views.md), [rules/R9](../../docs/design/rules/R9-patronymic-view.md)); `Lexicon` reads them, and since 3.0 no constant is public (#1007). A word has at most one suffix kind (check 4). A `given` reading carrying `same_as` goes to `GIVEN_NAME_ABBREVIATIONS`, a given name written short (see [Name readings](#name-readings)).

`generation` is a word that numbers or ranks its bearer among relatives of the same name, written after the name: junior and senior and their translations, `fils`, the roman numerals the vocabulary lists. `agnomen` is the Brazilian and Portuguese kind of it (`filho`, `neto`, `sobrinho` and their feminines): it is written in the case of the name around it, so its writing settles nothing, and an agnomen reading needs a name reading on its word (check 11), which gates it by the count alone ([rules/S11](../../docs/design/rules/S11-suffix-word-that-is-also-a-name.md), a suffix word that is also a name). The column shows an agnomen with that name reading.

The title kinds say what the title is:

- `salutation`: a language's everyday form of address, its "Mr" and "Mrs" (`mr`, `mrs`, `mx`, `herr`, `señora`, `г-н`, `श्री`), and the English `master` for a boy;
- `style`: an honorific style or dignity rather than an office (`hon`, `excellency`, `highness`, `sheikh`);
- `academic`: an academic or professional form of ADDRESS (`dr`, `prof`, `docent`, the Egyptian `مهندس`, engineer);
- `religious`: a clergy, monastic, saintly or religious-scholar title (`rev`, `rabbi`, `swami`, `saint`), and a kinship word used as one (`father`, `sister`);
- `nobility`: a royal, noble, chiefly or chivalric rank (`king`, `prince`, `graf`, `sultan`, `sir`, `dame`, `knight`);
- `military`: a military or police rank and its abbreviations (`gen`, `capt`, `sgt`);
- `office`: a public, judicial, civic, corporate or court office held (`president`, `judge`, `mayor`, `ceo`);
- `occupation`: a job DESCRIBED before a name, as bylines and captions write it, household service included (`actor`, `novelist`, `guitarist`, `maid`);
- `kinship`: a family word written as a title (`aunt`, `uncle`);
- `modifier`: a word that is a title only inside a phrase with a head title (`vice`, `grand`, `assistant`, `his`, `1st`), decision 10 of [decisions/vocabulary-model](../../docs/design/decisions/vocabulary-model.md). A word whose every title reading is a modifier compiles into `TITLE_MODIFIERS` too, and in the leading run of titles before the first comma it is a title only with a head title after it in that run, before `of` (`Mother Superior of the Convent`), or inside the object of `of` or `the` there (`President of the United States`); ending the name, or after a comma, it is read as any title is ([rules/H9](../../docs/design/rules/H9-title-phrase.md), the title phrase), save a modifier with a `given` reading (`wing`), which that test reads in every part. A word that qualifies the head it stands behind is no modifier in this sense: `d'affaires`, after `chargé`, is an `office`. A word written in a part after a comma as the person's role is not one either: `resident`, `rt` and `pro` were reclassified for that (2026-10-25). A `style` compiles into `TITLE_STYLES`, the one other kind with a set of its own: a style or a modifier before a title that may be a given name puts it in a title phrase (`The Hon. Justice Smith`).

`academic` and `occupation` are told apart by what the word does, not its subject: `Dr` addresses the person, `chemist` describes them. A title is written with one kind per file, as a particle is (a convention, not a check), and check 5 holds every title reading of a word to the same `addresses` whatever its kind. `gender` is recorded, as each title is classified, on one marked for one sex (a feminine form, `actress`, `señora`, or one half of a fixed pair, `mr` and `mrs`, `king` and `queen`), and on `mx` as `"n"`; an unmarked noun (`actor`, `doctor`) records none.

The particle kinds say what the word does in the names of the file's language:

- `preposition`: "of", "from", "at", alone or contracted with the article after it (`de`, `van`, `von`, `du`, `del`, `vom`, `ter`);
- `article`: a definite article standing alone or elided (`la`, `der`, `het`, `'t`, `l'`, the Arabic `al-` and its assimilated spellings);
- `patronymic`: "son of" or "daughter of", where the word after it is a parent's name (`bin`, `binti`, `ibn`, `بن`, `בת`, `ould`);
- `teknonymic`: "father of", naming the bearer by a child (`abu`, `أبو`);
- `clan`: a lineage prefix, where the word after it is a family name shared by the lineage rather than a parent's name (`mac`, `mc`, `ó`, `ní`, `آل`, and `ben` and `בן`, whose family names no longer name a father);
- `rank`: a former rank written inside the surname (`freiherr`, `freiherrin`, `graf`, `gräfin`, `fürst`, `prinz`);
- `saint`: "Saint" opening a surname (`san`, `santa`, `st`, `ste`, `sta`, `sto`);
- `alias`: a word joining two surnames of one person (`vel`).

Unlike the suffix kinds, one word may take a different particle kind in each language: `de` is a preposition in `fr.toml` and an article in `nl.toml`. Whether a particle may be given is the word's, not the reading's: its `given` reading, in any file, decides it for every particle reading (check 11). On a particle reading, `expands` is the word's meaning in that language, and `note` is reserved for vetting. A never-given particle may rest on its kind and `expands` alone: one attested bearer settles the may-be-given side, but no amount of searching settles absence, so what is recorded is what the word IS (an article, a preposition) rather than a failed search. And a word with a `given` reading whose particle readings carry no `note` in any file sits on the conservative default and nobody has examined it, and so does one whose note says so, as `heer`'s does: counts on the given reading were taken for phase 2's derivation (2026-10-25), not read against the particle position. The test is per word, because a word's note sits in one of its files, not in each: `mac` is examined though only `en.toml` holds its note.

**Classifying a category adds kinds to every check that tests it.** While a category has only its generic kind, a check that asks for the category and one that asks for the generic kind give the same answer, so a test row written in the generic kind cannot tell them apart. When a category gets its first fine kinds, give every check on that category a row in `tests/v2/test_vocab.py` written in a fine kind, and run each row against the check keyed on the kind to see it fail. #749's review found four particle checks pinned only on the generic `particle` kind once the shipped data used it for two words: the required `may_be_given`, an exclusion refusing a sibling kind, the bound given name that is a never-given particle, and the elided particle's two spellings. Each passed every test when keyed on the kind, which would have let a `preposition = {}` with no `may_be_given` compile silently into the never-given set.

The `name` kinds compile to nothing on their own. They record that a word is borne as a given or family name, with counts (see [Bearer counts](#bearer-counts)), as evidence for a reading or an exclusion, and a `given` or `family` reading beside an acronym reading, or a `given` reading beside a particle reading derives a marker (see [Derived markers](#derived-markers)), unless it is written `default = false`.

## Properties

A property is **behavioral** when it compiles into a set and so changes how names are parsed, **stated** when it compiles to nothing but the build holds it to the word's readings, **matching** when it compiles into a map only the name match reads and so changes no parse (`short_for`, a `familiar` reading's own), and **descriptive** when it is checked and recorded but compiled to nothing, save `same_as`, which compiles into `SAME_AS` on every kind a name match compares (in the group of its kind) and, on a `given` reading, also puts the word in `GIVEN_NAME_ABBREVIATIONS` (see [Name readings](#name-readings)). Each is allowed only on the categories listed; a `name` reading takes its own keys (see [Name readings](#name-readings)). Two of the sets are not properties at all but [derived markers](#derived-markers), read off a word's name readings.

| Property | Type | Applies to | Unwritten | Effect |
|---|---|---|---|---|
| `addresses` | behavioral | `title` | `"family"` | `"given"` adds the word to `GIVEN_NAME_TITLES`: `Sir John` reads `John` as the given name ([rules/H1](../../docs/design/rules/H1-title-and-one-name-word.md), a title and one name word) |
| `attaches` | behavioral | `title` | none | `TITLE_PHRASES`: the title kinds, or the title words, this word stands before in a title phrase, a list (`chief = { attaches = ["office", "military"] }`, `sergeant = { attaches = ["major"] }`, a word where a kind would reach too far; a name that is also a kind of another category names the word, `pope = { attaches = ["saint"] }`, `saint` being a particle kind too, as `family` is a name kind and a modifier title word), compiled into the two-word phrases it makes with each title word of those kinds and each word named (`chief justice`, `sergeant major`); a title that may be a given name on either side of one is a title there ([rules/H9](../../docs/design/rules/H9-title-phrase.md), the title phrase) |
| `after_given` | behavioral | `title` | false | `AFTER_GIVEN_TITLES`, on a `salutation` reading only: written bare at the end of the given part after a family comma, the word is the title, as in `Doe, Jane Mrs` ([rules/H8](../../docs/design/rules/H8-salutation-ending-the-given-part.md), a salutation ending the given part). A salutation borne as a given name or a surname is left out with an exclusion of the property, its counts beside it (`goodman`, `herr`), since a middle name may be either |
| `abbreviation` | behavioral | `title` | false | `TITLE_ABBREVIATIONS`: true says the title reading is written short (`maj`, Major; `gen`, General). On a title that may be a given name ([rules/H9](../../docs/design/rules/H9-title-phrase.md)) it makes the word, written with its period at the end of the name, the trailing title, as in `SMITH, JOHN B. MAJ.` ([rules/H5](../../docs/design/rules/H5-trailing-title-run.md), the trailing title run), and on a style it makes the article before it the word's phrase partner, as in `The Hon John Smith` under a Chinese choice ([rules/H9](../../docs/design/rules/H9-title-phrase.md)); on any other title it changes nothing, H5 reading every listed title there already. `expands` names the full form and compiles to nothing |
| `acronym` | behavioral | `suffix` | true for `credential`, false for every other kind | true: `SUFFIX_ACRONYMS`, matched with every period removed (`M.D.` is `md`); false: `SUFFIX_WORDS`, and a credential's `CREDENTIAL_WORDS`, a credential written as a word |
| `title_case_is_name` | behavioral | `suffix` | false | `TITLE_CASE_NAME_WORDS`, on a `generation` or a `credential` written as a word (`acronym = false`) only: says the word's Title case is its writing as a name, so where a name reading gates the word ([rules/S11](../../docs/design/rules/S11-suffix-word-that-is-also-a-name.md), a suffix word that is also a name), its writing leans: Title case is the name, lower case in a name of mixed case the suffix, capitals nothing ([rules/S6](../../docs/design/rules/S6-case-signal-at-the-suffix-slot.md), the case signal at the suffix slot), as in `Marie Fils` and `Alexandre Dumas fils`. Unwritten, a gated word's writing says nothing and the count decides, as for `Junior`, whose Title case is how the generation is written too; an agnomen's writing never speaks (#1039) |
| `attached` | behavioral | `suffix`, `title` | absent | on a suffix word reading, `GLUED_HONORIFICS`: `{ side = "after" }` splits the word off the end of a name token, as in `田中さん` ([rules/W2](../../docs/design/rules/W2-glued-honorific-peel.md), the glued-honorific peel); on a one-word title reading, `GLUED_TITLES`: `{ side = "before" }` splits the title off the start of the name's first word, as in `นายสมชาย` ([rules/W6](../../docs/design/rules/W6-glued-title-peel.md), the glued-title peel) |
| `shared` | behavioral | `name` | false | `SHARED_NAMES`: a name a community gives every member, written after the personal name and before a family name where there is one (Sikh `kaur` and `singh`), no personal or family name of the bearer's own: two-family-name handling ([rules/O6](../../docs/design/rules/O6-two-family-names.md)) and two-given-name handling ([rules/O7](../../docs/design/rules/O7-two-given-names.md)) neither take it nor complete one with it, so `Harpreet Kaur Dhillon` keeps middle `Kaur` under either, and a given name a particle completes ([rules/P10](../../docs/design/rules/P10-given-name-a-particle-completes.md)) is never one, so `Kaur del Carmen García` keeps family `del Carmen García` by default (#704) |
| `after_particle` | behavioral | `name` | false | `PARTICLE_GIVEN_NAMES`, on a `given` reading only: a given name written behind a particle as the second of a compound given name (`carmen` in `María del Carmen`): behind a one-word given name the particle run and the word are a middle name, though the chain would run on into the family, as in `María del Carmen García` ([rules/P10](../../docs/design/rules/P10-given-name-a-particle-completes.md), a given name a particle completes, which states the conditions), which two-given-name handling ([rules/O7](../../docs/design/rules/O7-two-given-names.md)) then takes into the given name and two-family-name handling ([rules/O6](../../docs/design/rules/O6-two-family-names.md)) leaves where it stands. A word is marked where, of the names its reading moves to the boxes their filers filled or away from them, at least 75% move to them, with ten such names or more: on by default where that holds over every language's countries pooled, written `default = false` in its language's file where it holds in that language's countries alone, for a choice of the language to turn on, and left out where it fails (`kassia`); a word with fewer than ten such names keeps the tier an earlier measure gave it (`ribamar`, `piedade`), and `luz` was left out by #704's given-box share (decisions/P10, #704, #1118, #1122) |
| `completed_by` | behavioral | `bound_given` | none | `BOUND_PHRASES`: the words that complete the bound given name into one name unit past the first name word, a list (`completed_by = ["الله", "الرحمن"]` on `عبد`), each one word written folded: `سعيد عبد الله` reads family `عبد الله` ([rules/P12](../../docs/design/rules/P12-bound-given-name-and-the-word-that-completes-it.md), a bound given name and the word that completes it), while a word left off the list after it is a name of its own, as in `نوال عبد هاشم` (#694) |
| `dotted` | behavioral | `title` | false | `DOTTED_TITLES`: the title abbreviates several words and is written with a full stop after each letter (`us`, `uk`, German `pd`), so a run of single letters joined by full stops that spells it is that title at the head of a name where a title the name keeps follows it, as in `U.S. District Judge Marc Treadwell`, and the initials it is written as otherwise (`U.S. Grant`) ([rules/H10](../../docs/design/rules/H10-title-written-as-a-run-of-letters.md), a title written as a run of letters). A title abbreviating one word (`dr`, `mr`, `lt`) is left unmarked, since two initials spell it (`D.R. Judge Smith` keeps given `D.R.`) |
| `capital_opening` | behavioral | `particle` | false | `CAPITAL_OPENING_PARTICLES`: the particle is written with a capital where the word before it in the family name is no particle, nor, where it opens the family name, the word written right before it in any role (`Van der Walt` keeps its lowercase `der`), as the Armenian priestly prefix is (`ter` and `der`: `LEVON TER PETROSYAN` repairs to `Levon Ter Petrosyan`), and keeps its lowercase after one (`Jan van der Berg`) ([rules/R12](../../docs/design/rules/R12-particle-opening-the-family-name-with-a-capital.md), a particle opening the family name with a capital); it moves no parse. A Dutch surname opened by `ter` takes the capital too (`Gerard Ter Borch`), a cost accepted in decisions/R12 |
| `may_be_given` | stated | `particle` | none: required where the word has no `given` reading | `false` is required where the word has no `given` reading in any file, and that absence, not the property, is what puts the word in `NON_GIVEN_NAME_PARTICLES`: a particle opening the name starts the family name ([rules/P1](../../docs/design/rules/P1-lone-particle-fold.md), the lone particle fold). `true` is refused, naming the `given` reading to write instead (check 11) |
| `may_be_initial` | behavioral | `conjunction` | false | `CONJUNCTIONS_AMBIGUOUS`, on a cased single letter only: read as an initial in a name written in one case, as in `JOHN E SMITH` ([rules/P8](../../docs/design/rules/P8-single-letter-connective-against-the-initial-it-spells.md), a single-letter connective against the initial it spells) |
| `default` | behavioral | `title`, `suffix`, `particle`, `conjunction`, `bound_given`, `relation`, `name`, `familiar`, `spelling` | true | `false` keeps the reading out of every compiled set, `SUFFIX_WORDS` and `GENERATION_WORDS` included for a generation: recorded and checked as a reading, for a choice of languages to turn on (3.0's phase 3), where its writing offers the default no cue (`i`, the German regnal ordinal, written `I.`, exactly as an initial is). An exclusion does not refuse it, and it cannot read two ways beside the word's live readings (checks 4 to 6); a name reading beside it marks nothing. On a `given` or `family` reading (3.0's phase 3a) it derives no marker in the default, so the word's other readings compile as they would without it, until a pack turns the name on. It does not count as the name reading an agnomen on by default needs (check 11), and a particle whose word's only `given` readings are off is refused, which side of check 11 it takes being left to the first pack that needs one; a bound given name that is also a particle is refused with it, before check 9 would ask for its `given` reading. `true` is refused: it is what every reading is unwritten |
| `cased` | behavioral | `title`, `suffix`, `particle`, `conjunction`, `bound_given`, `relation`, `name` | the word as written | `CAPITALIZATION_EXCEPTIONS`: the case `capitalized()` gives the word (`PhD`), a mask over its letters and digits, never a replacement (#459); on a name reading, a name whose capitals case repair cannot work out from its spelling (`MacGregor`, #1014) |
| `short_for` | matching | `familiar` | none: required | `FAMILIAR`: the longer given names the word stands for, a non-empty list of single words written normalized, never the word itself (`max = { short_for = ["maximilian", "maxwell"] }`), read by the name match alone: where `familiar-form` is accepted, `Max Smith` and `Maximilian Smith` are consistent, and `Maximilian Smith` and `Maxwell Smith` are not: the match reads a pair whichever way it is written (`barbara = { short_for = ["babs"] }` matches as its reverse would) and never chains two pairs. An `add(w, kind="familiar", short_for=[...])` extends the longer names the word's readings list, in a reading of the caller's own that names no file; a pair lives on the word whose reading lists the other, so to cut one, `remove(w, kind="familiar")` and add back the names to keep. A `familiar` reading needs a `note` saying where the pair is attested, and takes no `same_as`, `expands`, `native` or `gender` |
| `spelling_of` | matching | `spelling` | none: required | `ALTERNATE_SPELLINGS`: the given names the word is another spelling of, a non-empty list of single words written normalized, never the word itself (`olha = { spelling_of = ["olga"] }`), read by the name match alone as the opt-in `alternate-spelling`: where it is accepted, `Olha Petrenko` and `Olga Petrenko` are consistent. Unlike a `given` reading's `same_as`, it gives the word no name reading and puts it in no set a parse reads (`GIVEN_NAME_ABBREVIATIONS` among them), so `Olha. Petrenko` parses as it did. A pair is read either way and never chained, as a familiar form is. An `add(w, kind="spelling", spelling_of=[...])` extends the word's names in a reading of the caller's own. A `spelling` reading needs a `note` saying where the pair is attested, and takes no `same_as`, `expands`, `native` or `gender` |
| `note` | descriptive | every category, a `name` reading included | | free text: why the reading is as it is |
| `issue` | descriptive | every category but `name` | | an issue number, or a list of them |
| `decided` | descriptive | every category but `name` | | a TOML date |
| `expands` | descriptive | every category but `name`, `familiar` and `spelling` | | the meaning the entry was added for, not every meaning |
| `same_as` | descriptive | every category but `familiar` and `spelling` | | another word of the same category that this one is a spelling of (`jnr` is `jr`); every reading's `same_as` compiles into `SAME_AS`, keyed by the group of its kind (`given` for a given name or a bound given name, `family` for a surname or a particle, `title`, `suffix`; a conjunction's and a birth marker's into none), each word with every full form it carries there: the map `Lexicon` reads for the name match, which reads two words of one role as listed spellings where the words reachable from each through that role's group meet (`Wm.` and `William` as given names, `Jr.` and `Junior` as suffixes, `Ma.` and `María` as given names but never as surnames, `ma` being a given name of its own too, which the match reads as `María` only written with its period: `SAME_AS_NAMED`, a [derived marker](#derived-markers)), and which moves no word between sets; on a `given` reading, the full given name the word abbreviates, which also compiles the word into `GIVEN_NAME_ABBREVIATIONS` (see [Name readings](#name-readings)) |
| `native` | descriptive | every category but `familiar` and `spelling`, a `name` reading included | | a native-script spelling |
| `gender` | descriptive | every category but `familiar` and `spelling`, a `name` reading included | | `"f"`, `"m"` or `"n"`, only where the word gives a definitive clue |

Two of these need more than their row:

- **`may_be_given` has no default.** The format before this one listed the never-given particles and treated every other particle as possibly a given name, so a new particle was ambiguous unless argued otherwise ([decisions/vocabulary-collisions](../../docs/design/decisions/vocabulary-collisions.md), C-i). A default here would pick one side of that silently, so the build refuses a particle reading that neither states `may_be_given = false` nor has a `given` reading on its word. When unsure, write the `given` reading, with a `note` if no source counts it.
- **`cased` belongs to the word**, not the reading: one mask per word, whichever reading carries it.

### Derived markers

Four sets mark a clash with a name, and all four are derived: a word is in one when it carries the clashing reading and a name reading on by default, in any of its files (check 11, since 2026-10-25, [decisions/vocabulary-model](../../docs/design/decisions/vocabulary-model.md)). Phase 1 wrote two of them as flags, `may_be_name` and `may_be_given = true`, which the build now refuses, naming the reading to write; the third, a suffix word that is also a name, arrived with phase 2h, and the fourth, a title that may be a given name, with phase 2i.

A fifth derived set marks no clash: a word whose name reading carries `same_as` beside a plain name reading of the same kind, in any of its files, a name written short that is a name of its own too, is in `SAME_AS_NAMED`, which only the name match reads ([decisions/name-matching](../../docs/design/decisions/name-matching.md), 2026-11-08). It shares the table below.

| Marker | Readings | Compiled into | Effect |
|---|---|---|---|
| possibly a name, a word | a `generation` or `agnomen` reading, or a `credential` written as a word (`acronym = false`, `kc`, `pc`, `dl`), and a `given` or `family` reading; a name reading beside any other suffix word kind is refused (check 11), no gate reading that clash | `SUFFIX_WORDS_AMBIGUOUS` | a suffix word that is also a name (`fils`, `neto`) is read as a suffix only where the name has words to spare, as an ambiguous acronym is: `Alexandre Dumas fils` and `Pedro Alves Neto` end in a suffix, `Marie Fils` and `Ana Neto` in a family name, either way reported ([rules/S11](../../docs/design/rules/S11-suffix-word-that-is-also-a-name.md)). A word written `title_case_is_name` (`fils`, `kc`) leans to the name in Title case in a name of mixed case, and its lower case settles it as the suffix wherever the name keeps a family word; any other's writing settles nothing, an agnomen's or `junior`'s |
| possibly a name | an acronym `suffix` reading and a `given` or `family` reading | `SUFFIX_ACRONYMS_AMBIGUOUS` | an acronym that is also a name (`ma`) is read as a suffix only where its spelling or the name around it says so: `John Smith MA` and `John Smith M.A.` end in a suffix, `John Smith Ma` in a family name ([rules/S4](../../docs/design/rules/S4-ambiguous-acronym-needs-words-to-spare.md), the ambiguous acronym needs words to spare; [rules/S6](../../docs/design/rules/S6-case-signal-at-the-suffix-slot.md), the case signal at the suffix slot) |
| possibly a name, a title | a title reading and a `given` reading, on a word with no particle reading | `TITLES_AMBIGUOUS`, and kept out of `TITLES` | a title that may be a given name (`dean`, `justice`, `major`) is a title only inside a title phrase: after a modifier, a style or a title it stands behind in a phrase `attaches` makes, or before `of` or a title it attaches to. Elsewhere it is a name word, reported where it opens the name if a phrase `attaches` makes holds it (`grace`, held by none, is a title only behind a style or a modifier and reports nothing): `Dean of Students` and `Major General Smith` read the title, `Dean Smith` and `Mr Major Smith` the given name ([rules/H9](../../docs/design/rules/H9-title-phrase.md), the title phrase). A title that is also a particle (`st`, `freiherr`) is left to the particle rules, its `given` reading deriving the particle's marker alone. A salutation's given-name counts kept as evidence for `after_given` sit in the salutation reading's `note` (`mr`, `herr`), so they mark nothing |
| a name of its own, a spelling | a name reading carrying `same_as` and a name reading of the same kind carrying none (`jo`: José written short in `fil.toml`, the given name Jo in `en.toml`) | `SAME_AS_NAMED`, in the group of the kind | the name match reads the word as a listed spelling of its full form only written with its trailing period: `Jo. Garcia` and `José Garcia` are a listed spelling, `Jo Garcia` and `José Garcia` a conflict, while a word that is no name of its own reaches its full form either way (`Wm Smith`, `WM SMITH` and `William Smith`). It moves no parse. A bound given name's or a particle's `same_as`, a spelling written without a period (`ابو` of `أبو`), marks nothing |
| possibly given | a `particle` reading and a `given` reading | kept out of `NON_GIVEN_NAME_PARTICLES` | a particle opening the name stays a given name there (`van Gogh`, given `van`) and the fork is reported, rather than starting the family name ([rules/P1](../../docs/design/rules/P1-lone-particle-fold.md), the lone particle fold) |

Before phase 2h (2026-10-25) a word reading of the suffix category beside a name reading marked nothing, and no shipped word had one. The marker is the clash, not the counts: a count recorded for a word that should stay unmarked goes in the clashing reading's `note`, as `ld`'s does, since a name reading would mark it. `may_be_initial` is not derived: its clash is with the initial, a shape every cased single letter has, and which letters a tradition writes both ways is a judgment about the letter, not a name anyone bears.

### Name readings

A `given` or `family` reading takes its own keys:

| Key | Meaning |
|---|---|
| `us_census_2010` | bearers as a surname in the 2010 US Census |
| `us_ssa` | births with this given name in US Social Security data, all years summed; say in `note` which sex, or that both are added |
| `wikidata` | people in Wikidata with this as their given or family name, a lower bound |
| `as_of` | the date the counts were taken, required beside any count |
| `native` | a native-script spelling |
| `note` | free text |
| `gender` | `"f"`, `"m"` or `"n"` |
| `same_as` | on a `given` reading only (the build refuses one on a `family` reading; a caller's `add` may write one): the full given name the word abbreviates, normalized (`chas` is `charles`), which puts the word in `GIVEN_NAME_ABBREVIATIONS`: written with its period at the head of the part of the name that carries the given name, the word is that given name, where an unlisted abbreviation there is a title by its shape ([rules/H2](../../docs/design/rules/H2-leading-abbreviation-title.md), the leading-abbreviation title), so `Chas. Smith` reads given `Chas.`. It also compiles into `SAME_AS`'s `given` group, so the name match reads the word and the name as listed spellings of each other in the given name, middle name and nickname (`Ma.` and `Maria`), never in the surname; where the word is also a given name of its own, a `given` reading with no `same_as` in any file (`jo`, `ma`, `jas`), only written with its period (`Jo.`, the word then in `SAME_AS_NAMED`, a [derived marker](#derived-markers)). The marker reads the vocabulary as edited: a caller's `add(w, kind="given", same_as=...)` writes the link onto the word's given readings, so the word has no plain given reading left and its link counts written bare, and a caller cannot currently mark a word of its own as a name of its own. Parsing reads it nowhere else. A name is no word of the vocabulary, so this `same_as`, unlike a reading's, names no entry, and an entry holding only such a reading is not inert |

A name reading may stand without a count, as a particle kept possibly given under C-i's default with no source counting it does, but it then needs a `note` saying why it is declared (check 3). It may also be written `default = false`, the behavioral property in [Properties](#properties): recorded and checked, it derives no marker until a pack turns it on. And it may carry `cased`, the word's case mask, another behavioral property a name reading takes: case repair title-cases a Mac surname, so one its bearers write with the inner capital carries the mask (`macgregor` is `MacGregor`, #1014), and its entry, holding only that name reading, compiles. So do the two properties the two-name switches read: `after_particle` on a `given` reading (`carmen`, of `María del Carmen`) and `shared` on either (`kaur`, `singh`), each an entry holding only that name reading (#704).

## Exclusions

An exclusion records that a reading was considered and refused, with the reason, so that the next person to propose it meets the reason as a build error instead of rediscovering the evidence. It means the reading is wrong in every language: a reading right in its own language and wrong only as a default, because another language collides with it, is written `default = false` instead ([Properties](#properties)), for a choice of that language to turn on, as cs `ml` is.

- **A refused reading** is a word-level table: `[word.excluded.generation]` with a `reason`, or `excluded = { generation = "the reason" }`. It refuses that kind in every file, and also every other kind that compiles into the same set, so a generic `suffix = {}` cannot put back a refused `generation`. A category name refuses the whole category (`excluded = { suffix = "..." }`). A `name` kind refuses only itself.
- **A refused property** sits on a reading the word keeps: `[word.honorific.excluded]` with `attached = "the reason"`. It refuses any value of that property other than the one it takes unwritten, on any reading of the category; a refused `cased`, which belongs to the word, on any reading of the word.

The value is a reason string, or a table with `reason` and optionally `issue`, `decided` and `note`. The exclusion goes in the file of the language whose reading it refuses. An entry may hold exclusions and no vocabulary reading, as `duke` does. An entry with no reading and no exclusion is refused as inert, and one holding only a name reading is a warning, which the test suite makes an error, unless that reading is a `given` reading carrying `same_as` or a reading carrying `cased`, each of which compiles.

To see what has been refused, and why: `uv run python tools/vocab/query.py --excluded generation`.

## Bearer counts

Counts come from `tools/name_usage.py`, which reports how often a word is borne as a given name and as a family name in four name sources: 2010 US Census surnames (listed from 100 bearers), US Social Security given names (a name-sex pair is listed for a year from 5 births, reported per sex), Jörg Michael's nam_dict (a given-name frequency band per country, not a count) and Wikidata (live, with countries of citizenship, and a lower bound because many people have no name statement). For a word holding a Han, kana or hangul letter it adds a row of the Wikidata names that END in the word, which is the question for a glued honorific. For a word holding a Tamil, Sinhala, Thai, Ge'ez, Burmese, Gurmukhi, Georgian or Armenian letter it adds a row of the people with an article on that script's Wikipedia whose name holds the word, counted by where the word stands (first, inner, last or alone), since Wikidata's name items carry almost no labels in those scripts (#1244, #1225). With `--fetch-nppes` it also counts the US healthcare providers who write the word as a credential (NPPES), the other side of a suffix that is also a name; `--rank N` lists the commonest credentials with their name counts and how a comma name ending in each one parses. Its docstring says what each number can and cannot show.

Record a count on the word as a `given` or `family` reading, with the date you took it in `as_of`. A source's count is left out when it is below that source's floor, never written as 0. A suffix reading has no count field yet, so a credential count goes in the reading's `note`, with its date and source. Counts are provenance: they are the evidence a decision was made on, and nothing computes a reading from them. The reading itself is not inert where it clashes, as a `given` or `family` reading beside an acronym reading, or a `given` reading beside a particle reading does, marking the clash, so counts kept there as evidence AGAINST marking go in the clashing reading's `note` (`ld`).

## Adding a word

1. **Look up the word's other readings.** `uv run python tools/vocab/query.py --word <word>` lists every reading and exclusion of it in every file. An exclusion there is a decision already made; a reading in another category is a clash you are about to create, which is fine when position settles it (`do`) and needs an argument when it does not.
2. **Check it against real names, not memory.** `uv run python tools/name_usage.py <word>` gives the counts (add `--fetch-nppes` for a suffix, to see how often it is written as a credential), and [decisions/vocabulary-collisions](../../docs/design/decisions/vocabulary-collisions.md) is the criterion they are read against: a word that is a real name in the position the reading acts on needs a name reading with those counts, which marks the clash (see [Derived markers](#derived-markers)), or should stay out. `nameparser/vocab/AGENTS.md` lists the traps that have bitten before, filed under these steps.
3. **Check how it is written.** The entry's `text` is the folded spelling (`mbchb`), and `capitalized()` writes an acronym credential in capitals unless the word has a `cased` mask, so one that people write in mixed case (`MBChB`, `DPhil`, `ScD`) needs the mask: `cased = "MBChB"`. Nothing in the build can see this, since no source it reads records case. The ClinicalTrials.gov row of `name_usage.py` lists the spellings as typed ("written MBChB 1,442, MBCHB 72, MbChB 28"), once that local corpus is fetched (`uv run python tools/differential/local_corpora.py fetch ctgov-officials`). Where a mask would cost a name its rendering, refuse it instead, with the reason, as `edd` does (`'edd smith'` would render `'EdD Smith'`). #806 added twelve mixed-case credentials without their masks, and review caught it.
4. **Write the entry** in the file of the language whose names it occurs in (`und.toml` when that is not known), in its place in the [word order](#word-order), with what the checks found on it: `note`, `issue`, a dated name reading, a `cased` mask, or an `excluded` entry if you decided against it.
5. **Rebuild**: `uv run python tools/vocab/build.py`. It refuses what it can detect, naming the word and, where one file is at fault, the file, and rewrites `nameparser/config/_compiled.py`, `nameparser/config/_index.py` and `nameparser/config/_rules.py`. Commit the file and whichever modules it moved.
6. **Run the tests**: `uv run pytest tests/v2/test_vocab.py` for the build, then the full suite, and read what `tests/v2/test_snapshot.py` reports as moved (the root `AGENTS.md`, "Validating a new parsing rule"). `uv run python tools/differential/measure.py --base <checkout>` runs that check and the CLDR one against the branch's committed records, and every local-corpus check against the base checkout, in one command, writing one summary (`tools/differential/README.md`, "Measuring a change").

For a word whose reading acts on a name position, such as a title that is also a given name, `uv run python tools/vocab/word_report.py <word>... --base <checkout>` reads it both ways in one run: the word in a grid of shapes (a head, behind a title, after a family comma, after a full name and a comma, past a second comma, trailing with a period, inside a title phrase), each in three cases and under the three name orders, printing the rows the base reads differently; how the names in every fetched local corpus that open with the word, or open the part after the first comma with it, read it (title, given or other, counts only, with the corpora it could not read named); and `name_usage.py`'s rows. Without `--base` it prints every text, one line where the three orders agree and one block where the three cases read alike once lowercased; with it, what moved, folded the same way. `--rank` takes a list of words, the triage for a batch, which needs no change to the tree. It counts the corpus names that read each word as the title at either position, which holds real titles too, and beside them the `psc-individuals` filings opening with the word by the box the filer typed it into: the title box (a real title, what the move costs) and the forename box (a given name the title takes, what it gives back). The words are ordered by the forename box's count, printed beside its share of the two as a fraction (`164/165`), so a word three filers typed as a forename does not outrank one 164 did. On 2026-10-27 `sir` read as the title in 495 names but was filed 277 times as a title and 8 as a forename, while `sheikh`'s 13 title-box filings were the 13 agreement records #912 moved away from agreeing.

For what a language's file is missing before a strict choice of it stands alone, `uv run python tools/differential/config_diff.py gaps [tag...]` reads each language's plain and strict choices over the names of the countries it is written in and ranks the words strict reads differently by the records it breaks (`tools/differential/README.md`, "Measuring a change").

`uv run python tools/vocab/build.py --check` exits 1 when a committed module is stale and 2 when a file fails a check. The checks themselves are numbered in `build.py`'s docstring.

## Rules

A file a shipped locale pack reads may hold a `[rules]` table: the rules that pack turns on, compiled by the build into `nameparser/config/_rules.py` and read by `nameparser._locale.rules_patch` as the pack's `policy` (3.0's sub-phase 4f, #754). Each key is the `Policy` field of the same name, so the table says in data what `Policy(...)` says in code:

```toml
[rules]
patronymic_rules = ["east-slavic"]
```

| Key | Value | The `Policy` field it sets |
|---|---|---|
| `patronymic_rules` | a non-empty array of rule names, each once: `"east-slavic"`, `"turkic"` | `patronymic_rules`, a set of `PatronymicRule` (rules/O1, rules/O2) |
| `name_order` | `"family-first"` or `"family-first-given-last"` | `name_order`, the order constant of that name |
| `two_family_names` | `true` | `two_family_names` (rules/O6) |
| `two_given_names` | `true` | `two_given_names` (rules/O7) |
| `initials_as_family` | `true` | `initials_as_family` (rules/O8) |

A rule is written only to turn it on: `name_order = "given-first"`, `two_family_names = false`, `two_given_names = false` and `initials_as_family = false` are the defaults, and a pack's value overrides the caller's own, so the build refuses all four rather than let a pack switch a caller's rule off. The files that hold a table are exactly the ones `PACK_RULES` in `tools/vocab/build.py` lists, each beside the pack that reads it (`tr.toml` is `locales.TR_AZ`'s, one file for Turkish and Azerbaijani, since there is no `az.toml`; `es.toml`'s is `locales.ES_AR`'s too, a country pack reading its language's table, since none of the countries measured turns a rule differently from its language); a table in any other file is a build error, since nothing would read it, and so is a file listed there without one. Writing a `[rules]` table does not choose the file's vocabulary: that is the pack's `languages`, a separate field.

A rule KIND the table does not list (a married-name ending) is a change to the parser, not to a file: a new `Policy` field (with `ADDED_IN`), a row in `build.py`'s `RULE_KEYS` and in `_locale.py`'s `_RULE_VALUES`, and a mechanisms.md entry of its own for the rule kind, or an amendment to the entry whose shape it shares (`initials_as_family` joined DECLARED-SPAN's switches) (mechanisms.md#LOCALE-PACKS-PURE-DATA). `tests/v2/test_vocab.py` holds the two tables to each other and to `Policy`.

## Names reserved for later releases

These names are reserved for a meaning phase 4 planned and 3.0 did not build: unbuilt, 3.x. Writing one now as a key, in a file, an entry or a reading, is a build error saying so, so nothing reads as working before it does.

| Name | Unbuilt, reserved for |
|---|---|
| `bare_only` | 3.x |
| `leading_only` | 3.x |
| `trailing_only` | 3.x |
| `separators` | 3.x |

`prefer` and `strict`, reserved for phase 3 by phase 1, are refused for good: phase 3 made each the caller's (a choice of languages prefers its readings, and `parser_for(..., strict=True)` is strict), so the build says a strength is never data.

Phase 2 gave `default` and `attaches` their meaning (2026-10-25, see [Properties](#properties)). The gate's slots carry position and shape already settles a bare letter ([rules/P7](../../docs/design/rules/P7-one-letter-particle-against-the-initial-it-spells.md), a one-letter particle against the initial it spells), so `leading_only`, `trailing_only` and `bare_only` wait for the shapes phase 4 planned, as `separators` waits for its glued words, none of them built in 3.0.

Two property values are refused for the same reason, with a message saying a later phase: `addresses = "full"` and `"any"`. `attached` takes the one `side` its category reads, `"after"` on a suffix and `"before"` on a title (#317 gave it the second), and the build refuses the other.

A locale pack's words are written in this folder and reached through its choice of languages (`Locale.languages`, phase 3). Not here are the lists outside the per-word model, whole lists a stage reads rather than readings of a word: the Korean surname list, a segmentation list, in `nameparser/config/_ko_surnames.py` because the default lexicon reads it (`Lexicon.default().surnames`), and the lists a pack carries beside its module in `nameparser/locales/` (ZH's surnames in `zh.py`, ES's and ES_AR's given names in `_es_given_names.py` and `_es_ar_given_names.py`).
