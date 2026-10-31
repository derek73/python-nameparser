"""The dof-signatures local corpus: the signatures in Mexico's Diario
Oficial de la Federación.

dof-signatures -- one record per signature in the notes the DOF published
from DOF_FROM to DOF_TO, each the name cut from the clause that precedes
its "Rúbrica" (the printed mark of a signed original), with the clause
kept beside it. The signatories are officials, judges' clerks and the
parties to agreements, and they sign as the DOF prints them: in spoken
order, mixed case, mostly with the courtesy or academic title they use
(`Lic.`, `Mtra.`, `C.`, `Dr.`, `Ing.`, `Licenciada`), after an office
that a comma usually, but not always, sets off. So it is the population
for Spanish titles as written, and for a title that marks where a name
starts after an office. Unscored: no box says which words are the name,
so the name is a cut, and the cut is a rule this module states (cut())
and records on every row, which a reader can filter by.

Fetched through SIDOF, the DOF's own site, from the JSON web services
its open-data page offers (sidof.segob.gob.mx/datos_abiertos): a day's
listing (`/dof/sidof/notas/<DD-MM-YYYY>`), then each note's HTML
(`/dof/sidof/notas/nota/<codNota>`), sequentially, DOF_DELAY seconds
apart, skipping the notes robots.txt disallows. Each day's excerpts --
the blocks around each "Rúbrica", with which characters the DOF set in
bold -- are cached beside the corpus under days/, written once the
day's every note has been read, so a fetch cut short resumes at the
first day it has not cached and the cut can be read again without
fetching anything (three days sampled on 2026-10-30 ran to 3, 12 and
18 MB of HTML, where a day's excerpts are under 10 KB gzipped).

Terms: the Ley Federal del Derecho de Autor, art. 14 fr. VIII, puts
"Los textos legislativos, reglamentarios, administrativos o judiciales"
outside copyright, and SIDOF's Aviso Legal (sidof.segob.gob.mx/avisoLegal,
read 2026-10-30) permits reproducing its content without profit as long
as the source is cited, which the credit line does. The signatories are
named public officials, but they are real people, so the corpus stays in
the cache, like every local corpus.
"""
from __future__ import annotations

import datetime
import gzip
import html.parser
import json
import re
import sys
import zlib
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import corpus_build
from local_core import (Fetched, _pinned, _refuse_past, _retried, directory,
                        fetch_command)


DOF = "dof-signatures"
SIDOF = "https://sidof.segob.gob.mx"
DOF_DAY_URL = SIDOF + "/dof/sidof/notas/{day}"
DOF_NOTE_URL = SIDOF + "/dof/sidof/notas/nota/{cod}"
DOF_ROBOTS_URL = SIDOF + "/robots.txt"
#: The days read, both included: the whole of 2025, the last full year
#: on 2026-10-30.
DOF_FROM = datetime.date(2025, 1, 1)
DOF_TO = datetime.date(2025, 12, 31)
#: Seconds slept after each request.
DOF_DELAY = 0.25
#: The day listing's three editions.
DOF_EDITIONS = ("NotasMatutinas", "NotasVespertinas", "NotasExtraordinarias")
#: How a note's HTML is read into excerpts (EXCERPT_BLOCKS, the block
#: tags, what counts as bold), stored in each day file and in meta.json:
#: a change to excerpts() must bump it, and a day cached under another
#: is fetched again.
DOF_EXCERPT_VERSION = 1
#: How excerpts are cut into records (cut(), signatures()), in
#: meta.json's detail: a change must bump it, and a corpus cut the old
#: way is refused on load (check_dof). No refetch is needed: the cut is
#: read from the cached days.
DOF_CUT_VERSION = 5
#: The blocks kept before each block holding a "Rúbrica": the stacked
#: signature's office lines and name, or a date line before them.
EXCERPT_BLOCKS = 3
#: Gates, each a share past which the fetch is refused: notes listed with
#: HTML that state a size and come back without it (22 of 23,816 in
#: 2025); notes listed with HTML that state a size of 0, published as page
#: images (2,936 of 26,752, 11.0%), gated in case an ordinary note comes
#: to state 0; weekdays listing no note at all (7 of 261, each a public
#: holiday); and "Rúbrica"s no rule could cut (1,741 of 35,305 under cut
#: version 5). Measured 2026-10-31.
DOF_MAX_EMPTY = 0.05
DOF_MAX_IMAGE_ONLY = 0.20
DOF_MAX_SILENT = 0.05
DOF_MAX_UNCUT = 0.10

