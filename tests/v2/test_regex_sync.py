"""Pins the pipeline's and render's hand-duplicated patterns to the
copy each was taken from.

The 2.0 layering rule forbids nameparser._render importing the
pipeline, so a pattern both need is copied by hand into _render, with
a "keep in sync by hand" comment. Nothing else enforces that promise:
if the pipeline's copy changed, render's would silently diverge with
no CI signal. Tests may legally import both sides (test_layering.py's
own convention), so this module is where the promise gets checked.

Each copy is pinned to the PIPELINE's pattern, the one that parses.
Until 3.0 both sides were pinned to nameparser.config.regexes, the v1
table the parser had not read since 2.0, which #1008 removed
(decisions/3-0-reevaluations). A pattern with no second copy has no
promise to check and is declared with None.

Layering is the usual reason for a copy but not the only one, so the
scope here is the PROMISE rather than that one pair of packages: the
comma-set pin below reads _pipeline._state.
"""
import pathlib
import re

import pytest

from nameparser._pipeline import (
    _assemble, _assign, _classify, _comma, _extract, _group, _pieces,
    _post_rules, _script_segment, _segment, _state, _tokenize, _vocab,
)
import nameparser._pipeline
from nameparser import _render


def test_initial_copies_agree() -> None:
    # _vocab._INITIAL and _render._INITIAL are both v1's "initial"
    # pattern minus its trailing "?" (documented at _render.py's
    # _INITIAL definition: the two call sites always fullmatch a
    # non-empty token, so the empty-string alternative is dropped on
    # purpose). Declared in _SOURCES below as well; this test keeps
    # the reason the agreement matters beside it.
    # The two copies stopped answering the same question in #458 and
    # the agreement matters MORE for it, not less: _vocab's asks what
    # the parse decided about a token, _render's what it would have
    # decided about text spliced into a field afterwards, and the
    # second is only right while it answers as the first would. This
    # test is what says so. (#458 briefly deleted _render's copy, when
    # nothing read it; the unparsed-text fallback gave it a reader
    # again -- see _render._reads_as_conjunction.)
    assert _vocab._INITIAL.pattern == _render._INITIAL.pattern
    assert _vocab._INITIAL.flags == _render._INITIAL.flags


def test_dotted_initial_is_the_period_alternative_of_initial() -> None:
    # _render._DOTTED_INITIAL (#478's hyphen clause) is _INITIAL's
    # period alternative alone -- the bare-capital half is deliberately
    # not used there (#458). _INITIAL is "^(\\w\\.|[A-Z])$"; splitting
    # its alternation and re-wrapping the first half must reproduce
    # _DOTTED_INITIAL exactly, so the two cannot drift apart unnoticed.
    inner = _render._INITIAL.pattern[2:-2]  # strip "^(" and ")$"
    period_alt = inner.split("|")[0]
    assert _render._DOTTED_INITIAL.pattern == f"^{period_alt}$"
    assert _render._DOTTED_INITIAL.flags == _render._INITIAL.flags


