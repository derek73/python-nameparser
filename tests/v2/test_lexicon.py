import dataclasses

import pytest

from nameparser._lexicon import Lexicon


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
    # normalized -- only keys are casefolded/period-stripped at
    # construction, values pass through unchanged).
    assert lex.capitalization_exceptions_map["phd"] == "Ph.D."


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


def test_exception_keys_normalizing_to_empty_are_dropped() -> None:
    lex = Lexicon(capitalization_exceptions=(("...", "X"), ("phd", "PhD")))
    assert lex.capitalization_exceptions == (("phd", "PhD"),)


def test_colliding_exception_keys_dedupe_last_wins() -> None:
    lex = Lexicon(capitalization_exceptions=(("Ph.D.", "A"), ("phd", "B")))
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
    lex = base.add(titles={"zqtitle"}).remove(suffix_words={"bishop"})
    assert "zqtitle" in lex.titles and "zqtitle" not in base.titles
    assert "bishop" not in lex.suffix_words


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