_DAYS = "days"


# -- reading a note's HTML ---------------------------------------------------

_BLOCK_TAGS = frozenset({"div", "p", "td", "th", "tr", "br", "li", "table",
                         "h1", "h2", "h3", "h4", "h5", "h6"})
_SKIPPED_TAGS = frozenset({"style", "script", "title", "head"})
_VOID_TAGS = frozenset({"br", "img", "hr", "meta", "link", "input", "col"})
_BOLD_STYLE = re.compile(r"font-weight:\s*(?:bold|[6-9]00)", re.I)


class _Blocks(html.parser.HTMLParser):
    """A note's text, cut into blocks at the block tags, each character
    marked with whether an element around it is bold: a <b> or <strong>,
    or a bold font-weight. The DOF sets a signatory's name in bold,
    which is what cut() reads first."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[list[tuple[str, bool]]] = [[]]
        self._open: list[tuple[str, bool]] = []
        self._skipping = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIPPED_TAGS:
            self._skipping += 1
            return
        if tag in _BLOCK_TAGS:
            self.blocks.append([])
        if tag in _VOID_TAGS:
            return
        style = next((v or "" for k, v in attrs if k == "style"), "")
        self._open.append((tag, tag in ("b", "strong") or bool(_BOLD_STYLE.search(style))))

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIPPED_TAGS:
            self._skipping = max(0, self._skipping - 1)
            return
        for at in range(len(self._open) - 1, -1, -1):
            if self._open[at][0] == tag:
                del self._open[at:]
                break
        if tag in _BLOCK_TAGS:
            self.blocks.append([])

    def handle_data(self, data: str) -> None:
        if not self._skipping:
            self.blocks[-1].append((data, any(bold for _, bold in self._open)))


def _block(runs: list[tuple[str, bool]]) -> tuple[str, str]:
    """A block's runs as its text, whitespace read as single spaces and
    trimmed, and a mask of the same length, "1" under a bold character."""
    text: list[str] = []
    mask: list[str] = []
    for data, bold in runs:
        for char in data:
            if char.isspace():
                if text and text[-1] != " ":
                    text.append(" ")
                    mask.append("0")
            else:
                text.append(char)
                mask.append("1" if bold else "0")
    while text and text[-1] == " ":
        text.pop()
        mask.pop()
    return "".join(text), "".join(mask)


RUBRICA = re.compile(r"r[úu]brica", re.I)


def excerpts(content: str) -> list[list[tuple[str, str]]]:
    """The excerpts of a note's HTML that cut() reads: for each block
    holding a "Rúbrica", that block with the EXCERPT_BLOCKS before it,
    each a (text, bold mask) pair. Runs of such blocks share one
    excerpt, so a signature's blocks are never split between two."""
    parser = _Blocks()
    parser.feed(content)
    parser.close()
    blocks = [b for b in (_block(runs) for runs in parser.blocks) if b[0]]
    found: list[list[tuple[str, str]]] = []
    start = -1
    for at, (text, _) in enumerate(blocks):
        if not RUBRICA.search(text):
            continue
        if found and at - EXCERPT_BLOCKS <= start + 1:
            found[-1].extend(blocks[start + 1:at + 1])
        else:
            found.append(blocks[max(0, at - EXCERPT_BLOCKS):at + 1])
        start = at
    return found


# -- cutting a name ----------------------------------------------------------

