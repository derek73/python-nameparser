"""Stage: classify.

Consumes: tokens, comma_offsets (with token roles, the two halves of
the structural-boundary test the marker pass applies -- see
_vocab.tag_marker_runs), and one_case where an earlier stage recorded
it -- segment writes it lazily where C2's flag on a part past the
second comma asks for it (#289/#516, #613), so this read is the
fallback for every other name.
Produces: tokens with vocabulary tags added (text/span/role unchanged),
plus ambiguities (CONJUNCTION_OR_INITIAL) and
one_case -- whether the name's own words are written in one case,
recorded for the later stages that read it (#289/#516) and left alone
where an earlier stage already asked.
Reads: every Lexicon vocabulary field except surnames and
honorific_tails, which script_segment consumes upstream; and, since
2.4, Policy.unlisted_dotted_suffixes and Policy.unlisted_caps_suffixes,
which decide whether an UNLISTED dotted or all-caps token joins the
ambiguous credential class by SHAPE (#516) -- the all-caps half here
only under CapsSuffixes.EVERYWHERE, the default's part after a comma
being tagged by `_comma.decide` when group binds it (#613); and
Policy.extra_suffix_delimiters, with the built-in semicolon
(_vocab.glued_cores), so a word after the first comma with a
delimiter glued to it is tagged as the word without it (rules/C10).
is_initial also consults
the _policy module's _NO_INITIALS constant. It is named apart from the
fields above because it is not CONFIGURATION -- no Lexicon or Policy
carries it and no caller can change it -- and not because it decides
nothing: the tags this stage writes do vary by it ('씨.' is not tagged
`initial`, which is the whole of #320).

Tags emitted -- stable (API): "particle", "conjunction", "initial";
namespaced (unstable): "vocab:title", "vocab:given-title",
"vocab:after-given-title", "vocab:title-ambiguous",
"vocab:suffix", "vocab:suffix-word", "vocab:suffix-ambiguous",
"vocab:suffix-word-ambiguous", "vocab:agnomen",
"vocab:particle-ambiguous", "vocab:bound-given",
"vocab:given-abbreviation", "vocab:maiden-marker",
"vocab:maiden-marker-cont"; in a namespace of its own,
"shape:acronym"; and in another, "split:credential" and
"split:member", written on the first word of a credential split across
a space (`_vocab.split_pair`) to name the piece the pair merges into:
the Ph./D. pair's unambiguous suffix, or any other pair's member of the
ambiguous class (rules/S12).
"vocab:maiden-marker" tags the HEAD of a maiden marker, which is a
whole marker whenever the marker is one word; the continuation tag
carries the rest of a PHRASE marker ("z domu"), so a site asking
"does a marker start here" reads the same tag it always did and a site
asking "where does it end" walks the continuations.
"vocab:suffix" means "counts as a suffix as written": unambiguous
suffix vocabulary, or an ambiguous acronym written with periods --
at the TAG level 'M.A.' gets "vocab:suffix" while 'Ma' gets only
"vocab:suffix-ambiguous"; what assign then does with a trailing
ambiguous tag is rules S4 to S7 (the words-to-spare guard, the
case, the company) and their Accepted consequences.
The initial veto is assign's job, not classify's: 'V' carries both
"vocab:suffix" and "initial".
"shape:acronym" is the one tag in the shape: namespace and it records
WHERE a class claim came from rather than what the vocabulary holds:
an unlisted token the writing makes credential-shaped. It rides
beside "vocab:suffix-ambiguous" where a Policy switch admits the
token to that class, and stands alone where the switch is off, which
is what lets the fork be reported without being taken.
"""
from __future__ import annotations

import unicodedata

from nameparser._lexicon import _normalize, _spells_an_initial
from nameparser._policy import CapsSuffixes
from nameparser._pipeline._state import (
    AGNOMEN_TAG, AMBIGUOUS_ACRONYM_TAG, AMBIGUOUS_WORD_TAG,
    GIVEN_ABBREVIATION_TAG, SHAPE_ACRONYM_TAG,
    SPLIT_CREDENTIAL_TAG, SPLIT_MEMBER_TAG, TITLE_AMBIGUOUS_TAG, ParseState,
    Deferred, PendingAmbiguity, PendingReading,
    WorkToken, copy_with,
)
from nameparser._types import AmbiguityKind, ReadingKind, ReadingSource
from nameparser._pipeline._vocab import (
    BUILTIN_GLUED_DELIMITERS, SPLIT_CHUNK, SPLIT_PAIR_OPENS, _INITIAL, caps_shape_candidate,
    composed_len, glued_cores, glued_stem, is_cased_paired_initials,
    is_initial, is_one_case, period_joined_vocab, split_pair,
    suffix_as_written, tag_marker_runs, title_readings,
)
from nameparser._pipeline._pieces import own_words




