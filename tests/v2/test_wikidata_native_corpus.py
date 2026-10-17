"""Offline checks on tools/differential/build_wikidata_native_corpus.py.

The builder is the only part of the native-script corpus that touches
the network, so what it adds to build_wikidata_corpus.py's alignment --
the script filter, character alignment for unspaced text, per-language
feminine surnames, the order a script decides -- is pinned here on
hand-written items in wbgetentities' shape.
"""
import json
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from nameparser import Policy

from ._differential_fixtures import load_tool, serve

native = load_tool("build_wikidata_native_corpus")
wikidata = load_tool("build_wikidata_corpus")
agreement = load_tool("cldr_agreement")

_STRATA = {stratum.label: stratum for stratum in native.STRATA}


def _claim(value: dict[str, str] | str) -> dict[str, Any]:
    return {"rank": "normal", "mainsnak": {"snaktype": "value",
                                           "datavalue": {"value": value}}}


def _person(labels: dict[str, str], native_name: tuple[str, str] | None = None,
            female: bool = False, **parts: str | list[str]) -> dict[str, Any]:
    claims: dict[str, list[dict[str, Any]]] = {}
    for prop, ids in parts.items():
        claims[prop] = [_claim({"id": i}) for i in ([ids] if isinstance(ids, str) else ids)]
    if native_name:
        claims["P1559"] = [_claim({"text": native_name[0], "language": native_name[1]})]
    if female:
        claims["P21"] = [_claim({"id": wikidata.FEMALE})]
    return {"labels": {lang: {"value": text} for lang, text in labels.items()},
            "claims": claims}


def _names(language: str, **labels: str) -> dict[str, Any]:
    return {qid: {"labels": {language: {"value": text}}} for qid, text in labels.items()}


def _one(person: dict[str, Any], names: dict[str, Any], label: str) -> dict[str, Any]:
    [row] = native.renderings("Q1", person, names, _STRATA[label])
    return row


# -- the script filter ------------------------------------------------------------

@pytest.mark.parametrize(("text", "language", "result"), [
    ("Anushka Sharma", "hi", False),        # a `mul` label: Latin, not Devanagari
    ("अनुष्का शर्मा", "hi", True),            # vowel signs are marks of the script
    ("عزت‌الله انتظامی", "fa", True),       # the ZWNJ is not a letter, so not asked
    ("佐々木 勇人", "ja", True),               # 々 is IDEOGRAPHIC, not CJK UNIFIED
    ("長谷川テル", "ja", True),
    ("長谷川テル", "zh", False),             # kana is not Han
    ("Ратко Janković", "sr", False),        # a mixed text is in no one script
    ("·", "zh", False),                     # no letter: in no script
    ("مِحمد", "ar", True),                  # an Arabic point is a mark of the script
    ("محمد\u05b4", "ar", False),            # a Hebrew point is not
])
def test_a_text_is_used_only_in_its_strata_script(text: str, language: str,
                                                  result: bool) -> None:
    assert native.in_script(text, native.LANGUAGES[language].script) is result


def test_a_latin_label_does_not_pass_as_a_native_name() -> None:
    names = {**_names("mul", Q2="Anushka", Q3="Sharma"),
             **_names("hi", Q3="शर्मा")}
    person = _person({"hi": "Anushka Sharma", "mul": "Anushka Sharma"},
                     P735="Q2", P734="Q3")
    assert native.renderings("Q1", person, names, _STRATA["hi-in"]) == []


# -- character alignment ------------------------------------------------------------

def test_an_unspaced_name_is_aligned_by_character() -> None:
    assert native.align_chars("김기영", [("surname", {"김"}), ("given", {"기영"})]) == {
        "surname": [0], "given": [1, 2]}


@pytest.mark.parametrize(("text", "parts"), [
    ("김기영", [("surname", {"김"}), ("given", {"기"})]),        # 영 unclaimed
    ("이이영", [("surname", {"이"}), ("given", {"영"})]),        # 이 in two places
    ("김기영", [("surname", {"김기"}), ("given", {"기영"})]),    # 기 claimed twice
    ("刘放", [("surname", {"刘"})]),                           # the given is unstated
])
def test_an_unspaced_name_not_covered_once_per_character_is_left_out(
        text: str, parts: list[tuple[str, set[str]]]) -> None:
    assert native.align_chars(text, parts) is None


