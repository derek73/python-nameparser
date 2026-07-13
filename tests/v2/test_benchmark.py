"""Perf smoke (core spec §7 tail): parse cost stays v1-comparable
(microseconds per name). Deliberately generous bound -- guards against
order-of-magnitude regressions, does not gate normal variance."""
import time

from nameparser import parse


def test_parse_thousand_names_under_a_second() -> None:
    parse("warm up the default parser cache")
    start = time.perf_counter()
    for i in range(1000):
        parse(f"Dr. Juan{i} de la Vega III")
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, f"1000 parses took {elapsed:.2f}s"
