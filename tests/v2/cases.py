"""THE shared behavior case table (rules.md cites it as the pin of
CURRENT behavior).

Format is fixed here, in the first pipeline PR, and never per-PR:
one Case per input, expected values for exactly the non-empty fields,
optional Policy/Locale context, and a mandatory classification --
"parity" (matches v1.4.0, pinned live 2026-07-12) or "fix(#N)" /
"fix(<slug>)" (an intentional 2.0 behavior change, annotated with its
issue or a design-decision slug). No silent expectation edits:
changing a row means changing its classification.

"UNDETERMINED" is a fourth value and a TEMPORARY one: a row added
before anyone has run its input against 1.4.0 carries it until the
comparison is made and it resolves to one of the three above. It is
not a standing category, and nothing enforces its removal -- a row
still wearing it is a row whose parity is simply unknown.

The v1 suite's full corpus is extracted into this table by the
migration plan (facade runner consumes the same rows); this file seeds
it with the pinned battery.

What earns a row is a FORK: a branch taken for one input and not
another -- a rule's boundary, a precedence contest between two rules,
a policy that changes the answer. A row demonstrating one more member
of a vocabulary set pins nothing its other members do not, and one row
per entry grows this table without narrowing what can break
(mechanisms.md#VOCABULARY-EXERCISES-FORKS -- a restatement, and
nothing checks it against the entry: test_doc_citations verifies an
excerpt only where the reference is followed by a colon and a quoted
span, which running prose like this one is not. Read the entry, not
this paragraph, if the two ever disagree).
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from nameparser import (FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST, GIVEN_FIRST,
                         Policy)
# Not in nameparser.__all__: _order_repr renders a name_order for an
# error message, Script/_SCRIPT_RANGES/_script_matcher build the same
# borrowed predicates build_cjk_corpus.py uses to find CJK text.
from nameparser._policy import (PatronymicRule, Script, _SCRIPT_RANGES,
                               _order_repr, _script_matcher)

#: mirrors tools/differential/shapes.py's SHAPES keys;
#: test_case_shape_ids_exist_in_the_inventory (test_ledger_guards.py)
#: holds the two equal, since this file cannot import tools/.
_SHAPE_IDS = frozenset({1, 2, 3, 4, 5, 6, 7})


def _has_ascii_letter(text: str) -> bool:
    """True when text contains an ASCII a-z/A-Z letter. Shapes 6/7's
    purity check calls this ALONGSIDE a comma test and a residue test
    that takes every OTHER non-space ASCII character -- this function
    tests neither a comma nor a non-ASCII Latin letter on its own. The
    ASCII restriction is deliberate: a diacritic or a letter
    outside a-z/A-Z is not what a Latin WRAPPER around CJK text looks
    like in the corpus today (title/credential vocabulary is ASCII),
    and widening this is a call for whichever future row needs it."""
    return any(c.isascii() and c.isalpha() for c in text)


def _stray_ascii(text: str) -> str:
    """The distinct ASCII characters in text other than a space,
    sorted, as one string ("" when there are none). The residue arm of
    shapes 6/7's purity test: the comma and the ASCII letter keep
    messages of their own because each names a composed form with its
    own doctrine, and this takes everything else -- a period, a digit,
    a parenthesis. A space is the one ASCII character a pure CJK
    arrangement writes (rules.md#W4's '山田 太郎'), so it is the one
    exemption."""
    return "".join(sorted({c for c in text if c.isascii() and c != " "}))


#: Shape 7's other admission besides an explicit divider: a
#: transcription written wholly in katakana with no dividing
#: punctuation at all (e.g. "マイケルジャクソン" or the spaced
#: "マイケル ジャクソン"). Built on the parser's own predicate --
#: _script_matcher(Script.KATAKANA, whole=True) -- rather than a
#: hand-copied codepoint range, so the KATAKANA span lives in exactly
#: one place (nameparser._policy._SCRIPT_RANGES). That table's choice,
#: not this file's: halfwidth katakana (a different Unicode block,
#: U+FF65-U+FF9F, per _policy.py's own comment) is out of scope.
#: Applied to the text with whitespace stripped, so a spaced
#: transcription still counts as wholly katakana; a whitespace-only
#: string never reaches this predicate in practice, since the purity
#: check's _has_cjk gate (a real classified codepoint) has already
#: run by the time shape 7 consults it.
_wholly_katakana = _script_matcher(Script.KATAKANA, whole=True)

#: Whether a text carries a codepoint the parser's script table
#: classifies -- built once, same idiom as build_cjk_corpus.py's
#: module-scope `_has_cjk`.
_has_cjk = _script_matcher(*_SCRIPT_RANGES)


@dataclass(frozen=True)
class Case:
    id: str
    text: str
    expect: dict[str, str]          # field -> value; absent fields == ""
    policy: Policy | None = None
    locale: str | None = None       # locale CODE (keeps this table
                                     # import-light); mutually exclusive
                                     # with policy
    classification: str = "parity"
    ambiguities: tuple[str, ...] = ()   # expected AmbiguityKind values
    notes: str = ""
    #: input-shape id from tools/differential/shapes.py (#468/#469).
    #: Tagging a row admits its text to the differential's CONTRACT
    #: corpus (see tools/differential/shapes.py, projected into
    #: corpus_shapes.jsonl by build_shapes_corpus.py beside it) under
    #: the shape's name_order. For shapes 6/7 that admission is
    #: NOMINAL: a pure CJK text is already in corpus_cjk.jsonl, also
    #: contract, and compare.py's (name, order) dedup collapses the
    #: two -- the tag buys the coverage answer, not a comparison.
    #: Optional: a row
    #: exercising a policy fork rather than an input shape stays
    #: untagged.
    shape: int | None = None
    #: Marks a row's text as TOLERATED input (2026-09-01 CJK demotion):
    #: read best-effort, exempt from the DIFFERENTIAL's contract tier
    #: -- not from this table, whose expectations are asserted by the
    #: suite either way, and a behavior change on a tolerated row still
    #: edits its classification. The opposite of a shape
    #: tag -- mutually exclusive with `shape`, since a shape ADMITS a
    #: text to the contract and tolerated deliberately does not. Every
    #: composed/wrapped CJK form (a comma listing, a Latin title or
    #: credential around a CJK name, since 2026-09-05 a trailing ASCII
    #: period on an honorific, and since #323 an edge full stop of any
    #: width on any CJK name word) is this table's ground for it,
    #: not shapes 6/7's. Restricted to CJK-bearing text (`_has_cjk`):
    #: it exists to demote composed/wrapped CJK forms specifically, and
    #: a Latin row asking for it is a smell until some future arc
    #: argues otherwise. build_cjk_corpus.py reads the flag: a
    #: tolerated row's text goes to the radar-tier
    #: corpus_cjk_tolerated.jsonl instead of the contract
    #: corpus_cjk.jsonl, and clearing the flag promotes it back at the
    #: next regeneration. Mark every row of a text, or none: the
    #: generator reads the flag per TEXT (a corpus line is a name
    #: string) and HARD-ERRORS on a split declaration, which
    #: __post_init__ cannot catch from inside one row.
    tolerated: bool = False

    def __post_init__(self) -> None:
        if self.policy is not None and self.locale is not None:
            raise ValueError(
                f"{self.id}: policy and locale are mutually exclusive")
        # A shape CARRIES its order (the 2026-09-01 corpus design), so
        # a tag that disagrees with the row's own policy would admit a
        # name to the corpus under an order the row never asserted.
        if self.shape is not None:
            if self.shape not in _SHAPE_IDS:
                raise ValueError(f"{self.id}: unknown shape {self.shape}")
            if self.shape in (6, 7):
                self._check_cjk_shape_purity()
            else:
                self._check_latin_shape_order()
        # tolerated is the opposite of a shape tag: a reviewed act
        # admitting a composed/wrapped CJK form to the radar corpus
        # rather than the contract one. Checked regardless of which
        # branch above ran (or whether shape was tagged at all), so a
        # row cannot smuggle both declarations onto one text.
        if self.tolerated:
            if self.shape is not None:
                raise ValueError(
                    f"{self.id}: tolerated is mutually exclusive with "
                    f"shape; a tolerated row is the opposite of admitted")
            if not _has_cjk(self.text):
                raise ValueError(
                    f"{self.id}: tolerated requires CJK text (a "
                    f"classified codepoint _has_cjk recognizes); it "
                    f"exists for the CJK comma demotion, and a Latin "
                    f"row asking for it is a smell until some future "
                    f"arc argues otherwise")

    def _check_latin_shape_order(self) -> None:
        """Shapes 1-5: the Latin-order arrangements, each implying a
        name_order the row's own policy (or its absence) must agree
        with, and each refusing CJK text outright."""
        # Contract: only called from the `if self.shape is not None`
        # branch above -- restated here (not just implied by the call
        # site) because it also narrows the type for mypy, which
        # cannot see across the method boundary on its own.
        assert self.shape is not None
        # A locale carries an order too (script_orders), but as a
        # LOOKUP this table cannot see -- cases.py stays
        # import-light and stores only the locale CODE. Faking
        # "declared" as GIVEN_FIRST for a locale row would let a
        # tag validate against an order nobody here can name.
        if self.locale is not None:
            raise ValueError(
                f"{self.id}: a shape tag needs the row's own "
                f"policy; a locale carries an order this table "
                f"cannot see")
        # Shapes 1-5 are the LATIN-ORDER arrangements -- a title
        # slot, a comma listing, a suffix run -- and CJK text does
        # not instantiate one: the arrangement is what the shape id
        # names, so tagging a CJK string shape 1 asserts a form the
        # string does not have. The CJK arrangements are shapes 6/7
        # (#469's now-settled third-shape question), where the same
        # text is admitted under a purity test of its own. (That
        # shapes 6/7 do double-admit into corpus_cjk.jsonl is fine
        # and deliberate -- the dedup collapses it; double admission
        # is not what this check is about.)
        # Order alone cannot stand in for this check --
        # DEFAULT_SCRIPT_ORDERS forces HAN/HANGUL/HIRAGANA to
        # FAMILY_FIRST but leaves KATAKANA unmapped, so a pure-
        # katakana text can carry a GIVEN_FIRST name_order and
        # still be CJK ground, not a shape.
        if _has_cjk(self.text):
            raise ValueError(
                f"{self.id}: shape {self.shape} cannot tag CJK "
                f"text; that ground belongs to shapes 6/7 "
                f"(corpus_cjk.jsonl), not this shape")
        declared = (self.policy.name_order if self.policy is not None
                    else GIVEN_FIRST)
        wanted = {4: FAMILY_FIRST, 5: FAMILY_FIRST_GIVEN_LAST}.get(
            self.shape, GIVEN_FIRST)
        if declared != wanted:
            if self.policy is not None:
                declared_desc = (
                    f"the row's policy declares {_order_repr(declared)}")
            else:
                declared_desc = ("this row declares no policy, so it "
                                  "is GIVEN_FIRST")
            raise ValueError(
                f"{self.id}: shape {self.shape} implies name_order "
                f"{_order_repr(wanted)}, but {declared_desc}; add "
                f"policy=Policy(name_order={_order_repr(wanted)}) or "
                f"drop the tag")

    def _check_cjk_shape_purity(self) -> None:
        """Shapes 6/7 (2026-09-01): the CJK arrangements, admitted
        wholly classified-script text only -- no ASCII character at
        all except the space between two name words (WIDENED
        2026-09-05: the check read 'no comma, no Latin letter', which
        admitted the trailing-period honorifics '田中さん 様.' and
        '김민준 씨.' -- a listing artifact no writing system produces,
        and the same class as the forms it was already refusing).
        Every composed/wrapped form is tolerated=True's
        ground, not a shape tag's, so this REFUSES rather than
        requires a particular arrangement beyond that purity test
        (plus shape 7's divider/katakana requirement, and shape 6's
        interpunct refusal, below)."""
        # Contract: only called from the `if self.shape in (6, 7)`
        # branch above -- restated here (not just implied by the call
        # site) because it also narrows the type for mypy, which
        # cannot see across the method boundary on its own.
        assert self.shape in (6, 7)
        # A zh-pack row exercises a locale FORK (the segmenter, an
        # opt-in policy choice), not an input shape: the default-
        # policy reading of the same string is what the shape admits,
        # so shape 6/7 rows carry neither. (Nothing separately checks
        # self.policy here because shapes 6/7's order is None --
        # there is no order for a policy to agree or disagree with --
        # so a stray policy would silently do nothing; refusing both
        # together keeps the row's intent legible.)
        if self.policy is not None or self.locale is not None:
            raise ValueError(
                f"{self.id}: shape {self.shape} rows carry neither "
                f"policy nor locale; a zh-pack row exercises a locale "
                f"fork, not an input shape")
        if not _has_cjk(self.text):
            raise ValueError(
                f"{self.id}: shape {self.shape} requires a classified "
                f"codepoint (CJK text); {self.text!r} carries none")
        if "," in self.text:
            raise ValueError(
                f"{self.id}: shape {self.shape} refuses a comma; "
                f"composed comma forms belong under tolerated=True, "
                f"not a shape tag")
        if _has_ascii_letter(self.text):
            raise ValueError(
                f"{self.id}: shape {self.shape} refuses a Latin "
                f"letter; Latin-wrapped compositions belong under "
                f"tolerated=True, not a shape tag")
        # The residue, after the two forms with doctrine of their own:
        # a space is the only ASCII character a pure CJK arrangement
        # writes, so anything else ASCII came in with a convention
        # from elsewhere -- a trailing period, a digit, a bracket --
        # and is a composed form whatever it is called.
        stray = _stray_ascii(self.text)
        if stray:
            raise ValueError(
                f"{self.id}: shape {self.shape} refuses the ASCII "
                f"{stray!r} ({self.text!r}); a space is the only "
                f"ASCII character a pure arrangement carries, and "
                f"composed forms belong under tolerated=True, not a "
                f"shape tag")
        # U+00B7 (间隔号) marks a name transcription in SOURCE order
        # (W1 Accepted) -- shape 7's ground, not shape 6's family-
        # first one. The fullwidth nakaguro U+30FB is NOT a source-
        # order marker on its own: decisions.md#T3 scopes that reading
        # to the codepoint, so U+30FB on non-katakana text is an
        # ordinary Han/Hangul separator and the text reads family-
        # first (cases.py's own ja_nakaguro_han_takes_the_han_order,
        # '高橋・一郎', pins exactly this). A wholly-katakana text
        # DOES read as a transcription regardless of whether it
        # happens to contain U+30FB internally -- that admission comes
        # from being wholly katakana, not from the nakaguro -- so
        # _wholly_katakana already covers the katakana case and U+30FB
        # is not tested as a divider here at all.
        has_divider = "·" in self.text
        stripped = "".join(self.text.split())
        is_transcription = has_divider or _wholly_katakana(stripped)
        if self.shape == 6:
            if is_transcription:
                raise ValueError(
                    f"{self.id}: shape 6 refuses U+00B7 and wholly-"
                    f"katakana text; that reads source order and "
                    f"belongs to shape 7")
        else:
            if not is_transcription:
                raise ValueError(
                    f"{self.id}: shape 7 requires U+00B7 or wholly-"
                    f"katakana text; {self.text!r} has neither")


_ES = Policy(patronymic_rules=frozenset({PatronymicRule.EAST_SLAVIC}))
_TK = Policy(patronymic_rules=frozenset({PatronymicRule.TURKIC}))
_SD = Policy(extra_suffix_delimiters=frozenset({" - "}))

CASES: tuple[Case, ...] = (
    Case("plain", "John Smith", {"given": "John", "family": "Smith"},
         notes="shape 1's bare Given Family arrangement, the floor the "
               "other shape-1 rows vary from",
         shape=1),
    Case("family_comma", "Smith, John",
         {"given": "John", "family": "Smith"},
         notes="shape 2's bare Family, Given arrangement",
         shape=2),
    Case("suffix_comma", "John Smith, PhD",
         {"given": "John", "family": "Smith", "suffix": "PhD"},
         notes="shape 3's bare Given Family, Suffix arrangement",
         shape=3),
    Case("bound_given_pairwise_only", "Salem, Abdul Rahman Ahmed",
         {"given": "Abdul Rahman", "middle": "Ahmed", "family": "Salem"},
         notes="the bound-given join is PAIRWISE (one merge, v1 "
               "parity): the third piece stays a middle name. Shape "
               "2's post-comma given slot, at the arity where the "
               "join stops",
         shape=2),
    Case("family_comma_three_part_trailing_strict", "Smith, John V, Jr.",
         {"given": "John", "middle": "V", "family": "Smith",
          "suffix": "Jr."},
         notes="the lenient trailing test applies only to TWO-part "
               "names; a third comma part makes the trailing token a "
               "middle initial (v1 parity, pinned live 2026-07-17). "
               "Shape 2's trailing suffix WITH the optional comma "
               "written; family_comma_run_with_a_name_is_not_a_run is "
               "the spelling without it",
         shape=2),
    Case("triple_trailing_commas", "Doe,,,",
         {"family": "Doe"},
         notes="one trailing comma is cosmetic; the rest are "
               "structural empties (pinned live 2026-07-17)"),
    Case("paren_suffix_word_escapes_nickname", "John Smith (Esq)",
         {"given": "John", "family": "Smith", "suffix": "Esq"},
         notes="the suffix_words branch of the delimited-content "
               "escape (v1 parity, pinned live 2026-07-17)"),
    Case("the_removed_esq_spelling_returns_as_a_credential",
         "John Smith E.S.Q.",
         {"given": "John", "family": "Smith", "suffix": "E.S.Q."},
         classification="fix(#516)",
         ambiguities=("suffix-or-name",),
         notes="1.4.0 RESTORED a SECOND time, by a different route "
               "than it lost it. 'esq' left SUFFIX_ACRONYMS 2026-09-08: "
               "Esquire is a contraction, not an initialism, the entry "
               "arrived in the 2019 bulk post-nominal import "
               "(af5bdab, #93), and the multi-dot spelling was its "
               "only unique coverage -- so for one bundle this read "
               "family 'E.S.Q.' (a deliberate 2.x parity break, "
               "decisions.md#suffix-acronym-collisions; same criterion "
               "as the rai/cha rows above, asked of the machinery "
               "instead of a surname: does the entry describe the "
               "WORD or the set's normalization; the bundle that "
               "carried the removal is #489/#316). #516's by-shape "
               "class reads it again now, with no wordlist entry at "
               "all: an unlisted dotted token of three single-letter "
               "chunks joins the ambiguous class by SHAPE and the "
               "words-to-spare count reads it as the credential it is",
         shape=1),
    Case("suffix_acronym_multidot_after_a_family_comma",
         "Smith, E.S.Q.",
         {"given": "E.S.Q.", "family": "Smith"},
         classification="parity",
         ambiguities=("suffix-or-name",),
         notes="the other path the same removal moved, once -- with "
               "'esq' in SUFFIX_ACRONYMS the multi-dot spelling was a "
               "suffix piece, so the post-comma segment held no name "
               "word and read suffix 'E.S.Q.' (2.0.0 through 2.2.0); "
               "out of the set it briefly restored 1.4.0 instead, "
               "first 'E.S.Q.' / last 'Smith' (measured 2026-09-09). "
               "#516's by-shape class now reads the SAME single "
               "pre-comma word as a candidate for the ambiguous class "
               "-- one word is never enough to flip the structure "
               "(rules.md#C1), so the FIELDS stay at the 1.4.0 "
               "reading, but the class is now considered, and the "
               "consideration reports: the parity note above is about "
               "the reading, not about whether a fork was called",
         shape=2),
    Case("suffix_word_esq_still_reads_as_a_suffix", "John Smith Esq",
         {"given": "John", "family": "Smith", "suffix": "Esq"},
         notes="the other half of the row above, and what the removal "
               "rests on: the SUFFIX_WORDS membership carries every "
               "single-token spelling on its own, so it stops being "
               "inert rather than becoming dead. Deleting 'esq' there "
               "too is what this row refuses. 'Esquire' rides the "
               "same membership and is deliberately unpinned, being "
               "one more word in a set rather than a fork "
               "(mechanisms.md#VOCABULARY-EXERCISES-FORKS); the "
               "dotted 'John Smith Esq.', the comma form 'Smith, "
               "Esq.' and the leading 'Esq. Smith' each have a row of "
               "their own below"),
    Case("bound_given_whole_segment", "salem, abdul salam",
         {"given": "abdul salam", "family": "salem"},
         notes="v1 joins bound given names freely in the post-comma "
               "segment (reserve_last=False, parser.py:1366) -- even "
               "when the join consumes the whole segment"),
    Case("middle_as_family_fold_order", "Hassan, Mohamad Ahmad Ali",
         {"given": "Mohamad", "family": "Ahmad Ali Hassan"},
         policy=Policy(middle_as_family=True),
         notes="v1 PREPENDED middle_list to last_list; folded tokens "
               "carry vocab:folded-middle and every view of them orders "
               "them first (spans cannot reorder). This table has no "
               "initials column, so the half #408 moved is pinned in "
               "rules.md#R3 and tests/v2/test_render.py: initials were "
               "'M. H. A. A.' here and are 'M. A. A. H.' now, which is "
               "also 1.4.0's answer. Since #484 the differential compares "
               "initials() too, for names whose roles are identical -- "
               "but only under the policies it runs, and middle_as_family "
               "is not one, so this row stays pinned here"),
    # MOVED by #289, not deleted: 'MA' is written in capitals inside a
    # mixed-case name, so it now leans CREDENTIAL and is taken with no
    # words to spare -- the reserve/count this row used to pin no
    # longer decides here, the written case does (decisions.md#S2).
    Case("ambiguous_surname_acronyms", "Jack MA",
         {"given": "Jack", "suffix": "MA"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name", "given-or-family"),
         notes="the defect #289 reports: an all-caps member of the "
               "ambiguous set inside a mixed-case name is written the "
               "way a credential is written, so it is taken as one "
               "even though peeling it leaves no family -- what "
               "'Jack MD' has always done with an unambiguous one. "
               "'Jack' is then the only name word left, which is also "
               "what turns on GIVEN_OR_FAMILY. 1.4.0 read LAST 'MA' "
               "here (family 'MA'), so this row BREAKS 1.4.0 parity "
               "deliberately, in the direction the East Asian surname "
               "wants (decisions.md#S2) -- corrected 2026-09-17, F3 "
               "review finding: an earlier version of this note "
               "wrongly claimed the opposite"),
    Case("ambiguous_surname_acronym_with_suffix", "Jack MA Jr",
         {"given": "Jack", "suffix": "MA Jr"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name", "given-or-family"),
         notes="'Jr' peels first as unambiguous vocabulary; 'MA' is "
               "then the last piece, and the caps lean takes it with "
               "no words to spare rather than leaving it the family "
               "the old reserve kept (decisions.md#S2) -- both suffix "
               "words render as one run"),
    Case("ambiguous_acronym_is_a_suffix_when_a_family_name_remains",
         "John Smith MA",
         {"given": "John", "family": "Smith", "suffix": "MA"},
         ambiguities=("suffix-or-name",),
         notes="the other half of the same rule: three pieces means "
               "peeling 'MA' still leaves given+family, so the "
               "credential reading wins (v1 parity)"),
    # -- #342: rai and cha left SUFFIX_ACRONYMS. The criterion is in
    # decisions.md#suffix-acronym-collisions and it compares
    # FREQUENCIES: how common the word is as a borne name in the
    # trailing position against how common it is as a credential.
    # Rough balance earns the ambiguous marking (ba, do, ed, jd, ma);
    # the name reading dominating REMOVES the entry, a caller adding
    # it back with Lexicon.default().add(suffix_acronyms={"cha"});
    # the credential dominating leaves it unambiguous. Length is a
    # correlate, not the test. These rows pin
    # the FORK, not the entries (mechanisms.md#VOCABULARY-EXERCISES-FORKS).
    Case("bare_surname_is_not_a_credential", "Aishwarya Rai",
         {"given": "Aishwarya", "family": "Rai"},
         classification="parity",
         notes="#342's own subject: 'rai' arrived in the 2019 bulk "
               "wikipedia post-nominal import and was never reviewed "
               "against the surname, so 2.0.0 through 2.2.0 read "
               "suffix 'Rai' with NO family name at all. 1.4.0 read "
               "family 'Rai' and this restores that reading, which is "
               "why it classifies parity rather than fix, and why "
               "the 1.4.0 ledger replaces a NOT WANTED rule where the "
               "three 2.x ledgers gain a new one, and its heading "
               "explains four names where theirs explain five. Named "
               "in the release note"),
    Case("removed_credential_loses_its_suffix_reading", "John Smith RAI",
         {"given": "John", "middle": "Smith", "family": "RAI"},
         classification="fix(#342)",
         notes="the accepted cost, pinned so the reversal is visible. "
               "RAI is a real if specialized credential and a full "
               "name in front of it used to be enough to read it as "
               "one; with the entry gone the all-caps shape carries "
               "no signal the parser reads, so the word families and "
               "'Smith' becomes a middle name. The shape-plus-position "
               "heuristic that would recover it is a parking-lot "
               "bullet of decisions.md#suffix-acronym-collisions"),
    Case("removed_credential_after_a_comma_reads_as_the_given_name",
         "Ahmad Jayadi, CHA",
         {"given": "CHA", "family": "Ahmad Jayadi"},
         classification="fix(#342)",
         notes="the comma form moves the OTHER way and is why the "
               "ledger rule declares four fields rather than two. "
               "With 'cha' gone the comma is an ordinary family "
               "comma (C1): the pre-comma run is the family and the "
               "post-comma word is the given name. 'John Smith, RAI' "
               "is the same shape and moves with it"),
    Case("removed_credential_loses_the_dotted_spelling_too",
         "John Smith C.H.A.",
         {"given": "John", "family": "Smith", "suffix": "C.H.A."},
         classification="fix(#516)",
         ambiguities=("suffix-or-name",),
         notes="for one bundle the removal reached the DOTTED spelling "
               "through S3's period fold, which strips the periods to "
               "reach the entry -- so with 'cha' gone this read family "
               "(the contrast was 'John Smith R.A.I.', which kept "
               "reading suffix as an accident of 'i' being a "
               "SUFFIX_WORDS numeral rather than a survival of the "
               "vocabulary, decisions.md#suffix-acronym-collisions). "
               "#516's by-shape class now reads BOTH the same way, by "
               "POSITION rather than by any chunk claim -- three "
               "single-letter chunks, none of them vocabulary, still "
               "join the ambiguous class by shape and the words-to-"
               "spare count reads this one a credential too",
         shape=1),
    # -- #342: 'ba' is the other half of the same decision. BA is a
    # common credential and Ba a real surname (Vietnamese; Senegalese
    # Fula), which is the ma/Ma shape exactly, so it takes the
    # marking rather than the removal. Two rows, the two halves of
    # S2's words-to-spare guard; the release note names both texts.
    Case("bare_ba_is_a_surname", "Anna Ba",
         {"given": "Anna", "family": "Ba"},
         ambiguities=("suffix-or-name",),
         classification="parity",
         notes="the marking's point: with only two pieces, 'one of "
               "them is a credential' is the less likely reading, so "
               "S2's words-to-spare guard keeps the family name and "
               "the parse reports which reading it took. 2.0.0 "
               "through 2.2.0 read suffix 'Ba' with no family name; "
               "1.4.0 read family 'Ba' unflagged, so this row "
               "restores 1.4.0's roles and adds the flag"),
    # MOVED by #289, not deleted: 'BA' is written in capitals inside a
    # mixed-case name, so it now leans CREDENTIAL and the post-comma
    # slot takes it with one word to spare where the count alone would
    # not -- back to what 2.0.0 through 2.2.0 read, though for a
    # different reason (decisions.md#S2, Derek's own #289 comment:
    # positive evidence outranks position here).
    Case("comma_ambiguous_acronym_ba", "Smith, BA",
         {"family": "Smith", "suffix": "BA"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="the marking's comma cost, and it is 'Smith, Ed' "
               "arriving for a second word: with 'ba' ambiguous, S2 "
               "declines the post-comma credential and C1 reads it as "
               "the given name. 2.0.0 through 2.2.0 read family "
               "'Smith', suffix 'BA'; 1.4.0 read given 'BA'. #289 moves "
               "this row again: the caps lean now reads 'Smith, BA' the "
               "way a business form is written"),
    Case("ba_is_a_suffix_when_a_family_name_remains", "John Smith BA",
         {"given": "John", "family": "Smith", "suffix": "BA"},
         ambiguities=("suffix-or-name",),
         notes="the words-to-spare half: a full name in front leaves "
               "the credential reading available, so the role does "
               "NOT move -- only the flag is new. The twin of "
               "ambiguous_acronym_is_a_suffix_when_a_family_name_remains "
               "above"),
    Case("by_design_trailing_mc_reads_as_a_credential", "Donald Mc",
         {"given": "Donald", "suffix": "Mc"},
         classification="fix(suffix-routing)",
         ambiguities=("given-or-family",),
         notes="#454, dispositioned by design with this bundle. "
               "1.4.0 read last 'Mc'; the 1.4.0 ledger's "
               "fix(suffix-routing) rule -- a two-token name ending "
               "in a credential acronym keeps it in `suffix` -- is "
               "what explains the divergence. This is the one "
               "row whose point is that it must NOT change. 'mc' is "
               "SUFFIX_ACRONYMS and PARTICLES both, and it is not a "
               "borne name: it has no vowel, and the Scottish prefix "
               "never detaches from the name it belongs to, so "
               "'Donald Mc' is not a name anyone writes and its "
               "suffix reading costs nothing real. rules.md#P6's "
               "attachment is scoped to shapes where something has "
               "already named the family, which this has not, so S2 "
               "takes the trailing word -- 'an unambiguous suffix is "
               "consumed even when that leaves no family name at "
               "all'. The neighbours that DO hold: 'Mc Donald' reads "
               "family 'Mc Donald' and 'John van Mc' family 'van "
               "Mc', both because 'mc' is a never-given particle "
               "(#360), which is the membership that actually bears "
               "on #454's example. See "
               "decisions.md#suffix-acronym-collisions. The peel "
               "leaves 'Donald' the only name word, so O5's "
               "convention places it and says so (#449): roles "
               "parity, the flag is #449's"),
    Case("ambiguous_acronym_suffix_with_middle", "John Q Smith MA",
         {"given": "John", "middle": "Q", "family": "Smith",
          "suffix": "MA"},
         ambiguities=("suffix-or-name",)),
    Case("titled_ambiguous_particle_does_not_chain", "Dr. Van Johnson",
         {"title": "Dr.", "given": "Van", "family": "Johnson"},
         classification="fix(#367)",
         ambiguities=("particle-or-given",),
         notes="reads exactly as the untitled 'Van Johnson' does, "
               "because a title is not part of the name and so cannot "
               "decide whether the NAME begins with a particle (#367). "
               "This row pinned the opposite until 2.2 -- title 'Dr.', "
               "family 'Van Johnson', the chain having fired because "
               "the title shifted Van off piece index 0 -- and cited "
               "v1 parity for it. Parity was real (1.4.0 gives last "
               "'Van Johnson') and still not the tiebreaker it looked "
               "like: this is the SAME shape as 'Mr. Van Nguyen', "
               "which v1 shipped as an xfail calling the reading "
               "wrong, so v1 pinned one shape both as correct and as "
               "broken. Resolved toward the xfail, which now passes "
               "(tests/test_first_name.py::"
               "test_first_name_is_prefix_if_three_parts). The fork is "
               "still reported, from assign rather than group -- the "
               "same place the untitled 'Van Johnson' reports it"),
    Case("titled_ambiguous_particle_keeps_its_middles", "Dr. Van Johnson Smith",
         {"title": "Dr.", "given": "Van", "middle": "Johnson",
          "family": "Smith"},
         classification="fix(#367)",
         ambiguities=("particle-or-given",),
         notes="the release log names this shape and nothing asserted "
               "it. 1.4.0 gives title 'Dr.', last 'Van Johnson Smith'; "
               "un-chaining leaves three name pieces, so the middle "
               "appears where the whole thing used to be one surname"),
    Case("given_name_title_ambiguous_particle", "Sir Van Johnson",
         {"title": "Sir", "given": "Van", "family": "Johnson"},
         classification="fix(#367)",
         ambiguities=("particle-or-given",),
         notes="a GIVEN-NAME title, which is the worse half of the bug "
               "#367 fixed: 1.4.0 and 2.1 alike gave first "
               "'Van Johnson' and no family name at all, the chain "
               "having fired and then been handed whole to `given`. "
               "Now identical to the untitled 'Van Johnson'"),
    Case("given_name_title_never_given_particle", "Sir de Mesnil",
         {"title": "Sir", "family": "de Mesnil"},
         classification="fix(#367)",
         notes="the never-given half: `de` is not an ambiguous "
               "particle, so there is no fork to report and post_rules "
               "1b folds the name into the family. 1.4.0 and 2.1 gave "
               "first 'de Mesnil' with no family, because the chain "
               "left 1b nothing standing alone to fire on"),
    Case("title_plus_one_word_with_maiden", "Dr. Smith née Jones",
         {"title": "Dr.", "family": "Smith", "maiden": "Jones"},
         classification="fix(#410)",
         notes="H1's 'and nothing else' counted a maiden name as a "
               "further name word, so adding a maiden clause moved the "
               "surname into `given` and emptied `family`: 'Dr. Smith' "
               "reads family 'Smith' and 'Dr. Smith née Jones' read "
               "given 'Smith'. A maiden name is announced beside the "
               "name, not part of it. 1.4.0 had no maiden SUPPORT -- "
               "the field exists, but no default marker vocabulary "
               "routes to it -- and read first 'Smith', middle 'née', "
               "last 'Jones'"),
    Case("title_plus_one_word_with_maiden_particle_spelling",
         "Freiherr von Richthofen geb. Albrecht",
         {"title": "Freiherr", "family": "von Richthofen",
          "maiden": "Albrecht"},
         classification="fix(#410)",
         ambiguities=("particle-or-given",),
         notes="the spelling #410 was found through: #399 stopped the "
               "particle chain at the marker, which routed the "
               "canonical title-and-particle shape into H1 for the "
               "first time and so into this bug. 1.4.0 read the whole "
               "tail as one surname, last 'von Richthofen geb. "
               "Albrecht'"),
    Case("given_name_title_plus_one_word_with_maiden",
         "Sir John née Jones",
         {"title": "Sir", "given": "John", "maiden": "Jones"},
         classification="fix(#274)",
         notes="H1's carve-out is untouched by #410: a given-name "
               "title addresses by given name, so the one name word "
               "stays `given` and the family stays empty, exactly as "
               "'Sir John' reads -- in the DEFAULT order, which is "
               "what this row pins: under either family-first order "
               "the same name reads family 'John', H1 being a no-op "
               "there because assign has already placed the word. "
               "The boundary of the widening, and "
               "the row that fails if the retag is made unconditional. "
               "The fix classification is #274's marker consumption, "
               "which is what makes this differ from 1.4.0 (first "
               "'John', middle 'née', last 'Jones')"),
    Case("title_plus_one_word_comma_suffix", "Dr. King, Jr.",
         {"title": "Dr.", "family": "King", "suffix": "Jr."},
         ambiguities=("title-or-name",), classification="fix(#410)",
         notes="the most ordinary shape H1's widening touches, and "
               "the one the suite could least afford to leave "
               "unpinned: mutating H1 to decline on any name carrying "
               "a comma left all 5819 tests green. Nothing else sees "
               "the class -- the corpus-wide maiden-clause property "
               "test filters commas out of its parametrization "
               "(_clause_free_latin_corpus_names), and "
               "'Smith, Dr.' takes its family from the comma rule "
               "(C1), not from H1. 1.4.0 had the same empty family "
               "here (title 'Dr.', first 'King', last ''), so this "
               "row records a v1 bug fixed, not a v2 divergence. The "
               "`title-or-name` flag is H4's and not #410's: `king` is "
               "title vocabulary and a suffix beside the word is not a "
               "shape that silences the convention"),
    Case("title_plus_one_word_multi_word_maiden",
         "Dr. Smith née Mary Jones",
         {"title": "Dr.", "family": "Smith", "maiden": "Mary Jones"},
         classification="fix(#410)",
         notes="the maiden name at two words rather than one. H1 "
               "counts what stands in the NAME, so the arity of the "
               "clause beside it is irrelevant -- a rule that "
               "declined on a second maiden token would pass every "
               "single-word row above. 1.4.0 read first 'Smith', "
               "middle 'née Mary', last 'Jones'"),
    Case("given_name_title_plus_one_word_multi_word_maiden",
         "Sir John née Mary Jones",
         {"title": "Sir", "given": "John", "maiden": "Mary Jones"},
         classification="fix(#410)",
         notes="the carve-out at the same arity: 'whatever maiden "
               "name stands beside it' has to leave the given-name "
               "title alone however long the clause is. Without this "
               "row the `whatever` is asserted only at one word. "
               "1.4.0 read first 'John', middle 'née Mary', last "
               "'Jones'"),
    Case("title_plus_one_word_two_suffixes", "Dr. Smith PhD Jr.",
         {"title": "Dr.", "family": "Smith", "suffix": "PhD Jr."},
         classification="fix(#410)",
         notes="two suffix pieces, not one. The removed term asked "
               "whether ANY token carried a suffix role, so a guard "
               "rebuilt to decline on the SECOND one would look "
               "correct against every row that carries a single "
               "credential. 1.4.0 split them, reading first 'Smith', "
               "last 'PhD', suffix 'Jr.'. The comma between them was "
               "the shape machinery's artifact and never a reading "
               "anyone chose: the writer typed no comma, so #436 "
               "renders none (rules.md#R1)"),
    Case("title_plus_one_word_nickname_and_suffix",
         "Dr. (Bud) Smith Jr.",
         {"title": "Dr.", "family": "Smith", "suffix": "Jr.",
          "nickname": "Bud"},
         classification="fix(#410)",
         notes="two DIFFERENT annotations at once, which is the "
               "combination the single-annotation rows cannot reach: "
               "a guard declining only where a nickname and a suffix "
               "are both present passes all of them. 1.4.0 read first "
               "'Smith', last 'Jr.' with nickname 'Bud' -- the "
               "credential taking the family slot"),
    # The smallest shape in which the two family-first orders can
    # disagree about this rule's leftovers: with one leftover both
    # send it to `given`, and two or more is what separates them (the
    # orders differ on plenty of names outside this rule -- 186 of the
    # 751 corpus names -- so the claim is about the fold, not about
    # the orders). Spanish because the listing is real: "Apellidos
    # Nombres" keeps the particle in place, where Dutch moves it
    # behind the given name ("Jong, Jan Pieter de", the tussenvoegsel
    # convention -- rule P6's subject, though P6's attachment is
    # deviates: #379, so that spelling does not yet parse the way P6
    # describes). Added before #395 landed, when all three orders
    # still agreed, each taking the whole name into the family.
    Case("leading_never_given_particle_two_leftovers",
         "de la Cruz Juan Carlos",
         {"family": "de la Cruz Juan Carlos"},
         classification="parity",
         notes="the DEFAULT order, which #395 leaves alone: with no "
               "order declared there is no evidence that 'Juan Carlos' "
               "is anything but more surname, and a particle followed "
               "by several words really can be all surname -- 'von "
               "Bergen Wessels' is one. (An earlier draft cited "
               "'pennie von bergen wessels' as the same SHAPE, which "
               "it is not: pennie is the given name there and von is "
               "ambiguous, so this fold cannot fire on it. See "
               "decisions.md#P1, 2026-08-17.) 1.4.0 gives last 'de la "
               "Cruz Juan Carlos' too, so this row must not move when "
               "#395 lands. #471 DECLINED 2026-09-07: the reach is "
               "the reading and not a gap in one -- a declared order "
               "is a property of the data source, so under the "
               "default order nothing has said this surname ends "
               "before the string does. See decisions.md#P1"),
    Case("leading_never_given_particle_two_leftovers_family_first",
         "de la Cruz Juan Carlos",
         {"family": "de la Cruz", "given": "Juan", "middle": "Carlos"},
         policy=Policy(name_order=FAMILY_FIRST),
         classification="feat(#395)",
         notes="core-only: name_order has no v1 spelling. The run "
               "stops at 'Cruz' because the declared order says what "
               "follows the family is not more surname. It reaches "
               "'Cruz' THROUGH ambiguous 'la', which is the chain a "
               "stop keyed on never-given membership would break",
         shape=4),
    Case("leading_never_given_particle_two_leftovers_"
         "family_first_given_last",
         "de la Cruz Juan Carlos",
         {"family": "de la Cruz", "middle": "Juan", "given": "Carlos"},
         policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST),
         classification="feat(#395)",
         notes="the row that makes the leftover DISTRIBUTION testable, "
               "and the divergence is here: FAMILY_FIRST reads 'Juan' "
               "as the given name, this order reads 'Carlos'. Nothing "
               "with fewer leftovers can tell the two apart. When "
               "PR #394 put the placing in grouping, its review found "
               "the whole suite passed with name_order discarded from "
               "it; on this branch the same mutation fails three "
               "tests, this row among them",
         shape=5),
    # The Dutch alphabetized listing: "Beethoven, Ludwig van" is how
    # "Ludwig van Beethoven" is filed, the tussenvoegsel moved behind
    # the given name but belonging to the surname (#379).
    Case("tussenvoegsel_after_family_comma", "Beethoven, Ludwig van",
         {"given": "Ludwig", "family": "van Beethoven"},
         classification="fix(#379)",
         ambiguities=("particle-or-given",),
         notes="1.4.0 gives middle 'van', last 'Beethoven'. The "
               "particle attaches to the family the comma already "
               "named and renders before it, so the derived views "
               "move with it -- family_particles 'van', family_base "
               "'Beethoven', which is what #130 asked for. The "
               "textbook-correct Dutch listing reports the fork all "
               "the same (#405): the parser cannot tell it from "
               "'Nguyen, Thi Van', which is the same string shape. "
               "Shape 2's particle slot in the tussenvoegsel "
               "spelling, where the particle stands behind the given "
               "name rather than before the family",
         shape=2),
    Case("tussenvoegsel_multiword", "Berg, Jan van der",
         {"given": "Jan", "family": "van der Berg"},
         classification="fix(#379)",
         ambiguities=("particle-or-given",),
         notes="the whole run attaches, not just its last word -- and "
               "one report covers the whole run, named for 'van', the "
               "word that is ambiguous vocabulary ('der' is never a "
               "given name)"),
    Case("tussenvoegsel_outranks_the_suffix_reading", "Berg, Jan vd",
         {"given": "Jan", "family": "vd Berg"},
         classification="fix(#380)",
         ambiguities=("suffix-or-name",),
         notes="'vd' is particle AND suffix vocabulary, and assign "
               "read the trailing one as a post-nominal (1.4.0 and "
               "2.1 alike gave suffix 'vd'). After a family comma the "
               "tussenvoegsel abbreviation is far more often the "
               "reading meant; P6 states that precedence over S2. "
               "The declined post-nominal is what the report names "
               "(#405), so the kind is suffix-or-name and not "
               "particle-or-given -- 'vd' is no given name in either "
               "reading. Also the control for #531's P6 condition, "
               "which declines a piece that is one token, roled SUFFIX "
               "and carries `vocab:suffix-ambiguous`: 'vd' is "
               "UNAMBIGUOUS suffix vocabulary, so it carries no such "
               "tag and stays inside P6's run -- byte-identical before "
               "and after #531. Narrowing that condition to the "
               "ambiguous tag is what buys it"),
    Case("tussenvoegsel_behind_a_post_nominal", "Berg, Jan van Jr.",
         {"given": "Jan", "family": "van Berg", "suffix": "Jr."},
         classification="fix(#379)",
         ambiguities=("particle-or-given",),
         notes="the credential sits BEHIND the tussenvoegsel in this "
               "listing, so the run is found by walking past it. "
               "Without that walk the same name parsed two ways on "
               "whether a comma preceded the credential -- "
               "'Berg, Jan van, Jr.' attached and this one did not"),
    Case("tussenvoegsel_declines_with_no_given_word_left",
         "Smith, de Mesnil van",
         {"family": "Smith de Mesnil van"},
         classification="fix(comma-precomma-family)",
         notes="P1's fold has already made all of segment 1 the "
               "family, so no GIVEN word remains and the "
               "attachment declines. Testing for any NAME role here "
               "instead would pass on family text P1 just produced, "
               "and hoist 'van' in front of a base it never preceded "
               "('van Smith de Mesnil'). NOT parity: 1.4.0 leaves no "
               "given name either, but renders last 'de Mesnil van "
               "Smith' -- it treats only the leading 'de' as a "
               "last-prefix and leaves 'van' inside the base. The "
               "structure agrees, the string does not"),
    Case("tussenvoegsel_behind_a_comma_post_nominal",
         "Berg, Jan van, Jr.",
         {"given": "Jan", "family": "van Berg", "suffix": "Jr."},
         classification="fix(#379)",
         ambiguities=("particle-or-given",),
         notes="the credential in its own comma segment, which is the "
               "spelling the no-comma row is defined against -- both "
               "must read the same, and gating the rule on a two"
               "-segment name silently reverts this one"),
    Case("tussenvoegsel_behind_a_title", "Berg, Dr. Jan van",
         {"title": "Dr.", "given": "Jan", "family": "van Berg"},
         classification="fix(#379)",
         ambiguities=("particle-or-given",),
         notes="the words-to-spare test asks whether ANY word ahead "
               "of the run holds a given role, not whether all of "
               "them do: the title does not, and the rule must still "
               "fire. decisions.md#P6 calls that guard load-bearing"),
    Case("tussenvoegsel_takes_the_vietnamese_reading", "Nguyen, Thi Van",
         {"given": "Thi", "family": "Van Nguyen"},
         classification="fix(#379)",
         ambiguities=("particle-or-given",),
         notes="the accepted cost, pinned so it cannot move without "
               "someone deciding to move it: Nguyen Thi Van is "
               "family-middle-given, so the given name Van is lost "
               "here. The listing is identical to the Dutch one and "
               "nothing separates them. The comma-less "
               "FAMILY_FIRST_GIVEN_LAST spelling reads it correctly -- "
               "that ONE order, not family-first generally, which #467 "
               "made load-bearing by giving comma-less FAMILY_FIRST the "
               "same attachment (there it reads family Van Nguyen too). "
               "That surviving format is what makes the "
               "loss acceptable -- see rules.md#P6. Since #405 the "
               "loss is at least REPORTED: 'Van' is ambiguous "
               "vocabulary, so the attachment declines a live reading "
               "as a name word and says so"),
    Case("tussenvoegsel_report_names_the_reading_overridden",
         "Berg, Jan do",
         {"given": "Jan", "family": "do Berg"},
         classification="fix(#379)",
         ambiguities=("particle-or-given",),
         notes="`do` is the third word in BOTH the particle and the "
               "suffix vocabularies, and it reports the OTHER kind "
               "from vd and mc. The report names what the attachment "
               "overrode, not what the word is: `do` sits in the "
               "AMBIGUOUS acronym half, which already left it a name "
               "word, so assign never read it as a post-nominal and "
               "there was no credential reading to decline (#405). A "
               "rule keyed on 'is also suffix vocabulary' would say "
               "suffix-or-name here and be wrong for the one word "
               "that most looks like it should"),
    Case("tussenvoegsel_multiword_run_reports_on_its_reading",
         "Berg, Jan de vd",
         {"given": "Jan", "family": "de vd Berg"},
         classification="fix(#379)",
         notes="the same point from the other side: `vd` IS suffix "
               "vocabulary, but behind `de` the run is read as name "
               "words rather than as a post-nominal, so nothing was "
               "declined and nothing is reported -- where the lone "
               "`Berg, Jan vd` reports suffix-or-name. Neither word "
               "is ambiguous vocabulary either, so no arm fires. The "
               "arms turn on the READING assign made, which is the "
               "only thing that makes them a fork"),
    Case("tussenvoegsel_never_given_reports_nothing", "Jong, Piet de",
         {"given": "Piet", "family": "de Jong"},
         classification="fix(#379)",
         notes="the reporting boundary (#405): 'de' is never-given "
               "particle vocabulary and is not suffix vocabulary "
               "either, so the attachment declines no reading the "
               "parse could have taken and stays SILENT. A single "
               "kind covering every attachment would assert "
               "'particle or given' about a word that is no given "
               "name in any reading"),
    Case("tussenvoegsel_needs_a_given_word_to_spare", "Nguyen, Van",
         {"given": "Van", "family": "Nguyen"},
         classification="parity",
         notes="the words-to-spare boundary: the only given word IS "
               "the particle, so it stays a given name rather than "
               "leaving the name with none. Vietnamese Van is exactly "
               "the case that guard protects"),
    # A family made only of particle vocabulary. Position decides:
    # nothing joins these words to a name, so they are not acting as
    # particles and they anchor the base (rules.md#R2, #404).
    Case("all_particle_family_anchors_its_own_base", "Anh Do",
         {"given": "Anh", "family": "Do"},
         classification="parity",
         ambiguities=("suffix-or-name",),
         notes="the ROLES are parity -- 1.4.0 gives first 'Anh', last "
               "'Do' too -- and the views are what #404 moved, which "
               "this table cannot assert (no initials or base column; "
               "rules.md#R2/#R3 carry those). Worth recording which "
               "way: 1.4.0's own _split_last guard kept last_base "
               "'Do', so the empty family_base was a 2.0 regression "
               "and this restores it. The initials half was broken in "
               "both: 'A.' at 1.4.0 and 2.1, 'A. D.' now"),
    Case("all_particle_family_multi_word", "Juan van der",
         {"given": "Juan", "family": "van der"},
         classification="parity",
         notes="roles are parity again; R3's Accepted block used to "
               "pin the views the other way, reasoning that 'van der' "
               "has no borne name to anchor a base. Position trumps "
               "that -- neither word joins anything here, so both are "
               "name words. 1.4.0 also gave last_base 'van der'; the "
               "core's '' was the 2.0 regression"),
    Case("particle_beside_a_name_still_a_particle", "Juan de la Vega",
         {"given": "Juan", "family": "de la Vega"},
         classification="parity",
         notes="the boundary the row above needs: here the particles "
               "DO join a name word, so they stay particles -- base "
               "'Vega', particles 'de la', initials 'J. V.'. Shape "
               "1's particle-bearing family slot",
         shape=1),
    Case("suffix_word_title_ambiguous_particle", "Jr. Van Johnson",
         {"title": "Jr.", "given": "Van", "family": "Johnson"},
         classification="fix(#367)",
         ambiguities=("particle-or-given",),
         notes="a leading 'Jr.' classifies as a TITLE, not a suffix, "
               "which is why the transparency scan does not step over "
               "suffix pieces -- see tests/v2/pipeline/test_group.py::"
               "test_a_suffix_shaped_leading_piece_is_not_stepped_over. "
               "1.4.0 gives title 'Jr.', last 'Van Johnson'"),
    Case("titled_particle_chain_survives_a_title_that_is_also_a_particle",
         "Freiherr von Richthofen",
         {"title": "Freiherr", "family": "von Richthofen"},
         ambiguities=("particle-or-given",),
         notes="#367's title transparency skips a piece that can ONLY "
               "be a title, never one that could be the name's own "
               "first piece. 'freiherr' is both a title and an "
               "ambiguous particle, so it stops the scan and stays the "
               "leading NAME piece; 'von' behind it is therefore "
               "non-leading and chains, exactly as before 2.2. This is "
               "also the CANONICAL shape reaching group's "
               "PARTICLE_OR_GIVEN emitter, not the only one -- 'St Van "
               "Johnson', 'Do St Johnson' and 'Dr. Do van Johnson' "
               "reach it too, the last with a plain title ahead of the "
               "both-vocabulary word; see tests/v2/test_parser.py -- "
               "and the class that a plain "
               "'first piece that is not a title' test broke: it "
               "skipped 'St'/'Do'/'Freiherr' and collapsed the "
               "untitled 'St John Smith' into one given name"),
    Case("titled_ambiguous_particle_no_op_chain", "St Van Jr.",
         {"title": "St", "family": "Van", "suffix": "Jr."},
         notes="the piece after the particle is a suffix, so the chain "
               "scan never advances and the merge is a no-op -- nothing "
               "was chained, so there is no fork to report (the emitter "
               "fired here for all ambiguous particles, and _assign "
               "double-reported the same token). Spelled with 'St' "
               "since #296's audit took 'do' out of TITLES; before that "
               "with 'Do', and before 2.2 with 'Dr.': "
               "under #367 a plain title is transparent, so 'Dr. Van "
               "Jr.' leaves Van the leading name piece and the chain "
               "loop skips it without ever reaching the no-op. 'Do' is "
               "a title AND a particle, which stops the transparency "
               "scan, so the chain does fire on Van and the j > k + 1 "
               "guard is what declines it -- the same reading of the "
               "name, reached through the branch the row exists to pin. "
               "Not parity, and not #367's doing either: 1.4.0 reads "
               "'Do Van Jr.' as first 'Do Van', last 'Jr.', so the "
               "divergence is 2.0's suffix routing plus 'do' being a "
               "title -- both older than this row's respelling"
               " -- and since #410 the one name word left standing "
               "behind the title reads as the family, the suffix no "
               "longer counting as something else in the name",
         classification="fix"),
    Case("initial_shaped_not_conjunction", "john e. smith",
         {"given": "john", "middle": "e.", "family": "smith"},
         notes="v1 is_conjunction excludes initials at classify too"),
    # #383/#479: a single-letter connective joins only on positive
    # evidence, and a name written wholly in one case has none. These
    # 17 rows pin the FORK, not the wordlist
    # (mechanisms.md#VOCABULARY-EXERCISES-FORKS).
    #
    # The 12 Latin e/y rows, plainly: 'e' at four words carries
    # one-case-lower ('jose e maria santos'), one-case-upper ('JOSE E
    # MARIA SANTOS'), mixed-lower where 'e' joins ('Jose e Maria
    # Santos'), and mixed-upper where 'E' is an initial ('Jose E Maria
    # Santos') -- four spellings, because within a mixed-case name the
    # letter's OWN case still decides which reading it gets. 'e' at
    # three words carries the same one-case-lower/one-case-upper/mixed-
    # lower trio ('john e smith' / 'JOHN E SMITH' / 'John e Smith');
    # its mixed-upper twin ('John E Smith') is absent because it would
    # pin nothing these rows do not -- the three-word carve-out already
    # keeps 'e' a name word either way, exactly as
    # one_case_three_word_e_is_an_initial does. 'y'
    # carries one-case-upper and one-case-lower at four words ('JUAN
    # GARCIA Y LOPEZ' / 'juan garcia y lopez'), mixed-upper at four
    # words where 'Y' still vetoes ('Juan Garcia Y Lopez'), and one-
    # case-upper/one-case-lower at three words where the carve-out
    # already held ('JUAN Y GARCIA' / 'juan y garcia'). 'Juan Garcia y
    # Lopez' (mixed-lower, four words) is absent for the same reason as
    # 'John E Smith': it pins the same BRANCH the mixed-lower 'e' row
    # already demonstrates, a different JOIN though -- 'Garcia y Lopez'
    # into the family where 'Jose e Maria' joins into the given run.
    # 'Juan Y Garcia' (mixed-UPPER, three words) is absent because its
    # control lives beside the capitalize() pin instead, in
    # tests/test_capitalization.py::test_a_one_letter_conjunction_is_case_sensitive_to_repair;
    # 'Juan y Garcia' (mixed-lower, three words) is absent from this
    # table because rules.md#P3 carries it as its boundary example and
    # test_render.py pins its initials.
    #
    # The other five rows are three DIFFERENT reasons a row does not
    # move, not "three scripts that must not enter the fork": the
    # Cyrillic pair DOES enter the fork -- 'и' is cased conjunction
    # vocabulary and takes the non-member branch exactly as 'y' does,
    # joining without a report -- the Catalan pair's 'i' is Latin script
    # but is not conjunction vocabulary AT ALL, so it never reaches
    # `single_letter_connective` in the first place (a different, earlier exclusion
    # than Cyrillic's, and #397's before-picture); only the Arabic row
    # is genuinely caseless and so never enters the fork on that
    # ground.
    #
    # All 17 rows are shape-tagged so build_shapes_corpus.py projects
    # them into the contract corpus -- measured 2026-09-13, no corpus
    # file held a uniform-case name with a single-letter connective
    # beyond the eight already there, and none held a standalone و at
    # all, so without these the fork is invisible to every future gate
    # run.
    Case("one_case_lower_e_reads_as_an_initial", "jose e maria santos",
         {"given": "jose", "middle": "e maria", "family": "santos"},
         classification="fix(#479)",
         ambiguities=("conjunction-or-initial",),
         notes="#479 row 1, the defect. 1.4.0 and 2.0-2.3 alike read "
               "'e' as the connective and gave given 'jose e maria'. "
               "A lowercase letter in an all-lowercase name is no more "
               "evidence than an uppercase one in an all-uppercase "
               "name, so the vocabulary decides and 'e' is marked",
         shape=1),
    Case("one_case_upper_e_reads_as_an_initial", "JOSE E MARIA SANTOS",
         {"given": "JOSE", "middle": "E MARIA", "family": "SANTOS"},
         ambiguities=("conjunction-or-initial",),
         notes="#479 row 4. The READING is unchanged from 1.4.0 and "
               "from 2.3 -- what is new is the report: an all-upper "
               "name's capital is not the evidence a mixed-case name's "
               "capital is, so the same fork was being called silently",
         shape=1),
    Case("mixed_case_lower_e_is_the_connective", "Jose e Maria Santos",
         {"given": "Jose e Maria", "family": "Santos"},
         notes="the mixed-case control for the row above: here the "
               "lowercase letter IS evidence, because the rest of the "
               "name is not lowercase, so 'e' joins and nothing is in "
               "doubt",
         shape=1),
    Case("mixed_case_upper_e_is_an_initial", "Jose E Maria Santos",
         {"given": "Jose", "middle": "E Maria", "family": "Santos"},
         notes="the other mixed-case control: a bare capital among "
               "mixed case is how an initial is written, unchanged "
               "since 1.4.0 and unreported",
         shape=1),
    Case("one_case_three_word_e_is_an_initial", "john e smith",
         {"given": "john", "middle": "e", "family": "smith"},
         ambiguities=("conjunction-or-initial",),
         notes="P3's three-word carve-out is untouched -- 'e' stays a "
               "name word either way -- so the ROLES do not move and "
               "the visible change is the tag: ParsedName.initials() "
               "(the v2 view this table exercises) gives 'j. e. s.' "
               "where 2.3 gave 'j. s.', and capitalize() gives 'John E "
               "Smith' where 2.3 gave 'John e Smith', pinned in "
               "tests/v2/test_render.py. Measured 2026-09-13: the v1 "
               "facade's HumanName.initials() did not follow this fork "
               "that morning and still gave 'j. s.'; #528 closed the "
               "split the same day by making that view read the "
               "parse's tags, so both surfaces give 'j. e. s.' now and "
               "test_facade_initials_follow_the_one_case_fork in "
               "tests/v2/test_render.py pins the agreement where a "
               "test pinned the split. This table asserts roles",
         shape=1),
    Case("one_case_upper_three_word_e_is_an_initial", "JOHN E SMITH",
         {"given": "JOHN", "middle": "E", "family": "SMITH"},
         ambiguities=("conjunction-or-initial",),
         notes="the all-upper spelling of the row above: same reading, "
               "and the report is what is new",
         shape=1),
    Case("mixed_case_three_word_e_is_the_connective", "John e Smith",
         {"given": "John", "middle": "e", "family": "Smith"},
         notes="the mixed-case control at three words. The carve-out "
               "means the ROLE is the same as the row above; the "
               "difference is the tag, and so the initials -- 'J. S.' "
               "here against 'J. E. S.' for 'JOHN E SMITH'",
         shape=1),
    Case("one_case_upper_y_joins_as_a_bare_capital", "JUAN GARCIA Y LOPEZ",
         {"given": "JUAN", "family": "GARCIA Y LOPEZ"},
         classification="fix(#383)",
         notes="#383 answered with 'bless', and this is the half that "
               "moves: 1.4.0 through 2.3 vetoed a bare Latin capital "
               "into an initial and gave middle 'GARCIA Y'. An "
               "all-upper name's capital is not evidence, 'y' is not "
               "marked as reading both ways, so it joins -- and "
               "reports nothing, because nothing about it is in doubt",
         shape=1),
    Case("one_case_lower_y_joins", "juan garcia y lopez",
         {"given": "juan", "family": "garcia y lopez"},
         notes="the parity half of the pair above: a lowercase 'y' "
               "joined before this change and joins after it",
         shape=1),
    Case("mixed_case_upper_y_is_an_initial", "Juan Garcia Y Lopez",
         {"given": "Juan", "middle": "Garcia Y", "family": "Lopez"},
         notes="the mixed-case control: here the capital IS evidence, "
               "so the bare 'Y' reads as an initial exactly as it "
               "always has, and the join does not happen",
         shape=1),
    Case("one_case_upper_y_keeps_the_three_word_carveout", "JUAN Y GARCIA",
         {"given": "JUAN", "middle": "Y", "family": "GARCIA"},
         notes="the boundary between the two exceptions: 'Y' is now "
               "conjunction-tagged rather than initial-tagged, and the "
               "three-word carve-out still refuses the join, so the "
               "ROLE is unchanged. What moves is initials() -- "
               "ParsedName.initials() gives 'J. G.' where 2.3 gave "
               "'J. Y. G.', a conjunction contributing none "
               "(rules.md#R3) -- and the v1 facade's "
               "HumanName.initials() gave 'J. Y. G.' until #528 made "
               "it read the same tags on 2026-09-13. That is the "
               "split the 'john e smith' row records, closed on the "
               "same day and by the same change "
               "(test_facade_initials_follow_the_one_case_fork in "
               "tests/v2/test_render.py). It runs the other way here: "
               "there the facade GAINED a letter it had been "
               "dropping, and here it loses one it had been keeping. "
               "Which is why this row needs the lowercase twin below "
               "to be readable",
         shape=1),
    Case("one_case_lower_y_keeps_the_three_word_carveout", "juan y garcia",
         {"given": "juan", "middle": "y", "family": "garcia"},
         notes="the twin of the row above, unchanged in every release: "
               "lowercase 'y' was already the connective at three "
               "words, and the carve-out already kept it a name word",
         shape=1),
    Case("one_case_upper_cyrillic_connective_joins", "ХОСЕ И МАРИЯ САНТОС",
         {"given": "ХОСЕ И МАРИЯ", "family": "САНТОС"},
         classification="feat(#269)",
         notes="#267's blessing survives the #383 rewrite, and for a "
               "different reason than it had: 'И' joins because 'и' is "
               "not in conjunctions_ambiguous, not because the veto "
               "tested a LATIN shape. No report -- the reading is not "
               "in doubt. 1.4.0 has no Cyrillic conjunction vocabulary "
               "at all and reads 'И' as a middle word (first ХОСЕ, "
               "middle И МАРИЯ, last САНТОС -- measured on the 1.4.0 "
               "wheel); #269 is what joins it, and this PR only adds "
               "the one-case spellings to the roster #269 already "
               "ships",
         shape=1),
    Case("one_case_lower_cyrillic_connective_joins", "хосе и мария сантос",
         {"given": "хосе и мария", "family": "сантос"},
         classification="feat(#269)",
         notes="the lowercase spelling of the row above; both cases "
               "read alike, which is the point of making the rule "
               "about evidence rather than about capitals. 1.4.0 reads "
               "'и' as a middle word here too (measured on the 1.4.0 "
               "wheel: first хосе, middle и мария, last сантос) for "
               "the same reason -- no Cyrillic conjunction vocabulary "
               "-- and #269 is what joins it",
         shape=1),
    Case("caseless_connective_never_enters_the_fork", "محمد و علي",
         {"given": "محمد", "middle": "و", "family": "علي"},
         notes="Arabic و has no case at all, so the fork's cased-token "
               "test is false and today's rule stands whatever the "
               "name's case class is. The first standalone و in any "
               "corpus -- measured 2026-09-13, none held one -- and "
               "the three-word carve-out keeps it a name word, as it "
               "does for 'juan y garcia'. shape=1 measured accepted by "
               "Case.__post_init__ (2026-09-13): the row instantiates "
               "shape 1's given-first arrangement under the default "
               "order, exactly as the Cyrillic twins above do -- a "
               "shape tag asserts the ARRANGEMENT, not a script "
               "(tools/differential/shapes.py)",
         shape=1),
    # #289: a bare ambiguous credential acronym is read by the
    # EVIDENCE the writing carries, and a name written in more than
    # one case carries some. These rows pin the FORK, not the wordlist
    # (mechanisms.md#VOCABULARY-EXERCISES-FORKS): the same two letters
    # in the same slot, spelled five ways, with the one-case controls
    # that must not move beside them.
    Case("caps_ambiguous_leans_credential", "Jack MA",
         {"given": "Jack", "suffix": "MA"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name", "given-or-family"),
         notes="the defect. An all-caps member of the ambiguous set "
               "inside a mixed-case name is written the way a "
               "credential is written, so it is taken as one even "
               "though peeling it leaves no family -- which is what "
               "'Jack MD' has always done with an unambiguous one. "
               "1.4.0 read last 'MA' here, so this breaks v1 parity "
               "deliberately",
         shape=1),
    Case("caps_ambiguous_leans_credential_with_a_period", "Jack MA.",
         {"given": "Jack", "suffix": "MA."},
         classification="fix(#289)",
         ambiguities=("suffix-or-name", "given-or-family"),
         notes="the lean reads CASE, not periods: a single trailing "
               "period is the abbreviation shape any word can wear "
               "(rules.md#S2) and changes nothing here, where the "
               "capitals have already spoken",
         shape=1),
    Case("title_case_ambiguous_leans_surname_two_words", "Jack Ma",
         {"given": "Jack", "family": "Ma"},
         ambiguities=("suffix-or-name",),
         notes="the contrast that makes the row above a fork rather "
               "than a wordlist entry: Title case is how a surname is "
               "written, and this row is unchanged in every release",
         shape=1),
    Case("one_case_upper_ambiguous_takes_the_count", "JACK MA",
         {"given": "JACK", "family": "MA"},
         ambiguities=("suffix-or-name",),
         notes="the one-case control for 'Jack MA': all-caps against "
               "all-caps is no contrast at all, so nothing leans and "
               "rules.md#S2's words-to-spare count decides alone -- "
               "two pieces, so the acronym stays the family name",
         shape=1),
    Case("one_case_lower_ambiguous_takes_the_count", "jack ma",
         {"given": "jack", "family": "ma"},
         ambiguities=("suffix-or-name",),
         notes="the lowercase spelling of the row above; both cases "
               "read alike, which is the point of asking about "
               "evidence rather than about capitals",
         shape=1),
    Case("title_case_ambiguous_leans_surname_with_words_to_spare",
         "John Smith Ma",
         {"given": "John", "middle": "Smith", "family": "Ma"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="the lean's other direction, and the one that costs a "
               "credential rather than a surname: with words to spare "
               "the count read 'Ma' as a suffix, and a Title-case "
               "word beside 'John Smith' is how a surname is written. "
               "1.4.0 read suffix 'Ma', so this is a deliberate "
               "parity break in the direction the East Asian surname "
               "wants (decisions.md#S2)",
         shape=1),
    Case("one_case_upper_ambiguous_with_words_to_spare",
         "JOHN SMITH MA",
         {"given": "JOHN", "family": "SMITH", "suffix": "MA"},
         ambiguities=("suffix-or-name",),
         notes="the one-case control for the row above: no evidence, "
               "so the count decides and three pieces make the "
               "acronym a credential, exactly as before 2.4",
         shape=1),
    Case("mixed_case_caps_ambiguous_with_words_to_spare",
         "john smith MA",
         {"given": "john", "family": "smith", "suffix": "MA"},
         ambiguities=("suffix-or-name",),
         notes="the lean and the count AGREE here, which is why the "
               "row does not move: capitals against lowercase lean "
               "credential, and three pieces read credential anyway",
         shape=1),
    Case("one_case_ambiguous_surname_is_untouched", "ANH DO",
         {"given": "ANH", "family": "DO"},
         ambiguities=("suffix-or-name",),
         notes="the name this whole design must not break: an "
               "all-caps Vietnamese surname in an all-caps name. One "
               "case, so nothing leans, and the count keeps the "
               "family -- the reading 2.0 shipped and 1.4.0 had",
         shape=1),
    Case("one_case_ambiguous_surname_behind_a_particle",
         "anh van do",
         {"given": "anh", "family": "van do"},
         notes="its lowercase, particle-bearing twin: the particle "
               "chain takes 'do' as part of the surname before any of "
               "this is asked",
         shape=1),
    Case("a_title_and_one_ambiguous_word_is_still_a_name", "Mr MA",
         {"title": "Mr", "family": "MA"},
         notes="the floor the lean does not move, measured "
               "2026-09-15: the trailing peel's walk starts after the "
               "leading title run, so one piece is all it sees and "
               "rules.md#S2's two-piece floor refuses it. A lean that "
               "reached below the floor would read this as a title "
               "with a credential and no name at all -- and nothing "
               "is reported, because no fork was taken",
         shape=1),
    Case("the_lean_reaches_the_post_comma_slot", "Smith, MA",
         {"family": "Smith", "suffix": "MA"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="Derek's own reading of #289: positive evidence "
               "outranks position, so the credential lean fires with "
               "ONE word before the comma where the words-to-spare "
               "count would not. The first report of the comma's OWN "
               "decision rides with it -- C2's structural flag already "
               "reports on the comma path, but reports what the parse "
               "could not recognize, not a fork it called "
               "(rules.md#C1's exception, scoped to this class; P6's "
               "attachment fork has reported on a family-comma path "
               "since 2.3, e.g. 'Berg, Jan vd')",
         shape=2),
    Case("the_surname_lean_keeps_the_post_comma_given", "Smith, Ma",
         {"given": "Ma", "family": "Smith"},
         ambiguities=("suffix-or-name",),
         notes="the contrast: Title case leans surname, so the word "
               "stays the given name exactly as it did -- and the "
               "call is reported all the same, both directions of one "
               "fork being worth telling the caller about",
         shape=2),
    Case("the_comma_count_is_of_name_words", "Smith Jr., MA",
         {"family": "Smith", "suffix": "Jr., MA"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="rules.md#C1's count for this class is of NAME words, "
               "not of words: two tokens and one name here, so the "
               "structure does not flip and the family survives. "
               "Counting tokens read it as given 'Smith' with suffix "
               "'Jr., MA' -- no reading of this string puts the "
               "family anywhere but where this row does "
               "(decisions.md#S2)",
         shape=2),
    Case("the_by_shape_class_never_reaches_is_wholly_suffix",
         "Smith Jr., A.B.",
         {"given": "A.B.", "family": "Smith", "suffix": "Jr."},
         classification="parity",
         ambiguities=("suffix-or-name",),
         notes="FULL PARITY on the 1.4.0 wheel -- first 'A.B.', last "
               "'Smith', suffix 'Jr.'; only the report is new, like "
               "its report-only siblings above. Also the control that "
               "pins the review-round fix: an EARLIER version of "
               "`is_wholly_suffix` admitted a by-shape member "
               "unconditionally, and combined with C1's own legacy "
               "TOKEN-count disjunct in `_segment.py` that flipped "
               "this to given 'Smith' with a self-contradicting "
               "'holds 1 name words' report. `ambiguous_class_candidate` "
               "is the only reader the by-shape class has at the "
               "comma form, and it declines here exactly as the "
               "listed class does above -- one name word, so `A.B.` "
               "stays the given and `Jr.` its own suffix",
         shape=2),
    Case("two_name_words_read_the_listed_acronym_as_a_credential",
         "John Smith, MA",
         {"given": "John", "family": "Smith", "suffix": "MA"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="1.4.0 RESTORED: v1 read first John, last Smith, "
               "suffix MA and 2.0 through 2.3 read given 'MA' with "
               "the whole name in `family`. The comma structure moves "
               "with the class, so this is the SUFFIX_COMMA form "
               "again",
         shape=3),
    Case("the_comma_count_reaches_the_listed_set_title_case",
         "John Smith, Ed",
         {"given": "John", "family": "Smith", "suffix": "Ed"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="one rule for the whole ambiguous class rather than "
               "two: where case is silent -- 'Ed' leans SURNAME here, "
               "and the lean does not reach the structure -- the "
               "count of name words before the comma decides, and two "
               "of them make it a credential. 1.4.0 read suffix 'Ed' "
               "too, so this restores parity rather than opening "
               "distance from it (decisions.md#S2, 2026-09-15)",
         shape=3),
    Case("the_comma_count_reaches_the_listed_set_lower",
         "john smith, ma",
         {"given": "john", "family": "smith", "suffix": "ma"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="the one-case spelling of the row above: no evidence "
               "either way, so the count decides and 1.4.0's suffix "
               "reading comes back",
         shape=3),
    Case("the_comma_count_reaches_the_listed_set_upper",
         "JOHN SMITH, MA",
         {"given": "JOHN", "family": "SMITH", "suffix": "MA"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="the all-caps spelling, and the reason the count has "
               "to reach the listed set at all: an all-caps name "
               "carries no lean, and leaving it to the lean alone "
               "would read this one way and its mixed-case twin "
               "another. 1.4.0 parity restored",
         shape=3),
    Case("two_name_words_before_the_comma_at_two_words",
         "Davis Royce, Ed",
         {"given": "Davis", "family": "Royce", "suffix": "Ed"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="the two-word twin of 'Royce, Ed' below, and the case "
               "row item 5 of decisions.md#S2 turns on -- no corpus "
               "name has this shape, so this row carries the whole "
               "weight of that decision",
         shape=3),
    Case("one_name_word_before_the_comma_is_never_enough",
         "Royce, Ed",
         {"given": "Ed", "family": "Royce"},
         ambiguities=("suffix-or-name",),
         notes="the control: one name word before the comma leaves "
               "nothing to spare, 'Ed' leans surname anyway, and the "
               "row is unchanged in every release. The pair above and "
               "below it is what makes the count visible",
         shape=2),
    Case("a_declined_ambiguous_pick_stops_the_walk",
         "abdul Smith Jr Ma",
         {"given": "abdul Smith", "middle": "Jr", "family": "Ma"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="an ACCEPTED cost, pinned rather than repaired "
               "(decisions.md#S2): the surname lean breaks the peel "
               "AT 'Ma', so the unambiguous 'Jr' in front of it is "
               "never reached and becomes a name word. The walk stops "
               "at the declined pick rather than continuing past it, "
               "and a name-leaning acronym blocking a genuine suffix "
               "behind it is the shape that costs",
         shape=1),
    Case("a_tail_segment_of_leaning_credentials_is_a_run",
         "Steven Hardman, MD, DO, DDS",
         {"given": "Steven", "family": "Hardman", "suffix": "MD, DO, DDS"},
         classification="fix(#289)",
         notes="the one place this design QUIETS a report rather than "
               "adding one: 'DO' is a listed ambiguous acronym "
               "written in capitals inside a mixed-case name, so the "
               "third comma segment is wholly suffix and rules.md#C2 "
               "stops flagging it. The FIELDS do not move -- a "
               "quieted flag is invisible to a reader sweeping for "
               "new reports, which is why it has a row of its own",
         shape=3),
    # Quality-review finding, 2026-09-17: "one name never reports
    # twice" was wrong as a blanket claim -- what is true is that one
    # DECISION never reports twice. Two DIFFERENT ambiguous acronyms
    # at two different forks each report once: the trailing peel over
    # the pre-comma part ('MA', credential lean, no words to spare)
    # and the comma structure's own flip ('Ed', two pre-comma name
    # words -- 'Smith' and 'MA' both count, since a bare undotted
    # ambiguous acronym is not suffix vocabulary to `name_word_count`
    # either).
    Case("two_different_forks_each_report_once", "Smith MA, Ed",
         {"given": "Smith", "suffix": "MA, Ed"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name", "suffix-or-name",
                      "given-or-family"),
         notes="'Smith MA' reads two name words, flipping the comma "
               "structure so 'Ed' joins the credential run; peeling "
               "'Smith MA' positionally then peels 'MA' too (caps "
               "lean, no words to spare), leaving 'Smith' the only "
               "name word, which is also what turns on "
               "GIVEN_OR_FAMILY. Three reports, none of them the same "
               "fork reporting twice"),
    Case("a_caseless_script_wrote_no_contrast", "毛泽东, MA",
         {"given": "MA", "family": "毛泽东"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="the LEAN is inert by construction: is_one_case answers "
               "True for text that has only one case, so nothing leans "
               "and the count decides -- one word before the comma, so "
               "the acronym stays the given name, as in every release. "
               "But the REPORT is not lean-gated (F4/F5 review finding, "
               "2026-09-17): it tracks the fork being consulted, "
               "exactly as the trailing slot always has, so this comma "
               "form is read positionally and still reports which way "
               "it went -- an earlier round wrongly excluded this row",
         tolerated=True),
    # MEASURED, not the plan's prediction: unlike its single-token
    # Chinese twin above, '마틴 킹' is TWO whitespace tokens, so item
    # 5's name-word count -- uniform across the whole ambiguous class,
    # case silent or not -- sees two name words before the comma and
    # flips the structure exactly as 'JOHN SMITH, MA' does. The comma
    # form then reads segment 0 the way a NO_COMMA name would (the
    # (a-lazy) mechanism's own tradeoff: the flip is decided before
    # script_segment, so the Hangul surname split runs over '마틴 킹'
    # positionally rather than over the untouched pre-comma text) --
    # the same shape 'Smith 김민준씨, MA' shows in the spec's decision
    # table. Not a caseless-script exemption: item 5 answers "where "
    # case is silent" by the SAME count the rest of item 5 uses, and a
    # two-word Hangul name is silent about case but not about how many
    # name words it has.
    Case("a_caseless_script_wrote_no_contrast_hangul", "마틴 킹, MA",
         {"given": "틴", "middle": "킹", "family": "마", "suffix": "MA"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="MEASURED 2026-09-17, not the spec's older prediction "
               "(given MA, family '마틴 킹', unchanged): dated before "
               "item 5's name-word-count extension was decided "
               "(2026-09-15) reached the listed set in ANY case. Two "
               "name words before the comma flip the structure here "
               "exactly as they do for 'JOHN SMITH, MA', and the flip "
               "precedes script_segment's Hangul surname split, which "
               "then runs over '마틴 킹' as if no comma had stood "
               "there at all",
         tolerated=True),
    # F2 review finding, 2026-09-17: the SAME mechanism reaches Japanese
    # too, by the same two-token count -- '田中 太郎' is two whitespace
    # tokens, not one, so it is not '毛泽东, MA's twin (a single token)
    # but '마틴 킹, MA's. 1.4.0 read both '마틴 킹, MA' and
    # '田中 太郎, MA' as suffix MA (measured on the wheel), so the
    # suffix half of this move is a PARITY RESTORATION, not a fresh
    # deviation -- only the pre-comma surname split (given '太郎',
    # family '田中') is #271/#272's pre-existing positional behavior,
    # unrelated to #289.
    Case("a_caseless_script_wrote_no_contrast_japanese", "田中 太郎, MA",
         {"given": "太郎", "family": "田中", "suffix": "MA"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="MEASURED 2026-09-17: two name words before the comma "
               "flip the structure exactly as '마틴 킹, MA' and "
               "'JOHN SMITH, MA' do, and the flip again precedes "
               "script_segment, so the family-first Han split runs "
               "over '田中 太郎' positionally. Docs/design's older "
               "'a caseless script is inert by construction' bullet "
               "is true of the LEAN alone; item 5's name-word count "
               "is orthogonal to case and reaches this row too",
         tolerated=True),
    # #516's dotted half: an UNLISTED token of two or more
    # period-separated chunks joins the ambiguous credential class BY
    # SHAPE, and the words-to-spare count then reads it. These rows
    # pin the FORK -- the same token in the two positions the count
    # separates, with the chunk-claim names that must NOT move beside
    # them (mechanisms.md#VOCABULARY-EXERCISES-FORKS).
    Case("unlisted_dotted_reads_by_position_with_words_to_spare",
         "John Smith X.Y.Z.",
         {"given": "John", "family": "Smith", "suffix": "X.Y.Z."},
         classification="fix(#516)",
         ambiguities=("suffix-or-name",),
         notes="the periods are the signal and the position decides: "
               "three pieces, so the unlisted acronym is the "
               "credential. 1.4.0 read last 'X.Y.Z.', so this breaks "
               "parity deliberately -- the parking-lot entry of "
               "decisions.md#suffix-acronym-collisions is what it "
               "closes",
         shape=1),
    Case("unlisted_dotted_is_case_blind", "john smith x.y.z.",
         {"given": "john", "family": "smith", "suffix": "x.y.z."},
         classification="fix(#516)",
         ambiguities=("suffix-or-name",),
         notes="the control that separates this switch from #289's "
               "lean: case is irrelevant here, the PERIODS being the "
               "signal, so the all-lower spelling reads as the "
               "mixed-case one does",
         shape=1),
    Case("unlisted_dotted_without_words_to_spare_is_the_family",
         "Jack X.Y.Z.",
         {"given": "Jack", "family": "X.Y.Z."},
         ambiguities=("suffix-or-name",),
         notes="the other half of the count, and the row is unchanged "
               "in its FIELDS: two pieces, so the shape loses to the "
               "surname reading. What is new is the report -- the "
               "fork was always there and was called silently",
         shape=1),
    Case("unlisted_dotted_of_any_chunk_length", "John Smith B.Tech.",
         {"given": "John", "family": "Smith", "suffix": "B.Tech."},
         classification="fix(#516)",
         ambiguities=("suffix-or-name",),
         notes="chunk LENGTH is not the test: two chunks, one of them "
               "four letters, and the Indian degree reads as the "
               "credential it is",
         shape=1),
    Case("the_s3_boundary_example_moves", "John Smith Q.W.E.R.T.",
         {"given": "John", "family": "Smith", "suffix": "Q.W.E.R.T."},
         classification="fix(#516)",
         ambiguities=("suffix-or-name",),
         notes="rules.md#S3's own boundary example, which said this "
               "shape stays a name. It moves, and the rule moves with "
               "it",
         shape=1),
    Case("the_roman_chunk_accident_retires_narrowly", "Jack X.Y.I.",
         {"given": "Jack", "family": "X.Y.I."},
         classification="fix(#516)",
         ambiguities=("suffix-or-name",),
         notes="1.4.0 RESTORED. The chunk 'i' is a roman numeral in "
               "the suffix vocabulary, so this read as a generational "
               "suffix -- by accident, the fork being about "
               "generations and the word being nothing of the kind. "
               "Retired where every matched chunk is a single ASCII "
               "character -- the roster this retirement is scoped to "
               "is asserted, not just described, in "
               "test_vocab.test_period_joined_vocab_retires_the_single_"
               "character_chunk",
         shape=1),
    Case("a_retired_chunk_claim_still_reads_by_position",
         "John Smith R.A.I.",
         {"given": "John", "family": "Smith", "suffix": "R.A.I."},
         ambiguities=("suffix-or-name",),
         notes="the pair to the row above, and the reason the "
               "retirement is safe: with words to spare the shape "
               "reads the same token the accident read, so the FIELDS "
               "do not move and only the cause does. The report is "
               "what makes the new cause visible",
         shape=1),
    Case("a_multi_letter_roman_chunk_also_reads_by_position",
         "John Smith J.u.n.i.o.r.",
         {"given": "John", "family": "Smith", "suffix": "J.u.n.i.o.r."},
         ambiguities=("suffix-or-name",),
         notes="the six-chunk twin of the row above: no chunk here is "
               "vocabulary at all (this is not 'junior' the suffix "
               "word, glued letter by letter), so the shape read this "
               "one before the retirement existed and reads it the "
               "same way after -- the FIELDS never moved, only the "
               "report is new",
         shape=1),
    Case("the_comma_structure_moves_with_the_shape_class",
         "John Smith, A.B.",
         {"given": "John", "family": "Smith", "suffix": "A.B."},
         classification="fix(#516)",
         ambiguities=("suffix-or-name",),
         notes="two NAME words before the comma read the part after "
               "it as the credential run, for the by-shape half "
               "exactly as for the listed one (rules.md#C1)",
         shape=3),
    Case("one_word_before_the_comma_keeps_the_given", "Smith, A.B.",
         {"given": "A.B.", "family": "Smith"},
         ambiguities=("suffix-or-name",),
         notes="its control: one name word before the comma is never "
               "enough, so the dotted token stays the given name and "
               "the structure does not move. Unchanged in every "
               "release; the report is new",
         shape=2),
    Case("whole_token_vocabulary_wins_over_the_shape",
         "Smith, A.B.C.",
         {"family": "Smith", "suffix": "A.B.C."},
         notes="'abc' IS a suffix acronym, so the whole-token lookup "
               "settles this before any shape reading and the count "
               "never runs. The boundary between #516's shape class "
               "and the vocabulary it does not touch",
         shape=2),
    Case("a_leading_dotted_run_is_untouched", "X.Y.Z. Smith",
         {"given": "X.Y.Z.", "family": "Smith"},
         notes="rules.md#S2 already says a suffix never opens the "
               "string, and the shape class is read only by the "
               "trailing peel and the post-comma slot -- so every "
               "leading dotted run, 'J.R.R. Tolkien' included, is "
               "untouched by this switch",
         shape=1),
    Case("a_leading_dotted_run_of_three_chunks_is_untouched",
         "J.R.R. Tolkien",
         {"given": "J.R.R.", "family": "Tolkien"},
         notes="the three-chunk twin of the row above: 'j', 'r' and "
               "'r' claim nothing either, and the leading slot never "
               "asks the shape class regardless",
         shape=1),
    Case("a_multi_character_chunk_claim_survives", "Doe, John Msc.Ed.",
         {"given": "John", "family": "Doe", "suffix": "Msc.Ed."},
         notes="the narrow retirement's protected control: the chunk "
               "'ed' is two characters, so the chunk rule still fires "
               "and this real credential is not handed to the shape "
               "class. The WIDE retirement -- any chunk match yielding "
               "to the shape -- would have read 'Msc.Ed.' as a middle "
               "name, which is what rejected it (decisions.md#S2)",
         shape=2),
    Case("a_glued_honorific_chunk_is_not_ascii", "J.씨",
         {"given": "J.", "suffix": "씨"},
         notes="the reason the retirement says ASCII and not just "
               "single-character: '씨' is one character and MUST keep "
               "its chunk claim, the honorific peel resting on it",
         tolerated=True),
    Case("a_delimited_dotted_token_keeps_its_clause_reading",
         "Bridge (1.4)",
         {"family": "Bridge", "nickname": "1.4"},
         notes="delimited content is decided by the clause escape "
               "rather than at the trailing slot -- so the shape "
               "class is not offered to a token that already carries "
               "a role, and this row gains neither a reading nor a "
               "report. Cannot exercise the `token.role is None` "
               "guard on its own, though: a digit chunk never reaches "
               "the shape verdict at all (period_joined_vocab's own "
               "alphabetic gate) -- the row beside it is the guard's "
               "real control",
         shape=1),
    Case("the_role_guard_is_the_real_delimited_control", "Bridge (A.B)",
         {"family": "Bridge", "nickname": "A.B"},
         notes="unlike the digit row above, 'A.B' WOULD reach the "
               "shape verdict were it not for classify's `token.role "
               "is None` guard -- without it this nickname gains "
               "SHAPE_ACRONYM_TAG and, with the switch on, "
               "'vocab:suffix-ambiguous', and classify's own nickname "
               "check misreports SUFFIX_OR_NICKNAME on a token the "
               "clause escape already decided (measured regression, "
               "#516 review round). This row is what actually pins "
               "the guard load-bearing",
         shape=1),
    Case("a_bare_digit_chunk_is_never_an_acronym_by_shape",
         "John Smith 1.4",
         {"given": "John", "middle": "Smith", "family": "1.4"},
         notes="#516 review round: the shape gate requires every chunk "
               "to be ALPHABETIC, not merely unclaimed -- '1' and '4' "
               "are chunks nothing spells as letters, so this stays "
               "name material exactly as 'Bridge (1.4)' does, and "
               "unlike the delimited control this one was never inside "
               "a clause at all. Unchanged from dfb3170, and the gap "
               "the delimited control alone did not cover",
         shape=1),
    Case("a_bare_digit_chunk_after_the_comma_is_never_an_acronym",
         "John Smith, 1.4",
         {"given": "1.4", "family": "John Smith"},
         notes="the comma-form twin of the row above: one word before "
               "the comma is never enough regardless, but the point "
               "this row pins is that the digit chunk never even "
               "becomes a CANDIDATE for the class -- no report, "
               "unchanged from dfb3170",
         shape=2),
    Case("a_leading_shape_token_never_reports_only_the_trailing_one",
         "J.A. K.D.",
         {"given": "J.A.", "family": "K.D."},
         ambiguities=("suffix-or-name",),
         notes="'K.D.' is a considered pick -- the peel records it "
               "even though k == 2 declines to take it, so the FIELDS "
               "stay the two-piece positional read while the fork is "
               "reported, exactly as a declined LISTED pick always "
               "has been. 'J.A.' gets no such consideration: the peel "
               "walks from the END, so a LEADING shape-admitted token "
               "never reaches it and this reports exactly once, for "
               "'K.D.' alone",
         shape=1),
    Case("an_initialless_script_glued_into_periods_is_not_this_shape",
         "John Smith 田.中.",
         {"given": "John", "middle": "Smith", "family": "田.中."},
         notes="the CJK control for #516's shape verdict, on the same "
               "reasoning is_title_shaped already gives H2's own "
               "period-abbreviation inference (#323): a script with "
               "no period abbreviations at all has nothing for "
               "interior periods to abbreviate, so this stays name "
               "material exactly as it did at dfb3170 -- no reading "
               "and no report",
         tolerated=True),
    # The whole-PR review round, 2026-09-18. Three groups: the fork
    # the prefix chain swallowed, the honorific peel that stopped
    # asking for the lean, and the tail segment that started flagging
    # its own new reading. Every row here is a REPORT moving, not a
    # role -- which is exactly why none of them had a row before.
    Case("the_chain_reports_the_acronym_it_takes",
         "John van der Berg Ma",
         {"given": "John", "family": "van der Berg Ma"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="rules.md#S2 says either reading carries the flag, and "
               "this reading carried none. assign reports from the "
               "peel's picks and a pick reaches it only as a LONE "
               "piece, so once the prefix chain merged 'Ma' into the "
               "family piece the token assign would have reported on "
               "no longer existed. The roles are unchanged and were "
               "never in doubt -- 'Ma' is Title-case in a mixed-case "
               "name, so #289's lean declines it; what the review "
               "round restored is the report, emitted at the chain's "
               "own merge (mechanisms.md#AMBIGUITY-AT-THE-DECISION-"
               "SITE)",
         shape=1),
    Case("the_chain_reports_at_one_particle_too", "John de Ma",
         {"given": "John", "family": "de Ma"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="the shortest spelling of the row above: one particle, "
               "one chained acronym. Kept beside it because the chain "
               "reaches the merge by a different route here -- 'de' "
               "takes the single following piece rather than a run -- "
               "and the emitter's `j > k + 1` floor is what both have "
               "to clear",
         shape=1),
    Case("the_chain_reports_the_by_shape_half_too",
         "John van der Berg X.Y.Z.",
         {"given": "John", "family": "van der Berg X.Y.Z."},
         policy=Policy(unlisted_dotted_suffixes=False),
         ambiguities=("suffix-or-name",),
         classification="fix(#516)",
         notes="the BY-SHAPE half of the chain emitter's two-tag "
               "test, unpinned until the verification round "
               "(2026-09-18): with the listed tag alone, all 8624 "
               "tests still passed. The switch is what makes the "
               "half reachable -- at the default, classify writes "
               "BOTH tags, so the listed tag answers for this name "
               "too and the shape tag's absence is invisible. Off, "
               "only the shape tag is written, and dropping it from "
               "`_AMBIGUOUS_CREDENTIAL_TAGS` silences this row, "
               "'Freiherr von Berg X.Y.I.' and 'John van Berg A.B.' "
               "at once"),
    Case("a_particle_that_is_also_an_acronym_reports_nothing",
         "anh van mc",
         {"given": "anh", "family": "van mc"},
         notes="the control the emitter above must NOT claim, and the "
               "reason it asks `prefix(j - 1)` last. 'mc' is a "
               "particle as well as suffix vocabulary, so the chain's "
               "PARTICLE run takes it -- P4's reading and P6's fork, "
               "not S2's -- and 1.4.0 read it this way in silence. "
               "'anh van do' is the shipped twin (its own row above) "
               "and this is its unambiguous-vocabulary sibling, which "
               "the peel never even considers",
         shape=1),
    Case("the_glued_honorific_peels_behind_a_leaning_credential",
         "Kim김민준씨, MA",
         {"family": "Kim김민준", "suffix": "씨, MA"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="script_segment asked `is_wholly_suffix` of the "
               "post-comma run WITHOUT the case fact segment had just "
               "recorded, so 'MA' read as name material, the run was "
               "scanned, its only peel site was 'MA' itself -- which "
               "ends in no listed tail -- and the person's own 씨 went "
               "unpeeled (family 'Kim김민준씨'). 'Kim김민준씨, PhD' "
               "peeled all along, so one name in two credential "
               "spellings parsed two ways. Passing the fact is the "
               "whole fix (review round, 2026-09-18)",
         tolerated=True),
    Case("the_glued_honorific_peel_reads_the_lean_not_the_word",
         "Jo김민준씨, DO",
         {"family": "Jo김민준", "suffix": "씨, DO"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="a second member of the ambiguous set behind the same "
               "comma, so the row above pins the mechanism rather "
               "than the word 'MA' "
               "(mechanisms.md#VOCABULARY-EXERCISES-FORKS is about "
               "not doing this per entry; 'DO' is here because it is "
               "ALSO particle vocabulary, which nothing else on this "
               "path exercises)",
         tolerated=True),
    Case("the_glued_honorific_peel_behind_a_title_and_a_lean",
         "Dr. 김민준씨, MA",
         {"title": "Dr.", "family": "김민준", "suffix": "씨, MA"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="the title is what makes this name MIXED-case at all "
               "-- Hangul is caseless, so '김민준씨, MA' on its own is "
               "one case, leans nothing and keeps today's reading "
               "(given 'MA', family '김민준씨', unpeeled). Two rows, "
               "one difference, and the difference is the case "
               "contrast rather than the honorific",
         tolerated=True),
    Case("a_tail_segment_of_by_shape_credentials_is_not_flagged",
         "John Smith, MD, R.A.I.",
         {"given": "John", "family": "Smith", "suffix": "MD, R.A.I."},
         classification="fix(#516)",
         notes="rules.md#S3's narrow roman retirement moved 'R.A.I.' "
               "out of the vocabulary verdict and into the shape "
               "class, and segment's tail-segment test reads "
               "`is_wholly_suffix`, which is blind to that class by "
               "design -- so a third segment the parser itself reads "
               "as a credential run gained a COMMA_STRUCTURE flag 2.3 "
               "did not raise. A report about the parser's own new "
               "reading rather than about the name (review round, "
               "2026-09-18). Roles unchanged at every policy: a tail "
               "segment is consumed as suffix either way",
         shape=3),
    Case("the_by_shape_tail_segment_is_flagged_with_the_switch_off",
         "John Smith, MD, R.A.I.",
         {"given": "John", "family": "Smith", "suffix": "MD, R.A.I."},
         policy=Policy(unlisted_dotted_suffixes=False),
         ambiguities=("comma-structure",),
         notes="the negative control for the row above, and the "
               "reason the test is policy-sensitive rather than a "
               "blanket quiet: with the switch off 'R.A.I.' is name "
               "material, is no candidate for the class, and the "
               "segment genuinely is beyond the recognized comma "
               "structures. Same fields, opposite report",
         classification="fix(#516)"),
    Case("a_listed_tail_segment_keeps_its_flag_where_nothing_leans",
         "John Smith, MD, Ma",
         {"given": "John", "family": "Smith", "suffix": "MD, Ma"},
         ambiguities=("comma-structure",),
         notes="the other boundary of the same test: the quiet is the "
               "BY-SHAPE half's alone. A LISTED member reaches this "
               "reading through the case lean "
               "('Steven Hardman, MD, DO, DDS', "
               "test_segment.py's own negative control), and 'Ma' "
               "leans the other way, so the flag stands exactly as it "
               "did at 1f78bef. Folding membership into the test "
               "instead would have silenced the lean's own control",
         shape=3),
    Case("the_caps_shape_never_reaches_a_tail_segment",
         "John Smith, MD, XYZ",
         {"given": "John", "family": "Smith", "suffix": "MD, XYZ"},
         policy=Policy(unlisted_caps_suffixes=True),
         ambiguities=("comma-structure",),
         classification="fix(#516)",
         notes="the SECOND way C2's quiet is narrow, and the half its "
               "examples did not pin until the verification round "
               "(2026-09-18). The shape a tail segment is recognized "
               "by is the DOTTED one alone, so turning the caps "
               "switch on does not quiet 'XYZ' here -- the flag is "
               "the same one the default policy raises. Folding "
               "`caps_shape_candidate` into the class run would make "
               "this row fail"),
    # #516's all-caps half, and it is OPT-IN. The rows come in pairs:
    # the same name under the DEFAULT policy, where nothing moves and
    # nothing is reported, and under Policy(unlisted_caps_suffixes=
    # True), where the shape reads. The French and Korean names are
    # why the default is off (mechanisms.md#VOCABULARY-EXERCISES-FORKS
    # -- each pair pins the switch, not the words). A row that sets
    # the non-default policy carries no `shape=` tag: the contract
    # corpus (build_shapes_corpus.py) keys only on (shape, text), with
    # no policy of its own, so admitting one of these texts under a
    # shape id would have compare.py diff it against the released
    # wheels under the DEFAULT policy -- the wrong question for a row
    # whose point IS the non-default policy.
    Case("caps_surname_is_a_family_name_by_default", "Jean DUPONT",
         {"given": "Jean", "family": "DUPONT"},
         notes="the writing convention the default protects: French "
               "records write the surname in capitals, and shape "
               "cannot tell that from a credential. 1.4.0's reading, "
               "2.3's reading, and the reading at this default",
         shape=1),
    Case("caps_surname_is_swallowed_with_the_switch_on",
         "Jean Pierre DUPONT",
         {"given": "Jean", "family": "Pierre", "suffix": "DUPONT"},
         policy=Policy(unlisted_caps_suffixes=True),
         classification="fix(#516)",
         ambiguities=("suffix-or-name",),
         notes="the cost of the switch, pinned so nobody turns it on "
               "without meeting it: three name words, so the count "
               "reads the capitalised surname as a credential and the "
               "family becomes 'Pierre'. This row is the argument for "
               "the default being off (decisions.md#S2)"),
    # #516 review round (quality-review finding): the TWO-word shape
    # ('Jean DUPONT') is the row `_policy.py`'s own docstring needed
    # and did not have -- turning the switch on reports a genuine
    # candidate even where one word before the credential declines
    # the structure flip, matching 'the_caps_comma_count_declines_at_
    # one_word' (the comma form's own twin of this exact guarantee).
    Case("caps_surname_reports_but_does_not_move_at_two_words",
         "Jean DUPONT",
         {"given": "Jean", "family": "DUPONT"},
         policy=Policy(unlisted_caps_suffixes=True),
         ambiguities=("suffix-or-name",),
         notes="one name word is never enough to spend the credential "
               "reading, so the family stays 'DUPONT' -- but the fork "
               "was genuinely considered and declined, and reports so "
               "even though nothing moved"),
    Case("caps_surname_default_reading_at_three_words",
         "Jean Pierre DUPONT",
         {"given": "Jean", "middle": "Pierre", "family": "DUPONT"},
         notes="the same name at the default, which is the half a "
               "reader of the row above needs: nothing moves and "
               "nothing is reported, so a caller who never sets the "
               "switch never meets that cost",
         shape=1),
    Case("caps_korean_surname_is_a_family_name_by_default",
         "Minjun KIM",
         {"given": "Minjun", "family": "KIM"},
         notes="the second convention the default protects: Korean "
               "records write the family name in capitals to mark "
               "which of two words it is, which is the opposite of a "
               "credential",
         shape=1),
    Case("unlisted_caps_reads_by_position_with_the_switch_on",
         "John Smith XYZ",
         {"given": "John", "family": "Smith", "suffix": "XYZ"},
         policy=Policy(unlisted_caps_suffixes=True),
         classification="fix(#516)",
         ambiguities=("suffix-or-name",),
         notes="what the switch buys: the shape reads, and the "
               "words-to-spare count decides it exactly as it decides "
               "the listed set"),
    Case("unlisted_caps_is_silent_at_the_default", "John Smith XYZ",
         {"given": "John", "middle": "Smith", "family": "XYZ"},
         notes="the same name at the default: name material, and NO "
               "report -- the one place this design emits nothing "
               "where a fork could be said to exist, because the "
               "reading was never on offer (#516)",
         shape=1),
    Case("the_caps_comma_count_needs_two_name_words",
         "John Smith, XYZ",
         {"given": "John", "family": "Smith", "suffix": "XYZ"},
         policy=Policy(unlisted_caps_suffixes=True),
         classification="fix(#516)",
         ambiguities=("suffix-or-name",),
         notes="the comma structure moves with this half too, on the "
               "same NAME-word count"),
    Case("the_caps_comma_count_declines_at_one_word", "Smith, XYZ",
         {"given": "XYZ", "family": "Smith"},
         policy=Policy(unlisted_caps_suffixes=True),
         ambiguities=("suffix-or-name",),
         notes="its control, switch and all: one name word before the "
               "comma is never enough, so the capitalised word stays "
               "the given name"),
    Case("one_case_input_never_reaches_the_caps_switch",
         "JOHN SMITH XYZ",
         {"given": "JOHN", "middle": "SMITH", "family": "XYZ"},
         policy=Policy(unlisted_caps_suffixes=True),
         notes="the one-case control, and it needs the switch ON to "
               "mean anything: capitals against capitals are no "
               "contrast, so the shape never fires and the row is "
               "unchanged with the switch either way"),
    Case("suffix_vocabulary_never_reaches_the_caps_switch",
         "John Smith MC",
         {"given": "John", "family": "Smith", "suffix": "MC"},
         policy=Policy(unlisted_caps_suffixes=True),
         notes="UNLISTED is the load-bearing word: 'mc' is suffix "
               "vocabulary, so the whole-token lookup claims it before "
               "any shape reading and this row reads the same with "
               "the switch on or off"),
    Case("the_caps_comma_count_reaches_a_multi_word_run",
         "John Smith, LEED AP",
         {"given": "John", "family": "Smith", "suffix": "LEED AP"},
         policy=Policy(unlisted_caps_suffixes=True),
         classification="fix(#516)",
         ambiguities=("suffix-or-name",),
         notes="the first time this class reaches the comma form as "
               "MORE than one token: 'LEED' and 'AP' are two separate "
               "all-caps words, and every token in the run must be a "
               "candidate for the run itself to be one -- rules.md#C1's "
               "`deviates: #291` line comes true ONLY under this "
               "switch. At the DEFAULT this exact text still reads "
               "given 'LEED', middle 'AP', family 'John Smith' -- the "
               "deviation stands there unchanged -- so nothing in "
               "this arc may remove rules.md#C1's `deviates: #291` "
               "marker on this switch's account; the switch only "
               "narrows what makes the deviation true"),
    Case("the_caps_comma_multi_word_run_declines_at_one_word",
         "Smith, LEED AP",
         {"given": "LEED", "family": "Smith", "suffix": "AP"},
         policy=Policy(unlisted_caps_suffixes=True),
         classification="fix(#531)",
         ambiguities=("suffix-or-name", "suffix-or-name"),
         notes="the one-pre-comma-word twin of the row above, and the "
               "only corpus mover #531 found outside the two known "
               "names -- only behind a default-off switch, so no "
               "default reading is at stake (Derek's Q3, accepted "
               "2026-09-18). The STRUCTURE still does not flip: one "
               "name word before the comma is never enough, item 5's "
               "count doing its job on real data, so 'LEED' stays the "
               "given name. What moved is the TRAILING slot behind it "
               "-- before #531 'AP' was the middle name and the only "
               "report was assign's family-comma emitter reading the "
               "first post-comma piece's tag; now the given part's "
               "trailing slot takes 'AP' as the credential and reports "
               "its own decision. Two slots, two forks, two reports"),
    # #516 review round: LISTED members must keep #289's lean with
    # the switch on -- the caps branch must never ride SHAPE_ACRONYM_
    # TAG beside a listed member's own membership tag, which is what
    # silenced `listed_lean` for these before the fix (F1, decided by
    # the reviewer; decisions.md#S2). Both rows are byte-identical to
    # their DEFAULT-policy siblings above (`caps_ambiguous_leans_
    # credential`, `the_lean_reaches_the_post_comma_slot`) and carry
    # no `shape=` tag for the same reason every other policy-on row
    # here does not: the contract corpus keys on (shape, text) with no
    # policy of its own, so tagging one would have the gate diff it
    # against the released wheels under the DEFAULT policy -- the
    # wrong question for a row whose point IS the non-default policy
    # (`Case.shape`'s own docstring).
    Case("caps_switch_does_not_silence_the_listed_lean", "Jack MA",
         {"given": "Jack", "suffix": "MA"},
         policy=Policy(unlisted_caps_suffixes=True),
         ambiguities=("suffix-or-name", "given-or-family"),
         notes="the switch must not touch a LISTED member's own "
               "#289 lean: identical to the default reading"),
    Case("caps_switch_does_not_silence_the_comma_lean", "Smith, MA",
         {"family": "Smith", "suffix": "MA"},
         policy=Policy(unlisted_caps_suffixes=True),
         ambiguities=("suffix-or-name",),
         notes="the comma-form twin of the row above, same guarantee"),
    # #516 review round: UNLISTED means in no wordlist at all, not
    # merely "no whole-token suffix vocabulary" -- a capitalized
    # particle or particle phrase must not join the class either
    # (F1b, decided by the reviewer; decisions.md#S2's amendment).
    Case("caps_switch_does_not_claim_a_capitalized_particle",
         "John Smith DE",
         {"given": "John", "middle": "Smith", "family": "DE"},
         policy=Policy(unlisted_caps_suffixes=True),
         notes="'de' is a particle, not merely absent from suffix "
               "vocabulary -- identical to the default reading with "
               "the switch on"),
    Case("caps_switch_does_not_claim_a_capitalized_particle_phrase",
         "John Smith, DE LA",
         {"family": "John Smith DE LA"},
         policy=Policy(unlisted_caps_suffixes=True),
         notes="the multi-token twin: 'DE' and 'LA' are both "
               "particles, so the RUN test (#516's own 'LEED AP' "
               "shape) must decline them too -- identical to the "
               "default reading"),
    # #516 review round, F5: the spec's stated mechanism for why
    # 'Jack VI' does not move was wrong -- 'VI' DOES reach the caps
    # predicate and carries both tags with the switch on. It stays
    # unchanged because `_pieces.is_trailing_numeral_suffix` (the
    # roman-numeral fork) claims it downstream, before the lean/count
    # this switch adds is ever consulted -- unrelated to this switch,
    # and the reason these controls read identically on or off.
    Case("caps_switch_does_not_move_a_roman_numeral", "Jack VI",
         {"given": "Jack", "suffix": "VI"},
         policy=Policy(unlisted_caps_suffixes=True),
         ambiguities=("suffix-or-name", "given-or-family"),
         notes="the roman-numeral fork claims 'VI' before this "
               "switch's lean/count is consulted -- identical to the "
               "default reading, on or off"),
    Case("caps_switch_does_not_move_a_roman_numeral_with_words_to_spare",
         "John Smith VI",
         {"given": "John", "family": "Smith", "suffix": "VI"},
         policy=Policy(unlisted_caps_suffixes=True),
         ambiguities=("suffix-or-name",),
         notes="the words-to-spare twin of the row above, same "
               "mechanism, same guarantee"),
    Case("caps_switch_does_not_move_a_title_floor_control", "Mr XXX",
         {"title": "Mr", "family": "XXX"},
         policy=Policy(unlisted_caps_suffixes=True),
         notes="one piece behind a title never reaches the peel's "
               "`k >= 2` floor -- identical to the default reading"),
    Case("caps_switch_does_not_reach_delimited_content",
         "Andrew Perkins (XYZ)",
         {"given": "Andrew", "family": "Perkins", "nickname": "XYZ"},
         policy=Policy(unlisted_caps_suffixes=True),
         notes="delimited content is decided by the clause escape, "
               "never at the trailing slot -- identical to the "
               "default reading"),
    # #516 review round, F2: the multi-token run test is a property of
    # the CAPS class alone -- a run of pure LISTED members must keep
    # its EXISTING reading (`_pieces.segment_suffix_reading`'s own
    # per-piece walk, #289, unrelated to this switch and to its
    # structure-flip candidate test) rather than being swept into the
    # caps run test's `all()`. Identical to the default reading.
    Case("caps_switch_run_test_declines_a_pure_listed_run",
         "John Smith, Ed Ma",
         {"given": "Ed", "middle": "Ma", "family": "John Smith"},
         policy=Policy(unlisted_caps_suffixes=True),
         classification="fix(#531)",
         ambiguities=("suffix-or-name", "suffix-or-name"),
         notes="'Ed' and 'Ma' are both LISTED ambiguous members, "
               "Title-case (leans NAME, #289) -- the caps run test "
               "must not admit a run the listed class already reads "
               "on its own. #531 adds the SECOND report and moves no "
               "field: this is a family-comma name whose given part "
               "now ends in a class member, and 'Ma' is Title-cased, "
               "so the slot consults the fork and declines it "
               "exactly as 'Doe, John Ma' does. The report tracks "
               "the fork CONSULTED (#530), which is why a declined "
               "reading still says so"),
    # #516 review round (second finding): the caps branch read
    # `one_case_own` -- true only for a token INSIDE the maiden
    # clause's own-words span -- where it needed the bare NAME-level
    # fact. 'NEE' opens the clause, so it sits OUTSIDE that span by
    # construction and read as False regardless of the whole name's
    # case, wrongly joining the shape class in a wholly one-case name.
    # `maiden_markers` is also the one wordlist the ten-list exclusion
    # first shipped without.
    Case("caps_switch_does_not_claim_a_one_case_maiden_marker",
         "JOHN SMITH NEE",
         {"given": "JOHN", "middle": "SMITH", "family": "NEE"},
         policy=Policy(unlisted_caps_suffixes=True),
         notes="one case, and a maiden marker with no clause to open "
               "(nothing follows it) -- identical to the default "
               "reading either way"),
    Case("caps_switch_does_not_claim_a_mixed_case_maiden_marker",
         "John Smith NEE",
         {"given": "John", "middle": "Smith", "family": "NEE"},
         policy=Policy(unlisted_caps_suffixes=True),
         notes="the mixed-case twin: 'NEE' is unlisted by the caps "
               "shape test's OWN membership check too, so this one "
               "was already declining before this fix -- pinned "
               "beside its one-case sibling for the same guarantee"),
    # The 2026-09-18 review round's unpinned branches: live code paths
    # that no row named, found by reading the diff rather than by a
    # failure. Nothing here moved; every value is measured.
    Case("caps_switch_reads_the_name_level_case_past_a_clause",
         "née JONES XYZ",
         {"given": "née", "middle": "JONES", "family": "XYZ"},
         policy=Policy(unlisted_caps_suffixes=True),
         notes="the positive half of the two NEE rows above, and the "
               "row that fails if classify's caps branch is reverted "
               "to `one_case_own`: a marker OPENING the name leaves "
               "own_words EMPTY, so the name-level fact is one-case "
               "and nothing in the clause can join the shape class. "
               "Under `one_case_own` every token past the cut reads "
               "as mixed and 'XYZ' becomes a credential. "
               "test_classify.py monkeypatches the revert and asserts "
               "this very reading breaks"),
    Case("caps_one_case_comma_declines_a_single_token",
         "JOHN SMITH, XYZ",
         {"given": "XYZ", "family": "JOHN SMITH"},
         policy=Policy(unlisted_caps_suffixes=True),
         notes="the comma control for the one-case gate: two name "
               "words before the comma would flip the structure for a "
               "LISTED member, but the caps class needs a case "
               "contrast to be a member at all, and a wholly "
               "upper-case name has none. No report either -- there "
               "was no fork to call"),
    Case("caps_one_case_comma_declines_a_run",
         "JOHN SMITH, LEED AP",
         {"given": "LEED", "middle": "AP", "family": "JOHN SMITH"},
         policy=Policy(unlisted_caps_suffixes=True),
         notes="the multi-token twin: segment's run test asks "
               "`caps_shape_candidate` of every token and then reads "
               "the case fact ONCE, so a one-case name declines the "
               "whole run rather than per token"),
    Case("caps_run_needs_every_token_not_any",
         "John Smith, LEED BA",
         {"given": "LEED", "family": "John Smith", "suffix": "BA"},
         policy=Policy(unlisted_caps_suffixes=True),
         classification="fix(#531)",
         ambiguities=("suffix-or-name", "suffix-or-name"),
         notes="pins `all()` rather than `any()`: 'BA' is a LISTED "
               "ambiguous acronym, so the caps shape test excludes it "
               "and the run is no caps run -- the structure stays the "
               "listing form. The first report is assign's post-comma "
               "one, fired on 'LEED' alone, which carries the shape "
               "tag from classify whatever segment made of the run. "
               "#531 moves 'BA' itself: this is a family-comma name "
               "whose given part now ends in a class member, and the "
               "member is written in CAPITALS in a name written in "
               "more than one case, so it leans credential (#289) and "
               "reads suffix where it read middle -- its own second "
               "report. What #516 pins here is untouched: the caps "
               "run test still declines, and the structure is still "
               "the listing form"),
    Case("the_comma_count_counts_names_not_words_behind_a_title",
         "Mr Smith, Ma",
         {"given": "Ma", "family": "Mr Smith"},
         ambiguities=("suffix-or-name",),
         notes="MEASURED. name_word_count's TITLE arm: 'Mr' is title "
               "vocabulary, so the part before the comma holds ONE "
               "name word and the count declines the flip. Without "
               "that arm two tokens would read as two names and hand "
               "the family to `given`"),
    Case("the_comma_count_counts_names_not_words_behind_a_suffix",
         "Smith Jr, Ma",
         {"given": "Ma", "family": "Smith", "suffix": "Jr"},
         ambiguities=("suffix-or-name",),
         notes="the SUFFIX arm of the same count, and the shape "
               "decisions.md#S2 names: 'Smith Jr., MA' is two tokens "
               "and one name. The Title-case spelling declines where "
               "the all-caps one flips, which is the pair rules.md#C1 "
               "states"),
    Case("strict_comma_reads_the_dotted_numeral_as_a_name_word",
         "Smith V., Ma",
         {"given": "Smith", "family": "V.", "suffix": "Ma"},
         policy=Policy(lenient_comma_suffixes=False),
         ambiguities=("suffix-or-name",),
         notes="MEASURED, and a known rough edge recorded rather than "
               "repaired (decisions.md#S2, 2026-09-18). Under strict "
               "the initial-shaped 'V.' fails the suffix test, so "
               "name_word_count sees TWO name words before the comma, "
               "flips the structure, and the positional read of "
               "'Smith V.' gives given 'Smith', family 'V.'. "
               "Consistent with master: 'Smith V., PhD' reads the "
               "same way under the same knob, so this is the knob's "
               "own reading of 'V.' and not the credential class's"),
    Case("strict_comma_reads_the_bare_numeral_into_the_run",
         "Smith V, Ma",
         {"given": "Smith", "suffix": "V, Ma"},
         policy=Policy(lenient_comma_suffixes=False),
         ambiguities=("suffix-or-name", "suffix-or-name",
                      "given-or-family"),
         notes="the period is the whole difference from the row "
               "above: bare 'V' is still initial-shaped and still "
               "counts as a name word here, so the structure flips "
               "the same way -- but the trailing peel then takes it "
               "as the roman numeral, leaving 'Smith' the only name "
               "word and reporting all three forks"),
    Case("caps_run_declines_a_bound_given_head", "John Smith, ABDUL AP",
         {"given": "ABDUL AP", "family": "John Smith"},
         policy=Policy(unlisted_caps_suffixes=True),
         notes="the exclusion end to end rather than at the "
               "predicate: 'ABDUL' is bound-given vocabulary, so the "
               "run is no caps run and the part after the comma is "
               "the given name it would be at the default"),
    Case("caps_run_declines_a_conjunction", "John Smith, AND AP",
         {"given": "AND AP", "family": "John Smith"},
         policy=Policy(unlisted_caps_suffixes=True),
         notes="the same end to end for `conjunctions`, the row "
               "test_classify.py's predicate table names as the one "
               "that genuinely exercises that arm ('Y' declines at "
               "the two-character gate first)"),
    Case("caps_switch_leaves_a_capitalized_title_a_title",
         "John Smith, MR",
         {"title": "MR", "given": "John", "family": "Smith"},
         policy=Policy(unlisted_caps_suffixes=True),
         notes="`titles` end to end: the post-comma part holds no "
               "name word, so C1's no-name-word clause keeps the "
               "pre-comma positional read and 'MR' is the title it "
               "is at the default"),
    Case("a_period_final_delimited_clause_joins_the_shape_class",
         "Andrew Perkins (X.Y.Z.)",
         {"given": "Andrew", "family": "Perkins", "suffix": "X.Y.Z."},
         classification="fix(#516)",
         ambiguities=("suffix-or-name",),
         notes="MEASURED, and it NARROWS the note on "
               "caps_switch_does_not_reach_delimited_content: "
               "`_extract._suffix_shaped` releases period-final "
               "delimited content with role None, so it is ordinary "
               "trailing material by the time classify runs and the "
               "shape class claims it -- matching '(M.D)', which the "
               "escape already sent to `suffix`. What the "
               "`token.role is None` guard keeps out is content the "
               "escape did NOT release ('Bridge (A.B)', a nickname), "
               "which is a different population from 'delimited "
               "content' whole"),
    Case("a_leading_period_is_not_the_dotted_shape", "John Smith .XY",
         {"given": "John", "middle": "Smith", "family": ".XY"},
         notes="`period_joined_vocab` splits on interior periods, so "
               "a LEADING one leaves a single chunk and there is no "
               "acronym shape to read -- name material, and no fork "
               "was called, so nothing is reported"),
    Case("a_caseless_name_word_leaves_the_count_to_decide", "毛泽东 MA",
         {"given": "毛泽东", "family": "MA"},
         ambiguities=("suffix-or-name",),
         notes="the comma-less twin of the 毛泽东, MA row: one name "
               "word before the acronym, so the peel's two-piece "
               "floor declines it whatever the writing says, and the "
               "fork is reported all the same. Han is caseless, so "
               "the NAME is mixed-case (the all-caps 'MA' contrasts "
               "with nothing that has a case) -- the lean reads "
               "'credential' and the floor is what refuses it",
         tolerated=True),
    Case("a_digit_chunk_moves_the_trailing_slot_silently",
         "John Smith 1.4.2",
         {"given": "John", "middle": "Smith", "family": "1.4.2"},
         classification="fix(#516)",
         notes="ACCEPTED and SILENT, recorded at decisions.md#S2. "
               "rules.md#S3's narrow retirement drops a dotted token "
               "whose every matched chunk is a single ASCII "
               "character, and the vocabulary's lone digit '2' is one "
               "of them -- so the chunk claim goes, and the shape "
               "class cannot take it either, its own gate wanting "
               "every chunk ALPHABETIC. A version string read as a "
               "credential was the same accident the retirement "
               "removes, so it moves suffix -> family at every "
               "policy with no report"),
    Case("a_digit_chunk_moves_the_post_comma_slot_silently",
         "Smith, 1.4.2",
         {"given": "1.4.2", "family": "Smith"},
         classification="fix(#516)",
         notes="the comma twin: no candidate, so no flip and no "
               "report -- the part after the comma is simply the "
               "given name, where 2.3 read family 'Smith', suffix "
               "'1.4.2'"),
    Case("a_digit_chunk_moves_the_two_word_comma_slot_silently",
         "John Smith, 1.4.2",
         {"given": "1.4.2", "family": "John Smith"},
         classification="fix(#516)",
         notes="and with TWO name words before the comma, where a "
               "real class member would flip the structure: '1.4.2' "
               "is no member, so the listing form stands and the "
               "whole pre-comma run is the family. The widest of the "
               "three silent moves"),
    Case("the_comma_flip_is_read_under_the_declared_order",
         "John Smith, MA",
         {"given": "Smith", "family": "John", "suffix": "MA"},
         policy=Policy(name_order=FAMILY_FIRST),
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="MEASURED. The count flips the structure whatever the "
               "order -- it counts NAME words, which no order changes "
               "-- and the pre-comma run is then read positionally, "
               "so the declared order decides which of 'John Smith' "
               "is the family. The report's wording quotes the count, "
               "not a role, so it reads the same under every order"),
    Case("two_caps_credentials_peel_as_a_run",
         "John MA XYZ",
         {"given": "John", "suffix": "MA XYZ"},
         policy=Policy(unlisted_caps_suffixes=True),
         classification="fix(#516)",
         ambiguities=("given-or-family", "suffix-or-name",
                      "suffix-or-name"),
         notes="MEASURED, and the widest reading the switch reaches: "
               "the peel walks from the END, so 'XYZ' goes first (two "
               "pieces still stand behind it), and 'MA' then has "
               "'John' alone behind it -- but its LISTED lean says "
               "credential, which needs no words to spare. The name "
               "loses its family name entirely and says so three "
               "times. At the default it reads given John, middle MA, "
               "family XYZ, silently"),
    Case("the_caps_shape_is_script_agnostic_cyrillic",
         "Иван Петр ИВАНОВ",
         {"given": "Иван", "family": "Петр", "suffix": "ИВАНОВ"},
         policy=Policy(unlisted_caps_suffixes=True),
         classification="fix(#516)",
         ambiguities=("suffix-or-name",),
         notes="the switch's docstring claims `isupper()` is "
               "script-agnostic, so the convention and the reason for "
               "the default are the same in any script with a case "
               "contrast. Measured rather than asserted in prose: a "
               "Cyrillic all-caps surname joins the class exactly as "
               "'Jean Pierre DUPONT' does, and is swallowed the same "
               "way"),
    Case("the_dotted_switch_off_still_reports_the_post_comma_fork",
         "Smith, A.B.",
         {"given": "A.B.", "family": "Smith"},
         policy=Policy(unlisted_dotted_suffixes=False),
         ambiguities=("suffix-or-name",),
         notes="MEASURED. With the switch off the token never joins "
               "the class, so the STRUCTURE cannot flip -- but "
               "classify still writes SHAPE_ACRONYM_TAG (the fork was "
               "real and the parser declined it), and assign's "
               "post-comma report reads that tag directly. Exactly "
               "ONE report: the shape tag is on one piece and the "
               "reading is read off the first post-comma piece alone",
         classification="fix(#516)"),
    Case("the_dotted_switch_off_leaves_a_lone_token_to_the_convention",
         "A.B.", {"given": "A.B."},
         policy=Policy(unlisted_dotted_suffixes=False),
         ambiguities=("given-or-family",),
         notes="one piece, so the peel's two-piece floor refuses the "
               "class before the switch is consulted at all, and what "
               "is left is O5's lone-name-word convention. GIVEN_OR_"
               "FAMILY and nothing else -- pinned because the shape "
               "tag is present and must NOT produce a second report "
               "where no fork was taken"),
    Case("the_dotted_switch_off_leaves_a_titled_token_a_name",
         "Dr. A.B.", {"title": "Dr.", "family": "A.B."},
         policy=Policy(unlisted_dotted_suffixes=False),
         notes="the title floor: the peel's walk starts after the "
               "leading title run, so one piece is all it sees and "
               "the fork is never consulted -- no report at all, the "
               "same floor 'Mr MA' pins for the listed half"),
    Case("the_caps_shape_is_script_agnostic_accented",
         "Jean Pierre ÉCOLE",
         {"given": "Jean", "family": "Pierre", "suffix": "ÉCOLE"},
         policy=Policy(unlisted_caps_suffixes=True),
         classification="fix(#516)",
         ambiguities=("suffix-or-name",),
         notes="the other half of the same claim: a non-ASCII LATIN "
               "letter. `isalpha()`/`isupper()` are Unicode-wide, so "
               "an accented capital is admitted -- the docstring's "
               "'Jean ÉCOLE' example, given the third word it needs "
               "to have words to spare"),
    Case("catalan_i_is_not_connective_vocabulary_upper",
         "JOSEP CAROD I ROVIRA",
         {"given": "JOSEP", "middle": "CAROD I", "family": "ROVIRA"},
         notes="pinned at TODAY's reading so #397 shows its move: 'i' "
               "is not in CONJUNCTIONS at all, so the bare capital is "
               "an initial by shape and this row never reaches the "
               "fork. If #397 adds 'i' it ships in "
               "conjunctions_ambiguous too, and this row changes",
         shape=1),
    Case("catalan_i_is_not_connective_vocabulary_lower",
         "josep carod i rovira",
         {"given": "josep", "middle": "carod i", "family": "rovira"},
         notes="the lowercase twin: 'i' is an ordinary name word, not "
               "vocabulary, so nothing joins and nothing reports. This "
               "row pins NOTHING today -- both readings are what every "
               "release including 1.4.0 already gives -- and is kept "
               "anyway as the other half of #397's before-picture, "
               "beside its upper twin above",
         shape=1),
    # ---- #531: the given part's trailing slot ----------------------
    # The slot: after a family comma the comma has already named the
    # family and the first word after it is the given name, so a class
    # member ENDING the given part has words to spare by construction
    # and the count says nothing. The writing decides, exactly as it
    # does for the comma-less spelling of the same name.
    Case("the_given_parts_trailing_slot_reads_the_credential",
         "Doe, John MA",
         {"given": "John", "family": "Doe", "suffix": "MA"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="1.4.0 RESTORED: v1 read suffix 'MA' and 2.0 through "
               "2.3 read middle 'MA' in silence. The comma fixed the "
               "family and the first post-comma word is the given "
               "name, so the words-to-spare count is satisfied by "
               "construction and the positional reading at this slot "
               "IS the credential. Same answer as the comma-less "
               "'John Doe MA', which is the whole point "
               "(decisions.md#S2)",
         shape=2),
    Case("the_given_parts_trailing_dotted_slot_reads_the_credential",
         "Doe, John X.Y.Z.",
         {"given": "John", "family": "Doe", "suffix": "X.Y.Z."},
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="the BY-SHAPE half of the same slot, and the half that "
               "does NOT restore 1.4.0: v1 read middle 'X.Y.Z.' here "
               "and this becomes a suffix. `listed_lean` returns None "
               "wherever the shape tag rides, so a by-shape member "
               "never leans and falls to the positional reading, which "
               "at this slot is the credential -- matching the "
               "comma-less 'John Doe X.Y.Z.' and the 2.4 shape rule "
               "rather than v1. One name, one new divergence, accepted "
               "(decisions.md#S2)",
         shape=2),
    Case("the_given_parts_trailing_slot_in_all_caps",
         "DOE, JOHN MA",
         {"given": "JOHN", "family": "DOE", "suffix": "MA"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="one case, so the lean is inert and the positional "
               "reading decides alone -- and at this slot it is the "
               "credential. 1.4.0 parity",
         shape=2),
    Case("the_given_parts_trailing_slot_in_all_lower",
         "doe, john ma",
         {"given": "john", "family": "doe", "suffix": "ma"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="the other one-case spelling, same reason as its "
               "all-caps twin: nothing leans, the position decides. "
               "1.4.0 parity",
         shape=2),
    Case("the_trailing_slot_reads_every_listed_member",
         "Doe, John BA",
         {"given": "John", "family": "Doe", "suffix": "BA"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="'ba' is another listed member (one of the five "
               "decisions.md#suffix-acronym-collisions marked "
               "ambiguous rather than removing), so the slot is not a "
               "rule about 'ma' -- it is the whole class",
         shape=2),
    Case("the_trailing_slot_leaves_the_middle_initial_alone",
         "Doe, John Q. MA",
         {"given": "John", "middle": "Q.", "family": "Doe",
          "suffix": "MA"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="the member leaves the given part and 'Q.' stays the "
               "middle initial it always was -- the slot reaches the "
               "trailing word, not the run in front of it. 1.4.0 "
               "parity on both fields",
         shape=2),
    Case("the_trailing_slot_joins_the_credential_run_behind_it",
         "Doe, John MA PhD",
         {"given": "John", "family": "Doe", "suffix": "MA PhD"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="'ending the given part' REACHES PAST the credentials "
               "behind it, so 'MA' joins the run rather than being "
               "walled off by it. Rendered with a SPACE and not a "
               "comma: R1 derives suffix entries from the commas the "
               "WRITER typed (#436/#437), so only 'Doe, John MA, PhD' "
               "renders 'MA, PhD'. 1.4.0 wrote a comma in both. ONE "
               "report: 'PhD' is settled vocabulary and carries "
               "neither class tag",
         shape=2),
    Case("the_trailing_slot_reaches_past_a_generational_suffix",
         "Doe, John MA Jr",
         {"given": "John", "family": "Doe", "suffix": "MA Jr"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="the run behind the member does not have to be "
               "credentials -- a generational suffix is a suffix "
               "piece and the walk reaches past it the same way",
         shape=2),
    Case("the_trailing_slot_is_a_run_not_a_position",
         "Doe, John PhD MA",
         {"given": "John", "family": "Doe", "suffix": "PhD MA"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="the member stands LAST here and the settled "
               "credential in front of it is what used to strand it: "
               "2.0 through 2.3 read middle 'MA' with suffix 'PhD', "
               "which is a name word behind a post-nominal. One "
               "reading now, and it is 1.4.0's",
         shape=2),
    Case("the_trailing_slot_survives_a_third_comma_part",
         "Doe, John MA, PhD",
         {"given": "John", "family": "Doe", "suffix": "MA, PhD"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="#144's two-segment restriction is NOT inherited by "
               "this branch. That restriction exists because a "
               "trailing 'V' before a third comma part is likely a "
               "middle initial; 'MA' is not initial-shaped, and a "
               "credential list behind it makes the credential "
               "reading MORE likely rather than less. The comma the "
               "writer typed is what renders here, which is why this "
               "row shows 'MA, PhD' where its spaced twin shows "
               "'MA PhD' (#436/#437)"),
    Case("two_members_in_the_trailing_run_report_twice",
         "Doe, John MA JD",
         {"given": "John", "family": "Doe", "suffix": "MA JD"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name", "suffix-or-name"),
         notes="one decision, one report; two members, two reports -- "
               "matching 'John Doe MA JD', which reports twice today. "
               "No token is ever reported twice: these are two "
               "tokens",
         shape=2),
    # ---- the declined direction: the reading does NOT move and the
    # report is new. Derek's Q4, answered 'report both directions':
    # #530's rule is that the report tracks the FORK CONSULTED, not
    # the lean.
    Case("the_trailing_slot_declines_a_title_cased_member",
         "Doe, John Ma",
         {"given": "John", "middle": "Ma", "family": "Doe"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="Title case in a mixed-case name is written the way a "
               "NAME is written, so the member stays a middle name -- "
               "and the fork was consulted, so it reports. The first "
               "of the rows where #531 adds a report without moving a "
               "field; 'Doe, Mary Jo Ma', 'Doe, John Ed' and 'Doe, "
               "John MA Ma' below are the others, each declining on "
               "the same signal. It is the same rule the comma-less "
               "'John Doe Ma' has followed since #289",
         shape=2),
    Case("the_trailing_slot_declines_behind_two_given_words",
         "Doe, Mary Jo Ma",
         {"given": "Mary", "middle": "Jo Ma", "family": "Doe"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="the lean does not care how many given words stand in "
               "front -- Title case declines here exactly as it does "
               "with one. 1.4.0 read middle 'Jo', suffix 'Ma'; the "
               "case signal is what this release chose over that",
         shape=2),
    Case("the_trailing_slot_declines_a_title_cased_name_word",
         "Doe, John Ed",
         {"given": "John", "middle": "Ed", "family": "Doe"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="'Ed' is a given name far more often than it is a "
               "doctorate, and Title case is how that is written. The "
               "report is how a caller finds the other reading",
         shape=2),
    Case("the_trailing_slot_declines_then_takes_the_next_member",
         "Doe, John Ma JD",
         {"given": "John", "middle": "Ma", "family": "Doe",
          "suffix": "JD"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name", "suffix-or-name"),
         notes="two members, two decisions, two reports -- and they "
               "go opposite ways. 'JD' is all-caps and takes the "
               "credential; 'Ma' is Title-cased and stays a name, "
               "which also ENDS the run, so nothing in front of it is "
               "reached"),
    Case("a_declined_member_ends_the_trailing_run",
         "Doe, John MA Ma",
         {"given": "John", "middle": "MA Ma", "family": "Doe"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="the trailing member declines on its Title case, and "
               "the walk stops at the declined pick rather than "
               "continuing past it -- so the all-caps 'MA' in front "
               "is never asked and never reports. ONE report, for "
               "'Ma'. Identical in shape to rules.md#S2's accepted "
               "'Jack Wei Ma' clause",
         shape=2),
    Case("a_taken_member_behind_a_declined_one_still_reports",
         "Doe, John Ma MA",
         {"given": "John", "middle": "Ma", "family": "Doe",
          "suffix": "MA"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name", "suffix-or-name"),
         notes="the mirror of the row above, and the pair is the "
               "argument: order in the string decides which member "
               "the run reaches. Here the trailing 'MA' is taken, the "
               "run then reaches 'Ma', which declines and ends it"),
    Case("a_third_member_behind_the_declined_one_stays_silent",
         "Doe, John MA Ma MA",
         {"given": "John", "middle": "MA Ma", "family": "Doe",
          "suffix": "MA"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name", "suffix-or-name"),
         notes="the run walked to its floor and then measured against "
               "it: the trailing 'MA' is taken, 'Ma' declines on its "
               "Title case and STOPS the run there, and the leading "
               "'MA' -- behind a piece this walk refused -- is an "
               "ordinary middle name, silent. TWO reports, for 'Ma' "
               "and the trailing 'MA'; the third member reaches no "
               "fork. The row that would catch a floor left over from "
               "an earlier member, since the three members ask the "
               "same walk three times and only the first two are "
               "above the floor. Today middle 'MA Ma MA', silent"),
    # ---- H5: a trailing title is transparent to this reading ------
    Case("a_trailing_title_is_transparent_to_the_slot",
         "Doe, John MA Prof.",
         {"title": "Prof.", "given": "John", "family": "Doe",
          "suffix": "MA"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="the walk starts at previous_kept(), which is the H5 "
               "chain's own notion of where the name ends -- so "
               "'past a trailing title' costs no second definition "
               "of 'trailing'. 1.4.0 read middle 'Prof.', suffix "
               "'MA'; the title role is 2.x's own H5 and not at "
               "stake here"),
    Case("a_title_in_front_of_the_member_becomes_a_title",
         "Doe, John Prof. MA",
         {"title": "Prof.", "given": "John", "family": "Doe",
          "suffix": "MA"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="MEASURED, and a SECOND field moves: today this is "
               "middle 'Prof. MA'. Once 'MA' leaves `walkable` the "
               "H5 trailing-title chain reaches 'Prof.' and takes "
               "it. That is H5's stated transparency working, and it "
               "lands this row on the same answer as its neighbour "
               "above rather than against it"),
    Case("a_leading_title_does_not_block_the_slot",
         "Doe, Dr. John MA",
         {"title": "Dr.", "given": "John", "family": "Doe",
          "suffix": "MA"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="the leading title run is peeled before the walk "
               "starts, so the slot sees exactly what it sees "
               "without it. 1.4.0 parity",
         shape=2),
    Case("an_initial_given_name_does_not_block_the_slot",
         "Doe, J. MA",
         {"given": "J.", "family": "Doe", "suffix": "MA"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="the first post-comma piece is the given name "
               "whatever its shape, so a one-letter given leaves the "
               "member at the trailing slot as any other would. "
               "1.4.0 parity",
         shape=2),
    Case("the_trailing_slot_reads_two_given_words_in_one_case",
         "DOE, MARY JO MA",
         {"given": "MARY", "middle": "JO", "family": "DOE",
          "suffix": "MA"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="an ACCEPTED COST stated plainly: one case carries no "
               "contrast, so the positional reading takes the member "
               "and a record writing a middle name in capitals loses "
               "it. 1.4.0 read exactly this, and the comma-less form "
               "has carried the same cost since 2.0",
         shape=2),
    # ---- the negative controls: the reading does NOT move and
    # NOTHING is reported -----------------------------------------
    Case("a_name_word_behind_the_member_ends_the_reach",
         "Doe, John MA Smith",
         {"given": "John", "middle": "MA Smith", "family": "Doe"},
         classification="fix(comma-family)",
         notes="UNCHANGED and SILENT, and the silence is the point: "
               "a name word behind the member ends the trailing run, "
               "so the member is an ordinary middle name and no fork "
               "was consulted. AGENTS.md's 'a kind is worth adding "
               "only if a reader would hesitate too' is why this must "
               "stay silent rather than why it happens to -- that "
               "sentence is the 2.0-conventions section's, and this "
               "note cited rules.md#A1 for it until 2026-09-19. NOT "
               "1.4.0 "
               "parity, and not #531's doing either: v1 read middle "
               "'Smith', suffix 'MA', and 2.0.0 already read what "
               "this row reads (both measured on the released wheels, "
               "2026-09-18). What moved was 2.0 reading the "
               "post-comma part's suffix vocabulary by POSITION, so "
               "the divergence files under the family-comma group "
               "rather than under the case signal -- measured "
               "case-independent, 'DOE, JOHN MA SMITH' and "
               "'doe, john ma smith' reading the same way",
         shape=2),
    Case("a_multi_token_piece_never_reaches_the_slot",
         "Doe, John MA y",
         {"given": "John", "middle": "MA y", "family": "Doe"},
         classification="fix(comma-family)",
         notes="the slot reads a PIECE, not a token: 'y' is a "
               "conjunction, so grouping joins 'MA y' into one piece "
               "and both len() tests -- the branch's and the report "
               "gate's -- decline it. The row that PINS them, and the "
               "one the particle rows above cannot be: delete the "
               "branch's test and the piece reads as a credential, "
               "suffix 'MA y'; delete the report gate's and 'MA' is "
               "reported where nothing was decided (both measured "
               "2026-09-19). 'Doe, John A.B. e' is the by-shape "
               "spelling of the same piece and moves with it, so it "
               "gets no row of its own. UNCHANGED by #531 -- 2.0.0 "
               "and 2.3.0 read this middle too, where 1.4.0 read "
               "middle 'y', suffix 'MA' -- and the divergence is "
               "'Doe, John MA Smith's, the post-comma part read by "
               "POSITION since 2.0",
         shape=2),
    Case("a_maiden_clause_takes_the_member_with_it",
         "Doe, Jane nee Smith MA",
         {"given": "Jane", "family": "Doe", "suffix": "MA",
          "maiden": "Smith"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="the row that named the silence, now naming the "
               "reading. The maiden marker no longer claims a "
               "trailing credential: the words it takes end where a "
               "trailing credential begins, and after a family comma "
               "the reader of what is left standing is the given "
               "part's own trailing slot (#531), which reads 'MA' as "
               "the credential. 1.4.0 had no maiden routing and read "
               "middle 'nee Smith', suffix 'MA', so the SUFFIX is "
               "1.4.0 parity and the maiden field is not; 2.0.0 "
               "through 2.3.0 read maiden 'Smith MA' in silence "
               "(measured 2026-09-19). Keeping the id: it is the same "
               "question, answered the other way",
         shape=2),
    # ---- #533: the maiden clause's trailing credential -------------
    # The rule: the words a maiden marker takes end where a trailing
    # credential begins, and a member of the ambiguous credential
    # class is one of those -- but only where the rule that reads the
    # name left standing reads it as the credential, both as written
    # and as the take would leave it. That is the same double question
    # the trailing roman numeral is asked, for the same reason: the
    # count of words to spare includes the very words the marker
    # removes.
    Case("a_trailing_credential_ends_the_maiden_clause",
         "Jane Doe nee Smith MA",
         {"given": "Jane", "family": "Doe", "suffix": "MA",
          "maiden": "Smith"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="the comma-less spelling of the row above, and the "
               "statement of the rule. The peel over the pieces as "
               "they stand takes 'MA', and the peel over the view the "
               "take would leave ('Jane Doe MA') takes it too, so the "
               "clause stops before it. 1.4.0 read middle 'Doe nee', "
               "family 'Smith', suffix 'MA' -- the suffix restored, "
               "the maiden field new since #274",
         shape=1),
    Case("the_clause_keeps_the_member_its_writing_declines",
         "Jane Doe nee Smith Ma",
         {"given": "Jane", "family": "Doe", "maiden": "Smith Ma"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="the other direction, and the one that carries most of "
               "this change's visible effect at the default: Title "
               "case in a mixed-case name is written the way a NAME "
               "is written, so the peel declines the member and the "
               "clause keeps it -- and the fork was consulted, so it "
               "reports. The reading is unchanged from 2.0.0 through "
               "2.3.0; only the report is new. 1.4.0 read suffix 'Ma'",
         shape=1),
    Case("the_all_caps_clause_reads_the_credential",
         "JANE DOE NEE SMITH MA",
         {"given": "JANE", "family": "DOE", "suffix": "MA",
          "maiden": "SMITH"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="one case, so the lean is inert and the count decides "
               "alone -- and with 'Jane Doe' standing in front of the "
               "clause there are words to spare both as written and "
               "as the take would leave the name. 1.4.0 parity on the "
               "suffix",
         shape=1),
    Case("the_all_lower_clause_reads_the_credential",
         "jane doe nee smith ma",
         {"given": "jane", "family": "doe", "suffix": "ma",
          "maiden": "smith"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="the other one-case spelling, same reason as its "
               "all-caps twin. 1.4.0 parity on the suffix",
         shape=1),
    Case("the_clause_keeps_a_member_standing_alone_after_the_marker",
         "Jane Doe nee MA",
         {"given": "Jane", "family": "Doe", "maiden": "MA"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="the FLOOR, and it is deliberate that this differs "
               "from what a suffix word or a roman numeral gets in "
               "the same position ('Jane Smith nee PhD' and 'Jane "
               "Smith nee V' leave the marker standing as an ordinary "
               "word). The marker announces a NAME, and the rule "
               "gives a word up only where a maiden name is left "
               "standing; certain suffix vocabulary declines the "
               "marker, an ambiguous word is kept by the clause it "
               "ends. It reports all the same. 1.4.0 read family "
               "'nee', suffix 'MA', so this half restores nothing and "
               "does not try to",
         shape=1),
    Case("a_name_word_behind_the_member_leaves_the_clause_silent",
         "Jane Doe nee MA Smith",
         {"given": "Jane", "family": "Doe", "maiden": "MA Smith"},
         classification="fix(#274)",
         ambiguities=(),
         notes="the recorded negative control for the emitter: the "
               "word the walk was asked about is the LAST piece of "
               "the maiden name, and a member with a name word behind "
               "it is never that piece. Nothing was consulted, so "
               "nothing reports -- which is what rules.md#A1's "
               "hesitating reader asks for rather than an accident of "
               "where the emitter sits. Unchanged from 2.0.0; 1.4.0 "
               "read middle 'Doe nee MA', family 'Smith'",
         shape=1),
    Case("the_clause_gives_up_the_whole_credential_run",
         "Jane Doe nee Smith MA PhD",
         {"given": "Jane", "family": "Doe", "suffix": "MA PhD",
          "maiden": "Smith"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="the peel walks the run from the end, so 'PhD' is "
               "settled vocabulary and 'MA' is the fork it reaches "
               "behind it -- one report, not two. Rendered with a "
               "SPACE: R1 derives suffix entries from the commas the "
               "WRITER typed (#436/#437), where 1.4.0 wrote 'MA, "
               "PhD'. 2.0.0 through 2.3.0 read maiden 'Smith MA' with "
               "suffix 'PhD', which is the order-sensitivity the "
               "issue reported",
         shape=1),
    Case("the_credential_run_reads_the_same_written_the_other_way",
         "Jane Doe nee Smith PhD MA",
         {"given": "Jane", "family": "Doe", "suffix": "PhD MA",
          "maiden": "Smith"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="the control the row above needs, and the whole point "
               "of the issue: this spelling already stopped at the "
               "suffix WORD and read both credentials, so whether the "
               "member was read at all used to depend on which side "
               "of 'PhD' the writer put it. Unchanged here -- the two "
               "orders now agree",
         shape=1),
    Case("the_declined_member_still_ends_the_clause_for_the_run",
         "Jane Doe nee Smith Ma JD",
         {"given": "Jane", "family": "Doe", "suffix": "JD",
          "maiden": "Smith Ma"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name", "suffix-or-name"),
         notes="both halves in one name: 'JD' is taken and reported "
               "by assign where it peels it, 'Ma' is declined by its "
               "writing and reported by the walk that kept it. TWO "
               "reports, one per member, and never two for one word "
               "-- the maiden pieces are gone before the chain runs. "
               "1.4.0 read suffix 'Ma, JD'",
         shape=1),
    Case("two_members_ending_the_clause_report_once_each",
         "Jane Doe nee Smith MA JD",
         {"given": "Jane", "family": "Doe", "suffix": "MA JD",
          "maiden": "Smith"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name", "suffix-or-name"),
         notes="the same pair with both members taken. The peel "
               "resolves each in turn and assign reports both; the "
               "walk reports none, the last maiden piece being an "
               "ordinary name word",
         shape=1),
    Case("the_dotted_member_ends_the_clause",
         "John Smith nee Jones R.A.I.",
         {"given": "John", "family": "Smith", "suffix": "R.A.I.",
          "maiden": "Jones"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="the name #530's close-out reported from the other "
               "side, and this row RESTORES 2.3.0 rather than "
               "changing it: at 2.3.0 'R.A.I.' carried vocab:suffix "
               "and the walk's suffix-piece test stopped at it, while "
               "#516 retagged it shape:acronym plus "
               "vocab:suffix-ambiguous, it stopped being a suffix "
               "piece, and the walk took it -- maiden 'Jones R.A.I.' "
               "on this tree, unrecorded because the name was in no "
               "corpus file. 1.4.0 read middle 'Smith nee', family "
               "'Jones', suffix 'R.A.I.' (all measured 2026-09-19)",
         shape=1),
    Case("the_dotted_member_is_kept_with_the_switch_off_and_reports",
         "John Smith nee Jones R.A.I.",
         {"given": "John", "family": "Smith", "maiden": "Jones R.A.I."},
         policy=Policy(unlisted_dotted_suffixes=False),
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="with the switch off classify writes the SHAPE tag and "
               "the class does not admit the token, so the PEEL "
               "declines to consume it -- it records the word in "
               "`picks` and breaks, leaving nothing for the walk's "
               "own reading gate to be asked about -- and the clause "
               "keeps the word. The emitter's gate reads EITHER tag, "
               "as the chain emitter's does, so the declined fork is "
               "still reported. That asymmetry is the whole of the "
               "two gates' difference and is what this row pins. "
               "Measured 2026-09-19 by stepping the peel, not "
               "reasoned from the gate's text"),
    Case("the_caps_switch_reaches_the_clause",
         "Jane Doe nee Smith XYZ",
         {"given": "Jane", "family": "Doe", "suffix": "XYZ",
          "maiden": "Smith"},
         policy=Policy(unlisted_caps_suffixes=True),
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="the opt-in class reaches this slot like any other, "
               "the switch being what admits the token to the "
               "ambiguous class in the first place"),
    Case("an_unlisted_word_is_no_member_of_the_class",
         "Jane Doe nee Smith XYZ",
         {"given": "Jane", "family": "Doe", "maiden": "Smith XYZ"},
         classification="fix(#274)",
         ambiguities=(),
         notes="the default-policy control for the row above, and the "
               "recorded negative control for the membership gate: "
               "with the caps switch off 'XYZ' carries neither tag, "
               "so the walk never asks and the clause keeps it in "
               "silence. 1.4.0 read family 'XYZ'",
         shape=1),
    Case("the_peel_never_reaches_a_title_behind_the_member",
         "Jane Doe nee Smith MA Prof.",
         {"given": "Jane", "family": "Doe", "maiden": "Smith MA Prof."},
         classification="fix(#274)",
         ambiguities=(),
         notes="the H5 BOUNDARY, recorded rather than fixed: the "
               "maiden walk has always read peel_trailing alone, and "
               "the trailing-title chain lives in tail_reading, which "
               "trailing_start does not run -- so the peel breaks at "
               "'Prof.' and never reaches the member behind it. This "
               "change inherits that boundary rather than creating "
               "it, and a follow-up carries the question of whether "
               "the walk should move onto tail_reading (both forks, "
               "numeral included). Silent, because nothing was asked",
         shape=1),
    Case("a_title_in_front_of_the_member_is_the_other_spelling",
         "Jane Doe nee Smith Prof. MA",
         {"given": "Jane", "family": "Doe", "suffix": "MA",
          "maiden": "Smith Prof."},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="the boundary's other side, and the pair is the "
               "finding: the two spellings DISAGREE here, where at "
               "the given part's own trailing slot they agree "
               "(#531's 'Doe, John MA Prof.' and 'Doe, John Prof. "
               "MA' land on one answer). The peel reaches 'MA' "
               "because nothing stands behind it, so the clause stops "
               "and 'Prof.' stays maiden text. 1.4.0 read family "
               "'Prof.', suffix 'MA'",
         shape=1),
    Case("a_connective_behind_the_member_stops_the_peel",
         "Jane Doe nee Smith MA y",
         {"given": "Jane", "family": "Doe", "maiden": "Smith MA y"},
         classification="fix(#274)",
         ambiguities=(),
         notes="the recorded negative control for the PEEL's reach, "
               "measured 2026-09-19 rather than reasoned: the marker "
               "pass runs before every join, so 'MA' and 'y' are two "
               "pieces here and no joined one -- and 'y' is no "
               "suffix, so the peel takes nothing, the walk is never "
               "asked about the member behind it, and the clause "
               "keeps both words. The connective joins them a stage "
               "later, into the maiden name. Silent for the reason "
               "the row below is: nothing was decided",
         shape=1),
    Case("the_numeral_half_of_the_walk_is_unmoved",
         "Jane Doe nee Smith V",
         {"given": "Jane", "family": "Doe", "suffix": "V",
          "maiden": "Smith"},
         classification="fix(#424)",
         ambiguities=("suffix-or-name",),
         notes="#424's own fork, pinned beside the acronym one "
               "because the two now share a single peel: the numeral "
               "half answers off Peel.numeral exactly as it did, and "
               "this row is what says the shared call did not move "
               "it. Unchanged since #424",
         shape=1),
    Case("the_digit_shaped_trailing_suffix_is_unmoved_and_silent",
         "Jane Doe nee Smith 2",
         {"given": "Jane", "family": "Doe", "suffix": "2",
          "maiden": "Smith"},
         classification="fix(#424)",
         ambiguities=(),
         notes="the numeral half's silent twin -- a lone digit is "
               "generational vocabulary and no fork, so the walk "
               "stops and nothing reports. The pair with the row "
               "above is what separates 'the walk stopped' from 'the "
               "walk reported'",
         shape=1),
    Case("the_one_case_record_loses_its_second_birth_word",
         "JANE DOE NEE YO-YO MA",
         {"given": "JANE", "family": "DOE", "suffix": "MA",
          "maiden": "YO-YO"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="an ACCEPTED COST, and the control beside it is what "
               "makes it the one-case reading's cost rather than this "
               "rule's: 'JANE YO-YO MA' reads suffix 'MA' too, so the "
               "clause form now agrees with the bare form. In mixed "
               "case the writing saves the name -- see the row below",
         shape=1),
    Case("the_one_case_records_control_without_the_clause",
         "JANE YO-YO MA",
         {"given": "JANE", "family": "YO-YO", "suffix": "MA"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="the recorded control for the accepted cost above. "
               "Unchanged by this rule and read by #289's count, "
               "which is the point: a clause must not change how a "
               "word outside it reads, and here the clause form "
               "joined the bare form rather than the other way round",
         shape=1),
    Case("the_mixed_case_record_keeps_its_second_birth_word",
         "Jane Doe nee Yo-Yo Ma",
         {"given": "Jane", "family": "Doe", "maiden": "Yo-Yo Ma"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="the same two-word birth surname where the writing "
               "CAN speak: Title case in a mixed-case name declines "
               "the peel, so 'Yo-Yo Ma' stays whole and the fork "
               "reports. 1.4.0 read family 'Yo-Yo', suffix 'Ma'",
         shape=1),
    Case("the_view_check_asks_whether_the_reader_takes_that_word",
         "JOHN NEE JONES SMITH MA PHD",
         {"family": "JOHN", "suffix": "PHD",
          "maiden": "JONES SMITH MA"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="the row that distinguishes the check this change "
               "SHIPS from the weaker one. The take would leave "
               "'JOHN MA PHD', whose peel takes 'PHD' and then "
               "DECLINES 'MA' for want of words to spare -- so 'does "
               "the reader take SOMETHING' answers yes while 'MA' "
               "becomes the FAMILY name, which is #424's own disaster "
               "one word further on. The check compares the view's "
               "run start against the member's index in it, answers "
               "no, and the clause keeps the word -- reporting, "
               "because the fork was consulted and declined",
         shape=1),
    Case("the_view_checks_control_without_the_clause",
         "JOHN MA PHD",
         {"given": "JOHN", "family": "MA", "suffix": "PHD"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="the recorded control: this IS the view the take would "
               "leave, and family 'MA' is what the row above must "
               "not produce. Unchanged",
         shape=1),
    Case("a_dangling_connective_can_end_a_maiden_name",
         "Jane Smith nee Jones and MA",
         {"given": "Jane", "family": "Smith", "suffix": "MA",
          "maiden": "Jones and"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="an ACCEPTED COST. The take runs before the joins "
               "(#420), so the connective is a piece of its own when "
               "the walk stops and the maiden name ends on it; M2's "
               "Accepted row about the join order already owns this "
               "shape. Untagged: the point is the stage order, not "
               "the input shape"),
    Case("a_marker_phrase_ends_at_the_credential_too",
         "Maria Kowalska z domu Nowak MA",
         {"given": "Maria", "family": "Kowalska", "suffix": "MA",
          "maiden": "Nowak"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="the rule is about the marker's CLAUSE, not about a "
               "one-word marker: the Polish phrase entry (#434) "
               "reaches the same walk and the same stop. 1.4.0 read "
               "middle 'Kowalska z domu', family 'Nowak', suffix 'MA'",
         shape=1),
    Case("the_german_marker_ends_at_the_credential_too",
         "Jane Doe geb. Smith MA",
         {"given": "Jane", "family": "Doe", "suffix": "MA",
          "maiden": "Smith"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="a second vocabulary spelling, for the same reason as "
               "the row above: nothing here is about the word 'nee'",
         shape=1),
    Case("a_kyusei_clause_ends_at_the_credential",
         "田中 太郎 旧姓 佐藤 MA",
         {"given": "太郎", "family": "田中", "suffix": "MA",
          "maiden": "佐藤"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="the CJK marker reaches the walk like any other, and "
               "the Latin credential behind it is read by the Latin "
               "rule -- is_one_case answers True for a caseless "
               "script, so the lean is inert and the count decides. "
               "tolerated rather than shape-tagged: a Latin "
               "credential wrapped around a CJK name is a composed "
               "form (the 2026-09-01 demotion), read best-effort",
         tolerated=True),
    # ---- #533 after a family comma: #531's slot is the reader ------
    Case("the_comma_reader_declines_the_title_cased_member",
         "Doe, Jane nee Smith Ma",
         {"given": "Jane", "family": "Doe", "maiden": "Smith Ma"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="after a family comma the comma has already settled "
               "the count, so the reader is #531's slot and the "
               "writing decides alone -- Title case in a mixed-case "
               "name keeps the word. Reported either way. 1.4.0 read "
               "suffix 'Ma'",
         shape=2),
    Case("the_comma_reader_takes_the_all_lower_member",
         "Doe, Jane nee Smith ma",
         {"given": "Jane", "family": "Doe", "suffix": "ma",
          "maiden": "Smith"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="the row that makes the COMMA reader load-bearing "
               "rather than decorative: the count-based reader "
               "declines an all-lower member with two pieces to "
               "spare, and #531's declines nothing but a particle. "
               "Measured -- this name moves under the comma reader "
               "and would not under the count. 'Doe, Jane ma' already "
               "reads suffix 'ma', which is what the clause form now "
               "agrees with",
         shape=2),
    Case("the_do_pair_after_a_comma_keeps_the_particle_spelling",
         "Doe, Jane nee Smith do",
         {"given": "Jane", "family": "Doe", "maiden": "Smith do"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="'do' is the one class member that is also particle "
               "vocabulary, so after a comma the clause's trailing "
               "slot, #531's slot and P6's attachment all want it -- "
               "and the reading is #531's, unchanged and shared "
               "through one predicate. Lean None plus a particle tag "
               "means P6's word, so the clause keeps it and reports "
               "the fork it consulted",
         shape=2),
    Case("the_do_pair_after_a_comma_reads_the_capitals",
         "Doe, Jane nee Smith DO",
         {"given": "Jane", "family": "Doe", "suffix": "DO",
          "maiden": "Smith"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="the same word where the capitals speak: a positive "
               "credential lean is the one spelling that outranks "
               "P6's attachment (decisions.md#S2, 2026-09-18), so the "
               "clause gives the word up. 1.4.0 read suffix 'DO'",
         shape=2),
    Case("the_no_comma_do_reads_by_the_count_instead",
         "Jane Doe nee Smith do",
         {"given": "Jane", "family": "Doe", "suffix": "do",
          "maiden": "Smith"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="the row the issue flagged as needing a decision, and "
               "it goes the other way from its comma twin BECAUSE the "
               "reader is different: with no comma the reader is the "
               "S2 peel over the view, which reads the count, and "
               "P6 does not run at all. The comma-less 'John Doe do' "
               "reads suffix 'do' today, and a clause must not change "
               "how a word outside it reads -- so the two now agree",
         shape=1),
    Case("the_no_comma_dos_control_without_the_clause",
         "John Doe do",
         {"given": "John", "family": "Doe", "suffix": "do"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="the recorded control for the row above. Unchanged, "
               "and it is what the clause form was measured against",
         shape=1),
    Case("the_comma_floor_keeps_a_member_a_particle_follows",
         "Doe, Jane nee Smith MA do",
         {"given": "Jane", "family": "Doe", "maiden": "Smith MA do"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="where #531's FLOOR earns its place, and a check that "
               "asked only about 'MA' got this wrong: the take would "
               "leave 'Jane MA do', where 'do' does not read as a "
               "suffix (P6 keeps it) so #531's slot reads 'MA' as a "
               "MIDDLE name -- releasing it from the clause would "
               "move a word from one person's name into another's. "
               "With the floor the clause keeps 'MA do' whole, and "
               "reports the 'do' it kept. rules.md#S2's own 'Doe, "
               "John MA do' clause is the reading this rests on",
         shape=2),
    Case("the_clamp_never_takes_the_first_word_after_the_marker",
         "Doe, J. nee MA ba",
         {"given": "J.", "family": "Doe", "suffix": "ba",
          "maiden": "MA"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name", "suffix-or-name"),
         notes="the floor is a CLAMP, not a veto, and this row is "
               "why. The peel takes 'ba' and then 'MA', so the first "
               "piece the peel took IS the only maiden word; a veto "
               "that cancelled the stop whenever nothing would be "
               "left handed 'ba' back to the clause too, giving "
               "maiden 'MA ba' where 'Doe, J. ba' reads suffix 'ba'. "
               "Clamped to the piece after the marker, the clause "
               "keeps 'MA' and gives 'ba' up. TWO reports: the walk's "
               "for the word it kept, assign's for the word it took",
         shape=2),
    Case("the_clamps_control_without_the_clause",
         "Doe, J. ba",
         {"given": "J.", "family": "Doe", "suffix": "ba"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="the recorded control for the clamp: this is what the "
               "released 'ba' must go on reading, and it is #531's "
               "slot doing the reading. 'ba' is the fifth listed "
               "member, the one decisions.md#suffix-acronym-collisions "
               "marked ambiguous rather than removing. 1.4.0 parity",
         shape=2),
    Case("the_clause_leaves_a_middle_initial_alone",
         "Doe, Jane Q. nee Smith MA",
         {"given": "Jane", "middle": "Q.", "family": "Doe",
          "suffix": "MA", "maiden": "Smith"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="the member leaves the clause and 'Q.' stays the "
               "middle initial it always was -- the stop reaches the "
               "clause's trailing word, not the name in front of it",
         shape=2),
    Case("a_no_name_segment_leaves_the_clause_nobody_to_read_it",
         "Doe, Dr. nee Smith MA",
         {"title": "Dr.", "family": "Doe", "maiden": "Smith MA"},
         classification="parity",
         ambiguities=("suffix-or-name",),
         notes="rules.md#M2's invariant, and the row that used to "
               "record the opposite: an earlier round of #533 read "
               "suffix 'MA' here and said so in silence. Once 'Smith' "
               "leaves with the marker, segment 1 is 'Dr. MA' -- a "
               "no-name segment, which the credential-run gate reads "
               "whole without ever reaching #531's emitter, so the "
               "released word would have landed in `given`, not in "
               "`suffix`. With no name word ahead of it the member is "
               "no trailing word of a given part, the walk declines, "
               "and the clause keeps it. The REPORT survives the "
               "decline: the emitter asks whether a trailing rule "
               "reads these words at all, which after a family comma "
               "it does. 1.4.0 read given 'nee', middle 'Smith', "
               "suffix 'MA'",
         shape=2),
    Case("the_bound_given_join_would_take_the_released_member",
         "Berg, abdul nee Jones MA",
         {"given": "abdul", "family": "Berg", "maiden": "Jones MA"},
         classification="parity",
         ambiguities=("suffix-or-name",),
         notes="the other half of M2's invariant: P5's LENIENT "
               "post-comma join runs BELOW the marker pass and would "
               "swallow the released 'MA' into the bound-given pair "
               "before assign could read it -- 'abdul MA' as the "
               "given name, which is where the clause-less control "
               "below genuinely puts it. A word joined away is a word "
               "the clause gave up for nothing, so the walk declines "
               "and keeps it. An earlier round of #533 released it "
               "and read given 'abdul MA' in silence",
         shape=2),
    Case("the_bound_given_joins_control_without_the_clause",
         "Berg, abdul MA",
         {"given": "abdul MA", "family": "Berg"},
         classification="parity",
         ambiguities=(),
         notes="the recorded control for the row above -- what the "
               "released member WOULD have read as, and why releasing "
               "it buys nothing. 1.4.0 read it identically (first "
               "'abdul MA', last 'Berg'). Unchanged by this rule",
         shape=2),
    Case("a_particle_chain_would_take_the_released_member",
         "Berg, Jane van der nee Smith DO",
         {"given": "Jane", "family": "van der Berg",
          "maiden": "Smith DO"},
         classification="parity",
         ambiguities=("particle-or-given", "suffix-or-name"),
         notes="M2's invariant against P2 rather than P5. 'DO' is "
               "particle vocabulary standing behind a particle piece, "
               "so the chain below this pass would absorb it into the "
               "family -- a word crossing from the BIRTH name into "
               "the current one, which is #424's failure from the "
               "other side. An earlier round of #533 released it and "
               "read family 'van der DO Berg' in silence, and the "
               "clause-less 'Berg, Jane van der DO' reads that way "
               "for its own reasons and is unchanged",
         shape=2),
    Case("two_released_particle_members_would_chain_each_other",
         "Jane Doe nee Smith DO DO",
         {"given": "Jane", "family": "Doe", "maiden": "Smith DO DO"},
         classification="parity",
         ambiguities=("suffix-or-name",),
         notes="the no-comma spelling of the same decline, where what "
               "would do the joining is the OTHER released member: "
               "the trailing peel reads both 'DO's as credentials, "
               "but the moment they are out of the clause the first "
               "is a non-leading particle and chains the second into "
               "family 'DO DO'. An earlier round of #533 read exactly "
               "that, and in silence",
         shape=2),
    Case("the_default_vocabularys_own_corpus_mover",
         "John née Jones Smith Ma",
         {"family": "John", "maiden": "Jones Smith Ma"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="the one name in the pre-existing differential corpus "
               "this rule reaches at the DEFAULT vocabulary, and it "
               "moves by gaining the REPORT rather than a field: "
               "'Ma' is Title-case inside a mixed-case name, so the "
               "lean declines the credential reading and the clause "
               "keeps it -- which is a fork called, and now said out "
               "loud. It was only ever pinned under a test lexicon "
               "before. Already a corpus_rules.jsonl name, so the "
               "shape tag re-witnesses it rather than growing the "
               "deduped corpus",
         shape=2),
    Case("a_member_alone_after_the_marker_keeps_its_credential_behind",
         "Jane Doe nee MA PhD",
         {"given": "Jane", "family": "Doe", "suffix": "PhD",
          "maiden": "MA"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="THE FIRST-WORD FLOOR with an unambiguous credential "
               "behind it: the walk may not take the first word after "
               "the marker, so 'MA' stays the maiden name whatever "
               "the peel read, and the 'PhD' behind it was never this "
               "rule's to give -- a suffix WORD ends the clause the "
               "way it always did. The report is the clause's own",
         shape=2),
    Case("a_particle_member_declines_on_its_lean_after_a_comma",
         "Doe, Jane nee Smith Do",
         {"given": "Jane", "family": "Doe", "maiden": "Smith Do"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="#531's reading at the given slot, reached through a "
               "clause: a member that is also particle vocabulary is "
               "the credential on a POSITIVE lean alone, and "
               "Title-case inside a mixed-case name is not one. So "
               "the clause keeps it and says so. The caps spelling "
               "'Doe, Jane nee Smith DO' is the other direction",
         shape=2),
    Case("a_numeral_between_the_clause_and_the_member",
         "Jane Doe nee Smith V MA",
         {"given": "Jane", "family": "Doe", "suffix": "MA",
          "maiden": "Smith V"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="both stops read the TRAILING word, so the numeral is "
               "not the word either fork asks about: the acronym fork "
               "stops at 'MA' and 'V' stays maiden text behind it. "
               "The mirror image, 'Jane Smith née Jones Ma V', keeps "
               "maiden 'Jones Ma' and reads suffix 'V'",
         shape=2),
    Case("delimiters_keep_the_whole_span_whatever_the_last_word_is",
         "Jane Doe (nee Smith MA)",
         {"given": "Jane", "family": "Doe", "maiden": "Smith MA"},
         classification="parity",
         ambiguities=(),
         notes="rules.md#M2, the delimited clause: the writer drew "
               "the boundary and it outranks every reading inside it, "
               "so no fork is called and none is reported. The marker "
               "inside the pair is what says the span is a maiden "
               "clause even where the pair is not in "
               "`maiden_delimiters`. Unchanged by #533 and by every "
               "release before it -- a settled position, not one of "
               "the silences about un-asked forks",
         shape=2),
    Case("delimiters_keep_the_whole_span_in_title_case_too",
         "Jane Doe (nee Smith Ma)",
         {"given": "Jane", "family": "Doe", "maiden": "Smith Ma"},
         classification="parity",
         ambiguities=(),
         notes="the pair for the row above: the two spellings differ "
               "in everything the lean reads and the delimiters make "
               "the difference immaterial. Undelimited, 'Jane Doe nee "
               "Smith MA' reads suffix 'MA' and 'Jane Doe nee Smith "
               "Ma' keeps it -- and both report",
         shape=2),
    Case("a_word_outside_the_delimiters_is_outside_the_clause",
         "Jane Doe (nee Smith) MA",
         {"given": "Jane", "family": "Doe", "suffix": "MA",
          "maiden": "Smith"},
         classification="parity",
         ambiguities=("suffix-or-name",),
         notes="the boundary cuts both ways: the span is the maiden "
               "name whole, and a member the writer left OUTSIDE it "
               "is an ordinary trailing credential that assign peels "
               "and reports. The control for the two rows above",
         shape=2),
    Case("two_released_members_each_get_their_own_report",
         "Jane Doe nee Smith Ma JD",
         {"given": "Jane", "family": "Doe", "suffix": "JD",
          "maiden": "Smith Ma"},
         classification="fix(#533)",
         ambiguities=("suffix-or-name", "suffix-or-name"),
         notes="the shape that puts BOTH suffix-or-name emitters on "
               "one parse: the clause keeps 'Ma' on its lean and "
               "reports it, assign peels 'JD' and reports that, and "
               "the two name different tokens -- which is what "
               "test_properties' span test needs to actually "
               "exercise its own check",
         shape=2),
    Case("no_trailing_rule_reads_the_family_segments_clause",
         "Smith nee Jones, Jane MA",
         {"given": "Jane", "family": "Smith", "suffix": "MA",
          "maiden": "Jones"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="the clause is in segment 0 of a family comma, where "
               "the comma has ALREADY named the family: those words "
               "are family text and a stop would hand one to `family` "
               "rather than to `suffix`, so no trailing rule is "
               "consulted and the clause keeps what it has. The 'MA' "
               "that does read as a credential here is in segment 1 "
               "and is #531's slot's, not this rule's. Unchanged",
         shape=2),
    Case("no_trailing_rule_reads_a_third_comma_part",
         "Smith, John, Jr nee Jones MA",
         {"given": "John", "family": "Smith", "suffix": "Jr",
          "maiden": "Jones MA"},
         classification="fix(#274)",
         ambiguities=("comma-structure",),
         notes="the other NONE reader, and the row that killed the "
               "first prototype: a segment past the second comma is "
               "read as credentials whole, so no trailing rule is "
               "consulted, the clause keeps 'MA' -- and nothing "
               "reports, because nothing was decided. Untagged: shape "
               "2 is a TWO-part listing. Unchanged from 2.0.0",
               ),
    # ---- #533: the policy sweep, all core-only -----------------------
    Case("the_clause_reads_the_same_under_the_strict_comma_knob",
         "Doe, Jane nee Smith MA",
         {"given": "Jane", "family": "Doe", "suffix": "MA",
          "maiden": "Smith"},
         policy=Policy(lenient_comma_suffixes=False),
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="the knob governs the LENIENT trailing predicate, "
               "which this slot does not inherit, so the reading is "
               "the default's"),
    Case("the_clause_reads_the_same_under_family_first",
         "Doe, Jane nee Smith MA",
         {"given": "Jane", "family": "Doe", "suffix": "MA",
          "maiden": "Smith"},
         policy=Policy(name_order=FAMILY_FIRST),
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="name_order does not enter it: the peel is "
               "order-independent and the comma has already named the "
               "family, so all three orders move the same names "
               "(measured over the whole corpus under six policies). "
               "UNTAGGED, and a shape 4 tag would be wrong -- this is "
               "a comma listing, not the family-first arrangement"),
    Case("the_clause_reads_the_same_under_ff_given_last",
         "Doe, Jane nee Smith MA",
         {"given": "Jane", "family": "Doe", "suffix": "MA",
          "maiden": "Smith"},
         policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST),
         classification="fix(#533)",
         ambiguities=("suffix-or-name",),
         notes="the third order, for the same reason as the row above"),
    Case("a_leading_title_takes_the_slot_the_member_would_have_had",
         "Doe, Dr. MA Smith",
         {"title": "Dr.", "given": "MA", "middle": "Smith",
          "family": "Doe"},
         notes="beside 'Doe, MA Smith' below, and the pair is what "
               "says how far the FIRST-PIECE emitter reaches: it reads "
               "the piece standing immediately after the comma, which "
               "is the title here, so the member behind it is read as "
               "the given name in silence. Not this slot either -- a "
               "title took the position the given part would have had. "
               "Parity at 1.4.0, 2.0.0 and 2.3.0 alike (measured "
               "2026-09-19)",
         shape=2),
    Case("the_post_comma_emitter_reports_the_same_member_untitled",
         "Doe, MA Smith",
         {"given": "MA", "middle": "Smith", "family": "Doe"},
         ambiguities=("suffix-or-name",),
         notes="the same member, the same reading, one title fewer -- "
               "and now the first piece after the comma IS the member, "
               "so #289's emitter reports it. The report is the whole "
               "difference from the row above: 1.4.0 read first 'MA', "
               "middle 'Smith' too, so the fields are parity",
         shape=2),
    Case("a_title_led_segment_consumes_a_whole_run_in_silence",
         "Doe, Mr. MA PhD",
         {"title": "Mr.", "family": "Doe", "suffix": "MA PhD"},
         classification="fix(#289)",
         notes="'Doe, Dr. MA' with a credential run behind the "
               "member, which is what the row adds: the no-name gate "
               "reads the segment whole, so the member joins the run "
               "rather than taking the given slot, and neither "
               "emitter is in that path. 1.4.0, 2.0.0 and 2.3.0 all "
               "read first 'MA', suffix 'PhD' -- the case lean moved "
               "it, which is 'Doe, Dr. MA's classification "
               "(measured 2026-09-19)",
         shape=2),
    Case("the_initial_veto_before_a_third_comma_part_is_untouched",
         "Doe, John V, PhD",
         {"given": "John", "middle": "V", "family": "Doe",
          "suffix": "PhD"},
         notes="#144's two-segment restriction still governs its own "
               "predicate: 'V' is a roman numeral reached by the "
               "LENIENT trailing test, not by the ambiguous class, so "
               "the new branch never sees it and the middle initial "
               "survives. The control that pins the restriction's "
               "scope after #531 narrowed nothing about it"),
    Case("the_no_name_gate_path_still_reports_exactly_once",
         "Doe, MA",
         {"family": "Doe", "suffix": "MA"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="the reading is the_lean_reaches_the_post_comma_slot's "
               "('Smith, MA') word for word, so it carries that row's "
               "classification: 1.4.0 AND 2.0.0 both read first 'MA', "
               "last 'Doe', and #289's lean is what made the "
               "credential (measured on both wheels 2026-09-18). "
               "UNCHANGED by #531, and structurally unreachable by the new "
               "emitter rather than luckily missed: segment 1 holds "
               "no name word, `segment_suffix_reading` returns "
               "non-None, and assign sets every role from that "
               "reading without entering the placement loop at all. "
               "So the slot the old emitter owns and the slot the new "
               "one owns cannot both fire -- which is why no token is "
               "ever reported twice",
         shape=2),
    Case("the_no_name_gate_path_with_a_run_still_reports_once",
         "Doe, MA PhD",
         {"family": "Doe", "suffix": "MA PhD"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="the same gate path with a credential run behind the "
               "member, and the same classification as its bare twin "
               "above: 1.4.0 and 2.0.0 alike read first 'MA', suffix "
               "'PhD'. One report, for the one class member, exactly "
               "as before #531",
         shape=2),
    Case("a_title_led_segment_consumes_the_member_in_silence",
         "Doe, Dr. MA",
         {"title": "Dr.", "family": "Doe", "suffix": "MA"},
         classification="fix(#289)",
         notes="the THIRD position this kind stays silent at, and a "
               "boundary rather than an omission: a title took the "
               "slot the given name would have had, so there is no "
               "given part for the member to end. The segment holds "
               "no name word, the credential-run gate reads it whole, "
               "and #531's emitter is in the placement loop the gate "
               "path never enters. The post-comma emitter cannot "
               "reach it either -- that one reads the FIRST piece "
               "after the comma, which is 'Dr.'. So the reading moves "
               "and nothing reports. MEASURED on the wheels: 1.4.0, "
               "2.0.0 and 2.3.0 all read first 'MA', last 'Doe'; "
               "#289's case lean is what makes it a credential, which "
               "is this row's twin 'Doe, MA' above, and 'DOE, DR. MA' "
               "keeps given 'MA' where one case carries no lean",
         shape=2),
    # ---- the `do` pairing: capitals decide, the particle rule keeps
    # every other spelling (Derek, 2026-09-18) ---------------------
    Case("capitals_decide_for_the_particle_member",
         "Doe, John DO",
         {"given": "John", "family": "Doe", "suffix": "DO"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="'do' is the one class member that is also particle "
               "vocabulary, so this slot and P6's attachment want the "
               "same word. A POSITIVE credential lean -- an all-caps "
               "member in a name written in more than one case -- is "
               "what takes it, and P6 stands down. 1.4.0 read suffix "
               "'DO'. Reports ONCE: where this reading wins, P6 has "
               "nothing to report",
         shape=2),
    Case("the_particle_rule_keeps_the_lower_case_member",
         "Nascimento, Edson Arantes do",
         {"given": "Edson", "middle": "Arantes",
          "family": "do Nascimento"},
         classification="fix(#380)",
         ambiguities=("particle-or-given",),
         notes="UNCHANGED, and the record the pairing is built to "
               "protect. Mixed case with an all-lower member leans "
               "nothing, so the reading carve-out hands it to P6 and "
               "the report carve-out keeps P6's own kind as the only "
               "one. This is the half of the pair the capitals buy. "
               "NOT 1.4.0 parity: v1 read suffix 'do', and P6's "
               "attachment has outranked that since 2.3 -- which is "
               "'Berg, Jan vd's classification, this word being the "
               "same collision",
         shape=2),
    Case("one_case_cannot_tell_the_osteopath_from_the_record",
         "SMITH, JOHN DO",
         {"given": "JOHN", "family": "DO SMITH"},
         classification="fix(#380)",
         ambiguities=("particle-or-given",),
         notes="ACCEPTED COST, and the pairing IS the argument: in "
               "one case the rule cannot tell this from "
               "'NASCIMENTO, EDSON ARANTES DO' and reads both as the "
               "particle -- right about the Brazilian record, wrong "
               "about the osteopath, whose 'DO' 1.4.0 read as a "
               "suffix. Both report `particle-or-given`, which is how "
               "a caller finds the second. Accepted rather than "
               "repaired: the one-case reading is the commoner of the "
               "two collisions and the Nascimento record is the name "
               "a wrong answer would damage",
         shape=2),
    Case("a_member_inside_a_particle_run_never_reaches_the_slot",
         "Doe, John van DO",
         {"given": "John", "family": "van DO Doe"},
         classification="fix(#380)",
         ambiguities=("particle-or-given",),
         notes="the capitals lean cannot reach this 'DO', and the "
               "reason is EARLIER than #531: grouping merges 'van DO' "
               "into ONE particle piece before the trailing slot "
               "exists. What declines it is the TAG test -- the "
               "piece's first token is 'van', which carries no class "
               "tag -- and the len() test in front of that decides "
               "nothing here, since deleting it leaves this row where "
               "it stands ('Doe, John MA y' is the row that pins it). "
               "Not a carve-out and not this release's doing -- "
               "verified byte-identical at cc78c960 and on the 2.3.0 "
               "wheel (2026-09-19), where 'Doe, John DO' moved and "
               "this did not. The report is P6's, named for 'van', "
               "the word of the run that is also a given name. 1.4.0 "
               "read middle 'van DO'; the attachment is #380's, which "
               "is the classification 'Nascimento, Edson Arantes do' "
               "carries above",
         shape=2),
    Case("a_member_heading_a_particle_chain_never_reaches_it_either",
         "Doe, John DO Ed",
         {"given": "John", "middle": "DO Ed", "family": "Doe"},
         classification="fix(comma-family)",
         notes="the member HEADS the joined piece here where 'van DO' "
               "has it trailing: 'do' is particle vocabulary, so the "
               "chain takes the name word behind it and 'DO Ed' is "
               "one two-token piece. Both words silent -- though "
               "'Doe, John DO' alone reads the credential and reports "
               "-- and nothing attaches, the run not being wholly "
               "particles. The SECOND killer for the len() tests, and "
               "the one where the piece's first token IS the class "
               "member: without them the piece reads as a credential, "
               "suffix 'DO Ed'. 1.4.0 read suffix 'DO, Ed'; 2.0.0 and "
               "2.3.0 read this (measured 2026-09-19)",
         shape=2),
    Case("a_declining_member_inside_a_particle_run_is_silent_too",
         "Doe, John van Ma",
         {"given": "John", "middle": "van Ma", "family": "Doe"},
         classification="fix(comma-family)",
         notes="'Doe, John van DO's Title-cased twin, and it differs "
               "in what P6 does rather than in what the slot does: "
               "the joined piece is two tokens either way, but 'Ma' "
               "is not particle vocabulary, so the trailing run is "
               "not wholly particles and nothing attaches -- middle "
               "'van Ma', family 'Doe', silent on both counts. 1.4.0 "
               "read middle 'van', suffix 'Ma'; 2.0.0 and 2.3.0 read "
               "this",
         shape=2),
    Case("the_particle_carve_out_silences_the_member_in_front",
         "Doe, John MA do",
         {"given": "John", "middle": "MA", "family": "do Doe"},
         classification="fix(#380)",
         ambiguities=("particle-or-given",),
         notes="the carve-out cascades: lower-case 'do' leans "
               "nothing, so this walk does not read it as a suffix -- "
               "and a piece the walk refuses ENDS the run, so the "
               "all-caps 'MA' in front of it is never asked and never "
               "reports, capitals and all. P6 then attaches 'do' a "
               "stage later, too late to re-open the question. One "
               "report, P6's. UNCHANGED by #531: byte-identical at "
               "cc78c960 and on the 2.3.0 wheel (2026-09-19)",
         shape=2),
    Case("one_case_keeps_the_particle_on_the_real_record",
         "NASCIMENTO, EDSON ARANTES DO",
         {"given": "EDSON", "middle": "ARANTES",
          "family": "DO NASCIMENTO"},
         classification="fix(#380)",
         ambiguities=("particle-or-given",),
         notes="the fourth corner of the pairing, and the reason the "
               "one-case cost is accepted: this is a real Portuguese "
               "record and the particle reading is right about it. "
               "1.4.0 read middle 'ARANTES', suffix 'DO'",
         shape=2),
    Case("the_particle_member_declines_in_title_case_too",
         "Doe, John Do",
         {"given": "John", "family": "Do Doe"},
         classification="fix(#380)",
         ambiguities=("particle-or-given",),
         notes="Title case leans NAME, which is not a positive "
               "credential lean, so the carve-out hands it to P6 "
               "like every non-capital spelling. One report, P6's. "
               "1.4.0 read suffix 'Do'",
         shape=2),
    Case("p6_still_claims_the_other_unambiguous_suffix_particle",
         "Berg, Jan mc",
         {"given": "Jan", "family": "mc Berg"},
         classification="fix(#380)",
         ambiguities=("suffix-or-name",),
         notes="'mc' is the second word in both vocabularies whose "
               "suffix half is unambiguous, and it is the control "
               "that stops #531's P6 condition being written against "
               "one example -- 'Berg, Jan vd' above is the first, and "
               "both are byte-identical before and after. Carries "
               "that row's classification for the same reason: 1.4.0 "
               "and 2.0.0 both read suffix 'mc' and P6's attachment "
               "is what took it (measured on both wheels 2026-09-18)",
         shape=2),
    # ---- the particle cascade Derek accepted (Q1) ----------------
    Case("the_slot_hands_a_trailing_particle_to_p6",
         "Doe, John van MA",
         {"given": "John", "family": "van Doe", "suffix": "MA"},
         classification="fix(#531)",
         ambiguities=("particle-or-given", "suffix-or-name"),
         notes="A FAMILY MOVE, found by measurement and accepted by "
               "Derek 2026-09-18: today this is middle 'van MA', "
               "silent. Once 'MA' becomes a suffix, P6's own walk "
               "looks past that post-nominal, finds 'van' as a "
               "trailing all-particle run and attaches it. That is "
               "exactly 'Berg, Jan van Jr.'s reading, arriving "
               "through a shape it could not reach before. TWO "
               "reports, one per fork, and neither is this slot "
               "reporting twice"),
    Case("the_slot_reaches_past_an_unambiguous_suffix_particle",
         "Doe, John MA vd",
         {"given": "John", "family": "vd Doe", "suffix": "MA"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name", "suffix-or-name"),
         notes="the row above with the particle BEHIND the member "
               "instead of in front, and the pair says the cascade is "
               "not about where the particle stands: 'vd' is claimed "
               "outright by the suffix vocabulary, so this walk reads "
               "past it and takes 'MA', and P6 then attaches 'vd' "
               "over that reading -- reporting in the kind naming the "
               "reading it OVERRODE, which is why both reports here "
               "are `suffix-or-name` where 'Doe, John van MA' gives "
               "one of each. Today middle 'MA', family 'vd Doe', one "
               "report ('Berg, Jan vd' is that reading with nothing "
               "in front of the particle)"),
    # ---- policy rows. Every one is _CORE_ONLY (see
    # tests/v2/test_facade_cases.py) --------------------------------
    Case("the_dotted_slot_reports_with_the_switch_off",
         "Doe, John X.Y.Z.",
         {"given": "John", "middle": "X.Y.Z.", "family": "Doe"},
         policy=Policy(unlisted_dotted_suffixes=False),
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="the declined-but-reported shape at this slot: "
               "classify writes `shape:acronym` whether or not the "
               "switch admits the token, which `peel_trailing` "
               "already relies on, so the fork is consulted and "
               "reported while the reading stays a middle name. Same "
               "treatment 'Smith, A.B.' gets at the first post-comma "
               "slot"),
    Case("the_caps_switch_reaches_the_trailing_slot",
         "Doe, John XYZ",
         {"given": "John", "family": "Doe", "suffix": "XYZ"},
         policy=Policy(unlisted_caps_suffixes=True),
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="the by-shape class reaches this slot through the "
               "same tag the listed class does. `listed_lean` returns "
               "None wherever `shape:acronym` rides, so a by-shape "
               "member never has a lean and takes the positional "
               "reading -- which at this slot is the credential"),
    Case("the_trailing_slot_ignores_the_strict_comma_knob",
         "Doe, John MA",
         {"given": "John", "family": "Doe", "suffix": "MA"},
         policy=Policy(lenient_comma_suffixes=False),
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="`lenient_comma_suffixes` governs #144's initial-veto "
               "predicate, which this branch does not go through -- "
               "so the strict knob reads this slot exactly as the "
               "default does. The control that says which predicate "
               "owns the word"),
    Case("the_trailing_slot_reads_the_same_under_family_first",
         "Doe, John MA",
         {"given": "John", "family": "Doe", "suffix": "MA"},
         policy=Policy(name_order=FAMILY_FIRST),
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="a family comma names the family, so the declared "
               "order arbitrates nothing here. Measured identical "
               "under all three orders, which is also why "
               "`_ORDER_EXEMPTION_EFFECT` gains no row"),
    Case("the_trailing_slot_reads_the_same_under_ff_given_last",
         "Doe, John MA",
         {"given": "John", "family": "Doe", "suffix": "MA"},
         policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST),
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="the third order, for the same reason as the second"),
    # ---- caseless scripts. tolerated=True, NOT a shape tag:
    # cases.py's __post_init__ hard-errors on a composed CJK comma
    # form carrying a shape.
    Case("a_caseless_script_takes_the_trailing_credential",
         "田中, 太郎 MA",
         {"given": "太郎", "family": "田中", "suffix": "MA"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="'caseless is inert' holds for the LEAN, not for the "
               "OUTCOME: `is_one_case` answers True for a caseless "
               "script, so nothing leans, so the positional reading "
               "applies -- and at this slot the positional reading IS "
               "the credential. 1.4.0 parity, measured. A composed "
               "CJK comma form, so tolerated rather than contract "
               "(rules.md#W3's 2026-09-01 demotion)",
         tolerated=True),
    Case("a_hangul_family_takes_the_trailing_credential_too",
         "김, 민준 MA",
         {"given": "민준", "family": "김", "suffix": "MA"},
         classification="fix(#531)",
         ambiguities=("suffix-or-name",),
         notes="the Korean twin of the row above, and the pair is "
               "what stops the reading being a fact about Han. "
               "Tolerated for the same reason",
         tolerated=True),
    Case("family_comma_lenient_trailing", "Smith, John V",
         {"given": "John", "family": "Smith", "suffix": "V"},
         notes="v1 #144: the trailing piece of a two-part comma name "
               "takes the lenient suffix test"),
    Case("family_comma_first_piece_is_given", "Steven Hardman, RN - CRNA",
         {"given": "RN", "middle": "-", "family": "Steven Hardman",
          "suffix": "CRNA"},
         notes="v1 walk order: the first post-comma piece is the given "
               "before any suffix check (the delimiter is UNSET here "
               "-- v1's documented limitation, kept)"),
    Case("family_comma_lone_suffix_piece", "Andrews, M.D.",
         {"family": "Andrews", "suffix": "M.D."},
         classification="fix(comma-family)",
         notes="v1 made the lone post-comma strict-suffix piece the "
               "given; 2.0 routes it to suffix (same family as the "
               "'Smith, Dr.' row)"),
    Case("family_comma_suffix_run_renders_unjoined", "Smith, MD PhD",
         {"family": "Smith", "suffix": "MD PhD"},
         classification="fix(comma-family)",
         notes="a space-separated post-nominal run after a family "
               "comma RENDERED with a comma the input never had "
               "('MD, PhD'), because the one-entry join was asked by "
               "segment index and this segment is not a tail one. The "
               "full-name 'John Smith, MD PhD' has rendered 'MD PhD' "
               "since 1.4.0, and #429 brought this form into line with "
               "it. The roles were already right after #428; this was "
               "its remaining half"),
    Case("period_joined_ambiguous_chunk", "John Doe, Msc.Ed.",
         {"given": "John", "family": "Doe", "suffix": "Msc.Ed."},
         notes="chunk-level suffix membership is v1's is_suffix: bare "
               "ambiguous acronyms count within period-joined tokens"),
    Case("suffix_comma_split_phd", "John Smith, Ph. D.",
         {"given": "John", "family": "Smith", "suffix": "Ph. D."},
         notes="the adjacent Ph./D. pair counts as one suffix unit in "
               "the suffix-comma detection (v1 fix_phd parity). The "
               "pair leads the run here; the row below is where it does "
               "not"),
    Case("suffix_comma_split_phd_after_another_suffix",
         "John Smith, Jr. Ph. D.",
         {"given": "John", "family": "Smith", "suffix": "Jr. Ph. D."},
         classification="fix(credential-pair-order)",
         notes="the pair is merged wherever it sits in the run, not "
               "only at its head, and the row above cannot say so -- "
               "there the pair IS the head. Restricted to position 0 "
               "the merge never fires, 'D.' is suffix vocabulary in no "
               "lexicon, and the run stops being wholly suffix: this "
               "reads as a FAMILY comma instead, family 'John Smith' / "
               "title 'Jr.' / suffix 'Ph. D.'. Pinned at the segment "
               "stage too (test_segment.test_the_credential_pair_"
               "merges_anywhere_in_the_run), because the neighbouring "
               "input 'John Smith, MD, Jr. Ph. D.' keeps every field "
               "under that break and gains only a comma-structure "
               "ambiguity, so fields alone do not catch it. Measured: "
               "1.4.0 gave suffix 'Ph. D., Jr.' -- fix_phd EXTRACTED "
               "the pair pre-parse and re-appended it, reordering the "
               "tail, where 2.0 renders it as written. Same words, "
               "same roles, different order, and the harness cannot "
               "currently see it: expected_since_1.4.0.toml states that a "
               "diffing trailing 'Ph. D.' must fail the run, but this "
               "input is absorbed by fix(comma-family), whose "
               "name_regex is a bare comma -- measured on a probe "
               "corpus, unexplained 0. See the note there"),
    Case("tail_segment_entry_space_joined", "John Smith, V MD",
         {"given": "John", "family": "Smith", "suffix": "V MD"},
         notes="v1 renders each tail comma segment as ONE suffix "
               "entry; words within an entry space-join via the "
               "'joined' tag"),
    Case("inline_suffix_then_comma_suffix", "John Smith Jr., PhD",
         {"given": "John", "family": "Smith", "suffix": "Jr., PhD"},
         classification="parity",
         notes="shape 3's optional inline suffix standing WITH a comma "
               "suffix, which no other row writes: the two compose "
               "rather than one displacing the other. C1 decides on "
               "the part after the comma alone -- wholly suffix words, "
               "more than one word before it -- so the trailing-suffix "
               "mode fires with 'Jr.' already inside the name part, "
               "and the written comma survives between the pieces. "
               "'John Smith, PhD' is the comma half alone and "
               "'John Smith Jr.' the inline half",
         shape=3),
    Case("maiden_delimiters_win_when_shared",
         'Baker (Johnson), Jenny',
         {"given": "Jenny", "family": "Baker", "maiden": "Johnson"},
         policy=Policy(maiden_delimiters=frozenset({("(", ")")})),
         notes="listing a pair in maiden_delimiters drops it from the "
               "effective nickname set (maiden wins, 2026-07-19) -- the "
               "one-liner replaces the bucket-move idiom. The facade "
               "runner reaches this row by making that same move, so "
               "it agrees. What v1 does NOT agree on is a pair left in "
               "BOTH buckets, which it gives to nickname; that spelling "
               "is a different config, not this row, and is pinned in "
               "test_config_shim"),
    # #269 follow-up: Arabic-script bound given names, mirroring the
    # Latin transliterations' behavior (probed live 2026-07-19: bound
    # join fires only with 3+ tokens, eats the NEXT token into given;
    # two-token kunya stays split -- 'أبو مازن' pinned in test_locales;
    # non-leading أبو still prefix-chains onto family).
    Case("arabic_bound_given_abd", 'عبد الرحمن محمد',
         {"given": "عبد الرحمن", "family": "محمد"},
         classification="feat(#269)",
         notes="script twin of 'Abdul Rahman Mohammed'; عبد was the "
               "missing bound entry -- 1.x split it into given عبد + "
               "middle الرحمن"),
    Case("arabic_bound_given_kunya", 'أبو بكر أحمد',
         {"given": "أبو بكر", "family": "أحمد"},
         classification="feat(#269)"),
    Case("arabic_bound_given_kunya_hamzaless", 'ابو بكر احمد',
         {"given": "ابو بكر", "family": "احمد"},
         classification="feat(#269)",
         notes="both kunya spellings ship, like the أبو/ابو prefix pair"),
    Case("arabic_bound_given_umm", 'أم كلثوم إبراهيم',
         {"given": "أم كلثوم", "family": "إبراهيم"},
         classification="feat(#269)"),
    # #273: typographic nickname delimiters ship as defaults -- one row
    # per new pair; expectations verified live 2026-07-19 before the
    # pairs were added to DEFAULT_NICKNAME_DELIMITERS.
    Case("smart_double_quotes_nickname", 'John “Jack” Kennedy',
         {"given": "John", "family": "Kennedy", "nickname": "Jack"},
         classification="feat(#273)"),
    Case("low_high_quotes_nickname", 'Hans „Hansi“ Müller',
         {"given": "Hans", "family": "Müller", "nickname": "Hansi"},
         classification="feat(#273)",
         notes="the closing '“' doubles as the English pair's opener; "
               "no spurious unbalanced-delimiter ambiguity (pinned in "
               "test_extract)"),
    Case("guillemets_nickname_inner_spaces", 'Jean « Petit » Dupont',
         {"given": "Jean", "family": "Dupont", "nickname": "Petit"},
         classification="feat(#273)",
         notes="French spacing: inner padding is trimmed from the "
               "extracted nickname"),
    Case("reversed_guillemets_nickname", 'Hans »Hansi« Müller',
         {"given": "Hans", "family": "Müller", "nickname": "Hansi"},
         classification="feat(#273)"),
    Case("swedish_right_quotes_nickname", 'Anna ”Ann” Larsson',
         {"given": "Anna", "family": "Larsson", "nickname": "Ann"},
         classification="feat(#273)"),
    Case("cjk_corner_bracket_nickname", '山田「タロ」太郎',
         {"family": "山田", "given": "太郎", "nickname": "タロ"},
         classification="feat(#273) + fix(#271)",
         notes="extraction also splits the unspaced remainder -- the "
               "masked region acts as a token boundary. Both name "
               "pieces are then wholly Han, so script_orders reads "
               "them family-first; the nickname's kana is outside the "
               "name pieces and does not enter that test"),
    Case("cjk_white_corner_bracket_nickname", '田中『ハナ』花子',
         {"family": "田中", "given": "花子", "nickname": "ハナ"},
         classification="feat(#273) + fix(#271)"),
    Case("fullwidth_paren_nickname", 'John （Jack） Kennedy',
         {"given": "John", "family": "Kennedy", "nickname": "Jack"},
         classification="feat(#273)"),
    Case("curly_apostrophe_stays_literal", 'Sean O’Connor',
         {"given": "Sean", "family": "O’Connor"},
         notes="U+2019 is the typographic apostrophe; curly single "
               "quotes are deliberately NOT delimiters (#273 excludes "
               "them)"),
    Case("family_segment_trailing_suffix", "Smith Jr., John",
         {"given": "John", "family": "Smith", "suffix": "Jr."},
         notes="v1: the family part may have suffixes in it "
               "(parser.py:1368); the first piece is always the family "
               "(pinned live 2026-07-17). Shape 2's pre-comma "
               "[Suffix] slot",
         shape=2),
    Case("family_segment_multiple_suffixes", "Smith Jr. MD, John",
         {"given": "John", "family": "Smith", "suffix": "Jr. MD"},
         classification="fix(#436/#437)",
         notes="the pre-comma segment's post-nominal run, written "
               "with spaces and rendered with them since #436. It "
               "read 'Jr., MD' at 1.4.0 and through 2.2.0, the "
               "one-entry join being asked by segment index and this "
               "run standing in segment 0. The corpus twin is "
               "'Washington Jr. MD, Franklin'"),
    Case("family_segment_particle_chain_suffix", "de la Vega III, Juan",
         {"given": "Juan", "family": "de la Vega", "suffix": "III"}),
    Case("interior_periods_block_vocab", "Smith, J.R.",
         {"given": "J.R.", "family": "Smith"},
         ambiguities=("suffix-or-name",),
         notes="v1's lc() keeps interior periods: 'J.R.' is not the "
               "suffix word 'jr' (pinned live 2026-07-17), so this "
               "FIELD reading is unchanged clear back to 1.4.0. #516: "
               "two unlisted single-letter chunks join the ambiguous "
               "class by shape all the same, the same fork "
               "'Smith, A.B.' reports -- the class is considered and "
               "declined (one word before the comma is never enough), "
               "and the consideration is what reports, exactly as the "
               "trailing peel's own declined picks always have"),
    Case("dotted_acronym_suffix", "John Smith M.D.",
         {"given": "John", "family": "Smith", "suffix": "M.D."},
         notes="suffix-ACRONYM membership alone strips periods (v1 "
               "is_suffix parity)"),
    Case("nickname_rule_counts_whole_segment", "Xyz. (Bud) Smith",
         {"title": "Xyz.", "family": "Smith", "nickname": "Bud"},
         classification="fix(#410)",
         notes="v1's lone-piece nickname rule counts the segment "
               "BEFORE title peeling (parser.py:1285, pinned live "
               "2026-07-17), which is what this row pins and what "
               "#410 does not change. The FIELD moved: a nickname is "
               "not a further name word, so the one name word behind "
               "the title is the family. 1.4.0 read first 'Smith'"),
    Case("suffix_comma_decided_by_first_segment",
         "Dr. John P. Doe-Ray, CLU, CFP, LUTC",
         {"title": "Dr.", "given": "John", "middle": "P.",
          "family": "Doe-Ray", "suffix": "CLU, CFP, LUTC"},
         ambiguities=("comma-structure",),
         notes="only parts[1] decides the suffix-comma structure "
               "(v1 parser.py:1318); 'lutc' is not in the vocabulary "
               "but rides along (v1 parity, pinned live 2026-07-16). "
               "Deliberately the COMPOUND shape-3 exemplar: it is the "
               "only row filling Title, Middle and the repeated "
               "[, Suffix] at once, and it carries the corpus's "
               "hyphenated family besides, so a diff on it is not "
               "attributable to any one slot -- read it as the "
               "notation's fullest form rather than as a witness for "
               "whichever slot the failure seems to be about",
         shape=3),
    Case("suffix_comma_nonsuffix_tail_flagged", "John Smith, MD, Xyzzy",
         {"given": "John", "family": "Smith", "suffix": "MD, Xyzzy"},
         ambiguities=("comma-structure",),
         notes="the unrecognized tail is consumed best-effort with the "
               "flag (v1 consumed it silently)"),
    Case("period_joined_titles", "Lt.Gov. John Doe",
         {"title": "Lt.Gov.", "given": "John", "family": "Doe"},
         notes="v1 derived-title rule: ANY period chunk being a title "
               "makes the token a title (pinned live 2026-07-16). "
               "Title wins before #516's shape verdict is even asked, "
               "so this stays a protected control for the switch, not "
               "just for the chunk rule",
         shape=1),
    Case("period_joined_suffixes", "John Doe JD.CPA",
         {"given": "John", "family": "Doe", "suffix": "JD.CPA"},
         notes="the multi-character chunk match 'jd'/'cpa' still wins "
               "over #516's shape verdict, which is asked only where "
               "classify's own fall-through has not already tagged "
               "'vocab:suffix' -- unchanged either side of the switch",
         shape=1),
    Case("period_joined_any_rule", "Mr.Smith",
         {"title": "Mr.Smith"},
         notes="the ANY rule is deliberate v1 parity: one title chunk "
               "claims the whole token"),
    Case("doubled_comma_suffix", "Doe,, Jr.",
         {"family": "Doe", "suffix": "Jr."},
         notes="the EMPTY given segment keeps its position: 'Jr.' is a "
               "tail suffix, not a lone post-comma title (v1 parity, "
               "pinned live 2026-07-16)"),
    Case("doubled_comma_given_kept", "Doe, John,, Jr.",
         {"given": "John", "family": "Doe", "suffix": "Jr."}),
    Case("single_trailing_comma_cosmetic", "John,",
         {"given": "John"}, ambiguities=("given-or-family",),
         notes="v1 collapse_whitespace strips exactly ONE trailing "
               "comma before parsing -- and a comma stripped before "
               "parsing decided nothing, so what is left is one name "
               "word and O5's convention reports it (#449). Roles "
               "parity; the flag is #449's"),
    Case("double_trailing_comma_structural", "Doe,,",
         {"family": "Doe"},
         notes="one trailing comma is cosmetic, the second is "
               "structural: an empty given segment makes this a "
               "family-comma parse (v1 parity, pinned live 2026-07-16)"),
    Case("doubled_comma_blocks_suffix_comma", "John Smith,, MD",
         {"family": "John Smith", "suffix": "MD"},
         notes="an empty segment 1 fails the suffix-comma detection "
               "(v1 parity)"),
    Case("suffix_delimiter_tail_segment", "Doe, John, RN - CRNA",
         {"given": "John", "family": "Doe", "suffix": "RN, CRNA"},
         policy=_SD,
         notes="v1 suffix_delimiter parity (#206): the delimiter token "
               "is dropped from consumed tail segments (pinned live "
               "2026-07-16)"),
    Case("suffix_delimiter_detection", "Doe, John RN - CRNA",
         {"given": "John", "middle": "-", "family": "Doe",
          "suffix": "RN, CRNA"},
         policy=_SD,
         notes="the delimiter fires only at suffix sites; the stray "
               "token keeps its per-piece walk role (v1 parity, pinned "
               "live 2026-07-16)"),
    Case("suffix_delimiter_suffix_comma", "John Smith, RN - CRNA",
         {"given": "John", "family": "Smith", "suffix": "RN, CRNA"},
         policy=_SD,
         notes="delimiter transparency in the SUFFIX_COMMA "
               "determination: the post-comma segment counts as "
               "all-suffix (v1 parity, pinned live 2026-07-16)"),
    Case("suffix_delimiter_no_space_core", "John Smith, RN/CRNA",
         {"given": "John", "family": "Smith", "suffix": "RN/CRNA"},
         policy=Policy(extra_suffix_delimiters=frozenset({"/"})),
         classification="fix(suffix-delimiter-rendering)",
         notes="v1 split 'RN/CRNA' and rendered 'RN, CRNA'; v2 keeps "
               "the token whole (anti-#100) with Role.SUFFIX -- role "
               "assignment matches, rendering differs (migration plan "
               "deviation 5, release-log classified)"),
    Case("suffix_delimiter_name_segment_untouched", "Doe, Mary - Kate, RN",
         {"given": "Mary", "middle": "- Kate", "family": "Doe",
          "suffix": "RN"},
         policy=_SD,
         notes="a delimiter token in a NAME segment is kept (v1 parity, "
               "pinned live 2026-07-16)"),
    Case("suffix_delimiter_core_between_entries_is_a_boundary",
         "John Doe, MD - PhD - FACS",
         {"given": "John", "family": "Doe", "suffix": "MD, PhD, FACS"},
         policy=_SD,
         classification="fix(#436/#437)",
         notes="the DROPPED core half of #436's entry boundary: a "
               "suffix-comma tail drops the delimiter cores (#206), "
               "and the entry the writer drew ends at each of them. "
               "The core is gone before the render sees it, so the "
               "boundary is read off the dropped indices rather than "
               "off a surviving token. Parity at every baseline"),
    Case("suffix_delimiter_core_that_survives_is_a_boundary_too",
         "Smith, MD - PhD - FACS",
         {"title": "MD", "given": "-", "middle": "-", "family": "Smith",
          "suffix": "PhD, FACS"},
         policy=_SD,
         classification="fix(#436/#437)",
         notes="the other half, and the one a dropped-core test alone "
               "would miss. After a FAMILY comma segment 1 is not a "
               "tail, so nothing drops the cores and the dashes stand "
               "as ordinary name words between the two post-nominals. "
               "A run does not span a name word: the separator holds "
               "whether the core was dropped or kept, which is why "
               "#436's predicate asks what stands between the two "
               "rather than only what was dropped. The bare-policy "
               "spelling of this string is a corpus name and reads "
               "the same, the dash being no delimiter there either"),
    Case("family_comma_transparent_then_core",
         'John Doe, MD "Doc" PhD - FACS',
         {"given": "John", "family": "Doe", "nickname": "Doc",
          "suffix": "MD PhD, FACS"},
         policy=_SD,
         classification="fix(#436/#437)",
         notes="both arms of #436's predicate in one run: the nickname "
               "between MD and PhD renders into another field, so it "
               "is transparent and the two are one entry, while the "
               "dropped core between PhD and FACS parts them. A row "
               "pinning either arm alone passes on a rule that "
               "collapses the two into one test -- part at every "
               "dropped index and the suffix reads 'MD, PhD, FACS'; "
               "part at no dropped index and it reads 'MD PhD FACS'"),
    Case("comma_extras_become_suffixes", "Smith, John, Extra, Jr.",
         {"given": "John", "family": "Smith", "suffix": "Extra, Jr."},
         ambiguities=("comma-structure",),
         notes="post-comma segments land in suffix even when not "
               "suffix-shaped; the ambiguity flags the guess (v1 "
               "parity, pinned live 2026-07-13). Shape 2's repeated "
               "[, Suffix] slot, the double trailing suffix",
         shape=2),
    Case("delavega", "Dr. Juan de la Vega III",
         {"title": "Dr.", "given": "Juan", "family": "de la Vega",
          "suffix": "III"},
         notes="shape 1's Title and trailing Suffix slots paired, the "
               "arrangement written end to end",
         shape=1),
    Case("prefix_chain_to_end", "Juan de la Vega Martinez",
         {"given": "Juan", "family": "de la Vega Martinez"}),
    Case("van_johnson", "Van Johnson",
         {"given": "Van", "family": "Johnson"},
         ambiguities=("particle-or-given",),
         notes="v2 surfaces #121's irreducible ambiguity"),
    Case("family_comma_particles", "de la Vega, Juan",
         {"given": "Juan", "family": "de la Vega"},
         notes="shape 2's particle-bearing family, before the comma",
         shape=2),
    Case("paren_suffix_escapes_nickname", "Andrew Perkins (MBA)",
         {"given": "Andrew", "family": "Perkins", "suffix": "MBA"},
         notes="v1 parse_nicknames: suffix-shaped delimited content is "
               "left in place for normal parsing (pinned live "
               "2026-07-17)"),
    Case("paren_period_escapes_nickname", "Andrew Perkins (Ret.)",
         {"given": "Andrew", "family": "Perkins", "suffix": "Ret."}),
    Case("nickname_quotes", 'John "Jack" Kennedy',
         {"given": "John", "family": "Kennedy", "nickname": "Jack"},
         notes="shape 1's double-quoted Nickname slot, which is the "
               "spelling its notation writes",
         shape=1),
    Case("nickname_parens", "John (Jack) Kennedy",
         {"given": "John", "family": "Kennedy", "nickname": "Jack"}),
    Case("sir_bob", "Sir Bob Andrew Dole",
         {"title": "Sir", "given": "Bob", "middle": "Andrew",
          "family": "Dole"},
         notes="shape 1's first Middle slot; middle_run_at_two_words "
               "below is the second",
         shape=1),
    Case("middle_run_at_two_words", "John Jack Andrew Kennedy",
         {"given": "John", "middle": "Jack Andrew", "family": "Kennedy"},
         classification="parity",
         notes="shape 1's SECOND Middle slot, which sir_bob above "
               "leaves unwritten: everything standing between the "
               "given name and the family is middle, at any arity, and "
               "the pieces render space-joined. The row that fails if "
               "the middle run is ever capped at one word",
         shape=1),
    Case("family_comma_paren_nickname", "Kennedy, John (Jack)",
         {"given": "John", "family": "Kennedy", "nickname": "Jack"},
         classification="parity",
         notes="shape 2's (Nickname) slot: the clause is lifted out "
               "before the comma structure is read, so what reaches "
               "C1 is the bare 'Kennedy, John' and the listing form "
               "still wins. nickname_parens above is the same clause "
               "in the medial position of shape 1",
         shape=2),
    Case("long_title", "President of the United States Barack Obama",
         {"title": "President of the United States",
          "given": "Barack", "family": "Obama"}),
    Case("secretary", "The Secretary of State Hillary Clinton",
         {"title": "The Secretary of State", "given": "Hillary",
          "family": "Clinton"}),
    Case("comma_middle_initial", "Doe, John A.",
         {"given": "John", "middle": "A.", "family": "Doe"},
         notes="shape 2's post-comma Middle slot, in the form it is "
               "usually written after a family comma -- an initial",
         shape=2),
    Case("single", "John", {"given": "John"},
         ambiguities=("given-or-family",),
         notes="the plainest O5 shape there is: nothing decides one "
               "name word, so the convention picks the field and says "
               "so (#449). Roles parity; the flag is #449's"),
    Case("title_only", "Dr.", {"title": "Dr."},
         notes="rules.md#H4's boundary as well as a shape row: a LONE "
               "title word demotes nothing, so no reading was chosen "
               "and nothing is reported. The title-vs-given-name "
               "collision on a word like `Baron` is #348's"),
    Case("double_comma_suffix", "Smith, John, Jr.",
         {"given": "John", "family": "Smith", "suffix": "Jr."}),
    Case("bound_given_two", "abdul rahman",
         {"given": "abdul", "family": "rahman"}),
    Case("bound_given_three", "abdul rahman al-said",
         {"given": "abdul rahman", "family": "al-said"}),
    Case("mr_and_mrs", "Mr. and Mrs. John Smith",
         {"title": "Mr. and Mrs.", "given": "John", "family": "Smith"}),
    Case("roman_suffix", "John Smith V",
         {"given": "John", "family": "Smith", "suffix": "V"},
         ambiguities=("suffix-or-name",),
         notes="a trailing single letter is a name part unless it is a "
               "roman numeral; V/X/I are also ordinary middle initials, "
               "so the reading is reported"),
    Case("initial_not_suffix", "John V. Smith",
         {"given": "John", "middle": "V.", "family": "Smith"},
         notes="shape 1's Middle slot filled by an initial-shaped "
               "word, which is the branch a numeral spelling would "
               "otherwise take to the suffix",
         shape=1),
    Case("lenient_after_comma", "John Ingram, V",
         {"given": "John", "family": "Ingram", "suffix": "V"}),
    Case("comma_then_title", "Smith, Dr. John",
         {"title": "Dr.", "given": "John", "family": "Smith"},
         notes="shape 2's post-comma Title slot",
         shape=2),
    Case("nickname_single_name", "John (Jack)",
         {"family": "John", "nickname": "Jack"}),
    Case("nickname_only", "(Jack)", {"nickname": "Jack"}),
    Case("suffix_run", "John Jack Kennedy PhD MD",
         {"given": "John", "middle": "Jack", "family": "Kennedy",
          "suffix": "PhD MD"},
         classification="fix(#436/#437)",
         notes="the NO-COMMA path, which is the one rules.md#R1 "
               "described and the parser violated from 1.4.0 to "
               "2.2.0: no comma stands between PhD and MD, so none "
               "is rendered. The corpus twin is 'John Doe MD PhD'"),
    Case("maiden_marker", "Jane Smith née Jones",
         {"given": "Jane", "family": "Smith", "maiden": "Jones"},
         classification="fix(#274)",
         notes="v1 mangles to middle='Smith née'"),
    Case("phrase_marker_takes_the_maiden_name",
         "Maria Kowalska z domu Nowak",
         {"given": "Maria", "family": "Kowalska", "maiden": "Nowak"},
         classification="fix(#434)",
         notes="the fork a PHRASE entry opens: a marker matched over "
               "more than one token. 'z domu' is the first multi-word "
               "entry any shipped vocabulary set holds, so this is the "
               "row where the multi-token branch of the lookahead is "
               "taken at all -- and the row that pins how many tokens "
               "the take drops. With the marker run forced back to one "
               "piece this reads maiden 'domu Nowak' (measured "
               "2026-08-26), which is also what the library's former "
               "advice produced: the dead-entry warning used to say "
               "'split it into separate entries', and z plus domu as "
               "two entries gives exactly that. 1.4.0 read first Maria "
               "/ middle 'Kowalska z domu' / last Nowak (2026-08-26) "
               "-- the marker inside the name, its ordinary reading of "
               "every marker. phrase_marker_partial_is_not_a_marker "
               "and preposition_alone_is_not_a_marker below are the "
               "boundaries"),
    Case("phrase_marker_partial_is_not_a_marker",
         "Maria Kowalska z Nowak",
         {"given": "Maria", "middle": "Kowalska z", "family": "Nowak"},
         notes="the boundary above it: the phrase's first word with "
               "the second one missing. A lookahead that settled for a "
               "PREFIX of an entry would find a marker here and read "
               "family Kowalska, maiden Nowak (measured 2026-08-26 "
               "with the match relaxed to entries starting with the "
               "key). Nothing about z is marker-ish on its own -- it "
               "is an ordinary Polish preposition -- which is the "
               "whole reason the entry is a phrase. Parity"),
    Case("preposition_alone_is_not_a_marker", "Anna z Nowak",
         {"given": "Anna", "middle": "z", "family": "Nowak"},
         notes="the same boundary with only one name word ahead of "
               "the preposition, which is where the damage of getting "
               "it wrong is worst: under the split-entry workaround "
               "the library used to advise, a bare z IS a marker and "
               "M2 hands it every word after it, so this name reads "
               "maiden 'Nowak' with NO family name at all (measured "
               "2026-08-26). This is the row that would have caught "
               "that advice. It is also the shape "
               "diminutive_that_was_a_marker_keeps_the_family pins for "
               "the roz collision -- a marker entry that is also an "
               "ordinary word eats the family name, and a phrase entry "
               "is how that is avoided rather than accepted "
               "(decisions.md#vocabulary-collisions). Parity"),
    Case("phrase_marker_split_by_a_clause_is_not_a_marker",
         "Anna z (domu) Nowak",
         {"given": "Anna", "middle": "z", "family": "Nowak",
          "nickname": "domu"},
         notes="the fork that is about WHERE a run stands rather than "
               "how it is spelled: the phrase's two words with a "
               "bracketed clause between them. A marker run is tagged "
               "over the whole token stream and consumed over one "
               "SEGMENT, and a segment holds neither -- extract gives "
               "a clause's tokens a role and segment keeps only the "
               "role-less ones -- so a run written across a clause "
               "edge is one the consuming walk cannot see whole. "
               "Tagged anyway, the walk read the first word as the "
               "entire marker and this name came back family 'Anna', "
               "maiden 'Nowak' (measured 2026-08-26): the bare "
               "preposition eating the name, which is the exact damage "
               "the phrase entry exists to prevent. classify refuses "
               "to tag a run that crosses such a boundary, so the "
               "clause is an ordinary nickname and nothing else moves. "
               "Parity: 1.4.0 read first Anna / middle z / last Nowak "
               "/ nickname domu (2026-08-26)"),
    Case("phrase_marker_split_by_a_clause_keeps_the_family",
         "Maria z (domu) Kowalska Nowak",
         {"given": "Maria", "middle": "z Kowalska", "family": "Nowak",
          "nickname": "domu"},
         notes="the row above with a family name to lose, and it is "
               "kept as its own row for the reason "
               "preposition_alone_is_not_a_marker is: the two fail the "
               "same mutation and record different damage from it. "
               "Where that one shuffles fields, this one came back "
               "family 'Maria', maiden 'Kowalska Nowak' -- the real "
               "family name inside the maiden value and gone from its "
               "own field (measured 2026-08-26). Losing a family name "
               "is the consequence worth pinning, not the shuffle. "
               "Parity: 1.4.0 read first Maria / middle 'z Kowalska' / "
               "last Nowak / nickname domu (2026-08-26)"),
    Case("diminutive_that_was_a_marker_keeps_the_family",
         "Rosalind Roz Smith",
         {"given": "Rosalind", "middle": "Roz", "family": "Smith"},
         notes="'roz', the Czech/Slovak abbreviation, shipped in "
               "MAIDEN_MARKERS through 2.1 and collided with the "
               "English diminutive of Rosalind -- matching is "
               "whole-token, case-folded and period-insensitive, so "
               "Roz, roz and roz. are one string. This name read "
               "maiden 'Smith' with NO family name at all (measured on "
               "the pre-removal tree), because M2 hands the marker "
               "every word after it. The entry is gone in 2.2, which "
               "is what this row pins. Nothing to do with the "
               "delimited path, though M3 would have widened it: "
               "the defect is M2's and predates #335, and the one-word "
               "'(Roz)' spelling was never affected since M3 declines "
               "a lone marker -- but 'Jane Smith (Roz Jones)' reads "
               "maiden 'Jones' with the entry restored, where 2.1.0 "
               "read nickname 'Roz Jones' (measured 2026-08-26). "
               "Parity, and it is "
               "RESTORED parity rather than untouched -- 1.4.0 has no "
               "maiden support and read first Rosalind / middle Roz / "
               "last Smith (2026-08-26), which is where the removal "
               "puts this name back"),
    Case("full_participle_marker_still_consumes",
         "Anna Nováková rozená Svobodová",
         {"given": "Anna", "family": "Nováková", "maiden": "Svobodová"},
         classification="fix(#274)",
         notes="the other half of the roz removal, and the reason it "
               "was a removal and not a retreat from Czech: the full "
               "participle rozená stays, being a word no one is "
               "called. Pinned because deleting a vocabulary entry "
               "invites deleting its neighbours, and because nothing "
               "else in the suite reaches this entry: removing "
               "rozená from MAIDEN_MARKERS fails exactly this row's "
               "two tests, one per runner, and nothing else (measured "
               "2026-08-26) -- the position "
               "maiden_marker_delimited_unaccented holds for 'nee'. "
               "The cost the removal accepts is the "
               "abbreviation: 'Anna Nováková roz. Svobodová' now reads "
               "middle 'Nováková roz.', family 'Svobodová' (measured), "
               "which is exactly how 1.4.0 read it. 1.4.0 read this "
               "row middle 'Nováková rozená' / last Svobodová "
               "(2026-08-26) -- the marker inside the name, the "
               "ordinary v1 reading of every marker"),
    Case("maiden_marker_after_particle_chain",
         "Ursula von der Leyen geb. Albrecht",
         {"given": "Ursula", "family": "von der Leyen",
          "maiden": "Albrecht"},
         classification="fix(#399)",
         notes="#399: the chain that joins 'von der' to Leyen used to "
               "run on past the marker and take the maiden name with "
               "it (family 'von der Leyen geb. Albrecht', maiden ''), "
               "because the marker is consumed AFTER the chain merges "
               "and by then there is no lone marker piece left to "
               "find. A suffix already stopped the chain; a marker now "
               "does too. The same words one chain apart -- "
               "maiden_marker_no_particle below is the control"),
    Case("maiden_marker_no_particle", "Ursula Leyen geb. Albrecht",
         {"given": "Ursula", "family": "Leyen", "maiden": "Albrecht"},
         classification="fix(#274)",
         notes="the control for maiden_marker_after_particle_chain: "
               "identical but for the particles, and it always worked. "
               "Pinned so a regression in the plain path cannot hide "
               "behind the particle rows"),
    Case("maiden_marker_after_one_particle", "Anna von Müller geb. Schmidt",
         {"given": "Anna", "family": "von Müller", "maiden": "Schmidt"},
         classification="fix(#399)",
         notes="one particle is enough to break it -- #399 is not "
               "about the length of the run"),
    Case("maiden_marker_after_leading_particle", "von Müller geb. Schmidt",
         {"given": "von", "family": "Müller", "maiden": "Schmidt"},
         classification="fix(#274)",
         ambiguities=("particle-or-given",),
         notes="the second control for #399, and the one that shows "
               "where the old boundary fell: a LEADING particle chains "
               "nothing (P4), so it never reached the marker and this "
               "shape always worked. given 'von' is P4 plus P1 "
               "declining to fold ('von' is outside the never-given "
               "particles), which is also why the row reports the "
               "fork -- not R2, whose output here is the family "
               "('Müller', base 'Müller', particles '')"),
    Case("maiden_marker_after_leading_particle_run",
         "von der Müller geb. Schmidt",
         {"given": "von", "family": "der Müller", "maiden": "Schmidt"},
         classification="fix(#399)",
         ambiguities=("particle-or-given",),
         notes="a leading RUN of two broke where a leading single did "
               "not: 'der' is not the leading piece, so its own chain "
               "fired and swallowed the marker. What #399 left alone "
               "is the given/family SPLIT -- given 'von', family "
               "starting at 'der' (P4 + R2); the family itself shed "
               "the marker and the maiden name it had swallowed "
               "('der Müller geb. Schmidt' -> 'der Müller')"),
    Case("maiden_marker_after_particle_chain_with_suffix",
         "Jane van der Berg née Jones PhD",
         {"given": "Jane", "family": "van der Berg", "maiden": "Jones",
          "suffix": "PhD"},
         classification="fix(#399)",
         notes="marker and suffix in the same name: M2's walk takes "
               "the maiden name up to the suffix before the chain "
               "runs, so the chain has nothing to stop at (under #399 "
               "it stopped at the marker). Dutch spelling of the same "
               "defect, and 'née' unaccented-vs-accented is not the "
               "variable here"),
    Case("maiden_marker_stops_the_leading_run_family_first",
         "de la Cruz née Vega",
         {"family": "de la Cruz", "maiden": "Vega"},
         policy=Policy(name_order=FAMILY_FIRST),
         classification="fix(#399)",
         notes="#399's open question, answered by the marker being "
               "consumed before anything can place it rather than by "
               "a rule of its own: the marker used to "
               "survive as an ordinary name word and compete for the "
               "leftover given slot, so this read given 'née' / middle "
               "'Vega'. Consumed and dropped, it never reaches the "
               "placement. No given name at all is the right answer "
               "for family-plus-maiden input",
         shape=4),
    Case("maiden_marker_leaves_family_all_particles",
         "Jane de la née Jones",
         {"given": "Jane", "family": "de la", "maiden": "Jones"},
         classification="fix(#399)",
         notes="taking the marker before the chain runs can leave a "
               "family group that is wholly particles, which is exactly "
               "the shape R2 "
               "reserves: they are not in particle position, so they "
               "report as ordinary words -- family_base 'de la', "
               "family_particles ''. test_cases pins that split only "
               "up to the partition invariant (non-empty base, words "
               "conserved), so base 'la' / particles 'de' would also "
               "satisfy it. Before #399 this read family 'de la née "
               "Jones' with base 'née Jones'. Nonsense input either "
               "way; pinned "
               "because the two rules have to compose without "
               "either producing an empty base"),
    Case("maiden_marker_trailing_after_particles",
         "Jane van der Berg née",
         {"given": "Jane", "family": "van der Berg née"},
         notes="M2's boundary on the particle side. A marker with "
               "nothing after it is just a word: the consumer declines "
               "it and the chain takes it like any other word. A chain "
               "that stopped at it instead left the marker as a piece "
               "of its own, which then took the whole family field and "
               "demoted the real surname to the middle (family 'née', "
               "middle 'van der Berg'). The first cut "
               "of #399 did exactly that -- the marker-less spelling "
               "'Jones née' -> family 'née' is M2's own boundary "
               "example, and the particle spelling has to agree with "
               "the rest of the family name, not replace it"),
    Case("maiden_marker_trailing_before_suffix",
         "Jane van der Berg née PhD",
         {"given": "Jane", "family": "van der Berg née",
          "suffix": "PhD"},
         notes="the other way the consumer declines: it walks only up "
               "to a trailing suffix, so a marker with nothing but a "
               "suffix after it is not consumed either, and the chain "
               "takes it. Pinned "
               "separately from the row above because the two reach "
               "the same decision through different conditions -- last "
               "piece vs nothing-but-suffix-follows -- and #399's chain "
               "stop, keyed on only one of them, looked correct on the "
               "other"),
    Case("maiden_marker_surname_spelling_keeps_its_particles",
         "Jane van der Nee",
         {"given": "Jane", "family": "van der Nee"},
         notes="'Nee' is an attested surname as well as a marker "
               "spelling, which M1 already says ('a one-word clause "
               "keeps its word, which may itself be a surname'). "
               "Because nothing follows it the consumer declines, so a "
               "Dutch bearer of the surname keeps the tussenvoegsel "
               "in the family name. Ungated, #399 moved 'van der' out "
               "to the middle and left family 'Nee'"),
    Case("maiden_marker_trailing_keeps_the_fork_report",
         "St St née",
         {"title": "St", "family": "St née"},
         ambiguities=("particle-or-given", "title-or-name"),
         notes="'st' is both a title and an ambiguous particle (#367), "
               "so this shape reaches group's PARTICLE_OR_GIVEN "
               "emitter, which is guarded on the chain having merged "
               "something. An ungated marker stop made the chain merge "
               "nothing for a DIFFERENT reason than the guard assumes, "
               "silencing the report while still deciding the fork -- "
               "the shape A1 forbids and #405 closed at P6. Pinned because "
               "removing a report a caller already sees is worse than "
               "never emitting one. The second flag is H4's join "
               "clause, gained in the #518 review round: the one name "
               "unit is a particle CHAIN rather than a P3 join, and "
               "carries `st` -- title vocabulary -- beside the word it "
               "places, which is the same fork. The `particle` tag on "
               "that word is what used to silence it, and a claimed "
               "word decides the FIELD and not whether the word is a "
               "title"),
    Case("maiden_marker_particles_on_both_sides",
         "Anna von der Müller geb. von der Berg",
         {"given": "Anna", "family": "von der Müller",
          "maiden": "von der Berg"},
         classification="fix(#399)",
         notes="a particle chain on each side of the marker. This is "
               "the shape decisions.md#M2 first cited against moving "
               "the maiden handler ahead of the chain and then "
               "retracted -- merged and unmerged pieces hand the "
               "consumer the same words -- and the handler now does "
               "run ahead (#420); pinned so the claim that the reorder "
               "cannot disturb it stays checked. Before #399 the marker rode "
               "into the middle name (middle 'von der Müller geb.')"),
    Case("maiden_marker_stops_the_leading_run", "de la Cruz née Vega",
         {"family": "de la Cruz", "maiden": "Vega"},
         classification="fix(#399)",
         notes="the default-order reading of the family-first row "
               "below, added because that one is core-only and the "
               "facade runner would otherwise never see this class. "
               "Before #399: family 'de la Cruz née Vega'"),
    Case("maiden_marker_stops_the_leading_run_family_first_given_last",
         "de la Cruz née Vega",
         {"family": "de la Cruz", "maiden": "Vega"},
         policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST),
         classification="fix(#399)",
         notes="the sibling of the family-first row, and the point is "
               "that the two orders now AGREE: consuming the marker "
               "leaves no leftover to distribute, so the reading that "
               "distinguishes them has nothing to work on. Before "
               "#399 they differed -- given 'Vega' middle 'née' here "
               "against given 'née' middle 'Vega' under FAMILY_FIRST",
         shape=5),
    Case("connective_join_never_reaches_a_taken_marker",
         "Jane van der Berg née y Jones",
         {"given": "Jane", "family": "van der Berg",
          "maiden": "y Jones"},
         classification="fix(#412)",
         notes="the last of the join-swallows. #399's stop tested for "
               "a LONE marker piece, and P3's connective join ran "
               "earlier in the same stage and merged the marker into "
               "a multi-word piece the stop could not see. The marker "
               "pass now runs before every join, so there is no piece "
               "list on which a join can reach a taken marker. The "
               "maiden name is 'y Jones' by M2's own reading: the "
               "marker takes the words after it, and a connective is "
               "one of them"),
    Case("connective_carveout_counts_the_surviving_name",
         "juan y garcia nee jones",
         {"given": "juan", "middle": "y", "family": "garcia",
          "maiden": "jones"},
         classification="fix(#418)",
         notes="P3's three-word carve-out counted the marker and the "
               "maiden name, so a two-word maiden clause lifted "
               "'juan y garcia' from three words to five, 'y' joined, "
               "and when the clause left nothing was behind for the "
               "family: given 'juan y garcia', family ''. The count "
               "now sees the name that remains, so the clause changes "
               "nothing about how the rest of this name reads -- the "
               "reading is 'juan y garcia' plus a maiden name. "
               "test_parser.py asserts that over the corpus, and "
               "since #410 the only names it steps over are those "
               "that parse to nothing at all"),
    Case("bound_given_reserve_excludes_a_multi_word_maiden_name",
         "Abd Berg née Mary Jones",
         {"given": "Abd", "family": "Berg", "maiden": "Mary Jones"},
         classification="fix(#411)",
         notes="the maiden name is TWO pieces, which is what "
               "distinguishes excluding the span from excluding the "
               "marker plus one. Capping the exclusion at two pieces "
               "reproduces #411 exactly -- given 'Abd Berg', family "
               "'' -- and every other row here has a one-word maiden "
               "name, so none of them can tell the two apart. A "
               "particle-led maiden name does NOT serve: P2's chain "
               "makes 'van der Jones' a single piece"),
    Case("bound_given_join_sees_only_the_surviving_name",
         "abd née Jones Jr Smith Berg",
         {"given": "abd", "middle": "Jr Smith", "family": "Berg",
          "maiden": "Jones"},
         classification="fix(#418)",
         notes="#411's shape, re-pinned twice. The maiden walk stops "
               "at the inner suffix and takes only 'Jones'; with the "
               "marker pass ahead of the joins, P5 then sees 'abd Jr "
               "Smith Berg' and reads it exactly as it reads that "
               "name written alone. Under #411 the join declined here "
               "because the piece it would absorb was the marker; "
               "under #420 the marker was gone before P5 looked and "
               "the join took the suffix instead, given 'abd Jr'; "
               "since #421 the join declines a suffix piece as it "
               "declines a marker, so it takes nothing and 'Jr Smith' "
               "is the middle name, as for 'John Jr Smith Berg'"),
    Case("bound_given_join_takes_a_chain_carrying_a_declined_marker",
         "Abd van der Berg née Jr Jones",
         {"given": "Abd van der Berg née", "middle": "Jr",
          "family": "Jones"},
         classification="fix(#417)",
         notes="the field-level face of #417. The consumer declines "
               "(a suffix follows the marker), the particle chain "
               "takes the declined marker as the word M2 says it is, "
               "and P5 then joins the bound word to the chain -- a "
               "name piece like any other. P5's decline is for a "
               "marker standing as a word of its own, and this one "
               "is not. Under the #399 stop this read given 'Abd van "
               "der Berg', middle 'née Jr'. Pinned here because the "
               "lone-piece reading is the nicer-looking one: a "
               "marker test widened to match inside a piece would "
               "give given 'Abd', middle 'van der Berg née Jr' with "
               "the whole suite otherwise green"),
    Case("bound_given_join_declines_a_marker_before_only_a_suffix",
         "Berg, abdul née PhD",
         {"given": "abdul", "middle": "née", "family": "Berg",
          "suffix": "PhD"},
         classification="fix(#411)",
         notes="a marker the consumer declines is still a piece when "
               "P5 looks, which is why the join asks about the marker "
               "directly rather than relying on the marker pass having "
               "removed it. Nothing but a suffix follows the marker, so "
               "M2 declines -- yet the join would "
               "still absorb it, reading given 'abdul née'. The "
               "marker stays an ordinary word here (M2: with nothing "
               "after it, it is just a word)"),
    Case("bound_given_join_declines_leaving_the_suffix_reading",
         "Berg, abd née Jones",
         {"family": "Berg", "suffix": "abd", "maiden": "Jones"},
         classification="fix(#411)",
         notes="'abd' is the one word in both the bound-given and the "
               "suffix vocabulary, and P5 says the suffix reading "
               "wins in the given slot after a family comma. With the "
               "join declining, that reading is what is left -- so "
               "the name has no given name at all, matching how "
               "'Berg, abd' alone has always parsed. Pinned because "
               "it is the shape where the declining join changes most "
               "and it reads alarmingly"),
    Case("bound_given_marker_immediately_after_the_bound_word",
         "abd née Jones",
         {"given": "abd", "maiden": "Jones"},
         classification="fix(#411)",
         notes="the shortest form of the same decision: the very next "
               "piece is the marker. It is also M4's boundary on the "
               "vocabulary side, and a corpus name rather than a "
               "constructed one: 'abd' is a bound given-name word, so "
               "the vocabulary layer has claimed it as a GIVEN name "
               "and M4 -- which changes only the positional default "
               "-- does not reach it (mechanisms.md#TWO-LAYER-ASSIGN). "
               "Dropping that carve-out reads family 'abd'. The empty "
               "family is what M4 leaves standing here, not a "
               "leftover of the join, and not M2's ordinary "
               "one-name-word behaviour either -- since #445 'Smith "
               "née Jones' reads family 'Smith', and this row is why "
               "'abd née Jones' does not"),
    Case("bound_given_reserve_arabic_script",
         "عبد Berg née Jones",
         {"given": "عبد", "family": "Berg", "maiden": "Jones"},
         classification="fix(#411)",
         notes="the Arabic-script bound word, in the vocabulary since "
               "2.0, pinned so the reserve change reaches it too. "
               "Script segmentation is NOT the point and does not "
               "fire: the segments and the effective script are the "
               "same as for the Latin row, so what this adds is "
               "vocabulary coverage, not a second code path"),
    Case("bound_given_join_no_longer_swallows_a_marker",
         "van der Berg, abdul née Jones",
         {"given": "abdul", "family": "van der Berg",
          "maiden": "Jones"},
         classification="fix(#411)",
         notes="was the second of #412's two join-swallows and is now "
               "fixed as a side effect of #411, which is why the row "
               "is renamed rather than deleted. P5's join used to "
               "merge 'abdul' with the marker before M2's bound could "
               "see a lone marker piece. #411 made the join decline by "
               "counting the reserve without the words the maiden name "
               "takes; since #420 the marker pass takes 'née Jones' "
               "before P5 looks, leaving 'abdul' alone with nothing to "
               "join. P3's connective join was the "
               "last to go, under #412 -- "
               "connective_join_never_reaches_a_taken_marker"),
    Case("maiden_marker_ahead_of_a_conjunction",
         "Jane née and Jones Smith",
         {"family": "Jane", "maiden": "and Jones Smith"},
         classification="fix(#445)",
         notes="M2's greedy reading, with a connective among the "
               "words taken: the same as 'Jane née Jones Smith' with "
               "'and' inside it -- which is why M4 reads it the same "
               "way too, the take leaving one name word either way "
               "(the family was empty here until #445; 1.4.0 read "
               "first 'Jane' / middle 'née and Jones' / last 'Smith', "
               "measured 2026-08-27). Until #412 closed, P3's join ran "
               "first and produced a marker-HEADED piece 'née and "
               "Jones' that the lone-piece test could not see, so the "
               "name read middle 'née and Jones', family 'Smith'. "
               "The lone-piece test stays as M2's own wording "
               "('standing as a word of its own'), but with the pass "
               "ahead of the joins no default-vocabulary input reaches "
               "a marker-headed piece any more, so nothing pins its "
               "`len(piece) == 1` half: kept as definition, not as a "
               "guard -- the comment at _is_maiden_marker_piece "
               "records the measurement"),
    Case("maiden_marker_after_particles_in_a_comma_segment",
         "Smith, Jane van der Berg née Jones",
         {"given": "Jane", "middle": "van der Berg",
          "family": "Smith", "maiden": "Jones"},
         classification="fix(#399)",
         notes="the listing form, where the chain and the marker are "
               "both on the given side of the comma. Before #399 the "
               "marker and the maiden name stayed in the middle name "
               "('van der Berg née Jones'). Distinct from M2's "
               "remaining Accepted note, which is about a marker "
               "standing straight AFTER the comma"),
    Case("bound_given_reserve_excludes_the_maiden_name",
         "Abd Berg née Jones",
         {"given": "Abd", "family": "Berg", "maiden": "Jones"},
         classification="fix(#411)",
         notes="#411: P5 reserves a name word so the join always "
               "leaves a family name behind, but until #420 the "
               "reserve was counted while the marker and the maiden "
               "name were still pieces, the marker pass running after "
               "the join. Four words counted, the join fired, and when "
               "the two departed nothing was left for the family: given "
               "'Abd Berg', family ''. The pass now runs first, so the "
               "reserve sees the two-word name P5 says must not join"),
    Case("bound_given_reserve_excludes_the_maiden_name_with_particles",
         "Abd van der Berg née Jones",
         {"given": "Abd", "family": "van der Berg", "maiden": "Jones"},
         classification="fix(#411)",
         notes="the particle spelling of the row above, which is how "
               "#411 was found -- #399's chain stop put this shape in "
               "front of the reserve for the first time. The chain "
               "makes 'van der Berg' ONE piece, so the count is the "
               "same three-versus-two question"),
    Case("bound_given_reserve_still_joins_with_a_word_to_spare",
         "Abd Allah Smith née Jones",
         {"given": "Abd Allah", "family": "Smith", "maiden": "Jones"},
         classification="fix(#400)",
         notes="the control: one more name word, so the join has its "
               "word to spare even after the maiden name leaves, and "
               "fires exactly as it does without a maiden clause. "
               "Unchanged by #411 -- pinned so the fix cannot be "
               "mistaken for switching the join off near a marker"),
    Case("bound_given_reserve_maiden_and_suffix",
         "Abd Berg née Jones PhD",
         {"given": "Abd", "family": "Berg", "maiden": "Jones",
          "suffix": "PhD"},
         classification="fix(#411)",
         notes="the marker walk stops at a trailing suffix, so the "
               "excluded span is the marker plus 'Jones' and not the "
               "suffix -- which the reserve already discounted. Two "
               "different reasons for a piece not to count, on one "
               "name"),
    Case("maiden_marker_kyusei", "山田花子 旧姓 佐藤",
         {"family": "山田花子", "maiden": "佐藤"},
         classification="fix(#309)",
         notes="旧姓 is default vocabulary, not pack data: a "
               "native-script marker cannot collide with a Latin-script "
               "name and matching is whole-token, the same rule that "
               "admitted урожд. Reaches a marker that is its own TOKEN. "
               "Japanese more often brackets the marker and writes a "
               "fullwidth colon after it, and '山田（旧姓：佐藤）' under "
               "maiden_delimiters still gives maiden '旧姓：佐藤', marker "
               "and colon attached -- not because the marker escapes "
               "tagging (classify tags it fine wherever it is a token; "
               "what #329 fixed was the CONSUMING, since group's #274 "
               "rule walks pieces and a role-bearing token is not in "
               "pieces) but because ：glues marker to name into a "
               "single token, leaving nothing to drop. The spaced "
               "bracketed form is pinned by "
               "maiden_marker_kyusei_delimited below; the glued one "
               "wants the head-peel #317 tracks. 1.4.0 read this "
               "first 山田花子 / middle 旧姓 / last 佐藤 -- the marker "
               "sat in the name"),
    Case("maiden_marker_kyusei_segmented", "山田 花子 旧姓 佐藤",
         {"given": "花子", "family": "山田", "maiden": "佐藤"},
         classification="fix(#309)",
         notes="the row above with the family name spaced, so the "
               "marker is consumed from a name that already has a "
               "given side -- pinned because #274's consuming rule "
               "takes the marker plus the piece after it, and the "
               "pieces before it are what could have gone wrong. "
               "1.4.0 read this first 山田 / middle '花子 旧姓' / "
               "last 佐藤"),
    Case("maiden_marker_delimited", "Jane Smith (née Jones)",
         {"given": "Jane", "family": "Smith", "maiden": "Jones"},
         policy=Policy(maiden_delimiters=frozenset({("(", ")")})),
         classification="fix(#329)",
         notes="#329: the bracketed form now agrees with the bare "
               "maiden_marker row above -- both give maiden 'Jones'. "
               "Before, the marker rode along inside the value: "
               "extract records the clause as a span (it makes no "
               "tokens at all), tokenize gives the tokens it cuts "
               "there Role.MAIDEN, and group's #274 consuming rule "
               "walks pieces, which hold no role-bearing token; the "
               "fix drops the marker inside the CLAUSE instead. The "
               "facade runner reaches this row by performing the "
               "bucket move itself, so it is exercised twice. 1.4.0 "
               "expresses the policy the same way: "
               "measured 2026-08-02 through the bucket-move idiom "
               "maiden_delimiters['parenthesis'] = "
               "nickname_delimiters.pop('parenthesis'), it gave first "
               "Jane / last Smith / maiden 'née Jones' -- same name "
               "fields, marker still inside the value, which is the "
               "single field this change moves. Since #335 the same "
               "input reads identically with NO policy at all "
               "(maiden_marked_clause_reads_maiden_by_default below), "
               "which does not make this row redundant: the pair "
               "sitting in the maiden bucket settles the role before "
               "M3 is consulted, so this row exercises M1's path and "
               "that one exercises M3's. Rewriting it to drop the "
               "policy would delete the configured path's coverage "
               "rather than move it"),
    Case("maiden_marker_delimited_unaccented", "Jane Smith (nee Jones)",
         {"given": "Jane", "family": "Smith", "maiden": "Jones"},
         policy=Policy(maiden_delimiters=frozenset({("(", ")")})),
         classification="fix(#329)",
         notes="the row above with the marker spelled unaccented, and "
               "it is the ONLY row in the suite whose value depends "
               "on 'nee' being in the default MAIDEN_MARKERS: "
               "everything else reaches the marker branch through "
               "'née', 'geb' or '旧姓', or through a stage lexicon of "
               "its own. Removing the entry now fails exactly this "
               "row's two tests, one per runner (measured 2026-08-03); "
               "before this row existed it left the whole suite green, "
               "so the shipped spelling English writes most often was "
               "one vocabulary edit from silence. 1.4.0 under the "
               "bucket-move idiom gave first Jane / last Smith / "
               "maiden 'nee Jones' (2026-08-03) -- the same diff the "
               "accented row records, which is the point: the two "
               "spellings behave alike on both sides"),
    Case("maiden_marked_clause_reads_maiden_by_default",
         "Jane Smith (née Jones)",
         {"given": "Jane", "family": "Smith", "maiden": "Jones"},
         classification="fix(#335)",
         notes="rules.md#M3 -- the clause says 'maiden' out loud, so the "
               "pair enclosing it does not have to be configured. "
               "maiden_marker_delimited above is the same input under "
               "Policy(maiden_delimiters=...) and reads identically -- "
               "what M3 adds is the DEFAULT reading, where 1.4.0 and "
               "2.1 alike gave nickname 'née Jones'"),
    Case("phrase_marker_delimited_clause",
         "Maria Kowalska (z domu Nowak)",
         {"given": "Maria", "family": "Kowalska", "maiden": "Nowak"},
         classification="fix(#434)",
         notes="the phrase fork at the OTHER drop site. M3 reads the "
               "clause and #329's clause pass drops the marker from "
               "inside it, and that pass counts tokens of its own -- "
               "phrase_marker_takes_the_maiden_name above exercises "
               "M2's pieces walk instead, so a count that stayed at "
               "one token in either place is caught by exactly one of "
               "the two rows (measured 2026-08-26: forcing the clause "
               "pass back to a single token moves this row to maiden "
               "'domu Nowak' and leaves the bare row alone, and "
               "forcing the pieces walk back does the mirror). 1.4.0 "
               "read first Maria / last Kowalska / nickname 'z domu "
               "Nowak' (2026-08-26), the clause a nickname because "
               "nothing looked inside it"),
    Case("phrase_marker_delimited_alone_stays_a_nickname",
         "Maria Kowalska (z domu)",
         {"given": "Maria", "family": "Kowalska", "nickname": "z domu"},
         notes="M3's word-after condition, asked of a PHRASE: the word "
               "must come after the whole marker run, not after the "
               "clause's first word. "
               "maiden_marked_clause_one_word_stays_a_nickname holds "
               "the same boundary for a one-word marker, and cannot "
               "reach this one -- a condition written as 'more than "
               "one word in the clause' satisfies that row and turns "
               "this clause into a maiden one. What it produces is "
               "maiden 'z domu' (measured 2026-08-26): the same two "
               "words, in the other field, which is the whole of what "
               "M3 decides here. The VALUE does not move, because the "
               "#329 drop is a separate site and declines for its own "
               "reason -- there is no word past the run inside the "
               "clause -- so this row catches the mutation on the "
               "field alone. Parity: 1.4.0 read nickname 'z domu'"),
    Case("phrase_marker_delimited_alone_keeps_its_words",
         "Maria Kowalska (z domu)",
         {"given": "Maria", "family": "Kowalska", "maiden": "z domu"},
         policy=Policy(maiden_delimiters=frozenset({("(", ")")})),
         notes="the same string as "
               "phrase_marker_delimited_alone_stays_a_nickname above, "
               "under the pair M1 governs, and it reaches a branch "
               "that row cannot: with the pair configured the clause "
               "IS the maiden name, so the #329 drop runs and has to "
               "decide whether a word stands past the marker. It does "
               "not -- both words ARE the marker -- so M1's carve-out "
               "keeps them, which is what the value shows. That "
               "containment test spans the whole marker run, and "
               "reading it one token in instead deletes this clause's "
               "text: the marker is dropped and nothing is left. "
               "Measured 2026-08-26, that mutation fails exactly one "
               "test in the suite, M1's own doc example -- which is a "
               "doc, edited by the commit that changes behavior, so "
               "the pin belongs here too (the argument "
               "build_rules_corpus.py makes for the rules corpus, one "
               "layer down). Deleting the guard OUTRIGHT is caught by "
               "the one-word rows instead -- "
               "maiden_marker_delimited_two_clauses and M1's (Nee) "
               "examples -- so this row is the phrase half of the "
               "branch and not the branch. Parity: 1.4.0 under the "
               "bucket-move idiom read first Maria / last Kowalska / "
               "maiden 'z domu' (2026-08-26)"),
    Case("maiden_marked_clause_interior_keeps_the_family",
         "Jane (née Jones) Smith",
         {"given": "Jane", "family": "Smith", "maiden": "Jones"},
         classification="fix(#335)",
         notes="the row that decides the MECHANISM. Extracting the "
               "clause as a Role.MAIDEN region keeps the closing "
               "delimiter as the maiden name's right boundary; masking "
               "the delimiters and letting M2's bare-marker rule "
               "consume the content instead would read maiden 'Jones "
               "Smith' with an empty family, because M2's take runs to "
               "the end of the name. The parens say where it stops"),
    Case("maiden_marked_clause_one_word_stays_a_nickname",
         "Jane Smith (née)",
         {"given": "Jane", "family": "Smith", "nickname": "née"},
         notes="M3's boundary: a marker with no word after it is not a "
               "maiden clause. Without this condition the default "
               "reading of a lone parenthesized marker would flip to "
               "maiden 'née', and M1's own (Nee) boundary -- a "
               "one-word clause keeps its word, which may be the "
               "surname Nee -- would be contradicted on the "
               "unconfigured path. Parity: 1.4.0 read nickname 'née'"),
    Case("markerless_parenthesized_clause_stays_a_nickname",
         "Cherice J. (Mary Johnson) Williams",
         {"given": "Cherice", "middle": "J.", "family": "Williams",
          "nickname": "Mary Johnson"},
         notes="M3's other boundary, and the reason the maiden "
               "delimiters remain worth configuring: the parenthesized "
               "birth surname without a marker is a real US convention "
               "-- 'Cherice J. (Johnson) Williams' is the corpus name "
               "(corpus_issues.jsonl) -- but nothing in the clause "
               "says 'maiden', so it stays a nickname by default. Only "
               "a caller who knows their data can say otherwise, which "
               "is what Policy(maiden_delimiters=...) is for. The "
               "clause is TWO words here, and that is the whole point "
               "of the row: M3 tests the clause length before it tests "
               "the vocabulary, so the corpus spelling's one-word "
               "clause is refused by the length condition and never "
               "reaches the vocabulary one -- it would duplicate "
               "maiden_marked_clause_one_word_stays_a_nickname rather "
               "than fence the other condition. Measured 2026-08-26: "
               "with the vocabulary test dropped this reads maiden "
               "'Mary Johnson' -- the WHOLE clause, because #329's "
               "drop is gated on the first token carrying "
               "vocab:maiden-marker and 'Mary' does not, so nothing is "
               "dropped -- and with the vocabulary test in place the "
               "one-word spelling reads nickname either way. Parity: "
               "1.4.0 and 2.1.0 both read nickname 'Mary Johnson'"),
    Case("markerless_one_word_clause_stays_a_nickname",
         "Cherice J. (Johnson) Williams",
         {"given": "Cherice", "middle": "J.", "family": "Williams",
          "nickname": "Johnson"},
         notes="the corpus spelling (corpus_issues.jsonl) of the row "
               "above, kept beside it rather than replaced by it. It "
               "reaches M3's length condition and stops there, so it "
               "cannot fence the vocabulary one -- which is why the "
               "row above widens the clause to two words -- but it is "
               "the name real US data actually carries, and a row for "
               "the corpus name is worth its two lines. Parity"),
    Case("maiden_marker_not_first_stays_a_nickname",
         "Jane Smith (Jones née)",
         {"given": "Jane", "family": "Smith", "nickname": "Jones née"},
         notes="the OPENS-WITH half of M3, which nothing else reaches: "
               "a marker inside the clause but not first leaves the "
               "clause a nickname. Measured 2026-08-26, widening the "
               "predicate from the first word to any word left the "
               "whole suite green and all three gates at 0 unexplained "
               "-- this row is what closes that. The bracketed twin of "
               "maiden_marker_delimited_trailing_marker, which pins the "
               "same asymmetry one layer down, inside a clause already "
               "routed to maiden by policy: no marker the shipped "
               "vocabulary carries is written after the name it marks. "
               "Parity: 1.4.0 and 2.1.0 both read nickname 'Jones née'"),
    Case("marker_led_clause_with_one_name_word",
         "Smith (née Jones)",
         {"family": "Smith", "maiden": "Jones"},
         classification="fix(#445)",
         notes="N3's shape meeting M3, and the row exists because the "
               "two rules disagree about what a clause is. N3 reads a "
               "name that is only a nickname plus one name word as "
               "'that word is the family name' -- but a marker-led "
               "clause is not a nickname clause, so N3 never sees this "
               "one, and until #445 the word kept the given-name "
               "reading the bare spelling gives it. M4 now reaches "
               "both spellings from the other side: the marker "
               "announces a FORMER surname, so the one name word left "
               "beside it is the current one. The bracketed spelling "
               "RESTORES the family EVERY released version read: "
               "1.4.0, 2.0.0 and 2.1.0 all read this name family "
               "'Smith', nickname 'née Jones' (measured on the wheels "
               "2026-08-27), so the clause reading maiden rather than "
               "nickname is #335's half and the only thing left that "
               "differs -- at all three baselines alike. Be exact "
               "about which spelling read `given`, because a ledger "
               "took the loose wording this note used to carry and "
               "narrowed one baseline where three needed it: the BARE "
               "spelling is what read given 'Smith' on 2.0.0, on "
               "2.1.0 and here until this rule (1.4.0 read it first "
               "'Smith' / middle 'née' / last 'Jones'). The bracketed "
               "spelling this row holds never read `given` on any "
               "released version"),
    Case("maiden_marker_makes_the_lone_name_word_the_family",
         "Smith née Jones",
         {"family": "Smith", "maiden": "Jones"},
         classification="fix(#445)",
         notes="the rule, in its bare spelling: a maiden marker marks "
               "a surname the bearer no longer uses, so it only means "
               "anything beside one they do. With exactly one name "
               "word left after the take, that word is the current "
               "surname, and the positional convention O5 would "
               "otherwise apply (a lone name word is read given) is "
               "the thing M4 overrides. Read given 'Smith', family '' "
               "on 2.0.0 and 2.1.0; 1.4.0 had no maiden support and "
               "read first 'Smith' / middle 'née' / last 'Jones' "
               "(measured 2026-08-27), so this is a new reading and "
               "not a restoration -- the bracketed sibling "
               "marker_led_clause_with_one_name_word is the "
               "restoration"),
    Case("maiden_marker_interior_makes_the_lone_name_word_the_family",
         "Jane née Jones Smith",
         {"family": "Jane", "maiden": "Jones Smith"},
         classification="fix(#445)",
         notes="the marker standing INSIDE the name, where M2's take "
               "runs to the end and swallows the rest -- so what is "
               "left is again one name word, and M4 counts what is "
               "left rather than where the marker stood. The widest "
               "half of the rule and the row that pins it: a guard "
               "that asked for the marker to be trailing would leave "
               "this one given 'Jane'. A new reading, and the one "
               "furthest from 1.4.0, which read first 'Jane' / middle "
               "'née Jones' / last 'Smith' (measured 2026-08-27) -- "
               "the real surname there is 'Smith', which 2.x reads as "
               "part of the maiden name (M2's greedy take, unchanged "
               "here)"),
    Case("maiden_marker_lone_name_word_with_suffix",
         "Smith née Jones PhD",
         {"family": "Smith", "suffix": "PhD", "maiden": "Jones"},
         classification="fix(#445)",
         notes="an annotation is not a name word, which is what #410 "
               "established for H1 and M4 inherits: the credential "
               "stands beside the name and does not make it any "
               "longer, so the count that decides this reading is "
               "one either way. A guard written over roles generally "
               "rather than the three name roles reads this name as "
               "two words and declines. 1.4.0 read first 'Smith' / "
               "middle 'née' / last 'Jones' / suffix 'PhD' (measured "
               "2026-08-27)"),
    Case("maiden_marked_lone_initial_stays_given",
         "J. née Jones Smith V",
         {"given": "J.", "maiden": "Jones Smith V"},
         classification="fix(#274)",
         notes="M4's boundary on the shape side, and a corpus name "
               "rather than a constructed one: an initial is not a "
               "family name, so the word the vocabulary layer has "
               "already claimed as a shape keeps its reading "
               "(mechanisms.md#TWO-LAYER-ASSIGN -- M4 changes the "
               "POSITIONAL default and must not reach a word another "
               "layer has claimed). Dropping the carve-out reads "
               "family 'J.'. Unchanged by #445, and the maiden value "
               "is M2's: the trailing 'V' is S2's suffix reading only "
               "where a name word precedes it, and an initial does "
               "not count, so the numeral stays maiden text (M2 "
               "carries the same input as a boundary example). The "
               "fix classification is #274's marker consumption, "
               "which is what makes this differ from 1.4.0 (first "
               "'J.' / middle 'née Jones' / last 'Smith' / suffix "
               "'V', measured 2026-08-27)"),
    Case("lone_name_word_reports_the_convention", "Andrew",
         {"given": "Andrew"}, ambiguities=("given-or-family",),
         classification="feat(#449)",
         notes="rules.md#O5 -- nothing decided this reading, so the "
               "convention picked the field and says so"),
    Case("lone_name_word_reports_the_convention_family_first", "Garcia",
         {"family": "Garcia"}, policy=Policy(name_order=FAMILY_FIRST),
         ambiguities=("given-or-family",), classification="feat(#449)",
         notes="the kind cannot name the field -- the convention "
               "follows the read order, the PARTICLE_OR_GIVEN precedent"),
    Case("lone_name_word_joined_by_a_connective_is_one_word", "Juan & Garcia",
         {"given": "Juan & Garcia"}, ambiguities=("given-or-family",),
         classification="feat(#449)",
         notes="rules.md#P3 -- a joined part is one name word wherever "
               "another rule counts them, and O5 counts them"),
    Case("lone_name_word_bound_given_vocabulary_decides", "abdul",
         {"given": "abdul"}, classification="parity",
         notes="negative control: the vocabulary claimed the word as a "
               "given name, so the convention decided nothing"),
    Case("lone_name_word_particle_reading_is_p4s", "de",
         {"given": "de"}, classification="parity",
         notes="negative control: a lone particle's reading is P4's, "
               "not O5's convention"),
    Case("lone_name_word_initial_shape_decides_it", "J",
         {"given": "J"}, classification="parity",
         notes="negative control: the word's own SHAPE claimed it as "
               "an initial -- the third member of "
               "_WORD_ALREADY_CLAIMED beside 'abdul' and 'de', and "
               "the only one of the three that is not vocabulary"),
    Case("lone_name_word_beside_a_suffix_still_reports", "Smith Jr.",
         {"given": "Smith", "suffix": "Jr."},
         ambiguities=("given-or-family",), classification="feat(#449)",
         notes="rules.md#S2 peels the suffix and leaves ONE name word, "
               "which O5's convention then places -- the peel decided "
               "the suffix, not the field"),
    Case("lone_name_word_beside_a_nickname_and_a_suffix_reports",
         "'Smitty' Jones Jr.",
         {"given": "Jones", "suffix": "Jr.", "nickname": "Smitty"},
         ambiguities=("given-or-family",), classification="feat(#449)",
         notes="rules.md#O5's own example: N3's count does not set "
               "aside a suffix standing beside the nickname, so N3 "
               "declines and the convention is what places 'Jones'"),
    Case("lone_name_word_title_decides_it", "Dr. Smith",
         {"title": "Dr.", "family": "Smith"}, classification="parity",
         notes="negative control for both conventions: H1 decided it, "
               "and `smith` is not title vocabulary, so H4 does not "
               "claim the input either"),
    Case("lone_name_word_nickname_decides_it", "'Smitty' Smith",
         {"family": "Smith", "nickname": "Smitty"}, classification="parity",
         notes="boundary: N3 returns before the O5 site is reached, so "
               "the convention never ran -- not a control of any guard "
               "clause, which is why the emitter carries none"),
    Case("lone_name_word_comma_decides_it", "Smith, Andrew",
         {"given": "Andrew", "family": "Smith"}, classification="parity",
         notes="boundary: the comma named the family before the "
               "positional read, so one name word never stood alone "
               "here -- not a control of any guard clause"),
    Case("all_titles_input_reports_the_demoted_word", "Lord Chancellor",
         {"title": "Lord", "family": "Chancellor"},
         ambiguities=("title-or-name",), classification="feat(#491)",
         notes="rules.md#H4 -- nothing but title vocabulary, so the "
               "last title word is the name by convention and says so"),
    Case("all_titles_input_the_queens_bench_string",
         "The Right Hon. the President of the Queen's Bench Division",
         {"title": "The Right Hon. the President of the Queen's Bench",
          "family": "Division"},
         ambiguities=("title-or-name",), classification="feat(#491)",
         notes="decisions.md#v1-xfail-triage's fourth NOT FIXED entry: "
               "the reading stands, and the guess stops being silent"),
    Case("all_titles_input_a_title_vocabulary_surname", "Dr. King",
         {"title": "Dr.", "family": "King"},
         ambiguities=("title-or-name",), classification="feat(#491)",
         notes="`king` is title vocabulary for the addressing forms, so "
               "the peel leaves one title-vocabulary word and the rule "
               "claims it"),
    Case("all_titles_input_family_first", "Lord Chancellor",
         {"title": "Lord", "family": "Chancellor"},
         policy=Policy(name_order=FAMILY_FIRST),
         ambiguities=("title-or-name",), classification="feat(#491)",
         notes="the report is made where the word is PLACED, so a "
               "declared family-first order -- which puts 'Chancellor' "
               "in the family directly and leaves H1's retag no work -- "
               "gives the same reading and the same kind. The site was "
               "H1's retag until the family-first orders were measured "
               "silent there"),
    Case("title_run_then_a_credential_reports_the_name_word",
         "Dr. King MD",
         {"title": "Dr.", "family": "King", "suffix": "MD"},
         ambiguities=("title-or-name",), classification="fix(#489)",
         notes="rules.md#H3's floor: everything behind the run is a "
               "suffix piece and `King` is not one, so the run gives "
               "it back and the credential is a credential. `king` "
               "being title vocabulary, the word left standing is "
               "H4's title half -- the same reading `Dr. King, Jr.` "
               "has always had"),
    Case("title_run_then_a_bare_generational_reports_the_name_word",
         "Dr King Jr", {"title": "Dr", "family": "King", "suffix": "Jr"},
         ambiguities=("title-or-name",), classification="fix(#489)",
         notes="v1 wanted exactly this reading and the 2026-09-01 "
               "triage pinned the old one as NOT FIXED; rules.md#S2's "
               "descriptive note said a change toward S2's prediction "
               "would be an improvement, and this is it"),
    Case("title_run_floor_gives_back_a_given_name_title",
         "Dr Jr", {"given": "Dr", "suffix": "Jr"},
         ambiguities=("title-or-name",), classification="fix(#489)",
         notes="the accepted edge: with `Dr` given back and `Jr` "
               "peeled as the suffix, no title is left to make the "
               "reading H1's, so the lone name word is H4's -- "
               "`dr` is title vocabulary and the word standing is it. "
               "This shape is what rules.md#S2's descriptive note "
               "named, in its `Sir Jr` spelling, as the reading it "
               "predicted and did not get; once the floor empties the "
               "run no branch reads `vocab:given-title` at all, so "
               "`Sir Jr` is this row in every part -- same roles, same "
               "kind, the detail naming a different word -- and it is "
               "not pinned twice"),
    Case("title_run_floor_gives_back_the_last_of_a_run",
         "Lord Chancellor Jr",
         {"title": "Lord", "family": "Chancellor", "suffix": "Jr"},
         ambiguities=("title-or-name",), classification="fix(#489)",
         notes="the floor takes back ONE word, the run's last, and "
               "`Lord Chancellor` is the input decisions.md#H4 already "
               "uses for the all-titles convention"),
    Case("title_run_floor_keeps_a_joined_title_unit",
         "Prince of Wales Jr",
         {"title": "Prince of Wales", "family": "Jr"},
         classification="parity",
         notes="the floor gives back its last piece only when that "
               "piece is ONE WORD: a joined unit led by a title is a "
               "title run, and handing it back would turn a title into "
               "a given name and leave the name with no title at all"),
    Case("title_run_floor_declines_an_all_suffix_input", "MD DDS",
         {"title": "MD", "family": "DDS"}, classification="parity",
         notes="negative control: the word the run would give back is "
               "`MD`, which IS suffix vocabulary, so the floor "
               "declines. `md` is title vocabulary too, so the run is "
               "`MD` and H1's fold claims `DDS` -- not the bare-suffix "
               "carve-out, which reads the FIRST word as the name and "
               "reports `suffix-or-name` (`DDS MD`). Nothing reports "
               "here"),
    Case("title_run_floor_declines_a_split_credential", "Jr. Ph. D.",
         {"title": "Jr.", "suffix": "Ph. D."}, classification="parity",
         notes="negative control: `Jr.` is suffix vocabulary wearing "
               "H2's opening-abbreviation shape, so the floor declines "
               "there too"),
    Case("title_run_floor_declines_an_all_title_input",
         "Marquess of Bath", {"title": "Marquess of Bath"},
         classification="parity",
         notes="negative control: nothing stands behind the run, so "
               "there is no all-suffix rest for the floor to see"),
    Case("title_run_addresses_by_its_last_title",
         "Her Majesty Queen Elizabeth",
         {"title": "Her Majesty Queen", "given": "Elizabeth"},
         classification="fix(#489)",
         notes="rules.md#H1 -- `queen` is a given-name title and it is "
               "the last word of the run, so the run addresses as it "
               "does; the empty family is H1's Accepted outcome"),
    Case("title_run_addresses_by_its_last_title_with_a_suffix",
         "Her Majesty Queen Elizabeth II",
         {"title": "Her Majesty Queen", "given": "Elizabeth",
          "suffix": "II"}, classification="fix(#489)",
         notes="the suffix peel runs first and does not decide H1"),
    Case("title_run_addresses_by_its_last_title_clerical",
         "Reverend Mother Teresa",
         {"title": "Reverend Mother", "given": "Teresa"},
         classification="fix(#489)",
         notes="`mother` is a given-name title, `reverend` is not"),
    Case("title_run_addresses_by_its_last_title_dotted",
         "Dr. Sir John", {"title": "Dr. Sir", "given": "John"},
         classification="fix(#489)",
         notes="the whole run keyed 'dr sir', which the shipped "
               "vocabulary has no entry for; the last word is `sir`"),
    Case("title_run_addresses_by_its_last_title_bare", "Mr Sir John",
         {"title": "Mr Sir", "given": "John"},
         classification="fix(#489)",
         notes="the 2026-08-22 #369 entry's own example -- 'mr sir' is "
               "not a given-name title to either site, and now the "
               "LAST word is what both sites read"),
    Case("title_run_addresses_by_its_last_title_unlisted_first",
         "Xyz. Sir John", {"title": "Xyz. Sir", "given": "John"},
         classification="fix(#489)",
         notes="H2's unlisted abbreviation joins the run: it sits "
               "inside the whole-run key, which the shipped "
               "vocabulary has no entry for, and an unlisted word can "
               "never match as a last-word key either -- `sir` is "
               "what this run is read by"),
    Case("title_run_licences_the_bound_join_by_its_last_title",
         "Sir Sheikh abdul rahman",
         {"title": "Sir Sheikh", "given": "abdul rahman"},
         classification="fix(#489)",
         notes="rules.md#P5's licence keys the same way H1 does, the "
               "invariant the #369 entry set: behind a given-name "
               "title there is no family to spare"),
    Case("title_run_does_not_address_by_a_non_given_name_title",
         "His Excellency Lord Duncan",
         {"title": "His Excellency Lord", "family": "Duncan"},
         classification="parity",
         notes="negative control: `lord` is not a given-name title, so "
               "the run's last word does not address by given name"),
    # -- #519: prince and princess join the given-name titles. The
    # criterion is rules.md#H Background's: a title that precedes and
    # addresses by the GIVEN name belongs. "Prince Harry", "Princess
    # Anne" address by given name and no surname reading of the word
    # behind them exists. lord and lady stay out, decided: both split
    # by the bearer's rank, given name for children of the senior
    # ranks (Lord Peter, Lady Diana) and title or surname for every
    # peer and every wife (Lord Byron, Lady Thatcher), and the set
    # has no way to say "sometimes" -- the reason `venerable` stayed
    # out.
    Case("title_run_princess_addresses_by_given_name",
         "Her Royal Highness Princess Anne",
         {"title": "Her Royal Highness Princess", "given": "Anne"},
         classification="fix(#519)",
         notes="was the #489 bundle's negative control for the "
               "vocabulary question it filed as #519; `princess` now "
               "IS a given-name title, so the run's last word "
               "addresses by given name and the family is empty"),
    Case("prince_and_one_name_word_is_a_given_name", "Prince Harry",
         {"title": "Prince", "given": "Harry"},
         classification="fix(#519)",
         notes="the name the release note advertises: 1.4.0 through "
               "2.2.0 read family 'Harry'. H1's fold is pinned by the "
               "Sir John rows; this pins the membership"),
    Case("prince_licences_the_bound_given_join", "Prince abdul Rahman",
         {"title": "Prince", "given": "abdul Rahman"},
         classification="fix(#519)",
         notes="the second site that reads the set, rules.md#P5's "
               "licence: behind a given-name title there is no family "
               "to spare, so the bound word joins forward as it does "
               "behind Sir. Read family 'Rahman' before #519"),
    Case("prince_as_a_given_name_is_still_the_collision", "Prince Fielder",
         {"title": "Prince", "given": "Fielder"},
         classification="fix(#519)",
         notes="wrong either way -- Prince is his given name (#348). "
               "Membership only decides which field the one word "
               "behind the title takes; it does not decide whether "
               "the word IS a title, and that is #348's question, "
               "not this one's"),
    Case("lord_stays_a_surname_title", "Lord Byron",
         {"title": "Lord", "family": "Byron"},
         notes="negative control for #519: `lord` addresses a duke's "
               "or marquess's younger son by given name (Lord Peter) "
               "and every peer by title (Lord Byron); the set cannot "
               "say 'sometimes', so it stays out and H1 families the "
               "one word"),
    Case("lady_stays_a_surname_title", "Lady Gaga",
         {"title": "Lady", "family": "Gaga"},
         notes="negative control for #519: `lady` addresses by given "
               "name for a peer's daughter (Lady Diana) and by "
               "surname for a wife (Lady Thatcher); the set cannot "
               "say 'sometimes', so it stays out as `lord` does"),
    Case("title_and_two_name_words_is_not_h1s", "Sir John Smith",
         {"title": "Sir", "given": "John", "family": "Smith"},
         classification="parity",
         notes="negative control: H1 never fires with two name words, "
               "whatever the run keys to"),
    Case("all_suffix_input_reports_suffix_or_name", "Rinpoche",
         {"given": "Rinpoche"}, ambiguities=("suffix-or-name",),
         classification="feat(#491)",
         notes="rules.md#H4's suffix half: post-nominal vocabulary with "
               "no name word beside it, read as the name"),
    Case("all_suffix_input_two_words", "QC MP",
         {"given": "QC", "suffix": "MP"}, ambiguities=("suffix-or-name",),
         classification="feat(#491)",
         notes="the first word is the name and the rest the run; only "
               "the word made into a name reports"),
    Case("lone_joined_unit_carrying_title_vocabulary", "John of Prince",
         {"given": "John of Prince"}, ambiguities=("title-or-name",),
         classification="feat(#491)",
         notes="rules.md#O5's exception: the one name unit is a join "
               "(P3) carrying title vocabulary, so the doubt is "
               "whether `Prince` is a title rather than which field "
               "the unit takes -- one of the inputs measured to reach "
               "that branch, `prince` being in TITLES"),
    Case("lone_joined_unit_carrying_collision_set_title_vocabulary",
         "Smith and King", {"given": "Smith and King"},
         ambiguities=("title-or-name",),
         classification="feat(#491)",
         notes="the clause reaches every join whose non-leading member "
               "is TITLES vocabulary, not just `prince`: `John and "
               "King`, `Smith and Bishop` and `John of Judge` report "
               "it too. That is the king/judge/bishop collision set "
               "(decisions.md#vocabulary-collisions) met inside a "
               "join, and the report is deliberate -- a second surname "
               "that is also title vocabulary is the doubt the kind "
               "names"),
    Case("lone_joined_unit_led_by_a_title_is_a_title_run",
         "Prince of Wales", {"title": "Prince of Wales"},
         classification="parity",
         notes="boundary: a join whose FIRST word is title vocabulary "
               "chains into a title run (H3) and never reaches the "
               "assignment site at all, so it reports nothing -- the "
               "same silence as a lone `Dr.`"),
    Case("lone_joined_unit_behind_a_peeled_title", "Dr. Smith and Prince",
         {"title": "Dr.", "family": "Smith and Prince"},
         ambiguities=("title-or-name",), classification="parity",
         notes="the join clause is H4's and asks whether a WORD is a "
               "title, so a title peeled in FRONT of the unit does not "
               "answer it -- which is why the clause sits beside H4's "
               "peel half rather than under O5's field-deciding "
               "leg (#449 review round). 'Lord Chancellor née Jones' "
               "is the same hoist on the maiden clause. Roles parity; "
               "the flag is #491's"),
    Case("lone_title_word_beside_a_maiden_name_still_reports",
         "Lord Chancellor née Jones",
         {"title": "Lord", "family": "Chancellor", "maiden": "Jones"},
         ambiguities=("title-or-name",), classification="fix(#410)",
         notes="a maiden name decides the FIELD (M4, and H1's widening "
               "is what keeps 'Chancellor' in the family), and says "
               "nothing about whether 'Chancellor' is a title -- so it "
               "silences O5's report and not H4's. 1.4.0 had no maiden "
               "SUPPORT and read title 'Lord Chancellor', first 'née', "
               "last 'Jones'"),
    Case("comma_path_title_decides_the_lone_word", "John V, Dr.",
         {"title": "Dr.", "family": "John", "suffix": "V"},
         ambiguities=("suffix-or-name",), classification="fix(#296)",
         notes="a comma with no name word after it hands segment 0 "
               "back to the positional read, and the title deciding "
               "the field stands in the OTHER segment where the "
               "leading-title peel cannot count it -- so the read is "
               "told (`titled`) and O5 stays silent, where it named "
               "`given` for a word H1 then wrote to `family` (#449 "
               "review round). The roman numeral still reports, that "
               "fork being untouched. 1.4.0 read first 'John', last "
               "'V', suffix 'Dr.', 'dr' having been suffix vocabulary "
               "before the audit"),
    Case("comma_path_given_name_title_decides_the_lone_word",
         "John V, Sir",
         {"title": "Sir", "given": "John", "suffix": "V"},
         ambiguities=("suffix-or-name",), classification="fix(#296)",
         notes="the row above with a GIVEN-NAME title, which leaves "
               "the word in `given` -- the field O5 would have named. "
               "Silenced all the same: what the report is about is a "
               "field NOTHING decided, and this one a title decided, "
               "so the two agreeing is not the report being right. "
               "1.4.0 read title 'Sir', last 'John V'"),
    Case("marker_led_clause_in_a_quote_pair",
         'Jane Smith "née Jones"',
         {"given": "Jane", "family": "Smith", "maiden": "Jones"},
         classification="fix(#335)",
         notes="M3 is keyed on the CONTENT, not on which pair matched, "
               "and this is the row that says so in the commonest "
               "spelling: a quote pair is how nicknames are usually "
               "written, and the same clause inside one reads maiden "
               "exactly as it does inside parentheses. Three of the "
               "eleven shipped nickname pairs are exercised by a "
               "marker-led clause anywhere in the suite -- this one, "
               "the parenthesis, and the fullwidth pair below -- and "
               "the other EIGHT have no row. Measured 2026-08-26 by "
               "disabling the swap one pair at a time: those three "
               "redden and the eight do not. That is a count over a "
               "wordlist, so read it the way "
               "mechanisms.md#VOCABULARY-EXERCISES-FORKS says to: the "
               "eight are not eight gaps, since the pairs fork on "
               "whether open and close are the same character and on "
               "the apostrophe carve-out inside that, not on which "
               "pair. This row is here because a quote pair is the "
               "same-character branch, and because the release note "
               "advertises the spelling. 1.4.0 and 2.1.0 both read "
               "nickname 'née Jones'"),
    Case("maiden_marked_clause_takes_the_suffix_reading_from_s1",
         "Jane Smith (née Jr.)",
         {"given": "Jane", "middle": "Smith", "family": "née",
          "suffix": "Jr."},
         notes="S1 takes a suffix-shaped clause before M3 is "
               "consulted, and the whole reading is here because the "
               "surprising part is not the suffix: it is that the "
               "MARKER becomes the family name. S1 drops the brackets "
               "and lets the content read as if written bare, and "
               "bare 'Jane Smith née Jr.' has no name word after the "
               "marker for M2 to take, so 'née' stays an ordinary "
               "word and lands in the family. rules.md#M3 carries the "
               "same input as an example line, but the runner checks "
               "one field per line; this row is the other three. "
               "Parity, and unchanged by #335 -- 1.4.0 and 2.1.0 read "
               "it the same way, which is why the corpus row it added "
               "diffs against no baseline"),
    Case("maiden_marked_clause_beside_a_nickname",
         'Jane "Janey" Smith (née Jones)',
         {"given": "Jane", "family": "Smith", "nickname": "Janey",
          "maiden": "Jones"},
         classification="fix(#335)",
         notes="two clauses, two roles. Through 2.1 both were "
               "nicknames and the facade joined them into one value, "
               "'Janey née Jones' -- the merged-nickname half of #335"),
    Case("maiden_marker_delimited_unmarked_content",
         "Jane Smith (Mary Jones)",
         {"given": "Jane", "family": "Smith", "maiden": "Mary Jones"},
         policy=Policy(maiden_delimiters=frozenset({("(", ")")})),
         classification="parity",
         notes="the row the rest of the #329 battery leaves out: a "
               "multi-token clause whose first token is NOT a marker, "
               "which keeps every one of its tokens. The clause-size "
               "test and the marker-tag test are separate conditions, "
               "and this shape is one of the two that separates them "
               "-- with the tag test removed the pass eats the opening "
               "word of every delimited maiden name ('Jones' here), "
               "and five tests go red across this row and "
               "maiden_marker_delimited_trailing_marker (measured "
               "2026-08-03). What is this row's alone is that NO token "
               "in its clause is a marker; the trailing-marker row has "
               "one, just not first. Measured against "
               "1.4.0 2026-08-03 through the bucket-move idiom "
               "maiden_delimiters['parenthesis'] = "
               "nickname_delimiters.pop('parenthesis'): first Jane / "
               "last Smith / maiden 'Mary Jones', so #329 leaves this "
               "input exactly where v1 had it"),
    Case("maiden_marker_delimited_three_token_clause",
         "Jane Smith (née Mary Jones)",
         {"given": "Jane", "family": "Smith", "maiden": "Mary Jones"},
         policy=Policy(maiden_delimiters=frozenset({("(", ")")})),
         classification="fix(#329)",
         notes="the only clause in the battery holding THREE tokens, "
               "which is what bounds the drop in both directions: it "
               "takes the marker and stops. Every other delimited row "
               "has a two-token clause, where 'the first token' and "
               "'all but the last token' agree, so two opposite "
               "mistakes both survive them -- restricting the drop to "
               "a clause of exactly two tokens gives maiden 'née Mary "
               "Jones' here (marker never dropped), and letting it eat "
               "the token after the marker gives maiden 'Jones' "
               "(a name eaten). Both measured 2026-08-03. 1.4.0 under "
               "the bucket-move idiom "
               "maiden_delimiters['parenthesis'] = "
               "nickname_delimiters.pop('parenthesis') gave first Jane "
               "/ last Smith / maiden 'née Mary Jones' (2026-08-03) -- "
               "marker inside the value, the single field #329 moves"),
    Case("maiden_marker_delimited_trailing_marker",
         "Jane Smith (Jones née)",
         {"given": "Jane", "family": "Smith", "maiden": "Jones née"},
         policy=Policy(maiden_delimiters=frozenset({("(", ")")})),
         classification="parity",
         notes="the drop takes the clause's FIRST token or nothing: a "
               "marker anywhere else in the clause is content. Pinned "
               "because the cheap generalization -- drop every marker "
               "in the clause -- passes the whole battery above and "
               "gives maiden 'Jones' here, and because no marker the "
               "shipped vocabulary carries is written after the name "
               "it marks. Measured against 1.4.0 2026-08-03 "
               "through the bucket-move idiom: first Jane / last "
               "Smith / maiden 'Jones née'"),
    Case("maiden_marker_delimited_beside_a_nickname_clause",
         'Jane "née Janie" Smith {née Jones}',
         {"given": "Jane", "family": "Smith", "maiden": "Janie Jones"},
         policy=Policy(maiden_delimiters=frozenset({("{", "}")})),
         classification="fix(#335)",
         notes="#335 took this row's job away, and the row is kept to "
               "record that. It was the pin for the #329 drop pass "
               "being scoped to MAIDEN clauses -- two extracted "
               "clauses, both opening with a marker word, only the "
               "maiden one losing it, nickname 'née Janie' and maiden "
               "'Jones'. M3 now reads the QUOTED clause as maiden too, "
               "since it is marker-led like the braced one and M3 is "
               "keyed on content rather than on which pair matched, so "
               "there is no nickname left to contrast: both clauses "
               "are maiden and M1's independence rule joins them into "
               "one value. The role filter it used to discriminate "
               "(the 'role is not Role.MAIDEN' branch of "
               "_group.group's drop pass) is still reachable and "
               "still pinned -- "
               "that job moved to "
               "marker_glued_to_punctuation_keeps_the_clause_a_nickname "
               "below, which reaches a marker-led clause M3 declines. "
               "1.4.0 cannot express a brace delimiter at "
               "all (its buckets hold the NAMES of compiled regexes "
               "and there is no brace one; measured 2026-08-03, "
               "maiden_delimiters['brace'] = ('{', '}') is accepted "
               "and then raises ValueError('references unknown "
               "regexes key') at parse time), so the "
               "classification compares against its single reading, "
               "first Jane / middle 'Smith {née' / last 'Jones}' / "
               "nickname 'née Janie' -- braces as name text, the same "
               "convention maiden_marker_kyusei_delimited uses for a "
               "knob with no v1 spelling (re-measured 2026-08-26, "
               "unchanged)"),
    Case("marker_glued_to_punctuation_keeps_the_clause_a_nickname",
         'Jane "née, Janie" Smith (née Jones)',
         {"given": "Jane", "family": "Smith", "nickname": "née Janie",
          "maiden": "Jones"},
         classification="fix(#335)",
         notes="M3 and the #329 drop pass ask the marker question of "
               "different things, and this row is where the two "
               "answers differ. M3 splits the clause on WHITESPACE and "
               "normalizes the first word: 'née,' normalizes to "
               "'née,' -- _normalize strips a trailing period but not "
               "a comma -- so M3 declines and the quoted clause stays "
               "a nickname. tokenize splits the comma off as a "
               "separator, so the clause's first TOKEN is 'née' and "
               "carries vocab:maiden-marker, which is exactly what "
               "the 'role is not Role.MAIDEN' branch of "
               "_group.group's drop pass exists to refuse. Measured 2026-08-26: with that "
               "branch removed this reads nickname 'Janie', the "
               "marker dropped out of a nickname. BOTH clauses are "
               "load-bearing -- the drop pass is gated on the name "
               "holding a MAIDEN region at all, so the same quoted "
               "clause alone ('Jane \"née, Janie\" Smith') leaves the "
               "branch unexercised, removing it measurably changes "
               "nothing there. The paren clause is what opens the "
               "block, and M3 is what makes it maiden. The comma is "
               "absent from the nickname VALUE because tokenize "
               "treats COMMA_CHARS as a separator inside every region "
               "including an extracted one, which predates #335 and "
               "is not part of it. 1.4.0 gave first Jane / last Smith "
               "/ nickname 'née, Janie née Jones' (2026-08-26) -- "
               "comma kept, both clauses merged into the one field, "
               "which is the merged-nickname half of #335"),
    Case("maiden_marker_delimited_two_clauses",
         "Jane Smith (Nee) (Jones)",
         {"given": "Jane", "family": "Smith", "maiden": "Nee Jones"},
         policy=Policy(maiden_delimiters=frozenset({("(", ")")})),
         classification="parity",
         notes="the scoping pin for #329, and the row a simplification "
               "would break: the drop is CLAUSE-scoped, so a one-token "
               "clause keeps its token even when the next clause could "
               "read as the name it marks. A neighbour-scoped rule -- "
               "drop a marker whose successor is also maiden -- gives "
               "'Jones' here, eating a real surname (Irish Ní/Nee, and "
               "a Chinese romanization). Unaccented 'nee' is in the "
               "default MAIDEN_MARKERS, so the 'Nee' token really is "
               "tagged and the CLAUSE bound is the only thing keeping "
               "it -- which is what makes this row kill a rule that "
               "drops the bound. The VALUE does not depend on that "
               "vocabulary entry, though: the clause test is checked "
               "before the tag test, so 'nee' leaving MAIDEN_MARKERS "
               "would leave this expectation green. "
               "maiden_marker_delimited_unaccented above is the row "
               "that fails when it goes. "
               "Parity is measured, not inferred from the row being "
               "untouched: 1.4.0 under the same bucket move gave first "
               "Jane / last Smith / maiden 'Nee Jones' (2026-08-02), "
               "so the two clauses joined with a space on that side "
               "too -- the classification the facade runner checks "
               "against, since it expresses this policy through the "
               "same bucket move"),
    Case("maiden_marker_delimited_content_free", "(née —)",
         {},
         policy=Policy(maiden_delimiters=frozenset({("(", ")")})),
         classification="fix(#329)",
         notes="the drop can empty the WHOLE parse, and that is a "
               "decision rather than fallout. assemble's content test "
               "runs over the SURVIVING tokens, so once the marker "
               "goes structural the em dash is the only one left, no "
               "alnum character remains and every field clears -- "
               "bool() False. Reachable only where a maiden clause is "
               "the entire input and its non-marker tokens are pure "
               "punctuation -- the same clause inside a name is "
               "maiden_marker_delimited_content_free_in_a_name below. "
               "Coherent with the model 2.0 "
               "already had: a dropped marker is structural like a "
               "delimiter character, and '(-)' empties on both sides "
               "of this change. Structurally unreachable on the bare "
               "#274 path, whose scan starts at piece 1, so a token "
               "always survives ahead of the marker ('née —' gives "
               "given 'née', family '—'). Do NOT restore the old value "
               "with a guard on what else the clause holds: that is a "
               "different rule, and it would leave maiden holding "
               "marker-plus-punctuation. fix rather than parity "
               "because 1.4.0 CAN express this policy and disagrees: "
               "measured 2026-08-03 through the bucket-move idiom "
               "maiden_delimiters['parenthesis'] = "
               "nickname_delimiters.pop('parenthesis'), it gave maiden "
               "'née —' and a truthy name, as pre-#329 did. The 2.0 "
               "content rule already deviated from 1.4.0 here ('(-)' "
               "is maiden '-' in 1.4.0); this change moves one more "
               "input into its reach"),
    Case("maiden_marker_delimited_content_free_in_a_name",
         "Jane Smith (née —)",
         {"given": "Jane", "family": "Smith", "maiden": "—"},
         policy=Policy(maiden_delimiters=frozenset({("(", ")")})),
         classification="fix(#329)",
         notes="the row above with a name in front of the clause, "
               "which is what bounds the emptying: assemble's content "
               "test is about the WHOLE parse, so a clause of "
               "marker-plus-punctuation empties only a name that is "
               "nothing else. Here Jane Smith carries the alnum "
               "content and maiden keeps the em dash. Pinned because "
               "the drop could plausibly have been widened to take the "
               "clause's punctuation with the marker -- that mutation "
               "gives maiden '' here (measured 2026-08-03) and leaves "
               "the row above green, since both readings empty a parse "
               "that is only the clause. 1.4.0 under the bucket-move "
               "idiom gave first Jane / last Smith / maiden 'née —' "
               "(2026-08-03)"),
    Case("maiden_marker_kyusei_delimited", "山田 花子（旧姓 佐藤）",
         {"given": "花子", "family": "山田", "maiden": "佐藤"},
         policy=Policy(
             maiden_delimiters=frozenset({("(", ")"), ("（", "）")})),
         classification="fix(#329)",
         notes="the Japanese bracketed form that #329 reaches: the "
               "marker is spaced off inside fullwidth brackets, so it "
               "is a token of its own and the clause-scoped drop "
               "applies. The form Japanese more often writes puts a "
               "fullwidth colon after the marker instead, and "
               "'山田（旧姓：佐藤）' is ONE token -- nothing reaches it, "
               "and it wants the head-peel #317 tracks (see "
               "maiden_marker_kyusei above). Unlike its two Latin "
               "siblings, 1.4.0 cannot express this policy at all: v1's "
               "delimiter buckets hold the NAMES of compiled regexes, "
               "and no fullwidth pair is among them (#273 added it), so "
               "maiden_delimiters['fullwidth_parenthesis'] = ('（', '）') "
               "raises ValueError('references unknown regexes key') at "
               "parse time. The classification therefore compares "
               "against 1.4.0's single reading, first 山田 / middle "
               "'花子（旧姓' / last '佐藤）' -- the brackets were name "
               "text -- the same convention "
               "ko_honorific_period_under_strict_comma_suffixes uses "
               "for a knob with no v1 spelling. That reading is also "
               "what the differential harness sees, since it runs the "
               "corpus under the DEFAULT policy. What the harness does "
               "with it changed in 2.2: through 2.1 the （） pair was a "
               "#273 NICKNAME delimiter and nothing in #329 was "
               "reachable, so the diff classified under "
               "fix(cjk-fullwidth-paren-nickname). Since #335 the marker "
               "inside the clause is enough on its own, so this name "
               "reads maiden under the default policy too -- see "
               "maiden_marked_fullwidth_clause_by_default below -- and "
               "the diff classifies under fix(#335) at 2.1.0 and 2.0.0 "
               "while at 1.4.0 it moved to fix(cjk-maiden-marker), "
               "leaving the fullwidth-paren rule dormant in that ledger. "
               "This row keeps its policy because M1 still governs a "
               "configured pair and settles the role before M3 is "
               "consulted"),
    Case("maiden_marked_fullwidth_clause_by_default",
         "山田 花子（旧姓 佐藤）",
         {"given": "花子", "family": "山田", "maiden": "佐藤"},
         classification="feat(#273) + fix(#271) + fix(#335)",
         notes="the row above without its policy, and the one "
               "that fences M3 across the delimiter SET rather "
               "than at the parenthesis. Measured 2026-08-26 by "
               "gating the swap to '(' and the double quote: this row "
               "and its facade twin are the only two failures in the "
               "suite, and of the gates only 1.4.0 and 2.0.0 redden "
               "-- 2.1.0 stays green with its fix(#335) rule quietly "
               "falling from six names to five, while the 2.0.0 "
               "ledger catches it on the four-field rule it gives "
               "this name. The fullwidth pair is the "
               "one the maiden_markers docstring and the 2.2 "
               "release note both advertise as newly working "
               "without configuration, so it is the one that "
               "most needs a row. Three changes compound in the "
               "classification: #273 taught the parser the "
               "fullwidth pair, #271 gives the wholly-Han "
               "remainder its family-first reading, and #335 "
               "makes the marker inside the clause enough on its "
               "own. 1.4.0 read first 山田 / middle '花子（旧姓' / "
               "last '佐藤）' with the brackets as name text; "
               "2.1.0 read given 花子 / family 山田 / nickname "
               "'旧姓 佐藤' (both measured 2026-08-26)"),
    Case("east_slavic", "Сидоров Иван Петрович",
         {"given": "Иван", "middle": "Петрович", "family": "Сидоров"},
         policy=_ES),
    Case("turkic", "Mammadova Aygun Ali kizi",
         {"given": "Aygun", "middle": "Ali kizi", "family": "Mammadova"},
         policy=_TK),
    Case("ru_pack_formal_rotation", "Сидоров Иван Петрович",
         {"given": "Иван", "middle": "Петрович", "family": "Сидоров"},
         locale="ru",
         notes="the RU pack end-to-end: same expectation as the "
               "east_slavic synthetic row, through parser_for"),
    Case("ru_pack_transliterated", "Petrov Ivan Sergeyevich",
         {"given": "Ivan", "middle": "Sergeyevich", "family": "Petrov"},
         locale="ru"),
    Case("ru_pack_comma_untouched", "Петров, Иван",
         {"given": "Иван", "family": "Петров"},
         locale="ru",
         notes="a comma is an explicit signal that suppresses the "
               "rotation (rule O1)"),
    Case("tr_az_pack_marker", "Mammadova Aygun Ali kizi",
         {"given": "Aygun", "middle": "Ali kizi", "family": "Mammadova"},
         locale="tr_az",
         notes="the TR_AZ pack end-to-end: same expectation as the "
               "turkic synthetic row (pinned live during Plan 3), "
               "through parser_for"),
    Case("empty", "", {}),
    Case("whitespace", "   ", {}),
    Case("bare_ambiguous_acronym", "John Ed",
         {"given": "John", "family": "Ed"},
         ambiguities=("suffix-or-name",),
         notes="'ed' is an ambiguous acronym; bare form is a name (C1), "
               "and the parse reports which reading it took"),
    # MOVED by #289, not deleted (roles unchanged, a report gained):
    # 'Ed' is Title-case in a mixed-case name, so it leans SURNAME and
    # the post-comma slot declines it exactly as before -- but the
    # decision is now reported, both directions of the fork being
    # worth telling the caller about (decisions.md#S2).
    Case("comma_ambiguous_acronym", "Smith, Ed",
         {"given": "Ed", "family": "Smith"},
         ambiguities=("suffix-or-name",)),
    # Quality-review finding, 2026-09-17 (item 5): name_word_count's
    # title half used a bare `folded in lexicon.titles` lookup, not
    # is_leading_title's H2 shape test -- so an UNLISTED period-marked
    # opener counted as a NAME word where a LISTED one did not, and
    # this pair split on that alone: 'Dr. Smith, Ed' (LISTED 'Dr.')
    # read family 'Dr. Smith' unflipped, but 'Xyz. Smith, Ed'
    # (UNLISTED, H2-shaped) flipped the comma structure and read title
    # 'Xyz.', family 'Smith', suffix 'Ed' -- a different STRUCTURE for
    # the same shape, from a title-vocabulary difference the count had
    # no business seeing. Fixed by sharing H2's shape test
    # (`_vocab.is_title_shaped`, asked in this count and inlined in
    # `_pieces.is_leading_title`, two spellings of one predicate --
    # sharing the function costs a frame on the hot leading-peel path,
    # measured, so they stay separate call sites instead).
    Case("comma_count_reads_h2_s_shape_test_too", "Xyz. Smith, Ed",
         {"given": "Ed", "family": "Xyz. Smith"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="MOVED: title 'Xyz.', family 'Smith', suffix 'Ed' before "
               "this fix (measured at e545803) -- an unlisted period-"
               "marked opener now reads the way a listed title does at "
               "this count, exactly as 'Dr. Smith, Ed' beside it"),
    Case("ambiguous_acronym_with_suffix", "John Ed III",
         {"given": "John", "family": "Ed", "suffix": "III"},
         ambiguities=("suffix-or-name",)),
    Case("phd_split", "John Ph. D.",
         {"given": "John", "suffix": "Ph. D."},
         ambiguities=("given-or-family",),
         notes="v1 fix_phd; healed via the stable 'joined' tag. Roles "
               "parity; the flag is #449's -- a split credential beside "
               "the lone word decides the field no more than a whole "
               "one does"),
    Case("phd_split_mid_name", "Dr. John Ph. D. Smith",
         {"title": "Dr.", "given": "John", "family": "Smith",
          "suffix": "Ph. D."}),
    Case("phd_split_leading_van_johnson", "Ph. D. Van Johnson",
         {"title": "Ph.", "given": "D.", "family": "Van Johnson"},
         classification="parity",
         notes="#371's own subject: the leading pair read given "
               "'Van Johnson' with an EMPTY family until the merge "
               "learned to decline at the head of the input. A Case "
               "row rather than a rules.md line because the empty "
               "fields are the symptom -- test_case asserts the whole "
               "dict, so `suffix` and `middle` being empty is pinned "
               "here and nowhere else"),
    Case("phd_split_leading_bare", "Ph. D.",
         {"title": "Ph.", "family": "D."},
         classification="parity",
         notes="a bare credential yields a family name, which is "
               "surprising and is 1.4.0's reading exactly. Pinned "
               "because nothing else in the suite says so -- the "
               "ledger reaches it, and the ledger is an out-of-band "
               "tool run"),
    Case("phd_split_leading", "Ph. D. John Smith",
         {"title": "Ph.", "given": "D.", "middle": "John",
          "family": "Smith"},
         classification="parity",
         notes="v1's fix_phd regex required a preceding space, so it "
               "split them (title 'Ph.', given 'D.', real given name "
               "pushed to middle). Surfaced by the issue-tracker "
               "corpus, which is where this shape existed at all."),
    Case("leading_never_given_particle", "de la Vega",
         {"family": "de la Vega"},
         notes="v1 handle_non_first_name_prefix: never-given leading "
               "particle folds the whole name into family"),
    Case("unbalanced_quote", 'Jon "Nick Smith',
         {"given": "Jon", "middle": '"Nick', "family": "Smith"},
         ambiguities=("unbalanced-delimiter",),
         notes="quote char stays literal (rule N2)"),
    Case("suffix_stays_suffix", "Johnson PhD",
         {"given": "Johnson", "suffix": "PhD"},
         classification="fix(suffix-routing)",
         ambiguities=("given-or-family",),
         notes="v1 routes a lone trailing suffix to family "
               "(first=Johnson last=PhD); v2 keeps recognized "
               "suffixes in suffix -- which leaves 'Johnson' the one "
               "name word O5's convention places, reported since "
               "#449. Roles parity; the flag is #449's"),
    Case("suffix_stays_suffix_title", "Mr. Johnson PhD",
         {"title": "Mr.", "family": "Johnson", "suffix": "PhD"},
         classification="fix(#410)",
         notes="two fixes meet here. v1 routed a lone trailing suffix "
               "to family (title 'Mr.', first 'Johnson', last 'PhD') "
               "and v2 keeps recognized suffixes in `suffix` "
               "(fix(suffix-routing)); that left 'Johnson' in `given` "
               "with an empty family until #410 stopped counting the "
               "suffix as a further name word"),
    Case("family_comma_lone_title", "Smith, Dr.",
         {"title": "Dr.", "family": "Smith"},
         classification="fix(comma-family)",
         notes="pre-comma is definitionally family; v1 put it in first"),
    Case("family_comma_all_title_segment_keeps_split", "John Smith, Mr.",
         {"title": "Mr.", "given": "John", "family": "Smith"},
         classification="fix(comma-family)",
         notes="a comma followed only by titles said nothing about "
               "where the family name ends, so segment 0 keeps its "
               "positional read instead of merging into one family "
               "name (v1 read first 'John Smith'; 2.0 read it as the "
               "family, the comma-precomma-family move)"),
    Case("family_comma_all_title_segment_needs_two_pieces", "Smith, Dr.",
         {"title": "Dr.", "family": "Smith"},
         classification="fix(comma-family)",
         notes="the guard on family_comma_all_title_segment_keeps_split: "
               "one pre-comma piece has no split to keep, and the "
               "positional read would make it a lone GIVEN"),
    Case("family_comma_untitled_segment_still_merges", "John Smith, Jones",
         {"given": "Jones", "family": "John Smith"},
         notes="the non-flip: a post-comma NAME means the comma did fix "
               "the family, so segment 0 stays wholly family (v1 parity)"),
    # -- #296: the TITLES/suffix overlap audit. A word that is only ever
    # a postnominal leaves TITLES, so the title peel stops claiming it
    # first. Leading position is the price and is pinned here.
    Case("audit_phd_leading_is_a_name", "PhD Smith",
         {"given": "PhD", "family": "Smith"},
         classification="fix(#296)",
         notes="'phd' left TITLES because M.D./Ph.D. are postnominal "
               "only; nothing is prenominal-'PhD', so the leading "
               "position falls through to the positional read"),
    Case("audit_jr_leading_is_a_name", "Jr Smith",
         {"given": "Jr", "family": "Smith"},
         classification="fix(#296)",
         notes="same as audit_phd_leading_is_a_name: 'jr' is never "
               "prenominal in any tradition"),
    Case("audit_md_leading_stays_a_title", "Md Abdul Karim",
         {"title": "Md", "given": "Abdul", "family": "Karim"},
         notes="the one word the 2026-07-30 table got wrong: 'md' KEEPS "
               "dual membership. Bare 'Md' before a name is the "
               "Bengali and South Asian Muslim abbreviation of "
               "Muhammad (#343/#345's corpus rows), a prenominal use "
               "the 'postnominal only' disposition did not consider; "
               "'MD' after the name is the degree. Position decides, "
               "as for 'sr'. The shape-1 tag rides on that disposition "
               "-- 'md' is the ONE deviation from the approved "
               "2026-07-30 audit table (decisions.md#comma-suffix-arc, "
               "where #291 is still unshipped), so if the deviation is "
               "ever reversed this row stops being a Title Given "
               "Family arrangement and the tag has to move to another "
               "row rather than the expectations being edited under it",
         shape=1),
    Case("audit_md_after_comma_is_the_degree", "Smith, MD",
         {"family": "Smith", "suffix": "MD"},
         classification="fix(#296)",
         notes="the third leg of 'position decides' for 'md'"),
    # -- #346: the renunciate class. A title of religious renunciation
    # addresses the GIVEN name AND belongs to a tradition that
    # abolishes the surname, so rules.md#H1's given-name-title fold is
    # the right reading and family="" is the right output. The two
    # criteria are separate (rules.md#H Background) and the control
    # row below is what keeps them separate.
    Case("renunciate_title_keeps_the_given_name", "Swami Vivekananda",
         {"title": "Swami", "given": "Vivekananda"},
         classification="fix(#346)",
         notes="pins the #346 membership change the ledger "
               "classifies: 'swami' moved from the TITLES-only block "
               "into GIVEN_NAME_TITLES, so H1's fold fires and the "
               "family is empty where 1.4.0 through 2.2.0 read family "
               "'Vivekananda'. The fold itself is already pinned by "
               "the Sir John rows; this is the name the release note "
               "advertises"),
    Case("surname_retaining_title_keeps_the_family",
         "Rabbi Cohen",
         {"title": "Rabbi", "family": "Cohen"},
         notes="makes rules.md#H Background's 'Rabbi Cohen' sentence "
               "executable -- no other row parses a Rabbi. 'rabbi' "
               "addresses by title and the tradition keeps surnames, "
               "so it stays out of GIVEN_NAME_TITLES and H1 families "
               "the one name word. The control that keeps 'addresses "
               "by the given name' and 'has no surname' separate"),
    Case("renunciate_title_with_a_trailing_honorific",
         "Lama Zopa Rinpoche",
         {"title": "Lama", "given": "Zopa", "suffix": "Rinpoche"},
         classification="feat(#346)",
         notes="the renunciate fold and the spaced trailing honorific "
               "together. 'rinpoche' is postpositional in Tibetan "
               "usage ('Sogyal Rinpoche'), so it is SUFFIX_WORDS "
               "vocabulary rather than a title; that takes the third "
               "word out of the name and leaves H1 exactly one given "
               "to fold, which is why the family is empty. Without "
               "the suffix entry this reads family 'Rinpoche'"
               "; classified feat, not fix -- the fold was already "
               "pinned by the Swami row, and this row's delta is the "
               "rinpoche entry"),
    Case("renunciate_title_with_two_name_words_keeps_the_family",
         "Swami Vivekananda Saraswati",
         {"title": "Swami", "given": "Vivekananda",
          "family": "Saraswati"},
         notes="H1's fold requires exactly one name word. The ledger "
               "carries this name as a _MUST_NOT_MATCH probe, which "
               "pins the regex and not the parse -- and it is "
               "radar-tier in corpus_issues.jsonl, so the gate cannot "
               "fail on it either. The release note advertises it"),
    Case("renunciate_title_swallows_a_real_given_name", "Guru Dutt",
         {"title": "Guru", "given": "Dutt"},
         classification="fix(#346)",
         notes="the known Latin collision: Guru IS the filmmaker's "
               "given name. 'guru' was already a title, so the "
               "leading-position swallow predates #346; the promotion "
               "into GIVEN_NAME_TITLES is what moved 'Dutt' from "
               "family to given. Accepted as the pre-existing cost of "
               "'guru' being a title at all "
               "(decisions.md#indic-honorifics); TITLES has no "
               "ambiguous subset to say otherwise"),
    Case("audit_do_leading_is_a_name", "Do Nguyen",
         {"given": "Do", "family": "Nguyen"},
         ambiguities=("particle-or-given",),
         classification="fix(#296)",
         notes="the disposition's own argument, realized: 'Do' is a "
               "Vietnamese name, and dropping the title membership is "
               "what lets it be read as one -- with the fork 'Van "
               "Johnson' reports, since 'do' is an ambiguous particle "
               "too and the title membership had been hiding the fork"),
    Case("audit_se_leading_is_a_name", "SE Smith",
         {"given": "SE", "family": "Smith"},
         classification="fix(#296)",
         notes="Structural Engineer is a US licensure postnominal (the "
               "PE/SE pair); no prenominal SE convention exists"),
    Case("audit_junior_leading_is_a_name", "Junior Smith",
         {"given": "Junior", "family": "Smith"},
         classification="fix(#296)",
         notes="and 'Junior' is a real given name besides"),
    # the non-flips: trailing position was already right and must stay
    Case("audit_phd_trailing_unchanged", "John Smith PhD",
         {"given": "John", "family": "Smith", "suffix": "PhD"}),
    Case("audit_jr_trailing_unchanged", "John Smith Jr.",
         {"given": "John", "family": "Smith", "suffix": "Jr."},
         notes="shape 1's trailing Suffix slot, written without a "
               "comma",
         shape=1),
    Case("audit_lt_leading_stays_a_title", "Lt. Smith",
         {"title": "Lt.", "family": "Smith"},
         notes="'lt' KEPT its dual membership -- a prenominal rank with "
               "real retired-designation postnominal use; position "
               "decides, so leading is untouched"),
    Case("audit_sr_leading_stays_a_title", "Sr. Garcia",
         {"title": "Sr.", "family": "Garcia"},
         notes="Señor (leading) vs Senior (trailing): kept dual, and "
               "the leading read is the peel's normal path"),
    Case("audit_sra_leading_stays_a_title", "Sra Garcia",
         {"title": "Sra", "family": "Garcia"},
         notes="Señora is title-only; the SUFFIX_ACRONYMS entry was v1 "
               "residue and is what got dropped, not this"),
    Case("audit_dr_leading_stays_a_title", "Dr. Smith",
         {"title": "Dr.", "family": "Smith"}),
    Case("audit_dr_after_comma_is_a_title", "Smith, Dr.",
         {"title": "Dr.", "family": "Smith"},
         classification="fix(comma-family)",
         notes="'dr' left SUFFIX_WORDS: 'Dr.' is not a postnominal in "
               "any tradition and the entry was v1 residue. This is "
               "what keeps the postnominal reading of a lone post-comma "
               "suffix piece from taking it -- the vocabulary decides, "
               "not the position"),
    Case("audit_dr_after_two_word_comma_keeps_the_split", "John Smith, Dr.",
         {"title": "Dr.", "given": "John", "family": "Smith"},
         classification="fix(comma-family)",
         notes="with 'dr' gone from the suffix sets the post-comma word "
               "is a title only, so the no-name-word repair keeps the "
               "pre-comma split. v1, and 2.0 through master, kept the "
               "same split by a different route -- 'dr' was "
               "suffix-tagged, making this a SUFFIX_COMMA -- but put "
               "'Dr.' in suffix, not title: a change against every "
               "baseline"),
    Case("audit_sra_after_comma_is_a_title", "Smith, Sra",
         {"title": "Sra", "family": "Smith"},
         classification="fix(comma-family)",
         notes="the same removal on the acronym side"),
    Case("audit_ms_after_comma_is_the_degree", "Smith, MS",
         {"family": "Smith", "suffix": "MS"},
         classification="fix(#296)",
         notes="'ms' is a genuine dual -- 'Ms.' leading, 'MS' the "
               "degree trailing -- and position decides. The 2026-07-30 "
               "table put it in the AMBIGUOUS set so bare 'MS' would "
               "read as the honorific; measured, that gate is "
               "position-blind: 'John Smith, MS' lost its suffix-comma "
               "route and read title 'MS', and 'Smith, Ms.' passed the "
               "gate on its one period anyway. The second deviation "
               "from the table, with 'md'"),
    Case("audit_ms_after_two_word_comma_is_the_degree", "John Smith, MS",
         {"given": "John", "family": "Smith", "suffix": "MS"},
         notes="the common listing, unchanged at every baseline -- "
               "what the ambiguous gate would have cost"),
    Case("audit_ms_leading_is_the_honorific", "Ms. Smith",
         {"title": "Ms.", "family": "Smith"}),
    Case("audit_perioded_ms_is_the_degree", "Smith, M.S.",
         {"family": "Smith", "suffix": "M.S."}),
    Case("audit_ms_honorific_spelling_after_comma_is_the_postnominal",
         "Smith, Ms.",
         {"family": "Smith", "suffix": "Ms."},
         classification="fix(#296)",
         notes="the cost of the dual, recorded: after a family comma "
               "the slot is postnominal and the vocabulary says suffix, "
               "whatever the period suggests -- as for 'Smith, Sr.'. "
               "Every baseline read title 'Ms.' (the design-docs "
               "review found the flip unrecorded). 'Smith, Ms. Jane' "
               "still reads the title: a name word follows"),
    Case("audit_ms_before_a_name_after_comma_is_the_title",
         "Smith, Ms. Jane",
         {"title": "Ms.", "given": "Jane", "family": "Smith"}),
    Case("audit_sa_after_comma_is_the_postnominal", "Smith, SA",
         {"family": "Smith", "suffix": "SA"},
         classification="fix(#296)",
         notes="the same dual: Special Agent leading, the business "
               "form trailing"),
    Case("audit_perioded_sa_is_the_postnominal", "Smith, S.A.",
         {"family": "Smith", "suffix": "S.A."}),
    # MOVED by #289, not deleted: 'DO' is written in capitals inside a
    # mixed-case name, so it now leans CREDENTIAL and the post-comma
    # slot takes it with one word to spare rather than falling to the
    # given position (decisions.md#S2).
    Case("audit_bare_caps_do_after_comma_is_a_credential", "Smith, DO",
         {"family": "Smith", "suffix": "DO"},
         classification="fix(#289)",
         ambiguities=("suffix-or-name",),
         notes="'do' left TITLES but was already AMBIGUOUS; the period "
               "gate handles the real collision, which is that 'Do' is "
               "a name -- but the bare, all-caps spelling is now read "
               "the way a credential is written"),
    Case("audit_perioded_do_after_comma_is_a_suffix", "Smith, D.O.",
         {"family": "Smith", "suffix": "D.O."}),
    # -- the TRAILING half of the same two removals. `dr` and `sra` are
    # the ONLY audit words that lose SUFFIX membership; every other
    # audit word keeps its suffix membership, so trailing position is
    # untouched for them.
    Case("audit_dr_trailing_is_a_title", "John Smith Dr.",
         {"title": "Dr.", "given": "John", "family": "Smith"},
         classification="fix(#316)",
         notes="'dr' left SUFFIX_WORDS, so a trailing 'Dr.' stopped "
               "being suffix vocabulary and fell to the positional "
               "read, taking the family name with it -- the reading "
               "every other title-only word already had, which this "
               "row recorded 'dr' JOINING rather than endorsing. #316 "
               "answers the class, so it leaves that reading with "
               "them: the trailing walk takes the word to the title "
               "and 'Smith' is the family again"),
    Case("audit_sra_trailing_joins_the_title_word_gap", "John Smith Sra",
         {"given": "John", "middle": "Smith", "family": "Sra"},
         classification="fix(#296)",
         notes="the same move for the other word losing suffix "
               "membership -- and, since #316, the pair's contrast: "
               "'Dr.' wears the period the trailing walk reads and has "
               "gone to the title, 'Sra' bare wears no shape at all "
               "and a bare trailing title word is a name word"),
    Case("family_comma_lone_generational_suffix", "Smith, Jr.",
         {"family": "Smith", "suffix": "Jr."},
         classification="fix(#296)",
         notes="the issue as filed: the peel's whole-segment exception "
               "claimed 'Jr.' through the period-abbreviation inference "
               "even after the audit, so the ordering change is what "
               "actually reaches this input"),
    Case("family_comma_lone_generational_suffix_bare", "Smith, Jr",
         {"family": "Smith", "suffix": "Jr"},
         classification="fix(#296)"),
    Case("family_comma_lone_degree", "Smith, PhD",
         {"family": "Smith", "suffix": "PhD"},
         classification="fix(#296)"),
    Case("family_comma_dual_word_reads_postnominal", "Smith, Sr.",
         {"family": "Smith", "suffix": "Sr."},
         classification="fix(#296)",
         notes="Señor vs Senior: 'sr' keeps both memberships and this "
               "is the position that picks Senior"),
    Case("family_comma_dual_rank_reads_postnominal", "Smith, CPT",
         {"family": "Smith", "suffix": "CPT"},
         classification="fix(#296)",
         notes="the retired-designation reading of a prenominal rank"),
    Case("family_comma_lone_esquire_is_the_postnominal", "Smith, Esq.",
         {"family": "Smith", "suffix": "Esq."},
         classification="fix(#296)",
         notes="H2's period-abbreviation inference reads a LEADING "
               "'Esq.' as a title ('Esq. Smith'); after a family comma "
               "the slot is postnominal and the vocabulary says "
               "suffix, so the inference does not run"),
    # -- #325: the whole credential run, not the lone piece
    Case("family_comma_split_credential_run", "Smith, Ph. D. Jr.",
         {"family": "Smith", "suffix": "Ph. D. Jr."},
         classification="fix(#325) + fix(#429)",
         notes="one word before the comma, the space-split 'Ph. D.' "
               "and a suffix after it: the lone-piece route did not "
               "apply and the merged credential fell through to the "
               "given name (a 1.4.0 regression -- v1 read suffix 'Ph. "
               "D.', title 'Jr.'). A run that is nothing but suffix "
               "pieces is the credential run C1 describes, whole -- "
               "and #429 made it render whole too, where #325 shipped "
               "it as 'Ph. D., Jr.' with a comma the writer never "
               "typed. The full-name 'John Smith, Ph. D. Jr.' rendered "
               "it unjoined at 2.0.0 and after -- 1.4.0 rendered "
               "'Ph. D., Jr.' there too -- so this row now agrees with "
               "the form it has agreed with since 2.0"),
    Case("family_comma_credential_run_then_numeral", "Smith, Ph. D. III",
         {"family": "Smith", "suffix": "Ph. D. III"},
         classification="fix(#325) + fix(#429)",
         notes="the numeral does not end the run; the render lost its "
               "inserted comma with the rest (#429)"),
    Case("family_comma_two_credentials", "Smith, PhD Jr.",
         {"family": "Smith", "suffix": "PhD Jr."},
         classification="fix(#325) + fix(#429)",
         notes="'PhD' led the run as a title until the audit; the audit "
               "alone would have made it the given name, which is why "
               "the ordering shipped in the same commit. The run is "
               "suffixes, and since #429 renders as one entry rather "
               "than 'PhD, Jr.'"),
    Case("family_comma_title_led_credential_run", "Smith, Dr. MD PhD",
         {"title": "Dr.", "family": "Smith", "suffix": "MD PhD"},
         classification="fix(#429)",
         notes="the title-led run: assign routes Dr. to TITLE and the "
               "two credentials to SUFFIX, so the ENTRY is the "
               "credential run, not the whole segment. 384 inputs of "
               "this shape moved with #429 and none was pinned until "
               "the review said so"),
    Case("family_comma_title_between_credentials", "Smith, MD Dr. PhD",
         {"title": "Dr.", "family": "Smith", "suffix": "MD PhD"},
         classification="fix(#429)",
         notes="the entry is sticky across a piece that is not in it: "
               "an interleaved title must not split the run it sits "
               "in, or the render inserts the very comma #429 removes"),
    Case("family_comma_nickname_between_credentials",
         'Smith, MD "Doc" PhD',
         {"family": "Smith", "nickname": "Doc", "suffix": "MD PhD"},
         classification="fix(#436/#437)",
         notes="the transparency above is not a TITLE rule: a nickname "
               "renders into `nickname`, so it is no more standing in "
               "the credential run than a title is, and the writer "
               "typed no comma between MD and PhD. 'MD, PhD' at every "
               "baseline, and still 'MD, PhD' on #436's first draft, "
               "which read only a title as transparent"),
    Case("family_comma_title_led_run_keeps_the_written_comma",
         "Smith Jr., Mr. Jr.",
         {"title": "Mr.", "family": "Smith", "suffix": "Jr., Jr."},
         notes="THE #429 REGRESSION GUARD, and unchanged since 1.4.0. "
               "The pre-comma name leaves a suffix, and the segment "
               "after the comma is title-led. #429's first draft let "
               "the title piece OPEN the entry, so the following Jr. "
               "was tagged as a continuation and the view joined it "
               "backward across the writer's own comma -- suffix "
               "'Jr. Jr.', the exact inverse of the bug #429 fixes. "
               "Only a piece that renders into the same run may "
               "continue an entry"),
    Case("family_comma_written_commas_are_kept", "Smith, MD, PhD",
         {"family": "Smith", "suffix": "MD, PhD"},
         notes="the negative control for #429, and the distinction the "
               "whole change rests on: the parser renders the run as "
               "the writer spaced it, and never stops emitting a comma "
               "the writer typed. Parity at every baseline"),
    Case("family_comma_run_matches_the_full_name_form", "John Smith, MD PhD",
         {"given": "John", "family": "Smith", "suffix": "MD PhD"},
         notes="the full-name twin of family_comma_suffix_run_renders_"
               "unjoined, and the reference #429 brought the one-word "
               "form into line with. Unchanged since 1.4.0, so this row "
               "fails if a future change fixes one form by breaking the "
               "other"),
    Case("no_comma_suffix_run_renders_unjoined", "John Smith MD PhD",
         {"given": "John", "family": "Smith", "suffix": "MD PhD"},
         classification="fix(#436/#437)",
         notes="the NO-COMMA path #429 recorded as left alone, and "
               "the rules.md#R1 example line. 'MD, PhD' at 1.4.0, "
               "2.0.0, 2.1.0 and 2.2.0 alike -- a comma the writer "
               "never typed -- because the entry boundary was derived "
               "from segment SHAPE and this string has no comma to "
               "shape a segment with. It reads the same as the "
               "comma-written 'John Smith, MD PhD' above, which is "
               "what makes str() of that parse round-trip"),
    Case("family_comma_segment_zero_is_not_the_run", "MD PhD Jr., John",
         {"given": "John", "family": "MD", "suffix": "PhD Jr."},
         classification="fix(#436/#437)",
         notes="segment 0 is the family segment even when it is wholly "
               "credential-shaped, so 'MD' is the FAMILY and not the "
               "head of a credential run, and that is what this row "
               "still guards. The SEPARATOR is no longer the row's "
               "subject. Until #436 it was: the join was asked of "
               "segment 1 alone, and dropping that conjunct left the "
               "whole suite green while this shape's suffix silently "
               "became 'PhD Jr.' (the mutation matrix found it). The "
               "conjunct is gone with the block, and 'PhD Jr.' is now "
               "the right answer for a different reason -- PhD and "
               "Jr. share a comma bucket with nothing between them, "
               "so they render as the writer spaced them"),
    Case("family_comma_run_ending_in_a_numeral", "Smith, PSM I",
         {"family": "Smith", "suffix": "PSM I"},
         classification="fix(#430)",
         notes="the credential run does not end because its last word "
               "is a roman numeral: PSM I is Professional Scrum Master "
               "level I, and the numeral describes the credential "
               "rather than the person's generation. The run read as "
               "given 'PSM' + suffix 'I' because the initial veto in "
               "is_suffix_piece keeps a numeral out of a credential "
               "run, so the segment did not look like one"),
    Case("family_comma_run_numeral_ignores_the_period", "Smith, PSM I.",
         {"family": "Smith", "suffix": "PSM I."},
         classification="fix(#430)",
         notes="and the period does not end it either. After a suffix "
               "word the numeral is describing that suffix, and an "
               "initial in that position is not a name shape anyone "
               "writes -- so the abbreviation reading that governs "
               "#432 does not reach here. The full-name 'John Smith, "
               "PSM I.' has read it this way all along"),
    Case("family_comma_run_numeral_after_a_dual_word", "Smith, MD I",
         {"family": "Smith", "suffix": "MD I"},
         classification="fix(#430)",
         notes="the same shape reached through the leading-title peel "
               "instead: md is TITLES vocabulary too (the #296 "
               "deviation), so this read title 'MD' + given 'I' where "
               "'Smith, PSM I' read given 'PSM' + suffix 'I'. Two "
               "wrong answers, one cause -- a fix verified on PSM "
               "alone would leave this one broken and look green. "
               "'Smith, Jr. I' is the same story by the other route, "
               "reaching the peel through the period-abbreviation "
               "inference rather than TITLES membership, and is the "
               "spelling a writer actually produces; it had a row of "
               "its own until the mutation matrix showed the two trace "
               "identically once fixed -- both heads are suffix pieces "
               "now, so is_leading_title is never consulted for either"),
    Case("family_comma_numeral_after_a_name_is_an_initial",
         "Smith, John V.",
         {"given": "John", "middle": "V.", "family": "Smith"},
         classification="fix(#432)",
         notes="the other half of the boundary: after a NAME word the "
               "period is decisive, because it marks an abbreviation "
               "and an abbreviation is name material. 'Smith, John B.' "
               "has always read middle 'B.'; the only thing that made "
               "V. different is that V is also suffix vocabulary"),
    Case("family_comma_bare_numeral_after_a_name_is_the_suffix",
         "Smith, John V",
         {"given": "John", "family": "Smith", "suffix": "V"},
         notes="THE BOUNDARY, and v1 parity (#144): with no period "
               "there is no abbreviation, so the numeral is the "
               "generation it looks like. This row is what makes "
               "#432's fix a period test rather than a numeral test"),
    Case("family_comma_title_resets_the_credential_run", "Smith, PSM Dr. I",
         {"title": "Dr.", "given": "PSM", "family": "Smith",
          "suffix": "I"},
         classification="fix(#316)",
         notes="THE RESET. A title ends the run: what follows a bare "
               "title is not continuing a credential, so the numeral "
               "behind it does not join and the segment is no run at "
               "all. Removing that one line leaves the whole suite "
               "green while this becomes title 'Dr.' + suffix 'PSM "
               "I' -- the reset fires across the suite and until this "
               "row no input observed it, which is the "
               "inert-measurement shape. Since #316 the word it "
               "resets ON is a title here rather than a middle name: "
               "'I' is what this segment reads as its suffix, so "
               "'Dr.' is the trailing piece and the walk takes it. "
               "Transparency does NOT reach this row, and that is the "
               "reset itself: 'Smith, PSM I' reads suffix 'PSM I' "
               "with no given name at all (measured 2026-09-09), "
               "because with no title between them the numeral "
               "CONTINUES the credential run. Removing the title "
               "removes the reset, so the shorter spelling is a "
               "different reading and not this one minus a word. "
               "1.4.0 read suffix 'Dr., I' -- 'dr' was still "
               "postnominal vocabulary before #296's audit, so the "
               "row's old parity claim had outlived it"),
    Case("family_comma_run_numeral_after_a_split_credential",
         "Smith, Ph. D. I",
         {"family": "Smith", "suffix": "Ph. D. I"},
         classification="fix(#430)",
         notes="the numeral continues a run whose head is a MERGED "
               "piece -- the Ph./D. pair the #325 split-credential "
               "merge builds, which carries 'suffix' in its piece tags "
               "rather than on a single token. A structurally different "
               "pin on the same readers as the PSM rows, so an edit to "
               "those cannot quietly unpin this. #430 counted three of "
               "them; since #436 the render join is a rule over the "
               "written commas in post_rules, and the two that still "
               "share segment_suffix_reading are assign's gate and "
               "assign's router"),
    Case("family_comma_numeral_behind_a_suffix_is_not_an_initial",
         "Smith, John PhD I.",
         {"given": "John", "family": "Smith", "suffix": "PhD I."},
         notes="THE OTHER BOUNDARY. "
               "The period makes a numeral name material only behind a NAME "
               "word; behind a suffix the run owns it, and the first "
               "draft of #432 read the piece alone and made this middle "
               "'I.'. Rendered without a comma since #436: the "
               "boundary is the comma the writer typed, and this "
               "writer typed none between PhD and I. -- the walk "
               "still decides the ROLES, which is what this row is "
               "about, and no longer decides the separator"),
    Case("family_comma_strict_keeps_the_initial_veto",
         "Smith, PSM I.",
         {"given": "PSM", "family": "Smith", "suffix": "I."},
         policy=Policy(lenient_comma_suffixes=False),
         notes="C1's strict knob still vetoes initial-shaped words, so "
               "the run ends at the numeral where lenient continues "
               "through it. #430's first draft read no policy at all "
               "and silently overrode the one knob a caller sets to "
               "prevent exactly this; nothing in the suite saw it"),
    Case("family_comma_run_with_a_name_is_not_a_run", "Smith, John Jr.",
         {"given": "John", "family": "Smith", "suffix": "Jr."},
         notes="the non-flip: a name word in the run makes it the "
               "given-and-suffix walk v1 had. Shape 2's trailing "
               "suffix with the optional comma OMITTED; "
               "family_comma_three_part_trailing_strict is the "
               "spelling that writes it",
         shape=2),
    Case("family_comma_title_then_suffix", "Smith, Dr. Jr.",
         {"title": "Dr.", "family": "Smith", "suffix": "Jr."},
         classification="fix(comma-family)",
         notes="a title and a postnominal, each read where it stands "
               "-- the 2.0 deviation's other case (v1 read first "
               "'Jr.'), and what keeps the no-name-word test from "
               "reading 'Dr. Jr.' as one title run"),
    Case("family_comma_title_then_suffix_mr", "Smith, Mr. Jr.",
         {"title": "Mr.", "family": "Smith", "suffix": "Jr."},
         classification="fix(comma-family)"),
    Case("family_comma_title_then_suffix_keeps_the_split",
         "John Smith, Mr. Jr.",
         {"title": "Mr.", "given": "John", "family": "Smith",
          "suffix": "Jr."},
         classification="fix(#296)",
         notes="no name word after the comma, so it fixed no family "
               "boundary -- the same reasoning as 'John Smith, Mr.'; "
               "v1 read first 'Jr.', last 'John Smith', and 2.0 through "
               "master family 'John Smith' (the design-docs review "
               "found C1 silent on the shape)"),
    Case("family_comma_title_run_keeps_the_split", "John Smith, Mr. Dr.",
         {"title": "Mr. Dr.", "given": "John", "family": "Smith"},
         classification="fix(#296)"),
    Case("family_comma_title_run_one_word", "Smith, Mr. Dr.",
         {"title": "Mr. Dr.", "family": "Smith"},
         classification="fix(#296)",
         notes="one pre-comma piece, no split to keep; the run is "
               "titles (master read suffix 'Dr.')"),
    Case("family_comma_three_segments_credential_run", "Smith, Jr., PhD",
         {"family": "Smith", "suffix": "Jr., PhD"},
         classification="fix(#325)",
         notes="segments 2+ compose with the credential run"),
    Case("family_comma_suffixed_family_before_a_title", "Smith Jr., Dr.",
         {"title": "Dr.", "family": "Smith", "suffix": "Jr."},
         classification="fix(#296)",
         notes="two pre-comma pieces but ONE name piece: the positional "
               "read peels the suffix first and would have left a lone "
               "given and no family (the code review found 'Smith Jr., "
               "Mr.' reading so), so the guard counts name pieces and "
               "the family stays. v1 read first 'Smith', last 'Jr.', "
               "suffix 'Dr.'; 2.0 through master family 'Smith', "
               "suffix 'Jr.', title 'Mr.' for the Mr. spelling"),
    Case("family_comma_suffixed_family_before_a_title_mr", "Smith Jr., Mr.",
         {"title": "Mr.", "family": "Smith", "suffix": "Jr."},
         notes="unchanged at every baseline -- the shape the guard "
               "protects"),
    Case("family_comma_suffixed_two_word_family_before_a_title",
         "John Smith Jr., Mr.",
         {"title": "Mr.", "given": "John", "family": "Smith",
          "suffix": "Jr."},
         classification="fix(#296)",
         notes="two name pieces, so the split is kept"),
    # -- the positional read keeps its ORDER, so the family-first fold
    # (P1) reaches a particle-led pre-comma name as it does without
    # the comma (the test review found it reading family 'de')
    Case("family_comma_no_name_word_family_first", "de Mesnil Jean, Dr.",
         {"title": "Dr.", "given": "Jean", "family": "de Mesnil"},
         policy=Policy(name_order=FAMILY_FIRST),
         classification="feat(#395)",
         notes="core-only: name_order has no v1 spelling, so 'parity' "
               "(this field's default) could never have been true of "
               "this row. The differential compares it at 2.0.0 and "
               "2.1.0 under its own order instead, where it moves: "
               "#395's fold takes 'de Mesnil' where both read family "
               "'de', and the #296 half turns the post-comma 'Dr.' "
               "from a suffix into a title. As 'de Mesnil Jean' reads "
               "under the same order; master read it through the "
               "suffix-comma route ('dr' was suffix vocabulary) and "
               "got the fold that way",
         shape=4),
    Case("family_comma_no_name_word_family_first_given_last",
         "de la Cruz Juan Carlos, Dr.",
         {"title": "Dr.", "given": "Carlos", "middle": "Juan",
          "family": "de la Cruz"},
         policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST),
         classification="feat(#395)",
         notes="core-only: name_order has no v1 spelling. The row "
               "above with two leftovers instead of one, which is the "
               "only shape in which the two family-first orders can "
               "disagree about the distribution -- 'Juan' is the "
               "middle name here and the given name there",
         shape=5),
    Case("family_comma_no_name_word_family_first_plain", "John Smith, Dr.",
         {"title": "Dr.", "given": "Smith", "family": "John"},
         policy=Policy(name_order=FAMILY_FIRST),
         classification="fix(#296)",
         notes="core-only: name_order has no v1 spelling, but the "
               "CHANGE here is the vocabulary half alone -- no "
               "particle, so nothing folds, and the diff against 2.0.0 "
               "is the {title, suffix} move 'dr' leaving the suffix "
               "sets produces under every order. The declared order "
               "applies to the pre-comma name as it does to 'John "
               "Smith' alone -- deliberate",
         shape=4),
    Case("title_word_trailing_is_a_title", "John Smith Prof.",
         {"title": "Prof.", "given": "John", "family": "Smith"},
         classification="fix(#316)",
         notes="rules.md#H5 -- after the trailing suffix run, a "
               "period-marked title word chains into the title from "
               "the end. The comma path already read it this way "
               "('Smith, Prof.'); the two paths agree now"),
    Case("ja_honorific_glued_family_comma_title_only", "田中さん, Dr.",
         {"title": "Dr.", "family": "田中さん"},
         classification="fix(#296)",
         notes="Accepted (C1): with 'dr' out of the suffix sets the "
               "comma is a family comma, and the honorific peel runs "
               "in script_segment on the other structures only, before "
               "group or assign can say this comma fixed nothing -- so "
               "the honorific stays glued, joining master's '田中さん, "
               "Mr.'. Master peeled it through the suffix-comma route",
         tolerated=True),
    Case("title_word_trailing_is_a_title_mr", "John Smith Mr.",
         {"title": "Mr.", "given": "John", "family": "Smith"},
         classification="fix(#316)"),

    # -- #316(a): the trailing title RUN. The leading slot has a SHAPE
    # rule that outranks vocabulary (H2); the trailing slot has no
    # shape rule and reads vocabulary only. #316(b), the bare-safe
    # subset ('Smith Dr'), is deliberately out.
    Case("title_word_trailing_run_chains", "John Smith Prof. Dr.",
         {"title": "Prof. Dr.", "given": "John", "family": "Smith"},
         classification="fix(#316)",
         notes="a RUN, mirroring H3 -- one word only would leave "
               "'Prof.' a name word"),
    Case("title_word_trailing_joins_the_leading_run_in_input_order",
         "Dr. John Smith Prof.",
         {"title": "Dr. Prof.", "given": "John", "family": "Smith"},
         classification="fix(#316)",
         notes="the title view joins TITLE tokens in token order, so "
               "leading then trailing needs no rendering change"),
    Case("title_word_trailing_leaves_one_name_word", "Smith Prof.",
         {"title": "Prof.", "family": "Smith"},
         classification="fix(#316)",
         notes="the floor: the walk stops with one name piece "
               "standing, and H1 then names it the family. Nothing is "
               "reported -- the trailing title is a Role.TITLE by the "
               "time the lone-name-word emitter looks, so H1 decided "
               "the field and O5's convention did not, the same answer "
               "'Dr. Smith' gets"),
    Case("title_word_trailing_behind_a_peeled_suffix",
         "John Smith Prof. Jr.",
         {"title": "Prof.", "given": "John", "family": "Smith",
          "suffix": "Jr."}, classification="fix(#316)",
         notes="the suffix peel takes its run first and the title "
               "walk reads what it left"),
    Case("title_word_trailing_ahead_of_a_suffix_word",
         "John Smith Jr. Prof.",
         {"title": "Prof.", "given": "John", "family": "Smith",
          "suffix": "Jr."}, classification="fix(#316)",
         notes="the same reading with the two words swapped, and the "
               "reason the first peel is PROVISIONAL: 'Prof.' stood "
               "behind 'Jr.', so that peel halted there, and the walk "
               "then removed the very word that had stopped it. The "
               "walk's piece is spliced out and one peel runs over "
               "what stands, reading 'Jr.' the suffix it is; a single "
               "pass promoted a generational suffix to the family "
               "name"),
    Case("title_word_trailing_is_transparent_to_the_suffix_peel",
         "John Smith MA Prof.",
         {"title": "Prof.", "given": "John", "family": "Smith",
          "suffix": "MA"}, ambiguities=("suffix-or-name",),
         classification="fix(#316)",
         notes="the principle the two peels serve: 'X Prof. Y' reads "
               "exactly as 'X Y' reads, plus the title. This is "
               "'John Smith MA' -- suffix 'MA', ONE report -- because "
               "the reports come from the single peel over the "
               "spliced pieces. Collecting both peels' picks instead "
               "reported the same coin flip twice"),
    # MOVED by #289, not deleted: spliced, this is 'John MA' plus a
    # title, and 'MA' is written in capitals inside a mixed-case name
    # -- the caps lean now takes it with no words to spare where the
    # old reserve kept it the family (decisions.md#S2).
    Case("title_word_trailing_run_is_read_to_a_fixed_point",
         "John Prof. MA Prof.",
         {"title": "Prof. Prof.", "family": "John", "suffix": "MA"},
         ambiguities=("suffix-or-name",), classification="fix(#316)",
         notes="transparency for a SECOND title, which peel and chain "
               "reading to a FIXED POINT buys and one re-peel did "
               "not: the chain takes the last 'Prof.', the peel over "
               "what is left un-peels 'MA' and re-exposes the first "
               "'Prof.', and only asking the chain again takes it. "
               "Iterating once read title 'Prof.', given 'John', "
               "family 'Prof.', suffix 'MA' -- which is 'John Prof. "
               "MA' plus a title in no reading at all. Found by the "
               "/simplify round on the bundle, 2026-09-09; 1.4.0 read "
               "first 'John' / middle 'Prof. MA' / last 'Prof.' "
               "(measured 2026-09-09), so the row is #316's parity "
               "break either way and the round decided only which "
               "reading it is. #289 moves it again: the caps lean "
               "takes 'MA' as a credential rather than the family "
               "(decisions.md#S2)"),
    Case("title_word_trailing_keeps_the_bare_acronym_reserve",
         "John Prof. MA",
         {"title": "Prof.", "family": "John", "suffix": "MA"},
         ambiguities=("suffix-or-name",), classification="fix(#316)",
         notes="the same principle where the peel's answer DEPENDS on "
               "the spliced list: this is 'John MA' plus a title and "
               "reads exactly as 'Prof. John MA' does. Laying a "
               "second peel's roles over the first peel's read family "
               "'John', suffix 'MA'. #289 MOVES this row: 'MA' is "
               "written in capitals inside a mixed-case name, so the "
               "caps lean now takes it with no words to spare, where "
               "S2's reserve alone used to keep it the family "
               "(decisions.md#S2)"),
    Case("title_word_trailing_between_two_numerals",
         "John Smith V Prof. VI",
         {"title": "Prof.", "given": "John", "middle": "Smith V",
          "family": "VI"}, classification="fix(#316)",
         notes="'John Smith V VI' plus a title, reports and all. The "
               "numeral fork reads the piece BEFORE the numeral, and "
               "over the spliced list that piece is 'V', an initial "
               "shape, so the fork declines and nothing is reported. "
               "Two peels each reporting their own last piece read "
               "suffix 'V VI' and reported the fork twice"),
    Case("title_word_trailing_unlisted_abbreviation_is_a_name_word",
         "John Smith Xyz.",
         {"given": "John", "middle": "Smith", "family": "Xyz."},
         classification="parity",
         notes="negative control, and the doctrine: the leading slot "
               "has a SHAPE rule that outranks vocabulary (H2), the "
               "trailing slot reads vocabulary only",
         shape=1),
    Case("title_word_trailing_bare_is_a_name_word", "John Smith Sir",
         {"given": "John", "middle": "Smith", "family": "Sir"},
         classification="parity",
         notes="negative control: no period, so no claim -- TITLES "
               "holds ordinary surnames and a bare trailing title word "
               "is a name word (#316(b), deliberately out)"),
    Case("title_word_trailing_ordinary_surname_is_a_name_word",
         "Mary Jane King", {"given": "Mary", "middle": "Jane",
                            "family": "King"},
         classification="parity",
         notes="negative control: decisions.md's trailing-position "
               "rule that must NOT be adopted, still not adopted"),
    Case("title_word_trailing_credential_is_a_suffix",
         "John Smith Esq.",
         {"given": "John", "family": "Smith", "suffix": "Esq."},
         classification="parity",
         notes="negative control: the suffix peel runs first, so a "
               "period-marked post-nominal never reaches the walk"),
    Case("title_word_trailing_leading_slot_is_unchanged", "Esq. Smith",
         {"title": "Esq.", "family": "Smith"},
         classification="parity",
         notes="negative control: H2 stays unconditional and S2's 'a "
               "suffix never opens the string' stands (#316 open "
               "question 2 declined)"),
    Case("title_word_trailing_in_a_parenthetical",
         "Andrew Perkins (Mgr.)",
         {"title": "Mgr.", "given": "Andrew", "family": "Perkins"},
         classification="fix(#316)",
         notes="the fifth corpus name the walk reaches, found by "
               "measurement: the trailing period keeps the "
               "parenthetical out of nickname parsing and 'mgr' is "
               "title vocabulary, so the word arrives in the trailing "
               "slot as any other piece would"),
    Case("title_word_trailing_leaves_a_joined_title_unit_standing",
         "John of Prince Prof.",
         {"title": "Prof.", "family": "John of Prince"},
         ambiguities=("title-or-name",), classification="fix(#316)",
         notes="H4's join clause, reached through the trailing walk: "
               "the unit left standing is the one H4 already reports "
               "for on its own ('John of Prince'), and the walk is "
               "what makes it the only one. The single-word half of "
               "H4 cannot be reached this way -- a lone title-"
               "vocabulary word in front of a trailing title is taken "
               "by the LEADING run first ('King Prof.' reads title "
               "'King')"),
    Case("title_word_trailing_after_a_family_comma",
         "Smith, John Prof.",
         {"title": "Prof.", "given": "John", "family": "Smith"},
         classification="fix(#316)",
         notes="the comma path's walk gets the same rule: a name word "
               "in segment 1 keeps the gate from reading the segment "
               "as a credential run, so the trailing title had no "
               "route to 'title' there either. Contrast the no-name "
               "segment ('Smith, Dr.', pinned above as "
               "family_comma_lone_title): that shape routes through "
               "the no-name gate, a different mechanism, untouched"),
    Case("title_word_trailing_after_a_family_comma_run",
         "Smith, John Prof. Dr.",
         {"title": "Prof. Dr.", "given": "John", "family": "Smith"},
         classification="fix(#316)"),
    Case("title_word_trailing_after_a_family_comma_ahead_of_a_suffix",
         "Smith, John Prof. Jr.",
         {"title": "Prof.", "given": "John", "family": "Smith",
          "suffix": "Jr."}, classification="fix(#316)",
         notes="'Smith, John Jr.' plus a title. The walk's candidates "
               "are the pieces this segment does NOT read as a "
               "suffix, which is this path's answer to the peel the "
               "no-comma path runs first, so the walk reaches 'Prof.' "
               "past the postnominal behind it; over every piece it "
               "found no title at all"),
    Case("title_word_trailing_after_a_family_comma_ahead_of_a_numeral",
         "Smith, John Prof. V",
         {"title": "Prof.", "given": "John", "family": "Smith",
          "suffix": "V"}, classification="fix(#316)",
         notes="the same, through the LENIENT tail test (#144) rather "
               "than the strict one: 'V' is what this segment reads "
               "as its suffix, so it is not a candidate either and "
               "'Smith, John Prof. V' is 'Smith, John V' plus a "
               "title. Filtering the candidates on the strict suffix "
               "test alone left this a middle 'Prof.'"),
    Case("title_word_trailing_after_a_family_comma_behind_a_numeral",
         "Smith, John V Prof.",
         {"title": "Prof.", "given": "John", "family": "Smith",
          "suffix": "V"}, classification="fix(#316)",
         notes="the mirror of the row above, and what makes the "
               "lenient test read the pieces as if the title were "
               "absent: the walk took the last piece, so 'V' is where "
               "this segment's name ends and the test applies to it. "
               "Against the segment's literal last piece, 'V' was a "
               "middle initial here and a suffix one word earlier"),
    Case("title_word_trailing_after_a_family_comma_behind_an_initial",
         "Smith, John V. Prof.",
         {"title": "Prof.", "given": "John", "middle": "V.",
          "family": "Smith"}, classification="fix(#316)",
         notes="the boundary of the row above, kept: #432 reads the "
               "period as the abbreviation mark it is, so 'V.' is a "
               "middle initial -- 'Smith, John V.' plus a title"),
    Case("title_word_trailing_ahead_of_a_reserved_acronym",
         "John Smith Prof. MA",
         {"title": "Prof.", "given": "John", "family": "Smith",
          "suffix": "MA"}, ambiguities=("suffix-or-name",),
         classification="fix(#316)",
         notes="'John Smith MA' plus a title, from the other "
               "direction: S2's peel takes the acronym BEFORE the "
               "walk here, so the title is the trailing piece and the "
               "spliced peel reads the same suffix it reads without "
               "it. The comma path parts company here and is left "
               "alone -- after a family comma a bare ambiguous "
               "acronym has been a MIDDLE name since 2.0 ('Smith, "
               "John MA'), so in 'Smith, John Prof. MA' a name word "
               "stands behind 'Prof.' and no title is in trailing "
               "position at all"),
    Case("cjk_trailing_latin_title_keeps_the_script_order",
         "毛 泽东 Dr.",
         {"title": "Dr.", "given": "泽东", "family": "毛"},
         classification="fix(#316)",
         notes="why the walk runs BEFORE the positional read: a Latin "
               "title at the back of a wholly-Han name is the one "
               "piece that would make the piece set look "
               "mixed-script, and a mixed set declines the script "
               "order. Taken first, the pieces the script test sees "
               "are all Han and the Han order stands -- this is "
               "'毛 泽东' plus a title. 1.4.0 read first '毛' / last "
               "'泽东' / suffix 'Dr.' and master family 'Dr.' "
               "(measured 2026-09-09)",
         tolerated=True),
    Case("title_word_trailing_behind_a_bound_given_pair",
         "Prof. abdul rahman Prof.",
         {"title": "Prof. Prof.", "given": "abdul", "family": "rahman"},
         classification="fix(#316)",
         notes="P5's reserve counts the name words assign will leave, "
               "and a trailing title word is not one of them: this is "
               "'Prof. abdul rahman' plus a title, which reads given "
               "'abdul' / family 'rahman' because two name words "
               "alone do not join. Counting the title word as a word "
               "to spare joined the pair and read family 'abdul "
               "rahman' (measured on the bundle's third commit). "
               "1.4.0 read title 'Prof.' / first 'abdul rahman' / "
               "last 'Prof.'"),
    Case("title_word_trailing_behind_a_bound_pair_at_the_peel_reserve",
         "abdul rahman MA Prof.",
         {"title": "Prof.", "given": "abdul", "family": "rahman",
          "suffix": "MA"}, ambiguities=("suffix-or-name",),
         classification="fix(#316)",
         notes="the row above's shape at S2's bare-ambiguous reserve, "
               "which is the one place the reserve's own model of "
               "assign's reading and assign's reading disagreed. This "
               "is 'abdul rahman MA' plus a title, and that reads "
               "given 'abdul' / family 'rahman' / suffix 'MA': the "
               "join declines because peeling the acronym unjoined "
               "and not joined is a suffix reading the join would "
               "change. Modelling the peel and the chain as a "
               "subtraction, the reserve counted 'MA' a name word to "
               "spare here and not without the title, so the join "
               "fired and read given 'abdul rahman', family 'MA'. One "
               "shared reading of the tail is what makes the two "
               "agree -- found by the /simplify round on the bundle, "
               "2026-09-09 (decisions.md#H5). 1.4.0 read first 'abdul "
               "rahman' / middle 'MA' / last 'Prof.' (measured "
               "2026-09-09)"),
    Case("title_word_trailing_behind_a_licensed_bound_pair",
         "Sir abdul rahman Prof.",
         {"title": "Sir Prof.", "given": "abdul rahman"},
         classification="fix(#316)",
         notes="the licensed half of the row above, and transparent "
               "at both ends: the join fires ('sir' asserts a given "
               "name follows) and the joined pair stays the GIVEN "
               "name, which is what 'Sir abdul rahman' reads without "
               "the trailing title. Two fixes were needed and this "
               "row took both. P5's reserve had counted the trailing "
               "title word as a name word to spare, which made the "
               "join fire for the wrong reason; with that corrected "
               "the join is right and the field was still wrong, H1 "
               "reading the TITLE ROLE -- both ends of the name by "
               "then -- as one run keyed 'sir prof', which addresses "
               "by neither word, so the pair became the family. H1 "
               "now asks the LEADING run, and 'Sir John Prof.' "
               "against 'Sir John' is the same movement in one word "
               "(rules.md#H1, both are examples there). 1.4.0 read "
               "title 'Sir' / first 'abdul rahman' / last 'Prof.' "
               "(measured 2026-09-09)"),
    Case("title_word_trailing_behind_a_bound_pair_after_a_comma",
         "Berg, abdul Prof.",
         {"given": "abdul Prof.", "family": "Berg"},
         notes="the recorded GAP in rules.md#H5's P5 clause, pinned "
               "here rather than by an example there so that "
               "recording it does not make it normative. After a "
               "family comma the reserve reads no peel (rules.md#P5), "
               "so the bound join fires over the trailing title word "
               "and takes it into the given name; the trailing walk "
               "never sees it. The comma-less spelling is "
               "transparent -- 'Sir abdul rahman Prof.' above -- and "
               "so is this segment with an ordinary given name, "
               "'Smith, John Prof.' reading title 'Prof.'. PARITY, "
               "which is why it is not a fix row: 1.4.0 read first "
               "'abdul Prof.', last 'Berg' too (measured 2026-09-09). "
               "Tracked as part of #316"),
    Case("title_run_leading_addresses_over_a_trailing_title",
         "Sir John Prof.",
         {"title": "Sir Prof.", "given": "John"},
         classification="fix(#316)",
         notes="rules.md#H1's clause in one word: the run BEFORE the "
               "one name word addresses, so this is 'Sir John' plus a "
               "title and the given name survives the title being "
               "added. Keying every TITLE token as one run gave 'sir "
               "prof', which addresses by neither, and read family "
               "'John'. 1.4.0 read title 'Sir' / first 'John' / last "
               "'Prof.' (measured 2026-09-09)"),
    Case("title_run_leading_addresses_over_a_trailing_given_name_title",
         "Dr. Smith Sir.",
         {"title": "Dr. Sir.", "family": "Smith"},
         classification="fix(#316)",
         notes="the mirror, and the reading the clause's ordering "
               "decides: a trailing given-name title does NOT lift "
               "the leading run's reading, so this is 'Dr. Smith' "
               "plus a title and the family stands. The composite key "
               "'dr sir' matched on 'sir' and read given 'Smith'. "
               "Where NO run stands in front the trailing one does "
               "decide -- 'Smith Sir.' reads given 'Smith', a "
               "rules.md#H1 example unchanged by this. 1.4.0 read "
               "title 'Dr.' / first 'Smith' / last 'Sir.' (measured "
               "2026-09-09)"),
    Case("title_word_trailing_after_a_maiden_take",
         "Mary Smith née Jones Prof.",
         {"given": "Mary", "family": "Smith", "maiden": "Jones Prof."},
         classification="fix(#274)",
         notes="negative control for the trailing walk, and rules.md#"
               "H5's M2 boundary: M2's take runs to the name's end "
               "and the title is inside what it takes, so no title "
               "word is in trailing position at all. Unchanged by "
               "#316/#489 -- master reads the same (measured "
               "2026-09-09). 1.4.0 had no maiden support and read "
               "first 'Mary' / middle 'Smith née Jones' / last "
               "'Prof.'"),
    Case("title_word_trailing_ahead_of_a_maiden_marker",
         "Mary Jones Prof. née Smith",
         {"title": "Prof.", "given": "Mary", "family": "Jones",
          "maiden": "Smith"},
         classification="fix(#316)",
         notes="the mirror: with the marker BEHIND it the title is "
               "the last piece the walk sees, so it is taken and "
               "'Mary Jones née Smith' is what is left. Master read "
               "middle 'Jones' / family 'Prof.'; 1.4.0 read first "
               "'Mary' / middle 'Jones Prof. née' / last 'Smith' "
               "(measured 2026-09-09)"),
    Case("title_word_trailing_in_a_conjunction_unit",
         "John Smith Prof. and Dr.",
         {"given": "John", "middle": "Smith",
          "family": "Prof. and Dr."},
         classification="parity",
         notes="negative control for the ONE-WORD-per-piece gate: the "
               "conjunction merge made 'Prof. and Dr.' one piece, and "
               "the tokens of a joined unit are not each a title "
               "word. The row that PINS that gate -- with it deleted "
               "the walk takes the unit, because the shape test then "
               "runs on the piece's first token and 'Prof.' wears the "
               "period ('John de la Prof.' reads 0 either way; both "
               "measured 2026-09-09 in test_pieces.py)"),
    Case("family_comma_then_a_lone_suffix_word_segment",
         "Smith, John, Prof.",
         {"given": "John", "family": "Smith", "suffix": "Prof."},
         ambiguities=("comma-structure",),
         classification="parity",
         notes="the trailing slot is a segment away: a second comma "
               "makes the last part its own segment, which the tail "
               "consumes as a suffix before any trailing walk reads a "
               "piece -- so 'prof' leaving the suffix vocabulary "
               "(#296) does not reach this shape and 'Smith, John, "
               "Prof.' still reads suffix 'Prof.' where 'Smith, John "
               "Prof.' reads title. Unmoved by this bundle and by "
               "1.4.0 alike (measured 2026-09-09)"),

    # -- #271: script-scoped order + segmentation (amendment 2026-07-27)
    Case("ko_unspaced_default", "김민준",
         {"family": "김", "given": "민준"},
         classification="fix(#271)",
         notes="hangul is unambiguously Korean: census surnames ship "
               "as default vocabulary and HANGUL segmentation is "
               "default-on. Shape 6's bare Family Given arrangement, "
               "written unspaced, the floor the other shape-6 rows "
               "vary from",
         shape=6),
    Case("ko_two_syllable_surname_default", "남궁민수",
         {"family": "남궁", "given": "민수"},
         classification="fix(#271)",
         ambiguities=("segmentation",),
         notes="남 is itself a shipped surname; longest-first takes "
               "남궁 and records the decided fork. Shape 6's Family "
               "slot at two syllables, where the arrangement's own "
               "boundary is what has to be found",
         shape=6),
    Case("ko_bare_two_syllable_surname", "남궁",
         {"family": "남궁"},
         classification="fix(#271)",
         notes="a token that IS a surname never splits by its "
               "shorter prefix (남+궁); whole token takes the script "
               "order's first role; nothing was split, so no fork is "
               "recorded"),
    Case("ko_family_comma_stays_whole", "남궁민수, 지훈",
         {"family": "남궁민수", "given": "지훈"},
         classification="fix(#271)",
         notes="the comma already decided the family: segmentation "
               "is inert under FAMILY_COMMA (comma doctrine -- see "
               "the script_segment stage docstring, which uses this "
               "exact example)",
         tolerated=True),
    Case("ko_family_comma_given_side_stays_whole", "지훈, 남궁민수",
         {"family": "지훈", "given": "남궁민수"},
         notes="the mirror of the row above, and one of "
               "rules.md#W3's comma illustrations: with the "
               "comma naming 지훈 the family, the post-comma side is "
               "given text with no family to find, so 남궁민수 is "
               "not segmented THERE either -- the same inertness "
               "reached from the other side. Added 2026-09-01 with "
               "the W3 demotion: the rules corpus stopped harvesting "
               "W3's examples, and this text lived in no other "
               "corpus, so without a row it would have left the "
               "differential harness entirely rather than moving to "
               "the radar tier. Classification measured for this row "
               "rather than copied from the row above: 1.4.0 gives "
               "first 남궁민수 / last 지훈, field for field what 2.3 "
               "gives, so parity",
         tolerated=True),
    Case("ko_suffix_comma_name_part_splits", "Dr 김민준, Jr.",
         {"title": "Dr", "family": "김", "given": "민준", "suffix": "Jr."},
         classification="fix(#271)",
         notes="the one comma structure where segmentation still "
               "fires: a second word before the comma makes it "
               "SUFFIX_COMMA, and the name part is a full positional "
               "name",
         tolerated=True),
    Case("ko_spaced_family_first_default", "김 민준",
         {"family": "김", "given": "민준"},
         classification="fix(#271)",
         notes="script_orders, no segmentation involved. Shape 6's "
               "Family Given with the space written, the spelling "
               "ko_unspaced_default reaches by segmenting instead",
         shape=6),
    Case("han_spaced_family_first_default", "毛 泽东",
         {"family": "毛", "given": "泽东"},
         classification="fix(#271)",
         notes="Han ORDER is default-safe without knowing zh from ja "
               "(both write family-first natively); only "
               "SEGMENTATION needs the zh opt-in"),
    Case("han_unspaced_unsegmented_default", "毛泽东",
         {"family": "毛泽东"},
         classification="fix(#271)",
         notes="no default Han segmentation: one token, and a lone "
               "wholly-Han token takes the script order's first "
               "role = family"),
    Case("han_unspaced_no_script_orders_reports_the_convention", "毛泽东",
         {"given": "毛泽东"}, policy=Policy(script_orders=()),
         ambiguities=("given-or-family",), classification="feat(#449)",
         notes="core-only: an emptied script table has no v1 spelling, "
               "so 'parity' could never have been true of this row -- "
               "though the ROLES are 1.4.0's, v1 having no script "
               "orders to empty. The positive control for `by_script`: "
               "with nothing resolving the order the same text takes "
               "O4/O5's default read and the convention reports it. "
               "The row below is the same input with the entries in "
               "place and is SILENT, which is the pair"),
    Case("kana_honorific_no_script_orders_reports_the_convention", "さん",
         {"given": "さん"}, policy=Policy(script_orders=()),
         ambiguities=("suffix-or-name",), classification="feat(#491)",
         notes="core-only for the reason given on the Han row above. "
               "The suffix half's positive control, and what makes "
               "rules.md#H4's CJK-honorific silence a `by_script` "
               "scope rather than a claim about the word: empty the "
               "script table and the same lone honorific reaches the "
               "bare-suffix carve-out and reports"),
    Case("han_unspaced_family_first_declared_reports_nothing", "毛泽东",
         {"family": "毛泽东"}, policy=Policy(name_order=FAMILY_FIRST),
         notes="W4 AUTHORED this reading, and a declared family-first "
               "order agreeing with the Han entry is agreement, not "
               "authorship: the script rule resolved the order, so O5's "
               "convention decided nothing and reports nothing (#449). "
               "The one row that would fail if the emitter compared the "
               "order used against the order declared"),
    Case("mixed_script_untouched_by_script_orders", "John 王",
         {"given": "John", "family": "王"},
         notes="effective_script is None for a mixed name: script_orders "
               "declines and the positional default governs. Swept as a "
               "2026-09-01 tolerated candidate and declined for the "
               "reason the kana-stem rows were: the Latin is a name "
               "PART here, not a wrapper around a CJK name"),
    Case("two_han_scripts_untouched_by_script_orders", "毛 김",
         {"given": "毛", "family": "김"},
         notes="two scripts also decline -- the rule is one script, or "
               "the Han/kana repertoire the #272 license covers"),

    Case("zh_unspaced", "毛泽东",
         {"family": "毛", "given": "泽东"},
         locale="zh", classification="fix(#271)"),
    Case("zh_unspaced_two_char", "张伟",
         {"family": "张", "given": "伟"},
         locale="zh", classification="fix(#271)"),
    Case("zh_compound_tie_break", "夏侯惇",
         {"family": "夏侯", "given": "惇"},
         locale="zh", classification="fix(#271)",
         ambiguities=("segmentation",),
         notes="夏 (rank 65) is itself listed, so longest-first "
               "decides a real fork here and records it; most "
               "compounds' first chars are NOT listed"),
    Case("zh_compound_two_char_given", "司马相如",
         {"family": "司马", "given": "相如"},
         locale="zh", classification="fix(#271)"),
    Case("zh_traditional_compound", "諸葛亮",
         {"family": "諸葛", "given": "亮"},
         locale="zh", classification="fix(#271)"),
    Case("zh_no_surname_match", "阿明",
         {"family": "阿明"},
         locale="zh", classification="fix(#271)",
         notes="no surname prefix in the vocabulary: the token stays "
               "whole and takes the script order's first role"),
    Case("zh_japanese_kanji_tradeoff", "高橋一郎",
         {"family": "高", "given": "橋一郎"},
         locale="zh", classification="fix(#271)",
         notes="the RECORDED tradeoff, not a bug: applying the zh "
               "pack declares the data Chinese, so Japanese kanji "
               "names mis-split (高橋 is the real surname). This is "
               "why Han segmentation is opt-in and why the gate "
               "cannot guard it (DEVIATES declares all Han); "
               "Japanese data belongs under locales.JA and its "
               "segmenter instead"),

    # -- #272: the kana license + nakaguro (amendment 2026-07-29).
    # Segmenter-dependent divisions cannot live here (Case has no
    # segmenter field); they are pinned in test_locales.py's
    # integration tests instead.
    Case("ja_kana_spaced_family_first", "高橋 みなみ",
         {"family": "高橋", "given": "みなみ"},
         classification="fix(#272)",
         notes="hiragana identifies Japanese as certainly as hangul "
               "identifies Korean; kana-licensed names read "
               "family-first by default. Shape 6's Family Given with "
               "a kanji family and a hiragana given rather than the "
               "hangul of the Korean rows -- the arrangement is one "
               "shape across the scripts that carry it, and across a "
               "mix of them within one name",
         shape=6),
    Case("ja_kanji_katakana_pieces", "山田 エミ",
         {"family": "山田", "given": "エミ"},
         classification="fix(#272)",
         notes="a kanji piece + a katakana piece cannot be a foreign "
               "transcription (those are katakana-only): native, "
               "licensed"),
    Case("ja_unspaced_unsegmented_default", "高橋みなみ",
         {"family": "高橋みなみ"},
         classification="fix(#272)",
         notes="no segmenter by default: one token, family role via "
               "the kana license"),
    Case("ja_pure_katakana_positional", "マイケル ジャクソン",
         {"given": "マイケル", "family": "ジャクソン"},
         notes="parity row guarding the license's boundary: "
               "pure-katakana is predominantly transcribed foreign "
               "names in original order -- never licensed"),
    Case("ja_nakaguro_divides_the_transcription", "マイケル・ジャクソン",
         {"given": "マイケル", "family": "ジャクソン"},
         classification="fix(#272)",
         notes="the katakana middle dot is the transcription's own "
               "part divider: it separates like whitespace, the "
               "license declines each katakana token, and the "
               "positional default keeps the source-language order. "
               "Shape 7's katakana-transcription half, the arrangement "
               "admitted by the script rather than by the 间隔号",
         shape=7),
    Case("ja_nakaguro_han_takes_the_han_order", "高橋・一郎",
         {"family": "高橋", "given": "一郎"},
         classification="fix(#272)",
         notes="the dot splits; both tokens are pure Han, so the HAN "
               "family-first entry fires -- the katakana row's sibling "
               "through the other outcome"),
    Case("ja_lone_hiragana_takes_family", "みなみ",
         {"family": "みなみ"},
         classification="fix(#272)",
         notes="hiragana earns a script_orders entry in its own right: "
               "a lone token takes the entry's first role"),
    Case("ja_lone_katakana_stays_given", "マイケル",
         {"given": "マイケル"}, ambiguities=("given-or-family",),
         notes="parity: katakana deliberately has no entry, so the "
               "positional default holds -- transcribed foreign names "
               "keep source order. W4 DECLINING is what leaves the "
               "reading to O5's convention, which reports it (#449); "
               "a name whose script order decides it stays silent. "
               "Roles parity; the flag is #449's"),
    Case("ja_iteration_mark_is_han", "佐々木 太郎",
         {"family": "佐々木", "given": "太郎"},
         classification="fix(#272)",
         notes="々 (U+3005, the ideographic iteration mark) repeats "
               "the preceding kanji and is Script=Han under UAX #24, "
               "but sits outside every CJK ideograph BLOCK -- and the "
               "classifier is a block table, so it needs its own "
               "entry to count as Han; without one 佐々木 -- a top-20 "
               "Japanese surname -- would be a mixed-script token and "
               "reverse"),
    Case("ja_shime_mark_is_han", "〆木 太郎",
         {"family": "〆木", "given": "太郎"},
         classification="fix(shime-mark)",
         notes="〆 (U+3006, the shime mark) opens real Japanese "
               "surnames -- 〆木 Shimeki, 〆谷 Shimetani, 〆野 -- but "
               "carries Script=Common under UAX #24; the table counts "
               "it as Han anyway (a deliberate step PAST the Script "
               "property, unlike 々's), else 〆木 is a mixed-script "
               "token and the name reverses"),
    Case("ja_shime_lone_token_takes_family", "〆木太郎",
         {"family": "〆木太郎"},
         classification="fix(shime-mark)",
         notes="wholly-Han lone token under the family-first entry: "
               "the whole token lands in family, unsegmented by "
               "default"),
    Case("ja_shime_with_kana_given", "〆木 ひろ",
         {"family": "〆木", "given": "ひろ"},
         classification="fix(shime-mark)",
         notes="the kana license composes with the widened Han span: "
               "〆木 reads as kanji beside a kana given name"),
    Case("ja_nakaguro_inside_a_nickname",
         "山田 太郎 (マイケル・ジャクソン)",
         {"family": "山田", "given": "太郎",
          "nickname": "マイケル ジャクソン"},
         classification="fix(#272)",
         notes="delimited content tokenizes under the same separator "
               "rules: the dot renders back as a space in the nickname "
               "join -- a decision, not an accident"),
    Case("zh_interpunct_transcription_source_order", "威廉·莎士比亚",
         {"given": "威廉", "family": "莎士比亚"},
         classification="fix(#298)",
         notes="间隔号-divided Han is a transcribed foreign name and "
               "keeps source order -- the B7 is the transcription "
               "marker, playing the role pure katakana plays in the "
               "kana license; it divides only between classified "
               "characters. Shape 7's Given·Family with the 间隔号 "
               "itself written, the divider half of the notation",
         shape=7),
    Case("zh_interpunct_nakaguro_typed_stays_roster", "威廉・莎士比亚",
         {"given": "莎士比亚", "family": "威廉"},
         classification="fix(#272)",
         notes="the SAME transcription typed with the Japanese "
               "nakaguro reads as the dot's own typography says -- a "
               "姓・名 roster pair, family-first (#272) -- because the "
               "nakaguro records nothing (per decisions.md#T3, "
               "codepoint-scoped; only the Chinese B7 marks a "
               "transcription). A limitation row: chosen, not "
               "accidental -- cross-convention input reads by the "
               "convention of the codepoint it was typed with"),
    Case("ja_interpunct_b7_katakana", "マイケル·ジャクソン",
         {"given": "マイケル", "family": "ジャクソン"},
         classification="fix(#298)",
         notes="sloppy-IME B7 between katakana divides like the "
               "nakaguro; katakana was never licensed, so order was "
               "already positional -- the split is the fix"),
    Case("latin_punt_volat_is_name_interior", "Gal·la Marcet",
         {"given": "Gal·la", "family": "Marcet"},
         notes="the Catalan punt volat: U+00B7 with Latin neighbors "
               "is interior to the name, never a divider -- the flank "
               "guard's whole reason"),
    Case("zh_interpunct_suppresses_segmentation", "马丁·路德·金",
         {"given": "马丁", "middle": "路德", "family": "金"},
         locale="zh",
         classification="fix(#298)",
         notes="马 is a listed zh surname, but a 间隔号-divided name "
               "is a transcription: the dot gates segmentation off, "
               "so 马丁 stays whole and the positional read stands"),
    Case("ko_interpunct_transcription_source_order", "마이클·잭슨",
         {"given": "마이클", "family": "잭슨"},
         classification="fix(#298)",
         notes="Korean writes transcribed foreign names with the "
               "interpunct too: the dot suppresses the hangul "
               "family-first entry AND the default segmentation -- 마 "
               "is a listed census surname, and the spaced form "
               "마이클 잭슨 really does mis-split 마|이클 today, so "
               "the dot is what rescues the ko transcription"),
    Case("zh_interpunct_with_suffix_comma", "威廉·莎士比亚, PhD",
         {"given": "威廉", "family": "莎士比亚", "suffix": "PhD"},
         classification="fix(#298)",
         notes="the transcription reading composes with a suffix "
               "comma: the marker is structure-independent",
         tolerated=True),
    Case("zh_interpunct_half_flanked_stays", "王·Smith",
         {"given": "王·Smith"}, ambiguities=("given-or-family",),
         notes="one classified neighbor is not enough: the guard "
               "requires both, so the undivided dot remains part of "
               "the word -- declining, not deciding. Swept as a "
               "2026-09-01 tolerated candidate and declined on the "
               "same boundary as 'John 王': the Latin is a name part, "
               "not a wrapper. T3 declining is what leaves the "
               "reading to O5's convention, which reports it (#449). "
               "Roles parity; the flag is #449's"),
    Case("zh_honorific_suffix_spaced", "王小明 先生",
         {"family": "王小明", "suffix": "先生"},
         classification="fix(#307) + fix(#271)",
         notes="CJK honorifics FOLLOW the name; a spaced 先生 (Mr.) is "
               "a suffix, and recognizing it must come before the "
               "family-first order hands it a role -- unrecognized it "
               "read as the GIVEN name under the 2.1 defaults. NOT "
               "tagged shape 6, though it looks like the Han spelling "
               "of one: no DEFAULT segmenter divides 王小明, so the "
               "fields here are an undivided name plus an honorific "
               "and the arrangement's Given slot is never filled -- "
               "the same reason han_unspaced_unsegmented_default "
               "(毛泽东) carries no tag. The zh pack is what splits "
               "the token (zh_honorific_glued_given), and a pack row "
               "exercises a locale fork rather than an input shape"),
    Case("ko_honorific_ssi", "김민준 씨",
         {"family": "김", "given": "민준", "suffix": "씨"},
         classification="fix(#307) + fix(#271)",
         notes="Korean orthography standardly SPACES 씨, so the "
               "whole-token suffix machinery reaches it; the name "
               "still segments (suffix classification runs after the "
               "script_segment stage, which only ever saw 김민준)"),
    Case("ko_degree_baksa", "김민준 박사",
         {"family": "김", "given": "민준", "suffix": "박사"},
         classification="fix(#307) + fix(#271)",
         notes="박사 (doctorate) is the ko analogue of a trailing "
               "PhD: fix(suffix-routing)'s two-token shape, one "
               "script over"),
    Case("ja_sama_spaced", "田中 太郎 様",
         {"family": "田中", "given": "太郎", "suffix": "様"},
         classification="fix(#307) + fix(#271)",
         notes="the spaced 様 of forms and databases, which whole-token "
               "matching reaches on its own; the glued "
               "mail-addressing form is ja_sama_glued below, reached "
               "by #308's peel instead"),
    Case("ja_san_spaced", "田中 さん",
         {"family": "田中", "suffix": "さん"},
         classification="fix(#308) + fix(#271)",
         notes="the kana honorifics ship as suffix vocabulary so the "
               "glued peel has somewhere to hand its tail; spaced "
               "recognition falls out of the same entry -- until this "
               "change さん read as the given name under the "
               "family-first default"),
    Case("ja_san_glued", "田中さん",
         {"family": "田中", "suffix": "さん"},
         classification="fix(#308) + fix(#271)",
         notes="the everyday glued form, and the one that also "
               "corrupted classification: 田中さん is Han plus "
               "hiragana, so the kana license read the whole string "
               "as a Japanese name. The peel runs before the license "
               "is consulted, so it now sees 田中 alone"),
    Case("ja_honorific_glued_before_a_roman_suffix", "田中さん II",
         {"family": "田中", "suffix": "さん II"},
         classification="fix(#308) + fix(#271)",
         notes="an unrelated trailing suffix does not hide the peel "
               "site: the scan-back steps over II and peels さん off "
               "the token behind it. Half of the pair that pins "
               "_is_post_nominal's use of is_suffix_STRICT -- the "
               "other half is the row below, and swapping in "
               "is_suffix_lenient changes that one and not this one. "
               "The run renders with the space the writer typed "
               "since #436; the comma form '田中さん, 様.' "
               "(ja_honorific_period_does_not_stop_the_peel) keeps "
               "its comma, which is the pair that shows the "
               "separator is read from the text",
         tolerated=True),
    Case("ja_honorific_glued_before_an_initial", "田中さん V.",
         {"given": "田中さん", "family": "V."},
         notes="the strict/lenient discriminator, and the reason "
               "_is_post_nominal reads is_suffix_strict. Bare 'v' is "
               "a suffix word, but 'V.' is an initial and the strict "
               "test vetoes it -- so the scan-back stops HERE rather "
               "than stepping over it, finds no tail on 'V.', and "
               "does not peel. Under is_suffix_lenient it would step "
               "over and give given 田中, middle さん, family 'V.'. "
               "Parity besides: 1.4.0 read this first 田中さん / last "
               "'V.', which is these fields under the 2.0 names. "
               "Classification agrees with what classify does with "
               "the same token downstream -- 'V.' is a middle "
               "initial, not a post-nominal",
         tolerated=True),
    Case("ja_honorific_with_a_period_no_comma", "田中さん 様.",
         {"family": "田中", "suffix": "さん 様."},
         classification="fix(#320)",
         notes="the SPACED form, and the example _vocab.is_initial's "
               "own docstring cites as what #320 cost. Same fields as "
               "the comma row below, reached without a comma: the peel "
               "scans segment 0 either way, and with '様.' no longer "
               "vetoed the scan-back steps over it onto 田中さん and "
               "peels さん. Worth its own row because it is the only "
               "one of the pair where the SCAN-BACK is what #320 "
               "fixes, and since #319 the only one where the PEEL "
               "depends on #320 at all: here '様.' shares the run with "
               "田中さん and has to be stepped over, while the comma "
               "form declines its post-comma run and never looks at "
               "'様.' in the peel. That decline does not carry the "
               "veto over -- is_wholly_suffix asks is_suffix_lenient "
               "under the default policy, which takes '様.' whether "
               "the veto is in place or not (see the row below) -- so "
               "restoring the veto strands さん HERE and nowhere else "
               "in the pair, giving given '田中さん', family '様.'. "
               "(Before #319 the distinction was structural -- "
               "FAMILY_COMMA flattened TWO runs before scanning where "
               "this has one -- which is no longer what separates "
               "them.) 1.4.0 read this first "
               "田中さん / last '様.', which is what 2.0 produced until "
               "#320: parity before, a classified change after. "
               "TOLERATED since 2026-09-05: a trailing ASCII period on "
               "a CJK honorific is a listing artifact no writing "
               "system produces -- the same class as a comma listing "
               "or a Latin credential. The row still pins #320's "
               "mechanism at HEAD; what moves is which corpus file "
               "carries the text. The run renders with the space the "
               "writer typed since #436; the comma form "
               "'田中さん, 様.' below keeps its comma, which is the "
               "pair that shows the separator is read from the text",
         tolerated=True),
    Case("ja_honorific_period_does_not_stop_the_peel", "田中さん, 様.",
         {"family": "田中", "suffix": "さん, 様."},
         classification="fix(#320)",
         notes="the comma spelling of the row above, and since #319 a "
               "DIFFERENT dependence on #320. At #320 this row was "
               "about the peel: the veto made _is_suffix_strict say "
               "no of '様.', so the #312 scan-back stopped AT it as "
               "the site, found no listed tail there and abandoned, "
               "leaving さん glued to 田中 over one period. #319 then "
               "declined the post-comma run outright, and what is "
               "left here for #320 to fix is the ASSIGNMENT -- with "
               "the veto restored the peel still fires (family 田中, "
               "suffix さん) and only '様.' moves, to given. The "
               "fields and the classification are unchanged either "
               "way. CORRECTION, recorded here because commit "
               "4aff219's message claims otherwise and cannot be "
               "amended: the veto does NOT reach is_wholly_suffix "
               "under this row's DEFAULT policy, so it is not true "
               "that #319 merely handed the same veto to a different "
               "predicate. is_wholly_suffix selects is_suffix_lenient "
               "there, whose contract is suffix_words accepted "
               "unconditionally, BYPASSING the initial veto, and "
               "_normalize('様.') is '様', a suffix word -- so "
               "is_wholly_suffix(['様.']) is True veto or no veto, "
               "the run is declined either way, and simulating the "
               "veto PEELS さん here rather than stranding it. The "
               "is_wholly_suffix route to an abandoned peel exists "
               "only under Policy(lenient_comma_suffixes=False), "
               "which drops the call to is_suffix_strict and gives "
               "family '田中さん', given '様.'; this row does not set "
               "that knob, and "
               "ko_honorific_period_under_strict_comma_suffixes is "
               "the table's row for it. Was the "
               "shape of "
               "ja_honorific_glued_before_an_initial above, except "
               "that here the token stopping the scan is a real "
               "honorific rather than an initial, which is what makes "
               "it a bug rather than the intended veto. The structure "
               "is FAMILY_COMMA throughout -- SUFFIX_COMMA needs more "
               "than one word ahead of the comma and 田中さん is one -- "
               "so at #320 both runs were in the peel's reach and "
               "only the strict test's answer moved. "
               "1.4.0 read "
               "this first '様.' / last 田中さん, which is exactly what "
               "2.0 produced before this change -- the row sat at "
               "parity until #320 moved it",
         tolerated=True),
    Case("ja_sama_glued", "山田太郎様",
         {"family": "山田太郎", "suffix": "様"},
         classification="fix(#308) + fix(#271)",
         notes="the mail-addressing form. Undivided without a "
               "segmenter -- no surname list divides a kanji name -- "
               "so the family name is the whole 山田太郎; "
               "tests/v2/test_locales.py pins the divided twin under "
               "locales.JA"),
    Case("ko_honorific_nim_glued", "김민준님",
         {"family": "김", "given": "민준", "suffix": "님"},
         classification="fix(#308) + fix(#271)",
         notes="the online/formal glued address form, 씨's twin"),
    Case("ko_honorific_written_with_a_period", "김민준, 씨.",
         {"family": "김민준", "suffix": "씨."},
         classification="fix(#320)",
         notes="the period-written form of ko_honorific_after_comma "
               "('김민준, 씨'), whose field ASSIGNMENT it must match "
               "and before #320 did not -- same roles, the suffix "
               "VALUE differing by the period it was written with. "
               "_normalize strips the trailing period, "
               "so the vocabulary sees 씨 either way -- the initial "
               "veto was the only thing rejecting the written form, "
               "and literally the veto: is_suffix_piece is "
               "'vocab:suffix' in tags and 'initial' not in tags, and "
               "'씨.' carried both, so the suffix-shaped piece went to "
               "the given. 1.4.0 read this first '씨.' / last 김민준 -- "
               "the same fields 2.0 gave before this change, so the row "
               "was at parity and #320 is what moves it",
         tolerated=True),
    Case("ko_honorific_period_under_strict_comma_suffixes", "김민준, 씨.",
         {"family": "김민준", "suffix": "씨."},
         policy=Policy(lenient_comma_suffixes=False),
         classification="fix(#320)",
         notes="the row above under the knob that governs exactly this "
               "shape, and one of the table's three exercises of it "
               "(ja_honorific_glued_family_comma_strict_knob is the "
               "second, on the initial-shaped side of the same gap; "
               "ja_honorific_glued_family_comma_credential_pair_strict_"
               "knob is the third, showing where the knob changes "
               "nothing). "
               "lenient_comma_suffixes=False drops segment's post-comma "
               "test to the strict one, so a 'Family, Suffix' input "
               "whose suffix is INITIAL-SHAPED reads as a given-name "
               "initial instead ('John Smith, V' -> given 'V'). '씨.' "
               "is a single character plus a period, so it was in that "
               "class by shape, and before #320 the knob decided it: "
               "given '씨.' / family 김민준. It is out of the class now, "
               "and the honorific parses identically under both "
               "settings -- which is the claim this row exists to "
               "hold, since the knob's own documentation scopes it to "
               "the initial-shaped suffix words ('John Smith, V') and "
               "_script_segment names it as the setting that keeps a "
               "glued honorific inside the name in a neighbouring "
               "shape ('田中さん, V.' gives family '田中さん' under "
               "it). No v1 spelling exists for the knob "
               "(the facade runner skips this row), so the "
               "classification compares against 1.4.0's single "
               "reading, first '씨.' / last 김민준 -- the same fields "
               "2.0 gave under EITHER setting before this change",
         tolerated=True),
    Case("ko_honorific_with_a_period_no_comma", "김민준 씨.",
         {"given": "민준", "family": "김", "suffix": "씨."},
         classification="fix(#320)",
         notes="the period-written ko_honorific_ssi ('김민준 씨'), and "
               "#320 by a different route than the row above: the veto "
               "left '씨.' a NAME piece, and effective_script('씨.') is "
               "None because the trailing period defeats the "
               "wholly-one-script test, so script_orders declined for "
               "the whole name and the three pieces fell back to "
               "name_order -- given 김, middle 민준, family '씨.'. "
               "Hangul segmentation is NOT what moves: it divides "
               "김민준 identically either way, and only the order the "
               "pieces are read in changes. 1.4.0 read this first "
               "김민준 / last '씨.' -- undivided, no suffix. The only "
               "row of the three that already differed from 1.4.0 "
               "before this change, but it differed as given 김 / "
               "middle 민준 / family '씨.'; the fields above are #320's, "
               "not the segmenter's, so the row is classified to it -- "
               "as ko_honorific_ssi is classified to #307 without "
               "naming the same segmentation it also depends on. "
               "TOLERATED since 2026-09-05 with its two period twins: "
               "a trailing ASCII period on a CJK honorific is a "
               "listing artifact no writing system produces. The row "
               "still pins #320's mechanism at HEAD",
         tolerated=True),
    Case("ko_honorific_with_a_fullwidth_full_stop", "김민준 씨．",
         {"family": "김", "given": "민준", "suffix": "씨．"},
         classification="fix(#322)",
         notes="U+FF0E, the stop a Japanese or Chinese IME produces by "
               "default. The lookup fold reads it as an edge period "
               "(_lexicon.FULL_STOPS), so 씨． reaches the suffix entry "
               "the ASCII spelling already reached; the token text "
               "keeps its stop. Pins the fold on the one stop NFKC "
               "would ALSO have folded -- the row beside it pins the "
               "one it would not -- and earns its place as a member "
               "of a set the library SHIPS, which "
               "mechanisms.md#VOCABULARY-EXERCISES-FORKS says is "
               "caller-visible behavior wanting a row per member, "
               "unlike caller-configured vocabulary. 2.2.0 read given "
               "김, middle 민준, family 씨．.",
         tolerated=True),
    Case("ko_honorific_with_an_ideographic_full_stop", "김민준 씨。",
         {"family": "김", "given": "민준", "suffix": "씨。"},
         classification="fix(#322)",
         notes="U+3002, which NFKC leaves alone -- the row that shows "
               "the stop SET is what fixes #322, not a Unicode "
               "normalization. 2.2.0 read given 김, middle 민준, "
               "family 씨。.",
         tolerated=True),
    Case("ko_honorific_with_a_halfwidth_ideographic_full_stop",
         "김민준 씨｡",
         {"family": "김", "given": "민준", "suffix": "씨｡"},
         classification="fix(#322)",
         notes="U+FF61, which NFKC folds to U+3002 and no further -- "
               "so even under NFKC this spelling needs the set. 2.2.0 "
               "read given 김, middle 민준, family 씨｡.",
         tolerated=True),
    Case("ko_honorific_written_nfd_after_a_family_comma",
         unicodedata.normalize("NFD", "김민준, 씨."),
         {"family": unicodedata.normalize("NFD", "김민준"),
          "suffix": unicodedata.normalize("NFD", "씨.")},
         classification="fix(#322)",
         notes="the lookup fold composes NFC, so decomposed 씨. reaches "
               "the suffix entry (2.2.0 read title 씨.). The family "
               "stays WHOLE and stays NFD: segmentation matches raw "
               "text on purpose (decisions.md#W1, 2026-07-29 ja "
               "amendment), so NFD degrades to no-split, never to a "
               "wrong split, and no "
               "token text is rewritten. Contrast 'NFD(田中さん, 様.)', "
               "which matched before: Han does not decompose. NEITHER "
               "tolerated NOR shape-tagged, deliberately: this table's "
               "_has_cjk reads raw codepoints (jamo sit outside "
               "_SCRIPT_RANGES), so a decomposed text is not CJK to the "
               "purity gate and reaches no corpus; the row is a HEAD "
               "pin only."),
    Case("latin_title_written_nfd_is_still_a_title",
         unicodedata.normalize("NFD", "Señor Juan Garcia"),
         {"title": unicodedata.normalize("NFD", "Señor"),
          "given": "Juan", "family": "Garcia"},
         classification="fix(#322)",
         notes="the Latin side of the NFC fork: the lookup fold "
               "composes every non-ASCII word, not hangul alone, so a "
               "decomposed spelling of a shipped diacritic entry "
               "(señor, née, attaché) reaches it. 2.2.0 read given "
               "Señor, middle Juan, family Garcia. The token keeps its "
               "NFD text; only the lookup composes."),
    Case("ko_leading_honorific_surname_with_a_period_keeps_the_given_name",
         "양. 지훈",
         {"family": "양.", "given": "지훈"},
         classification="fix(#323)",
         notes="the issue's own input. effective_script('양.') is "
               "HANGUL once the classification fold drops the edge "
               "stop, so the surname site lands on 양. -- which is "
               "post-nominal vocabulary in the LEADING position, "
               "which _is_post_nominal's docstring says the surname "
               "site reads as an ANSWER rather than a token to step "
               "past -- and declines, leaving 지훈 whole. The stop "
               "stays on the token: nothing rewrites text (rules.md T "
               "Background). 2.2.0 read given 양., middle 지, family "
               "훈.",
         tolerated=True),
    Case("ko_leading_family_name_with_a_period_keeps_the_given_name",
         "김. 민준",
         {"family": "김.", "given": "민준"},
         classification="fix(#323)",
         notes="the non-honorific twin of the row above, and the row "
               "that decides between #323's two candidate fixes: "
               "consulting is_suffix_strict at the surname site would "
               "have rescued 양. and left this one cut (김 is no "
               "suffix), so the fix is the classification fold. The "
               "site lands on 김. and matches on its CORE: 김 is itself "
               "a listed surname, so nothing splits and the stop stays "
               "on the family name (matched on the raw text, 김 was a "
               "listed HEAD and the stop was the remainder, cutting "
               "김 + '.'). 2.2.0 read given 김., middle 민, "
               "family 준.",
         tolerated=True),
    Case("ko_trailing_period_keeps_the_family_first_order", "양 지훈.",
         {"family": "양", "given": "지훈."},
         classification="fix(#323)",
         notes="the ORDER reader of the same None: assign's script "
               "walk returns the declared order the moment one piece "
               "has no script, so a stop on the LAST token flipped "
               "the name to given-first. rules.md#W4's family-first "
               "reading survives the stop now. 2.2.0 read given 양, "
               "family 지훈..",
         tolerated=True),
    Case("ko_glued_honorific_with_a_period_peels", "김민준씨.",
         {"family": "김", "given": "민준", "suffix": "씨."},
         classification="fix(#323)",
         notes="the W3 reading that was pinned by nothing (measured "
               "2026-09-05 as title 김민준씨.): the peel now matches "
               "its tail through the trailing stop and cuts before it, "
               "so this divides exactly as '김민준 씨.' does and the "
               "stop stays on the honorific. Peel first, then the "
               "surname site divides 김민준. 2.2.0 read title 김민준씨.",
         tolerated=True),
    Case("ja_glued_honorific_with_a_period_peels", "田中さん.",
         {"family": "田中", "suffix": "さん."},
         classification="fix(#323)",
         notes="the Japanese twin, and the one where nothing follows "
               "the peel: 田中 is a lone Han token under the default "
               "policy, so no division runs and the family stands "
               "whole, as it does for '田中さん'. 2.2.0 read title "
               "田中さん.",
         tolerated=True),
    Case("ko_lone_name_with_a_period_is_not_a_title", "김민준.",
         {"family": "김", "given": "민준."},
         classification="fix(#323)",
         notes="reads this way since the surname site learned the "
               "core match, NOT through H2's veto: HANGUL segmentation "
               "is on by default and script_segment runs before "
               "assign, so 김민준. is divided into 김 + 민준. before "
               "any period-marked opening word exists for H2 to see. "
               "Kept as the hangul reading of the shape; the veto's "
               "own witness is the Han row below, where no default "
               "segmentation stands in front. The stop rides with the "
               "given name -- nothing rewrites text. 2.2.0 read title "
               "김민준.",
         tolerated=True),
    Case("ko_period_marked_first_word_then_a_name_word", "김민준. 지훈",
         {"family": "김", "given": "민준.", "middle": "지훈"},
         classification="fix(#323)",
         notes="the two-word hangul shape, divided by the surname "
               "site before assign as the row above is: family 김, "
               "given 민준., middle 지훈 -- the reading of '김민준 "
               "지훈' with the stop kept. H2's veto is not what "
               "decides it (see the row above); the Han two-word row "
               "below is where the veto is the whole difference. "
               "2.2.0 read title 김민준., family 지, given 훈 -- "
               "hangul segmentation ran on the trailing word.",
         tolerated=True),
    Case("ja_lone_name_with_a_period_is_not_a_title", "田中.",
         {"family": "田中."},
         classification="fix(#323)",
         notes="the H2 veto's witness: Han has no default segmentation, "
               "so the period-marked word reaches assign whole, and "
               "rules.md#H2's shape -- a Latin convention, an "
               "abbreviation's period -- declines it because Han has "
               "no period abbreviations (the #320 veto, extended from "
               "is_initial to H2). A lone name word is the family "
               "name. Remove the veto and this reads title 田中. "
               "again, which is what 2.2.0 read.",
         tolerated=True),
    Case("ja_period_marked_first_word_then_a_name_word", "田中. 太郎",
         {"family": "田中.", "given": "太郎"},
         classification="fix(#323)",
         notes="the two-word Han shape, where the veto is the whole "
               "difference: without it H2 fires on 田中. and 太郎 "
               "becomes the entire name. With it the pair reads as "
               "'田中 太郎' does, family-first by script (rules.md#W4), "
               "with the stop kept. The stop stays on 田中, the word "
               "that carried it: family 田中., given 太郎. 2.2.0 read "
               "title 田中., family 太郎. Stays tolerated like its "
               "three #323 siblings, H2's Accepted clause being "
               "illustrated in W3's tolerated example block rather "
               "than by promoting this row, per the 2026-09-05 "
               "precedent recorded in tools/differential/compare.py: "
               "marking the row alone would leave the name enforced "
               "and documented as demoted.",
         tolerated=True),
    Case("ja_katakana_lone_name_with_a_period_is_not_a_title", "マイケル.",
         {"given": "マイケル."}, ambiguities=("given-or-family",),
         classification="fix(#323)",
         notes="the katakana arm of the H2 veto, and the one where it "
               "cuts across rules.md#W4 -- a wholly-katakana name keeps "
               "the declared order, so the lone word is the GIVEN name "
               "-- the veto decides title-or-name, the order rule "
               "decides which name. 2.2.0 read title マイケル.",
         tolerated=True),
    Case("latin_period_marked_opening_word_is_still_a_title",
         "Smith. John",
         {"title": "Smith.", "family": "John"},
         classification="parity",
         notes="the Latin side of the #323 veto's fork, pinned so the "
               "veto can never widen onto Latin: Latin has "
               "period abbreviations, H2's shape fires, and an "
               "unlisted period-marked opening word is a title even "
               "when it is a surname."),
    Case("cyrillic_period_marked_opening_word_is_still_a_title",
         "Проф. Иванов",
         {"title": "Проф.", "family": "Иванов"},
         classification="parity",
         notes="the alphabet _policy._NO_INITIALS's own comment names "
               "as the one it would be wrong to add: Cyrillic has "
               "initials and abbreviations, so H2's shape fires and "
               "the #323 veto stays out of its way. Pins the veto's "
               "repertoire at the four CJK scripts from the other "
               "side."),
    Case("ko_name_with_a_period_in_a_bracketed_credential",
         "(김민준.) John Smith",
         {"given": "김", "middle": "민준. John", "family": "Smith"},
         classification="fix(#323)",
         notes="a recorded DEGRADATION, pinned so it cannot move "
               "silently. rules.md#S1's bracketed-credential escape in "
               "_extract calls a clause suffix-shaped when it ends in "
               "an ASCII period -- an unwidened test, deliberately -- "
               "so the brackets are dropped and the content reads as "
               "if written bare. Bare, '김민준. John Smith' used to "
               "reach H2 and give title 김민준. (2.2.0's reading); "
               "since #323 the veto declines a period-marked opening "
               "word written in an initialless script, so 김민준. is "
               "name text, the surname site divides it, and the pieces "
               "spread across the Latin name -- given 김, middle "
               "'민준. John', family Smith. The TRAILING spelling "
               "degrades the same way ('John Smith (김민준.)' reads "
               "given John, middle 'Smith 김', family 민준., where "
               "2.2.0 read given John, middle Smith, family 김민준.); "
               "one row is enough, the mechanism being the unwrap in "
               "front rather than the position. Latin wrapped around a "
               "CJK name is the 2026-09-01 demotion's own ground, so "
               "the row is tolerated and the degradation is recorded "
               "in decisions.md#cjk-full-stops rather than fixed here",
         tolerated=True),
    Case("latin_suffix_with_an_ideographic_full_stop", "John Smith, Jr。",
         {"given": "John", "family": "Smith", "suffix": "Jr。"},
         classification="fix(#322)",
         notes="the stop set is script-agnostic at the lookup fold, so "
               "the reach it bought is not CJK-only: _normalize strips "
               "any of the four FULL_STOPS off any word, and a LATIN "
               "suffix wearing the ideographic stop now folds to its "
               "entry. 2.2.0 read given 'Jr。' / family 'John Smith' -- "
               "the stop defeated the lookup and the credential became "
               "name text. Not tolerated and carrying no shape: the "
               "text is Latin, which _has_cjk does not see, and the "
               "row is a HEAD pin on the fold's Latin reach"),
    Case("latin_roman_numeral_with_an_ideographic_full_stop",
         "Smith, John V。",
         {"given": "John", "family": "Smith", "suffix": "V。"},
         classification="fix(#322)",
         notes="the same reach where it costs something, and the "
               "asymmetry worth pinning: 'Smith, John V.' still reads "
               "middle 'V.', because _reads_as_a_trailing_suffix's "
               "carve-out (_assign) tests an ASCII period ending the "
               "piece's own text -- text.endswith('.') -- and nothing "
               "else; is_initial is not the decider: is_initial('V') "
               "is True, yet 'Smith, John V', no period at all, still "
               "reads suffix 'V'. The WIDE stop does not end the text "
               "in an ASCII period, so the carve-out never fires, the "
               "fold takes the stop off, and 'v' is roman five -- "
               "suffix. 2.2.0 read middle 'V。', the whole word being "
               "unfoldable then. Neither reading was designed; the "
               "bundle widened the stop set and this is where the "
               "widening lands on Latin text, which "
               "decisions.md#cjk-full-stops records as an unasked-for "
               "reach rather than a promise"),
    Case("ko_honorific_glued_teacher", "김선생님",
         {"family": "김", "suffix": "선생님"},
         classification="fix(#307) + fix(#271)",
         notes="longest-first, end to end: 선생님 peels whole where "
               "님 alone would have left 김선생 to segment into a "
               "family 김 and a given 선생. Classified to #307 "
               "because the fields do not move in this change -- "
               "segmentation already delivered this shape (김 is a "
               "listed surname, so the split reached it); #308 "
               "changes which mechanism gets there first"),
    Case("latin_stem_glued_kana_honorific", "Andersonさん",
         {"given": "Anderson", "suffix": "さん"},
         classification="fix(#308)",
         ambiguities=("given-or-family",),
         notes="no script precondition on the remainder -- the tail "
               "is the license. Japanese text about a foreigner, and "
               "the Latin remainder keeps the positional default. "
               "Single-issue on purpose where the block around it is "
               "compound: measured, disabling script_orders and "
               "segment_scripts leaves this row unchanged, because a "
               "Latin remainder never reaches either. Swept as a "
               "2026-09-01 tolerated candidate (CJK text, ASCII "
               "letters) and DECLINED, this row and its hangul twin "
               "below: the demoted forms wrap Latin AROUND a CJK "
               "name, while here the Latin is the name's own core "
               "with a CJK honorific glued on -- a form the glued "
               "peel is written for, and one #308 promises"),
    Case("latin_stem_glued_hangul_honorific", "Anderson선생님",
         {"given": "Anderson", "suffix": "선생님"},
         classification="fix(#308)",
         ambiguities=("given-or-family",),
         notes="the hangul twin of latin_stem_glued_kana_honorific, "
               "and the one that shows why a post-nominal is not a "
               "surname site: 선 is a listed census surname, so the "
               "peeled 선생님 would otherwise be split into 선 + 생님 "
               "-- the stage dissecting the honorific it had just "
               "manufactured. Single-issue for the same reason as its "
               "kana twin: the remainder is Latin, so #271 never "
               "applies -- and a remainder no script order can place "
               "is a remainder O5's convention places, which is what "
               "#449 reports here and on the kana twin. Roles "
               "parity; the flag is #449's"),
    Case("ko_honorific_glued_doctor", "김민준박사님",
         {"family": "김", "given": "민준", "suffix": "박사님"},
         classification="fix(#308) + fix(#271)",
         notes="박사님 is one honorific, not 박사 plus 님, and ships "
               "as one entry: 선생님, 교수님 and 박사님 are the three "
               "standard -님 professional honorifics and the first two "
               "shipped without it, which stranded 박사 in the given "
               "name here and rendered the spaced 김민준 박사님 as two "
               "suffixes. This row USED to pin the one-peel rule "
               "(named ko_glued_stack_peels_once) on the reading that "
               "left 박사 behind; no shipped vocabulary now has that "
               "shape, so the pin lives at stage level with a "
               "synthetic lexicon -- test_script_segment.py's "
               "test_one_peel_never_a_stack"),
    Case("ko_honorific_glued_doctor_spaced", "김민준 박사님",
         {"family": "김", "given": "민준", "suffix": "박사님"},
         classification="fix(#308) + fix(#271)",
         notes="the spaced twin, and the second half of the same gap: "
               "without a 박사님 entry the peel cut this token too -- "
               "it is not a whole-token suffix word, so 박사 + 님 came "
               "back as two suffixes for one honorific"),
    Case("ko_glued_tail_alone_never_peels", "씨",
         {"family": "씨"},
         classification="fix(#271)",
         notes="a token that IS a tail is not a peel site at all -- "
               "every tail is a suffix word, so the site scan steps "
               "past it and finds nothing else. NOT the length cap, "
               "which is never reached here. Classified to #271 "
               "because that is what moves the lone token from first "
               "to family; the row exists for the guard"),
    Case("ko_honorific_token_alone_stays_whole", "선생님",
         {"family": "선생님"},
         classification="fix(#308) + fix(#271)",
         notes="a lone honorific is not a name to be taken apart: it "
               "is not a peel site (every tail is a suffix word) and "
               "not a surname site, though 선 is listed and the "
               "default segmentation split it 선 + 생님 before this "
               "change"),
    Case("ja_glued_tail_alone_never_peels", "さん",
         {"family": "さん"},
         classification="fix(#272)",
         notes="the kana twin of ko_glued_tail_alone_never_peels, and "
               "of that row only: a lone さん carries none of "
               "ko_honorific_token_alone_stays_whole's risk, since no "
               "surname vocabulary is written in kana. The field "
               "placement is the kana-licensed order default, not the "
               "peel"),
    Case("ja_glued_degree_stays", "田中博士",
         {"family": "田中博士"},
         classification="fix(#271)",
         notes="the exclusion pinned: glued 田中博士 IS Tanaka "
               "Hiroshi, an attested given name, so 博士 never peels "
               "-- it stays recognized in the SPACED position only, "
               "where the writer's own token boundary settles it"),
    Case("zh_glued_jun_stays", "王君",
         {"family": "王君"},
         classification="fix(#271)",
         notes="likewise unpeeled: 君 is a common Chinese given-name "
               "final, so 王君 is a complete name, not Mr. Wang. "
               "Unlike its neighbours here, 君 is in NEITHER set -- "
               "there is no spaced entry to fall back on either, and "
               "only its kana spelling くん peels"),
    Case("zh_glued_shi_stays", "王氏",
         {"family": "王氏"},
         classification="fix(#271)",
         notes="likewise: 王氏 is a historical name form ('the Wang "
               "woman'). The spaced 田中氏 keeps its entry"),
    Case("ja_glued_dono_stays", "鵜殿",
         {"family": "鵜殿"},
         classification="fix(#271)",
         notes="the exclusion with the longest argument behind it and, "
               "until this row, the only one nothing held: adding 殿 "
               "back to GLUED_HONORIFICS passed the whole suite. 鵜殿 "
               "(Udono) is a real surname, one of roughly ninety "
               "Japanese surnames ending in 殿 (真殿, 大殿, ...), and a "
               "peeled 殿 would give family 鵜 with 殿 in suffix. It "
               "has to be the BARE surname: in a two-token 真殿 太郎 "
               "the site scan lands on 太郎 and the exclusion is never "
               "consulted, so only a lone surname discriminates. "
               "Classified to #271 like its neighbours, not parity: "
               "1.4 gave first 鵜殿 and no last, and it is the CJK "
               "order flip that makes the one token a family name"),
    Case("ja_dono_spaced", "田中 殿",
         {"family": "田中", "suffix": "殿"},
         classification="fix(#308) + fix(#271)",
         notes="殿 waited on an argument in #307 and gets one here: "
               "spaced it is safe for the reason 양/군 are -- a "
               "殿-surnamed person's name LEADS, and the suffix gate "
               "is trailing-only -- while glued it would cut 鵜殿 and "
               "真殿 in two, so it ships spaced only"),
    Case("ko_honorific_nim_spaced", "김민준 님",
         {"family": "김", "given": "민준", "suffix": "님"},
         classification="fix(#308) + fix(#271)",
         notes="님 is new in both sets -- #307 shipped only the -님 "
               "compounds 선생님/교수님. Standardly glued in online "
               "address, spaced too, and never the end of a Korean "
               "given name, which is what qualifies it for the "
               "harsher glued vetting as well"),
    Case("ko_honorific_glued_via_segmentation", "김씨",
         {"family": "김", "suffix": "씨"},
         classification="fix(#307) + fix(#271)",
         notes="the one glued shape that was already reachable before "
               "#308, which is why this row stays fix(#307) where its "
               "neighbours are fix(#308): stage order alone delivered "
               "it, since segmentation split 김 off the front and the "
               "honorific was whatever remained. The peel now takes 씨 "
               "off the END before segmentation is consulted, so the "
               "route changed and these fields did not. The glued "
               "shapes that needed the peel to be reached at all are "
               "the rows around it (김민준씨 below)"),
    Case("ko_honorific_after_comma", "김민준, 씨",
         {"family": "김민준", "suffix": "씨"},
         classification="fix(#307)",
         notes="the post-comma run is normally the given name -- "
               "'김민준, 태호' gives given 태호 -- and group's "
               "is_suffix_piece diverts this one because 씨 is a "
               "single-token piece carrying vocab:suffix. NOT the "
               "lenient comma gate, which an earlier note named: "
               "measured, lenient_comma_suffixes=False leaves this "
               "row unchanged. The comma disables segmentation per "
               "the comma doctrine, so 김민준 stays whole -- which is "
               "also why this row stays single-issue while the rest of "
               "the block is compound with fix(#271): measured, the "
               "order table and the segmenter both leave it alone, "
               "because the comma already decided the family",
         tolerated=True),
    Case("ko_honorific_glued_given", "김민준씨",
         {"family": "김", "given": "민준", "suffix": "씨"},
         classification="fix(#308) + fix(#271)",
         notes="the common full-name glued shape, and the row this "
               "replaces (ko_honorific_glued_given_stays) pinned the "
               "old boundary: 씨 peels off the last token first, and "
               "the remainder 김민준 then segments as usual -- peel "
               "and split compose, in that order. Shape 6's optional "
               "Honorific slot glued, the everyday spelling next to "
               "zh_honorific_suffix_spaced's spaced one",
         shape=6),
    Case("ko_honorific_glued_given_trailing_suffix", "김민준씨 Jr.",
         {"family": "김", "given": "민준", "suffix": "씨 Jr."},
         classification="fix(#308) + fix(#271)",
         notes="the peel site is the last token that is not itself a "
               "post-nominal, so an unrelated trailing suffix cannot "
               "hide it -- this now agrees with the comma-written "
               "'Dr 김민준씨, Jr.', where the suffix comma had "
               "already put 씨 within reach. The run renders with the "
               "space the writer typed since #436; the comma form "
               "'Dr 김민준씨, Jr.' below keeps its comma, which is "
               "the pair that shows the separator is read from the "
               "text",
         tolerated=True),
    Case("ko_honorific_glued_given_suffix_comma", "Dr 김민준씨, Jr.",
         {"title": "Dr", "family": "김", "given": "민준",
          "suffix": "씨, Jr."},
         classification="fix(#308) + fix(#271)",
         notes="the peel scans the NAME's runs, not the token stream: "
               "under a suffix comma that is segments[0] alone, a "
               "strict subset, and the peel site is found within it "
               "(a FAMILY comma is the one structure that splits the "
               "name across two runs, #312). Pairs with "
               "ko_honorific_glued_given_trailing_suffix, whose "
               "comma-less spelling of the same name reaches the same "
               "answer by the scan-back instead",
         tolerated=True),
    Case("ko_honorific_glued_given_nickname", "김민준씨 (Jimmy)",
         {"family": "김", "given": "민준", "suffix": "씨",
          "nickname": "Jimmy"},
         classification="fix(#308) + fix(#271)",
         notes="the other half of scanning the NAME's runs: extracted "
               "content is still in the token stream at this stage but "
               "in NO segment, so the scan-back never reaches "
               "Jimmy. Scanning the tokens instead would take Jimmy as "
               "the site -- it is no post-nominal -- and lose the peel "
               "entirely, with 씨 back in the given name. Nothing else "
               "pins that choice: under NO_COMMA the two are otherwise "
               "the same run",
         tolerated=True),
    Case("ko_honorific_glued_given_nickname_family_comma",
         "김, 민준씨 (Jimmy)",
         {"family": "김", "given": "민준", "suffix": "씨",
          "nickname": "Jimmy"},
         classification="fix(#312)",
         notes="the family-comma half of the same argument, which the "
               "row above cannot make: there the two runs are one, so "
               "'flatten the name's segments' and 'take segments[0]' "
               "agree. Here the peel has to cross the comma AND still "
               "not reach Jimmy, so declining to cross whenever "
               "extract_delimited claimed something passes the row "
               "above and fails only here",
         tolerated=True),
    Case("ja_honorific_glued_family_comma", "田中さん, PhD",
         {"family": "田中", "suffix": "さん, PhD"},
         classification="fix(#312)",
         notes="the peel reaches 田中さん across the comma, though no "
               "longer by crossing it: since #319 is_wholly_suffix "
               "declines the post-comma run outright (PhD is suffix "
               "vocabulary and it is the whole run), so the scan never "
               "meets the comma. PhD reads as the postnominal it is "
               "since #296's audit took 'phd' out of TITLES -- this row "
               "carried title 'PhD' until then, which was the title "
               "peel claiming a credential because v1's lists put it "
               "where v1's parser needed it",
         tolerated=True),
    Case("ja_honorific_glued_family_comma_suffixy_second_run",
         "田中さん, V.",
         {"given": "V.", "family": "田中", "suffix": "さん"},
         classification="fix(#319)",
         notes="under a family comma the peel scanned both runs on "
               "the premise that segments[1] is name text, and here it "
               "is not: segment picks FAMILY_COMMA when the pre-comma "
               "part is a single word, even where the post-comma part "
               "is entirely suffix-shaped, so the scan reached 'V.' -- "
               "which is_suffix_strict rejects as an initial where "
               "segment admitted the run on is_suffix_lenient. 'V.' "
               "was therefore the site, ended in no tail, and the peel "
               "was abandoned with さん still in the family name. #319 "
               "asks segment's own predicate (_vocab.is_wholly_suffix) "
               "instead of inferring name text from the structure: the "
               "run is declined, the scan stays inside segments[0], "
               "and さん peels off 田中さん as it always did without a "
               "second run. Same credential, three spellings, ONE "
               "answer FROM THE PEEL now -- this, '田中さん, PhD' "
               "above and '田中さん, Ph. D.' in "
               "ja_honorific_glued_family_comma_credential_pair below "
               "all reach 田中さん. Where the credential itself LANDS "
               "still differs by spelling (title 'PhD', given 'V.', "
               "suffix 'さん, Ph. D.'); that is assign's question, not the "
               "peel's, and this row is not a claim about it. Nor does "
               "the comma form now agree with its SPACED twin: "
               "ja_honorific_glued_before_an_initial ('田中さん V.') "
               "still does not peel, because under NO_COMMA there is "
               "one run and 'V.' is inside the name's own tokens where "
               "the scan-back legitimately stops -- declining a "
               "post-comma run does not reach it. Parity with 1.4.0 "
               "(first V., last 田中さん) until this change, which is "
               "what moves it; the 1.4.0 fields are still reachable "
               "through Policy(lenient_comma_suffixes=False), pinned "
               "by ja_honorific_glued_family_comma_strict_knob below",
         tolerated=True),
    Case("ja_honorific_glued_family_comma_credential_pair",
         "田中さん, Ph. D.",
         {"family": "田中", "suffix": "さん, Ph. D."},
         classification="fix(#319)",
         notes="the third of the three spellings #319 named, and the "
               "only one the Ph./D. merge reaches: is_wholly_suffix "
               "folds the adjacent pair into the single unit 'phd' "
               "(v1's fix_phd extracted the credential pre-parse), so "
               "the run counts as wholly suffix, the peel declines it, "
               "and さん comes off 田中さん exactly as in "
               "ja_honorific_glued_family_comma_suffixy_second_run "
               "above. The merge is also why this spelling is NOT the "
               "one to reach for when exercising "
               "Policy(lenient_comma_suffixes=False): 'phd' satisfies "
               "is_suffix_strict as readily as is_suffix_lenient, so "
               "the run is declined under EITHER setting and this row "
               "is identical under the knob, which "
               "ja_honorific_glued_family_comma_credential_pair_strict_"
               "knob below holds rather than leaving to the claim -- "
               "ja_honorific_glued_family_comma_strict_knob below uses "
               "'V.' because the initial-shaped words are where the "
               "two predicates actually part. Where the credential "
               "lands is a separate question and answers differently "
               "again: suffix here, title for 'PhD', given for 'V.' "
               "Measured: 1.4.0 gave first 田中さん / suffix 'Ph. D.' "
               "(fix_phd lifted the credential pre-parse, leaving a "
               "lone pre-comma word), so like "
               "ja_honorific_glued_family_comma above the expectation "
               "carries TWO deviations -- the peel is #319's, first -> "
               "family is comma-family's, which 2.0 already had before "
               "this change (family 田中さん / suffix 'Ph. D.')",
         tolerated=True),
    Case("ja_honorific_glued_family_comma_strict_knob", "田中さん, V.",
         {"family": "田中さん", "given": "V."},
         policy=Policy(lenient_comma_suffixes=False),
         classification="parity",
         notes="the same input as "
               "ja_honorific_glued_family_comma_suffixy_second_run "
               "above under the knob that keeps the pre-#319 answer, "
               "and one of the table's three exercises of it "
               "(ko_honorific_period_under_strict_comma_suffixes and "
               "ja_honorific_glued_family_comma_credential_pair_strict_"
               "knob are the others). The knob drops is_wholly_suffix "
               "to the "
               "strict predicate, which rejects 'V.' as an initial, so "
               "the post-comma run reads as name text after all, the "
               "scan crosses into it, 'V.' is the site, it ends in no "
               "listed tail and the peel is abandoned -- さん stays in "
               "the family name. Not a blanket freeze of pre-#319 "
               "behavior, and the row must not be read as one: it "
               "holds for the INITIAL-shaped suffix words ('V.', 'V', "
               "'I'), which is the whole of where the strict/lenient "
               "gap lives. The counterexample is the row above, "
               "ja_honorific_glued_family_comma_credential_pair: its "
               "Ph./D. pair merges to a form strict accepts too, so "
               "that run is "
               "declined and the peel fires under this setting as "
               "well -- pinned, not merely stated, by "
               "ja_honorific_glued_family_comma_credential_pair_strict_"
               "knob above. No v1 spelling exists for the knob, so the "
               "facade runner skips this row and the classification "
               "compares against 1.4.0's single reading of the same "
               "text, as the other exercise of the knob named above "
               "does: measured, 1.4.0 gave first 'V.' / last "
               "田中さん, which is field for field what the knob holds "
               "here -- parity, and the point of the knob",
         tolerated=True),
    Case("ja_honorific_glued_family_comma_credential_pair_strict_knob",
         "田中さん, Ph. D.",
         {"family": "田中", "suffix": "さん, Ph. D."},
         policy=Policy(lenient_comma_suffixes=False),
         classification="fix(#319)",
         notes="the counterexample the two rows above assert and "
               "neither measured: the knob does NOT freeze the "
               "pre-#319 reading in general, only for the "
               "initial-shaped suffix words. Here the Ph./D. merge "
               "folds the run into 'phd', which is_suffix_strict "
               "accepts as readily as is_suffix_lenient, so the run is "
               "declined and さん peels under this setting exactly as "
               "under the default -- field for field the same "
               "expectation as "
               "ja_honorific_glued_family_comma_credential_pair, which "
               "is the whole claim. Cheap to hold and worth holding "
               "separately, because the two rows differ only in the "
               "policy and a knob that started gating the decline "
               "wholesale would move this one alone. Same "
               "classification and the same two deviations as its "
               "default-policy twin (1.4.0: first 田中さん / suffix "
               "'Ph. D.'), which is also why the knob cannot be judged "
               "against a v1 spelling here -- there is none, so the "
               "facade runner skips this row as it does the other two "
               "knob rows",
         tolerated=True),
    Case("ko_honorific_glued_family_comma_suffixy_second_run",
         "김민준씨, V.",
         {"given": "V.", "family": "김민준", "suffix": "씨"},
         classification="fix(#319)",
         notes="ja_honorific_glued_family_comma_suffixy_second_run in "
               "hangul, and pinned because the decline reads no script "
               "at all: it asks is_wholly_suffix about the post-comma "
               "run and the peel's own scan-back about segments[0], "
               "both vocabulary questions, so a script-conditional "
               "regression would be invisible in a table whose every "
               "other witness to #319 is written in kana. The family "
               "stays 김민준 undivided -- the FAMILY comma gates the "
               "surname split off, so hangul segmentation never runs "
               "here and only the peel acts. 1.4.0 gave first 'V.' / "
               "last 김민준씨, peeling nothing",
         tolerated=True),
    Case("zh_honorific_glued_family_comma_suffixy_second_run",
         "王先生, V.",
         {"given": "V.", "family": "王", "suffix": "先生"},
         classification="fix(#319)",
         notes="the Han spelling of the row above, and the third "
               "script. 先生 is a shipped tail, so the peel fires with "
               "no locale opted in -- honorific_tails is licensed by "
               "the entries themselves rather than by "
               "Policy.segment_scripts, and HAN is not activated here "
               "(the family is what the peel left behind, not a "
               "vocabulary split). 1.4.0 gave first 'V.' / last "
               "王先生",
         tolerated=True),
    Case("ko_honorific_glued_family_comma_site_only_beyond_the_comma",
         "이, J.씨",
         {"given": "J.", "family": "이", "suffix": "씨"},
         classification="fix(#312)",
         notes="the limit of #319's decline, and the row that says why "
               "it carries a second condition. is_wholly_suffix reaches "
               "period_joined_vocab, which calls an interior-period "
               "token a suffix when ANY chunk is suffix vocabulary -- "
               "and every honorific tail is a suffix WORD by the "
               "Lexicon invariant, so 'J.씨' reads as suffix-shaped "
               "BECAUSE of the 씨 the peel exists to remove. Declining "
               "on that evidence does not move the peel elsewhere the "
               "way 田中さん, V. does: segments[0] is the lone 이, which "
               "ends in no tail, so the scan finds no site at all, "
               "nothing peels, and the given name goes to suffix "
               "glued to its honorific ('J.씨'). So the gate declines "
               "only where segments[0] holds a peel site of its own, "
               "and this input reaches the pre-#319 fields by having "
               "none. Not rescued by "
               "Policy(lenient_comma_suffixes=False) either, unlike the "
               "strict-knob row above: the knob picks between "
               "is_suffix_lenient and is_suffix_strict per token and "
               "period_joined_vocab is downstream of neither, so both "
               "settings call this run wholly suffix. 1.4.0 gave first "
               "'J.씨' / last 이 -- it peels nothing, so the deviation "
               "here is #312's crossing, which is what puts the site on "
               "'J.씨' in the first place",
         tolerated=True),
    Case("ko_honorific_glued_family_comma_site_in_both_runs",
         "김민준씨, J.씨",
         {"family": "김민준", "suffix": "씨, J.씨"},
         classification="fix(#319)",
         notes="the two-honorific input, where both runs hold a site "
               "and the decline therefore stands -- a deliberate choice "
               "between two readings rather than a fallout. Pre-#319 "
               "the scan crossed and took the LAST site, peeling the 씨 "
               "off the junk 'J.씨' and leaving the person's own "
               "honorific glued in the family name (given 'J.', family "
               "김민준씨, suffix 씨); now 씨 comes off 김민준씨 and "
               "'J.씨' is consumed whole as a suffix. It is also the "
               "row that rules out the narrower gate: declining only "
               "where the SECOND run has no peel site fixes "
               "ko_honorific_glued_family_comma_site_only_beyond_the_"
               "comma above and reverts this input to the pre-#319 "
               "reading, which is the worse of the two -- the same "
               "junk-tail reach "
               "ko_honorific_glued_given_suffix_comma_initial's note "
               "names under a suffix comma. 1.4.0 gave first 'J.씨' / "
               "last 김민준씨, peeling neither",
         tolerated=True),
    Case("ko_honorific_glued_family_comma_lone_post_nominal_before_it",
         "선생님, J.씨",
         {"given": "J.", "family": "선생님", "suffix": "씨"},
         classification="fix(#312)",
         notes="segments[0] is a single token that IS a listed tail "
               "entire, which the site scan skips as a post-nominal "
               "(the same guard that keeps 선생님 from being peeled to "
               "선생 + 님) -- so there is no site before the comma, the "
               "run beyond it is scanned after all, and the fields are "
               "the pre-#319 ones as in the 이 row above. Pinned "
               "because it separates asking for the site with the "
               "peel's own scan-back from asking the cheaper question, "
               "whether any token ENDS in a tail: the cheaper one "
               "counts 선생님, declines, and then finds nothing to cut "
               "-- 씨 lost into suffix 'J.씨'. Only the lone-token "
               "shape of that divergence is reachable from the gate, "
               "which is why this row is one token before the comma; "
               "_peel_site's docstring derives the bound. "
               "1.4.0 gave first 'J.씨' / last 선생님",
         tolerated=True),
    Case("ko_honorific_glued_family_comma_stop_on_the_first_run",
         "김민준씨., J.씨",
         {"family": "김민준", "suffix": "씨., J.씨"},
         classification="fix(#323)",
         notes="the stop-bearing spelling of "
               "ko_honorific_glued_family_comma_site_in_both_runs, "
               "here because the FAMILY_COMMA decline is a gate of TWO "
               "conjuncts and a trailing stop reaches exactly one of "
               "them. Measured on this tree and on d37b8ec: the first "
               "conjunct, is_wholly_suffix of the post-comma run, is "
               "True on both -- the stop is not there. The SECOND, "
               "segments[0] holding a peel site, is what the stop "
               "flipped, False before #323 (the tail match ran on the "
               "raw text and 김민준씨. ends in a stop, not in 씨) and "
               "True now. So the decline stands, 씨. peels off 김민준씨. "
               "and 'J.씨' is consumed whole. Agrees with the stop-less "
               "twin field for field, the stop riding on the honorific "
               "piece it arrived with (family 김민준, suffix '씨, J.씨' "
               "there). 2.2.0 read given 'J.', family 김민준씨., suffix "
               "씨 -- the junk 씨 peeled off 'J.씨' while the person's "
               "own honorific stayed in the family name",
         tolerated=True),
    Case("ja_honorific_glued_family_comma_stop_on_the_first_run",
         "田中さん., V.",
         {"given": "V.", "family": "田中", "suffix": "さん."},
         classification="fix(#323)",
         notes="the kana twin of the row above, and the same conjunct: "
               "is_wholly_suffix(['V.']) is True on both trees under "
               "the lenient default, and the segments[0] site is False "
               "before #323 and True now. Before, the gate therefore "
               "did not decline, the scan crossed to 'V.', which ends "
               "in no tail, and the peel was abandoned with さん. left "
               "in the family name -- 2.2.0 read given 'V.', family "
               "田中さん., no suffix at all. Agrees with "
               "ja_honorific_glued_family_comma_suffixy_second_run "
               "field for field (given 'V.', family 田中, suffix さん "
               "there), the stop riding on the honorific",
         tolerated=True),
    Case("ko_honorific_glued_family_comma_stop_beyond_the_comma",
         "이, J.씨.",
         {"given": "J.", "family": "이", "suffix": "씨."},
         classification="fix(#323)",
         notes="the stop on the OTHER side of the comma, and the row "
               "that keeps the two rows above from reading as 'a stop "
               "moves the gate'. Measured on this tree and on d37b8ec, "
               "NEITHER conjunct moves: the post-comma run is wholly "
               "suffix-shaped on both, and segments[0] -- the lone 이 "
               "-- holds no peel site on either, so the gate declines "
               "nothing and the scan crosses the comma under #312 both "
               "times. What the stop moved is the site scan itself. "
               "'J.씨.' ended in no listed tail before #323, so the "
               "peel found no site at all and the whole run went to "
               "suffix (2.2.0 read family 이, suffix 'J.씨.'); now the "
               "tail matches through the stop and the cut lands before "
               "it. Agrees with "
               "ko_honorific_glued_family_comma_site_only_beyond_the_"
               "comma field for field (given 'J.', family 이, suffix "
               "씨 there), the stop riding on 씨",
         tolerated=True),
    Case("ko_honorific_glued_given_after_family_comma", "김, 민준씨",
         {"family": "김", "given": "민준", "suffix": "씨"},
         classification="fix(#312)",
         notes="under a family comma the name spans both segments and "
               "the honorific is on the GIVEN side, where the peel "
               "never looked before #312. Agrees with the spaced "
               "김 민준씨",
         tolerated=True),
    Case("ja_honorific_glued_given_after_family_comma", "田中, 太郎さん",
         {"family": "田中", "given": "太郎", "suffix": "さん"},
         classification="fix(#312)",
         notes="the Han twin of the row above",
         tolerated=True),
    Case("zh_interpunct_transcription_glued_honorific", "威廉·莎士比亚さん",
         {"given": "威廉", "family": "莎士比亚", "suffix": "さん"},
         classification="fix(#312)",
         notes="the dot still gates the surname split -- a "
               "transcription's pieces are syllable groups -- but an "
               "honorific glued to a transcribed name is still an "
               "honorific, so the peel crosses it. Agrees with the "
               "spaced 威廉·莎士比亚 さん"),
    Case("ja_honorific_glued_family_comma_no_site", "田中さん, 太郎",
         {"family": "田中さん", "given": "太郎"},
         notes="unchanged, and pinned because a naive fix breaks it: "
               "the site is the last NON-POST-NOMINAL token, which is "
               "太郎, so nothing peels -- exactly as in the spaced "
               "田中さん 太郎. #312 was originally filed naming this "
               "pair as a disagreement; it never was one",
         tolerated=True),
    Case("ko_honorific_glued_given_suffix_comma_initial", "Dr 김민준씨, V.",
         {"title": "Dr", "family": "김", "given": "민준",
          "suffix": "씨, V."},
         classification="fix(#308) + fix(#271)",
         notes="fix(#308) rather than fix(#312) because the fields do "
               "not move in this change -- a SUFFIX comma keeps the "
               "whole name in segments[0], which is what the peel "
               "already scanned. The row is here as the end-to-end "
               "guard for the scoping #312 introduced: widen the scan "
               "to every segment and 'V.' becomes the site, since "
               "segment admits a post-comma run on is_suffix_lenient "
               "while the site scan asks is_suffix_strict and an "
               "initial fails it. 'V.' then ends in no tail, the peel "
               "is abandoned, and 씨 is back in the given name -- the "
               "original bug. It was the table's only witness to that "
               "widening until #319; ja_honorific_glued_family_comma_"
               "suffixy_second_run and "
               "ja_honorific_glued_family_comma_credential_pair notice "
               "it as well now, but from the FAMILY_COMMA side, where "
               "the guard is is_wholly_suffix rather than this "
               "structural scoping. Their strict-knob sibling does NOT "
               "join them: under the knob is_wholly_suffix is False on "
               "the same run, so the scan was already crossing into "
               "segments[1] and widening past it changes nothing. This "
               "row is still the only SUFFIX comma among the three. "
               "Its comma-less twin ja_honorific_glued_before_an_initial "
               "shows the same veto from the other side, where 'V.' is "
               "in the name's own run and so IS the site",
         tolerated=True),
    Case("zh_honorific_glued_surname", "王先生",
         {"family": "王", "suffix": "先生"},
         locale="zh",
         classification="fix(#307) + fix(#271)",
         notes="the Han twin of 김씨: the zh pack's segmentation "
               "splits off the surname and the remaining 先生 is the "
               "honorific token"),
    Case("zh_honorific_glued_given", "王小明先生",
         {"family": "王", "given": "小明", "suffix": "先生"},
         locale="zh",
         classification="fix(#308) + fix(#271)",
         notes="the Han twin, replacing zh_honorific_glued_given_stays: "
               "先生 peels, and the zh pack's surname vocabulary then "
               "divides the remainder 王小明"),
    Case("zh_honorific_glued_given_default", "王小明先生",
         {"family": "王小明", "suffix": "先生"},
         classification="fix(#308) + fix(#271)",
         notes="the same input WITHOUT the pack: the peel is default-on "
               "and script-independent, so the honorific still routes "
               "to suffix -- only the surname split needs the opt-in, "
               "so the undivided 王小明 stays one family name"),
    Case("ko_suffix_matching_is_whole_token", "김지양",
         {"family": "김", "given": "지양"},
         classification="fix(#271)",
         notes="지양 ENDS with the honorific 양 but is a given name: "
               "suffix matching is whole-token, never endswith -- the "
               "pin the differential rule's anchor mirrors at the "
               "name-string level. #308 leaves it alone too: 양 is "
               "excluded from the glued tail set for exactly this "
               "name. Classified to #271, not parity: 1.4 gave first "
               "김지양 and no last, and it is #271's hangul "
               "segmentation plus the CJK order flip that produces "
               "these two fields"),
    Case("ko_surname_yang_leads", "양 미선",
         {"family": "양", "given": "미선"},
         classification="fix(#271)",
         notes="양 is both a top-tier surname (Yang) and a shipped "
               "honorific: position decides, and a surname LEADS -- "
               "the trailing-only suffix gate never sees it here. "
               "Classified to #271, not parity: 1.4 gave first 양, "
               "last 미선, and it is the CJK order flip that swaps "
               "them"),
    Case("ko_honorific_yang_trails", "김민준 양",
         {"family": "김", "given": "민준", "suffix": "양"},
         classification="fix(#307) + fix(#271)",
         notes="the other side of ko_surname_yang_leads: the same "
               "token trailing a name is 'Miss', and that is the whole "
               "argument shipping it -- suffixes.py singles 양 out "
               "(with 군) as the risk class it takes, a top-tier "
               "surname admitted to the vocabulary on the strength of "
               "position alone. Nothing pinned the trailing reading "
               "before this row, so the leading rows carried the pair "
               "by themselves. Classified to #307 like ko_honorific_ssi "
               "(1.4 gave first 김민준, last 양; the recognition and "
               "the order flip both move it) -- the point of the row "
               "is the twin below"),
    Case("ko_honorific_yang_written_with_a_period", "김민준 양.",
         {"family": "김", "given": "민준", "suffix": "양."},
         classification="fix(#320)",
         notes="the period-written twin, whose fields must equal the "
               "row above and before #320 did not (given 김, middle "
               "민준, family '양.' -- the veto kept '양.' a name piece, "
               "exactly ko_honorific_with_a_period_no_comma's route). "
               "The pair is the point: 양 is the shipped vocabulary's "
               "acknowledged risk, so if the 양/군 policy is ever "
               "tightened or withdrawn, both spellings have to move "
               "together and neither row can be adjusted alone. 군 "
               "gets no pair of its own -- it parses identically and "
               "is the SAFER half (no surname reading), so it would "
               "pin nothing these two do not. Classified to #320 like "
               "its 씨 counterpart: 1.4.0 read this first 김민준 / last "
               "'양.', and the fields above are the ones this change "
               "produced, not the segmenter's. TOLERATED since "
               "2026-09-05 for the same reason as that counterpart -- "
               "a trailing ASCII period on a CJK honorific is a "
               "listing artifact no writing system produces -- and the "
               "pair moves tiers together the way it moves fields "
               "together. The row still pins #320's mechanism at HEAD",
         tolerated=True),
    Case("ko_surname_yang_leads_a_segmentable_given", "양 지훈",
         {"family": "양", "given": "지훈"},
         classification="fix(#271)",
         notes="양 is a surname AND a shipped honorific, and 지 is a "
               "listed surname too -- so this is the name that "
               "catches a segmentation site scanning PAST the "
               "honorific reading of 양 into the given name. The "
               "first script-written token decides, and deciding "
               "includes deciding there is no surname site. "
               "Classified to #271, not parity: 1.4 gave first 양, "
               "last 지훈, and it is the CJK order flip that puts 양 "
               "in family -- nothing in #308 moves these fields"),
    Case("ko_honorific_stack", "김민준 박사 씨",
         {"family": "김", "given": "민준", "suffix": "박사 씨"},
         classification="fix(#307) + fix(#271)",
         notes="a trailing RUN of honorifics peels whole, like "
               "'Smith PhD MD' -- the multi-suffix loop the peel "
               "shares with Latin suffixes. The run renders with the "
               "space the writer typed since #436; the comma form "
               "'Dr 김민준씨, Jr.' (ko_honorific_glued_given_suffix_"
               "comma) keeps its comma, which is the pair that shows "
               "the separator is read from the text"),
)