#: The spelled-out titles a name may open with, as the DOF writes them,
#: matched case-insensitively. An abbreviated title in capitals is told by
#: its shape (_CAPITALS), one in mixed case by this list (_ABBREVIATED).
SPELLED_TITLES = frozenset({
    "licenciado", "licenciada", "maestro", "maestra", "doctor", "doctora",
    "ingeniero", "ingeniera", "arquitecto", "arquitecta", "contador",
    "contadora", "ciudadano", "ciudadana", "profesor", "profesora",
    "actuario", "actuaria", "notario", "notaria"})
#: An abbreviated title in capitals: one or more chunks of up to five
#: capitals, each ending in a full stop (`LIC.`, `C.`, `C.P.`, `L.C.P.`,
#: `MVZ.`), the degrees too many to list. It is a shape, so a lone
#: initial passes (`J. Guadalupe`, José's), as does a short surname in
#: capitals ending a sentence.
_CAPITALS = re.compile(r"(?:[A-ZÁÉÍÓÚÑ]{1,5}\.)+")
#: The abbreviated titles in mixed case, without the full stop they are
#: written with: the courtesy and academic titles and the ranks the DOF's
#: 2025 signatures open with. A list, not a shape, since a capital and a
#: few letters with a full stop is also a given name written short (`Ma.`,
#: `Gpe.`) and a short surname ending a sentence (`Ruiz Paz. Conste`).
_ABBREVIATED = frozenset({
    "lic", "licda", "licdo", "lcda", "lcdo", "mtro", "mtra", "mtr", "dr", "dra",
    "ing", "arq", "prof", "profr", "profa", "act", "abog", "biól", "biol", "geóg",
    "psic", "med", "esp", "adm", "urb", "sen", "dip", "mag", "gral", "div", "brig",
    "bgda", "big", "cor", "tte", "sbtte", "cap", "alm", "almte", "nav", "cab", "pil",
    "cmdte", "magap", "ret"})  # `ret`: retirado, inside a rank (`Alm. Ret.`)
#: An article before a title or a name (`la Lic. ...`, `el C. ...`),
#: left out of the cut.
_ARTICLES = frozenset({"el", "la", "los", "las"})
# What a cut is refused as, though a rule cut it: a date (`a siete de
# noviembre de dos mil veinticinco`, `30 DE MAYO DE 2025`), and an office
# signing without a name (`EL
# SECRETARIO DE SALUD`), which opens with an article where a name does
# not (_office() has the rest). A bare digit or month is not enough: `CAP. 1/O. AYTE.` is a rank
# and `Julio` a given name; `Del Olmo` is a surname, so `del` is not an
# article here.
_MONTHS = ("enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre"
           "|octubre|noviembre|diciembre")
#: The head words of the offices that sign without a name, read only in
#: a cut wholly in capitals (`DIRECTORA GENERAL DE RECURSOS HUMANOS`, `C.
#: GOBERNADOR CONSTITUCIONAL DEL ESTADO`): in mixed case they open a name
#: as an office written as a title (`Magistrado José ...`, `Jueza de
#: Distrito Ana ...`), which is kept.
_OFFICE_HEADS = frozenset({
    "director", "directora", "subdirector", "subdirectora", "gobernador", "gobernadora",
    "secretario", "secretaria", "subsecretario", "subsecretaria", "presidente",
    "presidenta", "titular", "jefe", "jefa", "coordinador", "coordinadora", "delegado",
    "delegada", "encargado", "encargada", "procurador", "procuradora", "fiscal",
    "comisionado", "comisionada", "consejero", "consejera", "diputado", "diputada",
    "senador", "senadora", "tesorero", "tesorera", "oficial", "administrador",
    "administradora", "gerente", "representante", "apoderado", "apoderada"})
