# Corpus snapshot and released-wheel comparison

Dev-only tooling (not shipped: only `nameparser/` is packaged). Two
tools read the same corpora, `corpus*.jsonl` beside this file:

- **`snapshot.py`** records how the working tree reads every corpus
  name, one line per name in `snapshot.jsonl`, and
  `tests/v2/test_snapshot.py` fails when the tree stops matching it.
  This is the check that runs on every change (#664).
- **`compare.py`** reads the same names with a released nameparser
  installed fresh from PyPI and prints how the tree differs. It is for
  questions about a release older than the snapshot, and it fails on
  nothing.

Both print moves the same way: grouped by which fields changed, with
each name's old and new values, so a large change reads as a few
kinds of move rather than a wall of names.

## The snapshot

```
uv run python tools/differential/snapshot.py              # check, grouped
uv run python tools/differential/snapshot.py --record     # re-record
uv run python tools/differential/snapshot.py --since v2.5.0
```

Each line holds one (name, order): the seven role fields, the reported
ambiguity kinds, `initials()` and the two case-repair views on the 2.0
surface (#826) -- `capitalized` where `capitalized()` renders other than
the name as parsed, `capitalized_force` where `capitalized(force=True)`
renders other than `capitalized()` does. A name repair leaves alone
records neither, but a view is the whole repaired name, so in a name
repair does change, a role move that changes the rendering moves the
view too, whether or not a word's case changed -- and, under
`facade`, whatever `HumanName` reads differently from the 2.0 surface
(3 names on 2026-10-13). Empty values are left out, so a reading that
gains a field shows as one added key.

**When the test fails.** Read the grouped moves it prints. If every
move is one the change intends, re-record and commit `snapshot.jsonl`
with the change: the diff of that file is the review's list of the
names the change moved, one line per name. A move nobody predicted is
a finding, the same as any failing test. A corpus that loses names
shows them as `(removed from corpus)`, so a truncated file cannot
pass for a clean run.

**At release time.** `--since <last release tag>` compares the tree
against the snapshot as committed at that tag: the names this release
moved. That is the measurement a release-note claim about moved names
is drawn from. Count CLDR's fictional renderings out of such a figure,
or say it includes them: the closing line says how many moved names
only `corpus_cldr.jsonl` holds. A snapshot committed before #826
records no case view, so against one (`--since v2.5.0`) the views are
not compared and the report says so; a case claim for that release is
read from `compare.py --baseline 2.5.0`, which computes the views on
both sides.

`--tree PATH` reads with another checkout's `nameparser` (the corpus is
always this checkout's), and checks that the import really came from
there. It is how two commits are compared without a release between
them.

## Comparing against a released version

```
uv run python tools/differential/compare.py --baseline 1.4.0
uv run python tools/differential/compare.py   # bare = DEFAULT_BASELINE, the last release
uv run python tools/differential/compare.py --baseline 1.4.0 --corpus my_names.jsonl
```

`--corpus PATH` (repeatable) compares a file of your own instead of the
corpora here, one JSON string per line.

`compare.py` renders a small worker script with the release pinned in
PEP 723 inline metadata, writes it to a temp directory outside the
worktree, and runs it with `uv run --no-project`. The worker parses
every corpus name with the pinned release; `compare.py` parses the same
names with the tree and prints the moves. From 2.0.0 on both surfaces
are compared; at 1.4.0 the facade alone, since 1.4 has no 2.0 API.
A name tagged with a family-first shape is skipped below 2.0.0, which
introduced `name_order`. The closing lines count the moved entries
against the entries compared, how many of the moved are Latin-only,
and how many order-bearing entries were skipped: quote a figure with
its population.

Most of what is left in `compare.py` exists for one failure: a
comparison that silently reads the tree on both sides and reports no
differences. The worker prints its own `__version__` and `__file__`
first, and the run aborts unless the version matches the requested
release *and* the module loaded from outside the repository.
`compare.py` also checks that its own import is this checkout's source
package, and strips `PYTHONPATH` from the worker's environment. The
traps below are why.

## The three invocation traps

None of the three below is hypothetical -- the second was reproduced
twice while working on #320, and the third was demonstrated during
review of this harness's own generalization. The first two are
recorded here because the generated worker's cwd and script path are
what disarm them: a later change that runs the worker from a cwd
inside the project reopens both. The analysis is the
reason for the design, so it outlives the bug.

**Without `--no-project`,** `uv` installs the working tree as an
editable dependency and the version pin never takes effect, silently
comparing the tree against itself. `compare.py` passes `--no-project`,
and runs the worker from a temp cwd where there is no project to
discover in the first place.

**With `python` in front of the script path** --
`uv run --no-project python <script>` instead of
`uv run --no-project <script>` -- `python` becomes the command and the
script a mere argument, so `uv` never reads the script's PEP 723
inline metadata and the `nameparser==<baseline>` pin is never
installed. With nothing to satisfy, `uv` runs the script in the
project's own `.venv`, where the working tree is installed editable
(`__editable__.nameparser-2.0.0.pth`) -- so the import resolves to the
checkout and **the tree answers every query while the output is
labelled with the baseline version**.

It is the same editable working tree that the missing-`--no-project`
case lands on, by a different road. **`PYTHONSAFEPATH=1` does not
rescue it** -- that is the fix for the sibling CWD trap (`AGENTS.md`,
"Comparing against v1"), and reaching for it here is the natural wrong
turn, since a `.pth`-installed package is on `sys.path` proper and
safe-path never touches it. Measured: safe path on, still 2.0.0.
`sys.path[0]` is the SCRIPT's directory, which contains no
`nameparser` at all, so the CWD is not the route either. Running the
same command with an absolute script path from a directory outside the
project is the one variant that does not lie: it raises
`ModuleNotFoundError` instead. Generating the worker into a temp dir
makes that honest variant the only reachable one.

That corruption is worse than an ordinary mistake, because of what the
bad output looks like. It is not garbage and it does not crash: it is
exactly the tree's own expected values, which is exactly what someone
asking "did the baseline agree?" is hoping to see. Every diff
vanishes, the run comes out as parity, and the conclusion drawn is the
precise opposite of the truth.

So do not trust a version number you did not make the worker report.
Establishing which library actually answered is cheap, and the harness
now does it for you: the worker prints `nameparser.__version__` and
`nameparser.__file__` from **inside** itself as its first output line,
and `compare.py` aborts unless the release tuple matches the requested
baseline *and* the module resolved outside the repo root. Both halves
matter and neither implies the other -- an editable install reports
the TREE's version, so version agreement proves nothing when tree and
baseline share a number, while a genuine wheel at the wrong version
passes any path check.

### Trap 3: `PYTHONPATH` shadows BOTH sides, and the tell passes

The first two traps are about which library answers as the *baseline*.
This one is about the *tree*, and it defeats every guard aimed at the
other side.

Run as a script, `sys.path[0]` is `tools/differential/` -- which holds
no `nameparser` -- so a `PYTHONPATH` entry outranks the editable
install and `compare.py` imports a released wheel while believing it
read the checkout. PEP 723 does not save the worker either:
`PYTHONPATH` precedes site-packages *inside* uv's own environment.
Measured 2026-08-05, with a released 2.0.0 on `PYTHONPATH`:

```
baseline: nameparser 2.0.0 (.../shadow/nameparser/__init__.py)
corpus: 751 names; intentional diffs: 0; unexplained: 0
```

exit 0, with **both halves of the baseline tell passing** -- the
version matched, and the path was outside the repo. 89 diffs became 0.

(That output is the ledger-era summary line; the trap is the same for
today's report, which would print no differences.) Two things close
it. `_worker_env()` strips `PYTHONPATH`/`PYTHONHOME`
from the child, and `_check_tree()` requires `compare.py`'s own
`nameparser` to be this checkout's **source package**.

That second predicate was first written as "somewhere under the repo",
which was wrong in a way worth recording: the checkout also contains
`.venv/`, `build/lib/` and `dist/`, any of which can hold a released
wheel, so `PYTHONPATH=<repo>/build/lib` was the same trap with the
shadowing directory moved one level to the left -- and `uv` never
touches `build/`, so nothing self-heals it.

Why this is easy to miss when probing by hand: from the repo root,
`python -c "import nameparser"` puts the CWD on `sys.path` first, so
the checkout wins and the trap does not reproduce. Only the script
invocation shows it.

## The corpora

| File | Job | Source | Blind to |
|---|---|---|---|
| `corpus.jsonl` | Watch | v1's own test suite at a pinned ref | anything 2.0 added: v1's authors had no reason to test a typographic nickname delimiter or a Cyrillic title |
| `corpus_issues.jsonl` | Watch | name-like strings harvested from the GitHub issue tracker | anything nobody ever reported |
| `corpus_cjk.jsonl` | Watch | the CJK-bearing rows of `tests/v2/cases.py`, via `build_cjk_corpus.py` (#295) | anything the case table itself missed |
| `corpus_cldr.jsonl` | Watch, Score | Unicode CLDR's person-name formatting test data at `release-48`: each fictional name's long, formal rendering in givenFirst, surnameFirst and sorting order, about 110 locales in native scripts, via `build_cldr_corpus.py` (2026-10-12); Unicode-3.0, notice in `cldr_LICENSE` | real-world name distributions: the names are written to fill every field, so full-house names are over-represented and plain two-word names under-represented |
| `corpus_gnd.jsonl` | Watch, Score | the German National Library's authority file (GND, via lobid), real people who are deceased and have a Wikipedia article: each preferred name as cataloged (`Gogh, Vincent van`) and, outside family-first areas, a given-first rendering composed from its fields (a regnal name is composed only, `Johann II.`, without its German descriptor), sampled by shape and area via `build_gnd_corpus.py` (2026-10-16); CC0, credit in `gnd_LICENSE` | names as their bearers write them: German library romanization and German forms for historic figures, Latin script only, titles, credentials and nicknames kept out of the preferred name (a few slip into a `personalName`: `Imam Bonjol`), and the catalog's entry rules (not the bearer's culture) decide what counts as a surname |
| `corpus_wikidata.jsonl` | Watch, Score | Wikidata, real public figures (deceased, or with at least 10 sitelinks) whose item states a second surname (P1950: Spain, Mexico, Colombia) or a patronymic (P5056: Russia, the Soviet Union, the Russian Empire, Iceland, Malaysia): each P1559 native-language name and own-language label whose every word aligns with exactly one stated part, via `build_wikidata_corpus.py` (2026-10-16); CC0, credit in `wikidata_LICENSE` | everything the strict alignment drops: short display forms without the second surname, nicknames, and names with an unrecorded part, so tidy names are over-represented; only those eight citizenships; no titles, credentials or suffixes |
| `corpus_wikidata_native.jsonl` | Watch, Score | Wikidata, real public figures (deceased, or with at least 10 sitelinks) with a name written in their own script: Hangul, Han and kana, Arabic (Syria, Egypt, Saudi Arabia, Iran), Hebrew, Georgian, Armenian, Greek, Cyrillic beyond Russian (Serbia, Bulgaria, Ukraine, Kazakhstan), Bengali, Devanagari and Thai, 20 strata sampled by country and language. Each person's first P1559 or own-language label whose every word, or every character in unspaced text, aligns with exactly one stated part, via `build_wikidata_native_corpus.py` (2026-10-16). CC0, credit in `wikidata_native_LICENSE` | everything the strict alignment drops, which in these scripts is most names: Arabic nasab chains (`بن` is no connective in Arabic script), `آل` family names and kunyas (most Arabic items state no family name), Chinese names whose given name has no item (most), Japanese names whose given-name item holds only a kana reading, and names whose parts are labelled only in Latin script (most Devanagari, Bengali and Thai items, so those strata are 10–25 names); transcriptions with the 间隔号; Urdu and Marathi entirely; no titles, credentials or suffixes |
| `corpus_conventions.jsonl` | Watch, Score | invented names patterned on naming conventions the other corpora barely cover -- no family name, religious names, positional patronymics, honorifics after the name -- from the hand-written table in `conventions.py`, via `build_conventions_corpus.py` (#686) | real names, and every convention nobody has written a row for: about one row per convention, so it shows that a convention moved, not how often |
| `corpus_rules.jsonl` | Watch | every example in `docs/design/rules/`, via `build_rules_corpus.py` (#414) | anything the rules doc has no example for |
| `corpus_shapes.jsonl` | Watch | shape-tagged rows of `tests/v2/cases.py`, via `build_shapes_corpus.py` (#468) | anything no one has tagged a row for |

The jobs are mechanisms.md#NAME-DATA-JOBS: Watch is the snapshot above, Score the agreement records below (`cldr_agreement.py`). Each covers a blind spot of the others. `corpus.jsonl` is reproducible
forever from an immutable git ref, while the issue tracker is mutable,
so regenerating `corpus_issues.jsonl` is an explicit, reviewable act.
The CJK corpus exists because both of those are structurally blind to
unspaced CJK (v1's banks never tested it; `build_issues_corpus.py`
requires an internal space, which unspaced names never have). The
rules corpus watches the names the project wrote down as defining its
behavior: the doc tests pin each example against an expectation stored
beside it, so a deliberate change edits both and stays green, while
the snapshot shows the moved name in the diff.

A corpus line is a bare JSON string or an object carrying `name` and,
optionally, `tests` (labels, below) or `shape`, an input-shape id from
`shapes.py`, which records each shape's notation, the `name_order` it
is an input shape FOR, and the oldest release that can honor that
order. An entry whose shape declares an order is read under that order
on the 2.0 surface alone. Any other key is refused, since a misspelled
key would drop the shape and read the name under the default order
with nothing saying so. `corpus_shapes.jsonl` holds every distinct
(shape, name) pair from the tagged case rows, so a name tagged under
two orders is two entries. `--coverage` prints names per shape:

```
uv run python tools/differential/build_shapes_corpus.py
uv run python tools/differential/build_shapes_corpus.py --coverage
```

## Local corpora

A local corpus holds real names that are not committed: fetched into the cache by `local_corpora.py`, read by `snapshot.py --local` and by a row of `tools/name_usage.py`, and seen by no reviewer and no CI run (the SURVEY job in mechanisms.md#NAME-DATA-JOBS, and WATCH outside CI). What reaches the repository is what a contributor cites from it, counts and shapes written with made-up names.

```
uv run python tools/differential/local_corpora.py fetch ctgov-officials
uv run python tools/differential/local_corpora.py tally ctgov-officials --top 50
uv run python tools/name_usage.py --no-wikidata MA FNP-C
```

To read what a branch moves, record the local snapshot with the base checkout, then check with the branch:

```
uv run python tools/differential/snapshot.py --local ctgov-officials --record --tree ../master-checkout
uv run python tools/differential/snapshot.py --local ctgov-officials
```

`compare.py --corpus` takes the cached `corpus.jsonl` too, against a release.

| Source | What it is | Blind to |
|---|---|---|
| `ctgov-officials` | every overall official of every study on ClinicalTrials.gov, whatever the role (principal investigators, study directors and chairs, and a few sub-investigators and officials with no role), the name as the sponsor's staff typed it into a free-text field: credentials run together (`MBBS,FCPS`), job titles in the name, all-caps and all-lowercase names, typos. Fetched from API v2 (NLM) | names outside clinical research, which is mostly medicine and heavily credentialed; names nobody typed by hand |
| `fec-individuals` | the distinct names of every individual contributor in the FEC's bulk file for the 2026 cycle (`indiv26.zip`, downloaded once into the cache and read without unpacking; `fetch --refresh` downloads it again). Mostly a filer's software writing a form's fields in a fixed order: of its 1,893,964 names on 2026-10-18 every one was in capitals and 1,893,961 held a comma, with hand-typed text inside the fields -- 3,306 held a second comma, for a credential run or a suffix in a part of its own (`DOE, JR., JOHN`). The population for the one-case family-comma shape. The FEC's terms (52 U.S.C. 30111(a)(4)) bar using the names to solicit contributions or for any commercial purpose | case, since every name is in capitals; names written in their spoken order, or without a comma; small donors, since a committee need itemize only a donor whose gifts to it pass $200; names outside the US; names in any script but Latin |
| `tse-donors` | every individual donor to a candidate in Brazil's 2022 general and 2024 municipal elections (the TSE's candidates' accounts, rows from `Recursos de pessoas físicas`), a record per distinct pair of the name as the campaign filed it (`name`) and the federal tax registry's name for the same donor (`registry`): a typed form with its reference form beside it. Of 854,531 records fetched 2026-10-22 (848,351 distinct filed names), 205,925 differ from their registry name -- an agnomen dropped or abbreviated (`JR` filed for the registry's `JUNIOR` in 1,615, `JÚNIOR` for `JUNIOR` in 975), a word left out. Nearly all in capitals (845,498 filed names), in spoken order with no comma (184 records hold one), and full of particles and agnomens (`DE`, `DA`, `DOS`; `FILHO` ends 10,955 distinct filed names, `JUNIOR` 13,784, `NETO` 8,410). Published by the TSE under CC BY | case, mostly; the family-comma shape; credentials and titles, which a donation form has no place for; donors to parties rather than candidates; names outside Brazil; names in any script but Latin |
| `tw-donors` | the distinct names of every individual donor in every campaign finance report Taiwan's Control Yuan publishes on its political donation platform (ardata.cy.gov.tw, whose zips data.gov.tw also lists): 454 reports of 64 elections on 2026-10-22, presidential, legislative and local: every report from 2018's elections on, and the residual reports of 2014's and 2016's. Each report's zip is cached under the name the platform lists it by, which carries the date it was built, so a refresh downloads only the reports published or rebuilt since. Names as a candidate's staff typed them into a filing, published in full where the ID, address and phone beside them are masked. Of the 308,667 names dated 2026-10-05, 296,820 were three Han characters, 5,449 four and 5,260 two; the population for unspaced Han names written family first, and for the married double surname (冠夫姓) a four-character name often is. Under the Open Government Data License, version 1.0, with the platform's own bar on using the data for profit, credit investigation or another improper purpose | names in spoken order; Latin script (80 of the names dated 2026-10-05 held a Latin letter); the comma (3 of them held a fullwidth one, none an ASCII one); case; names outside Taiwan; donors whose names the report does not publish, such as anonymous gifts; Japanese kanji names, which the Han script cannot tell from Chinese |
| `ukec-individuals` | the distinct names of the individual donors in the UK Electoral Commission's register of donations (to parties, their members, third parties, permitted participants and regulated donees), from the search's CSV export under the site's own default filter, fetched whole on every fetch (9.5 MB on 2026-10-22, accepted dates from 2001 to 2026). The default leaves out donations reported only before a poll (`prePoll=false`: 374 rows and 21 names on 2026-10-22). A name as the donee's return gave it, mostly in its spoken order and mixed case, with the donor's title: of its 15,214 names on 2026-10-22, `parse()` read a title in 8,219 (its `title` field non-empty) (`Mr`, `Ms`, `Mrs`, `Lord`, `Dr`, `Sir`; 32 a run of two or more, `The Rt Hon`) and a suffix in 320 (`MP`, `OBE`, `CBE`, `QC`). The population for titled British names. The Commission publishes its documents under the Open Government Licence v3.0, but the register states no reuse terms of its own, which the credit line says | the family-comma shape (2 names hold a comma) and case (9 are in capitals); small donors, since a donation is reported only above a threshold that depends on the donee; names outside the UK; names in any script but Latin |

A live source has no fixed snapshot to pin, so the cached copy is the pin: `meta.json` holds the source's data date and the sha256 of `raw.jsonl` and `corpus.jsonl`, checked on every load, and every report, the `name_usage.py` row included, carries the source and that date. Quote a count with the date, and expect a later fetch to differ. A local snapshot records which fetch it was read from, and `snapshot.py --local` refuses to compare it with a corpus fetched since, which would report the names the source gained and lost as moves: after a `fetch --refresh`, record again from the base checkout. ClinicalTrials.gov's terms ask anyone redistributing its data to credit it, show NLM's processing date and say what was changed; keeping the names in the cache and citing counts with that header meets them. The FEC's bar on soliciting and commercial use is in the credit line of every `fec-individuals` report, so a count quoted from it carries the bar with it. A record there is a distinct name, not a contribution or a contributor: one donor gives many times (34,264,742 rows held 1,893,964 names in the file dated 2026-10-18), and counting contributions would weight a shape by how often its bearers give. `tools/name_usage.py` looks a word up in each corpus's word index, cached as `wordindex.json` beside it on first use and keyed to the records' sha256 and to the code that cuts and folds a word, so a refetch or a change to the fold rebuilds it; a single-word lookup it answers parses neither the records nor the names. Measured 2026-10-22 with both corpora fetched, a single-word `name_usage.py --no-wikidata` run took 2.5s with their indexes cached (12.5s before the cache, 14.8s on the run that builds it). A spaced word (`Ph. D.`) still scans every name, which took 8.6s, nearly all of it the FEC corpus's. `fetch --refresh` re-downloads the FEC's zip rather than re-reading the cached one, replacing it only once the new one is whole, and a corpus fetched for another cycle than `FEC_CYCLE` is refused on load. The `fec-individuals` fetch refuses a file whose lines stop matching the 21 columns it reads, or whose names stop holding a comma, rather than read it as a smaller or a different corpus. A `ukec-individuals` record is a distinct name too, not a donation or a `DonorId`: one name often holds several IDs, which seem to come with reports rather than with people (15,214 names held 24,473 on 2026-10-22, the IDs counted in `meta.json`'s detail; 2,663 names held several at one `RegulatedEntityId` alone, counted from the export and not kept, though some of those may be two people of one name), so a count of IDs would weight a name by how often it was reported. Its fetch reads the register's total from the JSON search under the same filter before and after the export, and refuses an export holding another number of rows, or a register that changed in between: the export ignores `rows=`, so the total is what tells a cut or capped export from the whole register. It refuses an export whose last row is cut short (Python's `csv` returns a body cut inside a row as a short last row, which the row count would otherwise take for a whole one), and a header other than the 29 columns `UKEC_COLUMNS` names, and counts into `meta.json`'s detail the rows it skips: rows not 29 fields, rows from a donor that is not an individual (the filter asks the server to leave those out), and individuals with no name. Past `UKEC_MAX_BAD` (1 in 10,000) of either of the first two, or `UKEC_MAX_NAMELESS` (1 in 1,000; 4 of 42,355 rows were nameless on 2026-10-22) of the third, it refuses the export. The data date is when the first search answered, in UTC: the register states no date of its own, so the counts above, dated by the day they were fetched (2026-10-22), carry the data date 2026-10-23T03:13:19Z in their header. `tw-donors` keeps one zip per report under `reports/`, whole, its masked ID, address and phone columns included, as the FEC's zip is kept: the platform's download answers a report that does not exist and a fault alike, with a 500 and an incident number, so the fetch reads which reports exist from the platform's listing and refuses a listed report it cannot download. It reads each file's columns by name, since a 2020 report lacks a column the newest ones write, and refuses a column it does not know, a category it does not know, a row whose serial column names another report (the zip is not the one asked for), a listing that changes during the fetch, and a report more than half of whose rows it reads past. It reads back the rows a stray quote took into one field (169 rows in 12 records of three reports on 2026-10-22, 8 of them two rows joined by two stray quotes), counts donor cells that hold no name (匿名, a dash) or a masked one, and caches a downloaded zip only once its rows are read, so a refused zip is asked for again. A zip the platform rebuilt under the name it had is not seen: delete `reports/` to download every report again. A layout check written from one surveyed file meets every other file only at fetch time: `tw-donors`' first three fetches were each refused partway, by a report with no income writing one row of dashes, by a 2020 report with 24 columns where the surveyed one had 25, and by a row with no category. Each refusal cost every download again until the source cached its zips, so a new source that downloads many files caches each one before its checks run. `tse-donors` caches nothing but the corpus: each election's national member (`receitas_candidatos_<year>_BRASIL.csv`) is read from the TSE's CDN in HTTP Range requests, 209 MB for the two elections where their zips are 1.82 GB (2026-10-22), because the TSE regenerates the zips every few days and a cached one would be stale within the week. Every range request carries `If-Range` with the ETag the HEAD gave if it is strong, else its `Last-Modified`, and every part must state the `Content-Range` asked for, so a zip replaced during the read is refused rather than read across two versions; a HEAD that states no length, neither a strong ETag nor a `Last-Modified`, or `Accept-Ranges` other than `bytes` is refused before the read. A fetch took 69s on 2026-10-22. It refuses a zip without the national member, a header that is not 60 columns or lacks its three columns, a `DS_ORIGEM_RECEITA` value it does not know (a renamed category, or the file no longer in Latin-1), malformed rows or lines folded into a field past `TSE_MAX_BAD`, an election with too few rows from individuals (`TSE_MIN_INDIVIDUALS`: a member cut to its header, or the donations moved under another category) too many without a name or registry name (`TSE_MAX_MISSING`, counting a placeholder such as `#NULO` or `***` as none: a masked column) or with a number in one (`TSE_MAX_NUMBERED`: a numeric column moved under a name), too few distinct filed or registry names (`TSE_MIN_DISTINCT`: a column masked with one word), and a corpus fetched for other elections than `TSE_ELECTIONS`. The CPF in each row is unmasked in the file, and like every other column it is read past, never stored or printed; a pair either of whose names holds more than 4 digits is dropped and counted, since campaigns sometimes typed a number, a CPF among them, into the name field. A record is a pair, so the counts in its reports (`tally`, the `name_usage.py` row) are of pairs, and a filed name standing beside two registry names counts twice.

## Corpus provenance

`corpus.jsonl` is checked in as a test fixture. It was built by
`build_corpus.py`'s AST walk over every top-level `tests/test_*.py`
file (the v1-style test banks; `tests/v2/` is a separate 2.0-only
harness and is deliberately not scanned), reading each file via
`git show <ref>:<path>` rather than the working tree:

```
uv run python tools/differential/build_corpus.py --ref 2d5d8c2 > tools/differential/corpus.jsonl
```

`2d5d8c2` ("Trim constant-factor waste on the tokenize hot path") is
the last commit before M12 reconciled/edited the v1 test banks against
the 2.0 facade -- M12 changed some expectations in place and deleted
bucket-A tests outright, which would have shrunk and skewed the
corpus. Reading history at an old ref via `git show` is a read-only
operation on this worktree's own log; it does not check out, stash, or
otherwise mutate anything.

The AST extraction over-collects on purpose (string literals passed as
`HumanName(...)`'s first argument, plus string members of list/dict/
tuple banks that contain a space) -- more candidate strings is more
coverage, and the corpus is deduplicated. Obvious non-names (strings
containing `{`, `@`, or a backslash -- format placeholders, decorator/
email-shaped fixtures, escape sequences) are dropped.

Each line is `{"name": ..., "tests": [...]}`: `tests` is the sorted
labels the name appeared under at the pinned ref -- the shape context
(`test_title_with_conjunction` and kin) the original bare-string scrape
kept the string but threw away. A `HumanName(...)` call is labelled by
its nearest enclosing test method, falling back to the source filename
(e.g. `test_titles.py`) for a call at module scope; a list/dict/tuple
bank is labelled by its variable name, prefixed `bank:` so it reads
apart from a test method at a glance (`bank:<unnamed>` when the
assignment target isn't a plain name). Labels merge across files: two
files sharing a method name (e.g. two `test_basic_parsing`s) produce
one merged label set on any name both contribute, which is accepted --
the merged labels still describe the same string.

Regenerate the corpus only (a) at the same ref, as a format-only
enrichment, with the name set proven identical to the previous file by
set comparison, or (b) if the v1 test banks are revisited again at a
still-earlier point in history; otherwise leave the checked-in file
alone so the harness stays comparable run to run. For (a):

```
uv run python tools/differential/build_corpus.py --ref 2d5d8c2 > /tmp/corpus-new.jsonl
uv run python -c "
import json, subprocess
def _n(x): return x if isinstance(x, str) else x['name']
old = {_n(json.loads(l)) for l in subprocess.run(
    ['git', 'show', 'HEAD:tools/differential/corpus.jsonl'],
    capture_output=True, text=True, check=True).stdout.splitlines() if l.strip()}
new = {_n(json.loads(l)) for l in open('/tmp/corpus-new.jsonl', encoding='utf-8') if l.strip()}
if old != new: raise SystemExit(sorted(old ^ new))
print(f'identical: {len(old)} names')"
cp /tmp/corpus-new.jsonl tools/differential/corpus.jsonl
```

`corpus_issues.jsonl` is built by `build_issues_corpus.py` from the
issue tracker (`gh issue list --state all`), taking `HumanName("...")`
calls and quoted capitalized phrases -- the two ways a reporter writes
the input that broke on them. Regenerate with:

```
uv run python tools/differential/build_issues_corpus.py > tools/differential/corpus_issues.jsonl
```

Unlike the ref-pinned corpus this is a mutable source, so the
checked-in file is the snapshot under test; re-running only adds names
as new issues arrive. Over-collection is fine in both builders: the
comparator just parses more names, and junk like `Bridge (1.4)` costs
one parse and produces no diff.

`corpus_cjk.jsonl` is a projection of the case table:

```
uv run python tools/differential/build_cjk_corpus.py
```

Every distinct CJK-bearing `text` in `tests/v2/cases.py`, `tolerated`
rows included. The generated corpora (`corpus_cjk`,
`corpus_conventions`, `corpus_rules`, `corpus_shapes`) are each pinned
by `tests/v2/test_corpora.py` against their generator's selection, so a
case row, a rules example or a `conventions.py` row added without
regenerating fails the suite instead of silently narrowing what the
snapshot watches.

`corpus_conventions.jsonl` is generated from `conventions.py`, a table
whose rows record the tradition, the convention a name exercises, and
what a reader who knows the convention would take each part to be:

```
uv run python tools/differential/build_conventions_corpus.py
```

The note is prose. Where a field can state the parts, the row
states them too, and the builder writes those rows to
`conventions_fields.jsonl` for the agreement ratchet (below). A row
whose reading is settled can graduate to `tests/v2/cases.py`. The names
are invented, never copied from the references the conventions come
from.

## What the corpora do not cover

The corpora run under the **default policy**, so any behavior gated
behind a non-default `Policy` field is invisible here. Default
*vocabulary* is a different matter: it is fully in EFFECT, never
gated off the way a `Policy` field is, so a change to it can show up
here. That is not the same as coverage -- only 5 of the 17 shipped
`maiden_markers` and 8 of the 15 `honorific_tails` appear anywhere in
the corpora (re-measured 2026-08-26; the marker count was 3 until
#414's rules corpus brought in a parenthesized `Nee`, the denominator
was 17 until `roz` left the vocabulary in 2.2 -- it appeared in no
corpus name, so only the denominator moved -- and #434's `z domu` then
put both back up by one), so an entry no corpus name exercises is as
invisible as an opt-in policy.

Those two numbers count WHOLE TOKENS, delimiters stripped, and
consecutive RUNS of them: an entry may be a PHRASE (`z domu`), which no
single token can equal. The run half earns exactly one of the five, and
it is the reason the count is not simply per word -- `z` and `domu`
each appear in corpus names that carry no marker at all. The strip
earns another: `nee`, which appears in the corpora only inside brackets
-- `Jane Smith (Nee)` and `Jane Smith (Nee) (Jones)` -- where the token
carries them until they come off. `née` needs no strip, appearing bare
in many names, and `né` is not counted at all: it occurs only as a
substring of `née`, never as a token. Matching a non-ASCII entry
anywhere inside a name instead (旧姓 is written flush against the name
it marks) makes the marker count 6, adding `né`. Recompute:

A heredoc, not `python -c "..."`: the strip set contains a double
quote, which closes the `-c` string and leaves the rest to the shell.
Paste this as it stands.

```
uv run python - <<'PY'
import glob, json
from nameparser import Parser
from nameparser._lexicon import _normalize
L = Parser().lexicon
def _n(x): return x if isinstance(x, str) else x['name']
names = [_n(json.loads(l)) for f in glob.glob('tools/differential/corpus*.jsonl') for l in open(f, encoding='utf-8') if l.strip()]
for s in ('maiden_markers', 'honorific_tails'):
    v = getattr(L, s)
    longest = max(e.count(' ') + 1 for e in v)
    runs = set()
    for n in names:
        t = [_normalize(w.strip('()\'"«»“”„「」『』（）')) for w in n.split()]
        runs |= {' '.join(t[i:i+k]) for k in range(1, longest+1) for i in range(len(t)-k+1)}
    carries = set(runs & v) | {e for e in v if not e.isascii() and any(e in n for n in names)}
    print(s, len(runs & v), 'of', len(v), sorted(runs & v),
          '| substring reading:', len(carries), sorted(carries))
PY
```


Two independent mechanisms put a birth surname in `maiden`, and what
is opt-in about them is narrower than it looks (rows measured
2026-08-05, re-measured 2026-08-26):

| input | default policy | `maiden_delimiters={("(", ")")}` |
|---|---|---|
| `Jane Smith (Jones)` | nickname `Jones` | maiden `Jones` |
| `Jane Smith née Jones` | maiden `Jones` | maiden `Jones` |

Row 1 carries no marker word, so it isolates the delimiter: the
brackets alone route their content to `maiden`, and only once the
policy says they do. Row 2 carries no brackets, so it isolates the
marker: `Lexicon.maiden_markers` ships 17 entries by default, `nee`
among them, and the bare form needs no configuration at all.

So what is opt-in is neither the marker words nor the delimited path
as a whole: it is the delimited path for content that does not
announce itself. Since #335 a clause holding a word past its marker
reads as the maiden name whichever bucket its pair sits in
(`rules/M3`), so `Jane Smith (née Jones)` needs no configuration
either. A word past the MARKER, not a second word in the clause: since
#434 a marker may be a phrase, and `Maria Kowalska (z domu)` is a
two-word clause that stays a nickname because both its words are the
marker. Row 1 is exactly the shape that still does — a markerless
clause — along with a one-word clause like `Jane Smith (Nee)`, where
nothing in the content says maiden and only a caller who knows the
data can.

## The CLDR agreement ratchet

`corpus_cldr.jsonl` was the first corpus whose names arrive with ground truth: CLDR states every name's fields separately, and `build_cldr_corpus.py` keeps them in `cldr_fields.jsonl`. The snapshot watches those names like any corpus's. Separately, `cldr_agreement.py` compares them against CLDR, role by role — title, given names, family, suffix, and the particle/base split where CLDR states it — and records every disagreement in `cldr_agreement.json`.

`tests/v2/test_cldr_agreement.py` holds the tree to each source's record (and to the locale record below). It fails when a role that agreed stops agreeing, when a recorded disagreement starts agreeing (so it can be recorded and guarded), when a recorded disagreement's answer changes, and when a recorded rendering no longer exists. When every reported change is intended:

    uv run python tools/differential/cldr_agreement.py --record

and say why in the commit. Run it without `--record` for per-role agreement counts. Nothing is special-cased: an unnatural rendering or a modelling difference (CLDR's `さん` title is a suffix here) simply stays a recorded disagreement, which makes the record a measured worklist as well as a guard.

A second view measures the locale packs (#672). `LOCALE_FILES` in `cldr_agreement.py` maps each CLDR file to the pack for its language (`zh`, `zh_Hant`, `yue`, `yue_Hans` → `ZH`; `ja` → `JA`; `ru` → `RU`; `tr`, `az` → `TR_AZ`); those renderings are parsed with `parser_for(pack)`, over the same `FAMILY_FIRST` base where CLDR's order is surnameFirst, and their disagreements go to `cldr_agreement_locales.json`, ratcheted per pack by the same test. The native-script Wikidata source's Han and kana strata are mapped by `NATIVE_LABELS` (`zh-cn`, `zh-tw` → `ZH`; `ja-jp` → `JA`), since their file is a QID that names no language, and the view parses them the same way into `wikidata_native_agreement_locales.json`. Each source's pack is read from its own rendering key (`locale_sources()`: CLDR's file, the native source's stratum), so a recorded rendering that is gone is still checked by its pack. The summary prints, per pack, how many of its renderings agree in every role under the default parser and under the pack, so a pack PR shows what it moved on its own language. A new pack adds its files to `LOCALE_FILES`, or its name to `NO_CLDR`; the test fails on a pack in neither. The modelling differences stay recorded here too: a pack is not meant to agree with CLDR where the models differ by design.

**The GND source.** `build_gnd_corpus.py` writes the GND's name parts in CLDR's field vocabulary (`forename` → `given`, `prefix` → `surname-prefix` with a one-word `surname` as `surname-core`, any other family → `surname` whole, `counting` → `generation`, and a `personalName` -- a person entered under the whole name, with no surname -- as `given` alone, so the family is expected empty), so `cldr_agreement.py` compares `gnd_fields.jsonl` by the same rules and records its disagreements in `gnd_agreement.json`, ratcheted by the same test. The locale view does not read it: no pack covers its names. A composed rendering says so (`composed: true`); where a particle is glued to the surname (`d'Arenberg`, `al-Ǧaʿfarī`) the composed line states the glued word as a whole `surname`, since the comparison matches fields word by word, and the index form, where the particle is a word of its own, keeps the split. A family with no `prefix`, or with a surname of several words, is stated whole for the same kind of reason: GND does not split a particle inside a surname (`Vélez de Guevara`, `Zuylen van Nijevelt`), so what it leaves unsplit means "not stated", not "no particle", and only `family` is compared there. Raw lobid responses are cached outside the tree, in a `gnd/` directory under `$NAMEPARSER_TOOLS_CACHE` (default `~/.cache/nameparser-tools`); `--refresh` fetches them again. The build stops before writing anything when a stratum falls below its floor, a query matches nothing, or a pool pages short, so a lobid change fails it rather than shrinking the corpus; `--record` prints, per source, how many changes of each kind it accepts.

**Adding a source.** Map only what the source states. The comparison reads a missing field as a statement that the role is empty, so a field the source leaves unstated must be mapped so that its role is not compared at all: #688's first build wrote a prefixless GND surname as `surname-core`, and 19 renderings recorded the parser's `de` in `Vélez de Guevara` as a disagreement no fix could clear; its fix then missed the same gap inside a several-word core after a prefix (`Zuylen van Nijevelt, Julius van`), so test each way a field can be left unstated, not the one that was reported. A field must also occur in its rendering's text, word by word (`test_every_committed_field_occurs_in_its_rendering`), or it is expected empty too. A build must fail rather than shrink: give every stratum a floor, check a response's shape before caching it (an API error arrives as HTTP 200), and raise on a query that matches nothing. But tell a broken fetch from a fact about the data: #689's first fix raised on any item Wikidata reported missing, so one deleted name-part item anywhere in a pool would have stopped every rebuild, with `--refresh` advice that could not help; a missing part now only refuses the person stating it. A source sampled by script must check each text's script itself: Wikidata's `mul` labels are Latin, and the native-script build's first probe kept `Anushka Sharma` as a Hindi name. And give each refusal a test row that fails for the reason it names, not for another: that build's review found an all-Hebrew text standing for "a Hebrew point is not Arabic", which passed with the mark check deleted. A builder change has one oracle the suite cannot run, since it needs the local cache: rebuild offline from `$NAMEPARSER_TOOLS_CACHE` and diff the result against the committed fields file. The same review's mutation pass scored every surviving mutation that way, and four of them would have moved committed rows or the figures quoted from them with every test passing. The fetch (`fetch_bytes`: User-Agent, timeout, optional POST body and politeness delay), the cache (`cache_dir`, `cached_json`, which checks a response before caching it and writes atomically) and the two output files (`corpus_lines`, `fields_lines`, `write_corpus`) are shared in `corpus_build.py`, and the two Wikidata builders share their stratum loop (`build_strata` in `build_wikidata_corpus.py`: a person taken once across strata, the missing-person stop, the floor stop) as well as the pool check; a new builder imports them rather than copying another builder's, because a guard added to one copy is how #696 happened.

**The Wikidata source.** `build_wikidata_corpus.py` exists for the two fields no other open source labels, and states them in `wikidata_fields.jsonl` as `surname2` (P1950, CLDR's own field name) and `patronymic` (P5056, which CLDR has no field for), beside `given` (P735) and `surname` (P734); its disagreements are in `wikidata_agreement.json`. A person's written names are token-aligned to the parts rather than composed from them: a text is kept only where every word is claimed by exactly one part, a connective (`bin`, `i`, `y`) joining the part after it, and a woman's Russian surname may match the feminine form of its item's label. ParsedName has no `surname2` or `patronymic` attribute, so `cldr_agreement.py` lists them in `PENDING_ROLES` and scores them inside `family` and `given_names` respectively -- a patronymic is not a family name, so `Vigdís Finnbogadóttir` expects the family empty -- and also scores each on its own the day ParsedName gains an attribute of that name (whether the merged role then drops it is for the 3.0 design). Until then the summary says how many renderings state each. CLDR's `surname2` is in the same position. A stratum that falls below its floor, a query that matches nothing, a pool short of its size (unless the stratum is marked `whole`, which a full pool then contradicts) and a response that is not what was asked for each stop the build before anything is written; Iceland (270 of a pool of 600 on 2026-10-16, measured in the native paragraph below) and Malaysia are marked `whole`; Malaysia's floor is set below its quota because only 17 Malaysian public figures with a P5056 statement matched the query on 2026-10-16, and 9 of them aligned. Raw responses are cached outside the tree, in a `wikidata/` directory under `$NAMEPARSER_TOOLS_CACHE` (default `~/.cache/nameparser-tools`); `--refresh` fetches them again.

**The native-script Wikidata source.** `build_wikidata_native_corpus.py` exists because every other real-name corpus is Latin script, apart from Wikidata's Russian patronymics, so the script-conditional readings (family-first Han, Hangul and kana; Korean surname segmentation) had been tested only against CLDR's invented names. No text holds an honorific, so the corpus does not exercise the CJK honorific peel; it shows only that the peel leaves plain names alone. It reuses `build_wikidata_corpus.py`'s fetches and token alignment and adds the following. Strata are a country and a language, not a property, and the query keeps people with a label in that language. A text is used only if every letter and combining mark is in the stratum's script (`mul` labels are Latin: `Anushka Sharma` would otherwise pass as a Hindi name). Unspaced text is aligned by character under the same exactly-one-part rule, and nothing is inferred: a Chinese item stating only its surname is left out rather than reading the rest of the text as the given name. Feminine surname forms are kept per language (Greek `Λελούδα` for `Λελούδας`, Bulgarian and Kazakh `-ова`, Ukrainian `-ська`), so the filter does not drop women. A Han, kana or Hangul text carries no shape, since the parser reads those scripts family-first by itself and that is what is being tested; pure katakana keeps the order it is written in, as the parser does. Each person gives one rendering, P1559 first, and its disagreements are in `wikidata_native_agreement.json`. On 2026-10-16 every spaced stratum agreed in every role except seven Arabic surnames of two words (`عبد العزيز`, `عز الدين`, `شكر الله`, `ذو الغنى`: the parser reads the first word as a middle name), a Persian double surname, and a Bulgarian name whose two stated family names include what is probably the father's name (`Динко Цветков Дерменджиев`); Hangul agreed on 120 of 120; Han read by default disagrees on every unspaced Chinese name and 49 of 60 Japanese ones, while the locale view reads 74/80 under `ZH` (six surnames it does not segment: `詹`, `卫`, `柯`, `茅`, `华`, `文`) and 59/60 under `JA`. Wikidata's P734 is a convention, not a fact, where the culture has none: an Arabic nisba (`البغدادي`) is entered as a family name, and the corpus scores it as one. `--lc-check` compares each name with the native-script variants of its Library of Congress record (P244), splitting by LC's comma or, in CJK, a space, and counts an LCCN LC no longer has; it runs after the build has written its files, and adds nothing to them and filters nothing from them. A pool that comes back shorter than its size stops the build unless its stratum is marked as the whole population (Thailand, Kazakhstan, Bangladesh), so a query that starts matching less cannot drift the sample unseen; a stratum so marked whose pool comes back full stops it too, since the mark is then stale. The check is `pooled()` in `build_wikidata_corpus.py`, which both Wikidata builders call; re-pooled on 2026-10-16 (#696), the parent's Iceland returned 270 of a pool of 600 and Malaysia 17 of 240, so both are marked whole, and the other six filled their pools (es 900, mx 600, co 480, ru 660, su 360, ri 240). On 2026-10-16, 99 of the 910 names had an LC variant that splits them, and 96 agreed; the other three are Arabic names whose LC record names a person written the other way round (`Ibrāhīm, Ṣāliḥ` for Wikidata's `إبراهيم صالح`), so the P244 link or the order is suspect, not the split. LC writes most Han variants unspaced, so it confirms almost no Chinese or Japanese split. The 907 corpus lines (904 names new to the snapshot; three Ukrainian names were already in `corpus_wikidata.jsonl`) cost about 2.9 s in the corpus-reading test modules and about 0.6 s in the agreement tests, measured locally without coverage on 2026-10-16. Raw responses are cached under `$NAMEPARSER_TOOLS_CACHE`, in `wikidata/` and `lc/`.

**The conventions source.** `conventions_fields.jsonl` states the parts of the hand-written conventions corpus, from the `fields` of `conventions.py`'s rows, and its disagreements are in `conventions_agreement.json`. The names are invented, so the record is a worklist of conventions rather than a measure of real data: a patronymic read as a family name (`Hassan bin Yusof`), a title read as a given name (`U Kyaw Win`). It uses the Wikidata source's `patronymic`, written with its connective (`bin Yusof`), and adds `honorific`, a word of address written after the name (`Bey`, `ssi`, `san`), scored inside `suffix` as nameparser reads `さん` (Derek, 2026-10-16). A row no field can state honestly is left out of the fields file and stays in the corpus, which the snapshot still watches: the kunya `Abu Karim`, the `-né` married form `Szabóné Kiss Éva`, and `arap`/`ole`/`wa`, whose last word is a parent's name or a family name depending on the family. Such a row says why in its `unstated`, and the builder refuses a row with neither `fields` nor `unstated`, so this fields file states a subset of its corpus without a row's fields being lost unseen. Being hand-written, it is also held to two checks the generated sources pass anyway: its fields partition each text word for word (`test_the_fields_partition_their_rendering`), and the scorer raises on a field name no rule reads, for every source.

`--record` rewrites every record. `JA` needs the `ja` extra (`namedivider-python`), which only CI's `ja-extra` job installs: without it the `JA` ratchet skips, the summary says `not measured`, and `--record` keeps the recorded `JA` entries of both locale records unchanged. Re-record with the extra installed (`uv sync --group dev --extra ja`) when a change moves Japanese.

`_CORPUS_NAMES` in `tests/v2/_differential_fixtures.py` leaves the file out (2026-10-12): the tests reading it carry counts measured over the names the other corpora held. `corpus_gnd.jsonl`, `corpus_wikidata.jsonl` and `corpus_wikidata_native.jsonl` stay in it (2026-10-16): the counts those tests carry are floors and dated snapshots, which a larger corpus cannot falsify, and their invariants now walk all three files' names too. A release figure counts GND's moved names in, its composed renderings included, since the names are real; AGENTS.md's rule of counting out names only `corpus_cldr.jsonl` holds stays CLDR's alone (Derek, 2026-10-16). Wikidata's moved names, native-script ones included, count in under the same rule, which singles out CLDR alone; they are real and written, not composed. `differential_corpus()` in `tests/v2/conftest.py`, which feeds the property tests, globs `corpus*.jsonl`, so it reads CLDR (since #652), GND and both Wikidata files, and the decomposed-twin test walks all their names.
