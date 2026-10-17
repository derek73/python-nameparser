"""Regenerate the CLDR corpus from Unicode CLDR's person-name test data.

A corpus with its own provenance. Each corpus covers a blind spot the
others have -- the roster, with each file's source and the blind spot it
leaves, is the table in tools/differential/README.md. This one is the
first whose names come with GROUND TRUTH from outside the project: CLDR's
person-name formatting tests state every name's fields separately (title,
given, given2, surname or surname-prefix + surname-core, surname2,
generation, credentials) and render it in about 110 locales, in their
native scripts. Every other corpus holds strings someone here chose or
reported; nothing in them says what the right answer is.

    uv run python tools/differential/build_cldr_corpus.py

Writes three files beside this script, always together:

- corpus_cldr.jsonl -- one line per distinct (rendering, shape), in the
  existing corpus line format, read by snapshot.py like every other
  corpus.
- cldr_fields.jsonl -- one line per rendering, with CLDR's fields, read
  by cldr_agreement.py and its ratchet test.
- cldr_LICENSE -- the Unicode License v3 notice, which must travel with
  the data. It is a separate file because the corpus loader
  (compare._load_entries) refuses any line that is not JSON.

Selection: each test name's long, referring, formal rendering in each of
the three orders CLDR formats -- givenFirst, surnameFirst and sorting.
Those are the full-name strings; the medium, short and monogram forms
drop or abbreviate parts. CLDR deliberately renders some names in an
order their culture does not use (a Japanese name given-first) to test
formatting; those stay in, and the ratchet simply does not guard what
does not agree.

Shape: a surnameFirst rendering, and a sorting rendering without a
comma, is tagged shape 4 (FAMILY_FIRST in shapes.py), so the harness
and the ratchet both parse it under the order it declares. A comma
carries its own order, and givenFirst is the default.

Blind to: real-world name distributions. These are fictional names
written by a formatting committee to exercise every field, so they
over-represent full-house names (title, two given names, prefixed and
double surnames, generation and credentials) and under-represent the
plain two-word names most data holds.

Pinned to CLDR_TAG; moving it is a deliberate edit and a rebuild.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

# The shared cache and file helpers (corpus_build.py), found by putting
# this directory on sys.path: see corpus_build's docstring for why.
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.append(_HERE)

from corpus_build import corpus_lines, fields_lines, write_corpus  # noqa: E402,F401

HERE = Path(__file__).resolve().parent
CLDR_TAG = "release-48"
_REPO = "unicode-org/cldr"
_DIR = "common/testData/personNameTest"
LIST_URL = f"https://api.github.com/repos/{_REPO}/contents/{_DIR}?ref={CLDR_TAG}"
RAW = f"https://raw.githubusercontent.com/{_REPO}/{CLDR_TAG}"
CORPUS = HERE / "corpus_cldr.jsonl"
FIELDS = HERE / "cldr_fields.jsonl"
LICENSE = HERE / "cldr_LICENSE"
ORDERS = ("givenFirst", "surnameFirst", "sorting")
LABELS = frozenset({"nativeG", "nativeGS", "nativeGGS", "nativeFull",
                    "foreignG", "foreignGS", "foreignGGS", "foreignFull"})
FAMILY_FIRST_SHAPE = 4
USER_AGENT = ("python-nameparser build_cldr_corpus "
              "(https://github.com/derek73/python-nameparser)")


def shape_for(order: str, text: str) -> int | None:
    """Shape 4 for a rendering written surname-first without a comma to
    say so; None where the default order or the comma carries it."""
    if order == "surnameFirst" or (order == "sorting" and "," not in text):
        return FAMILY_FIRST_SHAPE
    return None


def parse_test_file(text: str, stem: str) -> list[dict[str, object]]:
    """The selected renderings of one personNameTest file.

    The format: a `# <label>` comment, then `name ; <field> ; <value>`
    lines, then pairs of `expectedResult; <string>` followed by the
    `parameters; <order>; <length>; <usage>; <formality>` lines that
    string answers, then `endName`. Anything else is refused, so a format
    change in a later CLDR release fails the build instead of quietly
    yielding fewer names.
    """
    rows: list[dict[str, object]] = []
    label: str | None = None
    fields: dict[str, str] = {}
    results: dict[tuple[str, ...], str] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            candidate = line.lstrip("#").strip()
            if not fields and candidate in LABELS:
                label = candidate
            continue
        kind = line.split(";", 1)[0].strip()
        if kind == "enum":
            continue
        if kind == "name":
            _, field, value = (p.strip() for p in line.split(";", 2))
            fields[field] = value
        elif kind == "expectedResult":
            current = line.split(";", 1)[1].strip()
        elif kind == "parameters":
            if current is None:
                raise ValueError(f"{stem}: parameters before any expectedResult")
            results[tuple(p.strip() for p in line.split(";")[1:])] = current
        elif kind == "endName":
            if label is None:
                raise ValueError(f"{stem}: a name ends with no label comment before it")
            for order in ORDERS:
                rendered = results.get((order, "long", "referring", "formal"))
                if rendered:
                    rows.append({"file": stem, "label": label, "order": order,
                                 "text": rendered,
                                 "shape": shape_for(order, rendered),
                                 "fields": dict(fields)})
            label, fields, results, current = None, {}, {}, None
        else:
            raise ValueError(f"{stem}: unknown line kind {kind!r}: {line!r}")
    return rows


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        data: bytes = response.read()
    return data


def main() -> None:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()
    listing = json.loads(_get(LIST_URL))
    names = sorted(item["name"] for item in listing
                   if item["name"].endswith(".txt") and not item["name"].startswith("_"))
    rows: list[dict[str, object]] = []
    for name in names:
        text = _get(f"{RAW}/{_DIR}/{name}").decode("utf-8")
        rows.extend(parse_test_file(text, name[:-len(".txt")]))
    write_corpus(rows, CORPUS, FIELDS)
    LICENSE.write_bytes(_get(f"{RAW}/LICENSE"))
    print(f"CLDR {CLDR_TAG}: {len(names)} files, {len(rows)} renderings; "
          f"wrote {CORPUS.name}, {FIELDS.name}, {LICENSE.name}")


if __name__ == "__main__":
    main()
