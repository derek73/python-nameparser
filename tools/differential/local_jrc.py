"""The jrc-names local corpus: the person names of the JRC-Names resource.

jrc-names -- the person entities of the EU Joint Research Centre's
JRC-Names (wt-public.emm4u.eu), each with the spellings of its name
harvested from news text in many languages and scripts: a record is one
spelling, with the entity it spells and the script it is written in.
The one local corpus that holds several spellings of one person across
scripts (tse-donors pairs two spellings, both Latin), so it is the
population for spelling and transliteration variants, read by
local_corpora.py's `groups` view (25,415 persons are spelled in two
scripts or more, a "mixed" or "none" script() not counted), and for
Arabic-script names: 17,074 spellings of
7,833 persons, 5,347 of them spelled in Latin too, in the file dated
2024-03-15. Latin is most of it (1,203,634 of 1,317,586 spellings, then
Cyrillic 66,673, Katakana 13,039 and Han 8,016); the Indic scripts are
few (Devanagari 827 spellings, Bengali 419, Tamil 328, Malayalam 183,
the rest under 80 each). 1,510 of the Arabic spellings hold an Arabic
comma (U+060C), which the parser reads as a comma.

Licensed under the JRC-Names EULA (Resources/LICENCE-EULA_JRC-Names_2011.pdf
on the same site): a personal, non-exclusive, non-transferable licence
that bars redistribution, sublicensing and derivative works. So nothing
read from it is committed, not a name, not a per-name reading: the
download, the corpus, its snapshot and every file derived from them stay
in the cache, and what a contributor cites is counts and shapes written
with made-up names, as for every local corpus.
"""
from __future__ import annotations

import gzip
import hashlib
import os
import re
import unicodedata
import zlib
from collections import Counter
from pathlib import Path
from typing import Any

from local_core import Fetched, _download, _pinned, _refuse_past, directory, fetch_command


JRC = "jrc-names"
JRC_URL = "https://wt-public.emm4u.eu/data/entities.gzip"
#: The download, cached beside the corpus.
JRC_FILE = "entities.gzip"
#: The file this tool was written against, pinned: the JRC says the
#: resource is updated daily, but the file served on 2026-10-24 was last
#: modified on the date below. A download with another sha256 is refused
#: until someone has measured it and moved the pin, since a layout the
#: constants below were not measured on would otherwise read as a
#: smaller corpus.
JRC_SHA256 = "43144cee881ba8a81573ae28c089dffce0ca634d342791414628a5d54997a7d0"
#: The pinned file's Last-Modified, its data date: the file states none.
JRC_DATE = "2024-03-15T14:08:28Z"
#: How the file is read into records, stored in meta.json's detail: a
#: change to what _jrc_read keeps or to script() bumps it, so that a
#: corpus read the old way is refused on load (check_jrc) rather than
#: counted under labels the code no longer gives.
JRC_READ_VERSION = 1
#: A line: entity id, type, language and name, tab-separated, the name's
#: words joined by "+". Lines end in CRLF.
JRC_COLUMNS = 4
JRC_PERSON, JRC_ORGANISATION = "P", "O"
#: The language of a spelling the JRC did not mark: 1,317,644 of the
#: 1,338,463 person rows. A row with any other language is a
#: morphological variant of one that has it: an inflected form (a
#: Russian name in another case, a Slovene or Polish one with its case
#: ending) or an Arabic one with a word glued to it (و "and", ل "for",
#: ال "the"). Of the 20,819 marked rows in the pinned file, every one's
#: entity also held an unmarked spelling, and 18,594 had the same number
#: of words as one and, word by word in order, either every word the
#: same or sharing at least its first letter with the other and no more
#: than three letters past their common start (an ending), or every word
#: the other with no more than three letters glued to its front (a
#: prefix); so the fetch drops them, counted by language,
#: rather than read an ending or a conjunction as part of a name. The
#: unmarked spellings still hold some inflected forms the JRC did not
#: mark: 22,732 of the 66,673 distinct unmarked spellings whose script()
#: is Cyrillic are, by the ending rule above, another Cyrillic spelling
#: of the same entity (some may be two transliterations rather than an
#: inflection; the two were not measured apart), and they are kept.
JRC_UNMARKED = "u"
_LANGUAGE = re.compile(r"[a-z]{2,3}")
#: The share of lines read past (not JRC_COLUMNS columns, not UTF-8, a
#: type other than JRC_PERSON or JRC_ORGANISATION, an id that is not
#: digits, a language that is not a code, a name that is empty) before
#: the file is refused: 1 of the pinned file's 1,445,013 lines was, its
#: first, "#".
JRC_MAX_BAD = 1 / 10_000
#: The least share of well-formed lines that are people before the file
#: is refused: 1,338,463 of 1,445,012 (93%) in the pinned file. A type
#: renamed would otherwise read as a corpus of none.
JRC_MIN_PERSONS = 1 / 2
#: The most person rows that may carry a language before the file is
#: refused: 20,819 of 1,338,463 (1.6%) in the pinned file. A file whose
#: every row came marked would otherwise be dropped whole.
JRC_MAX_MARKED = 1 / 10

