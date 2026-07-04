from nameparser import HumanName
from tests.base import HumanNameTestBase


class BoundFirstNamesTestCase(HumanNameTestBase):

    def test_is_bound_first_name_true(self) -> None:
        hn = HumanName("test")
        assert hn.is_bound_first_name("Abdul")

    def test_is_bound_first_name_false(self) -> None:
        hn = HumanName("test")
        assert not hn.is_bound_first_name("Ahmed")

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

    # --- opt-out ---
    def test_opt_out_via_clear(self) -> None:
        """Clearing bound_first_names restores prior behavior."""
        from nameparser.config import Constants
        c = Constants(bound_first_names=set())
        hn = HumanName("abdul salam ahmed salem", constants=c)
        self.m(hn.first, "abdul", hn)
        self.m(hn.middle, "salam ahmed", hn)
        self.m(hn.last, "salem", hn)