def test_the_widest_spelling_of_a_part_claims_its_characters() -> None:
    # 佐 and 佐々木 both spell the surname item: the narrower match inside
    # the wider one is not a second place.
    assert native.align_chars("佐々木勇人", [("surname", {"佐", "佐々木"}),
                                          ("given", {"勇人"})]) == {
        "surname": [0, 1, 2], "given": [3, 4]}


def test_a_chinese_name_stating_only_its_surname_is_not_used() -> None:
    # Most Chinese items state P734 and no P735: the rest of the text is
    # NOT read as the given name, which would be an inference.
    person = _person({"zh": "王之玺"}, P734="Q2")
    assert native.renderings("Q1", person, _names("zh", Q2="王"), _STRATA["zh-cn"]) == []


# -- the rows ---------------------------------------------------------------------

def test_a_hangul_name_is_ordered_by_its_script() -> None:
    row = _one(_person({"ko": "김기영"}, P734="Q2", P735="Q3"),
               _names("ko", Q2="김", Q3="기영"), "ko-kr")
    assert (row["order"], row["shape"]) == ("surnameFirst", None)
    assert row["fields"] == {"surname": "김", "given": "기영"}


@pytest.mark.parametrize(("label", "surname", "given"), [
    ("zh-cn", "刘", "放"), ("ja-jp", "平賀", "淳")])
def test_a_han_name_is_ordered_by_its_script(label: str, surname: str, given: str) -> None:
    language = native.LANGUAGES[_STRATA[label].language].labels[0]
    row = _one(_person({language: surname + given}, P734="Q2", P735="Q3"),
               _names(language, Q2=surname, Q3=given), label)
    assert (row["order"], row["shape"]) == ("surnameFirst", None)


def test_the_scripts_said_to_decide_the_order_are_the_parsers() -> None:
    # A drift alarm, not a derivation: the builder states which scripts
    # order a name by themselves, so that a parser change shows in the
    # record; this fails when the two stop naming the same scripts.
    assert {script.name for script in dict(Policy().script_orders)} == {
        "HAN", "HANGUL", "HIRAGANA"}
    assert native.script_orders("平賀淳") and native.script_orders("김기영")
    assert native.script_orders("高橋みなみ")       # kana beside Han: licensed
    assert not native.script_orders("サトウハチロー")  # pure katakana: not


def test_a_spaced_han_name_is_ordered_by_its_script_not_by_a_shape() -> None:
    # Family first and spaced: build_wikidata_corpus would tag it
    # FAMILY_FIRST; the script reads it family-first by itself.
    row = _one(_person({"ja": "佐々木 勇人"}, P734="Q2", P735="Q3"),
               _names("ja", Q2="佐々木", Q3="勇人"), "ja-jp")
    assert (row["order"], row["shape"]) == ("surnameFirst", None)


def test_a_pure_katakana_name_keeps_the_family_first_shape() -> None:
    # The parser leaves pure katakana to the declared order (a transcribed
    # foreign name), so the script decides nothing here.
    row = _one(_person({"ja": "サトウ ハチロー"}, P734="Q2", P735="Q3"),
               _names("ja", Q2="サトウ", Q3="ハチロー"), "ja-jp")
    assert (row["order"], row["shape"]) == ("surnameFirst", wikidata.FAMILY_FIRST_SHAPE)


def test_an_unspaced_pure_katakana_name_keeps_the_family_first_shape() -> None:
    row = _one(_person({"ja": "サトウハチロー"}, P734="Q2", P735="Q3"),
               _names("ja", Q2="サトウ", Q3="ハチロー"), "ja-jp")
    assert (row["order"], row["shape"]) == ("surnameFirst", wikidata.FAMILY_FIRST_SHAPE)
    row = _one(_person({"ja": "ハチローサトウ"}, P734="Q2", P735="Q3"),
               _names("ja", Q2="サトウ", Q3="ハチロー"), "ja-jp")
    assert (row["order"], row["shape"]) == ("givenFirst", None)