# The roster of every compiled pattern in the scanned modules, with a
# completeness check below: adding a pattern without declaring where
# it was copied from fails here instead of being silently unpinned.
# Each value names the (module, attribute) the copy must equal, or
# None for a pattern that is its own only copy.
_SOURCES: dict[tuple[str, str], tuple[str, str] | None] = {
    ("_vocab", "_PERIOD_ABBREV"): None,
    # rules/H5's trailing shape, _PERIOD_ABBREV widened to an
    # abbreviation written joined or hyphenated (#1116)
    ("_vocab", "_TRAILING_TITLE_SHAPE"): None,
    # SAME object, imported for H5's trailing chain
    ("_pieces", "_TRAILING_TITLE_SHAPE"): ("_vocab", "_TRAILING_TITLE_SHAPE"),
    # rules/H5's listed joined title (#1104's narrow half)
    ("_vocab", "_JOINED_WORD"): None,
    # SAME object, imported for classify's JOINED_TITLE_TAG
    ("_classify", "_JOINED_WORD"): ("_vocab", "_JOINED_WORD"),
    # rules/S1's initials shape for a bracketed credential (#792)
    ("_vocab", "_INITIALS_SHAPE"): None,
    # its dotted alternative, from which _INITIALS_SHAPE is built, read
    # for S1's dual words by `reads_as_initials` beside it (#1088 moved
    # the test there from _post_rules, which imported it)
    ("_vocab", "_DOTTED_INITIALS"): None,
    # SAME object as _vocab's, not a second copy: _pieces imports it
    # from _vocab (#289/#516, quality-review finding -- is_title_shaped
    # moved there so name_word_count could share is_leading_title's H2
    # shape test), so it is visible under both module names and the
    # completeness scan below sees it twice.
    ("_pieces", "_PERIOD_ABBREV"): ("_vocab", "_PERIOD_ABBREV"),
    # the same object again: assemble imports it to name a title read
    # by rules/H2's shape (`Token.reading`, 3.0)
    ("_assemble", "_PERIOD_ABBREV"): ("_vocab", "_PERIOD_ABBREV"),
    # `split_pair`'s two halves, the Ph./D. split credential (#752;
    # declared under _group until then, which had stopped holding them)
    ("_vocab", "_PH"): None,
    ("_vocab", "_D"): None,
    ("_vocab", "_DOTTED"): None,
    # #544: the chunked sibling of _DOTTED ('M.Eng.'), S3's period gate
    # for a member with a lower-case tail
    ("_vocab", "_CHUNKED"): None,
    # the joiners of the caps shape's joined spelling ('PU-PH',
    # rules/S9, #752); a joined credential is cut by _JOINER_SPLIT (#1103)
    ("_vocab", "_JOINERS"): None,
    # the same joiners, kept by the split, for S3's cut of a joined
    # credential into listed runs (#1103)
    ("_vocab", "_JOINER_SPLIT"): None,
    # the caps shape's joined spelling ('PU-PH', rules/S9, #752)
    ("_vocab", "_JOINED_LETTERS"): None,
    # #563: paired initials ('M.J.'), C5's exception to C4's name-word
    # count after a comma
    ("_vocab", "_PAIRED_INITIALS"): None,
    ("_vocab", "_ROMAN"): None,
    # SAME object, imported for the trailing read's weighed-word test
    # (#620), as _PERIOD_ABBREV is above
    ("_pieces", "_ROMAN"): ("_vocab", "_ROMAN"),
    # SAME object, imported for the report on a numeral before a
    # credential (#721)
    ("_assign", "_ROMAN"): ("_vocab", "_ROMAN"),
    # the numeral clause's copy of _vocab._ROMAN (#459); layering
    # forbids _render the import, so it is pinned here instead
    ("_render", "_ROMAN"): ("_vocab", "_ROMAN"),
    # The patronymic patterns' hand copies are in the RU and TR_AZ
    # packs, not in a scanned module, and test_locales'
    # test_a_packs_marker_regexes_are_the_rules_its_patch_turns_on
    # holds them to these.
    ("_vocab", "_EAST_SLAVIC"): None,
    ("_vocab", "_EAST_SLAVIC_CYR"): None,
    ("_vocab", "_TURKIC"): None,
    ("_vocab", "_TURKIC_CYR"): None,
    # rules/O6's hyphens (#754)
    # rules/O6's hyphens, defined in _vocab since #1116 so rules/H5's
    # trailing shape reads the same set
    ("_vocab", "_HYPHENS"): None,
    ("_post_rules", "_HYPHENS"): ("_vocab", "_HYPHENS"),
    # render's own patterns, v1's "spaces", "space_before_comma",
    # "mac" and "word"; the v1 table they were pinned to until #1008
    # was their only other copy
    ("_render", "_SPACES"): None,
    ("_render", "_SPACE_BEFORE_COMMA"): None,
    # Mc alone since #1014
    ("_render", "_MC"): None,
    ("_render", "_WORD"): None,
    ("_vocab", "_PERIOD_NOT_AT_END"): None,
    ("_vocab", "_INITIAL"): None,
    # layering forbids _render the import (test_initial_copies_agree
    # above says why the agreement matters)
    ("_render", "_INITIAL"): ("_vocab", "_INITIAL"),
    # SAME object, imported for the one-case letter initial (#723)
    ("_classify", "_INITIAL"): ("_vocab", "_INITIAL"),
    # Deliberately NOT a straight copy -- _INITIAL's period
    # alternative, pinned by the dedicated test above:
    ("_render", "_DOTTED_INITIAL"): None,
    # #542: the name run after an Mc prefix, read on the word as
    # written once _MC has matched its composed spelling
    ("_render", "_NAME_RUN"): None,
    ("_tokenize", "_BIDI"): None,
    # Mirrors _pipeline._state.COMMA_CHARS, a set rather than a
    # pattern -- pinned by its own test below
    ("_render", "_COMMA_CHAR"): None,
}