#: A script's name as the first word of its letters' Unicode names
#: gives it, where that word is not the script's own name.
_SCRIPT_NAMES = {"CJK": "Han", "KATAKANA-HIRAGANA": "Katakana"}
#: First words that name no script: letters written in several (ʿ and ʼ,
#: MODIFIER LETTER, in a Latin and in a Ukrainian Cyrillic spelling; the
#: ordinals ª and º; the iteration mark 々, in kanji and kana names
#: alike), which script() reads past rather than call a second script.
_NO_SCRIPT = frozenset({"MODIFIER", "FEMININE", "MASCULINE", "IDEOGRAPHIC"})
#: A first word that names a form, not a script: the script is the next
#: word (HALFWIDTH KATAKANA LETTER A, FULLWIDTH LATIN CAPITAL LETTER A).
_FORMS = frozenset({"HALFWIDTH", "FULLWIDTH"})
_ID = re.compile(r"[0-9]+")


def script(name: str) -> str:
    """The script `name`'s letters are written in, from the first word
    of each letter's Unicode name ("Latin", "Cyrillic", "Arabic", "Han"
    for CJK, "Katakana" counting the prolonged sound mark), "mixed" where
    its letters are in two or more, and "none" where it has no letter.
    Coarser than the parser's own script test, which names only the
    scripts it treats apart, and enough to key a pair of spellings by."""
    found = set()
    for char in name:
        if char.isalpha():
            words = unicodedata.name(char, "UNKNOWN").split()
            word = words[1] if words[0] in _FORMS and len(words) > 1 else words[0]
            if word not in _NO_SCRIPT:
                found.add(_SCRIPT_NAMES.get(word, word.title()))
    if not found:
        return "none"
    return found.pop() if len(found) == 1 else "mixed"