_DATE = re.compile(rf"\bde (?:{_MONTHS})\b|\bdos mil\b|\b\d{{4}}\b", re.I)
#: The end of the sentence before a signature: `.-` or `.–`.
_CLAUSE_START = re.compile(r"\.\s*[-–—]\s*")
#: What ends the text before a "Rúbrica" in a signature: a dash, or a
#: full stop, with the spaces around it.
_BEFORE_RUBRICA = re.compile(r"(?:\.\s*)?[-–—]?\s*$")
_EDGE = " ,;:.-–—\"'()"
#: The most words a title rule's cut may hold: the longest name among the
#: 800 cuts checked by hand on 2026-10-31 (200 drawn at random under each
#: of cut versions 1, 2, 3 and 5) ran to 7 (`CAP. 1/O. AYTE. CONTAB. DANIEL LARA
#: HERNANDEZ`).
_TITLE_WORDS = 8


def _office(name: str) -> bool:
    """Whether a cut is an office signing without a name: one opening
    with an article (`EL SECRETARIO DE SALUD`), or, in capitals, with an
    office's head word after any titles or with `DE`/`DEL` (`DEL ESTADO`;
    in mixed case `Del Olmo` is a surname)."""
    words = name.split()
    if words[0].lower() in _ARTICLES:
        return True
    if not name.isupper():
        return False
    rest = [w for w in words if not is_title(w)] or words
    return rest[0].lower() in _OFFICE_HEADS or words[0] in ("DE", "DEL")


def is_title(word: str) -> bool:
    """Whether `word` is a title a name may open with, by cut()'s test."""
    return (bool(_CAPITALS.fullmatch(word))
            or (word.endswith(".") and word[:-1].lower() in _ABBREVIATED)
            or word.lower().strip(".") in SPELLED_TITLES)


def _words(text: str, mask: str) -> list[tuple[int, int, bool]]:
    """`text`'s words as (start, end, bold): bold when any letter in
    the word is."""
    out = []
    for match in re.finditer(r"\S+", text):
        bold = any(mask[i] == "1" and text[i].isalpha()
                   for i in range(match.start(), match.end()))
        out.append((match.start(), match.end(), bold))
    return out


def _with_titles(text: str, words: list[tuple[int, int, bool]], first: int) -> int:
    """The index of the first word of the run of titles directly before
    word `first`, or `first` when none is."""
    while first > 0 and is_title(text[words[first - 1][0]:words[first - 1][1]]):
        first -= 1
    return first


def _span(text: str, words: list[tuple[int, int, bool]], first: int, last: int) -> str:
    return text[words[first][0]:words[last][1]].strip(_EDGE + " ").rstrip(_EDGE)


def cut(text: str, mask: str) -> tuple[str, str] | None:
    """The name in a signature's clause and the rule that cut it, or
    None when no rule finds one. The rules, in order:

    - "bold": the last run of words with a bold letter, starting after
      the last bold word that ends in a comma, semicolon or colon, so
      that of a run in bold throughout the part after it is kept (`GRAL.
      BRIG. E.M., Ana Ruiz Paz` keeps `Ana Ruiz Paz`; in 2025 the part
      after the comma was the name in about 78 of the 90 signatures
      holding one, measured 2026-10-31 on cut version 4, the rest an
      office after the name, which _office() mostly refuses), with any
      titles directly before it (`Lic.`, which the DOF mostly leaves in
      roman);
    - "title": no bold, so the run from the last title (is_title) with
      a word behind it, to the first comma after it (`Sen. Ana Ruiz,
      Secretaria` keeps `Sen. Ana Ruiz`), and no longer than
      _TITLE_WORDS words, past which it is a sentence a title opened.

    Nothing else cuts: a clause with neither is mostly an office, a
    motto or a sentence, and in 2025 what follows its last comma was a
    name in 2 of 46 distinct cuts, the whole clause in about 5 of 60
    (measured 2026-10-31, cut version 1).
    """
    words = _words(text, mask)
    if not words:
        return None
    bold = [at for at, (_, _, b) in enumerate(words) if b]
    if bold:
        last = bold[-1]
        first = last
        while (first > 0 and words[first - 1][2]
               and not text[words[first - 1][0]:words[first - 1][1]].endswith((",", ";", ":"))):
            first -= 1
        name = _span(text, words, _with_titles(text, words, first), last)
        return (name, "bold") if name else None
    titles = [at for at in range(len(words) - 1)
              if is_title(text[words[at][0]:words[at][1]])]
    if not titles:
        return None
    first = _with_titles(text, words, titles[-1])
    last = next((at for at in range(titles[-1] + 1, len(words))
                 if text[words[at][0]:words[at][1]].endswith(",")), len(words) - 1)
    if last - first + 1 > _TITLE_WORDS:
        return None
    name = _span(text, words, first, last)
    return (name, "title") if name else None


