# The vocabulary files

This folder holds the parser's default vocabulary: the titles, suffixes, particles, conjunctions, bound given names and maiden markers it recognizes, and the case of the words it capitalizes specially, written one word at a time. It is the place to edit when a word should be recognized, should stop being recognized, or should be recognized differently.

The parser never reads these files. `tools/vocab/build.py` compiles them into `nameparser/config/_compiled.py`, a committed module of sorted `frozenset` literals and one `dict` (`CAPITALIZATION_EXCEPTIONS`), and the `nameparser.config` modules re-export them under their public names (`TITLES`, `PARTICLES`, ...). So an edit here does nothing until you rebuild, and `tests/v2/test_vocab.py` fails, naming the command, when the committed module and the files disagree.

Why the model looks this way, and what each decision cost, is recorded in [decisions/vocabulary-model](../../docs/design/decisions/vocabulary-model.md). Where it is going (phases 2 to 4) is in [the vocabulary model RFC](../../docs/design/vocabulary-model-rfc.md).

## What a file means

A file is named for a BCP 47 language tag in canonical case: `fr.toml`, `pt-BR.toml`, `zh-Hant.toml`. It holds **the words the parser might meet in names written in that language**, which is what occurs in names and records written in it, including particles common there through immigration. It is not a list of words of that language's etymology.

Two tags are not languages:

- **`und`** (undetermined) holds the words not yet assigned a language. Most of the vocabulary is still here (1,544 of 1,784 entries on 2026-10-19), converted mechanically from the Python lists it used to be; assigning a word to a language means moving its entry to that language's file. The comments above an entry here are the vetting notes that stood above the word in the Python module, in their old order; classifying a category is what turns them into fields.
- **`mul`** (multiple) holds words shared on purpose, such as the Roman numerals.

The script is read from the word, not from the file: `sr.toml` holds `mlađi` and `млађи` side by side. A script subtag (`zh-Hant`) is for a difference the text cannot show.

The default vocabulary loads every file, so which file a word is in changes nothing about how a name is parsed today. A word may be in more than one file; check 5 of the build makes each category of it read the same in every file, every behavioral property agreeing whatever kind each file gives it.

## How an entry is built

Each file has `schema = 1` at the top, then one `[[word]]` table per word. An entry has a `text` and its **readings**: what the word can be read as, each keyed by its kind and each a table, even when empty.

```toml
[[word]]
text = "van"
[word.preposition]
may_be_given = true
expands = "of, from"
note = "Vietnamese Văn, and Van Johnson -- the canonical particle-or-given ambiguity this whole flag exists for"
```

`van`, in `nl.toml`, has one reading, a particle of the kind `preposition`, with one behavioral property (`may_be_given`: the word is also a given name, so `van Gogh` keeps `van` as the given name and reports the fork) and two descriptive ones (`expands` and `note`, compiled to nothing).

```toml
[[word]]
text = "do"
credential = { may_be_name = true, expands = "Doctor of Osteopathic Medicine" }
```

```toml
[[word]]
text = "do"
[word.preposition]
may_be_given = true
expands = "of the, masc. sg."
note = "Vietnamese Đỗ leads a great many surnames"
```

`do` has two readings in two categories, a credential (still in `und.toml`) and a particle (a Portuguese preposition, in `pt.toml`), so it is in both `SUFFIX_ACRONYMS` and `PARTICLES`; which one applies is decided by where the word stands. A word's readings are where clashes between categories are recorded: before this format, such a clash was visible only as two sets that happened to overlap.

```toml
[[word]]
text = "fils"
family = { us_census_2010 = 767, wikidata = 5, as_of = 2026-10-16 }
[word.excluded.generation]
reason = "pack-shaped: Marie Fils, 767 US Census bearers of Fils"
issue = [679, 684]
```

`fils` ("son", the French generational word) is deliberately not a suffix. It has no vocabulary reading at all: a `family` reading recording the counts that kept it out, and an exclusion refusing the `generation` reading with the reason. Anyone who adds `generation = {}` to `fils` in any file gets a build error that quotes that reason.

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

Every file but `und.toml` lists its words in one order, and the build refuses a file that does not (check 10), naming the entry and the word it belongs after:

