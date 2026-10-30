# The vocabulary files

This folder holds the parser's default vocabulary: the titles, suffixes, particles, conjunctions, bound given names and maiden markers it recognizes, and the case of the words it capitalizes specially, written one word at a time. It is the place to edit when a word should be recognized, should stop being recognized, or should be recognized differently.

The parser never reads these files. `tools/vocab/build.py` compiles them into `nameparser/config/_compiled.py`, a committed module of sorted `frozenset` literals and one `dict` (`CAPITALIZATION_EXCEPTIONS`), and the `nameparser.config` modules re-export them under their public names (`TITLES`, `PARTICLES`, ...). Beside it the build writes a second committed module from the same readings, the reading index `nameparser/config/_index.py`, which keeps every reading with the tag of the file it is in and the properties the compiler reads, so that a choice of languages can compile from it later (3.0's phase 3), and a third, `nameparser/config/_rules.py`, holds the files' [rules](#rules) tables. So an edit here does nothing until you rebuild, and the tests fail, naming the command, when a committed module and the files disagree.

Why the model looks this way, and what each decision cost, is recorded in [decisions/vocabulary-model](../../docs/design/decisions/vocabulary-model.md). Where it is going (phases 2 to 4) is in [the vocabulary model RFC](../../docs/design/vocabulary-model-rfc.md).

## What a file means

A file is named for a BCP 47 language tag in canonical case: `fr.toml`, `pt-BR.toml`, `zh-Hant.toml`. It holds **the words the parser might meet in names written in that language**, which is what occurs in names and records written in it, including particles common there through immigration. It is not a list of words of that language's etymology.

Two tags are not languages:

- **`und`** (undetermined) holds the words no language file fits: `bon` and `dí`, particles of unrecorded origin until #766 refused their particle readings, now name readings and those exclusions (since 2026-10-20, when #751 finished what #749 and #750 began, giving every other word its languages). The comment at the top of the file says why they are there; a word whose language is found moves to that language's file.
- **`mul`** (multiple) holds words shared on purpose, such as the Roman numerals.

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

`duke` is deliberately not a title. It has no vocabulary reading at all, only its two name readings and an exclusion refusing the `nobility` reading with the reason. Anyone who adds `nobility = {}` to `duke` in any file gets a build error that quotes that reason. An exclusion means the reading is wrong wherever it is read. A reading that is right in its own language and wrong only as a default is written `default = false` instead ([Properties](#properties)), as `père` ("father", the French word for the Elder) is in `fr.toml`, so that choosing French turns it on; it was an exclusion until 3.0's phase 3c. Its son, `fils`, was an exclusion too until 2026-10-25, and is now on by default: its `generation` reading stands beside its `family` reading, which gates it by the name around it ([derived markers](#derived-markers)), so `Marie Fils` keeps her family name.

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
| `generation` | `suffix` | `SUFFIX_WORDS` |
| `agnomen` | `suffix` | `SUFFIX_WORDS`, `SUFFIX_WORDS_AMBIGUOUS`, `AGNOMENS` |
| `credential` | `suffix` | `SUFFIX_ACRONYMS` |
| `honorific` | `suffix` | `SUFFIX_WORDS` |
| `professional_honorific` | `suffix` | `SUFFIX_WORDS` |
| `status` | `suffix` | `SUFFIX_WORDS` |
| `courtesy` | `suffix` | `SUFFIX_WORDS` |
| `particle` | `particle` | `PARTICLES` |
| `preposition` | `particle` | `PARTICLES` |
| `article` | `particle` | `PARTICLES` |
| `patronymic` | `particle` | `PARTICLES` |
| `teknonymic` | `particle` | `PARTICLES` |
| `clan` | `particle` | `PARTICLES` |
| `rank` | `particle` | `PARTICLES` |
| `saint` | `particle` | `PARTICLES` |
| `alias` | `particle` | `PARTICLES` |
| `conjunction` | `conjunction` | `CONJUNCTIONS` |
| `bound_given` | `bound_given` | `BOUND_GIVEN_NAMES` |
| `birth_marker` | `relation` | `MAIDEN_MARKERS` |
| `given` | `name` | nothing |
| `family` | `name` | nothing |

A suffix reading goes to `SUFFIX_ACRONYMS` when its `acronym` property is true and to `SUFFIX_WORDS` otherwise; the column shows where each kind goes with `acronym` unwritten. A word has at most one suffix kind (check 4). A `given` reading carrying `same_as` goes to `GIVEN_NAME_ABBREVIATIONS`, a given name written short (see [Name readings](#name-readings)).

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
- `patronymic`: "son of" or "daughter of", where the word after it is a parent's name (`bin`, `binti`, `ibn`, `بن`, `בן`);
- `teknonymic`: "father of", naming the bearer by a child (`abu`, `أبو`);
- `clan`: a lineage prefix, where the word after it is a family name shared by the lineage rather than a parent's name (`mac`, `mc`, `ó`, `ní`, `آل`);
- `rank`: a former rank written inside the surname (`freiherr`, `freiherrin`);
- `saint`: "Saint" opening a surname (`san`, `santa`, `st`, `ste`);
- `alias`: a word joining two surnames of one person (`vel`).

Unlike the suffix kinds, one word may take a different particle kind in each language: `de` is a preposition in `fr.toml` and an article in `nl.toml`. Whether a particle may be given is the word's, not the reading's: its `given` reading, in any file, decides it for every particle reading (check 11). On a particle reading, `expands` is the word's meaning in that language, and `note` is reserved for vetting. A never-given particle may rest on its kind and `expands` alone: one attested bearer settles the may-be-given side, but no amount of searching settles absence, so what is recorded is what the word IS (an article, a preposition) rather than a failed search. And a word with a `given` reading whose particle readings carry no `note` in any file sits on the conservative default and nobody has examined it, and so does one whose note says so, as `heer`'s does: counts on the given reading were taken for phase 2's derivation (2026-10-25), not read against the particle position. The test is per word, because a word's note sits in one of its files, not in each: `mac` is examined though only `en.toml` holds its note.

**Classifying a category adds kinds to every check that tests it.** While a category has only its generic kind, a check that asks for the category and one that asks for the generic kind give the same answer, so a test row written in the generic kind cannot tell them apart. When a category gets its first fine kinds, give every check on that category a row in `tests/v2/test_vocab.py` written in a fine kind, and run each row against the check keyed on the kind to see it fail. #749's review found four particle checks pinned only on the generic `particle` kind once the shipped data used it for two words: the required `may_be_given`, an exclusion refusing a sibling kind, the bound given name that is a never-given particle, and the elided particle's two spellings. Each passed every test when keyed on the kind, which would have let a `preposition = {}` with no `may_be_given` compile silently into the never-given set.

The `name` kinds compile to nothing on their own. They record that a word is borne as a given or family name, with counts (see [Bearer counts](#bearer-counts)), as evidence for a reading or an exclusion, and a `given` or `family` reading beside an acronym reading, or a `given` reading beside a particle reading derives a marker (see [Derived markers](#derived-markers)), unless it is written `default = false`.

## Properties

A property is **behavioral** when it compiles into a set and so changes how names are parsed, **stated** when it compiles to nothing but the build holds it to the word's readings, and **descriptive** when it is checked and recorded but compiled to nothing, save `same_as` on a `given` reading, which compiles the word into `GIVEN_NAME_ABBREVIATIONS` (see [Name readings](#name-readings)). Each is allowed only on the categories listed; a `name` reading takes its own keys (see [Name readings](#name-readings)). Two of the sets are not properties at all but [derived markers](#derived-markers), read off a word's name readings.

| Property | Type | Applies to | Unwritten | Effect |
|---|---|---|---|---|
| `addresses` | behavioral | `title` | `"family"` | `"given"` adds the word to `GIVEN_NAME_TITLES`: `Sir John` reads `John` as the given name ([rules/H1](../../docs/design/rules/H1-title-and-one-name-word.md), a title and one name word) |
| `attaches` | behavioral | `title` | none | `TITLE_PHRASES`: the title kinds, or the title words, this word stands before in a title phrase, a list (`chief = { attaches = ["office", "military"] }`, `sergeant = { attaches = ["major"] }`, a word where a kind would reach too far), compiled into the two-word phrases it makes with each title word of those kinds and each word named (`chief justice`, `sergeant major`); a title that may be a given name on either side of one is a title there ([rules/H9](../../docs/design/rules/H9-title-phrase.md), the title phrase) |
| `after_given` | behavioral | `title` | false | `AFTER_GIVEN_TITLES`, on a `salutation` reading only: written bare at the end of the given part after a family comma, the word is the title, as in `Doe, Jane Mrs` ([rules/H8](../../docs/design/rules/H8-salutation-ending-the-given-part.md), a salutation ending the given part). A salutation borne as a given name or a surname is left out with an exclusion of the property, its counts beside it (`goodman`, `herr`), since a middle name may be either |
| `acronym` | behavioral | `suffix` | true for `credential`, false for every other kind | true: `SUFFIX_ACRONYMS`, matched with every period removed (`M.D.` is `md`); false: `SUFFIX_WORDS` |
| `attached` | behavioral | `suffix` | absent | `GLUED_HONORIFICS`, on a word reading only: `{ side = "after" }` splits the word off the end of a name token, as in `田中さん` ([rules/W2](../../docs/design/rules/W2-glued-honorific-peel.md), the glued-honorific peel) |
| `may_be_given` | stated | `particle` | none: required where the word has no `given` reading | `false` is required where the word has no `given` reading in any file, and that absence, not the property, is what puts the word in `NON_GIVEN_NAME_PARTICLES`: a particle opening the name starts the family name ([rules/P1](../../docs/design/rules/P1-lone-particle-fold.md), the lone particle fold). `true` is refused, naming the `given` reading to write instead (check 11) |
| `may_be_initial` | behavioral | `conjunction` | false | `CONJUNCTIONS_AMBIGUOUS`, on a cased single letter only: read as an initial in a name written in one case, as in `JOHN E SMITH` ([rules/P8](../../docs/design/rules/P8-single-letter-connective-against-the-initial-it-spells.md), a single-letter connective against the initial it spells) |
| `default` | behavioral | `title`, `suffix`, `particle`, `conjunction`, `bound_given`, `relation`, `name` | true | `false` keeps the reading out of every compiled set, `SUFFIX_WORDS` included for a generation: recorded and checked as a reading, for a pack to turn on in phase 3, where its writing offers the default no cue (`h`, Spanish *hijo*, written `H.`, exactly as an initial is). An exclusion does not refuse it, and it cannot read two ways beside the word's live readings (checks 4 to 6); a name reading beside it marks nothing. On a `given` or `family` reading (3.0's phase 3a) it derives no marker in the default, so the word's other readings compile as they would without it, until a pack turns the name on. It does not count as the name reading an agnomen on by default needs (check 11), and a particle whose word's only `given` readings are off is refused, which side of check 11 it takes being left to the first pack that needs one; a bound given name that is also a particle is refused with it, before check 9 would ask for its `given` reading. `true` is refused: it is what every reading is unwritten |
| `cased` | behavioral | `title`, `suffix`, `particle`, `conjunction`, `bound_given`, `relation` | the word as written | `CAPITALIZATION_EXCEPTIONS`: the case `capitalized()` gives the word (`PhD`), a mask over its letters and digits, never a replacement (#459) |
| `note` | descriptive | every category, a `name` reading included | | free text: why the reading is as it is |
| `issue` | descriptive | every category but `name` | | an issue number, or a list of them |
| `decided` | descriptive | every category but `name` | | a TOML date |
| `expands` | descriptive | every category but `name` | | the meaning the entry was added for, not every meaning |
| `same_as` | descriptive | every category | | another word of the same category that this one is a spelling of (`jnr` is `jr`); on a `given` reading, the full given name the word abbreviates, which compiles the word into `GIVEN_NAME_ABBREVIATIONS` (see [Name readings](#name-readings)) |
| `native` | descriptive | every category, a `name` reading included | | a native-script spelling |
| `gender` | descriptive | every category, a `name` reading included | | `"f"`, `"m"` or `"n"`, only where the word gives a definitive clue |

Two of these need more than their row:

- **`may_be_given` has no default.** The format before this one listed the never-given particles and treated every other particle as possibly a given name, so a new particle was ambiguous unless argued otherwise ([decisions/vocabulary-collisions](../../docs/design/decisions/vocabulary-collisions.md), C-i). A default here would pick one side of that silently, so the build refuses a particle reading that neither states `may_be_given = false` nor has a `given` reading on its word. When unsure, write the `given` reading, with a `note` if no source counts it.
- **`cased` belongs to the word**, not the reading: one mask per word, whichever reading carries it.

### Derived markers

Four sets mark a clash with a name, and all four are derived: a word is in one when it carries the clashing reading and a name reading on by default, in any of its files (check 11, since 2026-10-25, [decisions/vocabulary-model](../../docs/design/decisions/vocabulary-model.md)). Phase 1 wrote two of them as flags, `may_be_name` and `may_be_given = true`, which the build now refuses, naming the reading to write; the third, a suffix word that is also a name, arrived with phase 2h, and the fourth, a title that may be a given name, with phase 2i.

| Marker | Readings | Compiled into | Effect |
|---|---|---|---|
| possibly a name, a word | a `generation` or `agnomen` reading and a `given` or `family` reading; a name reading beside any other suffix word kind is refused (check 11), no gate reading that clash | `SUFFIX_WORDS_AMBIGUOUS` | a suffix word that is also a name (`fils`, `neto`) is read as a suffix only where the name has words to spare, as an ambiguous acronym is: `Alexandre Dumas fils` and `Pedro Alves Neto` end in a suffix, `Marie Fils` and `Ana Neto` in a family name, either way reported ([rules/S11](../../docs/design/rules/S11-suffix-word-that-is-also-a-name.md)). A generation's Title case in a name of mixed case leans it to the name, and its lower case settles it as the suffix wherever the name keeps a family word; an agnomen's writing settles nothing |
| possibly a name | an acronym `suffix` reading and a `given` or `family` reading | `SUFFIX_ACRONYMS_AMBIGUOUS` | an acronym that is also a name (`ma`) is read as a suffix only where its spelling or the name around it says so: `John Smith MA` and `John Smith M.A.` end in a suffix, `John Smith Ma` in a family name ([rules/S4](../../docs/design/rules/S4-ambiguous-acronym-needs-words-to-spare.md), the ambiguous acronym needs words to spare; [rules/S6](../../docs/design/rules/S6-case-signal-at-the-suffix-slot.md), the case signal at the suffix slot) |
| possibly a name, a title | a title reading and a `given` reading, on a word with no particle reading | `TITLES_AMBIGUOUS`, and kept out of `TITLES` | a title that may be a given name (`dean`, `justice`, `major`) is a title only inside a title phrase: after a modifier, a style or a title it stands behind in a phrase `attaches` makes, or before `of` or a title it attaches to. Elsewhere it is a name word, reported where it opens the name if a phrase `attaches` makes holds it (`grace`, held by none, is a title only behind a style or a modifier and reports nothing): `Dean of Students` and `Major General Smith` read the title, `Dean Smith` and `Mr Major Smith` the given name ([rules/H9](../../docs/design/rules/H9-title-phrase.md), the title phrase). A title that is also a particle (`st`, `freiherr`) is left to the particle rules, its `given` reading deriving the particle's marker alone. A salutation's given-name counts kept as evidence for `after_given` sit in the salutation reading's `note` (`mr`, `herr`), so they mark nothing |
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
| `same_as` | on a `given` reading only: the full given name the word abbreviates, normalized (`chas` is `charles`), which puts the word in `GIVEN_NAME_ABBREVIATIONS`: written with its period at the head of the part of the name that carries the given name, the word is that given name, where an unlisted abbreviation there is a title by its shape ([rules/H2](../../docs/design/rules/H2-leading-abbreviation-title.md), the leading-abbreviation title), so `Chas. Smith` reads given `Chas.`. Anywhere else the reading acts on nothing. A name is no word of the vocabulary, so this `same_as`, unlike a reading's, names no entry, and an entry holding only such a reading is not inert |

A name reading may stand without a count, as a particle kept possibly given under C-i's default with no source counting it does, but it then needs a `note` saying why it is declared (check 3). It may also be written `default = false`, the behavioral property in [Properties](#properties): recorded and checked, it derives no marker until a pack turns it on.

## Exclusions

An exclusion records that a reading was considered and refused, with the reason, so that the next person to propose it meets the reason as a build error instead of rediscovering the evidence. It means the reading is wrong in every language: a reading right in its own language and wrong only as a default, because another language collides with it, is written `default = false` instead ([Properties](#properties)), for a choice of that language to turn on, as cs `ml` is.

- **A refused reading** is a word-level table: `[word.excluded.generation]` with a `reason`, or `excluded = { generation = "the reason" }`. It refuses that kind in every file, and also every other kind that compiles into the same set, so a generic `suffix = {}` cannot put back a refused `generation`. A category name refuses the whole category (`excluded = { suffix = "..." }`). A `name` kind refuses only itself.
- **A refused property** sits on a reading the word keeps: `[word.honorific.excluded]` with `attached = "the reason"`. It refuses any value of that property other than the one it takes unwritten, on any reading of the category; a refused `cased`, which belongs to the word, on any reading of the word.

The value is a reason string, or a table with `reason` and optionally `issue`, `decided` and `note`. The exclusion goes in the file of the language whose reading it refuses. An entry may hold exclusions and no vocabulary reading, as `duke` does. An entry with no reading and no exclusion is refused as inert, and one holding only a name reading is a warning, which the test suite makes an error, unless that reading is a `given` reading carrying `same_as`, which compiles.

To see what has been refused, and why: `uv run python tools/vocab/query.py --excluded generation`.

## Bearer counts

Counts come from `tools/name_usage.py`, which reports how often a word is borne as a given name and as a family name in four name sources: 2010 US Census surnames (listed from 100 bearers), US Social Security given names (a name-sex pair is listed for a year from 5 births, reported per sex), Jörg Michael's nam_dict (a given-name frequency band per country, not a count) and Wikidata (live, with countries of citizenship, and a lower bound because many people have no name statement). For a word holding a Han, kana or hangul letter it adds a row of the Wikidata names that END in the word, which is the question for a glued honorific. With `--fetch-nppes` it also counts the US healthcare providers who write the word as a credential (NPPES), the other side of a suffix that is also a name; `--rank N` lists the commonest credentials with their name counts and how a comma name ending in each one parses. Its docstring says what each number can and cannot show.

Record a count on the word as a `given` or `family` reading, with the date you took it in `as_of`. A source's count is left out when it is below that source's floor, never written as 0. A suffix reading has no count field yet, so a credential count goes in the reading's `note`, with its date and source. Counts are provenance: they are the evidence a decision was made on, and nothing computes a reading from them. The reading itself is not inert where it clashes, as a `given` or `family` reading beside an acronym reading, or a `given` reading beside a particle reading does, marking the clash, so counts kept there as evidence AGAINST marking go in the clashing reading's `note` (`ld`).

## Adding a word

1. **Look up the word's other readings.** `uv run python tools/vocab/query.py --word <word>` lists every reading and exclusion of it in every file. An exclusion there is a decision already made; a reading in another category is a clash you are about to create, which is fine when position settles it (`do`) and needs an argument when it does not.
2. **Check it against real names, not memory.** `uv run python tools/name_usage.py <word>` gives the counts (add `--fetch-nppes` for a suffix, to see how often it is written as a credential), and [decisions/vocabulary-collisions](../../docs/design/decisions/vocabulary-collisions.md) is the criterion they are read against: a word that is a real name in the position the reading acts on needs a name reading with those counts, which marks the clash (see [Derived markers](#derived-markers)), or should stay out. `nameparser/vocab/AGENTS.md` lists the traps that have bitten before, filed under these steps.
3. **Check how it is written.** The entry's `text` is the folded spelling (`mbchb`), and `capitalized()` writes an acronym credential in capitals unless the word has a `cased` mask, so one that people write in mixed case (`MBChB`, `DPhil`, `ScD`) needs the mask: `cased = "MBChB"`. Nothing in the build can see this, since no source it reads records case. The ClinicalTrials.gov row of `name_usage.py` lists the spellings as typed ("written MBChB 1,442, MBCHB 72, MbChB 28"), once that local corpus is fetched (`uv run python tools/differential/local_corpora.py fetch ctgov-officials`). Where a mask would cost a name its rendering, refuse it instead, with the reason, as `edd` does (`'edd smith'` would render `'EdD Smith'`). #806 added twelve mixed-case credentials without their masks, and review caught it.
4. **Write the entry** in the file of the language whose names it occurs in (`und.toml` when that is not known), in its place in the [word order](#word-order), with what the checks found on it: `note`, `issue`, a dated name reading, a `cased` mask, or an `excluded` entry if you decided against it.
5. **Rebuild**: `uv run python tools/vocab/build.py`. It refuses what it can detect, naming the word and, where one file is at fault, the file, and rewrites `nameparser/config/_compiled.py`, `nameparser/config/_index.py` and `nameparser/config/_rules.py`. Commit the file and whichever modules it moved.
6. **Run the tests**: `uv run pytest tests/v2/test_vocab.py` for the build, then the full suite, and read what `tests/v2/test_snapshot.py` reports as moved (the root `AGENTS.md`, "Validating a new parsing rule"). `uv run python tools/differential/measure.py --base <checkout>` runs that check and the CLDR one against the branch's committed records, and every local-corpus check against the base checkout, in one command, writing one summary (`tools/differential/README.md`, "Measuring a change").

For a word whose reading acts on a name position, such as a title that is also a given name, `uv run python tools/vocab/word_report.py <word>... --base <checkout>` reads it both ways in one run: the word in a grid of shapes (a head, behind a title, after a family comma, after a full name and a comma, past a second comma, trailing with a period, inside a title phrase), each in three cases and under the three name orders, printing the rows the base reads differently; how the names in every fetched local corpus that open with the word, or open the part after the first comma with it, read it (title, given or other, counts only, with the corpora it could not read named); and `name_usage.py`'s rows. Without `--base` it prints every text, one line where the three orders agree and one block where the three cases read alike once lowercased; with it, what moved, folded the same way. `--rank` takes a list of words, the triage for a batch, which needs no change to the tree. It counts the corpus names that read each word as the title at either position, which holds real titles too, and beside them the `psc-individuals` filings opening with the word by the box the filer typed it into: the title box (a real title, what the move costs) and the forename box (a given name the title takes, what it gives back). The words are ordered by the forename box's count, printed beside its share of the two as a fraction (`164/165`), so a word three filers typed as a forename does not outrank one 164 did. On 2026-10-27 `sir` read as the title in 495 names but was filed 277 times as a title and 8 as a forename, while `sheikh`'s 13 title-box filings were the 13 agreement records #912 moved away from agreeing.

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

A rule is written only to turn it on: `name_order = "given-first"` and `two_family_names = false` are the defaults, and a pack's value overrides the caller's own, so the build refuses both rather than let a pack switch a caller's rule off. The files that hold a table are exactly the ones `PACK_RULES` in `tools/vocab/build.py` lists, each beside the pack that reads it (`tr.toml` is `locales.TR_AZ`'s, one file for Turkish and Azerbaijani, since there is no `az.toml`); a table in any other file is a build error, since nothing would read it, and so is a file listed there without one. Writing a `[rules]` table does not choose the file's vocabulary: that is the pack's `languages`, a separate field.

A rule KIND the table does not list (a compound given name, a married-name ending) is a change to the parser, not to a file: a new `Policy` field (with `ADDED_IN`), a row in `build.py`'s `RULE_KEYS` and in `_locale.py`'s `_RULE_VALUES`, and a mechanisms.md entry of its own for the rule kind (mechanisms.md#LOCALE-PACKS-PURE-DATA). `tests/v2/test_vocab.py` holds the two tables to each other and to `Policy`.

## Names reserved for later phases

These names will mean something in a later phase. Writing one now as a key, in a file, an entry or a reading, is a build error naming its phase, so nothing reads as working before it does.

| Name | Phase |
|---|---|
| `prefer` | 3 |
| `strict` | 3 |
| `bare_only` | 4 |
| `leading_only` | 4 |
| `trailing_only` | 4 |
| `separators` | 4 |

Phase 2 gave `default` and `attaches` their meaning (2026-10-25, see [Properties](#properties)). The gate's slots carry position and shape already settles a bare letter ([rules/P7](../../docs/design/rules/P7-one-letter-particle-against-the-initial-it-spells.md), a one-letter particle against the initial it spells), so `leading_only`, `trailing_only` and `bare_only` wait for phase 4's shapes, as `separators` waits for its glued words.

Two property values are refused for the same reason, with a message saying a later phase: `addresses = "full"` and `"any"`, and `attached` with a `side` other than `"after"`.

The locale packs' vocabulary (`nameparser/locales/`) and the Korean surname list (`nameparser/config/surnames.py`) are not in this folder: the surnames are a segmentation list, outside the per-word model, and the packs move here in phase 3.
