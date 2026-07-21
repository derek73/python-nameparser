import dataclasses
import pickle
from collections.abc import Callable

import pytest

from nameparser import Parser
from nameparser._lexicon import Lexicon, _normalize, _title_key


def test_entries_are_normalized_at_construction() -> None:
    lex = Lexicon(titles=frozenset({"Dr.", "MR"}))
    assert lex.titles == frozenset({"dr", "mr"})


def test_default_sources_v1_vocabulary() -> None:
    lex = Lexicon.default()
    assert "dr" in lex.titles
    assert "van" in lex.particles
    assert "phd" in lex.suffix_acronyms
    # flipped model: 'dos' is never-given in v1, so NOT ambiguous here
    assert "dos" in lex.particles and "dos" not in lex.particles_ambiguous
    assert "van" in lex.particles_ambiguous
    # v1's CAPITALIZATION_EXCEPTIONS maps 'phd' -> 'Ph.D.' (verbatim, not
    # normalized -- only keys are lowercased/period-stripped at
    # construction, values pass through unchanged).
    assert lex.capitalization_exceptions_map["phd"] == "Ph.D."
    # maiden markers source from the same data-module pattern (#274);
    # non-colliding Cyrillic entries live in the default per the locales
    # design's sorting rule, and both ё/е spellings are listed because
    # case normalization does not fold them.
    assert "geborene" in lex.maiden_markers
    assert "урожденная" in lex.maiden_markers and "урождённая" in lex.maiden_markers
    # #269 fidelity: entries whose spelling casefold() would mutate must
    # arrive in the lexicon exactly as authored in the data modules
    # (final sigma intact, ß intact) -- the review that caught 'κοσ'.
    assert "κος" in lex.titles and "κοσ" not in lex.titles
    assert "großfürst" in lex.titles and "grossfürst" not in lex.titles


def test_default_is_cached_single_instance() -> None:
    assert Lexicon.default() is Lexicon.default()


def test_particles_ambiguous_must_be_subset_of_particles() -> None:
    with pytest.raises(ValueError, match="subset"):
        Lexicon(particles_ambiguous=frozenset({"van"}))


def test_capitalization_exceptions_canonical_and_no_aliasing() -> None:
    exceptions = {"phd": "PhD", "ii": "II"}
    lex = Lexicon.empty()
    lex2 = dataclasses.replace(lex, capitalization_exceptions=exceptions)  # type: ignore[arg-type]
    exceptions["iii"] = "III"  # mutate caller's dict afterwards
    assert "iii" not in lex2.capitalization_exceptions_map
    # canonical: insertion order does not affect equality/hash
    lex3 = dataclasses.replace(lex, capitalization_exceptions=(("ii", "II"), ("phd", "PhD")))
    assert lex2 == lex3 and hash(lex2) == hash(lex3)


def test_lexicon_is_hashable() -> None:
    assert isinstance(hash(Lexicon.default()), int)


def test_lexicon_rejects_bare_string_vocab() -> None:
    with pytest.raises(TypeError, match="bare string"):
        Lexicon(titles="dr")  # type: ignore[arg-type]


def test_lexicon_rejects_non_str_vocab_entries() -> None:
    with pytest.raises(TypeError, match="entries must be strings"):
        Lexicon(titles={"Dr.", 42})  # type: ignore[arg-type]


def test_lexicon_rejects_non_iterable_vocab_field() -> None:
    # A non-iterable (an int) used to fall through to tuple(entries)
    # and surface as a bare "'int' object is not iterable" with no
    # hint which field was wrong.
    with pytest.raises(TypeError, match="titles.*iterable"):
        Lexicon(titles=5)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="titles.*iterable"):
        Lexicon.empty().add(titles=5)  # type: ignore[arg-type]


def test_capitalization_exceptions_rejects_non_iterable() -> None:
    with pytest.raises(TypeError, match="capitalization_exceptions"):
        Lexicon(capitalization_exceptions=5)  # type: ignore[arg-type]