# rules/S2: "a trailing word of the suffix vocabulary reads as a
# suffix — generational forms and credential acronyms alike" -- and
# rules/S3: "an ambiguous acronym written with its periods, one after
# each letter or one after each of two or more letter chunks, counts
# unambiguously; a single trailing period is the abbreviation shape
# any word can wear and does not" -- and rules/S4: "a
# bare ambiguous acronym is consumed only when the name has words to
# spare"
def _tags_for(token: WorkToken, n: str, state: ParseState,
              marker_tag: str | None, one_case_own: bool,
              one_case: bool, letter_one_case: bool) -> frozenset[str]:
    """`n` is _normalize(token.text), folded once by the caller and
    shared with the marker pass; `marker_tag` is what that pass decided
    for this token, or None. The marker DECISION is entirely
    `_vocab.tag_marker_runs`'; only the writing happens here, so the
    two tokens of a phrase are built once rather than replaced twice.

    `one_case_own` is true when the name's OWN words are written in one
    case AND this token is one of the name's own words -- a maiden clause
    and any delimited (nickname) content are not, so the fork never
    reads them either (rules/P3): a clause's words are not the
    name's own words, and appending one must not change how THIS token
    reads.

    `one_case` is the bare NAME-level fact alone -- P3's own-words
    span is not this question's business. #516's caps branch reads
    THIS, not `one_case_own`: a maiden clause's own words are outside
    `one_case_own`'s span by construction (`i < clause_at` fails for
    every one of them), so a token past the clause cut reads
    `one_case_own` as False regardless of whether the WHOLE name is
    written in one case -- 'JOHN SMITH NEE' flipped 'NEE' to a
    credential reading with the switch on, one case and all, because
    `not one_case_own` was true for it purely from being past the
    clause cut, never from the name's own writing (#516 review round,
    a second reviewer's finding). `single_letter_connective` below
    keeps `one_case_own`: that fork is genuinely about the OWN-WORDS
    span, and reads a clause's word as no evidence on purpose.

    `letter_one_case` is rules/T4's question for THIS token: the
    own-words fact for one of the name's own words, and for a word
    outside them -- a clause's, or past a declined marker -- the fact
    about the WHOLE name, since the own words' case says nothing
    about how the clause beside them was written: 'y' in 'MARIA
    GARCIA NEE LOPEZ y FERNANDEZ' is a lower-case letter among
    capitals, which T4 reads as no initial (#723's review)."""
    lex = state.lexicon
    tags = set(token.tags)
    if marker_tag is not None:
        tags.add(marker_tag)
    if n in lex.titles:
        tags.add("vocab:title")
    if n in lex.given_name_titles:
        tags.add("vocab:given-title")
    # rules/H8: "the word joins the title field" -- tagged only where the
    # word is a title too, so an entry outside `titles` is inert
    if n in lex.after_given_titles and n in lex.titles:
        tags.add("vocab:after-given-title")
    if suffix_as_written(n, token.text, lex):
        tags.add("vocab:suffix")
    if n in lex.suffix_words_ambiguous:
        # rules/S11: "it reads as the generation only where the name has
        # words to spare" -- the ambiguous class's tag, so every site
        # that weighs a member weighs this one, and the cue tags that
        # tell `_pieces.listed_lean` how its writing leans
        tags.add(AMBIGUOUS_ACRONYM_TAG)
        tags.add(AMBIGUOUS_WORD_TAG)
        if n in lex.agnomens:
            tags.add(AGNOMEN_TAG)
    elif n in lex.suffix_words:
        tags.add("vocab:suffix-word")
    if n in lex.suffix_acronyms_ambiguous:
        tags.add(AMBIGUOUS_ACRONYM_TAG)
    # rules/P7: "A one-letter word written with its period is an
    # initial and not a particle" -- both particle tags, so 'Ó.' is
    # neither half of the vocabulary
    if n in lex.particles and not _spells_an_initial(n, token.text):
        tags.add("particle")
        if n in lex.particles_ambiguous:
            tags.add("vocab:particle-ambiguous")
    # rules/P8: "a single-letter connective reads as an initial
    # where the writing says so: written as a bare Latin capital in a
    # name that is not written wholly in one case, or — in a name
    # written wholly in one case, where nothing says so — where the
    # letter is one the vocabulary marks as reading both ways"
    # (#383/#479; history: decisions/P8)
    # one letter as the writer sees it: a decomposed 'й' is two code
    # points (#665), so non-ASCII text is counted composed, after the
    # C-level tests have declined everything else
    single_letter_connective = (n in lex.conjunctions
                                and token.text.upper() != token.text.lower()
                                and (len(token.text) == 1
                                     or not token.text.isascii()
                                     and composed_len(token.text) == 1))
    if single_letter_connective and one_case_own:
        # No case evidence, so the vocabulary decides. No namespaced
        # tag beside it: the emitted ambiguity IS the record of the
        # decision (mechanisms.md#MARK-DONT-STRIP is satisfied by the
        # report) -- mechanisms.md#AMBIGUITY-AT-THE-DECISION-SITE says
        # emit where the branch is taken, not where an ambiguous tag
        # sits, and a vocab: tag records MEMBERSHIP, not the branch
        # taken, so it is the wrong shape of record here.
        if n in lex.conjunctions_ambiguous:
            tags.add("initial")
        else:
            # a bare capital y joins here, where mixed case vetoes it
            tags.add("conjunction")
    else:
        # the mixed-case rule, unchanged. v1's is_conjunction excludes
        # initials: 'e.' in 'john e. smith' is a middle initial, not
        # the Spanish conjunction 'e'
        # rules/T4: "in a name written wholly in one case, which says
        # nothing about any letter in it, a bare letter is an initial
        # wherever its capital would be" -- so every reader of the tag
        # after classify reads 'j' as it reads 'J' (#723; the roman
        # numerals first, #721). Readers that run before the tag
        # exists, or ask the word's text rather than its tag -- the
        # strict suffix test, which the honorific peel and
        # `lenient_comma_suffixes=False` ask -- take the same fact as
        # an argument (#727). `letter_one_case` is the own-words fact
        # for an own word and the whole name's for a clause's
        # (docstring). The capital is asked of the
        # bare pattern at C level, no frame per one-letter word, and
        # needs no script test: no capital `_INITIAL` matches is in a
        # script without initials. 'é' and 'ж' stay as they were,
        # their capitals being no initial either. A clause's letter
        # asks the whole name's case (`letter_one_case`, docstring)
        initial = is_initial(token.text) or (
            letter_one_case and len(token.text) == 1
            and _INITIAL.fullmatch(token.text.upper()) is not None)
        if n in lex.conjunctions and not initial:
            tags.add("conjunction")
        if initial:
            tags.add("initial")
    if n in lex.bound_given_names:
        tags.add("vocab:bound-given")
    # rules/H2: "an abbreviation the vocabulary reads as a given name
    # written short is that given name" -- the reading H2's shape test
    # weighs (`_pieces.is_leading_title`); a membership, so any spelling
    # carries it and only that test acts on it
    if n in lex.given_name_abbreviations:
        tags.add(GIVEN_ABBREVIATION_TAG)
    # maiden markers are NOT tagged here: an entry may be a phrase whose
    # words are not markers on their own, and this function sees one
    # token with no neighbours. `_vocab.tag_marker_runs` does the whole
    # field, single words included, so there is one place that decides
    # it (mechanisms.md#ONE-PREDICATE-PER-QUESTION).
    # The block a WHOLE-TOKEN vocabulary match skips, and four
    # readings inside it, in precedence order. The first two are v1's
    # period-joined derivation (parse_pieces): a token with a period
    # not at the end, ANY of whose period chunks is a title, is a
    # title as a whole ('Lt.Gov.', and by the ANY rule 'Mr.Smith');
    # else ANY suffix chunk makes it a suffix ('JD.CPA'). Title wins
    # (v1's continue). The third and fourth are 2.4's by-shape halves
    # (#516; rules/S9: "joins the ambiguous class (S4) by SHAPE, in
    # the positions each shape is admitted") and reach only a
    # token NO vocabulary claimed: a dotted token of two or more
    # alphabetic chunks, and -- where its switch is on -- an unlisted
    # all-caps word. They are an `elif` chain
    # with the dotted one first, so a dotted token never reaches the
    # caps test and the two shapes stay disjoint.
    #
    # Both by-shape branches carry SHAPE_ACRONYM_TAG BESIDE the
    # membership tag rather than instead of it: `vocab:` records
    # membership (the roster above) and the peel reads membership,
    # while the shape tag records that the claim came from the
    # WRITING. The dotted branch writes it even with its switch off,
    # which is what lets a declined fork be reported without being
    # taken. `role is None` guards both: a token already carrying a
    # role is delimited content, decided by extract's escape and never
    # at the trailing slot -- 'Bridge (A.B)' is the control that
    # proves the guard load-bearing (without it the nickname reading
    # of 'A.B' gains a spurious SUFFIX_OR_NICKNAME report in post_rules), and
    # 'Bridge (1.4)' cannot exercise it, a digit chunk never reaching
    # the shape verdict at all (period_joined_vocab's alphabetic
    # gate).
    if "vocab:title" not in tags and "vocab:suffix" not in tags:
        derived = period_joined_vocab(token.text, lex)
        if derived == "title":
            tags.add("vocab:title")
        elif derived == "suffix":
            tags.add("vocab:suffix")
        elif (derived == "shape" and token.role is None
                and n not in lex.suffix_acronyms_ambiguous):
            # This branch and `_vocab.ambiguous_class_candidate` ask
            # the SAME question twice, of necessity -- `segment` runs
            # before `classify` and has no tags to read yet -- kept
            # from drifting by `test_classify.
            # test_ambiguous_class_candidate_agrees_with_the_tag`
            # rather than by this sentence alone.
            #
            # `n not in suffix_acronyms_ambiguous` is the third guard,
            # and it is about a LISTED member rather than a role: a
            # caller may list a dotted entry ('a.b'), which the whole-
            # token membership test above matches while
            # `suffix_as_written`'s period-free acronym lookup ('ab')
            # misses, so the chunk view reached here and called the
            # word by-shape -- silencing `_pieces.listed_lean`, which
            # declines wherever SHAPE_ACRONYM_TAG rides, and costing
            # the caller's own listing its case lean ('Jack A.B.' read
            # family where 'Jack MA' reads suffix). One frozenset
            # lookup on a branch only a dotted token reaches; the
            # shipped ambiguous vocabulary carries no periods, so
            # nothing default changes.
            tags.add(SHAPE_ACRONYM_TAG)
            # rules/S3: "Paired initials are the exception, as C5 defines
            # them, in a script that writes capitals" -- the shape
            # tag alone, as with the switch off, so the trailing slots
            # read them as a name word and report the fork; the comma
            # restores the class tag where C5 reads them
            # (decisions/S3 (#864)); `is_cased_paired_initials` asks the
            # script half ('พ.บ.' is no initial)
            if (state.policy.unlisted_dotted_suffixes
                    and not is_cased_paired_initials(token.text)):
                tags.add(AMBIGUOUS_ACRONYM_TAG)
        elif (state.policy.unlisted_caps_suffixes is CapsSuffixes.EVERYWHERE
                and token.role is None
                # what the predicate would decline anyway, asked first in
                # C: a listed member ('John Smith, MA'), and a word that
                # is not alphabetic capitals ('John Smith, Ph. D.')
                and n not in lex.suffix_acronyms_ambiguous
                and (token.text.isupper()
                     and (token.text.isalpha() or "-" in token.text
                          or "/" in token.text)
                     or not unicodedata.is_normalized("NFC", token.text))
                and caps_shape_candidate(token.text, lex, state.policy,
                                         one_case)):
            # #516's all-caps half: an unlisted word written in capitals
            # inside a mixed-case name. EVERYWHERE tags it in every
            # slot; the default admits it only in the part after a
            # comma, which `_comma.decide` reads after this stage and
            # tags there when it binds the part (#564, #613), so the
            # reading carries the same marks under either setting --
            # case repair keeps 'XYZ' in 'John Smith, XYZ'
            # (rules/R4) rather than title-casing a credential the
            # default admitted.
            # The setting comes FIRST, then C-level checks of what the
            # predicate would decline, so the default never calls it
            # and EVERYWHERE calls it only for an unlisted all-caps
            # word (that is why this half is a call where the dotted branch
            # above stays inline: the dotted caller has no such cheap
            # first conjunct to hide behind). The predicate's own
            # docstring carries the whole-vocabulary roster and what
            # each measured entry would have cost unfixed.
            tags.add(SHAPE_ACRONYM_TAG)
            tags.add(AMBIGUOUS_ACRONYM_TAG)
    return frozenset(tags)


