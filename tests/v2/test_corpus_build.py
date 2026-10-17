"""Offline checks on tools/differential/corpus_build.py, the helpers the
labeled-corpus builders share.

The builders' own tests reach these helpers through one builder at a
time; what is pinned here is each helper's contract, and that every
builder can find the module at all. tools/ is not a package, so modules
are loaded by path, as _differential_fixtures.py loads compare.py.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from ._differential_fixtures import _TOOLS, load_tool

corpus_build = load_tool("corpus_build")

_BUILDERS = ("build_cldr_corpus", "build_gnd_corpus", "build_wikidata_corpus")


@pytest.mark.parametrize("stem", _BUILDERS)
def test_each_builder_finds_the_shared_module_on_its_own(
        stem: str, tmp_path: Path) -> None:
    # In a fresh interpreter, from an unrelated cwd and with safe-path on:
    # in the test process an earlier builder's sys.path entry, or a cached
    # import, would hide a builder that forgot its own.
    loader = ("import importlib.util as u, sys; "
              f"s = u.spec_from_file_location('b', {str(_TOOLS / (stem + '.py'))!r}); "
              "m = u.module_from_spec(s); s.loader.exec_module(m); "
              "print(m.corpus_lines is sys.modules['corpus_build'].corpus_lines)")
    result = subprocess.run([sys.executable, "-P", "-c", loader], cwd=tmp_path,
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True"


def test_a_shape_must_be_an_int_or_none() -> None:
    with pytest.raises(TypeError, match="shape must be an int or None, not '4'"):
        corpus_build.corpus_lines([{"text": "A", "shape": "4"}])


def test_an_untagged_line_sorts_before_the_tagged_ones_of_its_text() -> None:
    # Shape 0 is the case to watch: a key that ties it with None leaves
    # the order to set iteration, which a single text can pass by luck.
    texts = [f"name {i}" for i in range(40)]
    rows = [{"text": t, "shape": shape} for t in texts for shape in (0, None, 4)]
    assert corpus_build.corpus_lines(rows) == [
        line for t in sorted(texts)
        for line in (json.dumps(t), json.dumps({"name": t, "shape": 0}),
                     json.dumps({"name": t, "shape": 4}))]


def _row(text: str, order: str = "givenFirst") -> dict[str, object]:
    return {"file": "Q1", "label": "x", "order": order, "text": text,
            "shape": None, "fields": {"given": text}}


def test_write_corpus_writes_the_corpus_and_the_fields_file(tmp_path: Path) -> None:
    corpus, fields = tmp_path / "corpus.jsonl", tmp_path / "fields.jsonl"
    corpus_build.write_corpus([_row("B", "sorting"), _row("A")], corpus, fields)
    assert corpus.read_text(encoding="utf-8") == '"A"\n"B"\n'
    assert [json.loads(line)["order"] for line in
            fields.read_text(encoding="utf-8").splitlines()] == ["givenFirst", "sorting"]


def test_a_refused_row_leaves_both_files_as_they_were(tmp_path: Path) -> None:
    corpus, fields = tmp_path / "corpus.jsonl", tmp_path / "fields.jsonl"
    corpus.write_text("old corpus\n", encoding="utf-8")
    fields.write_text("old fields\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate rendering Q1/x/givenFirst"):
        corpus_build.write_corpus([_row("A"), _row("B")], corpus, fields)
    assert corpus.read_text(encoding="utf-8") == "old corpus\n"
    assert fields.read_text(encoding="utf-8") == "old fields\n"


def _check(body: bytes | str, source: str) -> dict[str, object]:
    data = corpus_build.parse_json(body, source)
    assert isinstance(data, dict)
    return data


def test_an_interrupted_cache_write_leaves_no_cache_file(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The body goes to a .part file and is renamed into place; if the
    # rename never happens, the next run must not find a cached answer.
    def interrupted(src: object, dst: object) -> None:
        raise OSError("interrupted")
    monkeypatch.setattr(corpus_build.os, "replace", interrupted)
    with pytest.raises(OSError, match="interrupted"):
        corpus_build.cached_json(tmp_path, "k", "label", lambda: b'{"a": 1}',
                                 _check, refresh=False)
    assert not list(tmp_path.glob("*.json"))