def test_entries_normalizing_to_empty_raise() -> None:
    # "." or "" is a data bug (stray split artifact, empty CSV cell);
    # dropping it silently would also let a future data-module typo
    # vanish instead of failing CI. One rule for vocab AND exception keys.
    with pytest.raises(ValueError, match="normalizes to empty"):
        Lexicon(titles=frozenset({"Dr.", "."}))
    with pytest.raises(ValueError, match="normalizes to empty"):
        Lexicon.empty().add(titles={" "})
    with pytest.raises(ValueError, match="normalizes to empty"):
        Lexicon(capitalization_exceptions=(("...", "X"), ("phd", "PhD")))


def test_colliding_exception_keys_dedupe_last_wins() -> None:
    # 'Phd.' and 'phd' collide under edge-period normalization
    lex = Lexicon(capitalization_exceptions=(("Phd.", "A"), ("phd", "B")))
    assert lex.capitalization_exceptions == (("phd", "B"),)
    rebuilt = Lexicon(capitalization_exceptions=lex.capitalization_exceptions_map)  # type: ignore[arg-type]
    assert rebuilt == lex and hash(rebuilt) == hash(lex)


def test_lexicon_rejects_non_str_exception_values() -> None:
    with pytest.raises(TypeError, match="str -> str"):
        Lexicon(capitalization_exceptions={"phd": 42})  # type: ignore[dict-item, arg-type]


def test_add_and_remove_return_new_lexicons() -> None:
    # "zqtitle" is a synthetic word absent from v1's TITLES data (unlike
    # e.g. "dra", the feminine "dr." abbreviation, which is already there).
    base = Lexicon.default()
    lex = base.add(titles={"zqtitle"}).remove(suffix_words={"esquire"})
    assert "zqtitle" in lex.titles and "zqtitle" not in base.titles
    # precondition, or the removal assertion passes vacuously (this is a
    # guard for the operation under test, not a vocabulary content pin)
    assert "esquire" in base.suffix_words
    assert "esquire" not in lex.suffix_words


def test_add_unknown_field_raises_with_valid_names() -> None:
    with pytest.raises(TypeError, match="prefixes"):
        Lexicon.default().add(prefixes={"van"})  # v1 name: helpful error


def test_add_capitalization_exceptions_raises_pointing_at_replace() -> None:
    with pytest.raises(TypeError, match="dataclasses.replace"):
        Lexicon.default().add(capitalization_exceptions={"x": "X"})


def test_union_is_fieldwise_and_right_biased_for_exceptions() -> None:
    a = dataclasses.replace(Lexicon.empty(),
                            capitalization_exceptions=(("phd", "PhD"),))
    a = a.add(titles={"dr"})
    b = dataclasses.replace(Lexicon.empty(),
                            capitalization_exceptions=(("phd", "Ph.D."),))
    b = b.add(titles={"mr"})
    u = a | b
    assert u.titles == frozenset({"dr", "mr"})
    assert u.capitalization_exceptions_map["phd"] == "Ph.D."  # right wins


def test_remove_breaking_subset_invariant_raises() -> None:
    lex = Lexicon(particles=frozenset({"van"}), particles_ambiguous=frozenset({"van"}))
    with pytest.raises(ValueError, match="subset"):
        lex.remove(particles={"van"})  # would orphan particles_ambiguous


def test_pickle_round_trip_preserves_equality_and_cap_map() -> None:
    # _cap_map holds a MappingProxyType, which pickle rejects; Lexicon
    # must round-trip anyway because Parser is picklable by construction
    # (spec: 2026-07-11-v2-core-api-design.md) and a Parser holds a Lexicon.
    import pickle

    for lex in (Lexicon.default(),
                Lexicon.empty().add(titles={"Dr."})):
        loaded = pickle.loads(pickle.dumps(lex))
        assert loaded == lex
        assert hash(loaded) == hash(lex)
        assert (loaded.capitalization_exceptions_map
                == lex.capitalization_exceptions_map)


def test_lexicon_rejects_mapping_for_plain_vocab_field() -> None:
    # A dict here almost always means the caller confused the field with
    # capitalization_exceptions; silently keeping just the keys would be
    # the lone quiet coercion on an otherwise fail-loud surface.
    with pytest.raises(TypeError, match="mapping"):
        Lexicon(titles={"Dr.": "Doctor"})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="mapping"):
        Lexicon.empty().add(titles={"Dr.": "Doctor"})


