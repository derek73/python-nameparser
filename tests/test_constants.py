import dataclasses

from nameparser import Lexicon, Parser, parse

from tests.base import ParsedNameTestBase


class LexiconCustomizationTests(ParsedNameTestBase):

    def test_add_title(self) -> None:
        lexicon = Lexicon.default().add(titles={'te'})
        self.assertEqual(len(Lexicon.default().titles) + 1, len(lexicon.titles))
        hn = Parser(lexicon=lexicon).parse("Te Awanui-a-Rangi Black")
        self.m(hn.title, "Te", hn)
        self.m(hn.given, "Awanui-a-Rangi", hn)
        self.m(hn.family, "Black", hn)

    def test_remove_title(self) -> None:
        lexicon = Lexicon.default().remove(titles={'hon'})
        self.assertEqual(len(Lexicon.default().titles) - 1, len(lexicon.titles))
        hn = Parser(lexicon=lexicon).parse("Hon Solo")
        self.m(hn.given, "Hon", hn)
        self.m(hn.family, "Solo", hn)

    def test_add_multiple_arguments(self) -> None:
        lexicon = Lexicon.default().add(titles={'dean', 'Chemistry'})
        hn = Parser(lexicon=lexicon).parse("Assoc Dean of Chemistry Robert Johns")
        self.m(hn.title, "Assoc Dean of Chemistry", hn)
        self.m(hn.given, "Robert", hn)
        self.m(hn.family, "Johns", hn)

    def test_remove_multiple_arguments(self) -> None:
        lexicon = Lexicon.default().remove(titles={'hon', 'ms'})
        hn = Parser(lexicon=lexicon).parse("Ms Hon Solo")
        self.m(hn.given, "Ms", hn)
        self.m(hn.middle, "Hon", hn)
        self.m(hn.family, "Solo", hn)

    def test_chain_multiple_arguments(self) -> None:
        lexicon = Lexicon.default().remove(titles={'hon', 'ms'}).add(titles={'dean'})
        hn = Parser(lexicon=lexicon).parse("Dean Ms Hon Solo")
        self.m(hn.title, "Dean", hn)
        self.m(hn.given, "Ms", hn)
        self.m(hn.middle, "Hon", hn)
        self.m(hn.family, "Solo", hn)

    def test_clear_removes_all_entries(self) -> None:
        lexicon = dataclasses.replace(Lexicon.default(), titles=frozenset())
        hn = Parser(lexicon=lexicon).parse("Ms Hon Solo")
        self.m(hn.given, "Ms", hn)
        self.m(hn.middle, "Hon", hn)
        self.m(hn.family, "Solo", hn)


class JoinedPieceTests(ParsedNameTestBase):
    """The parser derives joined pieces within a parse (period-joined
    titles/suffixes like "Lt.Gov.", conjunction-joined pieces like
    "Mr. and Mrs." or "von und zu")."""

    def test_period_joined_title(self) -> None:
        hn = parse("Lt.Gov. John Doe")
        self.m(hn.title, "Lt.Gov.", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Doe", hn)

    def test_period_joined_suffix(self) -> None:
        hn = parse("John Doe JD.CPA")
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Doe", hn)
        self.m(hn.suffix, "JD.CPA", hn)

    def test_joined_conjunctions(self) -> None:
        hn = parse("Louis of the Netherlands")
        self.m(hn.given, "Louis of the Netherlands", hn)

    def test_title_conjunction_join(self) -> None:
        hn = parse("Mr. and Mrs. John Smith")
        self.m(hn.title, "Mr. and Mrs.", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Smith", hn)

    def test_prefix_conjunction_join(self) -> None:
        hn = parse("Alois von und zu Liechtenstein")
        self.m(hn.given, "Alois", hn)
        self.m(hn.family, "von und zu Liechtenstein", hn)

    def test_derivations_reset_between_parses(self) -> None:
        # each parse must re-derive from a clean slate and still resolve
        # the period-joined title
        parse("Lt.Gov. John Doe")
        hn = parse("Lt.Gov. Jane Roe")
        self.m(hn.title, "Lt.Gov.", hn)
        self.m(hn.given, "Jane", hn)
        self.m(hn.family, "Roe", hn)