def test_a_one_word_name_outside_the_unspaced_scripts_is_never_split() -> None:
    # Only Han, kana and Hangul are aligned by character: an Arabic
    # compound written as one word is one word, never a given name and a
    # surname cut from it.
    person = _person({"ar": "عبدالله"}, P735="Q2", P734="Q3")
    assert native.renderings("Q1", person, _names("ar", Q2="عبد", Q3="الله"),
                             _STRATA["ar-eg"]) == []


def test_a_spaced_name_in_another_script_is_ordered_as_written() -> None:
    row = _one(_person({"ka": "ნოდარ ცინცაძე"}, P734="Q2", P735="Q3"),
               _names("ka", Q2="ცინცაძე", Q3="ნოდარ"), "ka-ge")
    assert (row["order"], row["shape"]) == ("givenFirst", None)
    row = _one(_person({"uk": "Полунін Михайло Степанович"},
                       P734="Q2", P735="Q3", P5056="Q4"),
               _names("uk", Q2="Полунін", Q3="Михайло", Q4="Степанович"), "uk-ua")
    assert (row["order"], row["shape"]) == ("surnameFirst", wikidata.FAMILY_FIRST_SHAPE)
    assert row["fields"]["patronymic"] == "Степанович"


def test_the_native_name_wins_and_one_rendering_is_kept() -> None:
    person = _person({"ja": "鍵山秀三郎"}, native_name=("鍵山 秀三郎", "ja"),
                     P734="Q2", P735="Q3")
    rows = native.renderings("Q1", person, _names("ja", Q2="鍵山", Q3="秀三郎"),
                             _STRATA["ja-jp"])
    assert [row["text"] for row in rows] == ["鍵山 秀三郎"]


def test_a_given_name_and_a_surname_are_both_required() -> None:
    person = _person({"he": "אהרן"}, P735="Q3", P734="Q2")    # no surname written
    assert native.renderings("Q1", person, _names("he", Q2="הלוי", Q3="אהרן"),
                             _STRATA["he-il"]) == []
    person = _person({"ko": "김"}, P735="Q3", P734="Q2")       # no given name written
    assert native.renderings("Q1", person, _names("ko", Q2="김", Q3="기영"),
                             _STRATA["ko-kr"]) == []


def test_a_name_in_a_variant_language_is_used() -> None:
    # A zh-tw person may be labelled only in zh-hant.
    row = _one(_person({"zh-hant": "李正中"}, P734="Q2", P735="Q3"),
               _names("zh-hant", Q2="李", Q3="正中"), "zh-tw")
    assert row["text"] == "李正中"


def test_a_native_name_in_another_language_is_not_used() -> None:
    # A ja P1559 on a Chinese stratum is not a Chinese name, even in Han.
    person = _person({}, native_name=("李正中", "ja"), P734="Q2", P735="Q3")
    assert native.renderings("Q1", person, _names("zh", Q2="李", Q3="正中"),
                             _STRATA["zh-tw"]) == []


# -- feminine surnames ---------------------------------------------------------------

@pytest.mark.parametrize(("language", "male", "female"), [
    ("el", "Λελούδας", "Λελούδα"), ("el", "Γεωργιάδης", "Γεωργιάδου"),
    ("el", "Παπαδόπουλος", "Παπαδοπούλου"), ("el", "Παπαδάκης", "Παπαδάκη"),
    ("el", "Ευαγγελάτος", "Ευαγγελάτου"),
    ("uk", "Шевченко", ""), ("uk", "Заньківський", "Заньківська"),
    ("uk", "Полунін", "Полуніна"),
    ("bg", "Марков", "Маркова"), ("bg", "Стоянски", "Стоянска"),
    ("kk", "Тұрлыханов", "Тұрлыханова"),
])
def test_feminine_forms_by_language(language: str, male: str, female: str) -> None:
    assert wikidata.feminine(male, native.LANGUAGES[language].feminine) == female


