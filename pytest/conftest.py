import pytest


@pytest.fixture(
    scope="module",
    autouse=True,
    params=["", None],
    ids=["empty_is_blank", "empty_is_None"],
)
def empty_attribute_value(request):
    """Run the entire test suite twice to vary CONSTANTS.empty_attribute_default.

    First run CONSTANTS.empty_attribute_default = ""
    Second run CONSTANTS.empty_attribute_default = None
    """
    from nameparser.config import CONSTANTS

    CONSTANTS.empty_attribute_default = request.param
