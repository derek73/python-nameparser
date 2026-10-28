"""Offline checks on tools/differential/measure.py.

What these pin is the plan (which steps run for which fetched corpora,
in order, each handed --base and --jobs), the summary's refusal to
carry an indented line (where the tools list names), and that a failed
step fails the run while a step reporting moves does not. The steps
themselves are each tool's own tests'.
"""
import json
import sys
from pathlib import Path

import pytest

from ._differential_fixtures import load_tool, own_cache

measure = load_tool("measure")
corpora = measure.local_corpora


@pytest.fixture(autouse=True)
def _own_cache(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return own_cache(monkeypatch, tmp_path_factory)


def _fetch(cache: Path, *sources: str) -> None:
    """`sources` marked fetched: the plan reads meta.json's presence."""
    for source in sources:
        folder = cache / "local" / source
        folder.mkdir(parents=True)
        (folder / corpora.META).write_text(json.dumps({}))


def test_the_plan_runs_each_check_for_the_corpora_fetched(_own_cache: Path,
                                                          tmp_path: Path) -> None:
    _fetch(_own_cache, "ctgov-officials", corpora.PSC, corpora.JRC, corpora.ORCID,
           corpora.PV, "tse-donors")
    steps = measure.plan(tmp_path, 3)
    assert [s.label for s in steps] == [
        "committed snapshot", "CLDR and GND agreement",
        "local snapshot ctgov-officials", f"local snapshot {corpora.JRC}",
        f"local snapshot {corpora.ORCID}", f"local snapshot {corpora.PV}",
        f"local snapshot {corpora.PSC}", "local snapshot tse-donors",
        f"agreement {corpora.ORCID}", f"agreement {corpora.PV}",
        f"agreement {corpora.PSC}", f"alike {corpora.JRC}", "alike tse-donors"]
    for step in steps:
        # Every step through the wrapper: unwrapped, a refusal reads as moves.
        assert step.command[:3] == [sys.executable, str(measure.HERE / "measure.py"), "--step"]
        if step.label.startswith(("local", "agreement", "alike")):
            assert step.command[-4:] == ["--base", str(tmp_path), "--jobs", "3"]
            assert step.against == measure.AGAINST_BASE
        else:
            assert step.against == measure.AGAINST_RECORD
    assert steps[0].command[-2:] == ["--jobs", "3"]
    assert measure.unmeasured() == sorted(set(corpora.SOURCES) - {
        "ctgov-officials", corpora.PSC, corpora.JRC, corpora.ORCID, corpora.PV, "tse-donors"})


def test_the_plan_with_nothing_fetched_runs_the_committed_checks(tmp_path: Path) -> None:
    assert [s.label for s in measure.plan(tmp_path, 1)] == [
        "committed snapshot", "CLDR and GND agreement"]


def test_the_summary_keeps_the_counts_and_drops_the_listed_names() -> None:
    # snapshot.py's grouped moves: a count flush left, each name indented.
    output = ("base: /b, nameparser/ abc; reused\n\nfamily, given: 2\n    Ann Zyx\n"
              "      given: 'Ann' -> ''\n    Bo Qwv\n\n2 entries differ from the base /b\n")
    assert measure.digest(output) == ["base: /b, nameparser/ abc; reused",
                                      "family, given: 2", "2 entries differ from the base /b"]
    # Past the cap, the head and the tail, where a tool prints its
    # verdict, and a not-measured line from between.
    many = [f"line {i}" for i in range(measure.SUMMARY_LINES + 5)]
    many[6] = "JA ja-jp: not measured (needs namedivider)"
    kept = measure.digest("\n".join(many))
    head = measure.HEAD_LINES
    assert kept[:head] == many[:head]
    assert kept[-(measure.SUMMARY_LINES - head):] == many[head - measure.SUMMARY_LINES:]
    assert kept[head:head + 2] == [many[6], "... 4 more lines"]


def test_a_failed_step_fails_the_run_and_one_with_moves_does_not(
        monkeypatch: pytest.MonkeyPatch, _own_cache: Path, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    base = tmp_path / "base"
    (base / "nameparser").mkdir(parents=True)
    (base / "nameparser" / "__init__.py").write_text("")
    _fetch(_own_cache, "ukec-individuals")
    codes = {"committed snapshot": 1, "CLDR and GND agreement": 0}

    def run(step: object) -> object:
        label = step.label  # type: ignore[attr-defined]
        return measure.Done(step, codes.get(label, 0), 1.0, f"{label} out\n    Ann Zyx\n")
    monkeypatch.setattr(measure, "run", run)
    out = tmp_path / "out"
    assert measure.main(["--base", str(base), "--out", str(out)]) == 0
    summary = (out / "summary.txt").read_text()
    assert "Zyx" not in summary
    assert "none failed" in summary
    assert "== committed snapshot (against this branch's committed record): moves" in summary
    assert "not measured, not fetched: ctgov-officials," in summary
    assert (out / "01-committed-snapshot.txt").read_text().endswith("Ann Zyx\n")
    codes["CLDR and GND agreement"] = 2
    assert measure.main(["--base", str(base), "--out", str(out)]) == 1
    assert "failed: CLDR and GND agreement" in capsys.readouterr().out


def test_a_step_is_run_from_the_checkout_and_its_output_kept(tmp_path: Path) -> None:
    step = measure.Step("echo", [sys.executable, "-c",
                                 "import os, sys; print(os.getcwd()); sys.exit(1)"])
    done = measure.run(step)
    assert (done.code, done.status) == (1, "moves")
    assert done.output.strip() == str(measure.HERE.parents[1])
    assert measure.Done(step, 3, 0.0, "").status == "FAILED (exit 3)"


def test_a_base_that_is_this_checkout_is_refused() -> None:
    with pytest.raises(SystemExit, match="is the tree being read"):
        measure.main(["--base", str(measure.HERE.parents[1])])


def _wrapped(tmp_path: Path, body: str) -> object:
    """A step running a script of `body` through measure.py's --step
    wrapper, as every planned step runs."""
    script = tmp_path / "tool.py"
    script.write_text(body, encoding="utf-8")
    return measure.run(measure.Step("tool", [sys.executable, str(measure.HERE / "measure.py"),
                                             "--step", str(script), "--flag"]))


@pytest.mark.parametrize(("body", "status"), [
    ("import sys; sys.exit(0)", "no moves"),
    ("import sys; sys.exit(1)", "moves"),
    ("print('no exit')", "no moves"),
    # A tool's refusal and a crash both exit 1 unwrapped, which reads as
    # moves; the wrapper is what tells them from a result.
    ("raise SystemExit('refused: a damaged corpus')", "FAILED (exit 2)"),
    ("raise ValueError('a bug')", "FAILED (exit 2)"),
    ("import sys; sys.exit(3)", "FAILED (exit 3)"),
])
def test_a_refusal_or_a_crash_fails_a_step_and_moves_do_not(
        tmp_path: Path, body: str, status: str) -> None:
    done = _wrapped(tmp_path, body)
    assert done.status == status  # type: ignore[attr-defined]


def test_the_wrapper_hands_the_tool_its_arguments(tmp_path: Path) -> None:
    done = _wrapped(tmp_path, "import sys; print(sys.argv[1:])")
    assert done.output.strip() == "['--flag']"  # type: ignore[attr-defined]


def test_a_name_holding_a_line_break_stays_in_its_indented_line(tmp_path: Path) -> None:
    # Cut by str.splitlines(), or read in text mode (which turns \r into
    # \n), the rest of each name would stand flush left in the summary.
    done = _wrapped(tmp_path, "import sys; sys.stdout.buffer.write("
                              "'fields: 3\\n    Ann\\rZyx\\n    Bo\\u2028Qwv\\n    Cy\\x85Vex\\n'"
                              ".encode())")
    kept = measure.digest(done.output)  # type: ignore[attr-defined]
    assert kept == ["fields: 3"]


def test_a_run_with_no_local_corpus_fetched_fails_and_says_why(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # The committed steps compare with the branch's own records, so with
    # nothing fetched no step read --base: a clean run's look-alike.
    base = tmp_path / "base"
    (base / "nameparser").mkdir(parents=True)
    (base / "nameparser" / "__init__.py").write_text("")
    monkeypatch.setattr(measure, "run", lambda step: measure.Done(step, 0, 0.0, ""))
    out = tmp_path / "out"
    assert measure.main(["--base", str(base), "--out", str(out)]) == 1
    summary = (out / "summary.txt").read_text()
    assert "none failed" in summary and "no step read --base" in summary


def test_a_crash_s_message_stays_out_of_the_summary(tmp_path: Path) -> None:
    # An exception's message may hold a name; only its type is flush left.
    done = _wrapped(tmp_path, "raise KeyError('Ann Zyx')")
    assert done.status == "FAILED (exit 2)"  # type: ignore[attr-defined]
    kept = measure.digest(done.output)  # type: ignore[attr-defined]
    assert kept == ["uncaught KeyError; its traceback, indented:"]
    assert "Ann Zyx" in done.output  # type: ignore[attr-defined]
