from nameparser import HumanName
from nameparser.config import Constants
from tests.base import HumanNameTestBase


class MiddleNameAsLastFlagTests(HumanNameTestBase):

    def test_default_is_false(self) -> None:
        C = Constants()
        assert C.middle_name_as_last is False

    def test_can_set_true_via_constructor(self) -> None:
        C = Constants(middle_name_as_last=True)
        assert C.middle_name_as_last is True

    def test_does_not_affect_other_instance(self) -> None:
        C1 = Constants(middle_name_as_last=True)
        C2 = Constants()
        assert C1.middle_name_as_last is True
        assert C2.middle_name_as_last is False


class MiddleNameAsLastFoldTests(HumanNameTestBase):

    def setup_method(self) -> None:
        self.C = Constants(middle_name_as_last=True)

    def hn(self, name: str) -> HumanName:
        return HumanName(name, constants=self.C)

    def test_fold_no_comma(self) -> None:
        n = self.hn("Mohamad Ahmad Ali Hassan")
        self.m(n.first, "Mohamad", n)
        self.m(n.middle, "", n)
        self.m(n.last, "Ahmad Ali Hassan", n)

    def test_fold_comma_converges(self) -> None:
        no_comma = self.hn("Mohamad Ahmad Ali Hassan")
        comma = self.hn("Hassan, Mohamad Ahmad Ali")
        self.m(comma.first, no_comma.first, comma)
        self.m(comma.last, no_comma.last, comma)

    def test_title_and_suffix_preserved(self) -> None:
        n = self.hn("Dr. Mohamad Ahmad Hassan Jr")
        self.m(n.title, "Dr.", n)
        self.m(n.last, "Ahmad Hassan", n)
        self.m(n.suffix, "Jr", n)

    def test_no_middle_is_noop(self) -> None:
        n = self.hn("John Doe")
        self.m(n.first, "John", n)
        self.m(n.middle, "", n)
        self.m(n.last, "Doe", n)

    def test_single_token_is_noop(self) -> None:
        n = self.hn("Cher")
        self.m(n.first, "Cher", n)
        self.m(n.last, "", n)

    def test_given_names_and_surnames_track_fold(self) -> None:
        n = self.hn("Mohamad Ahmad Ali Hassan")
        self.m(n.given_names, n.first, n)
        self.m(n.surnames, n.last, n)

    def test_last_prefixes_still_split_after_fold(self) -> None:
        # Unfolded this is first="Miguel", middle="da Silva do Amaral",
        # last="de Souza" (last_prefixes="de"). Folded, last_list becomes
        # ["da","Silva","do","Amaral","de","Souza"]; _split_last() strips
        # leading contiguous prefix words from the start, so only the
        # leading "da" is stripped ("Silva" is not a prefix, so scanning
        # stops there) — last_prefixes="da", not "de".
        n = self.hn("Miguel da Silva do Amaral de Souza")
        self.m(n.last_prefixes, "da", n)


class MiddleNameAsLastFlagOffTests(HumanNameTestBase):

    def test_default_constants_unaffected(self) -> None:
        n = HumanName("Mohamad Ahmad Ali Hassan")
        self.m(n.middle, "Ahmad Ali", n)
        self.m(n.last, "Hassan", n)
