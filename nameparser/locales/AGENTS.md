# Building a locale pack (nameparser/locales/)

Loaded when a session reads or edits anything under `nameparser/locales/`. It is the contract a pack shipped in nameparser itself meets, written for whoever builds one: the maintainers and their agents. A pack kept local to a caller's own code needs none of it (docs/locales.rst is the user guide to using and writing one), and someone proposing a pack opens an issue first (CONTRIBUTING.md, "Proposing a pack or another large change"). It was `docs/contributing.rst`'s "Contributing a pack to nameparser" until 2026-11-15.

The contract is checked mechanically by `tests/v2/test_locales.py`. It has three parts, in the order to work through them: decide whether the vocabulary belongs in a pack at all, declare what the pack changes, then test it.

## 1. Pack, or default vocabulary?

Decide which layer the vocabulary belongs in, if the pack carries any.

- **Self-selecting vocabulary is default-safe, and belongs in the default lexicon.** Self-selecting means able to match only text of the tradition it came from, the way a hangul surname can only ever match hangul. It goes in `nameparser/vocab/*.toml` (a segmentation surname list such as the Korean one, in `nameparser/config/_ko_surnames.py`, is read as `Lexicon.default().surnames`) rather than in a pack: a pack nobody knows to ask for is vocabulary nobody gets.
- **Vocabulary that declares a language its script does not belongs in the pack**, where asking for it is the declaration. A Chinese surname list silently mangles the Japanese names written in the same characters.
- **A word reading that is right in its language and wrong as a default** is written in that language's vocabulary file with `default = false` (`nameparser/vocab/README.md`, Properties), and the pack's `languages` turns it on; the pack module lists nothing (`nameparser/locales/hi.py`).
- **A pack with no list of its own ships an empty `Lexicon`** (`Lexicon.empty()`, as `nameparser/locales/ru.py` does); `nameparser/locales/zh.py` is the template for one that carries a list.

Curate vocabulary conservatively, the same rule as the user guide's "Words that are also ordinary names" (docs/customize.rst, label `ambiguous-words`): when you're unsure whether a word or a marker belongs, leave it out.

## 2. Declare what the pack changes

### The registry entry

Add a `"CODE": ("module.path", "ATTR")` row to `_REGISTRY` in `nameparser/locales/__init__.py`, so the pack loads lazily on first access: importing `nameparser.locales` never imports pack modules.

### The rules, as data

Write the rules the pack turns on as data, if they are `Policy` fields the vocabulary files' `[rules]` table lists. `nameparser/vocab/README.md`'s "Rules" section lists the keys, and `RULE_KEYS` in `tools/vocab/build.py` holds them.

1. Put the table in the pack's language file.
2. List the file in `PACK_RULES` in `tools/vocab/build.py`.
3. Rebuild (`uv run python tools/vocab/build.py`).
4. Give the pack `policy=rules_patch("<tag>")` from `nameparser._locale`, as `nameparser/locales/ru.py` does. `PACK_RULES` maps each file holding a table to the pack it is written for; a country pack may read its language's file without a row of its own (`nameparser/locales/es_ar.py` reads `es.toml`'s), so `git grep -l rules_patch -- 'nameparser/locales/*.py'` lists every pack that reads one. A country that turns a rule its language does not writes the table in its own file, which may hold nothing else (`pt-PT.toml`, read by `nameparser/locales/pt_pt.py`): no table rides along a tag's ancestors, so `pt.toml`, which holds none, leaves `locales.PT` as it was.

A rule the table does not list is a change to the parser, not to a pack.

### The deviations

Declare a module-level `DEVIATES(name)` predicate. Given a name string, `DEVIATES` returns whether *this pack alone* might parse it differently from the default parser.

- **Over-declaring is safe; under-declaring is not.** When in doubt, `DEVIATES` should say yes.
- **A pack whose scope is a script builds the predicate with `_script_matcher`** from `nameparser/_policy.py`, the way `nameparser/locales/zh.py` does, never by compiling its own character ranges. The factory's docstring explains how the pack-contract test enforces this.
- **A pack's choice of languages is never declared.** Its deviations are derived from the words the choice changes. So a pack that is nothing but a choice (`nameparser/locales/hi.py`) declares no `DEVIATES`: the contract test (`test_registry_is_the_pack_contract`) refuses one, and refuses a choice that changes no word.
- **A pack with a fragment or a patch beside its choice declares only what those change** (`nameparser/locales/cs.py`).

## 3. Test it

### A rotator list

Add a rotator list to `_ROTATORS` in `tests/v2/test_locales.py`. Every pack needs one, but what it has to contain follows from how the pack declares its scope:

- **By marker regex** (`ru`): at least one name exercising every alternation branch of every regex it defines. `test_rotators_cover_every_marker_branch` fails until each branch is hit.
- **By codepoint range** (`zh`): there are no branches to sweep, so the pack drops out of that test and its rotators carry the same weight by hand: the unspaced names the pack must split, one per shape of the vocabulary it ships (single surname, compound surname, and any spelling variant it means to cover).
- **By a choice of languages** (`hi`; a pack with a patch beside its choice too, as `cs`, and `ja`, whose choice turns on 君): a name for each word the choice changes, in each script it is written in and each position where the default reads it otherwise. `test_choice_rotators_cover_every_changed_word` fails until every word is held.
- **By a choice that changes no word, beside a patch that does** (`mn`, whose file's readings are all on by default): there is no word to hold. List the pack in the test file's `_INERT_CHOICES`, and its rotators cover what the patch moves.
- **With no vocabulary at all** (`ja`'s segmentation): list the shapes its *segmenter* must divide instead, and make the rotator tests skip when the optional dependency is absent, so the contract tests still run everywhere: probe for the dependency and build the pack's parser only when it is there, in `_packed_parsers`, which handles `ja` alone today (`_JA_AVAILABLE`), and `_require_packed` then skips a test whose pack has no parser.

### The non-interference gate

Keep the non-interference gate green over the shared corpus plus your rotators (`test_non_interference_each_pack`, `test_non_interference_all_packs_combined`): every name the packed parser parses differently from the default must be one your `DEVIATES` predicate flags, or one a word its choice changes stands in. No silent, undeclared side effects on names outside the pack's stated scope.

## One exemplar per shape

The shipped packs are the rows of `_REGISTRY` in `nameparser/locales/__init__.py`, and the files holding a `[rules]` table are the keys of `PACK_RULES` in `tools/vocab/build.py`, each with the pack it is written for. Read those for the roster; these are one worked example of each shape:

| Shape | Exemplar |
|---|---|
| Policy only, rules from a `[rules]` table, declared by marker regex | `nameparser/locales/ru.py` |
| Carries a vocabulary list, declared by codepoint range | `nameparser/locales/zh.py` |
| Its main contribution is turning a stage on (segmentation, through an optional dependency) | `nameparser/locales/ja.py` |
| Nothing but a choice of languages | `nameparser/locales/hi.py` |
| A choice of languages beside a `[rules]` table | `nameparser/locales/cs.py` |
| A choice that changes no word, beside a patch | `nameparser/locales/mn.py` |
| A fragment that takes readings out | `nameparser/locales/vi.py` |
| A country pack reading its language's `[rules]` table | `nameparser/locales/es_ar.py` |
| A country pack writing a `[rules]` table its language's file does not, sharing its list with another country's pack | `nameparser/locales/pt_pt.py` |