def test_capitalization_exceptions_rejects_malformed_shapes() -> None:
    with pytest.raises(TypeError, match="bare string"):
        Lexicon(capitalization_exceptions="ab")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="pairs"):
        Lexicon(capitalization_exceptions=(("a", "b", "c"),))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="pairs"):
        # a 2-char string entry would unpack into two chars and silently
        # store {"a": "b"} -- reject str entries outright
        Lexicon(capitalization_exceptions=("ab",))  # type: ignore[arg-type]


def test_setstate_rejects_mismatched_field_layout() -> None:
    # A pickle from a different Lexicon version (field added/renamed)
    # must fail at load time with a message naming the mismatch, not at
    # some later attribute read far from the unpickle site.
    lex = Lexicon.empty()
    good_state = lex.__getstate__()
    missing = dict(good_state)
    del missing["titles"]
    with pytest.raises(ValueError, match="titles"):
        Lexicon.__new__(Lexicon).__setstate__(missing)
    extra = dict(good_state)
    extra["zq_future_field"] = frozenset()
    with pytest.raises(ValueError, match="zq_future_field"):
        Lexicon.__new__(Lexicon).__setstate__(extra)


def test_normalization_lowercases_and_keeps_interior_periods() -> None:
    # v1's lc() semantics: lowercase, EDGE periods trimmed, interior
    # periods KEPT ('J.R.' must not collapse to 'jr' and hit the
    # periodless vocabulary -- v1 parity, pinned live 2026-07-17).
    # Suffix-ACRONYM membership alone strips periods (see
    # _vocab.suffix_as_written).
    lex = Lexicon(titles=frozenset({"STRAßE", "Ph.D", "Dr."}))
    assert lex.titles == frozenset({"straße", "ph.d", "dr"})


def test_normalization_preserves_spellings_casefold_would_mutate() -> None:
    # lower(), not casefold(): casefold's caseless-matching folds would
    # rewrite stored vocabulary -- Greek final sigma flattens ('κος' ->
    # the misspelling 'κοσ') and German ß expands ('großfürst' ->
    # 'grossfürst'). lower() follows Unicode SpecialCasing contextually
    # ('ΚΟΣ' -> 'κος') and keeps entries as authored, matching v1's lc().
    lex = Lexicon(titles=frozenset({"ΚΟΣ", "Großfürst"}))
    assert lex.titles == frozenset({"κος", "großfürst"})


def test_suffix_ambiguous_must_be_subset_of_acronyms() -> None:
    # same invariant as particles_ambiguous <= particles: the ambiguous
    # set marks a subset of suffix_acronyms, and classify's period gate
    # depends on the membership tests agreeing about it
    with pytest.raises(ValueError, match="subset"):
        Lexicon(suffix_acronyms_ambiguous=frozenset({"ma"}))


def test_given_name_titles_may_hold_a_multi_word_phrase() -> None:
    # given_name_titles is looked up against the SPACE-JOINED title run
    # (_pipeline/_post_rules.py), not per token, so "grand duke" is a
    # legitimate entry. Its words must be titles -- that is what makes
    # the run a title in the first place -- but the phrase itself is
    # not, and must not be required to be.
    lex = Lexicon(titles=frozenset({"grand", "duke"}),
                  given_name_titles=frozenset({"grand duke"}))
    assert "grand duke" in lex.given_name_titles


@pytest.mark.parametrize("spelling", ["lt. col", "lt col", "Lt.  Col."])
def test_given_name_titles_folds_per_word_so_abbreviations_match(
        spelling: str) -> None:
    # The key is built per word and rejoined, so an abbreviated entry
    # has to fold the same way the parse folds the title run. Storing
    # 'lt. col' verbatim kept the interior period and matched nothing --
    # a silent no-op on the config surface, the failure this field is
    # most prone to (it has no validation by design).
    base = Lexicon.default()
    lex = dataclasses.replace(
        base,
        titles=base.titles | {"lt", "col"},
        given_name_titles=base.given_name_titles | {spelling})
    assert "lt col" in lex.given_name_titles
    assert Parser(lexicon=lex).parse("Lt. Col. Smith").given == "Smith"


