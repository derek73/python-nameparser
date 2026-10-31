import importlib.util
import json
import subprocess
import sys
import warnings
from collections.abc import Callable

import pytest

import nameparser.locales
from nameparser import (
    FAMILY_FIRST,
    Lexicon,
    Locale,
    PolicyPatch,
    Segmentation,
    Segmenter,
)
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


def test_cli_order_unknown_value_exits_2_listing_the_choices(
        capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--order", "sideways", "Jane Doe"])
    assert exc.value.code == 2
    assert "family-first-given-last" in capsys.readouterr().err


def test_cli_order_spellings_match_the_vocabulary_rules_tables() -> None:
    assert cli._ORDERS == _locale._ORDERS


# --locale ja attaches the segmenter where namedivider is installed. The
# two subprocess runs are the real thing, each in the environment it
# needs (the extra one only in CI's ja-extra job); the in-process ones
# stand in for the install so every branch runs everywhere.

_JA_EXTRA = importlib.util.find_spec("namedivider") is not None
_JA_NOTE = "pip install 'nameparser[ja]'"


@pytest.mark.skipif(_JA_EXTRA, reason="the ja extra is installed")
def test_cli_locale_ja_without_the_extra_divides_nothing_and_says_why() -> None:
    packed = _run("山田太郎", "--locale", "ja")
    default = _run("山田太郎")
    assert packed.returncode == 0
    assert packed.stdout == default.stdout
    assert _JA_NOTE in packed.stderr
    assert "Warning" not in packed.stderr


@pytest.mark.skipif(not _JA_EXTRA, reason="needs the ja extra")
def test_cli_locale_ja_with_the_extra_divides() -> None:
    proc = _run("山田太郎", "--locale", "ja", "--json")
    assert proc.returncode == 0, proc.stderr
    fields = json.loads(proc.stdout)
    assert (fields["family"], fields["given"]) == ("山田", "太郎")
    assert proc.stderr == ""


def test_cli_ja_extra_check_agrees_with_the_environment() -> None:
    # the in-process tests below stand in for this check; the real one
    # must answer what the subprocess runs' skips assume
    assert cli._ja_extra_installed() is _JA_EXTRA


def _cut_after_two(text: str) -> Segmentation:
    return Segmentation((2,))


def _installed(monkeypatch: pytest.MonkeyPatch,
               factory: Callable[[], Segmenter]) -> None:
    monkeypatch.setattr(cli, "_ja_extra_installed", lambda: True)
    monkeypatch.setattr(nameparser.locales, "ja_segmenter", factory)


@pytest.mark.parametrize("code", ["ja", "JA"])
@pytest.mark.parametrize("order", [(), ("--order", "given-first"),
                                   ("--order", "family-first"),
                                   ("--order", "family-first-given-last")])
def test_cli_locale_ja_attaches_the_installed_segmenter(
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        code: str, order: tuple[str, ...]) -> None:
    # --order rewrites the pack; the segmenter must survive it
    _installed(monkeypatch, lambda: _cut_after_two)
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        fields = _fields(capsys, "--locale", code, *order, "山田太郎")
    assert (fields["family"], fields["given"]) == ("山田", "太郎")
    assert record == []


@pytest.mark.parametrize("order", [(), ("--order", "family-first")])
def test_cli_locale_ja_without_the_extra_notes_once_and_does_not_warn(
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch, order: tuple[str, ...]) -> None:
    # the note replaces the parser's warning (rules/D1), whose remedies
    # are code a command line cannot pass; a print shows where warnings
    # are filtered out
    def unexpected() -> Segmenter:
        raise AssertionError("ja_segmenter called without the extra")
    monkeypatch.setattr(cli, "_ja_extra_installed", lambda: False)
    monkeypatch.setattr(nameparser.locales, "ja_segmenter", unexpected)
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        assert cli.main(["--locale", "ja", *order, "--json", "山田太郎"]) == 0
    out, err = capsys.readouterr()
    assert json.loads(out)["family"] == "山田太郎"
    assert err.count(_JA_NOTE) == 1
    assert record == []


@pytest.mark.parametrize("error", [
    ImportError("numpy.core.multiarray failed to import"),
    OSError("libomp.dylib not found"),
])
def test_cli_locale_ja_a_broken_install_fails_with_its_own_error(
        monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    # namedivider is there but will not load: not the missing-extra note
    def broken() -> Segmenter:
        raise error
    _installed(monkeypatch, broken)
    with pytest.raises(type(error), match=str(error)):
        cli.main(["--locale", "ja", "山田太郎"])


def test_cli_attaches_a_segmenter_only_for_the_ja_pack(
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch) -> None:
    # under zh its surname list divides, and a segmenter would answer
    # where the list declines
    calls: list[str] = []

    def factory() -> Segmenter:
        calls.append("ja_segmenter")
        return _cut_after_two
    _installed(monkeypatch, factory)
    _fields(capsys, "--locale", "zh", "王小明")
    assert calls == []
