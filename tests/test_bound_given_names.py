from nameparser import HumanName
from tests.base import HumanNameTestBase


class BoundGivenNamesTestCase(HumanNameTestBase):
    # The v1 is_bound_first_name predicate is gone with the other v1 parsing
    # hooks (#280); the vocabulary's behavior is pinned through the parsing
    # tests below.

    # --- no-comma: basic joining ---
    def test_no_comma_basic_join(self) -> None:
        hn = HumanName("abdul salam ahmed salem")
        self.m(hn.first, "abdul salam", hn)
        self.m(hn.middle, "ahmed", hn)
        self.m(hn.last, "salem", hn)

    def test_no_comma_three_tokens_no_middle(self) -> None:
        hn = HumanName("abdul salam salem")
        self.m(hn.first, "abdul salam", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "salem", hn)

    def test_no_comma_guard_two_tokens_no_join(self) -> None:
        """Guard: only last name remains after prefix → no join."""
        hn = HumanName("abdul salam")
        self.m(hn.first, "abdul", hn)
        self.m(hn.last, "salam", hn)

    def test_no_comma_guard_suffix_not_swallowed(self) -> None:
        """Guard: prefix + one name + suffix — suffix must not become last."""
        hn = HumanName("abdul salam jr")
        self.m(hn.first, "abdul", hn)
        self.m(hn.last, "salam", hn)
        self.m(hn.suffix, "jr", hn)

    # --- lastname-comma path ---
    def test_lastname_comma_join(self) -> None:
        hn = HumanName("salem, abdul salam")
        self.m(hn.first, "abdul salam", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "salem", hn)

    def test_lastname_comma_join_with_middle(self) -> None:
        hn = HumanName("salem, abdul salam ahmed")
        self.m(hn.first, "abdul salam", hn)
        self.m(hn.middle, "ahmed", hn)
        self.m(hn.last, "salem", hn)

    # --- interaction with titles ---
    def test_title_kept_prefix_joins(self) -> None:
        hn = HumanName("Dr. abdul salam ahmed salem")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "abdul salam", hn)
        self.m(hn.middle, "ahmed", hn)
        self.m(hn.last, "salem", hn)

    # --- interaction with last-name prefixes ---
    def test_abu_bakr_al_baghdadi(self) -> None:
        """abu joins forward as first-prefix; al joins forward as last-prefix."""
        hn = HumanName("abu bakr al baghdadi")
        self.m(hn.first, "abu bakr", hn)
        self.m(hn.last, "al baghdadi", hn)

    # --- interaction with suffixes ---
    def test_suffix_kept_prefix_joins(self) -> None:
        hn = HumanName("abdul salam ahmed salem jr")
        self.m(hn.first, "abdul salam", hn)
        self.m(hn.middle, "ahmed", hn)
        self.m(hn.last, "salem", hn)
        self.m(hn.suffix, "jr", hn)

    # --- guard / no-op ---
    def test_mohamad_unchanged(self) -> None:
        """mohamad is deliberately not in bound_first_names."""
        hn = HumanName("Mohamad Ali Khalil")
        self.m(hn.first, "Mohamad", hn)
        self.m(hn.middle, "Ali", hn)
        self.m(hn.last, "Khalil", hn)

    def test_single_token_already_joined_unchanged(self) -> None:
        """abdulsalam is one token — not in the set, no join."""
        hn = HumanName("abdulsalam ahmed salem")
        self.m(hn.first, "abdulsalam", hn)
        self.m(hn.middle, "ahmed", hn)
        self.m(hn.last, "salem", hn)

    def test_prefix_alone_no_join(self) -> None:
        """Single-word name that is a prefix: nothing to join."""
        hn = HumanName("abdul")
        self.m(hn.first, "abdul", hn)

    def test_lastname_comma_prefix_only_no_join(self) -> None:
        """Prefix as sole post-comma token: nothing to join."""
        hn = HumanName("salem, abdul")
        self.m(hn.first, "abdul", hn)
        self.m(hn.last, "salem", hn)

    def test_mid_name_prefix_becomes_last_prefix(self) -> None:
        """abu in non-first position is handled as a last-name prefix, not first-name."""
        hn = HumanName("ahmed abu bakr")
        self.m(hn.first, "ahmed", hn)
        self.m(hn.last, "abu bakr", hn)

    # --- suffix-comma path ---
    def test_suffix_comma_join(self) -> None:
        hn = HumanName("Abdul Salam Hassan, MD")
        self.m(hn.first, "Abdul Salam", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Hassan", hn)
        self.m(hn.suffix, "MD", hn)

    def test_suffix_comma_join_with_middle(self) -> None:
        hn = HumanName("Abdul Salam Ahmed Salem, MD")
        self.m(hn.first, "Abdul Salam", hn)
        self.m(hn.middle, "Ahmed", hn)
        self.m(hn.last, "Salem", hn)
        self.m(hn.suffix, "MD", hn)

    def test_suffix_comma_guard_two_tokens_no_join(self) -> None:
        """Guard: only last name remains after prefix → no join, even with suffix comma."""
        hn = HumanName("Abdul Salam, MD")
        self.m(hn.first, "Abdul", hn)
        self.m(hn.last, "Salam", hn)
        self.m(hn.suffix, "MD", hn)

    def test_suffix_comma_title_kept_prefix_joins(self) -> None:
        hn = HumanName("Dr. Abdul Salam Hassan, MD")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Abdul Salam", hn)
        self.m(hn.last, "Hassan", hn)
        self.m(hn.suffix, "MD", hn)

    def test_suffix_comma_abu_bakr_al_baghdadi(self) -> None:
        """abu joins forward as first-prefix; al joins forward as last-prefix, even with suffix comma."""
        hn = HumanName("Abu Bakr Al Baghdadi, MD")
        self.m(hn.first, "Abu Bakr", hn)
        self.m(hn.last, "Al Baghdadi", hn)
        self.m(hn.suffix, "MD", hn)

    # --- opt-out ---
    def test_opt_out_via_clear(self) -> None:
        """Clearing bound_first_names restores prior behavior."""
        from nameparser.config import Constants
        c = Constants(bound_first_names=set())
        hn = HumanName("abdul salam ahmed salem", constants=c)
        self.m(hn.first, "abdul", hn)
        self.m(hn.middle, "salam ahmed", hn)
        self.m(hn.last, "salem", hn)

    # --- 'abd', which is also the postnominal ABD ---
    def test_abd_joins_the_word_after_it(self) -> None:
        """The spelling that writes the article separately."""
        hn = HumanName("abd Allah Smith")
        self.m(hn.first, "abd Allah", hn)
        self.m(hn.last, "Smith", hn)

    def test_abd_joins_after_a_family_comma(self) -> None:
        hn = HumanName("Smith, abd Allah")
        self.m(hn.first, "abd Allah", hn)
        self.m(hn.last, "Smith", hn)

    def test_abd_pairwise_like_abdul(self) -> None:
        """Joins ONCE: 'Rahman' pairs, 'Ahmed' stays a middle name."""
        hn = HumanName("abd Rahman Ahmed Salem")
        self.m(hn.first, "abd Rahman", hn)
        self.m(hn.middle, "Ahmed", hn)
        self.m(hn.last, "Salem", hn)

    def test_abd_joins_with_a_suffix_present(self) -> None:
        """The line this fix changes is a SUFFIX count, so the shapes
        that carry a real suffix piece are the ones it governs."""
        for text, suffix in (("abd Allah Smith jr", "jr"),
                             ("abd Allah Smith PhD", "PhD"),
                             ("abd Allah Smith, PhD", "PhD"),
                             ("abd Allah Smith III", "III")):
            hn = HumanName(text)
            self.m(hn.first, "abd Allah", hn)
            self.m(hn.middle, "", hn)
            self.m(hn.last, "Smith", hn)
            self.m(hn.suffix, suffix, hn)

    def test_both_readings_of_abd_in_one_name(self) -> None:
        """Position tells them apart -- the claim the collision rests
        on, in a single string: bound given name in front, postnominal
        behind."""
        hn = HumanName("abd Allah Smith ABD")
        self.m(hn.first, "abd Allah", hn)
        self.m(hn.last, "Smith", hn)
        self.m(hn.suffix, "ABD", hn)

    def test_abd_joins_behind_a_title(self) -> None:
        hn = HumanName("Dr. abd Allah Smith")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "abd Allah", hn)
        self.m(hn.last, "Smith", hn)

    def test_the_abd_postnominal_still_reads_as_a_suffix(self) -> None:
        """The collision: ABD is also All But Dissertation. Position
        tells the two apart, so neither reading had to be given up."""
        for text in ("Jane Smith ABD", "Jane Smith, ABD",
                     "Jane Smith A.B.D."):
            hn = HumanName(text)
            self.m(hn.first, "Jane", hn)
            self.m(hn.last, "Smith", hn)
            self.assertTrue(hn.suffix.upper().replace(".", "") == "ABD",
                            f"{text}: suffix={hn.suffix!r}")