def joined(before: str) -> str:
    """How a cut name meets the clause before it: "start" (nothing), "comma",
    "colon", "article" (`la`, `el`), "block" (a stacked signature, the
    office in the block above), or "word": glued to a word with no
    punctuation between, the shape a title marks the start of a name in.
    `before` is the clause's text before the cut, blocks joined by " | "."""
    rest = before.rstrip()
    if not rest:
        return "start"
    if rest.endswith("|"):
        return "block"
    if rest.endswith(","):
        return "comma"
    if rest.endswith((":", ";")):
        return "colon"
    if rest.split()[-1].lower() in _ARTICLES:
        return "article"
    return "word"


def signatures(excerpt: list[tuple[str, str]]) -> Iterator[dict[str, str] | str]:
    """Each signature in an excerpt, as a record without its source: the
    name cut, the rule, the title the name opens with ("" for none), how
    it meets the clause (joined()), the layout and the raw clause; or,
    for a "Rúbrica" that cut() found no name before, or whose cut is one
    word, a date or an office (_DATE, _ARTICLES), the reason, as a string, which
    the fetch counts.

    Two layouts. "stacked": a block that is the "Rúbrica" alone, the
    name the block above it and the office the blocks above that, which
    the clause holds joined by " | ". "inline": `Office, Title Name.-
    Rúbrica.-` in a paragraph, the clause running from the last `.-`
    before the name, so it may hold the end of an attestation (`Doy
    fe`, `Atentamente`)."""
    for at, (text, mask) in enumerate(excerpt):
        for match in RUBRICA.finditer(text):
            before = text[:match.start()]
            if not before.strip(_EDGE + " *|"):
                if at == 0 or RUBRICA.search(excerpt[at - 1][0]):
                    yield "stacked, no block above"
                    continue
                name_text, name_mask = excerpt[at - 1]
                above = [t for t, _ in excerpt[max(0, at - 1 - (EXCERPT_BLOCKS - 1)):at - 1]
                         if not RUBRICA.search(t)]
                layout = "stacked"
                prefix = "".join(f"{t} | " for t in above)
            else:
                end = _BEFORE_RUBRICA.search(before)
                body = before[:end.start()] if end else before
                if not body.strip() or body.rstrip()[-1:] in ",;:":
                    yield "inline, nothing before"
                    continue
                starts = list(_CLAUSE_START.finditer(body))
                begin = starts[-1].end() if starts else 0
                name_text, name_mask = body[begin:], mask[begin:len(body)]
                layout, prefix = "inline", ""
            found = cut(name_text, name_mask)
            if found is None:
                yield f"{layout}, no rule cut a name"
                continue
            name, rule = found
            if len(name.split()) == 1:  # `f`, `III`, `Atentamente`, a surname cut off
                yield f"{layout}, cut one word"
                continue
            if _DATE.search(name):
                yield f"{layout}, cut a date"
                continue
            if _office(name):
                yield f"{layout}, cut an office"
                continue
            clause = prefix + name_text
            where = clause.rfind(name)
            first = name.split()[0]
            yield {"name": name, "cut": rule, "layout": layout,
                   "title": first if is_title(first) else "",
                   "joined": joined(clause[:where] if where >= 0 else clause),
                   "clause": clause}


# -- fetching ----------------------------------------------------------------

def _days() -> Iterator[datetime.date]:
    day = DOF_FROM
    while day <= DOF_TO:
        yield day
        day += datetime.timedelta(days=1)


def _day_path(day: datetime.date) -> Path:
    return directory(DOF) / _DAYS / f"{day.isoformat()}.json.gz"


