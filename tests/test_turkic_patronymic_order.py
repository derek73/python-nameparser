from nameparser import HumanName
from nameparser.config import Constants
from tests.base import HumanNameTestBase


class TurkicPatronymicNameOrderReorderTests(HumanNameTestBase):
    """Names that SHOULD be rotated when the flag is on."""

    def setup_method(self) -> None:
        self.C = Constants(patronymic_name_order=True)

    def hn(self, name: str) -> HumanName:
        return HumanName(name, constants=self.C)

    def test_oglu(self) -> None:
        n = self.hn("Aliyev Vusal Said oglu")
        assert n.first == "Vusal"
        assert n.middle == "Said oglu"
        assert n.last == "Aliyev"