1. **By kind**, in the order of the table under [Kinds](#kinds), which lists the categories in turn and each category's kinds together. A word with several readings sorts under its first kind in that order. A word whose only vocabulary reading is a refusal (`fils`, `senior`) sorts under the kind it refuses, a refused category counting as its first kind, and a name reading places a word only when it has nothing else.
2. **Then by the word it is a spelling of**: a reading's `same_as`, or the word's own text when it has none. A head comes first and its spellings follow it, so `jr` is followed by `jnr` and `junior`, and `sr` by `snr`. A spelling that has spellings of its own heads a group inside its head's: in `ar.toml`, `el-` follows the other spellings of `al-` with its own assimilated forms after it.
3. **Then by the word's text.**

Text is compared by codepoint. The texts are already normalized, so this is the order of the normalized text, whatever the script: Latin before Cyrillic before Arabic, and within a script an accented letter after `z` (`aḍ-` follows `az-`). It is defined for every script and the same on every machine, and it is no one language's collation. A traditional and a simplified spelling with no `same_as` between them sort apart (`課長` and `课长` in `zh.toml`).

The build checks the order and never rewrites a file, because a comment above an entry belongs to it and must move with it, which a TOML reader cannot see. When the build says an entry belongs somewhere else, move it with its comment.

`und.toml` is exempt. Its entries keep the order of the Python lists they were converted from, and its vetting comments still point at their neighbours ("the bare-κ trap above"); a word leaving it for a language file takes its place in that file's order.

## Kinds

A reading's key is its **kind**. The table lists the kinds in their canonical order, which is the [word order](#word-order)'s first key and `CATEGORY`'s order in `tools/vocab/build.py`. Each kind belongs to one **category**, and the category decides which compiled set the reading feeds. For title, suffix, particle and conjunction the category's own name is also a kind (`title = {}`: a title not yet classified), so classifying a word later is a data edit that moves no compiled set. The one exception: a generic `suffix = {}` classified as `credential` moves from `SUFFIX_WORDS` to `SUFFIX_ACRONYMS`, because a credential's `acronym` is true unwritten; write `acronym = false` to keep it where it was. The suffix and particle categories are classified (two particles of unrecorded origin, `bon` and `dí`, keep the generic kind in `und.toml`); the others carry their generic kind.

| Kind | Category | Compiled into |
|---|---|---|
| `title` | `title` | `TITLES` |
| `suffix` | `suffix` | `SUFFIX_WORDS` |
| `generation` | `suffix` | `SUFFIX_WORDS` |
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

A suffix reading goes to `SUFFIX_ACRONYMS` when its `acronym` property is true and to `SUFFIX_WORDS` otherwise; the column shows where each kind goes with `acronym` unwritten. A word has at most one suffix kind (check 4).

The particle kinds say what the word does in the names of the file's language:

- `preposition`: "of", "from", "at", alone or contracted with the article after it (`de`, `van`, `von`, `du`, `del`, `vom`, `ter`);
- `article`: a definite article standing alone or elided (`la`, `der`, `het`, `'t`, `l'`, the Arabic `al-` and its assimilated spellings);
- `patronymic`: "son of" or "daughter of", where the word after it is a parent's name (`bin`, `binti`, `ibn`, `بن`, `בן`);
- `teknonymic`: "father of", naming the bearer by a child (`abu`, `أبو`);
- `clan`: a lineage prefix, where the word after it is a family name shared by the lineage rather than a parent's name (`mac`, `mc`, `ó`, `ní`, `آل`);
- `rank`: a former rank written inside the surname (`freiherr`, `heer`);
- `saint`: "Saint" opening a surname (`san`, `santa`, `st`, `ste`);
- `alias`: a word joining two surnames of one person (`vel`).

Unlike the suffix kinds, one word may take a different particle kind in each language: `de` is a preposition in `fr.toml` and an article in `nl.toml`. Check 5 holds every particle reading of a word to the same `may_be_given` whatever its kind. On a particle reading, `expands` is the word's meaning in that language, and `note` is reserved for vetting. A never-given particle may rest on its kind and `expands` alone: one attested bearer settles the may-be-given side, but no amount of searching settles absence, so what is recorded is what the word IS (an article, a preposition) rather than a failed search. And a word with `may_be_given = true` whose particle readings carry no `note` in any file sits on the conservative default and nobody has examined it, and so does one whose note says so, as `heer`'s does. The test is per word, because a word's note sits in one of its files, not in each: `mac` is examined though only `en.toml` holds its note.

**Classifying a category adds kinds to every check that tests it.** While a category has only its generic kind, a check that asks for the category and one that asks for the generic kind give the same answer, so a test row written in the generic kind cannot tell them apart. When a category gets its first fine kinds, give every check on that category a row in `tests/v2/test_vocab.py` written in a fine kind, and run each row against the check keyed on the kind to see it fail. #749's review found four particle checks pinned only on the generic `particle` kind once the shipped data used it for two words: the required `may_be_given`, an exclusion refusing a sibling kind, the bound given name that is a never-given particle, and the elided particle's two spellings. Each passed every test when keyed on the kind, which would have let a `preposition = {}` with no `may_be_given` compile silently into the never-given set.

The `name` kinds compile to nothing. They record that a word is borne as a given or family name, with counts (see [Bearer counts](#bearer-counts)), as evidence for a reading or an exclusion.

## Properties

A property is **behavioral** when it compiles into a set and so changes how names are parsed, and **descriptive** when it is checked and recorded but compiled to nothing. Each is allowed only on the categories listed; a `name` reading takes its own keys (see [Name readings](#name-readings)).

| Property | Type | Applies to | Unwritten | Effect |
|---|---|---|---|---|
| `addresses` | behavioral | `title` | `"family"` | `"given"` adds the word to `GIVEN_NAME_TITLES`: `Sir John` reads `John` as the given name ([rules/H1](../../docs/design/rules/H1-title-and-one-name-word.md), a title and one name word) |
| `acronym` | behavioral | `suffix` | true for `credential`, false for every other kind | true: `SUFFIX_ACRONYMS`, matched with every period removed (`M.D.` is `md`); false: `SUFFIX_WORDS` |
| `may_be_name` | behavioral | `suffix` | false | `SUFFIX_ACRONYMS_AMBIGUOUS`, on an acronym reading only: an acronym that is also a name (`ma`) is read as a suffix only where its spelling or the name around it says so: `John Smith MA` and `John Smith M.A.` end in a suffix, `John Smith Ma` in a family name ([rules/S4](../../docs/design/rules/S4-ambiguous-acronym-needs-words-to-spare.md), the ambiguous acronym needs words to spare; [rules/S6](../../docs/design/rules/S6-case-signal-at-the-suffix-slot.md), the case signal at the suffix slot) |
| `attached` | behavioral | `suffix` | absent | `GLUED_HONORIFICS`, on a word reading only: `{ side = "after" }` splits the word off the end of a name token, as in `田中さん` ([rules/W2](../../docs/design/rules/W2-glued-honorific-peel.md), the glued-honorific peel) |
| `may_be_given` | behavioral | `particle` | none: required | `NON_GIVEN_NAME_PARTICLES` when false: a particle opening the name starts the family name ([rules/P1](../../docs/design/rules/P1-lone-particle-fold.md), the lone particle fold) |
| `may_be_initial` | behavioral | `conjunction` | false | `CONJUNCTIONS_AMBIGUOUS`, on a cased single letter only: read as an initial in a name written in one case, as in `JOHN E SMITH` ([rules/P8](../../docs/design/rules/P8-single-letter-connective-against-the-initial-it-spells.md), a single-letter connective against the initial it spells) |
| `cased` | behavioral | `title`, `suffix`, `particle`, `conjunction`, `bound_given`, `relation` | the word as written | `CAPITALIZATION_EXCEPTIONS`: the case `capitalized()` gives the word (`PhD`), a mask over its letters and digits, never a replacement (#459) |
| `note` | descriptive | every category, a `name` reading included | | free text: why the reading is as it is |
| `issue` | descriptive | every category but `name` | | an issue number, or a list of them |
| `decided` | descriptive | every category but `name` | | a TOML date |
| `expands` | descriptive | every category but `name` | | the meaning the entry was added for, not every meaning |
| `same_as` | descriptive | every category but `name` | | another word of the same category that this one is a spelling of (`jnr` is `jr`) |
| `native` | descriptive | every category, a `name` reading included | | a native-script spelling |
| `gender` | descriptive | every category, a `name` reading included | | `"f"`, `"m"` or `"n"`, only where the word gives a definitive clue |

Two of these need more than their row:

- **`may_be_given` has no default.** The format before this one listed the never-given particles and treated every other particle as possibly a given name, so a new particle was ambiguous unless argued otherwise ([decisions/vocabulary-collisions](../../docs/design/decisions/vocabulary-collisions.md), C-i). A default here would pick one side of that silently, so the build refuses a particle reading that does not state it. When unsure, write `true`.
- **`cased` belongs to the word**, not the reading: one mask per word, whichever reading carries it.

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

## Exclusions

An exclusion records that a reading was considered and refused, with the reason, so that the next person to propose it meets the reason as a build error instead of rediscovering the evidence.

- **A refused reading** is a word-level table: `[word.excluded.generation]` with a `reason`, or `excluded = { generation = "the reason" }`. It refuses that kind in every file, and also every other kind that compiles into the same set, so a generic `suffix = {}` cannot put back a refused `generation`. A category name refuses the whole category (`excluded = { suffix = "..." }`). A `name` kind refuses only itself.
- **A refused property** sits on a reading the word keeps: `[word.honorific.excluded]` with `attached = "the reason"`. It refuses any value of that property other than the one it takes unwritten, on any reading of the category; a refused `cased`, which belongs to the word, on any reading of the word.

The value is a reason string, or a table with `reason` and optionally `issue`, `decided` and `note`. The exclusion goes in the file of the language whose reading it refuses. An entry may hold exclusions and no vocabulary reading, as `fils` does. An entry with no reading and no exclusion is refused as inert, and one holding only a name reading is a warning, which the test suite makes an error.

To see what has been refused, and why: `uv run python tools/vocab/query.py --excluded generation`.

## Bearer counts

Counts come from `tools/name_usage.py`, which reports how often a word is borne as a given name and as a family name in three sources: 2010 US Census surnames (listed from 100 bearers), US Social Security given names (a name-sex pair is listed for a year from 5 births, reported per sex) and Wikidata (live, with countries of citizenship, and a lower bound because many people have no name statement). For a word holding a Han, kana or hangul letter it adds a fourth row, the Wikidata names that END in the word, which is the question for a glued honorific. Its docstring says what each number can and cannot show.

Record a count on the word as a `given` or `family` reading, with the date you took it in `as_of`. A source's count is left out when it is below that source's floor, never written as 0. Counts are provenance: they are the evidence a decision was made on, and nothing computes a reading from them.

## Adding a word

1. **Look up the word's other readings.** `uv run python tools/vocab/query.py --word <word>` lists every reading and exclusion of it in every file. An exclusion there is a decision already made; a reading in another category is a clash you are about to create, which is fine when position settles it (`do`) and needs an argument when it does not.
2. **Check it against real names, not memory.** `uv run python tools/name_usage.py <word>` gives the counts, and [decisions/vocabulary-collisions](../../docs/design/decisions/vocabulary-collisions.md) is the criterion they are read against: a word that is a real name in the position the reading acts on needs the matching flag (`may_be_given`, `may_be_name`) or should stay out. The root `AGENTS.md`'s "Adding a word to the vocabulary" lists the traps that have bitten before.
3. **Write the entry** in the file of the language whose names it occurs in (`und.toml` when that is not known), in its place in the [word order](#word-order), with what the check found on it: `note`, `issue`, a dated name reading, or an `excluded` entry if you decided against it.
4. **Rebuild**: `uv run python tools/vocab/build.py`. It refuses what it can detect, naming the word and, where one file is at fault, the file, and rewrites `nameparser/config/_compiled.py`. Commit both.
5. **Run the tests**: `uv run pytest tests/v2/test_vocab.py` for the build, then the full suite, and read what `tests/v2/test_snapshot.py` reports as moved (the root `AGENTS.md`, "Validating a new parsing rule").

`uv run python tools/vocab/build.py --check` exits 1 when the committed module is stale and 2 when a file fails a check. The checks themselves are numbered in `build.py`'s docstring.

## Names reserved for later phases

These names will mean something in a later phase. Writing one now as a key, in a file, an entry or a reading, is a build error naming its phase, so nothing reads as working before it does.

| Name | Phase |
|---|---|
| `bare_only` | 2 |
| `leading_only` | 2 |
| `trailing_only` | 2 |
| `attaches` | 2 |
| `separators` | 2 |
| `default` | 3 |
| `prefer` | 3 |
| `strict` | 3 |

Two property values are refused for the same reason, with a message saying a later phase: `addresses = "full"` and `"any"`, and `attached` with a `side` other than `"after"`.

The locale packs' vocabulary (`nameparser/locales/`) and the Korean surname list (`nameparser/config/surnames.py`) are not in this folder: the surnames are a segmentation list, outside the per-word model, and the packs move here in phase 3.
