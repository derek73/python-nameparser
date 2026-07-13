from nameparser._lexicon import Lexicon
from nameparser._pipeline import run
from nameparser._pipeline._assemble import assemble
from nameparser._pipeline._state import ParseState
from nameparser._policy import Policy
from nameparser._types import AmbiguityKind, ParsedName

_LEX = Lexicon(
    titles=frozenset({"dr"}),
    particles=frozenset({"de", "la", "van"}),
    particles_ambiguous=frozenset({"van"}),
    suffix_words=frozenset({"iii"}),
    maiden_markers=frozenset({"née"}),
)


def _parse(text: str) -> ParsedName:
    return assemble(run(ParseState(original=text, lexicon=_LEX,
                                   policy=Policy())))


def test_assemble_produces_validated_parsedname() -> None:
    pn = _parse("Dr. Juan de la Vega III")
    assert pn.title == "Dr."
    assert pn.given == "Juan"
    assert pn.family == "de la Vega"
    assert pn.family_base == "Vega"          # particle tags carried over
    assert pn.family_particles == "de la"
    assert pn.suffix == "III"
    assert pn.original == "Dr. Juan de la Vega III"
    for t in pn.tokens:
        assert t.span is not None
        assert t.text == pn.original[t.span.start:t.span.end]


def test_assemble_materializes_ambiguities_on_final_tokens() -> None:
    pn = _parse("Van Johnson")
    assert len(pn.ambiguities) == 1
    amb = pn.ambiguities[0]
    assert amb.kind is AmbiguityKind.PARTICLE_OR_GIVEN
    assert amb.tokens[0] is pn.tokens[0]


def test_assemble_drops_structural_marker_tokens() -> None:
    pn = _parse("Jane Smith née Jones")
    assert [t.text for t in pn.tokens] == ["Jane", "Smith", "Jones"]
    assert pn.maiden == "Jones"


def test_empty_parse_is_falsy() -> None:
    assert not _parse("")
    assert not _parse("   ")