def test_every_pipeline_module_is_scanned_for_hand_copies() -> None:
    """The twin of test_layering's completeness check, in the file with
    the same shape of registry.

    test_every_hand_copied_pattern_is_declared iterates _MODULES, so a
    module absent from that dict is not scanned loosely -- it is not
    scanned at all, and an undeclared hand copy of a pattern in it goes
    unpinned. Measured on a scratch copy: a new pipeline module
    carrying a wrong copy of the mac pattern passed all 20 tests here.

    Scoped to _pipeline/ for the same reason the layering twin is: it
    is where a new module is a design decision. The directory is
    derived from the imported subpackage and the floor is asserted --
    Path.glob on a missing directory returns empty rather than raising,
    which would make this pass for every possible _MODULES.
    """
    pipeline_dir = pathlib.Path(nameparser._pipeline.__file__).parent
    shipped = {p.stem for p in pipeline_dir.glob("*.py")
               if p.stem != "__init__"}
    assert "_group" in shipped, (
        f"the glob matched no pipeline modules, so this check can no "
        f"longer fail: {sorted(shipped)}")
    missing = sorted(shipped - set(_MODULES))
    assert not missing, (
        f"pipeline modules absent from _MODULES, and therefore never "
        f"scanned for undeclared hand copies of a pattern: "
        f"{missing}. Add each one; a module with no hand copies costs "
        f"nothing to scan"
    )


_MODULES = {"_assemble": _assemble, "_assign": _assign,
            "_classify": _classify, "_comma": _comma, "_extract": _extract,
            "_group": _group, "_pieces": _pieces,
            "_post_rules": _post_rules, "_render": _render,
            "_script_segment": _script_segment, "_segment": _segment,
            "_state": _state, "_tokenize": _tokenize, "_vocab": _vocab}


@pytest.mark.parametrize(
    "where,source", [(w, s) for w, s in _SOURCES.items() if s is not None],
    ids=lambda v: f"{v[0]}.{v[1]}")
def test_declared_copy_matches_its_source(
        where: tuple[str, str], source: tuple[str, str]) -> None:
    copy = getattr(_MODULES[where[0]], where[1])
    original = getattr(_MODULES[source[0]], source[1])
    label = f"{where[0]}.{where[1]} vs {source[0]}.{source[1]}"
    assert copy.pattern == original.pattern, label
    assert copy.flags == original.flags, label


def test_every_hand_copied_pattern_is_declared() -> None:
    """The roster must cover every compiled pattern in these modules.

    Without this, the roster is just another list that a new constant
    can be left out of -- which is how the four above went unpinned.
    """
    undeclared = [
        (name, attr)
        for name, mod in _MODULES.items()
        for attr, value in vars(mod).items()
        if attr.startswith("_") and not attr.startswith("__")
        and isinstance(value, re.Pattern)
        and (name, attr) not in _SOURCES
    ]
    assert not undeclared, (
        f"compiled patterns missing from _SOURCES: {undeclared}. Add each "
        f"with the (module, attribute) it was copied from, or None if it "
        f"is its own only copy.")


def test_comma_char_matches_the_pipeline_comma_set() -> None:
    # _render splits on the same comma characters segment does; the set
    # lives in _state, so this one is pinned against that.
    from nameparser._pipeline._state import COMMA_CHARS

    assert set(_render._COMMA_CHAR.pattern.strip("[]")) == set(COMMA_CHARS)


def test_every_declared_pattern_still_exists() -> None:
    """The converse of the completeness check: an entry naming a
    pattern its module no longer holds pins nothing. `_group._PH` and
    `_group._D` stood here after both moved to `_vocab`, found when
    #752 renamed them there; an entry with no source was never read by
    the parametrized test above, so nothing failed."""
    stale = sorted(where for where in _SOURCES
                   if not isinstance(getattr(_MODULES[where[0]], where[1],
                                             None), re.Pattern))
    assert not stale, f"_SOURCES entries naming no compiled pattern: {stale}"
