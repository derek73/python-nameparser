import json

import pytest

from nameparser.__main__ import main


def _fields(capsys: pytest.CaptureFixture[str], *argv: str) -> dict[str, str]:
    assert main([*argv, "--json"]) == 0
    result: dict[str, str] = json.loads(capsys.readouterr().out)
    return result


@pytest.mark.parametrize(("order", "given", "middle", "family"), [
    ("given-first", "Kovács", "János", "Péter"),
    ("family-first", "János", "Péter", "Kovács"),
    ("family-first-given-last", "Péter", "János", "Kovács"),
])
def test_order_reads_the_words_in_that_order(
        capsys: pytest.CaptureFixture[str],
        order: str, given: str, middle: str, family: str) -> None:
    fields = _fields(capsys, "--order", order, "Kovács János Péter")
    assert (fields["given"], fields["middle"], fields["family"]) == (
        given, middle, family)


def test_without_order_the_default_is_given_first(
        capsys: pytest.CaptureFixture[str]) -> None:
    fields = _fields(capsys, "Kovács János Péter")
    assert (fields["given"], fields["family"]) == ("Kovács", "Péter")


def test_order_combines_with_a_locale(
        capsys: pytest.CaptureFixture[str]) -> None:
    # es reads Lic as a title; the order still places the name words
    fields = _fields(capsys, "--locale", "es", "--order", "family-first",
                     "Lic Kovács János")
    assert (fields["title"], fields["given"], fields["family"]) == (
        "Lic", "János", "Kovács")


def test_an_unknown_order_exits_2_listing_the_choices(
        capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--order", "sideways", "Jane Doe"])
    assert exc.value.code == 2
    assert "family-first-given-last" in capsys.readouterr().err


def test_an_unknown_locale_exits_2(
        capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--locale", "", "Jane Doe"])
    assert exc.value.code == 2


def test_default_output_labels_each_section(
        capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["dr. juan de la vega iii"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Parsed:\n")
    assert "\nCapitalized:\n" in out
    assert "\nInitials: j. v.\n" in out