#: The tags of a word that joins the word after it, which a delimiter
#: glued to the word stands between (rules/C10). A particle's are among
#: them though it also attaches backward (rules/P6): kept, it chained
#: forward across the delimiter ('Berg, de; Smith' read family 'Berg de;
#: Smith'), and blocking the forward joins alone would guard every site
#: that reads the tag (decisions/C10).
_JOINING_TAGS = frozenset({"particle", "conjunction",
                           "vocab:particle-ambiguous", "vocab:bound-given"})

#: What a word read out of the title gives up (rules/H9): the title tag
#: and the two that qualify one, which are read only beside it.
_TITLE_TAGS = frozenset({"vocab:title", "vocab:given-title",
                         "vocab:after-given-title"})


def classify(state: ParseState) -> ParseState:
    # One fold per token, shared by the marker pass and the vocabulary
    # tags -- the shape suffix_as_written already asks for ("n is
    # _normalize(text), passed in so callers normalize once").
    folded = [_normalize(t.text) for t in state.tokens]
    marker_tags = tag_marker_runs(state.tokens, state.comma_offsets,
                                  state.lexicon.maiden_markers, folded)
    # rules/P3 says a maiden marker, taken as one, and the words it
    # takes, are not among the name's own words -- so the span and its
    # clause cut are _pieces.own_words', shared with the site that
    # needs the same answer two stages earlier (#289/#516). The marker
    # map goes with it: this stage has already decided which tokens
    # are run HEADS, so the helper reads that decision rather than
    # walking the texts again, and classify's answer is the one it was
    # before the helper existed.
    own, clause_at = own_words(state.tokens, state.comma_offsets,
                               state.lexicon.maiden_markers, marker_tags)
    # ONE fact per parse, and it is recorded now (ParseState.one_case):
    # segment writes it first where C2's flag on a tail part asks, and
    # a fact two stages decide apart is what recording it prevents
    # (decisions/S6).
    one_case = state.one_case
    if one_case is None:
        one_case = is_one_case(own)
    # The fork itself must not read a clause's words either, so the
    # `one_case and ...` argument below repeats `own`'s membership test
    # per token, and the fork and its emitter then agree with the case
    # class they consult. No extra frame -- it is one more boolean in a
    # comprehension that already walks every token.
    # rules/T4 asks a word outside the own words about the WHOLE
    # name's case (`_tags_for`'s `letter_one_case`). Where every token
    # is an own word the two facts are one, so only a name with a
    # clause pays the second test's frame.
    whole_one_case = one_case and (
        len(own) == len(state.tokens)
        or is_one_case([t.text for t in state.tokens]))
    # rules/C10: "the word keeps the delimiter in its text and reads as
    # it would without it" -- tagged as the word without it ('MD;' as
    # 'MD'), so every reading that asks a word's vocabulary asks the
    # stem's; only where the delimiter "stands after the first comma",
    # a semicolon before it being a word (decisions/C10, D15)
    readers = list(state.tokens)
    stemmed: set[int] = set()
    if state.comma_offsets:
        policy_cores = state.policy.extra_suffix_delimiters
        cores = (BUILTIN_GLUED_DELIMITERS if not policy_cores
                 else glued_cores(policy_cores))
        first = state.comma_offsets[0]
        for i, t in enumerate(state.tokens):
            text = t.text
            if t.span.start < first:
                continue
            for core in cores:
                if core in text:
                    stem = glued_stem(text, cores)
                    if stem is not None:
                        readers[i] = copy_with(t, text=stem)
                        folded[i] = _normalize(stem)
                        stemmed.add(i)
                    break
    tokens = tuple(
        copy_with(
            t, tags=_tags_for(readers[i], folded[i], state, marker_tags.get(i),
                              one_case_own=one_case and i < clause_at
                              and t.role is None, one_case=one_case,
                              letter_one_case=whole_one_case or (
                                  one_case and i < clause_at
                                  and t.role is None)))
        for i, t in enumerate(state.tokens))
    # A word with a delimiter glued to it joins no neighbour across the
    # delimiter, so the stem's joining tags stay off it: 'y;' is no
    # connective to the word after it (rules/C10: "no join, maiden
    # clause or connective reaches across it")
    if stemmed:
        tokens = tuple(
            copy_with(t, tags=t.tags - _JOINING_TAGS) if i in stemmed else t
            for i, t in enumerate(tokens))
    # rules/H9: "the word is a title only inside a title phrase, and
    # elsewhere a name word" -- the phrase test (_vocab.title_readings)
    # asked per part, of the words carrying no role, and only of a part
    # holding one, so that a name with neither pays no frame. A word read out of the title keeps no
    # title tag, and every later stage reads it as the name word it is;
    # a contested word keeps TITLE_AMBIGUOUS_TAG either way, for the
    # report where it opens the name (assign)
    lex = state.lexicon
    if not (lex.titles_ambiguous.isdisjoint(folded)
            and lex.title_modifiers.isdisjoint(folded)):
        written = list(tokens)
        for at, seg in enumerate(state.segments):
            own_part = [i for i in seg if written[i].role is None]
            norms = [folded[i] for i in own_part]
            if (lex.titles_ambiguous.isdisjoint(norms)
                    and lex.title_modifiers.isdisjoint(norms)):
                continue
            readings = title_readings(
                [readers[i].text for i in own_part], norms, lex,
                head=at == 0,
                titled=["vocab:title" in written[i].tags for i in own_part])
            for i, title in zip(own_part, readings):
                tags = written[i].tags
                n = folded[i]
                if n not in lex.titles_ambiguous and n not in lex.title_modifiers:
                    continue
                if n in lex.titles_ambiguous and n not in lex.titles:
                    tags = tags | {TITLE_AMBIGUOUS_TAG}
                    if title:
                        # in a title phrase: a title (its given-name title
                        # tag, if any, `_tags_for` wrote already)
                        tags = tags | {"vocab:title"}
                if not title:
                    tags = tags - _TITLE_TAGS
                if tags != written[i].tags:
                    written[i] = copy_with(written[i], tags=tags)
        tokens = tuple(written)
    # rules/S12: "a credential written split across a space reads as one
    # word" -- each adjacent pair of a segment asked once, here, and
    # the answer written on its first word for group's merge and the
    # comma's reading of its part (`_vocab.split_pair`). The shape and
    # the fold's membership are asked first, in C, so an ordinary pair
    # of words pays no frame; a token carrying a role is delimited
    # content, which no pair reaches.
    split: dict[int, str] | None = None
    acronyms = state.lexicon.suffix_acronyms
    words = state.lexicon.suffix_words
    for seg in state.segments:
        for j in range(len(seg) - 1):
            a, b = tokens[seg[j]], tokens[seg[j + 1]]
            if (SPLIT_CHUNK.fullmatch(a.text) is not None
                    and SPLIT_CHUNK.fullmatch(b.text) is not None
                    and a.role is None and b.role is None
                    # the opening letter, the length a superset of the
                    # predicate's count of composed letters ('i i' folds
                    # to the listed 'ii' and opens with one)
                    and (len(a.text.rstrip(".")) >= 2
                         or a.text.endswith(".") and b.text.endswith(".")
                         and (len(b.text) == 2 or not b.text.isascii()))
                    # the Ph./D. pair whatever the vocabulary, as v1's
                    # fix_phd merged it; any other only where its words
                    # are not two suffix words, two credentials already,
                    # and its fold is listed, composed in C where it is
                    # not ASCII
                    and (SPLIT_PAIR_OPENS.fullmatch(a.text) is not None
                         or not ("vocab:suffix" in a.tags
                                 and "vocab:suffix" in b.tags)
                         and ((fold := (a.text + b.text).replace(".", "")
                               .lower()) in acronyms or fold in words
                              or not fold.isascii()
                              and ((nfc := unicodedata.normalize(
                                  "NFC", fold)) in acronyms
                                   or nfc in words)))
                    and (kind := split_pair(a.text, b.text,
                                            state.lexicon)) is not None
                    # a member pair a connective borders is no credential:
                    # the connective joins the words beside it
                    and (kind == "suffix" or (
                        j == 0
                        or "conjunction" not in tokens[seg[j - 1]].tags)
                        and (j + 2 >= len(seg)
                             or "conjunction" not in tokens[seg[j + 2]].tags))
                    # the Ph./D. pair outranks a pair overlapping it:
                    # 'Dr. Ph. D.' is no 'Dr. Ph.' ('drph') and a 'D.'
                    and not (kind == "split" and j + 2 < len(seg)
                             and split_pair(b.text, tokens[seg[j + 2]].text,
                                            state.lexicon) == "suffix")):
                if split is None:
                    split = {}
                split[seg[j]] = (SPLIT_CREDENTIAL_TAG if kind == "suffix"
                                 else SPLIT_MEMBER_TAG)
    if split is not None:
        # a loop, not a generator, which is a frame per token resumed
        written = list(tokens)
        for i, tag in split.items():
            written[i] = copy_with(written[i], tags=written[i].tags | {tag})
        tokens = tuple(written)
    ambiguities = list(state.ambiguities)
    for i, token in enumerate(tokens):
        # #383/#479: narrows the fork's own "initial" tag with the same
        # inputs the fork used, rather than re-deciding from scratch.
        # Only the casedness test is inherited from the tag --
        # `is_initial(token.text)` also tags a bare capital "initial"
        # in the fork's else branch, so the tag alone does not tell
        # this apart from that.
        #
        # Of the two clauses beside it, one is load-bearing and one is
        # not. `conjunctions_ambiguous` is IMPLIED by the others for a
        # fresh parse -- the contrapositive of what it looks like:
        # `is_initial` matches an ASCII capital only, so a bare
        # LOWERCASE letter is tagged "initial" only by the fork's
        # branch ("jose e maria santos" tags a lowercase e), for a
        # conjunctions_ambiguous member, or by the one-case letter
        # (#721, #723), which never tags an own word that is a
        # single-letter connective (the fork's branch takes those
        # first). So for a letter of EITHER case in `conjunctions`,
        # "initial" plus len 1 implies membership. It is kept only because `_tags_for`
        # starts from `set(token.tags)`, so
        # this clause is what keeps the emitter honest if a runner ever
        # hands classify tokens it did not build; no such path exists
        # today. `conjunctions` is the clause doing real work: it keeps
        # an orphan marker (a conjunctions_ambiguous entry no longer in
        # conjunctions) inert rather than reported (decisions/P8).
        # `i < clause_at and token.role is None` mirrors the fork's own
        # "own words" test above, for the same reason (rules/P3): a
        # clause's words were never eligible for the fork, so they must
        # never be eligible to report either. Emitted at the decision
        # site (mechanisms.md#AMBIGUITY-AT-THE-DECISION-SITE), per
        # token -- 'e and e e' emits twice; assemble withdraws the
        # report on a letter no name word follows (rules/P8, #721).
        if (one_case and "initial" in token.tags
                and folded[i] in state.lexicon.conjunctions_ambiguous
                and folded[i] in state.lexicon.conjunctions
                and i < clause_at and token.role is None
                and (len(token.text) == 1
                     or not token.text.isascii()
                     and composed_len(token.text) == 1)):
            ambiguities.append(PendingAmbiguity(
                AmbiguityKind.CONJUNCTION_OR_INITIAL,
                f"{token.text!r} is both a connective and an initial; "
                f"the name is written in one case, so nothing marks "
                f"which, and it is read as an initial",
                (i,),
                # the field of the join it would make is assign's to
                # name, once the name has positions
                alternative=PendingReading(ReadingKind.CONJUNCTION,
                                           ReadingSource.VOCABULARY,
                                           Deferred.JOINED)))
    # The write rides the replace this stage already makes, so
    # recording the fact costs no frame of its own.
    return copy_with(state, tokens=tokens,
                     ambiguities=tuple(ambiguities),
                     one_case=one_case)
