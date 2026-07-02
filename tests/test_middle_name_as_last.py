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
