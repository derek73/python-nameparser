import json
import subprocess
import sys


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