@pytest.mark.parametrize("text", ["Тарас Шевченко", "Оксана Полунін"])
def test_a_womans_surname_still_matches_as_its_item_spells_it(text: str) -> None:
    # The feminine forms are added to the item's spellings, not put in
    # their place: a surname with no feminine form (Шевченко), or one a
    # woman writes as the item does, still matches.
    given, surname = text.split()
    row = _one(_person({"uk": text}, female=True, P734="Q2", P735="Q3"),
               _names("uk", Q2=surname, Q3=given), "uk-ua")
    assert row["fields"]["surname"] == surname


def test_a_womans_greek_surname_matches_its_feminine_form() -> None:
    names = _names("el", Q2="Λελούδας", Q3="Ντόρα")
    woman = _person({"el": "Ντόρα Λελούδα"}, female=True, P734="Q2", P735="Q3")
    assert _one(woman, names, "el-gr")["fields"]["surname"] == "Λελούδα"
    man = _person({"el": "Ντόρα Λελούδα"}, P734="Q2", P735="Q3")
    assert native.renderings("Q1", man, names, _STRATA["el-gr"]) == []


def test_the_russian_default_is_unchanged() -> None:
    assert wikidata.feminine("Достоевский") == "Достоевская"


# -- the build --------------------------------------------------------------------

def _stub_build(monkeypatch: pytest.MonkeyPatch, strata: tuple[Any, ...],
                pooled: dict[str, list[str]]) -> None:
    people = {q: _person({"ko": "김기영"}, P734="Q2", P735="Q3")
              for qs in pooled.values() for q in qs}
    if "Q11" in people:
        people["Q11"]["claims"]["P244"] = [_claim("n82128473")]
    if "Q12" in people:  # past the first stratum's quota: never taken, so never kept
        people["Q12"]["claims"]["P244"] = [_claim("n99999999")]
    names = _names("ko", Q2="김", Q3="기영")
    monkeypatch.setattr(native, "STRATA", strata)
    monkeypatch.setattr(native, "pool", lambda stratum, refresh: pooled[stratum.label])
    monkeypatch.setattr(native, "entities", lambda ids, language, refresh:
                        {**{q: people[q] for q in ids if q in people},
                         **{q: names[q] for q in ids if q in names}})


def test_build_takes_each_person_once_up_to_the_quota(
        monkeypatch: pytest.MonkeyPatch) -> None:
    first = native.Stratum("first", "Q884", "ko", 2, 3)
    second = native.Stratum("second", "Q884", "ko", 2, 3)
    _stub_build(monkeypatch, (first, second),
                {"first": ["Q10", "Q11", "Q12"], "second": ["Q11", "Q13", "Q14"]})
    rows, lccns = native.build(refresh=False)
    taken = {lab: [r["file"] for r in rows if r["label"] == lab]
             for lab in ("first", "second")}
    assert taken == {"first": ["Q10", "Q11"], "second": ["Q13", "Q14"]}
    assert lccns == {"Q11": "n82128473"}


def test_build_stops_before_writing_when_a_stratum_falls_short(
        monkeypatch: pytest.MonkeyPatch) -> None:
    thin = native.Stratum("thin", "Q884", "ko", 5, 5, least=3)
    _stub_build(monkeypatch, (thin,), {"thin": ["Q10", "Q11"]})
    with pytest.raises(ValueError, match="thin 2/3"):
        native.build(refresh=False)


def test_a_missing_pooled_person_stops_the_build(monkeypatch: pytest.MonkeyPatch) -> None:
    stratum = native.Stratum("s", "Q884", "ko", 1, 1)
    _stub_build(monkeypatch, (stratum,), {"s": ["Q10"]})
    monkeypatch.setattr(native, "entities", lambda ids, language, refresh:
                        {q: {"id": q, "missing": ""} for q in ids})
    with pytest.raises(ValueError, match="s: WDQS pooled items .*missing: Q10"):
        native.build(refresh=False)


def test_a_deprecated_lccn_is_not_read() -> None:
    person = {"claims": {"P244": [{**_claim("n1"), "rank": "deprecated"}, _claim("n2")]}}
    assert native.lccn(person) == "n2"
    assert native.lccn({"claims": {}}) is None


