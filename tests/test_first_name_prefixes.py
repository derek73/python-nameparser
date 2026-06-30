from nameparser import HumanName
from nameparser.config import CONSTANTS

from tests.base import HumanNameTestBase


class FirstNamePrefixesTestCase(HumanNameTestBase):

    def test_default_set_contents(self) -> None:
        for word in ("abdul", "abdel", "abdal", "abu", "abou", "umm"):
            assert word in CONSTANTS.first_name_prefixes, f"{word!r} missing from first_name_prefixes"

    def test_is_first_name_prefix_true(self) -> None:
        hn = HumanName("test")
        assert hn.is_first_name_prefix("Abdul")

    def test_is_first_name_prefix_false(self) -> None:
        hn = HumanName("test")
        assert not hn.is_first_name_prefix("Ahmed")

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
        """mohamad is deliberately not in first_name_prefixes."""
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

    # --- opt-out ---
    def test_opt_out_via_clear(self) -> None:
        """Clearing first_name_prefixes restores prior behavior."""
        from nameparser.config import Constants
        c = Constants(first_name_prefixes=set())
        hn = HumanName("abdul salam ahmed salem", constants=c)
        self.m(hn.first, "abdul", hn)
        self.m(hn.middle, "salam ahmed", hn)
        self.m(hn.last, "salem", hn)
