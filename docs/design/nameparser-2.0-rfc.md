# RFC: nameparser 2.0 — a new core API

Status: **open for feedback** — no deadline. Implementation may proceed
in parallel; this document will be amended (as commits to this PR) as
implementation teaches us things. Comment on specific lines here, or on
the discussion issue (#284) for general reactions.

## The short version, and the promise

nameparser 2.0 introduces a new, immutable core API and keeps the
existing one working:

```python
from nameparser import parse

name = parse("Dr. Juan Q. Xavier de la Vega III (Doc Vega)")
name.given        # "Juan"
name.family       # "de la Vega"
name.family_base  # "Vega"
name.title        # "Dr."
```

**The compatibility promise:** code that runs warning-free on nameparser
1.4 keeps running on every 2.x release, with identical results, getting
at most `DeprecationWarning`s. `HumanName` continues to exist as a
compatibility layer over the new core. The exceptions to "identical
results" are (a) parse-output changes that are deliberate bug fixes,
each documented in the release log with its issue, and (b) three narrow
edge cases listed in the Migration section. Removal of the old API
happens in 3.0, not 2.x, and only after warnings have named every
replacement.

If you only use `HumanName` and never customize configuration, 2.0
should be a non-event for you. The rest of this document is for
everyone else — and for anyone who wants to push on the new design
while it is still cheap to change.

## Why a new core

Fifteen years of issues point at the same architectural limits:

- **`HumanName` is four things in one mutable class** — parser, state,
  vocabulary predicates, and formatter. Every feature grows all four at
  once (it is currently ~1,600 lines), and mutation semantics are
  inconsistent: assigning `full_name` re-parses, assigning `last` does
  not, `capitalize()` mutates in place.
- **Parse state is `list[str]`**, so position information is lost and
  re-derived by value lookups. That is the structural root cause of a
  whole family of prefix-join bugs (#100 and relatives): when the same
  string appears twice, the lookup answers the wrong question.
- **Configuration is a shared mutable module global** (`CONSTANTS`).
  Most of `nameparser.config`'s ~850 lines exist to make shared
  mutation survivable (custom set managers, descriptors, cache
  invalidation), and it still causes test pollution and cross-thread
  surprises.
- **Equality is broken by design** (#223): case-insensitive equality,
  equality with plain strings, and hashability are mutually
  inconsistent promises. 1.3.0 deprecated `==`/`hash()` and shipped
  `matches()`/`comparison_key()`.
- **The roadmap needs structure v1 can't cheaply provide**: family-first
  name order (#270), per-dataset configuration without global mutation,
  and honest reporting of genuinely ambiguous parses.

The rules-based approach is not changing. nameparser's niche is
deterministic, auditable, zero-dependency parsing — the same input
always parses the same way. The rewrite reorganizes *how the rules run*,
not what the library is.

## The new API

### Parsing produces an immutable value

`parse()` returns a `ParsedName`: a frozen dataclass. There is no
mutation anywhere in the new API — editing is `replace()`, which
returns a new value:

```python
name = parse("John Smith")
name2 = name.replace(given="Jane")   # new object; `name` unchanged
```

`parse()` is **total over `str`**: any string — empty, emoji,
garbage — returns a `ParsedName` rather than raising. Content problems
are represented in the result; the only exceptions are type errors
(`bytes` raises `TypeError` — decode first).

Equality is strict structural equality, and the semantic comparisons
are explicit and separate — `comparison_key()` for dedup/sorting and
`matches()` for component-wise case-insensitive comparison — resolving
the #223 trilemma by not conflating the three meanings of "equal".

### Two access layers: strings for the 95% case, tokens for the rest

The string properties behave like v1's: always `str`, `""` when empty.
Underneath, `ParsedName` carries the actual parse: a tuple of `Token`s,
each with its **span** (position in the original string), its role, and
tags recording *how it was classified*:

```python
name = parse("Juan de la Vega")
name.tokens_for(Role.FAMILY)
# (Token('de' @5:7 FAMILY {particle}),
#  Token('la' @8:10 FAMILY {particle}),
#  Token('Vega' @11:15 FAMILY),)
```

This is the structural fix for the value-lookup bug family: pipeline
stages address tokens by index, so "which 'de' did you mean?" cannot
arise. It is also the debuggability story — "why is 'Van' in my family
name?" is answered by the token's tags, and `repr(name)` prints a
compact component-per-line breakdown like v1's.

Derived views (`family_base`, `family_particles`, `surnames`,
`given_names`) are pure filters over tokens — they can never disagree
with the parse.

### `given` and `family`, not `first` and `last`

The v1 field names describe Western *position* — they date from before
the parser even supported comma formats, when position was all there
was. They read wrongly the moment name order varies: under family-first
order, `name.last` would return the first word. 2.0 adopts the names
the standards world already uses (HTML autocomplete
`given-name`/`family-name`, vCard, Unicode CLDR):

- `first` → `given`, `last` → `family`
- `last_base`/`last_prefixes` → `family_base`/`family_particles`
- config: `prefixes` → `particles` (every web standard uses "prefix"
  for honorifics like "Mr." — v1's usage collides; the linguistics term
  for van/de la is *particle*)
- `title` and `suffix` **stay** — they have ecosystem gravity, and the
  positional taxonomy ("pre-nominal"/"post-nominal") is documented
  rather than spelled into identifiers.

`HumanName` keeps every v1 spelling, including `string_format` keys, so
existing code is unaffected; only new-API adopters see the new names.

### Configuration: `Lexicon` (vocabulary) and `Policy` (behavior)

v1's `Constants` mixes three kinds of thing; 2.0 splits them by what
varies together:

- **`Lexicon`** — vocabulary data (titles, suffixes, particles,
  conjunctions, …). Immutable; composable by union; varies by
  *language*.
- **`Policy`** — behavior switches (`name_order`, patronymic rules,
  delimiter pairs, …). Immutable; varies by *data source*.
- **Rendering parameters** — `string_format`, initials style,
  capitalization — move to render-time arguments; they vary by *output
  destination* and are no longer configuration at all.

```python
from nameparser import Parser, Lexicon, Policy, FAMILY_FIRST

parser = Parser(
    lexicon=Lexicon.default().add(titles={"dra"}),
    policy=Policy(name_order=FAMILY_FIRST),
)
parser.parse("Wang Xiuying").family   # "Wang"
```

A `Parser` is immutable, thread-safe, and does all its compilation once
at construction — build it at startup, share it everywhere. There is no
shared mutable configuration in the new API, which retires the entire
test-pollution/config-war problem class. `name_order` is an order-spec
tuple (`FAMILY_FIRST = (Role.FAMILY, Role.GIVEN, Role.MIDDLE)`) rather
than a boolean, because Vietnamese order — family, middle, *then*
given — needs a third arrangement (#270).

### Honesty about ambiguity

Some parses are genuinely undecidable by rules — "Kelly Michael" could
be either order; in "Van Johnson", "Van" is a Dutch particle *and* a
common given name. v1 silently picks a reading. 2.0 picks the same
reading **and says so**:

```python
parse("Van Johnson").ambiguities
# (Ambiguity(PARTICLE_OR_GIVEN, "leading 'van' can be a particle or a
#   given name; chose given", tokens=(...)),)
```

`Ambiguity.kind` values are stable API you can filter on. This is also
groundwork: a future `parse_all()` returning ranked alternative
readings, and `explain()` returning a stage-by-stage parse trace, are
designed for (the pipeline supports both) but deliberately not in 2.0.

### Locales: opt-in packs, never auto-detection

Language-specific behavior cannot be auto-detected — "Tham Jun Hoe" is
token-for-token indistinguishable from a Western three-token name, and
"Ali" is Arabic or Italian. So locale support is explicit:

```python
from nameparser import parser_for, locales

parser_for(locales.RU).parse("Ivanova Anna Sergeevna").given   # "Anna"
```

A locale pack is pure data: a vocabulary fragment plus a partial policy
patch, folded in at parser construction. 2.0.0 ships `RU` and `TR_AZ`
(formalizing the patronymic support added in 1.3.0); Chinese/Korean
(bundled surname lists + segmentation of unspaced input), Vietnamese,
and Japanese (via a `nameparser[ja]` extra with a pluggable segmenter)
are designed and staged for 2.x minors. Vocabulary that cannot misfire
on other languages' names (e.g. Cyrillic honorifics) goes in the
default lexicon instead of packs.

## Migration: what actually happens to existing code

**`HumanName` in 2.0** is a wrapper over the new core with v1's exact
mutation semantics, field spellings, and formatting attributes. The v1
test suite runs against it as the compatibility gate. v1 pickles load
throughout 2.x.

**`CONSTANTS` keeps working** — mutations are honored exactly (the
facade rebuilds its config snapshot when the shared config changes) and
emit a `DeprecationWarning` pointing at the replacements. Mutating a
*private* `Constants` instance does not warn.

**Already-scheduled removals land as warned** (every one was deprecated
in 1.3.0 or 1.4 first): `==`/`hash()`, bytes input, slice item access,
`empty_attribute_default`, `constants=None`, silent config-typo
fallbacks, legacy pickle blobs, `add_with_encoding()`. Python floor
becomes 3.11; the last dependency is dropped.

**The three narrow behavior exceptions** (everything else identical):

1. `*_list` attributes return snapshots — in-place
   `name.first_list.append(...)` no longer mutates parse state
   (assignment still does).
2. Subclasses overriding parsing hooks (`parse_pieces`, `is_title`, …)
   are detected and warned at construction: the facade delegates to the
   new core, so such overrides are no longer called (#280). If you do
   this, we want to hear what your override does — that is a feature
   request we would rather absorb than break.
3. Assigning to `CONSTANTS.regexes` raises with a pointer to the named
   `Policy` flag that replaces it. Custom regex injection has no
   equivalent in the new model; nothing is silently ignored.

**Timeline:** 2.0.0's only *new* warning is on shared-`CONSTANTS`
mutation. A warning on `HumanName` construction itself comes in a later
2.x minor, once the new API has proven out — and 3.0 (which removes the
facade) does not ship before that warning has been out in a release.

## Alternatives considered and rejected

- **Auto-detecting name language/order** — impossible in principle, not
  just hard; see the Locales section.
- **A statistical/ML core** — determinism and auditability are the
  point of this library; the token/ambiguity model leaves room for
  optional escalation later without changing the core.
- **Keeping `first`/`last`** — see the naming section; the facade keeps
  them for v1 code, which serves the familiarity constituency without
  wiring position-based names into the new API.
- **A boolean `family_name_first`** — cannot express Vietnamese; the
  order-spec tuple can (#270).
- **Renaming `title`/`suffix` to `pre_nominal`/`post_nominal`** — more
  precise, but no ecosystem uses those as field names; precision lives
  in the docs instead.
- **Vocabulary entries as records with per-word metadata** — rejected
  under "no vocabulary data without a consuming rule": a flag the
  parser doesn't read is a promise it doesn't keep. Cross-category
  words are handled by dual set membership (closed classes) or the two
  `_ambiguous` sets (closed-vs-open), each of which has a consuming
  rule.
- **A user-replaceable regex escape hatch** — replaced by named policy
  flags; anything not expressible through them is a feature request we
  want to see.

## Feedback we are specifically looking for

No deadline — comment whenever, on lines here or on the discussion
issue. The questions where answers would most change things:

1. **Do you compare `HumanName` objects with `==` (especially against
   plain strings), or use them in sets/dicts?** 2.0 changes this to
   object identity (warned since 1.3.0; `matches()`/`comparison_key()`
   are the replacements). This is the one silent behavior change in the
   release.
2. **Do you subclass `HumanName` and override parsing methods?** Tell
   us what your override accomplishes — we would rather absorb it as a
   feature than break it silently (#280).
3. **Do you mutate `CONSTANTS` after startup** (not just at import
   time)? Anything beyond startup-time customization we should know
   about?
4. **Do you assign custom regexes to `CONSTANTS.regexes`?** What for?
   Each real use case either becomes a named policy flag or stays
   broken — we would like the list to be complete before 2.0.
5. **`given`/`family` instead of `first`/`last`** in the new API: does
   this help or annoy you?
6. **Is there anything you build on top of nameparser** (wrappers,
   pipelines) where the compatibility promise as stated would still
   break you?
