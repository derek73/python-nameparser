import dataclasses

import pytest

from nameparser._lexicon import Lexicon


def test_entries_are_normalized_at_construction():
    lex = Lexicon(titles={"Dr.", "MR"})
    assert lex.titles == frozenset({"dr", "mr"})


def test_default_sources_v1_vocabulary():
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


def test_default_is_cached_single_instance():
    assert Lexicon.default() is Lexicon.default()


def test_particles_ambiguous_must_be_subset_of_particles():
    with pytest.raises(ValueError, match="subset"):
        Lexicon(particles_ambiguous={"van"})


def test_capitalization_exceptions_canonical_and_no_aliasing():
    exceptions = {"phd": "PhD", "ii": "II"}
    lex = Lexicon.empty()
    lex2 = dataclasses.replace(lex, capitalization_exceptions=exceptions)
    exceptions["iii"] = "III"  # mutate caller's dict afterwards
    assert "iii" not in lex2.capitalization_exceptions_map
    # canonical: insertion order does not affect equality/hash
    lex3 = dataclasses.replace(lex, capitalization_exceptions={"ii": "II", "phd": "PhD"})
    assert lex2 == lex3 and hash(lex2) == hash(lex3)


def test_lexicon_is_hashable():
    assert isinstance(hash(Lexicon.default()), int)


def test_lexicon_rejects_bare_string_vocab():
    with pytest.raises(ValueError, match="bare string"):
        Lexicon(titles="dr")  # type: ignore[arg-type]


def test_lexicon_rejects_non_str_vocab_entries():
    with pytest.raises(ValueError, match="entries must be strings"):
        Lexicon(titles={"Dr.", 42})  # type: ignore[arg-type]


def test_colliding_exception_keys_dedupe_last_wins():
    lex = Lexicon(capitalization_exceptions={"Ph.D.": "A", "phd": "B"})
    assert lex.capitalization_exceptions == (("phd", "B"),)
    rebuilt = Lexicon(capitalization_exceptions=lex.capitalization_exceptions_map)
    assert rebuilt == lex and hash(rebuilt) == hash(lex)


def test_lexicon_rejects_non_str_exception_values():
    with pytest.raises(ValueError, match="str -> str"):
        Lexicon(capitalization_exceptions={"phd": 42})  # type: ignore[dict-item]


def test_add_and_remove_return_new_lexicons():
    # "zqtitle" is a synthetic word absent from v1's TITLES data (unlike
    # e.g. "dra", the feminine "dr." abbreviation, which is already there).
    base = Lexicon.default()
    lex = base.add(titles={"zqtitle"}).remove(suffix_words={"bishop"})
    assert "zqtitle" in lex.titles and "zqtitle" not in base.titles
    assert "bishop" not in lex.suffix_words


def test_add_unknown_field_raises_with_valid_names():
    with pytest.raises(TypeError, match="prefixes"):
        Lexicon.default().add(prefixes={"van"})  # v1 name: helpful error


def test_add_capitalization_exceptions_raises_pointing_at_replace():
    with pytest.raises(TypeError, match="dataclasses.replace"):
        Lexicon.default().add(capitalization_exceptions={"x": "X"})


def test_union_is_fieldwise_and_right_biased_for_exceptions():
    a = dataclasses.replace(Lexicon.empty(),
                            capitalization_exceptions={"phd": "PhD"})
    a = a.add(titles={"dr"})
    b = dataclasses.replace(Lexicon.empty(),
                            capitalization_exceptions={"phd": "Ph.D."})
    b = b.add(titles={"mr"})
    u = a | b
    assert u.titles == frozenset({"dr", "mr"})
    assert u.capitalization_exceptions_map["phd"] == "Ph.D."  # right wins


def test_remove_breaking_subset_invariant_raises():
    lex = Lexicon(particles={"van"}, particles_ambiguous={"van"})
    with pytest.raises(ValueError, match="subset"):
        lex.remove(particles={"van"})  # would orphan particles_ambiguous
