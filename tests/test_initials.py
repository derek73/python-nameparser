from nameparser import HumanName
from nameparser.config import Constants

from tests.base import HumanNameTestBase


class InitialsTestCase(HumanNameTestBase):
    def test_initials(self) -> None:
        hn = HumanName("Andrew Boris Petersen")
        self.m(hn.initials(), "A. B. P.", hn)

    def test_initials_simple_name(self) -> None:
        hn = HumanName("John Doe")
        self.m(hn.initials(), "J. D.", hn)
        hn = HumanName("John Doe", initials_format="{first} {last}")
        self.m(hn.initials(), "J. D.", hn)
        hn = HumanName("John Doe", initials_format="{last}")
        self.m(hn.initials(), "D.", hn)
        hn = HumanName("John Doe", initials_format="{first}")
        self.m(hn.initials(), "J.", hn)
        hn = HumanName("John Doe", initials_format="{middle}")
        self.m(hn.initials(), "", hn)

    def test_initials_all_empty_renders_empty_string(self) -> None:
        # The v1 None display mode (and its literal-"None" interpolation
        # regressions) died with #255: a fully-empty result is now always
        # '', matching the first/last accessors.
        hn = HumanName("", constants=Constants())
        self.assertEqual(hn.initials(), "")

    def test_initials_with_an_attached_tussenvoegsel(self) -> None:
        # "Vega, Juan de la" used to park "de la" in the middle name; #379
        # attaches it to the family instead, so the initials come from
        # 'Juan' and the family BASE. The all-prefix MIDDLE this test
        # was written for now comes from "Nguyen, Van Le" below --
        # whether such a middle should exist at all is #402.
        hn = HumanName("Vega, Juan de la")
        self.m(hn.middle, "", hn)
        self.m(hn.last, "de la Vega", hn)
        self.assertEqual(hn.initials_list(), ["J", "V"])
        self.assertEqual(hn.initials(), "J. V.")

    def test_initials_middle_name_all_prefixes(self) -> None:
        # "Nguyen, Van Le" parses with middle name "Le", every word of
        # which is particle vocabulary. A particle standing alone in a
        # name part is not doing a particle's work there, so it
        # initials as an ordinary name word (rules.md#R2/#R3) rather
        # than being dropped -- this read "V. N." until #404, losing
        # the middle name entirely.
        hn = HumanName("Nguyen, Van Le")
        self.m(hn.middle, "Le", hn)
        self.assertEqual(hn.initials_list(), ["V", "L", "N"])
        self.assertEqual(hn.initials(), "V. L. N.")

    def test_initials_still_drop_a_particle_beside_a_name(self) -> None:
        # The other half: where the part HAS a name word, the particle
        # is doing particle work and contributes nothing.
        hn = HumanName("Juan de la Vega")
        self.m(hn.last, "de la Vega", hn)
        self.assertEqual(hn.initials(), "J. V.")

    def test_initials_complex_name(self) -> None:
        hn = HumanName("Doe, John A. Kenneth, Jr.")
        self.m(hn.initials(), "J. A. K. D.", hn)

    def test_initials_format(self) -> None:
        hn = HumanName("Doe, John A. Kenneth, Jr.", initials_format="{first} {middle}")
        self.m(hn.initials(), "J. A. K.", hn)
        hn = HumanName("Doe, John A. Kenneth, Jr.", initials_format="{first} {last}")
        self.m(hn.initials(), "J. D.", hn)
        hn = HumanName("Doe, John A. Kenneth, Jr.", initials_format="{middle} {last}")
        self.m(hn.initials(), "A. K. D.", hn)
        hn = HumanName("Doe, John A. Kenneth, Jr.", initials_format="{first}, {last}")
        self.m(hn.initials(), "J., D.", hn)

    # The *_constants tests below ran on the shared CONSTANTS singleton in
    # v1; 2.0 deprecates shared mutation, so they use a private Constants
    # passed as constants= (the migration-guide idiom) -- the config
    # attribute under test is the same either way.

    def test_initials_format_constants(self) -> None:
        c = Constants()
        c.initials_format = "{first} {last}"
        hn = HumanName("Doe, John A. Kenneth, Jr.", constants=c)
        self.m(hn.initials(), "J. D.", hn)
        c.initials_format = "{first}  {last}"
        hn = HumanName("Doe, John A. Kenneth, Jr.", constants=c)
        self.m(hn.initials(), "J. D.", hn)

    def test_initials_delimiter(self) -> None:
        hn = HumanName("Doe, John A. Kenneth, Jr.", initials_delimiter=";")
        self.m(hn.initials(), "J; A; K; D;", hn)

    def test_initials_delimiter_constants(self) -> None:
        c = Constants()
        c.initials_delimiter = ";"
        hn = HumanName("Doe, John A. Kenneth, Jr.", constants=c)
        self.m(hn.initials(), "J; A; K; D;", hn)

    def test_initials_list(self) -> None:
        hn = HumanName("Andrew Boris Petersen")
        self.m(hn.initials_list(), ["A", "B", "P"], hn)

    def test_initials_list_complex_name(self) -> None:
        hn = HumanName("Doe, John A. Kenneth, Jr.")
        self.m(hn.initials_list(), ["J", "A", "K", "D"], hn)

    def test_initials_with_prefix_firstname(self) -> None:
        hn = HumanName("Van Jeremy Johnson")
        self.m(hn.initials_list(), ["V", "J", "J"], hn)

    def test_initials_with_prefix(self) -> None:
        hn = HumanName("Alex van Johnson")
        self.m(hn.initials_list(), ["A", "J"], hn)

    def test_initials_delimiter_empty_string_kwarg(self) -> None:
        # Regression: initials_delimiter='' was silently ignored due to `or` defaulting
        hn = HumanName("Doe, John A.", initials_delimiter="")
        self.m(hn.initials(), "J A D", hn)

    def test_initials_format_empty_string_kwarg(self) -> None:
        # Regression: initials_format='' was silently ignored due to `or` defaulting
        hn = HumanName("Doe, John A.")
        hn2 = HumanName("Doe, John A.", initials_format="")
        self.assertNotEqual(hn.initials(), hn2.initials())
        # "".format(...) returns ""; collapse_whitespace returns "" which falls through
        # to empty_attribute_default (may be "" or None depending on config variant).
        self.assertFalse(hn2.initials())

    def test_initials_separator_kwarg(self) -> None:
        # initials_separator="" with initials_format="{first}{middle}{last}" gives
        # period-separated initials with no spaces — a common academic citation style
        hn = HumanName(
            "Doe, John A. Kenneth",
            initials_separator="",
            initials_format="{first}{middle}{last}",
        )
        self.m(hn.initials(), "J.A.K.D.", hn)

    def test_initials_separator_custom_value(self) -> None:
        # Non-empty custom separator exercising _process_initial on a multi-word
        # token. "Van Berg" is a single name part whose two words produce two initials
        # joined by initials_separator.
        hn = HumanName("", initials_separator="-", initials_delimiter=".")
        result = hn._process_initial("Van Berg", firstname=True)
        self.assertEqual(result, "V-B")

    def test_str_default_behavior_unchanged(self) -> None:
        # Regression guard for the `or` → `is not None` change in __str__:
        # the default path (no string_format kwarg) must still produce the expected string.
        hn = HumanName("John Doe")
        self.assertEqual(str(hn), "John Doe")

    def test_initials_with_doubled_space_in_list_element(self) -> None:
        # v1's #232 hole -- direct *_list assignment injecting unnormalized
        # elements that made initials raise IndexError -- is unreachable in
        # 2.0: *_list attributes are read-only snapshots (spec section 2
        # exc. 1) and the field setter normalizes whitespace, splitting a
        # doubled-space element into clean members.
        hn = HumanName(first="John")
        hn.middle = ["Q  R"]
        self.assertEqual(hn.middle_list, ["Q", "R"])
        self.assertEqual(hn.initials_list(), ["J", "Q", "R"])
        self.assertEqual(hn.initials(), "J. Q. R.")

    def test_constructor_first(self) -> None:
        hn = HumanName(first="TheName")
        self.m(hn.first, "TheName", hn)

    def test_constructor_middle(self) -> None:
        hn = HumanName(middle="TheName")
        self.m(hn.middle, "TheName", hn)

    def test_constructor_last(self) -> None:
        hn = HumanName(last="TheName")
        self.m(hn.last, "TheName", hn)

    def test_constructor_title(self) -> None:
        hn = HumanName(title="TheName")
        self.m(hn.title, "TheName", hn)

    def test_constructor_suffix(self) -> None:
        hn = HumanName(suffix="TheName")
        self.m(hn.suffix, "TheName", hn)

    def test_constructor_nickname(self) -> None:
        hn = HumanName(nickname="TheName")
        self.m(hn.nickname, "TheName", hn)

    def test_constructor_multiple(self) -> None:
        hn = HumanName(first="TheName", last="lastname", title="mytitle", full_name="donotparse")
        self.m(hn.first, "TheName", hn)
        self.m(hn.last, "lastname", hn)
        self.m(hn.title, "mytitle", hn)

    def test_initials_separator_kwarg_multiword_part(self) -> None:
        # Regression: initials_separator kwarg must flow into _process_initial
        # for multi-word name parts, not just into the initials() join calls.
        hn = HumanName("", initials_separator="")
        result = hn._process_initial("Van Berg", firstname=True)
        self.assertEqual(result, "VB")

    def test_string_format_empty_string_kwarg(self) -> None:
        # Regression: string_format='' was silently ignored due to `or` defaulting
        hn = HumanName("John Doe", string_format="")
        self.assertEqual(str(hn), "")

    def test_initials_separator_empty_multi_part_middle(self) -> None:
        # Full workflow from issue #152: empty delimiter + separator + compact format
        # gives fully concatenated initials with no spaces or punctuation.
        # Spaces between groups come from initials_format, so that must also be set.
        hn = HumanName(
            "Doe, John A. Kenneth",
            initials_delimiter="",
            initials_separator="",
            initials_format="{first}{middle}{last}",
        )
        self.m(hn.initials(), "JAKD", hn)

    def test_initials_separator_constants_multi_part_middle(self) -> None:
        c = Constants()
        c.initials_delimiter = ""
        c.initials_separator = ""
        c.initials_format = "{first}{middle}{last}"
        hn = HumanName("Doe, John A. Kenneth", constants=c)
        self.m(hn.initials(), "JAKD", hn)

    def test_initials_separator_default_on_constants(self) -> None:
        # The shared singleton's default must be untouched by the private-
        # Constants tests above (and, in file order, by anything the autouse
        # fixture restores).
        from nameparser.config import CONSTANTS
        self.assertEqual(CONSTANTS.initials_separator, " ")

    def test_initials_keep_an_initial_shaped_conjunction_letter(self) -> None:
        # #462: v1's is_conjunction was "in the set AND NOT
        # is_an_initial", so a dotted or bare-capital E/Y is the
        # initial it looks like, not the Italian/Spanish connective.
        # The 2.0 facade lost that exclusion and gave 'S. W.';
        # parse().initials() never had the bug. 1.4.0 parity, all four.
        for name, want in (("Scott E. Werner", "S. E. W."),
                           ("John E Smith", "J. E. S."),
                           ("Juan Y. Garcia", "J. Y. G."),
                           ("Хосе И. Мария Сантос", "Х. И. М. С.")):
            hn = HumanName(name)
            self.m(hn.initials(), want, hn)

    def test_initials_still_drop_a_lowercase_conjunction(self) -> None:
        # the boundary #462 leaves alone: a bare lowercase e/y IS the
        # connective, and 1.4.0 and 2.x agree
        hn = HumanName("john e smith")
        self.m(hn.initials(), "j. s.", hn)
        hn = HumanName("maria y lopez")
        self.m(hn.initials(), "m. l.", hn)
