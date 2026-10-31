import json
import subprocess
import sys

import pytest

import nameparser.locales
from nameparser import FAMILY_FIRST, Lexicon, Locale, PolicyPatch
from nameparser import __main__ as cli
from nameparser import _locale


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "nameparser", *args],
                          capture_output=True, text=True)


def test_cli_prints_repr_capitalized_and_initials() -> None:
    out = _run("dr. juan de la vega iii").stdout
    assert "juan" in out                      # raw repr first
    assert "Juan" in out                      # capitalized repr second
    assert "Initials:" in out


def test_cli_labels_each_section() -> None:
    # two of the three outputs were unlabeled ParsedName reprs, and for
    # already-cased input they are byte-identical -- the reader cannot
    # tell which is the parse and which is the capitalized view
    out = _run("Dr. Juan de la Vega III").stdout
    assert out.count("<ParsedName:") == 2     # still both shown
    assert "Parsed:" in out
    assert "Capitalized:" in out
    assert out.index("Parsed:") < out.index("Capitalized:")


def test_cli_json() -> None:
    proc = _run("John Smith", "--json")
    data = json.loads(proc.stdout)
    assert data["given"] == "John" and data["family"] == "Smith"


def test_cli_no_args_usage() -> None:
    proc = _run()
    assert proc.returncode != 0


def test_cli_locale() -> None:
    proc = _run("Сидоров Иван Петрович", "--locale", "ru")
    assert proc.returncode == 0
    assert "Иван" in proc.stdout

    proc = _run("Сидоров Иван Петрович", "--locale", "ru", "--json")
    data = json.loads(proc.stdout)
    assert "Иван" in data["given"]


def test_cli_locale_unknown_code_lists_available() -> None:
    proc = _run("John Smith", "--locale", "xx")
    assert proc.returncode != 0
    assert "ru" in proc.stderr and "tr_az" in proc.stderr


def test_cli_locale_empty_string_errors_not_silent_default() -> None:
    # --locale "" is a mistake (empty shell variable, typo), not a
    # request for the default parser; a truthiness check would swallow
    # it silently -- it must error like any other unknown code
    proc = _run("John Smith", "--locale", "")
    assert proc.returncode != 0
    assert "ru" in proc.stderr and "tr_az" in proc.stderr


def test_cli_locale_ja_activates_nothing_by_itself() -> None:
    # usage.rst's claim, pinned at the layer it is about: the CLI takes
    # the pack but has no way to attach a segmenter, and the ja pack
    # ships no vocabulary -- so --locale ja is byte-identical to the
    # default parser on the very name the pack exists to divide. A
    # future --segmenter flag, or a pack that grew a surname list,
    # would land here first.
    packed = _run("山田太郎", "--locale", "ja")
    default = _run("山田太郎")
    assert packed.returncode == 0
    assert packed.stdout == default.stdout


def _fields(capsys: pytest.CaptureFixture[str], *argv: str) -> dict[str, str]:
    # in process, unlike _run: fast, and the warning tests can see what
    # main() emits
    assert cli.main([*argv, "--json"]) == 0
    result: dict[str, str] = json.loads(capsys.readouterr().out)
    return result


def _roles(fields: dict[str, str]) -> tuple[str, str, str]:
    return fields["given"], fields["middle"], fields["family"]


@pytest.mark.parametrize(("order", "roles"), [
    ("given-first", ("Kovács", "János", "Péter")),
    ("family-first", ("János", "Péter", "Kovács")),
    ("family-first-given-last", ("Péter", "János", "Kovács")),
])
def test_cli_order_reads_the_words_in_that_order(
        capsys: pytest.CaptureFixture[str],
        order: str, roles: tuple[str, str, str]) -> None:
    assert _roles(_fields(capsys, "--order", order,
                          "Kovács János Péter")) == roles


def test_cli_order_keeps_the_locale_packs_vocabulary_and_policy(
        capsys: pytest.CaptureFixture[str]) -> None:
    # es reads Lic as a title (the pack's lexicon); cs reads two family
    # names (its policy), which a parser rebuilt from the order alone
    # would lose: family 'Novák', given 'Jan', middle 'Petr'
    es = _fields(capsys, "--locale", "es", "--order", "family-first",
                 "Lic Kovács János")
    assert (es["title"], es["given"], es["family"]) == (
        "Lic", "János", "Kovács")
    cs = _fields(capsys, "--locale", "cs", "--order", "family-first",
                 "Novák Jan Petr")
    assert _roles(cs) == ("Petr", "", "Novák Jan")


def test_cli_order_wins_over_a_packs_order(
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch) -> None:
    # no shipped pack sets name_order, so a stand-in does
    pack = Locale(code="xx", lexicon=Lexicon.empty(),
                  policy=PolicyPatch(name_order=FAMILY_FIRST))
    monkeypatch.setattr(nameparser.locales, "get", lambda code: pack)
    assert _fields(capsys, "--locale", "xx",
                   "Kovács János Péter")["family"] == "Kovács"
    assert _fields(capsys, "--locale", "xx", "--order", "given-first",
                   "Kovács János Péter")["family"] == "Péter"


def test_cli_order_leaves_a_han_name_in_its_scripts_order(
        capsys: pytest.CaptureFixture[str]) -> None:
    # Policy.script_orders reads a wholly-Han name family-first (rules/W4)
    fields = _fields(capsys, "--order", "given-first", "毛 泽东")
    assert (fields["given"], fields["family"]) == ("泽东", "毛")


def test_cli_order_with_a_locale_warns_once_from_main() -> None:
    # the parser is built once, by parser_for, which re-emits the
    # segmenterless warning from its caller's frame (#337)
    with pytest.warns(UserWarning, match="segment_scripts") as record:
        assert cli.main(["--locale", "ja", "--order", "family-first",
                         "--json", "高橋一郎"]) == 0
    assert len(record) == 1
    assert record[0].filename == cli.__file__


def test_cli_order_unknown_value_exits_2_listing_the_choices(
        capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--order", "sideways", "Jane Doe"])
    assert exc.value.code == 2
    assert "family-first-given-last" in capsys.readouterr().err


def test_cli_order_spellings_match_the_vocabulary_rules_tables() -> None:
    assert cli._ORDERS == _locale._ORDERS
