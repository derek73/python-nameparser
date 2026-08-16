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

H2. Rationale: before a name, an abbreviation is almost always a
    title — "Rev.", "Ing.", "Mag." — and no vocabulary can list
    every profession's abbreviations in every language.
    A name-opening abbreviation — an unbroken run of two or more
    letters ending in its one period — reads as a title even when
    unlisted; a bare initial does not, and neither does anything
    with interior periods, hyphens or digits.
      "Rev. John Smith"           →  title="Rev."
      "Xyz. John Smith"           →  title="Xyz."
      "J. Smith"                  →  given="J."  · boundary
      "J.R. Smith"                →  given="J.R."  · boundary
    Accepted: the shape is only recognizable as an unbroken run of
    letters, so an abbreviation in a script whose letters carry
    combining vowel signs (Bengali, Devanagari) never reads as a
    title by shape — an unlisted abugida honorific stays a name
    word, and only vocabulary (#343) can recognize it.
      "প্রফেসর. Sen"              →  given="প্রফেসর."
    Accepted: before a family comma the pre-comma text is wholly the
    family name (C1), so no shape or vocabulary reading makes a
    title there.
      "Xyz. Smith, John"          →  family="Xyz. Smith"
    history: decisions.md#H2 · interacts: C1 · implemented: nameparser/_pipeline/_assign.py

H3. Rationale: compound titles are written as a run of title words,
    connectives included; a title word standing inside the name is
    just a name word.
    Successive title words at the name's start chain into one
    title; a title word elsewhere in the name does not.
      "Asst. Vice Chancellor John Smith"  →  title="Asst. Vice Chancellor"
      "Marquess of Bath"          →  title="Marquess of Bath"
      "John Doctor Smith"         →  middle="Doctor"  · boundary
    Accepted: before a family comma the pre-comma text is wholly the
    family name (C1), title words included.
      "Dr. Smith, John"           →  family="Dr. Smith"
    interacts: C1 · implemented: nameparser/_pipeline/_group.py

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
    history: decisions.md#P1 · interacts: P2 · implemented: nameparser/_pipeline/_post_rules.py

P2. Rationale: a particle is written as part of the surname it
    precedes, and a title stands outside the name entirely.
    A particle joins the words after it into one family name, and
    the join runs to the end of the name; the chain begins wherever
    the name begins, and a preceding title does not move that point.
      "John van der Berg"         →  family="van der Berg"
      "John van der Berg Smith"   →  family="van der Berg Smith"
      "Sir de Mesnil"             →  family="de Mesnil"
      "Juan de"                   →  family="de"  · boundary
    history: decisions.md#P2 · implemented: nameparser/_pipeline/_group.py

P3. Rationale: connective words ("y", "of the") bind name words into
    one name part; but a single letter in a short name is more
    likely an initial than a connective.
    A recognized connective joins its neighbors into one name part,
    connective runs included — except a single-letter connective in
    a three-word name, which stays a name word.
      "Juan y Eva Garcia"         →  given="Juan y Eva"
      "Juan y Garcia"             →  middle="y"  · boundary
    implemented: nameparser/_pipeline/_group.py

## Suffixes: generational & credentials (S)

Background: what follows a name is one of two different things —
generational suffixes (Jr., III), which attach to the name itself,
and credentials (PhD, MD, MBA), which are earned attachments. CLDR
personNames keeps them as separate fields (`generation`,
`credentials`) and formats them differently; this library currently
reports both in one `suffix` field, a merge #326 examines. The
vocabulary is largely split already: a generational word list and a
credential acronym list, plus a short list of acronyms that are also
ordinary names (MA, BA) and so are AMBIGUOUS as bare words.

S1. Rationale: brackets set off more than nicknames — credentials
    are routinely written parenthesized after a name, and a
    credential is recognizable by its form.
    A bracketed clause whose content is suffix-shaped is not a
    nickname: the brackets are dropped and the content reads exactly
    as if written bare.
      "Andrew Perkins (MBA)"      →  suffix="MBA"
      "Andrew Perkins (Andy)"     →  nickname="Andy"  · boundary
    implemented: nameparser/_pipeline/_extract.py

S2. Rationale: generational suffixes and credentials are recognized
    by vocabulary; an acronym that is also an ordinary name is only
    unmistakably a credential when its periods are written.
    A trailing word of the suffix vocabulary reads as a suffix —
    generational forms and credential acronyms alike, and an
    ambiguous acronym written with periods counts unambiguously. A
    BARE ambiguous acronym is consumed only when the name has words
    to spare: as the second of two words it stays the family name,
    flagged ambiguous.
      "John Smith Jr."            →  suffix="Jr."
      "John Smith M.A."           →  suffix="M.A."
      "John Smith PhD"            →  suffix="PhD"
      "John Ma"                   →  family="Ma"  · boundary
    Accepted: with words to spare, a bare ambiguous acronym reads
    as a suffix even beside an East Asian surname it more likely
    belongs to; and an unambiguous suffix is consumed even when
    that leaves no family name at all.
      "Jack Wei Ma"               →  suffix="Ma"
      "Smith Jr."                 →  family=""
    implemented: nameparser/_pipeline/_classify.py

## Nicknames & quoted names (N)

Background: a nickname is written beside the formal name, set off by
quotes or brackets. Quotation conventions vary by language („…“,
«…», “…”), several share characters — one convention's closer is
another's opener — and the straight apostrophe doubles as a
quotation mark and as a letter-like mark inside names (O'Connor).
Which pairs delimit nicknames is caller configuration.

N1. Rationale: a quoted or bracketed clause beside a name is an
    informal alias, not part of the name.
    A clause enclosed by a configured nickname delimiter pair reads
    as the nickname and is lifted out of the name; an empty
    enclosure is simply dropped.
      "Andrew (Andy) Perkins"     →  nickname="Andy"
      "Jean 'JD' Smith"           →  nickname="JD"
      "Anna () Smith"             →  nickname=""  · boundary
    implemented: nameparser/_pipeline/_extract.py

N2. Rationale: only a mark standing at word boundaries is quoting;
    anywhere else it is part of the word.
    A quote whose open and close are the same character opens only
    at a word start and closes only at a word end, so an apostrophe
    inside or at the end of a word is literal. Between conventions
    that share a character, position in the text decides: the
    leftmost valid opener wins.
      "Sean O'Connor"             →  family="O'Connor"
      "Hans „Erster“ und “Zweiter” Müller"  →  nickname="Erster Zweiter"
      "Mari' Aube'"               →  family="Aube'"  · boundary
    implemented: nameparser/_pipeline/_extract.py

N3. Rationale: a person set down as a nickname plus one name word is
    being identified by surname.
    A name that is only a nickname and one name word reads that word
    as the family name; with two or more name words the ordinary
    positional reading applies.
      "'Smitty' Jones"            →  family="Jones"
      "'Smitty' John Jones"       →  given="John"  · boundary
    Accepted: the count does not set suffixes or titles aside, so a
    nickname plus one name word plus a suffix reads the name word
    as given and leaves the family empty.
      "'Smitty' Jones Jr."        →  family=""
    history: decisions.md#N3 · implemented: nameparser/_pipeline/_assign.py

## Maiden names (M)

Background: a maiden name is written beside the current name, set
off by a marker word (née, geb., 旧姓) or by enclosure. Which
enclosures mean "maiden" rather than "nickname" is a caller
convention, so the maiden reading of a delimiter pair is opt-in.

M1. Rationale: an enclosure the caller has declared to mean maiden
    holds the former family name; a recognized marker word inside it
    marks the clause and is not itself part of the name.
    With a delimiter pair configured for maiden names, its enclosed
    clause reads as the maiden name — unless the content is
    suffix-shaped, which S1 takes first — a leading recognized
    marker word inside the clause being dropped; a pair configured
    for both maiden and nickname reads maiden.
      "Jane Smith (née Jones)"  maiden-parens  →  maiden="Jones"
      "Jane Smith (née Jones)"                 →  nickname="née Jones"  · boundary
    history: decisions.md#M1 · interacts: S1 · implemented: nameparser/_pipeline/_extract.py, nameparser/_pipeline/_group.py

M2. Rationale: a maiden marker announces that what follows it is the
    former family name; the marker is an announcement, not a name.
    A recognized maiden marker standing after at least one name
    word takes the words after it — up to any trailing suffix — as
    the maiden name, and the marker itself is dropped. A marker
    with nothing after it, or nothing before it, is just a word.
      "Jane Smith née Jones"      →  maiden="Jones"
      "Jane née Jones Smith"      →  maiden="Jones Smith"
      "Jane Smith née Jones PhD"  →  suffix="PhD"
      "Jones née"                 →  family="née"  · boundary
      "née Jones"                 →  family="Jones"  · boundary
    Accepted: a marker straight after a comma is post-comma given
    text, not a marker; and a particle chain swallows a marker in
    its path, the join (P2) running first.
      "Jane Smith, née Jones"     →  maiden=""
      "Jane de la née Jones"      →  family="de la née Jones"
    history: decisions.md#M2 · interacts: P2 · implemented: nameparser/_pipeline/_group.py

## Commas & structure (C)

Background: a comma in a name signals one of two conventions — the
listing form "Family, Given" or trailing credentials "Name, PhD" —
and which is meant can only be judged from what stands after the
first comma. Recognizing a credential run is by nature a vocabulary
judgment, so this is the one structural decision that consults the
suffix word lists.

C1. Rationale: a credential run after the comma means the name is in
    natural order with suffixes appended; anything else after the
    comma means the listing form.
    With a comma present, the name reads as trailing suffixes when
    the part after the first comma is entirely suffix words and more
    than one word precedes the comma; otherwise it reads as the
    listing form, the part before the comma being the family name.
    Only the part after the first comma decides. Both modes consult
    the vocabulary alone; by default a recognized suffix word counts
    even written like an initial ("V."), while strict mode vetoes
    initial-shaped words.
      "Smith, John"               →  family="Smith"
      "John Smith, PhD"           →  suffix="PhD"
      "John Smith, V."            →  suffix="V."
      "John Smith, V."  strict-comma-suffixes  →  family="John Smith"
      "Smith, PhD"                →  family="Smith"  · boundary
    history: decisions.md#C1 · implemented: nameparser/_pipeline/_segment.py

C2. Rationale: text beyond the recognized comma parts should be
    taken in without silent guessing.
    Parts beyond the second are consumed as suffixes either way; a
    non-empty extra part that is not entirely suffix words is
    flagged as a structural ambiguity rather than rejected — parsing
    never fails on content. An empty part between doubled commas is
    consumed silently.
      "John Smith, MD, Bart"      →  suffix="MD, Bart"
      "John Smith, MD,, Jr."      →  suffix="MD, Jr."  · boundary
    history: decisions.md#C1 · implemented: nameparser/_pipeline/_segment.py

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

O4. Rationale: what no vocabulary claims can only be read by where
    it stands, under the order the caller declared.
    Words no vocabulary has claimed read by position. In the default
    given-first order the first name word is the given name, the
    last is the family name, and everything between is middle names.
    In a family-first order the first name word is the family; in
    family-first-given-last the given name comes from the end, the
    middles from between.
      "Mary Beth Smith"           →  middle="Beth"
      "Garcia Juan Carlos"  family-first  →  family="Garcia"
      "Nguyễn Thị Minh Khai"  family-first-given-last  →  given="Khai"
    no-boundary: this is the default reading every other rule carves
    exceptions from; its boundaries are the other rules.
    implemented: nameparser/_pipeline/_assign.py

## Scripts & writing systems (W)

Background: script-conditional behavior is permitted exactly where
the writing system itself — not statistics about it — settles the
convention; a language can never be inferred from Latin-script text,
because transliteration destroys the signal. The facts this section
builds on: Chinese and Japanese both write the family name first in
native script, so the script settles the order without knowing the
language. Hangul is written by exactly one language and Korean
family names are a small closed census set. Han text does not
identify its language — a Chinese surname list would divide Japanese
高橋一郎 as 高 + 橋一郎 — which is why Han division is opt-in and
there is no Korean pack to opt into. Hiragana never transcribes a
foreign name (transcriptions are katakana alone), so kanji-plus-kana
is a Japanese name in Japanese order, while wholly-katakana is
predominantly a transcribed foreign name already in given-first
order. Real Chinese text is unspaced (毛泽东); the spaced 毛 泽东 is
an artifact. A fuller narrative lives in docs/usage.rst's East Asian
section.

W1. Rationale: hangul is monoglot Korean and its surnames are a
    closed census set, so an unspaced hangul name divides at a
    certain point; Han carries no such certainty by default.
    An undivided word in the family position of a name written in
    an activated script divides after a recognized surname, the
    longest recognized surname first; where the vocabulary
    recognizes nothing, an optional segmenter may divide instead,
    and with neither the word stays whole rather than divide in a
    wrong place. Korean division is active by default; Han division
    is opt-in.
      "김민준"                    →  family="김"
      "남궁민수"                  →  family="남궁"
      "남궁민수 지훈"             →  family="남궁"
      "毛泽东"                    →  family="毛泽东"  · boundary
      "毛泽东"  [zh]              →  family="毛"
      "高橋一郎"  [zh]            →  family="高"
    history: decisions.md#W1 · implemented: nameparser/_pipeline/_script_segment.py

W2. Rationale: some East Asian honorifics glue directly onto the end
    of the name (田中さん); a glued word peels off only if it could
    never itself end a name, so the listed vocabulary carries its
    own license and needs no other gate.
    A listed honorific glued to the end of the name's last name
    word splits off once and reads as a suffix. The split-off
    crosses a family comma and ignores surrounding punctuation, but
    never treats a part that is not name text as the name's end.
      "田中さん"                  →  suffix="さん"
      "김, 민준씨"                →  suffix="씨"
      "田中さん, V."              →  suffix="さん"
      "马丁·路德·金씨"            →  suffix="씨"
      "김지양"                    →  suffix=""  · boundary
      "王君"                      →  family="王君"  · boundary
    history: decisions.md#W2 · implemented: nameparser/_pipeline/_script_segment.py

W3. Rationale: a family name declared by a comma is the writer's
    own division, and re-dividing it would invent a boundary nobody
    drew.
    Under a family comma the pre-comma text is the family by
    declaration and never divides, and the post-comma side is given
    text with no family to find; only the honorific split-off (W2)
    crosses the comma, an honorific being no part of the name on
    either side. A segmenter — unlike the vocabulary — is consulted
    only for a name whose written form is wholly undivided, a
    spaced honorific counting as a written division.
      "남궁민수"                  →  family="남궁"
      "지훈, 남궁민수"            →  given="남궁민수"
      "남궁민수, 지훈"            →  family="남궁민수"  · boundary
    history: decisions.md#W3 · implemented: nameparser/_pipeline/_script_segment.py

W4. Rationale: Chinese, Japanese and Korean all write the family
    name first in native script — the script settles the order
    without knowing the language — while a wholly-katakana name is
    predominantly a transcribed foreign name already in its source
    order.
    A name written wholly in one East Asian script, or in the
    kana-licensed Japanese repertoire, reads family-first whatever
    order the caller declared; a wholly-katakana name keeps the
    declared order.
      "김 민준"                   →  family="김"
      "山田 太郎"                 →  family="山田"
      "高橋 みなみ"               →  family="高橋"
      "マイケル ジャクソン"        →  given="マイケル"  · boundary
    Accepted: a name the interpunct divides keeps its source order —
    the divider itself marks a transcription (T3) — so the override
    stands down there; the katakana middle dot (T2) carries no such
    signal, so a name it divides still reads by the script license.
      "毛·泽东"                   →  given="毛"
      "威廉・莎士比亚"            →  family="威廉"
    history: decisions.md#W4 · interacts: T3 · implemented: nameparser/_pipeline/_assign.py

## Tokens, initials & punctuation (T)

Background: every parsed name part is an exact piece of the input,
located by its position — nothing rewrites the text before parsing.
Some punctuation is a name divider only by convention of a
particular writing system: Japanese writes name parts with a middle
dot between them (マイケル・ジャクソン, 姓・名), while U+00B7 is
both the Chinese divider for transcribed foreign names and the
Catalan punt volat interior to legitimate words (Gal·la).

T1. Rationale: a character that carries no name content (emoji, an
    invisible directionality control) stands between words, not
    inside them.
    A name splits at whitespace and — unless the caller opts to
    keep them — at ignorable characters: an ignorable character
    separates its neighbors and never joins them.
      "John😀Smith"                →  family="Smith"
      "John😀Smith"  keep-emoji    →  given="John😀Smith"  · boundary
    history: decisions.md#T1 · implemented: nameparser/_pipeline/_tokenize.py

T2. Rationale: the katakana middle dot exists to divide name parts
    and appears in no native name.
    The katakana middle dot and its halfwidth twin divide a name
    like whitespace, always.
      "マイケル・ジャクソン"        →  given="マイケル"
      "高橋・一郎"                 →  family="高橋"
    no-boundary: the separation is unconditional; the
    context-sensitive interpunct is T3's subject.
    implemented: nameparser/_pipeline/_tokenize.py

T3. Rationale: U+00B7 is two marks in one codepoint — the Chinese
    间隔号 dividing a transcribed foreign name, and the Catalan punt
    volat interior to words.
    The interpunct divides a name only between two characters of a
    classified East Asian script; anywhere else it is part of the
    word.
      "威廉·莎士比亚"              →  family="莎士比亚"
      "Gal·la Serra"              →  given="Gal·la"  · boundary
    history: decisions.md#T3 · implemented: nameparser/_pipeline/_tokenize.py

## Ambiguity & tie-breaking (A)

Background: some name strings are genuinely ambiguous — the same
written shape carries two readings ("Van Johnson": given name or
particle?), or the text's structure is malformed. Parsing never
fails and never silently discards; it completes on the best reading
and says what it was unsure of.

A1. Rationale: a caller can only act on doubt that is reported.
    Parsing never fails on any input: where the text's structure or
    a word's reading is genuinely uncertain, the parse completes on
    the best reading and carries an ambiguity report naming the
    doubt.
      "Van Johnson"               →  ambiguities=("particle-or-given",)
      "Jane „JD Smith"            →  ambiguities=("unbalanced-delimiter",)
      "John Smith, MD, Bart"      →  ambiguities=("comma-structure",)
      "John Smith"                →  ambiguities=()  · boundary
    Accepted: the one exception to totality is a user-supplied
    segmenter's own error, which propagates — a user-code error is
    not a content error. (Needs the optional extra to demonstrate,
    so no example line.)
    implemented: nameparser/_pipeline/_state.py

## Rendering & views (R)

Background: parsing produces words with roles; every string a caller
reads is assembled from those words on request. Nothing about
rendering changes the parse, and nothing about reading a field
mutates anything.

R1. Rationale: a field is a way of reading the parse, not a stored
    string.
    Every field is a view computed from the parsed words at read
    time, joining its words in written order — except folded family
    words (O3), which render before the rest of the family wherever
    they stood in the string.
      "Dr. Juan Q. Xavier de la Vega III"  →  family="de la Vega"
      "Hassan, Mohamad Ahmad Ali"  middle_as_family  →  family="Ahmad Ali Hassan"
      "Hassan, Mohamad Ahmad Ali"          →  family="Hassan"  · boundary
    implemented: nameparser/_types.py

R2. Rationale: callers need the surname with and without its
    particles — sorting wants "Vega", display wants "de la Vega".
    The family name splits into further views: the base (the family
    without its leading particles) and the particles themselves.
      "Dr. Juan Q. Xavier de la Vega III"  →  family_base="Vega"
      "Dr. Juan Q. Xavier de la Vega III"  →  family_particles="de la"
      "Sean O'Connor"             →  family_base="O'Connor"  · boundary
    implemented: nameparser/_types.py

R3. Rationale: initials abbreviate the person's name words; titles,
    suffixes, particles and nicknames are not name words.
    Initials take the first letter of each given, middle, and base
    family word; titles, suffixes, particles and nicknames
    contribute nothing.
      "Dr. Juan Q. Xavier de la Vega III"  →  initials="J. Q. X. V."
      "Sean O'Connor"             →  initials="S. O."  · boundary
    implemented: nameparser/_render.py

R4. Rationale: case repair is a display concern, applied only on
    request and never destructively.
    Case repair returns a repaired copy — vocabulary exceptions
    (McDonald) included — and never mutates the parse; an
    already-correct name comes back unchanged.
      "juan mcdonald"             →  capitalized="Juan McDonald"
      "Juan McDonald"             →  capitalized="Juan McDonald"  · boundary
    implemented: nameparser/_render.py

## Construction & configuration diagnostics (D)

Background: configuration mistakes are reported when they are made —
at construction — not when a name happens to hit them; and a
diagnostic that hands the reader code must hand code that works and
type-checks.

D1. Rationale: a parser whose activated scripts nothing can divide
    behaves like a working parser minus a feature, silently — the
    one misconfiguration a caller cannot see in output.
    Constructing a parser that activates division for scripts with
    no covering surnames and no segmenter warns at construction,
    naming the dead scripts and each way out.
      [segmenterless-ja]  →  warns="deactivate with Policy(segment_scripts=frozenset())"
    no-boundary: any covering surname vocabulary, configured
    segmenter, or deactivation silences it — the default parser and
    the zh pack never warn, which every other example in this
    document exercises.
    history: decisions.md#D1 · implemented: nameparser/_parser.py

D2. Rationale: whatever a name contains, parsing answers; only a
    broken configuration may raise, and it must name the field.
    Configuration validation raises at construction with the
    offending field and value named; applying a locale pack wraps
    any such error with the locale's code, so a stacked
    configuration names which layer broke.
      [bad-name-order]  →  raises="name_order elements must be Role members"
      [bad-order-none]  →  raises="name_order must be an iterable"
    no-boundary: the non-raising side is every other rule's
    examples; parse() itself is total (A1).
    history: decisions.md#D2 · implemented: nameparser/_policy.py, nameparser/_parser.py
