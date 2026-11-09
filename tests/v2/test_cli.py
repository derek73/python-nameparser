import dataclasses
import importlib.util
import json
import subprocess
import sys
import warnings
from collections.abc import Callable
from typing import Any

import pytest

import nameparser.locales
from nameparser import (
    FAMILY_FIRST,
    CapsSuffixes,
    Lexicon,
    Locale,
    Policy,
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
    # es reads Maestra as a title (the pack's lexicon); cs reads two
    # family names (its policy), which a parser rebuilt from the order
    # alone would lose: family 'Novák', given 'Jan', middle 'Petr'
    es = _fields(capsys, "--locale", "es", "--order", "family-first",
                 "Maestra Kovács Ana")
    assert (es["title"], es["given"], es["family"]) == (
        "Maestra", "Ana", "Kovács")
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


@pytest.mark.parametrize(("argv", "field"), [
    ((), "given"),
    (("--order", "family-first"), "given"),
    (("--lone-name-word", "family"), "family"),
    (("--lone-name-word", "family", "--order", "family-first"), "family"),
    # the flag replaces the pack's reading, VI reading given by default
    (("--locale", "vi", "--lone-name-word", "family"), "family"),
    (("--lone-name-word", "given", "--order", "family-first"), "given"),
])
def test_cli_lone_name_word_names_the_field_of_a_one_word_name(
        capsys: pytest.CaptureFixture[str], argv: tuple[str, ...],
        field: str) -> None:
    # the switch, not the order, places a lone word (O5, #1111)
    assert _fields(capsys, *argv, "Nguyen")[field] == "Nguyen"


def test_cli_lone_name_word_refuses_a_field_no_lone_word_takes(
        capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--lone-name-word", "middle", "Nguyen"])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "given" in err and "family" in err


def test_cli_order_spellings_match_the_vocabulary_rules_tables() -> None:
    assert cli._ORDERS == _locale._ORDERS


# --locale ja attaches the segmenter where namedivider is installed. The
# two subprocess runs are the real thing, each in the environment it
# needs (the extra one only in CI's ja-extra job); the in-process ones
# stand in for the install so every branch runs everywhere.

def test_cli_sorts_every_policy_field_into_a_flag_or_a_reason() -> None:
    # a new Policy field fails here until someone decides whether the
    # command line sets it
    flagged = [*cli._SWITCHES, *cli._CHOICES, "name_order",
               "lone_name_word"]
    sorted_ = [*flagged, *cli._NOT_ON_THE_COMMAND_LINE]
    assert len(sorted_) == len(set(sorted_))
    assert set(sorted_) == {f.name for f in dataclasses.fields(Policy)}


def test_cli_switch_tables_name_fields_of_their_kind() -> None:
    defaults = Policy()
    assert cli._SWITCHES
    for field in cli._SWITCHES:
        assert isinstance(getattr(defaults, field), bool), field
    for field, (enum, _) in cli._CHOICES.items():
        assert isinstance(getattr(defaults, field), enum), field


# one row per flag in each direction: the name, and what the field it
# sets moves, against the parse with the flag turned the other way
_SWITCH_ROWS = [
    ("two_given_names", "Juan Carlos García", "given",
     "Juan Carlos", "Juan"),
    ("two_family_names", "Gabriel García Márquez", "family",
     "García Márquez", "Márquez"),
    ("middle_as_family", "John Quincy Adams", "family",
     "Quincy Adams", "Adams"),
    ("lenient_comma_suffixes", "John Smith, V", "suffix", "V", ""),
    ("unlisted_dotted_suffixes", "John Smith X.Y.Z.", "suffix",
     "X.Y.Z.", ""),
]


def test_cli_switch_rows_cover_every_switch() -> None:
    assert [row[0] for row in _SWITCH_ROWS] == list(cli._SWITCHES)


@pytest.mark.parametrize(
    ("field", "name", "role", "on", "off"), _SWITCH_ROWS,
    ids=[row[0] for row in _SWITCH_ROWS])
def test_cli_switch_turns_its_field_on_and_off(
        capsys: pytest.CaptureFixture[str], field: str, name: str,
        role: str, on: str, off: str) -> None:
    flag = "--" + field.replace("_", "-")
    no_flag = "--no-" + field.replace("_", "-")
    assert _fields(capsys, flag, name)[role] == on
    assert _fields(capsys, no_flag, name)[role] == off


def test_cli_switch_wins_over_a_packs_setting(
        capsys: pytest.CaptureFixture[str]) -> None:
    # es turns two_family_names on; the flag turns it off and keeps the
    # pack's vocabulary (Maestra a title, which the default reads as a name)
    name = "Maestra Ana García López"
    es = _fields(capsys, "--locale", "es", name)
    assert (es["title"], es["family"]) == ("Maestra", "García López")
    off = _fields(capsys, "--locale", "es", "--no-two-family-names", name)
    assert (off["title"], off["family"]) == ("Maestra", "López")


def test_cli_a_switch_left_out_keeps_the_packs_setting(
        capsys: pytest.CaptureFixture[str]) -> None:
    # another flag on the same pack must not reset two_family_names
    fields = _fields(capsys, "--locale", "es", "--two-given-names",
                     "María José García López")
    assert (fields["given"], fields["family"]) == (
        "María José", "García López")


# a stand-in pack sets each field against Policy()'s default, which no
# shipped pack does for most of them: with no flag the pack's value
# holds, and the flag turned the other way wins over it
_PACK_ROWS = [
    *[(field, name, role, off if getattr(Policy(), field) else on,
       f"--{'' if getattr(Policy(), field) else 'no-'}"
       f"{field.replace('_', '-')}",
       on if getattr(Policy(), field) else off)
      for field, name, role, on, off in _SWITCH_ROWS],
    ("unlisted_caps_suffixes", "Jean Pierre DUPONT", "suffix", "DUPONT",
     "--unlisted-caps-suffixes=after-comma", ""),
]


def test_cli_pack_rows_cover_every_flag() -> None:
    assert [row[0] for row in _PACK_ROWS] == [
        *cli._SWITCHES, *cli._CHOICES]


@pytest.mark.parametrize(
    ("field", "name", "role", "packs", "flag", "flagged"), _PACK_ROWS,
    ids=[row[0] for row in _PACK_ROWS])
def test_cli_flag_left_out_keeps_a_packs_setting_and_given_wins(
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch, field: str, name: str,
        role: str, packs: str, flag: str, flagged: str) -> None:
    default = getattr(Policy(), field)
    value = (CapsSuffixes.EVERYWHERE if isinstance(default, CapsSuffixes)
             else not default)
    setting: dict[str, Any] = {field: value}
    pack = Locale(code="xx", lexicon=Lexicon.empty(),
                  policy=PolicyPatch(**setting))
    monkeypatch.setattr(nameparser.locales, "get", lambda code: pack)
    assert _fields(capsys, "--locale", "xx", name)[role] == packs
    assert _fields(capsys, "--locale", "xx", flag, name)[role] == flagged


def test_cli_switch_combines_with_order(
        capsys: pytest.CaptureFixture[str]) -> None:
    fields = _fields(capsys, "--order", "family-first",
                     "--two-given-names", "García Juan Carlos")
    assert (fields["given"], fields["family"]) == ("Juan Carlos", "García")


# the suffix each setting reads after a comma, and ending a name
# without one: the pair tells all three apart
_CAPS_ROWS = [
    ("off", "", ""),
    ("after-comma", "XYZ", ""),
    ("everywhere", "XYZ", "DUPONT"),
]


@pytest.mark.parametrize(("value", "after_comma", "ending"), _CAPS_ROWS)
def test_cli_unlisted_caps_suffixes_takes_each_setting(
        capsys: pytest.CaptureFixture[str], value: str,
        after_comma: str, ending: str) -> None:
    flag = "--unlisted-caps-suffixes"
    assert _fields(capsys, flag, value, "John Smith, XYZ")[
        "suffix"] == after_comma
    assert _fields(capsys, flag, value, "Jean Pierre DUPONT")[
        "suffix"] == ending


def test_cli_unlisted_caps_suffixes_rows_cover_every_setting() -> None:
    assert [row[0] for row in _CAPS_ROWS] == [
        member.value for member in CapsSuffixes]


def test_cli_unlisted_caps_suffixes_lists_the_enums_values(
        capsys: pytest.CaptureFixture[str]) -> None:
    err = _usage_error(capsys, "--unlisted-caps-suffixes", "bogus", "x")
    # 3.12 lists the choices bare where 3.11 and 3.13 on quote them,
    # so match either
    listed = err.split("choose from")[1]
    for member in CapsSuffixes:
        assert member.value in listed


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


# --strict (#753, 3j) and --locale's fallback to a language tag

@pytest.mark.parametrize(("argv", "roles"), [
    (("--locale", "ko", "--strict", "Kim Do Hyun"), ("Kim", "Do", "Hyun")),
    # vi is locales.VI since #1108: its order reads the given name last,
    # with or without --strict
    (("--locale", "vi", "--strict", "Do Van Minh"), ("Minh", "Van", "Do")),
    (("--locale", "vi", "Do Van Minh"), ("Minh", "Van", "Do")),
    # a pack choosing no language chooses its code under --strict
    (("--locale", "zh", "--strict", "De Xu"), ("De", "", "Xu")),
    # without --strict, ko's file holds nothing Latin to prefer
    (("--locale", "ko", "Kim Do Hyun"), ("Kim", "", "Do Hyun")),
])
def test_cli_locale_falls_back_to_a_language_and_strict_reads_it_alone(
        capsys: pytest.CaptureFixture[str], argv: tuple[str, ...],
        roles: tuple[str, str, str]) -> None:
    assert _roles(_fields(capsys, *argv)) == roles


def _usage_error(capsys: pytest.CaptureFixture[str], *argv: str) -> str:
    # in process, so coverage sees the branch: argparse exits 2
    with pytest.raises(SystemExit) as info:
        cli.main([*argv, "John Smith"])
    assert info.value.code == 2
    return capsys.readouterr().err


def test_cli_strict_without_a_locale_is_a_usage_error(
        capsys: pytest.CaptureFixture[str]) -> None:
    assert "--strict needs --locale" in _usage_error(capsys, "--strict")


def test_cli_locale_neither_a_pack_nor_a_language_lists_both(
        capsys: pytest.CaptureFixture[str]) -> None:
    err = _usage_error(capsys, "--locale", "xx", "--strict")
    # the pack codes, then the language tags
    assert "tr_az" in err and "nor a language" in err
    assert "ko" in err.split("nor a language")[1]


def test_cli_locale_that_is_no_tag_at_all_lists_the_packs(
        capsys: pytest.CaptureFixture[str]) -> None:
    # "" cannot even be a tag, so the stand-in Locale refuses it
    err = _usage_error(capsys, "--locale", "")
    assert "tr_az" in err and "nor a language" not in err


def test_cli_a_language_with_no_reading_needs_strict(
        capsys: pytest.CaptureFixture[str]) -> None:
    # zu.toml holds only exclusions (vi.toml did until #1108, hu.toml
    # until its familiar forms, 2026-11-08)
    err = _usage_error(capsys, "--locale", "zu")
    assert "zu.toml holds no reading yet" in err
    assert "(--strict) accepts it" in err


def test_cli_strict_with_a_pack_whose_code_is_no_language(
        capsys: pytest.CaptureFixture[str]) -> None:
    err = _usage_error(capsys, "--locale", "tr_az", "--strict")
    assert "--strict needs a language" in err
    assert "--locale tr --strict" in err


@pytest.mark.parametrize("tag,pack", [
    # a bare choice would drop the pack's segmentation, two family
    # names and given-name list, and the segmenter, in silence
    ("zh-CN", "zh"), ("es-MX", "es"), ("ja-JP", "ja"), ("pt-PT", "pt"),
    # a script subtag is not a region, and the message says neither
    ("zh-Hant", "zh"),
])
def test_cli_a_subtag_of_a_packs_language_names_the_pack(
        capsys: pytest.CaptureFixture[str], tag: str, pack: str) -> None:
    err = _usage_error(capsys, "--locale", tag)
    assert f"use --locale {pack}" in err and "region" not in err


@pytest.mark.parametrize("tag", ["pt-BR", "pt_br", "PT-BR"])
def test_cli_a_tag_spelled_for_a_packs_code_is_that_pack(
        capsys: pytest.CaptureFixture[str], tag: str) -> None:
    assert (_fields(capsys, "--locale", tag, "Pedro Silva Sb")
            == _fields(capsys, "--locale", "pt_br", "Pedro Silva Sb"))
    assert _fields(capsys, "--locale", tag, "Pedro Silva Sb")["suffix"] == "Sb"
