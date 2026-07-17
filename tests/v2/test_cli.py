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


def test_cli_json() -> None:
    proc = _run("John Smith", "--json")
    data = json.loads(proc.stdout)
    assert data["given"] == "John" and data["family"] == "Smith"


def test_cli_no_args_usage() -> None:
    proc = _run()
    assert proc.returncode != 0