def test_a_query_names_the_strata_label_language() -> None:
    stratum = _STRATA["zh-cn"]
    assert 'FILTER(LANG(?own) = "zh")' in native.query(stratum)
    assert f"LIMIT {stratum.pool}" in native.query(stratum)


# -- the network and the cache ------------------------------------------------

def _results(n: int) -> bytes:
    return json.dumps({"results": {"bindings": [
        {"item": {"value": f"http://www.wikidata.org/entity/Q{i}"}}
        for i in range(n)]}}).encode()


def test_a_query_matching_nothing_stops_the_build(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    serve(monkeypatch, tmp_path, _results(0))
    with pytest.raises(ValueError, match="ko-kr: the query matches nothing"):
        native.pool(_STRATA["ko-kr"], refresh=False)


def test_a_pool_short_of_its_size_stops_the_build_unless_it_is_the_whole(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    serve(monkeypatch, tmp_path, _results(5))
    with pytest.raises(ValueError, match="ko-kr: the query matched 5 people, fewer "
                                         "than its pool of 300"):
        native.pool(_STRATA["ko-kr"], refresh=False)
    assert len(native.pool(_STRATA["th-th"], refresh=False)) == 5


def test_a_stratum_marked_whole_whose_pool_fills_stops_the_build(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # The population has outgrown the mark, which would otherwise go on
    # excusing a short pool.
    whole = native.Stratum("w", "Q869", "th", 1, 3, whole=True)
    serve(monkeypatch, tmp_path, _results(3))
    with pytest.raises(ValueError, match="w: marked whole=True, but the query filled"):
        native.pool(whole, refresh=False)


def test_entities_asks_only_for_the_languages_labels(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fetched = serve(monkeypatch, tmp_path, b'{"entities": {"Q1": {"id": "Q1"}}}')
    native.entities(["Q1"], "zh", refresh=False)
    [url] = fetched
    assert "languages=zh%7Czh-hans%7Czh-hant%7Czh-cn%7Czh-tw%7Czh-hk%7Cmul" in url


def test_an_lc_record_is_cached_and_read_back(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sleeps: list[float] = []
    fetched = serve(monkeypatch, tmp_path, _MARC.encode(), sleeps=sleeps)
    assert native.lc_variants("nr93008484", refresh=False) == ["הלוי, אהרן", "이 병기"]
    assert native.lc_variants("nr93008484", refresh=False) == ["הלוי, אהרן", "이 병기"]
    assert len(fetched) == 1
    assert sleeps == [1]  # one fetch, one polite wait; the cached read waits for nothing


def _fail(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, code: int) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))

    def urlopen(request: urllib.request.Request, timeout: int) -> None:
        raise urllib.error.HTTPError(request.full_url, code, "x", {}, None)  # type: ignore[arg-type]
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)


def test_an_lccn_lc_no_longer_has_is_none_and_not_cached(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fail(monkeypatch, tmp_path, 404)
    assert native.lc_variants("n0", refresh=False) is None
    assert not list((tmp_path / "lc").iterdir())


def test_any_other_lc_error_stops_the_check(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fail(monkeypatch, tmp_path, 503)
    with pytest.raises(urllib.error.HTTPError) as caught:
        native.lc_variants("n0", refresh=False)
    caught.value.close()  # unclosed, it warns on 3.14 and fails the run


def test_the_lc_check_tallies_each_name_once(monkeypatch: pytest.MonkeyPatch,
                                            capsys: pytest.CaptureFixture[str]) -> None:
    rows = [{"file": q, "label": "he-il", "text": "אהרן הלוי",
             "fields": {"given": "אהרן", "surname": "הלוי"}} for q in ("Q1", "Q2", "Q3")]
    variants = {"n2": ["הלוי, אהרן"], "n3": ["אהרן, הלוי"]}
    monkeypatch.setattr(native, "lc_variants", lambda lccn, refresh: variants[lccn])
    native.lc_check(rows, {"Q2": "n2", "Q3": "n3"}, refresh=False)
    out = capsys.readouterr().out
    assert ("names 3, with an LCCN 2, no LC record 0, LC splits it 2, agree 1"
            in out)
    assert "1 split differently" in out and "Q3" in out


def test_the_lc_check_counts_a_stale_lccn(monkeypatch: pytest.MonkeyPatch,
                                         capsys: pytest.CaptureFixture[str]) -> None:
    row = {"file": "Q1", "label": "he-il", "text": "אהרן הלוי",
           "fields": {"given": "אהרן", "surname": "הלוי"}}
    monkeypatch.setattr(native, "lc_variants", lambda lccn, refresh: None)
    native.lc_check([row], {"Q1": "n0"}, refresh=False)
    assert "no LC record 1, LC splits it 0" in capsys.readouterr().out


# -- the LC cross-check ------------------------------------------------------------

_MARC = """<record xmlns="http://www.loc.gov/MARC21/slim">
<datafield tag="100" ind1="1"><subfield code="a">Haleṿi, Aharon</subfield></datafield>
<datafield tag="400" ind1="1"><subfield code="a">הלוי, אהרן</subfield></datafield>
<datafield tag="400" ind1="1"><subfield code="a">이 병기,</subfield>
<subfield code="d">1891-1968</subfield></datafield>
</record>"""


def test_an_lc_record_yields_its_variants() -> None:
    assert native._lc_checked(_MARC, "x") == {"variants": ["הלוי, אהרן", "이 병기"]}
    with pytest.raises(ValueError, match="not MARC XML"):
        native._lc_checked("<html>", "x")
    with pytest.raises(ValueError, match="not a MARC record"):
        native._lc_checked("<feed/>", "x")


@pytest.mark.parametrize(("text", "variants", "split"), [
    ("אהרן הלוי", ["הלוי, אהרן"], ("הלוי", "אהרן")),     # the comma
    ("이병기", ["이병기", "이 병기"], ("이", "병기")),          # a CJK space
    ("李秉岐", ["李秉岐"], None),                            # unspaced: no split
    ("אהרן הלוי", ["Haleṿi, Aharon"], None),               # other letters
    ("إبراهيم صالح", ["صالح، إبراهيم"], ("صالح", "إبراهيم")),  # the Arabic comma
    # the comma's words in the text's own order: LC's family still leads
    ("إبراهيم صالح", ["إبراهيم، صالح"], ("إبراهيم", "صالح")),
    # no comma, and the text is spaced: a space splits only unspaced CJK
    ("إبراهيم صالح", ["إبراهيم صالح"], None),
])
def test_lc_splits_a_name_by_its_comma_or_a_cjk_space(
        text: str, variants: list[str], split: tuple[str, str] | None) -> None:
    assert native.lc_split({"text": text}, variants) == split


# -- the committed files ---------------------------------------------------------------

_ROWS = agreement.load_rows(agreement.NATIVE_FIELDS)


def test_each_committed_stratum_holds_what_the_build_promises() -> None:
    names = {label: {row["file"] for row in _ROWS if row["label"] == label}
             for label in {row["label"] for row in _ROWS}}
    assert set(names) == set(_STRATA)
    for label, ids in names.items():
        assert _STRATA[label].floor <= len(ids) <= _STRATA[label].quota, label
    # one rendering per person, and one stratum
    assert set(Counter(row["file"] for row in _ROWS).values()) == {1}


def test_every_committed_text_is_in_its_strata_script() -> None:
    assert not [row["text"] for row in _ROWS if not native.in_script(
        row["text"], native.LANGUAGES[_STRATA[row["label"]].language].script)]


def test_every_han_and_kana_stratum_is_scored_under_its_pack() -> None:
    # Both ways: a zh or ja stratum missing from the scorer's NATIVE_LABELS
    # would never be parsed with its pack, and nothing else would notice.
    packs = {"zh": "ZH", "ja": "JA"}
    assert agreement.NATIVE_LABELS == {s.label: packs[s.language]
                                       for s in native.STRATA if s.language in packs}


def test_a_committed_rendering_its_script_orders_has_no_shape() -> None:
    assert not [row["text"] for row in _ROWS
                if native.script_orders(row["text"]) and row["shape"] is not None]