@pytest.mark.parametrize("entry", ["lt .", "lt . col", ". col", ". ."])
def test_given_name_titles_fold_is_a_fixed_point(entry: str) -> None:
    # Storage re-runs the fold on unpickle and on every
    # dataclasses.replace, so a value that changes under a second pass
    # is one Lexicon later rejects as "not written by this version".
    once = _title_key(entry.split())
    assert _title_key(once.split()) == once
    assert once == once.strip() and "  " not in once


def test_a_title_word_that_folds_away_leaves_no_gap() -> None:
    # 'lt .' stored 'lt' before this field folded per word. A per-word
    # join that keeps the empty slot stores 'lt ', which match time can
    # never build -- silently inert config, the exact failure the
    # per-word fold was introduced to remove.
    base = Lexicon.default()
    lex = dataclasses.replace(
        base, titles=base.titles | {"lt", "col"},
        given_name_titles=base.given_name_titles | {"lt ."})
    assert "lt" in lex.given_name_titles
    assert Parser(lexicon=lex).parse("Lt. John").given == "John"


def test_the_constructor_and_add_store_an_entry_identically() -> None:
    # add() goes through dataclasses.replace, which re-runs
    # __post_init__ -- a non-idempotent fold converges there and not in
    # the constructor, so the two paths silently disagree.
    base = dataclasses.replace(Lexicon.default(),
                               titles=Lexicon.default().titles | {"lt", "col"})
    built = dataclasses.replace(
        base, given_name_titles=base.given_name_titles | {"lt . col"})
    assert built.given_name_titles == base.add(
        given_name_titles={"lt . col"}).given_name_titles


def test_an_all_punctuation_given_name_title_is_rejected() -> None:
    # every other vocab field raises on this; this one must not be
    # special just because it folds per word
    with pytest.raises(ValueError, match="normalizes to empty"):
        Lexicon(given_name_titles=frozenset({". ."}))


def test_given_name_titles_is_not_constrained_against_titles() -> None:
    # Deliberately unvalidated. The lookup key is the joined run of
    # Role.TITLE tokens, which the PARSE builds, and a conjunction
    # inside a run is title-tagged too -- so "sir and dame" is a
    # matchable key whose middle word is a conjunction, not a title.
    # A per-word check rejected it; a whole-entry check rejected
    # multi-word entries. An unreachable entry is inert rather than
    # harmful, so nothing is rejected here.
    assert Lexicon(titles=frozenset({"sir", "dame"}),
                   given_name_titles=frozenset({"sir and dame"}))
    # and an entry nothing will ever consult is accepted, not rejected
    assert Lexicon(given_name_titles=frozenset({"zzqnotatitle"}))


@pytest.mark.parametrize(("make", "marker", "base"), [
    (lambda w: Lexicon(particles_ambiguous=w),
     "particles_ambiguous", "particles"),
    (lambda w: Lexicon(suffix_acronyms_ambiguous=w),
     "suffix_acronyms_ambiguous", "suffix_acronyms"),
], ids=["particles_ambiguous", "suffix_acronyms_ambiguous"])
def test_subset_error_names_the_fix(
    make: Callable[[frozenset[str]], Lexicon], marker: str, base: str
) -> None:
    # the constraint alone leaves the reader to infer the remedy, and
    # the remedy is direction-dependent: a caller who was ADDING wants
    # to add to the base, one who was REMOVING wants to drop from the
    # marker. Naming both keeps the message right either way.
    with pytest.raises(ValueError, match=f"Add them to {base}, or drop "
                                         f"them from {marker}"):
        make(frozenset({"zzqnovel"}))


def test_bound_given_name_that_is_a_particle_must_be_ambiguous() -> None:
    # nameparser/config/prefixes.py asserts this on its own data:
    # NON_FIRST_NAME_PREFIXES stays disjoint from BOUND_FIRST_NAMES. In
    # 2.0's complement model that reads as bound_given_names & particles
    # <= particles_ambiguous. A particle declared never-to-start-a-given-
    # name cannot simultaneously bind one; without the check, one of the
    # two contradictory declarations is silently discarded.
    with pytest.raises(ValueError, match="particles_ambiguous"):
        Lexicon(particles=frozenset({"dos"}),
                particles_ambiguous=frozenset(),
                bound_given_names=frozenset({"dos"}))


