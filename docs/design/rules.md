# Parsing rules

This document is NORMATIVE, not descriptive: the rules state how
names are written and what should happen when they are parsed,
grounded in how people understand names — not in what the parser
currently does. The parser implements these rules. Where it does not
yet, the gap is a tracked deviation (`deviates:` marker below), not a
counterexample. Statements are implementation-free: no stage names,
no function names, no regexes.

Authority, scoped: `tests/v2/cases.py` pins CURRENT behavior; this
document states INTENDED behavior. A mismatch between them must be
classified, never defaulted: either the rule is wrong (fix it here)
or the parser is wrong (the example takes a `deviates:` marker and an
issue). Where this document is silent, the behavior is
pinned-but-undocumented — an extraction gap to close, not a
specification, and not license to change the behavior.

Rule IDs are stable forever: never renumbered, never reused. A
retired rule keeps its ID with a one-line tombstone pointing at
decisions.md. Cross-references use the anchor form `decisions.md#P2`
/ `mechanisms.md#SPANS`; a bare ID is never a citation. The
`interacts:` field on a pointer line is advisory — the
citation-integrity test checks the ID exists, not that the
interaction is real.

Every example line is EXECUTABLE. The grammar (its executable
definition is `tests/v2/rules_doc.py`; `tests/v2/test_rules_doc.py`
runs every line):

    "INPUT" [annotation] →  field="value"  [· boundary]
                            [deviates: #N (today: field="value")]

An `annotation` names a policy, locale (`[ru]`), or extras gate
(`[ja+segmenter]`) in the registry beside the test. `· boundary`
marks the non-firing example every rule must carry — or the rule
declares `no-boundary: <reason>` instead, so skipping the boundary is
a recorded decision. `deviates:` states the INTENDED output on the
example line while the marker records TODAY's output and the tracking
issue; the runner asserts today's output strictly, so a parser change
that closes the gap fails the suite until the marker is removed in
the same PR. `grep deviates:` on this file is the deviation backlog
(deviations from statable rules — coverage gaps are a separate,
larger category no grep can see).

## Not in scope

- **Language detection.** The parser never infers a language from
  Latin-script text: transliteration destroys the signal ("Ali",
  "Van", "Bin" each belong to several languages with conflicting
  readings). Language-specific behavior is opt-in configuration.
  Script-conditional behavior exists only where the script itself
  settles the convention (see the W section).
- **Grammatical inflection.** Names inflect in many languages
  (vocative, genitive); this library neither produces nor consumes
  inflected forms. CLDR personNames draws the same line.
- **Validation.** Deciding whether a string IS a person's name is not
  parsing; `parse()` is total over strings and never rejects input.

## Titles & honorifics (H)

Background: an honorific title precedes a name and is not itself part
of it; it addresses or ranks the person. Most titles address by
surname ("Mr. Johnson"), but a few — knighthoods, some clerical and
courtesy titles — address by given name ("Sir John"). The library
keeps a vocabulary of titles and, separately, of these given-name
titles.

H1. Rationale: a title normally addresses by surname, so a title
    followed by a single name word usually names the family; but a
    given-name title addresses by given name.
    A title followed by exactly one name word and nothing else makes
    that word the family name, unless the title is a given-name
    title, which keeps it the given name.
      "Mr. Johnson"               →  family="Johnson"
      "Mrs. Garcia"               →  family="Garcia"
      "Sir John"                  →  given="John"  · boundary
    implemented: nameparser/_pipeline/_post_rules.py

## Particles & surname prefixes (P)

Background: particles ("de", "la", "van", "von", "bin") link forward
to a surname and are written as part of it. Some are never anyone's
given name; others ("Van", "Bin") are ordinary given names in some
cultures, so the vocabulary distinguishes never-given particles from
ambiguous ones, and only the never-given ones license special
treatment. Which particles fall on which side of that line is its own
open question (#360).

P1. Rationale: a never-given particle standing alone cannot be
    someone's given name; a name that opens with one, or offers only
    one as the given name, is a surname written out in full.
    A never-given particle standing alone where the given name would
    go — or opening the name — marks the name as surname-only: the
    given and middle words fold into the family. It needs another
    name word to fold into. An ambiguous particle keeps whatever
    reading its position gives it.
      "de la Vega"                →  family="de la Vega"
      "Mesnil de"  family-first   →  family="Mesnil de"
      "Juan de la Vega"  family-first  →  given="de la Vega"  · boundary
      "van Gogh"                  →  given="van"  · boundary
    Accepted: a bare "de" stays the given name — there is nothing to
    fold into, and inventing a surname would be worse.
      "de"                        →  given="de"
    history: decisions.md#P1 · implemented: nameparser/_pipeline/_post_rules.py

## Suffixes: generational & credentials (S)

## Nicknames & quoted names (N)

## Maiden names (M)

## Commas & structure (C)

## Name order (O)

Background: written name order varies by convention: given-first
(the library's default reading), family-first, and family-first with
the given name last (Vietnamese). The order is declared by the
caller or a locale pack, never detected — but a few conventions
leave a recognizable trace in the name itself. Patronymics are one:
East Slavic names carry a father's-name derivative with distinctive
endings between given and family, and Turkic names use a standalone
marker word ("oglu" son-of, "qizi" daughter-of) after the father's
name. Where such a trace is present and unambiguous, an opted-in
parser can restore the intended reading from a family-first listing.

O1. Rationale: an East Slavic name written family-first still shows
    its patronymic — the distinctive ending identifies which word is
    the patronymic, and the patronymic sits next to the given name.
    With East Slavic patronymic handling active and no comma in the
    name, a name of exactly three name words — titles, suffixes and
    nicknames aside — whose last name word carries a patronymic
    ending and whose middle name word does not reads as family-first:
    the words are restored to given, patronymic, family. A middle
    word that also carries the ending blocks the reading, because
    the surname itself may be patronymic-derived.
      "Сидоров Иван Петрович"  [ru]  →  family="Сидоров"
      "Sidorov Ivan Petrovich Jr."  [ru]  →  family="Sidorov"
      "Иван Петрович Абрамович"  [ru]  →  family="Абрамович"  · boundary
    history: decisions.md#O1 · implemented: nameparser/_pipeline/_post_rules.py

O2. Rationale: a Turkic patronymic marker is a separate word that
    follows the father's name; a four-word name ending in one is a
    family-first listing.
    With Turkic patronymic handling active and no comma in the name,
    a name of exactly four name words — titles, suffixes and
    nicknames aside — ending in a standalone patronymic marker reads
    family-first: the first name word is the family name, and the
    marker stays beside the father's name in the middle.
      "Ali Ahmad Vali oglu"  [tr_az]  →  family="Ali"
      "Ali Ahmad Vali oglu Jr."  [tr_az]  →  family="Ali"
    Accepted: any other count of name words keeps its positional
    reading, even when that leaves the marker itself in a name
    field.
      "Ali Ahmad oglu"  [tr_az]  →  family="oglu"  · boundary
    history: decisions.md#O2 · implemented: nameparser/_pipeline/_post_rules.py

O3. Rationale: several traditions write compound family names
    unmarked, so that every word after the given name belongs to the
    family name.
    With compound-family handling active, every middle word joins
    the family name and is rendered before it; no word is a middle
    name.
      "Hassan Mohamad Ali"  middle_as_family  →  family="Mohamad Ali"
      "Hassan Mohamad Ali"                    →  family="Ali"  · boundary
    implemented: nameparser/_pipeline/_post_rules.py

## Scripts & writing systems (W)

## Tokens, initials & punctuation (T)

## Ambiguity & tie-breaking (A)

## Rendering & views (R)

## Construction & configuration diagnostics (D)
