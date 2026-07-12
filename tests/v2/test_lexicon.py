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
