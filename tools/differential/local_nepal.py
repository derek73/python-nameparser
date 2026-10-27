"""The nepal-candidates local corpus: Nepal's 2079 BS local election.

nepal-candidates -- every candidate in Nepal's local elections of 2079
BS (2022), as the Election Commission publishes them on its results
site (result.election.gov.np): one file per local body (municipality or
rural municipality), each candidate's name written twice, in Devanagari
as filed and in the Commission's own romanization. It is the
repository's first large population of South Asian names: romanized
names with surnames written as initials (B.K., K.C., G.C.), honorific
words that are titles in front and names elsewhere (Guru; Shekh until
#752's phase 2j made it a title only in a title phrase), Md.,
Muhammad's abbreviation, which its period makes a title by shape, and
Devanagari written with vowel signs and the virama, combining marks the
letter-shape tests do not count as letters (decisions/nfd-shapes), and
with the joiners (ZWJ, ZWNJ). The site states no licence; only the two
name columns are kept.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from typing import Any

import local_core
from local_core import Fetched, _backed_off, _pinned, _refuse_past, _retried


NEPAL_SITE = "https://result.election.gov.np/"
NEPAL_HANDLER = NEPAL_SITE + "Handlers/SecureJson.ashx?file="
NEPAL_ELECTION = "Election2079"
NEPAL_LOOKUP = f"JSONFiles/{NEPAL_ELECTION}/Local/Lookup/localbodies.json"
NEPAL_BODY = f"JSONFiles/{NEPAL_ELECTION}/Local/{{id}}.json"
#: The User-Agent this source sends: a browser's form, naming the tool
#: in it as a crawler does. The site refuses (HTTP 403) a User-Agent
#: holding "python" or "curl" (2026-10-24), which the shared
#: local_core.USER_AGENT does in the repository's URL.
NEPAL_USER_AGENT = "Mozilla/5.0 (compatible; nameparser local_corpora)"
#: The seconds of sleep after each request: the 754 requests of a fetch
#: took 28 minutes at 0.3 s on 2026-10-24.
NEPAL_DELAY = 0.3
#: The local bodies the lookup listed on 2026-10-24. The election is
#: over and its files final, so a lookup listing another number is a
#: changed site, refused rather than read as a smaller election.
NEPAL_BODIES = 753
#: The candidates the 753 files held on 2026-10-24, pinned as the
#: bodies are: a fetch reading every file whole must read exactly this
#: many, so a site that trimmed its files (to the winners, or to one
#: post) is refused however well formed what is left.
NEPAL_CANDIDATES = 152_960
#: The share of the listed bodies whose file the site may answer as
#: missing (HTTP 404) or as empty (a list of no candidates) before the
#: fetch is refused: a site that blanked its files would otherwise read
#: as a smaller election. Every listed file held candidates on
#: 2026-10-24: the 18 a survey on 2026-10-23 saw refused, among them ids
#: 5551 to 5554, answered when asked again, so they were refused by a
#: lapsed token (403), not missing. A hundredth (7 bodies) lets a few
#: lost files cost their names rather than the fetch, and refuses a
#: site that has moved its files.
NEPAL_MAX_MISSING = 1 / 100
#: Where files are missing or empty, the share of NEPAL_CANDIDATES the
#: fetch may fall short by (3,059 candidates, 15 bodies of the average
#: 203): the pin cannot be exact without those files, so a site that
#: also trimmed a few candidates elsewhere is not seen then. Not sized
#: against the largest bodies, which were not measured: losing a few
#: of them refuses the fetch, and the detail's largest_file says how
#: large the largest file read was.
NEPAL_MAX_SHORT = 1 / 50
#: The record keys read; every other key is read past.
NEPAL_NAME, NEPAL_ROMANIZED = "CandidateName", "CandidateNameEng"
#: The share of candidates without the two name keys, without a
#: romanized name, or without a Devanagari one, past which the fetch is
#: refused, a value holding no letter counted as none (_named): a column
#: renamed or emptied wholesale would otherwise read as a smaller
#: election. On 2026-10-24, 0, 26 and 0 of 152,960.
NEPAL_MAX_NAMELESS = 1 / 100
#: The share of the candidates kept (those with a romanized name) past
#: which a column holding the wrong script refuses the fetch: a
#: Devanagari name with no Devanagari letter, or a romanized one with a
#: letter outside Latin, is what two columns swapped, or a romanization
#: dropped, would show. 0 and 3 of the 152,934 kept on 2026-10-24 (a
#: romanization left partly in Devanagari).
NEPAL_MAX_WRONG_SCRIPT = 1 / 100
#: The distinct romanized names, and the distinct Devanagari ones, must
#: each be at least this share of the candidates kept: a column masked
#: with one word would otherwise pass, its pairs kept distinct by the
#: other column. 118,126 and 119,282 of 152,934 (77% and 78%) on
#: 2026-10-24.
NEPAL_MIN_DISTINCT = 1 / 4


def _cookies(headers: list[str]) -> dict[str, str]:
    """The cookies `headers` (Set-Cookie values) set, by name, each value
    as sent: a header is cut at its first semicolon, where its
    attributes start, and at its first equals sign. One that holds no
    name raises, rather than leaving a cookie out of every request."""
    cookies: dict[str, str] = {}
    for header in headers:
        name, sep, value = header.split(";", 1)[0].partition("=")
        if not sep or not name.strip():
            raise ValueError(f"{NEPAL_SITE} set a cookie with no name: the "
                             f"site's check has changed")
        cookies[name.strip()] = value.strip()
    return cookies


def _session() -> dict[str, str]:
    """The headers every handler request carries: the site's own
    double-submit check, the CsrfToken cookie a GET of the site sets
    echoed in X-CSRF-Token, beside every cookie it sets, with the
    Referer its pages send. Retried under local_core's policy."""
    request = urllib.request.Request(NEPAL_SITE, headers={"User-Agent": NEPAL_USER_AGENT})
    for attempt in range(local_core.RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                response.read()
                cookies = _cookies(response.headers.get_all("Set-Cookie") or [])
            break
        except local_core._TRANSIENT as exc:
            if not _backed_off(exc, attempt, NEPAL_SITE):
                raise
    else:
        raise AssertionError("unreachable: the last attempt raises")
    if not cookies.get("CsrfToken"):
        raise ValueError(f"{NEPAL_SITE} set no CsrfToken cookie: the site's "
                         f"check has changed")
    return {"User-Agent": NEPAL_USER_AGENT, "Referer": NEPAL_SITE,
            "X-CSRF-Token": cookies["CsrfToken"],
            "Cookie": "; ".join(f"{k}={v}" for k, v in sorted(cookies.items()))}


def _json(body: bytes, path: str) -> object:
    """`body` parsed as UTF-8, with or without a byte-order mark (a
    survey on 2026-10-23 saw one, the fetch on 2026-10-24 none). A body
    cut short is no JSON, and raises."""
    try:
        return json.loads(body.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"{path} is not UTF-8 JSON ({exc})") from None


def _get(path: str, headers: dict[str, str], counts: Counter[str]) -> object:
    """`path`'s JSON, retried under local_core's policy. A 403, what the
    site answers a token it no longer holds, renews the session in
    `headers`, counted, and asks once more (a fetch can outlast
    ASP.NET's default twenty-minute session, which the token seems bound
    to); a second 403 is raised."""
    url = NEPAL_HANDLER + path
    try:
        return _retried(url, lambda body: _json(body, path), NEPAL_DELAY, headers=headers)
    except urllib.error.HTTPError as exc:
        if exc.code != 403:
            raise
        exc.close()
    print(f"  renewing the session after a 403: {url}", file=sys.stderr)
    counts["sessions_renewed"] += 1
    headers.update(_session())
    return _retried(url, lambda body: _json(body, path), NEPAL_DELAY, headers=headers)


def _bodies(headers: dict[str, str], counts: Counter[str]) -> list[int]:
    """The ids of the local bodies the lookup lists; a list that is not
    NEPAL_BODIES distinct int ids is refused."""
    listed = _get(NEPAL_LOOKUP, headers, counts)
    if not isinstance(listed, list) or any(
            not isinstance(b, dict) or type(b.get("id")) is not int for b in listed):
        raise ValueError(f"{NEPAL_LOOKUP} is not a list of local bodies with ids")
    ids = sorted({b["id"] for b in listed})
    if len(ids) != len(listed) or len(ids) != NEPAL_BODIES:
        raise ValueError(f"{NEPAL_LOOKUP} lists {len(listed):,} local bodies "
                         f"({len(ids):,} distinct ids), not the {NEPAL_BODIES:,} "
                         f"of NEPAL_BODIES: the site has changed")
    return ids


def _candidates(body: int, headers: dict[str, str],
                counts: Counter[str]) -> list[dict[str, Any]] | None:
    """`body`'s candidates, or None where the site answers its file as
    missing (HTTP 404)."""
    path = NEPAL_BODY.format(id=body)
    try:
        rows = _get(path, headers, counts)
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        exc.close()
        return None
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        raise ValueError(f"{path} is not a list of candidates")
    return rows


def _devanagari(text: str) -> bool:
    return any("\u0900" <= char <= "\u097f" and char.isalpha() for char in text)


#: The letters a romanization may write beside ASCII's: Latin-1 and
#: Latin Extended-A and B, the modifier letters (an apostrophe written
#: as a letter), and Latin Extended Additional, where IAST's dotted
#: letters stand.
_LATIN = (("\u00c0", "\u024f"), ("\u02b0", "\u02ff"), ("\u1e00", "\u1eff"))


def _latin(text: str) -> bool:
    """Whether every letter of `text` is ASCII or in one of _LATIN's ranges."""
    return all(char.isascii() or any(low <= char <= high for low, high in _LATIN)
               for char in text if char.isalpha())


def _named(value: object) -> str:
    """`value` stripped, or "" where it is no text or holds no letter: the
    Commission wrote a placeholder of dashes or bars (`- - -`) for the
    romanization of 26 of 152,960 candidates fetched 2026-10-24, each
    beside a Devanagari name."""
    text = value.strip() if isinstance(value, str) else ""
    return text if any(char.isalpha() for char in text) else ""


def _read(rows: list[dict[str, Any]], pairs: set[tuple[str, str]],
          counts: Counter[str]) -> None:
    """Add one body's (romanized, Devanagari) pairs to `pairs`. A
    candidate without the name keys or a romanized name is counted and
    read past; of those kept, one without a Devanagari name is kept with
    an empty one, and one with a name in the wrong script is kept, each
    counted."""
    for row in rows:
        counts["candidates"] += 1
        if NEPAL_NAME not in row or NEPAL_ROMANIZED not in row:
            counts["without_the_name_keys"] += 1
            continue
        name, romanized = _named(row[NEPAL_NAME]), _named(row[NEPAL_ROMANIZED])
        if not romanized:
            counts["without_a_romanized_name"] += 1
            continue
        if not name:
            counts["without_a_devanagari_name"] += 1
        elif not _devanagari(name):
            counts["devanagari_name_without_devanagari"] += 1
        if not _latin(romanized):
            counts["romanized_name_not_latin"] += 1
        counts["with_a_romanized_name"] += 1
        pairs.add((romanized, name))


def _refuse_a_short_election(candidates: int, absent: int) -> None:
    """Refuse a fetch reading other than NEPAL_CANDIDATES with every file
    read (`absent` 0); with `absent` files missing or empty, one reading
    more than NEPAL_CANDIDATES less one a file (every file held a
    candidate), or short by more than NEPAL_MAX_SHORT."""
    if candidates > NEPAL_CANDIDATES - absent or not absent and candidates != NEPAL_CANDIDATES:
        raise ValueError(f"the files read hold {candidates:,} candidates, "
                         f"{absent:,} missing or empty, against the "
                         f"{NEPAL_CANDIDATES:,} of NEPAL_CANDIDATES: the site's "
                         f"files have changed")
    _refuse_past([(NEPAL_CANDIDATES - candidates, NEPAL_CANDIDATES, NEPAL_MAX_SHORT,
                   "NEPAL_CANDIDATES are missing")],
                 "more than a few missing or empty files account for, unless "
                 "they were among the largest")


def fetch_nepal() -> Fetched:
    """Every candidate of every local body the lookup lists, one record
    per distinct pair of the romanized name and the Devanagari one.

    The record's "name", the one parse() reads, is the romanized name
    (CandidateNameEng), since romanized South Asian names are where the
    parser misreads: surnames written as initials read as credentials
    where the name has a word to spare (B.K., K.C.; #864), and a leading
    Md. read as a title by its period.
    The Devanagari name (CandidateName) is kept beside it as
    "devanagari", and the corpus holds both (Source.corpus_keys), so a
    snapshot watches the script too. A candidate with no romanized name
    is dropped; one with no Devanagari name is kept, its "devanagari"
    empty. A record is a distinct pair, as tse-donors' are, not a
    candidate row: a body lists a candidate once per post, and a common
    name recurs across bodies, so a row count would weight a name by how
    often it stood; a person with two romanizations is two records.
    Gender, age, ward and post are read past, since no view reads them.

    A file the site answers as missing (HTTP 404) is counted, its id
    kept in the detail as an empty file's is, and with the empty files
    past NEPAL_MAX_MISSING of the bodies refuses the fetch. A 403 renews
    the session once (_get); a 5xx, a 429 or a dropped connection is
    retried and then raised, and any other 4xx is raised at once. A file
    is JSON, so one cut short does not parse, and is retried and then
    refused rather than read as fewer candidates. A lookup not listing
    NEPAL_BODIES bodies, a candidate count other than NEPAL_CANDIDATES
    (or short of it by more than NEPAL_MAX_SHORT where files are
    missing or empty), too many candidates without the name keys, a
    romanized name or a Devanagari one (NEPAL_MAX_NAMELESS) or with a
    name in the wrong script (NEPAL_MAX_WRONG_SCRIPT), and too few
    distinct names in either column (NEPAL_MIN_DISTINCT) refuse it too.
    The site states no date for the data, so the data date is the
    fetch's own, in UTC."""
    when = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    counts: Counter[str] = Counter()
    headers = _session()
    ids = _bodies(headers, counts)
    pairs: set[tuple[str, str]] = set()
    missing: list[int] = []
    empty: list[int] = []
    for number, body in enumerate(ids, 1):
        if number % 50 == 0:
            print(f"  {number:,} of {len(ids):,} local bodies", file=sys.stderr)
        rows = _candidates(body, headers, counts)
        if rows is None:
            missing.append(body)
            continue
        counts["files"] += 1
        if not rows:
            empty.append(body)
        counts["largest_file"] = max(counts["largest_file"], len(rows))
        _read(rows, pairs, counts)
    candidates = counts["candidates"]
    _refuse_past([(len(missing) + len(empty), len(ids), NEPAL_MAX_MISSING,
                   "local bodies' files are missing (HTTP 404) or empty")],
                 "the site has moved, dropped or emptied its files")
    _refuse_a_short_election(candidates, len(missing) + len(empty))
    _refuse_past([(counts["without_the_name_keys"], candidates, NEPAL_MAX_NAMELESS,
                   f"candidates have no {NEPAL_NAME} or {NEPAL_ROMANIZED} key"),
                  (counts["without_a_romanized_name"], candidates, NEPAL_MAX_NAMELESS,
                   "candidates have no romanized name"),
                  (counts["without_a_devanagari_name"], candidates, NEPAL_MAX_NAMELESS,
                   "candidates have no Devanagari name")],
                 "a name column may be renamed or emptied")
    kept = counts["with_a_romanized_name"]
    _refuse_past([(counts["devanagari_name_without_devanagari"], kept,
                   NEPAL_MAX_WRONG_SCRIPT, f"{NEPAL_NAME} values hold no Devanagari"),
                  (counts["romanized_name_not_latin"], kept, NEPAL_MAX_WRONG_SCRIPT,
                   f"{NEPAL_ROMANIZED} values are not Latin")],
                 "the two name columns may be swapped or replaced")
    if not pairs:
        raise ValueError("the local bodies' files hold no candidate with a name")
    for column, index in ((NEPAL_ROMANIZED, 0), (NEPAL_NAME, 1)):
        seen = len({pair[index] for pair in pairs})
        if seen < kept * NEPAL_MIN_DISTINCT:
            raise ValueError(f"{kept:,} candidates hold {seen:,} distinct "
                             f"{column}: the column may be masked")
    detail: dict[str, Any] = {
        "election": NEPAL_ELECTION, "local_bodies": len(ids),
        "local_bodies_missing": " ".join(map(str, missing)),
        "local_bodies_empty": " ".join(map(str, empty)),
        **{key: counts[key] for key in (
            "files", "candidates", "without_the_name_keys",
            "without_a_romanized_name", "without_a_devanagari_name",
            "devanagari_name_without_devanagari", "romanized_name_not_latin",
            "sessions_renewed", "largest_file")}}
    return Fetched([{"name": romanized, "devanagari": name}
                    for romanized, name in sorted(pairs)], when, detail)


check_nepal = _pinned("election", lambda: NEPAL_ELECTION,
                      "holds the election {held}, and this tool reads {wanted}")