def _get(url: str) -> dict[str, Any]:
    """`url`'s JSON object, required to answer messageCode 200; another
    answer is retried like a body cut short, and refused once the retries
    run out."""
    def read(body: bytes) -> dict[str, Any]:
        data = corpus_build.parse_json(body, url)
        if not isinstance(data, dict) or data.get("messageCode") != 200:
            code = data.get("messageCode") if isinstance(data, dict) else type(data).__name__
            raise ValueError(f"answered {code}, not messageCode 200")
        return data
    return _retried(url, read, DOF_DELAY, timeout=120)


def disallowed(robots: str) -> frozenset[int]:
    """The notes robots.txt disallows for every agent: its
    `Disallow: /notas/<codNota>` lines under `User-agent: *`."""
    found: set[int] = set()
    every = False
    for line in robots.splitlines():
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "user-agent":
            every = value == "*"
        elif every and key == "disallow":
            if match := re.fullmatch(r"/notas/(?:docFuente/)?(\d+)", value):
                found.add(int(match.group(1)))
    return frozenset(found)


def _fetch_day(day: datetime.date, skip: frozenset[int]) -> dict[str, Any]:
    """A day's listing and every listed note with HTML, read into
    excerpts; the counts read past are kept with them."""
    url = DOF_DAY_URL.format(day=day.strftime("%d-%m-%Y"))
    listing = _get(url)
    lacking = [e for e in DOF_EDITIONS if not isinstance(listing.get(e), list)]
    if lacking:
        # Every 2025 listing holds all three, a list each, an empty one
        # on a day without that edition; a day read from a listing
        # without one would be cached short for good.
        raise ValueError(f"{url} lists no {', '.join(lacking)}: the listing's "
                         f"layout may have changed under the reader")
    notes: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for edition in DOF_EDITIONS:
        for entry in listing[edition]:
            cod = int(entry["codNota"])
            if entry.get("existeHtml") != "S":
                counts["without html"] += 1
                continue
            if cod in skip:
                counts["disallowed"] += 1
                continue
            note = _get(DOF_NOTE_URL.format(cod=cod))["Nota"]
            content = note.get("cadenaContenido") or ""
            if not content:
                # A note published as page images only is listed with
                # HTML and states its size as 0 (2,936 of the 26,752
                # 2025 listed with HTML, spread over every month); a
                # blank note of stated size (22) is what the gate is for.
                image_only = str(note.get("tamanioContenido")) == "0"
                counts["image only" if image_only else "empty"] += 1
                continue
            counts["read"] += 1
            notes.append({"note": cod, "edition": edition,
                          "excerpts": excerpts(content)})
    return {"day": day.isoformat(), "excerpt_version": DOF_EXCERPT_VERSION,
            "counts": dict(counts), "notes": notes}


def _read_day(path: Path) -> dict[str, Any] | None:
    """A cached day, or None where none is cached or it was read under
    another DOF_EXCERPT_VERSION. A file that is not a whole gzip of one
    JSON object raises, naming the way out."""
    if not path.exists():
        return None
    try:
        day = json.loads(gzip.decompress(path.read_bytes()))
    except (EOFError, gzip.BadGzipFile, zlib.error, ValueError) as exc:
        raise ValueError(f"{path} is damaged ({type(exc).__name__}: {exc}); delete "
                         f"it and fetch again: {fetch_command(DOF)}") from None
    if not isinstance(day, dict) or day.get("excerpt_version") != DOF_EXCERPT_VERSION:
        return None
    return day


