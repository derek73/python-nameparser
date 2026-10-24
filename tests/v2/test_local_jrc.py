"""Offline checks on tools/differential/local_jrc.py, the jrc-names
local corpus, and on local_corpora.py's groups view, which reads it.

Every name here is invented: the JRC-Names licence bars redistributing
the resource or anything derived from it, so not one of its names, nor
a reading of one, may reach the repository. What these pin is the
fetch's refusals (a file other than the pinned one, a gzip cut short, a
file ending inside a line, a layout or a marking that has moved), what
it keeps and counts, and the view's counting, every count a person's.
"""
import gzip
import hashlib
import importlib
import unicodedata
import urllib.request
from pathlib import Path

import pytest

from ._differential_fixtures import load_tool, own_cache, plant_corpus

local = load_tool("local_corpora")
# The module the fetch reads its constants from, by name: a patch set on
# a second load by path would reach nothing (test_local_corpora.py).
jrc = importlib.import_module("local_jrc")

_JRC = "jrc-names"


@pytest.fixture(autouse=True)
def _own_cache(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return own_cache(monkeypatch, tmp_path_factory)


#: The header line, one person spelled three ways (one of them marked
#: Russian, one repeated), one person whose words run "++", an
#: organisation, and one person spelled twice, once marked Arabic with a
#: glued "and": 9 lines.
_LINES = ["#", "1\tP\tu\tAnn+Lee", "1\tP\tu\tАнна+Ли", "1\tP\tru\tАнны+Ли",
          "1\tP\tu\tAnn+Lee", "2\tP\tu\tBo++Wu", "3\tO\tu\tAcme+Corp",
          "4\tP\tar\tوأحمد+علي", "4\tP\tu\tأحمد+علي"]


def _body(lines: list[str], end: bytes = b"\r\n") -> bytes:
    return b"".join(line.encode() + end for line in lines)


def _cache(monkeypatch: pytest.MonkeyPatch, raw: bytes, *, pin: bool = True) -> Path:
    """`raw` as the cached download, pinned unless `pin` is False; its path."""
    path = local.directory(_JRC) / jrc.JRC_FILE
    path.write_bytes(raw)
    if pin:
        monkeypatch.setattr(jrc, "JRC_SHA256", hashlib.sha256(raw).hexdigest())
    return path


def _cached(monkeypatch: pytest.MonkeyPatch, lines: list[str], **kw: object) -> Path:
    return _cache(monkeypatch, gzip.compress(_body(lines, **kw)))  # type: ignore[arg-type]


def _lenient(monkeypatch: pytest.MonkeyPatch, *, but: str = "") -> None:
    """Shares a fixture of 9 lines can pass: its header is 1 in 9, its
    marked rows 2 in 7 and its repeat 1 in 7. Every share but `but`."""
    for share in ("JRC_MAX_BAD", "JRC_MAX_MARKED", "JRC_MAX_REPEATED", "JRC_MAX_LOST"):
        if share != but:
            monkeypatch.setattr(jrc, share, 1)


def test_a_jrc_fetch_keeps_each_plain_spelling_once_and_counts_the_rest(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _cached(monkeypatch, _LINES)
    _lenient(monkeypatch)
    corpus = local.fetch(_JRC)
    assert corpus.records == [
        {"entity": "1", "name": "Ann Lee", "script": "Latin"},
        {"entity": "1", "name": "Анна Ли", "script": "Cyrillic"},
        {"entity": "2", "name": "Bo Wu", "script": "Latin"},
        {"entity": "4", "name": "أحمد علي", "script": "Arabic"}]
    assert corpus.meta["data_date"] == jrc.JRC_DATE
    assert corpus.meta["detail"] == {
        "sha256": jrc.JRC_SHA256, "read_version": jrc.JRC_READ_VERSION,
        "unicode": unicodedata.unidata_version, "lines": 9, "lines_read_past": 1,
        "organisation_rows": 1, "person_rows": 7, "marked_variants_dropped": 2,
        "marked_variants_by_language": "ar:1 ru:1", "repeated_spellings": 1,
        "entities": 3, "entities_with_marked_spellings_only": 0,
        "entities_with_one_spelling": 2,
        "spellings_holding_a_replacement_character": 0}
    assert corpus.header().endswith("4 spellings (local corpus jrc-names)")


def test_a_jrc_file_that_is_not_the_pinned_one_is_refused(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _cache(monkeypatch, gzip.compress(_body(_LINES)), pin=False)
    with pytest.raises(ValueError, match="not the pinned JRC_SHA256.*fetch jrc-names --refresh"):
        local.fetch(_JRC)
    assert local.load(_JRC) is None


@pytest.mark.parametrize("damage", ["cut short", "not a gzip", "corrupt"])
def test_a_jrc_gzip_that_is_not_whole_names_the_way_out(
        monkeypatch: pytest.MonkeyPatch, damage: str) -> None:
    # Pinned to the damaged bytes: the pin is what stops this file, and
    # a pin moved to a cut download must still not read as a corpus.
    whole = gzip.compress(_body(_LINES))
    raw = {"cut short": whole[:-20], "not a gzip": _body(_LINES),
           "corrupt": whole[:20] + bytes(b ^ 0xFF for b in whole[20:40]) + whole[40:]}[damage]
    _cache(monkeypatch, raw)
    _lenient(monkeypatch)
    with pytest.raises(ValueError, match="not a whole gzip.*fetch jrc-names --refresh"):
        local.fetch(_JRC)


@pytest.mark.parametrize(("lines", "but", "match"), [
    ([*_LINES, "5\tP\tru\tАнны+Ли"], "JRC_MAX_LOST", "1 of 4 persons .* marked spellings only"),
    (_LINES, "JRC_MAX_REPEATED", "1 of 7 person rows .* repeat a spelling"),
], ids=["a person spelled only in marked rows", "a repeated spelling"])
def test_a_jrc_file_that_would_shrink_in_silence_is_refused(
        monkeypatch: pytest.MonkeyPatch, lines: list[str], but: str, match: str) -> None:
    _cached(monkeypatch, lines)
    _lenient(monkeypatch, but=but)
    monkeypatch.setattr(jrc, but, 0)
    with pytest.raises(ValueError, match=match):
        local.fetch(_JRC)
    monkeypatch.setattr(jrc, but, 1 / 4)
    detail = local.fetch(_JRC).meta["detail"]
    assert (detail["entities_with_marked_spellings_only"], detail["repeated_spellings"]) == (
        (1, 1) if but == "JRC_MAX_LOST" else (0, 1))


def test_a_jrc_file_naming_no_person_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _cached(monkeypatch, ["#"])
    _lenient(monkeypatch)
    with pytest.raises(ValueError, match="0 of 0 lines .* name a person"):
        local.fetch(_JRC)


def test_a_jrc_spelling_is_read_as_written_but_for_its_spaces(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # Ids are kept as written ("01" and "1" two entities), runs of "+"
    # and spaces are one space, and a replacement character is kept and
    # counted.
    _cached(monkeypatch, ["1\tP\tu\tAnn+ +Lee", "01\tP\tu\tAnn+Lee",
                          "2\tP\tu\tBo\ufffd+Wu"])
    _lenient(monkeypatch)
    corpus = local.fetch(_JRC)
    assert [(r["entity"], r["name"]) for r in corpus.records] == [
        ("01", "Ann Lee"), ("1", "Ann Lee"), ("2", "Bo\ufffd Wu")]
    assert corpus.meta["detail"]["spellings_holding_a_replacement_character"] == 1
    assert corpus.meta["detail"]["entities"] == 3


def test_a_jrc_file_ending_inside_a_line_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _cache(monkeypatch, gzip.compress(_body(_LINES)[:-6]))
    _lenient(monkeypatch)
    with pytest.raises(ValueError, match="ends inside a line"):
        local.fetch(_JRC)


@pytest.mark.parametrize("bad", [
    "5\tP\tu", "5\tP\tu\tAnn+Lee\tX", "x5\tP\tu\tAnn+Lee", "5\tQ\tu\tAnn+Lee",
    "5\tP\tRU\tAnn+Lee", "5\tP\tu\t+", b"5\tP\tu\tPe\xf1a".decode("latin-1"),
    "\u0665\tP\tu\tAnn+Lee", "\uff15\tP\tu\tAnn+Lee"],
    ids=["three columns", "five columns", "an id not digits", "another type",
         "a language not a code", "an empty name", "not UTF-8",
         "an Arabic-Indic digit id", "a fullwidth digit id"])
def test_a_jrc_line_read_past_is_counted_up_to_its_share(
        monkeypatch: pytest.MonkeyPatch, bad: str) -> None:
    # 2 lines of 10 read past: refused at a share under 2/10, read at it.
    # The two digit ids are digits to int() and to \\d, and would merge a
    # spelling into entity 5's group.
    lines = [*_LINES, bad]
    raw = (_body(lines[:-1]) + bad.encode("latin-1" if "\xf1" in bad else "utf-8")
           + b"\r\n")
    _cache(monkeypatch, gzip.compress(raw))
    _lenient(monkeypatch, but="JRC_MAX_BAD")
    monkeypatch.setattr(jrc, "JRC_MAX_BAD", 2 / 10 - 1e-9)
    with pytest.raises(ValueError, match="2 of 10 lines .* are not 4 well-formed columns"):
        local.fetch(_JRC)
    monkeypatch.setattr(jrc, "JRC_MAX_BAD", 2 / 10)
    assert local.fetch(_JRC).meta["detail"]["lines_read_past"] == 2


def test_a_jrc_file_with_too_few_persons_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    # A person type renamed reads every person row as read past, or, as
    # here, a file of organisations: 1 person row of 3.
    _cached(monkeypatch, ["1\tP\tu\tAnn+Lee", "2\tO\tu\tAcme", "3\tO\tu\tAcme+Two"])
    _lenient(monkeypatch)
    with pytest.raises(ValueError, match="1 of 3 lines .* name a person"):
        local.fetch(_JRC)
    monkeypatch.setattr(jrc, "JRC_MIN_PERSONS", 1 / 3)
    assert len(local.fetch(_JRC).records) == 1


def test_a_jrc_file_marking_too_many_spellings_is_refused(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # 2 of the fixture's 7 person rows carry a language.
    _cached(monkeypatch, _LINES)
    _lenient(monkeypatch, but="JRC_MAX_MARKED")
    monkeypatch.setattr(jrc, "JRC_MAX_MARKED", 2 / 7 - 1e-9)
    with pytest.raises(ValueError, match="2 of 7 person rows .* carry a language"):
        local.fetch(_JRC)
    monkeypatch.setattr(jrc, "JRC_MAX_MARKED", 2 / 7)
    assert len(local.fetch(_JRC).records) == 4


class _Download:
    """A streamed download stating its whole length."""

    def __init__(self, body: bytes) -> None:
        self.body = body
        self.headers = {"Content-Length": str(len(body))}

    def __enter__(self) -> "_Download":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self, n: int) -> bytes:
        chunk, self.body = self.body[:n], self.body[n:]
        return chunk


def _serve(monkeypatch: pytest.MonkeyPatch, *bodies: bytes) -> list[str]:
    queue, asked = list(bodies), []

    def urlopen(request: urllib.request.Request, timeout: int) -> _Download:
        asked.append(request.full_url)
        if not queue:
            pytest.fail(f"an unexpected download of {request.full_url}")
        return _Download(queue.pop(0))
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return asked


def test_a_jrc_fetch_downloads_the_file_when_it_is_missing_and_once(
        monkeypatch: pytest.MonkeyPatch) -> None:
    raw = gzip.compress(_body(_LINES))
    monkeypatch.setattr(jrc, "JRC_SHA256", hashlib.sha256(raw).hexdigest())
    _lenient(monkeypatch)
    asked = _serve(monkeypatch, raw)
    assert local.main(["fetch", _JRC]) == 0
    assert local.main(["fetch", _JRC]) == 0
    assert asked == [jrc.JRC_URL]
    assert (local.directory(_JRC) / jrc.JRC_FILE).read_bytes() == raw


def test_a_jrc_refresh_downloads_the_file_again(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = gzip.compress(_body(_LINES))
    _cache(monkeypatch, b"an older download")
    monkeypatch.setattr(jrc, "JRC_SHA256", hashlib.sha256(raw).hexdigest())
    _lenient(monkeypatch)
    asked = _serve(monkeypatch, raw)
    assert local.main(["fetch", _JRC, "--refresh"]) == 0
    assert asked == [jrc.JRC_URL]
    assert len(local.require(_JRC).records) == 4


@pytest.mark.parametrize("cached", [True, False], ids=["a refresh", "a first fetch"])
def test_a_jrc_download_that_is_not_the_pinned_file_replaces_nothing(
        monkeypatch: pytest.MonkeyPatch, cached: bool) -> None:
    # The JRC serves only its current file: a download writing a newer
    # one over the cached one would leave nothing to rebuild from. (A
    # refresh of the pinned file downloads nothing at all; this cached
    # file is a damaged one, which the refresh is for.)
    pinned = gzip.compress(_body(_LINES))
    damaged = pinned[:-20]
    path = local.directory(_JRC) / jrc.JRC_FILE
    if cached:
        path.write_bytes(damaged)
    monkeypatch.setattr(jrc, "JRC_SHA256", hashlib.sha256(pinned).hexdigest())
    _lenient(monkeypatch)
    newer = gzip.compress(_body(_LINES[:3]))
    _serve(monkeypatch, newer)
    with pytest.raises(ValueError, match="not the pinned JRC_SHA256: it is kept at"):
        local.main(["fetch", _JRC, "--refresh"] if cached else ["fetch", _JRC])
    assert path.with_name(jrc.JRC_FILE + ".new").read_bytes() == newer
    assert path.read_bytes() == damaged if cached else not path.exists()


def test_a_jrc_download_kept_by_a_mismatch_is_adopted_once_pinned(
        monkeypatch: pytest.MonkeyPatch) -> None:
    raw = gzip.compress(_body(_LINES))
    local.directory(_JRC).joinpath(jrc.JRC_FILE + ".new").write_bytes(raw)
    monkeypatch.setattr(jrc, "JRC_SHA256", hashlib.sha256(raw).hexdigest())
    _lenient(monkeypatch)
    assert _serve(monkeypatch) == [] and len(local.fetch(_JRC).records) == 4
    assert (local.directory(_JRC) / jrc.JRC_FILE).read_bytes() == raw


def test_a_jrc_fetch_adopts_a_kept_download_over_the_old_pinned_file(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # The pin moved to the download a refresh kept: a plain fetch reads
    # it, without calling the old file damaged or downloading again.
    _cache(monkeypatch, gzip.compress(_body(_LINES[:3])), pin=False)
    raw = gzip.compress(_body(_LINES))
    local.directory(_JRC).joinpath(jrc.JRC_FILE + ".new").write_bytes(raw)
    monkeypatch.setattr(jrc, "JRC_SHA256", hashlib.sha256(raw).hexdigest())
    _lenient(monkeypatch)
    assert _serve(monkeypatch) == [] and len(local.fetch(_JRC).records) == 4
    assert (local.directory(_JRC) / jrc.JRC_FILE).read_bytes() == raw


def test_a_jrc_refresh_of_the_pinned_file_downloads_nothing(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # The pinned file cannot change, and once the JRC serves another a
    # download would fail: a corpus read another way is read again from
    # the cached file.
    _cached(monkeypatch, _LINES)
    _lenient(monkeypatch)
    local.fetch(_JRC)
    monkeypatch.setattr(jrc, "JRC_READ_VERSION", jrc.JRC_READ_VERSION + 1)
    assert _serve(monkeypatch) == []
    assert local.main(["fetch", _JRC, "--refresh"]) == 0
    assert local.require(_JRC).meta["detail"]["read_version"] == jrc.JRC_READ_VERSION


def test_a_jrc_corpus_labelled_under_another_unicode_is_refused_on_load(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # script() reads the Unicode table this Python carries.
    _cached(monkeypatch, _LINES)
    _lenient(monkeypatch)
    local.fetch(_JRC)
    monkeypatch.setattr(jrc.unicodedata, "unidata_version", "0.0.0")
    with pytest.raises(ValueError, match="labelled under Unicode .* reads Unicode 0.0.0"):
        local.load(_JRC)


def test_a_jrc_corpus_read_another_way_is_refused_on_load(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # A change to script() would otherwise leave the cached records'
    # labels standing under code that no longer gives them.
    _cached(monkeypatch, _LINES)
    _lenient(monkeypatch)
    local.fetch(_JRC)
    held = jrc.JRC_READ_VERSION
    monkeypatch.setattr(jrc, "JRC_READ_VERSION", held + 1)
    with pytest.raises(ValueError, match=f"read by read version {held}, and this tool "
                                          f"reads version {held + 1}.*fetch {_JRC} --refresh"):
        local.load(_JRC)


def test_a_jrc_corpus_read_from_another_file_is_refused_on_load(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # Moving the pin would otherwise leave the old file's corpus standing
    # under the new pin's data date.
    _cached(monkeypatch, _LINES)
    _lenient(monkeypatch)
    local.fetch(_JRC)
    monkeypatch.setattr(jrc, "JRC_SHA256", "0" * 64)
    with pytest.raises(ValueError, match=f"read from the file with sha256 .*reads 0{{64}}"
                                          f".*fetch {_JRC} --refresh"):
        local.load(_JRC)


@pytest.mark.parametrize(("name", "script"), [
    ("Ann Lee", "Latin"), ("José Peña", "Latin"), ("Анна Ли", "Cyrillic"),
    ("أحمد علي", "Arabic"), ("王小明", "Han"), ("アン・リー", "Katakana"),
    ("ルーシー", "Katakana"), ("ｱﾝ", "Katakana"), ("Ｊｏｈｎ", "Latin"),
    ("ʿAli", "Latin"), ("Maªa", "Latin"), ("佐々木", "Han"), ("のゞ々", "Hiragana"),
    ("Мар\u02bcяна", "Cyrillic"), ("ʿ", "none"), ("Ann Ли", "mixed"),
    ("- ? -", "none")])
def test_a_spelling_s_script_is_the_script_of_its_letters(name: str, script: str) -> None:
    # ー, the prolonged sound mark, is a letter Unicode files under
    # KATAKANA-HIRAGANA; a halfwidth or fullwidth letter names its form
    # before its script; ʿ, ʼ, ª and 々 are written in several scripts
    # and name none: none is a second script.
    assert jrc.script(name) == script


# -- the groups view -------------------------------------------------------------

def _spelled(*spellings: tuple[str, str]) -> object:
    """A jrc-names corpus holding each (entity, name) of `spellings`."""
    return local.Local(_JRC, {"data_date": jrc.JRC_DATE},
                       [{"entity": entity, "name": name, "script": jrc.script(name)}
                        for entity, name in spellings])


def test_a_reading_names_its_fields_as_the_report_does() -> None:
    assert local.reading("Ann Lee").family_at == "last"
    assert local.GROUP_FIELDS == ("title", "suffix", "given", "family",
                                  "family words", "family at")


def test_a_reading_is_the_structure_of_the_parse_never_its_words() -> None:
    assert local.reading("Ann Lee") == (False, False, True, True, 1, "last")
    assert local.reading("Dr. Ann de la Lee Jr.") == (True, True, True, True, 3, "last")
    assert local.reading("Lee, Ann") == (False, False, True, True, 1, "first")
    assert local.reading("Ann") == (False, False, True, False, 0, "none")
    assert local.reading("de Mesnil") == (False, False, False, True, 2, "whole")
    assert local.reading("Анна Ли") == local.reading("Ann Lee")


def test_the_groups_view_counts_persons_by_the_scripts_of_their_spellings() -> None:
    found = local.group_counts(_spelled(
        ("1", "Ann Lee"), ("1", "Анна Ли"),
        ("2", "Bo Wu"), ("2", "Dr. Bo Wu"), ("2", "Бо Ву"),
        ("3", "Cy Ng")))  # one spelling: no group
    assert (found.persons, found.spellings) == (2, 5)
    assert found.groups == {"any": 2, "Cyrillic / Latin": 2, "Latin / Latin": 1}
    # Person 2's Latin spellings differ between themselves, and its
    # Cyrillic one reads as one of them does: the scripts agree.
    assert found.agree == {"any": 1, "Cyrillic / Latin": 2}
    assert found.differ == {("any", "title"): 1, ("Latin / Latin", "title"): 1}
    assert found.titles == {"dr": 1} and found.suffixes == {}


def test_the_groups_view_finds_two_scripts_that_read_a_field_apart() -> None:
    # Every Latin spelling reads a title and no Cyrillic one does; the two
    # titled spellings count the person once.
    found = local.group_counts(_spelled(("1", "Dr. Ann Lee"), ("1", "Dr Ann Lee"),
                                        ("1", "Анна Ли")))
    assert found.differ == {("any", "title"): 1, ("Cyrillic / Latin", "title"): 1}
    assert found.agree == {"Latin / Latin": 1}
    assert found.titles == {"dr": 1}


def test_the_groups_view_lists_no_title_every_spelling_reads() -> None:
    # Two titles, two suffixes, and no spelling without: no lead, since
    # the vocabulary already reads each spelling's word.
    found = local.group_counts(_spelled(("1", "Dr. Ann Lee"), ("1", "Prof. Ann Lee"),
                                        ("2", "Bo Wu Jr."), ("2", "Bo Wu Sr.")))
    assert found.titles == {} and found.suffixes == {} and found.differ == {}


def test_the_groups_view_lists_a_title_run_word_by_word() -> None:
    found = local.group_counts(_spelled(("1", "Dr. Prof. Ann Lee"), ("1", "Ann Lee")))
    assert found.titles == {"dr": 1, "prof": 1}


def test_the_groups_view_pairs_every_two_of_a_person_s_scripts() -> None:
    # The Arabic spelling reads a title the others do not: only its two
    # pairs differ. A spelling of two scripts keys a pair as "mixed".
    found = local.group_counts(_spelled(
        ("1", "Ann Lee"), ("1", "Анна Ли"), ("1", "الدكتور أحمد علي"), ("1", "Ann Ли")))
    assert local.reading("الدكتور أحمد علي").title
    assert found.groups == {"any": 1, "Arabic / Cyrillic": 1, "Arabic / Latin": 1,
                            "Arabic / mixed": 1, "Cyrillic / Latin": 1,
                            "Cyrillic / mixed": 1, "Latin / mixed": 1}
    assert found.agree == {"Cyrillic / Latin": 1, "Cyrillic / mixed": 1, "Latin / mixed": 1}


def test_two_scripts_read_alike_only_where_one_spelling_matches_one_whole() -> None:
    # The Cyrillic spelling reads a title and a suffix, and each Latin one
    # reads one of the two: no field is read apart, yet no spelling in one
    # script reads as any in the other does.
    found = local.group_counts(_spelled(("1", "Dr. Ann Lee"), ("1", "Ann Lee Jr."),
                                        ("1", "Др. Анна Ли мл.")))
    assert local.reading("Др. Анна Ли мл.")[:2] == (True, True)
    assert ("Cyrillic / Latin", "title") not in found.differ
    assert ("Cyrillic / Latin", "suffix") not in found.differ
    assert "Cyrillic / Latin" not in found.agree
    # Counted apart, so that the pair's persons are each alike, apart in
    # a field, or here.
    assert found.differ[("Cyrillic / Latin", local.NO_ONE_FIELD)] == 1


def test_the_groups_view_counts_a_person_once_however_many_spellings_differ() -> None:
    found = local.group_counts(_spelled(*[
        ("1", name) for name in
        ("Ann Lee", "Dr. Ann Lee", "Ann Lee Jr.", "Ann de Lee", "Lee")]))
    assert found.groups == {"any": 1, "Latin / Latin": 1}
    # Every spelling reads a given name; "Lee" alone reads no family.
    assert found.differ == {(pair, field): 1 for pair in ("any", "Latin / Latin")
                            for field in local.GROUP_FIELDS if field != "given"}
    assert found.titles == {"dr": 1} and found.suffixes == {"jr": 1}


def test_the_groups_report_gives_each_share_of_a_pair_s_persons(
        capsys: pytest.CaptureFixture[str]) -> None:
    rows = [("1", "Ann Lee"), ("1", "Dr. Ann Lee"), ("2", "Bo Wu"), ("2", "Bo Wu"),
            ("2", "Bo  Wu"), ("3", "Cy Ng"), ("3", "Сай Нг")]
    print(local.format_groups(local.group_counts(_spelled(*rows)), 1))
    out = capsys.readouterr().out
    assert "        2   50.0% alike  Latin / Latin; differ in title 50.0%" in out
    # top=1: "any" and the largest pair only.
    assert "Cyrillic / Latin" not in out


def test_the_groups_view_lists_only_titles_many_persons_share(
        capsys: pytest.CaptureFixture[str]) -> None:
    rows = [(str(i), name) for i in range(10) for name in ("Ann Lee", "Dr. Ann Lee")]
    rows += [("10", "Bo Wu"), ("10", "Prof. Bo Wu")]
    print(local.format_groups(local.group_counts(_spelled(*rows)), 5))
    out = capsys.readouterr().out
    assert out.startswith("11 persons with two or more spellings (22 spellings)")
    assert "title words read in some spellings only (10 persons or more): dr 10" in out
    assert "prof" not in out


@pytest.mark.parametrize(("records", "match"), [
    ([], "holds no records"),
    ([{"name": "ANA", "registry": "ANA"}], "carry no entity and script"),
], ids=["no records", "records with no entity"])
def test_the_groups_view_refuses_records_it_cannot_group(
        records: list[dict[str, str]], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        local.group_counts(local.Local("tse-donors", {"data_date": jrc.JRC_DATE}, records))


def test_the_groups_command_reports_a_fetched_corpus(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _cached(monkeypatch, _LINES)
    _lenient(monkeypatch)
    local.fetch(_JRC)
    capsys.readouterr()
    assert local.main(["groups", _JRC]) == 0
    out = capsys.readouterr().out
    assert out.startswith("JRC-Names (European Commission Joint Research Centre)")
    assert "1 persons with two or more spellings (2 spellings)" in out
    assert "100.0% alike  Cyrillic / Latin" in out


def test_the_groups_command_does_not_hide_a_parser_error_as_damage(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # Only the corpus's own refusals become a one-line exit: a ValueError
    # from parsing a name is a bug, and keeps its traceback.
    _cached(monkeypatch, _LINES)
    _lenient(monkeypatch)
    local.fetch(_JRC)

    def broken(name: str) -> None:
        raise ValueError("a parser bug")
    monkeypatch.setattr(local, "_read", broken)
    with pytest.raises(ValueError, match="a parser bug"):
        local.main(["groups", _JRC])


@pytest.mark.parametrize("top", ["0", "-1"])
def test_the_groups_command_refuses_a_top_under_one(
        monkeypatch: pytest.MonkeyPatch, top: str) -> None:
    # A fetched corpus, so that the refusal is the argument's (argparse
    # exits 2), not the missing corpus's.
    _cached(monkeypatch, _LINES)
    _lenient(monkeypatch)
    local.fetch(_JRC)
    with pytest.raises(SystemExit) as refused:
        local.main(["groups", _JRC, "--top", top])
    assert refused.value.code == 2


def test_the_groups_command_refuses_a_source_with_no_entities(
        monkeypatch: pytest.MonkeyPatch) -> None:
    plant_corpus(monkeypatch, local, "ukec-individuals", [{"name": "Ann Lee"}],
                 jrc.JRC_DATE, "names")
    with pytest.raises(SystemExit, match="carry no entity and script"):
        local.main(["groups", "ukec-individuals"])