def _jrc_download(path: Path) -> None:
    """Download JRC_URL to `path`, through a file beside it that replaces
    `path` only once its sha256 is JRC_SHA256's: the JRC serves only its
    current file, so a refresh that overwrote the pinned one with a newer
    one would leave the corpus nothing to be rebuilt from. A download
    that is not the pinned file is left beside it, to be measured."""
    new = path.with_name(path.name + ".new")
    # A download kept by an earlier mismatch, once the pin has moved to it.
    if not (new.exists() and _sha256(new) == JRC_SHA256):
        _download(JRC_URL, new)
    held = _sha256(new)
    if held != JRC_SHA256:
        old = (f"the cached file at {path} is untouched" if path.exists()
               else "no file is cached")
        raise ValueError(f"{JRC_URL} served a file with sha256 {held}, not the "
                         f"pinned JRC_SHA256: it is kept at {new}, and {old}. "
                         f"Measure the new file and move JRC_SHA256 and JRC_DATE "
                         f"to read it")
    os.replace(new, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while block := file.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def _jrc_read(path: Path) -> Fetched:
    """The person spellings of the file at `path`, read as fetch_jrc
    says."""
    counts: Counter[str] = Counter()
    marked: Counter[str] = Counter()
    kept: set[tuple[int, str]] = set()
    last = b"\n"
    with gzip.open(path, "rb") as lines:
        for raw in lines:
            counts["lines"] += 1
            last = raw
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                counts["bad"] += 1
                continue
            cols = text.rstrip("\r\n").split("\t")
            if len(cols) != JRC_COLUMNS:
                counts["bad"] += 1
                continue
            entity, kind, language, written = cols
            name = " ".join(word for word in written.split("+") if word).strip()
            if (not _ID.fullmatch(entity) or kind not in (JRC_PERSON, JRC_ORGANISATION)
                    or not (language == JRC_UNMARKED or _LANGUAGE.fullmatch(language))
                    or not name):
                counts["bad"] += 1
                continue
            if kind == JRC_ORGANISATION:
                counts["organisations"] += 1
                continue
            counts["persons"] += 1
            if language != JRC_UNMARKED:
                marked[language] += 1
                continue
            if (int(entity), name) in kept:
                counts["repeated"] += 1
                continue
            kept.add((int(entity), name))
    if not last.endswith(b"\n"):
        raise ValueError(f"{path} ends inside a line: the file is cut short; "
                         f"download it again: {fetch_command(JRC, refresh=True)}")
    well_formed = counts["lines"] - counts["bad"]
    _refuse_past([(counts["bad"], counts["lines"], JRC_MAX_BAD,
                   f"lines of {path} are not {JRC_COLUMNS} well-formed columns")],
                 "the file's layout has changed")
    if counts["persons"] < well_formed * JRC_MIN_PERSONS or not counts["persons"]:
        raise ValueError(f"{counts['persons']:,} of {well_formed:,} lines of {path} "
                         f"name a person ({JRC_PERSON}): the file's types have changed")
    _refuse_past([(sum(marked.values()), counts["persons"], JRC_MAX_MARKED,
                   f"person rows of {path} carry a language")],
                 f"the file no longer marks a plain spelling {JRC_UNMARKED!r}")
    entities = Counter(entity for entity, _ in kept)
    records = [{"entity": str(entity), "name": name, "script": script(name)}
               for entity, name in sorted(kept)]
    detail: dict[str, int | str] = {
        "sha256": JRC_SHA256, "read_version": JRC_READ_VERSION, "lines": counts["lines"],
        "lines_read_past": counts["bad"], "organisation_rows": counts["organisations"],
        "person_rows": counts["persons"],
        "marked_variants_dropped": sum(marked.values()),
        "marked_variants_by_language": " ".join(
            f"{lang}:{n}" for lang, n in sorted(marked.items(), key=lambda kv: (-kv[1], kv[0]))),
        "repeated_spellings": counts["repeated"], "entities": len(entities),
        "entities_with_one_spelling": sum(n == 1 for n in entities.values()),
        "spellings_holding_a_replacement_character": sum(
            "�" in r["name"] for r in records)}
    return Fetched(records, JRC_DATE, detail)


def fetch_jrc() -> Fetched:
    """One record per distinct spelling of a person entity: its entity
    id, the name with its "+" read as spaces (runs of them as one) and
    its script(). Read from the gzip cached beside the corpus,
    downloaded when missing and again by `fetch --refresh` (a download
    that is not the pinned file replaces nothing, _jrc_download), and
    refused unless its sha256 is JRC_SHA256's.

    Organisation rows are counted and read past, as are person rows
    carrying a language (JRC_UNMARKED says why), by language, and a
    spelling an entity repeats. A line that is not JRC_COLUMNS
    well-formed columns or not UTF-8 is counted, and past JRC_MAX_BAD
    refuses the file; so do a gzip cut short or a file ending inside a
    line, fewer person rows than JRC_MIN_PERSONS, and more marked ones
    than JRC_MAX_MARKED."""
    path = directory(JRC) / JRC_FILE
    if not path.exists():
        _jrc_download(path)
    held = _sha256(path)
    if held != JRC_SHA256:
        raise ValueError(f"{path} has sha256 {held}, not the pinned JRC_SHA256: the "
                         f"cached file is damaged, or was read under another pin. "
                         f"Download it again: {fetch_command(JRC, refresh=True)}")
    try:
        return _jrc_read(path)
    except (EOFError, gzip.BadGzipFile, zlib.error) as exc:
        raise ValueError(f"{path} is not a whole gzip ({type(exc).__name__}: {exc}); "
                         f"download it again: {fetch_command(JRC, refresh=True)}") from None


def renew_jrc() -> None:
    """Download the current file over the cached one, where it is the
    pinned file (_jrc_download)."""
    _jrc_download(directory(JRC) / JRC_FILE)


_check_file = _pinned("sha256", lambda: JRC_SHA256,
                      "was read from the file with sha256 {held}, and this tool "
                      "reads {wanted}")
_check_read = _pinned("read_version", lambda: JRC_READ_VERSION,
                      "was read by read version {held}, and this tool reads "
                      "version {wanted}")


def check_jrc(meta: dict[str, Any]) -> str:
    """Why a corpus fetched under another pin, or read another way, is
    refused: its file's sha256, then its read version."""
    return _check_file(meta) or _check_read(meta)