def _cache_days(*, again: bool = False) -> list[dict[str, Any]]:
    """Every day of DOF_FROM..DOF_TO, from the cache where it holds the
    day (unless `again`), else fetched and cached."""
    skip: frozenset[int] | None = None  # robots.txt, read once a day needs fetching
    (directory(DOF) / _DAYS).mkdir(exist_ok=True)
    out = []
    for number, day in enumerate(_days(), 1):
        path = _day_path(day)
        held = None if again else _read_day(path)
        if held is None:
            if skip is None:
                skip = disallowed(_retried(DOF_ROBOTS_URL, lambda b: b.decode("utf-8"),
                                           DOF_DELAY))
            held = _fetch_day(day, skip)
            body = (corpus_build.jsonl_line(held, sort_keys=True) + "\n").encode()
            corpus_build.write_atomic(path, gzip.compress(body, mtime=0))
            print(f"  {day.isoformat()}: {held['counts'].get('read', 0)} notes "
                  f"({number} of {(DOF_TO - DOF_FROM).days + 1} days)", file=sys.stderr)
        out.append(held)
    return out


def fetch_dof() -> Fetched:
    """One record per signature, from the days cached (fetching any not
    cached): the cut name, its rule, title and join (signatures()), the
    clause, the day and the note.

    A listed note that states a size but comes back without HTML, one
    stating 0 (image only), a weekday listing no note, and a "Rúbrica"
    no rule cut are counted, and past DOF_MAX_EMPTY, DOF_MAX_IMAGE_ONLY,
    DOF_MAX_SILENT or DOF_MAX_UNCUT the fetch is refused: a changed
    layout would otherwise read as a year with fewer signatures."""
    days = _cache_days()
    records: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    uncut: Counter[str] = Counter()
    for day in days:
        counts.update(day["counts"])
        for note in day["notes"]:
            for excerpt in note["excerpts"]:
                for found in signatures([tuple(block) for block in excerpt]):
                    if isinstance(found, str):
                        uncut[found] += 1
                        continue
                    records.append({**found, "day": day["day"], "note": str(note["note"])})
    listed = counts["read"] + counts["empty"]
    with_html = listed + counts["image only"]
    weekdays = [day for day in days
                if datetime.date.fromisoformat(day["day"]).weekday() < 5]
    silent = sum(1 for day in weekdays if not sum(day["counts"].values()))
    marks = len(records) + sum(uncut.values())
    _refuse_past([(counts["empty"], listed, DOF_MAX_EMPTY, "notes with HTML came back empty"),
                  (counts["image only"], with_html, DOF_MAX_IMAGE_ONLY,
                   "notes with HTML stated a size of 0"),
                  (silent, len(weekdays), DOF_MAX_SILENT, "weekdays listed no note"),
                  (sum(uncut.values()), marks, DOF_MAX_UNCUT, "Rúbricas cut no name")],
                 "the DOF's layout may have changed under the reader")
    return Fetched(records, DOF_TO.isoformat(), {
        "from": DOF_FROM.isoformat(), "to": DOF_TO.isoformat(),
        "excerpt_version": DOF_EXCERPT_VERSION, "cut_version": DOF_CUT_VERSION,
        "notes": dict(counts), "uncut": dict(uncut),
        "cuts": dict(Counter(r["cut"] for r in records))})


def renew_dof() -> None:
    """What `fetch --refresh` runs first: every day fetched again, each
    replacing its cached file once read whole. The DOF corrects a note
    by publishing another, so a day once cached seldom changes."""
    _cache_days(again=True)


_check_range = _pinned("from", lambda: DOF_FROM.isoformat(),
                       "was fetched from {held}, and this tool reads from {wanted}")
_check_to = _pinned("to", lambda: DOF_TO.isoformat(),
                    "was fetched to {held}, and this tool reads to {wanted}")
_check_cut = _pinned("cut_version", lambda: DOF_CUT_VERSION,
                     "was cut by cut version {held}, and this tool cuts by "
                     "version {wanted}; fetch again, which reads the cached days")


_check_excerpt = _pinned("excerpt_version", lambda: DOF_EXCERPT_VERSION,
                         "was cut from excerpts of version {held}, and this tool reads "
                         "version {wanted}; fetch again, which reads every day again")


def check_dof(meta: dict[str, Any]) -> str:
    """Why a corpus of other days, other excerpts or another cut is refused."""
    return (_check_range(meta) or _check_to(meta) or _check_excerpt(meta)
            or _check_cut(meta))
