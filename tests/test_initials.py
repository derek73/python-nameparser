from nameparser import parse

from tests.base import ParsedNameTestBase


class InitialsTestCase(ParsedNameTestBase):
    def test_initials(self) -> None:
        hn = parse("Andrew Boris Petersen")
        self.m(hn.initials(), "A. B. P.", hn)

    def test_initials_simple_name(self) -> None:
        hn = parse("John Doe")
        self.m(hn.initials(), "J. D.", hn)
        self.m(hn.initials("{given} {family}"), "J. D.", hn)
        self.m(hn.initials("{family}"), "D.", hn)
        self.m(hn.initials("{given}"), "J.", hn)
        self.m(hn.initials("{middle}"), "", hn)

    def test_initials_all_empty_renders_empty_string(self) -> None:
        # The v1 None display mode (and its literal-"None" interpolation
        # regressions) died with #255: a fully-empty result is now always
        # '', matching the given/family accessors.
        hn = parse("")
        self.assertEqual(hn.initials(), "")

    def test_initials_with_an_attached_tussenvoegsel(self) -> None:
        # "Vega, Juan de la" used to park "de la" in the middle name; #379
        # attaches it to the family instead, so the initials come from
        # 'Juan' and the family BASE. The all-prefix MIDDLE this test
        # was written for now comes from "Nguyen, Van Le" below --
        # whether such a middle should exist at all is #402.
        hn = parse("Vega, Juan de la")
        self.m(hn.middle, "", hn)
        self.m(hn.family, "de la Vega", hn)
        self.assertEqual(hn.initials(), "J. V.")

    def test_initials_middle_name_all_prefixes(self) -> None:
        # "Nguyen, Van Le" parses with middle name "Le", every word of
        # which is particle vocabulary. A particle standing alone in a
        # name part is not doing a particle's work there, so it
        # initials as an ordinary name word (rules/R2/#R3) rather
        # than being dropped -- this read "V. N." until #404, losing
        # the middle name entirely.
        hn = parse("Nguyen, Van Le")
        self.m(hn.middle, "Le", hn)
        self.assertEqual(hn.initials(), "V. L. N.")

    def test_initials_still_drop_a_particle_beside_a_name(self) -> None:
        # The other half: where the part HAS a name word, the particle
        # is doing particle work and contributes nothing.
        hn = parse("Juan de la Vega")
        self.m(hn.family, "de la Vega", hn)
        self.assertEqual(hn.initials(), "J. V.")

    def test_initials_complex_name(self) -> None:
        hn = parse("Doe, John A. Kenneth, Jr.")
        self.m(hn.initials(), "J. A. K. D.", hn)

    def test_initials_format(self) -> None:
        hn = parse("Doe, John A. Kenneth, Jr.")
        self.m(hn.initials("{given} {middle}"), "J. A. K.", hn)
        self.m(hn.initials("{given} {family}"), "J. D.", hn)
        self.m(hn.initials("{middle} {family}"), "A. K. D.", hn)
        self.m(hn.initials("{given}, {family}"), "J., D.", hn)
        self.m(hn.initials("{given}  {family}"), "J. D.", hn)

    def test_initials_delimiter(self) -> None:
        hn = parse("Doe, John A. Kenneth, Jr.")
        self.m(hn.initials(delimiter=";"), "J; A; K; D;", hn)

    def test_initials_with_prefix_firstname(self) -> None:
        hn = parse("Van Jeremy Johnson")
        self.m(hn.initials(), "V. J. J.", hn)

    def test_initials_with_prefix(self) -> None:
        hn = parse("Alex van Johnson")
        self.m(hn.initials(), "A. J.", hn)

    def test_initials_delimiter_empty_string_kwarg(self) -> None:
        # Regression: an empty delimiter was silently ignored due to `or` defaulting
        hn = parse("Doe, John A.")
        self.m(hn.initials(delimiter=""), "J A D", hn)

    def test_initials_format_empty_string_kwarg(self) -> None:
        # Regression: an empty spec was silently ignored due to `or` defaulting
        hn = parse("Doe, John A.")
        self.assertNotEqual(hn.initials(), hn.initials(""))
        self.assertFalse(hn.initials(""))

    def test_initials_separator_kwarg(self) -> None:
        # separator="" with spec "{given}{middle}{family}" gives
        # period-separated initials with no spaces — a common academic citation style
        hn = parse("Doe, John A. Kenneth")
        self.m(hn.initials("{given}{middle}{family}", separator=""),
               "J.A.K.D.", hn)

    def test_string_format_empty_string_kwarg(self) -> None:
        # Regression: an empty format was silently ignored due to `or` defaulting
        hn = parse("John Doe")
        self.assertEqual(hn.render(""), "")

    def test_initials_separator_empty_multi_part_middle(self) -> None:
        # Full workflow from issue #152: empty delimiter + separator + compact format
        # gives fully concatenated initials with no spaces or punctuation.
        # Spaces between groups come from the spec, so that must also be set.
        hn = parse("Doe, John A. Kenneth")
        self.m(hn.initials("{given}{middle}{family}", delimiter="",
                           separator=""), "JAKD", hn)

    def test_initials_keep_an_initial_shaped_conjunction_letter(self) -> None:
        # #462: v1's is_conjunction was "in the set AND NOT
        # is_an_initial", so a dotted or bare-capital E/Y is the
        # initial it looks like, not the Italian/Spanish connective.
        # The 2.0 facade lost that exclusion and gave 'S. W.';
        # parse().initials() never had the bug. 1.4.0 parity, all four.
        for name, want in (("Scott E. Werner", "S. E. W."),
                           ("John E Smith", "J. E. S."),
                           ("Juan Y. Garcia", "J. Y. G."),
                           # the letter is the WHOLE middle group here,
                           # so before the fix the group yielded nothing
                           # and was dropped outright: 'S. V.', a name
                           # short of its middle rather than a letter
                           ("Vega, Santa de Y", "S. Y. V."),
                           ("Хосе И. Мария Сантос", "Х. И. М. С.")):
            hn = parse(name)
            self.m(hn.initials(), want, hn)

    def test_initials_drop_a_bare_non_ascii_conjunction_letter(self) -> None:
        # v1's bound, kept: _render._INITIAL is `^(\w\.|[A-Z])$`, so
        # its DOTTED half is Unicode-aware (the 'И.' above survives)
        # and its bare-capital half is ASCII-only. A bare Cyrillic 'И'
        # is therefore not initial-shaped, stays the connective, and
        # drops -- 'Х. М. С.' for a four-word name. #462 restored v1's
        # exclusion; it did not widen the shape v1 excluded on.
        hn = parse("Хосе Мария И Сантос")
        self.m(hn.initials(), "Х. М. С.", hn)

    def test_initials_follow_the_one_case_fork_on_both_letters(self) -> None:
        # The two halves of the fork. 'y' is not marked
        # as reading both ways, so in a name written wholly in one case
        # it is the connective and drops -- 1.4.0's answer, unmoved.
        # 'e' IS marked, so the same name shape reads it as an initial
        # and it contributes: parse(...).initials() has given
        # 'j. e. s.' since #383/#479; decisions/P8 and decisions/R3
        # carry the split and its closing.
        hn = parse("john e smith")
        self.m(hn.initials(), "j. e. s.", hn)
        # 'maria y lopez' moved with #461, not with the one-case fork:
        # its 'y' holds the middle part alone, so there is nothing
        # there for it to join and it initials like any other name
        # word. rules/R3 states the rule for all three groups and
        # decisions/R3 records what it costs. The letter's TAG is
        # unchanged -- a lowercase 'y' outside the marked set is still
        # the connective.
        hn = parse("maria y lopez")
        self.m(hn.initials(), "m. y. l.", hn)
        # These two are among #528's four movers, written once with
        # the letter mid-name and once at the end after a comma: both
        # give the same initials() answer by different routes.
        hn = parse("john e jones")
        self.m(hn.initials(), "j. e. j.", hn)
        hn = parse("jones, john e")
        self.m(hn.initials(), "j. e. j.", hn)