def test_bound_given_name_may_overlap_an_ambiguous_particle() -> None:
    # the shipped case: "abu" is both, and legitimately so
    lex = Lexicon(particles=frozenset({"abu"}),
                  particles_ambiguous=frozenset({"abu"}),
                  bound_given_names=frozenset({"abu"}))
    assert "abu" in lex.bound_given_names
    # and a bound name that is not a particle at all is unconstrained
    assert "abdul" in Lexicon(bound_given_names=frozenset({"abdul"})
                              ).bound_given_names


def test_default_lexicon_satisfies_the_bound_particle_invariant() -> None:
    d = Lexicon.default()
    assert not (d.bound_given_names & d.particles) - d.particles_ambiguous


def test_removing_a_title_leaves_its_given_name_marker_alone() -> None:
    # the mirror of the above: removing from titles does not raise, and
    # the now-inert marker entry simply stops being reachable
    lex = Lexicon(titles=frozenset({"sheikh"}),
                  given_name_titles=frozenset({"sheikh"}))
    lean = lex.remove(titles={"sheikh"})
    assert lean.titles == frozenset()
    assert lean.given_name_titles == frozenset({"sheikh"})


@pytest.mark.parametrize("word", [
    "dr.", " Dr. ", ". a .", ".  .", "..x..", "  .b.  ",
])
def test_normalize_reaches_a_fixed_point(word: str) -> None:
    # strip() then strip(".") leaves periods-around-whitespace half
    # done: '. a .' -> ' a ' -> 'a'. Anything that stores a normalized
    # value and later re-normalizes it (unpickling, a second add) then
    # sees the value change under it, so the fold has to converge.
    once = _normalize(word)
    assert _normalize(once) == once


def test_unpickling_revalidates_invariants() -> None:
    # the field-layout guard catches SHAPE skew, but the likeliest skew
    # is same-name/flipped-meaning: particles_ambiguous inverted sense
    # between v1's never-given set and v2's may-be-given set. A state
    # dict that violates an invariant must not load in silence.
    lex = Lexicon(particles=frozenset({"van"}),
                  particles_ambiguous=frozenset({"van"}))
    state = lex.__getstate__()
    state["particles"] = frozenset()          # orphans particles_ambiguous
    forged = Lexicon.__new__(Lexicon)
    with pytest.raises(ValueError, match="particles_ambiguous"):
        forged.__setstate__(state)


def test_unpickling_rejects_unnormalized_entries() -> None:
    # a genuine pickle always holds normalized entries, so state that
    # does not is foreign. Correcting it silently would make the load
    # path a fourth place where caller data is rewritten without a
    # word; say so instead, at the site that can still name the entry.
    lex = Lexicon(titles=frozenset({"dr"}))
    state = lex.__getstate__()
    state["titles"] = {"Sir ", "DR."}
    restored = Lexicon.__new__(Lexicon)
    with pytest.raises(ValueError, match="not normalized"):
        restored.__setstate__(state)


def test_unpickling_rejects_uncanonical_capitalization_exceptions() -> None:
    # the pair field gets the same treatment as the vocab sets: it is
    # re-canonicalized by __post_init__ (normalized keys, sorted,
    # deduped), so accepting a rewritten value would leave one field
    # silently corrected while ten raise
    lex = Lexicon(capitalization_exceptions=(("phd", "PhD"),))
    state = lex.__getstate__()
    state["capitalization_exceptions"] = ((" PhD. ", "Ph.D."), ("aa", "AA"))
    restored = Lexicon.__new__(Lexicon)
    with pytest.raises(ValueError, match="not normalized"):
        restored.__setstate__(state)


def test_unpickling_a_real_pickle_is_the_identity() -> None:
    # the corollary: anything this library produced round-trips
    # unchanged, including entries whose normalized form needed more
    # than one strip pass to converge
    for lex in (Lexicon.default(), Lexicon.empty(),
                Lexicon(titles=frozenset({". a ."}))):
        assert pickle.loads(pickle.dumps(lex)) == lex


def test_remove_error_offers_the_removal_remedy_too() -> None:
    # a caller removing from the base does not want to be told to add
    # it back; the message names both directions
    lex = Lexicon(particles=frozenset({"van"}),
                  particles_ambiguous=frozenset({"van"}))
    with pytest.raises(ValueError,
                       match="drop them from particles_ambiguous"):
        lex.remove(particles={"van"})
