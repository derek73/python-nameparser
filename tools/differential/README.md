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
view too, whether or not a word's case changed. A snapshot recorded
before 3.0 also holds, under `facade`, whatever the removed `HumanName`
read differently from the 2.0 surface (3 names on 2026-10-13);
`load()` sets that key aside, so `--since v2.8.0` compares the rest.
Since 2.7 a line also holds `alternatives`,
the reading each ambiguity report did not take, one per report in
report order, so a report losing its alternative beside an identical
one still moves the line (#752 phase 2m). Since 3.0 it holds the
suffix's two views (rules/R8, #326): `generation` where the suffix
holds one, and `credentials` beside it where the suffix holds both,
so a line with neither has a suffix of credentials only, or none, and
the `patronymic` and `surname2` views (rules/R9, rules/R10) where
each is not empty, which for `surname2` is never: only
`two_family_names` fills it, and the snapshot parses the default.
Empty values are left out,
so a reading that gains a field shows as one added key. The file's
first line is a header, `{"recorded": [...]}`, naming the keys added
after the snapshot existed that the recording tree could record: a
comparison leaves out a key either side did not record, decided by
that header and not by whether a row holds one, since a tree with
the field can read a set of names no report reaches.

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
both sides. A snapshot without the header records no alternatives, so
`--since v2.6.0` leaves them out the same way, and so does
`compare.py --baseline` against a release before 2.7, whose worker
says it has no `Ambiguity.alternative`: a name the tree reports one
for is not a name that moved (867 of the 1,088 entries `--baseline
2.6.0` reported on 2026-10-26 were only that).

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
names with the tree and prints the moves. From 2.0.0 on the 2.0
surface is compared; at 1.4.0, which has no 2.0 API, the release's
`HumanName` fields and initials against the tree's. Through 2.x the
tree side of a 1.4.0 run read the tree's own `HumanName`; since 3.0
removed it, the tree is read on `parse()`, and on 2026-10-28 that moved
the run's count from 1,751 to 1,749: the two `Ph. D.` names whose
initials the facade wrote `J. P D.`, where 1.4.0 and `parse()` both
write `J. P. D.`.
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
| `corpus_wikidata_native.jsonl` | Watch, Score | Wikidata, real public figures (deceased, or with at least 10 sitelinks) with a name written in their own script: Hangul, Han and kana, Arabic (Syria, Egypt, Saudi Arabia, Iran, and Urdu in Pakistan and India), Hebrew, Georgian, Armenian, Greek, Cyrillic beyond Russian (Serbia, Bulgaria, Ukraine, Kazakhstan), Bengali, Devanagari (Hindi, Marathi, Nepali) and Thai, 24 strata sampled by country and language. Each person's first P1559 or own-language label whose every word, or every character in unspaced text, aligns with exactly one stated part, via `build_wikidata_native_corpus.py` (2026-10-16; the Hindi stratum grown and the Marathi, Urdu and Nepali strata added 2026-10-23). CC0, credit in `wikidata_native_LICENSE` | everything the strict alignment drops, which in these scripts is most names: Arabic nasab chains (`بن` is no connective in Arabic script), `آل` family names and kunyas (most Arabic items state no family name), Chinese names whose given name has no item (most), Japanese names whose given-name item holds only a kana reading, and names whose parts are labelled only in Latin script (most Devanagari, Bengali, Urdu and Thai items, so those strata are 10–60 names: Hindi's whole population of 4,806 yields 147 in build order, Indian Urdu 12 of 3,000, on 2026-10-23); transcriptions with the 间隔号; Dari entirely; no titles, credentials or suffixes |
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

A local corpus holds real names that are not committed: fetched into the cache by `local_corpora.py`, read by `snapshot.py --local` and by a row of `tools/name_usage.py`, scored by `local_agreement.py` where its records carry their fields, and seen by no reviewer and no CI run (the SURVEY job in mechanisms.md#NAME-DATA-JOBS, and WATCH and SCORE outside CI). What reaches the repository is what a contributor cites from it, counts and shapes written with made-up names.

`local_corpora.py` holds the `SOURCES` registry, the cache's files, the views and the command line; each source's fetch is a module of its own (`local_ctgov.py`, `local_fec.py`, `local_tse.py`, `local_tw.py`, `local_ukec.py`, `local_govuk.py`, `local_psc.py`, `local_jrc.py`, `local_nepal.py`, `local_orcid.py`, `local_patentsview.py`, `local_volby.py`) whose docstring says what the source is and what its terms allow, built on the retry policy, share gate and downloads in `local_core.py`. A new source is a module and a `SOURCES` row. A source whose records hold a value its own code derives, rather than one the source gave (`jrc-names`' script label), stores a read version in `meta.json`'s detail and refuses on load a corpus read by another (`JRC_READ_VERSION`, bumped by hand with any change to how a record is built; `psc-individuals` does the same for its cached extracts, with `PSC_EXTRACT_VERSION` in each extract's file name): the sha256 checks prove the files are the ones fetched, not that today's code would write them. A constant such as `TSE_MAX_BAD` or `RETRIES` lives in one module, which every reader reads it through, so a test patches it there; no other module `from`-imports it, so a patch set elsewhere raises rather than missing the code (`test_no_module_imports_a_sibling_constant` holds this).

```
uv run python tools/differential/local_corpora.py fetch ctgov-officials
uv run python tools/differential/local_corpora.py tally ctgov-officials --top 50
uv run python tools/name_usage.py --no-wikidata MA FNP-C
uv run python tools/differential/local_agreement.py psc-individuals
```

To read what a branch moves, check it from the branch against the base checkout you name:

```
uv run python tools/differential/snapshot.py --local ctgov-officials --base ../master-checkout
uv run python tools/differential/local_agreement.py psc-individuals --base ../master-checkout
```

`--base` reads the base's readings from the baseline kept for its `nameparser/` (below), recording one in a child process where none is kept, and never reads or writes the shared `snapshot.jsonl` or `agreement.jsonl` beside the corpus. It prints which base it read, by path and digest prefix, and whether the reading was reused or recorded now, and then the head's digest, saying outright when the two packages are byte-identical and so no reading can move. It refuses a base that is the tree being read, or that holds no `nameparser` package, and the child refuses a package imported from anywhere but the base, as `--record --tree` does; a reused baseline was keyed by the base's files on disk, so it needs no import to vouch for it. `--sample N` composes with it. Use it whenever another session may be measuring: the shared snapshot is whoever recorded last, and on 2026-10-25 parallel sessions of #752's phase 2 read each other's re-records as their own moves, the worse case being silent, a sibling's record from a branch holding the same change reading as "no moves". The shared file still works for a session alone, recorded with the base and checked with the branch:

```
uv run python tools/differential/snapshot.py --local ctgov-officials --record --tree ../master-checkout
uv run python tools/differential/snapshot.py --local ctgov-officials
```

Any snapshot reading of 5,000 entries or more, committed or local, parses in a worker process per CPU, as do, past the same floor, `local_agreement.py`'s score and the `pairs --agreement`, `groups` and `alike` views (`--jobs N` to change that; all of them share `snapshot.parallel`, whose workers abort the run where one imported another `nameparser`),. Measured 2026-10-23 on a 12-CPU machine: a 20,000-name sample cost about 120 µs a name for the 2.0 parse and its renders; a check of `fec-individuals` (1,893,964 names) took 49s, and of `ctgov-officials` (352,104) 9.6s. A local recording is kept gzipped in `baselines/` beside the snapshot (41 MB for `fec-individuals` against 249 MB plain, 2026-10-23), under a key of the fetch, a hash of every file in the read tree's `nameparser/` as it is on disk (`__pycache__` aside), the interpreter's minor version and the code that writes a row (`snapshot.py`, `corpus_build.py`, `shapes.py`); recording that base again copies it rather than parsing. The hash is taken again after the read, and a package that changed meanwhile keeps no baseline; a kept baseline that cannot be read, or holds another number of rows than the corpus has entries, is deleted and the names are read. The ten most recently recorded or reused baselines are kept per source, whole and sampled alike, so a few `--sample` recordings can push out a whole one: room for four sessions measuring at once with a base and a head each (four were kept until 2026-10-25, and parallel sessions evicted each other's bases), about 420 MB for `fec-individuals`, whose baseline is the largest (41.7 MB). A snapshot recorded before 2026-10-23 may carry facade rows; a check against one sets them aside. `--sample N` reads a fixed 1-in-N sample, chosen by a hash of the name, into `snapshot.sample-N.jsonl`, for iterating on a change; a sample is never compared with a snapshot of the whole corpus or of another sample, and a count quoted from one says it is a sample.

`compare.py --corpus` takes the cached `corpus.jsonl` too, against a release.

| Source | What it is | Blind to |
|---|---|---|
| `ctgov-officials` | every overall official of every study on ClinicalTrials.gov, whatever the role (principal investigators, study directors and chairs, and a few sub-investigators and officials with no role), the name as the sponsor's staff typed it into a free-text field: credentials run together (`MBBS,FCPS`), job titles in the name, all-caps and all-lowercase names, typos. Fetched from API v2 (NLM) | names outside clinical research, which is mostly medicine and heavily credentialed; names nobody typed by hand |
| `fec-individuals` | the distinct names of every individual contributor in the FEC's bulk file for the 2026 cycle (`indiv26.zip`, downloaded once into the cache and read without unpacking; `fetch --refresh` downloads it again). Mostly a filer's software writing a form's fields in a fixed order: of its 1,893,964 names on 2026-10-18 every one was in capitals and 1,893,961 held a comma, with hand-typed text inside the fields -- 3,306 held a second comma, for a credential run or a suffix in a part of its own (`DOE, JR., JOHN`). The population for the one-case family-comma shape. The FEC's terms (52 U.S.C. 30111(a)(4)) bar using the names to solicit contributions or for any commercial purpose | case, since every name is in capitals; names written in their spoken order, or without a comma; small donors, since a committee need itemize only a donor whose gifts to it pass $200; names outside the US; names in any script but Latin |
| `tse-donors` | every individual donor to a candidate in Brazil's 2022 general and 2024 municipal elections (the TSE's candidates' accounts, rows from `Recursos de pessoas físicas`), a record per distinct pair of the name as the campaign filed it (`name`) and the federal tax registry's name for the same donor (`registry`): a typed form with its reference form beside it. Of 854,531 records fetched 2026-10-22 (848,351 distinct filed names), 205,925 differ from their registry name -- an agnomen dropped or abbreviated (`JR` filed for the registry's `JUNIOR` in 1,615, `JÚNIOR` for `JUNIOR` in 975), a word left out. Nearly all in capitals (845,498 filed names), in spoken order with no comma (184 records hold one), and full of particles and agnomens (`DE`, `DA`, `DOS`; `FILHO` ends 10,955 distinct filed names, `JUNIOR` 13,784, `NETO` 8,410). Published by the TSE under CC BY | case, mostly; the family-comma shape; credentials and titles, which a donation form has no place for; donors to parties rather than candidates; names outside Brazil; names in any script but Latin |
| `tw-donors` | the distinct names of every individual donor in every campaign finance report Taiwan's Control Yuan publishes on its political donation platform (ardata.cy.gov.tw, whose zips data.gov.tw also lists): 454 reports of 64 elections on 2026-10-22, presidential, legislative and local: every report from 2018's elections on, and the residual reports of 2014's and 2016's. Each report's zip is cached under the name the platform lists it by, which carries the date it was built, so a refresh downloads only the reports published or rebuilt since. Names as a candidate's staff typed them into a filing, published in full where the ID, address and phone beside them are masked. Of the 308,667 names dated 2026-10-05, 296,820 were three Han characters, 5,449 four and 5,260 two; the population for unspaced Han names written family first, and for the married double surname (冠夫姓) a four-character name often is. Under the Open Government Data License, version 1.0, with the platform's own bar on using the data for profit, credit investigation or another improper purpose | names in spoken order; Latin script (80 of the names dated 2026-10-05 held a Latin letter); the comma (3 of them held a fullwidth one, none an ASCII one); case; names outside Taiwan; donors whose names the report does not publish, such as anonymous gifts; Japanese kanji names, which the Han script cannot tell from Chinese |
| `ukec-individuals` | the distinct names of the individual donors in the UK Electoral Commission's register of donations (to parties, their members, third parties, permitted participants and regulated donees), from the search's CSV export under the site's own default filter, fetched whole on every fetch (9.5 MB on 2026-10-22, accepted dates from 2001 to 2026). The default leaves out donations reported only before a poll (`prePoll=false`: 374 rows and 21 names on 2026-10-22). A name as the donee's return gave it, mostly in its spoken order and mixed case, with the donor's title: of its 15,214 names on 2026-10-22, `parse()` read a title in 8,219 (its `title` field non-empty) (`Mr`, `Ms`, `Mrs`, `Lord`, `Dr`, `Sir`; 32 a run of two or more, `The Rt Hon`) and a suffix in 320 (`MP`, `OBE`, `CBE`, `QC`). The population for titled British names. The Commission publishes its documents under the Open Government Licence v3.0, but the register states no reuse terms of its own, which the credit line says | the family-comma shape (2 names hold a comma) and case (9 are in capitals); small donors, since a donation is reported only above a threshold that depends on the donee; names outside the UK; names in any script but Latin |
| `govuk-people` | the distinct display names of every person GOV.UK has a page for (ministers, senior civil servants, ambassadors, military chiefs, past prime ministers), from the site's search API filtered to the person format and ordered by title (seven pages on 2026-10-30): the department's own display form, as written, with the British title run in front and post-nominals behind (`The Rt Hon`, `Dr`, `Professor`, `Sir`, `Lord`, `Baroness`, `Dame`, ranks; `MP`, `KC`, `CBE`, `OBE`, `CMG`, `KCB`, degrees). Of its 6,021 names, held by 6,125 people, on 2026-10-30, `parse()` read a title in 1,293, a suffix in 1,261, and one or both in 2,093 (34.8%). The population for English titles, honorifics and post-nominals as an office writes them; small. Crown copyright under the Open Government Licence v3, which does not cover the personal data in it, so cached and never committed | case (one display name is a lone post-nominal in capitals); the family-comma shape (83 names hold a comma, a peerage written after the name or post-nominals after one); names outside UK government; names in any script but Latin |
| `psc-individuals` | the people with significant control of UK companies, and the beneficial owners of overseas entities, from Companies House's daily snapshot (33 zipped parts of JSON lines, 2.44 GB on 2026-10-22): each person's display name, the four boxes the filer typed it into (title, forename, middle name, surname) and the stated nationality, nothing else. A record is a distinct filed name, kept one in eight by a hash of the record (1,040,708 of 8,322,939 on 2026-10-22), a size the machinery can hold in memory. A local corpus whose names carry their fields, scored by `local_agreement.py`, as `orcid-researchers` is | names nobody filed into boxes, so almost no comma (838 of 1,040,708 on 2026-10-22), no credential run and almost no suffix; a display name that is not its boxes joined, which the fetch drops (2 of 14,025,738 individuals on 2026-10-22) |
| `orcid-researchers` | the public names of ORCID iD holders, researchers worldwide, from ORCID's Public Data File 2025 (`ORCID_2025_10_summaries.tar.gz`, 46.3 GB, data as of 2025-10-17), read as a stream and never stored: each line of its extract is the two boxes the holder typed their own name into (given names, family name), the credit name they publish under where public, other names, and a country, taken from their public address, else the first employment that names one, else the first education that does; a corpus record keeps the boxes, the credit name and the country. The fetch caches an extract of every summary with a public name (24,990,909 of 26,078,951 on 2026-10-27, 1,086,356 private and 1,686 empty), 369 MB, and the corpus keeps at most `ORCID_CAP` (20,000) records a country, the lowest by a hash of the record, so a change to the cap re-reads the extract rather than the 46 GB file: 1,831,533 records: 250 countries, 65 of them at the cap, and the records with no country (14,293,215 of the extract, 57%) as one more group of 20,000, counted in that total. A record's name is its boxes joined, given first; the credit name is a second corpus key (125,960 kept records hold one). Scored by `local_agreement.py` by country, the boxes as the holder split them. CC0, with ORCID asking for credit and respect for the privacy of the people in it | frequency, since the cap flattens every large country to 20,000; people outside research; name order, which ORCID does not record, so a holder who typed a family-first name into the given box reads as a disagreement; names with no family name and names whose family name is private, which look alike (1,308,200 of the extract hold no family name); titles, credentials and suffixes, which the form has no box for |
| `patentsview-inventors` | the inventor of every patent the USPTO granted from 1976 to 2025, from PatentsView's granted-patent tables on the USPTO Open Data Portal (release to 2025-12-31): each inventor's name in the filing's two boxes (first name, last name) and the country of the inventor's address. A record is a distinct name in a country, with the number of people who filed under it (`people`, counted by PatentsView's disambiguated inventor id, so a prolific inventor weighs once): 24,037,380 inventor rows, one per inventor per patent, held 5,319,206 such names on 2026-10-28, 99.3% of rows with a country. The extract keeps every name with its count, the corpus at most 20,000 names a country (657,991 records: 202 countries, 23 of them at the cap, and the records with no country as one more group of 20,000, counted in that total). Split by a professional filer, the applicant's attorney, rather than the bearer: `parse()` agreed with 94.7% of the records, 99.8% in Japan, 99.5% in China and 99.0% in the US, so it reads beside `orcid-researchers` as how a name is written against how its bearer types it. A comma stands in the last box of 92,503 of the extract's names, against 129 in the first, before suffixes and legal roles typed after a deceased inventor's name: the text after it is exactly `Jr.` in 55,459 names, `III` in 14,227, `deceased` in 4,635, `heir` in 514, `legal representative` in 393, `executrix` in 328 and `administrator` in 288 (2026-10-28). CC BY 4.0, credit PatentsView; the portal needs an API key | names in any script but Latin, since a filing is romanized; titles and credentials, which a filing has no place for; names outside patenting, which is mostly engineering and science, and its countries' shares are of patents filed in the US, not of their populations |
| `jrc-names` | the person entities of the EU Joint Research Centre's JRC-Names, each with the spellings of its name harvested from news text in many languages and scripts: a record is one distinct spelling, with its entity and its script. The file (`entities.gzip`, 14.8 MB) is pinned by sha256 and dated by its Last-Modified, 2024-03-15. Of its 1,317,586 spellings kept, 1,203,634 are Latin, 66,673 Cyrillic, 17,074 Arabic (7,833 persons, 5,347 of them spelled in Latin too), 13,039 Katakana and 8,016 Han, and 218,822 persons have two or more spellings, 25,415 of them in two scripts or more (a spelling whose letters are in two scripts, or none, not counted as one). The population for spelling and transliteration variants of one name, read by the `groups` view, and for Arabic-script names. Licensed under the JRC-Names EULA, personal and non-transferable, with no redistribution or derivative works, so its views' output and its snapshot stay in the cache like every local corpus's, and here the licence, not only the names being real people's, is why | titles and credentials, since the names are harvested from running text (`parse()` read a title in 3,011 of its 1,315,051 names and a suffix in 1,940, 2026-10-24); the ASCII comma, which none holds (1,510 Arabic spellings hold an Arabic comma, U+060C, which the parser reads as one); the Indic scripts (Devanagari 827 spellings, Bengali 419, the others fewer); people the news did not name |
| `nepal-candidates` | every candidate in Nepal's local elections of 2079 BS (2022), from the Election Commission's results site (result.election.gov.np), one file per local body: a record per distinct pair of the Commission's romanization (`name`, the one `parse()` reads) and the name in Devanagari as filed (`devanagari`). The corpus and the word index hold both, so a snapshot and a `name_usage.py` lookup read both scripts; `tally`, which counts what follows a comma, reads the romanized name. Of 126,981 pairs fetched 2026-10-24 (152,960 candidates in 753 files, 26 of whose romanizations were a placeholder such as `- - -` and are dropped), the romanized names carry surnames written as initials (`B.K.`, `K.C.`, `G.C.`), honorific words that are titles in front (`Guru`; `Shekh` until #752's phase 2j made it a title only in a title phrase) and `Md.`, Muhammad's abbreviation, which its period makes a title by shape; the Devanagari ones carry vowel signs and the virama, combining marks the letter-shape tests do not count as letters (decisions/nfd-shapes), and the joiners ZWJ and ZWNJ. The population for romanized South Asian names and for Devanagari. The site states no licence, which the credit line says | case and the comma, since the Commission's romanization is one consistent hand; names a person typed themselves; credentials and generational words; the parliament and provincial candidates, whose files carry Devanagari only; names outside Nepal |
| `cz-candidates` | every candidate on the registers the Czech Statistical Office (ČSÚ) publishes on volby.gov.cz for the 2022 municipal elections (`kv2022`) and the 2025 Chamber of Deputies election (`ps2025`): a record is a distinct candidate's four name boxes in one election, the title before the name (`TITULPRED`), the given names (`JMENO`), the surname (`PRIJMENI`) and the title after it (`TITULZA`), with the election; 165,736 records of kv2022's 197,506 candidates and 4,445 of ps2025's 4,475 on 2026-10-30. A record's name is COMPOSED, not written by anyone: the boxes joined in the Czech convention, `TITULPRED JMENO PRIJMENI, TITULZA` (`Ing. Jan Novák, Ph.D.`). 61,320 of its 170,181 records carry a title (58,667 before the name, 7,687 after it), nearly all academic degrees (`Ing.`, `Mgr.`, `Bc.`, `MUDr.`; `DiS.`, `Ph.D.`, `MBA`): the population for titles and post-nominals the filer kept apart from the name. Scored by `local_agreement.py` by election, under the default parser and under `--locale cs`. ČSÚ licenses it under CC BY 4.0, asking that derived data be marked as derived, which the composed names are and the credit line says | case, spacing and punctuation of a writer's own, since the string is composed; the family-comma shape; courtesy titles and offices; names outside Czechia; the elections not in `VOLBY_ELECTIONS` (the index lists kv2002 to kv2026 and ps2002 to ps2025) |

A live source has no fixed snapshot to pin, so the cached copy is the pin: `meta.json` holds the source's data date and the sha256 of `raw.jsonl` and `corpus.jsonl`, checked on every load, and every report, the `name_usage.py` row included, carries the source and that date. Quote a count with the date, and expect a later fetch to differ. A local snapshot records which fetch it was read from, and `snapshot.py --local` refuses to compare it with a corpus fetched since, which would report the names the source gained and lost as moves: after a `fetch --refresh`, record again from the base checkout. ClinicalTrials.gov's terms ask anyone redistributing its data to credit it, show NLM's processing date and say what was changed; keeping the names in the cache and citing counts with that header meets them. The FEC's bar on soliciting and commercial use is in the credit line of every `fec-individuals` report, so a count quoted from it carries the bar with it. A record there is a distinct name, not a contribution or a contributor: one donor gives many times (34,264,742 rows held 1,893,964 names in the file dated 2026-10-18), and counting contributions would weight a shape by how often its bearers give. `tools/name_usage.py` looks a word up in each corpus's word index, cached as `wordindex.json` beside it on first use and keyed to the records' sha256, to the code that cuts and folds a word and to the record keys it reads (`Source.corpus_keys`; a record whose two names write one word counts once), so a refetch, a change to the fold or a change to which of a record's names are read rebuilds it; a single-word lookup it answers parses neither the records nor the names. Measured 2026-10-22 with both corpora fetched, a single-word `name_usage.py --no-wikidata` run took 2.5s with their indexes cached (12.5s before the cache, 14.8s on the run that builds it). A spaced word (`Ph. D.`) still scans every name, which took 8.6s, nearly all of it the FEC corpus's. For `orcid-researchers` and `patentsview-inventors`, whose extracts keep every record's boxes and country uncapped, `name_usage.py --boxes` adds a row by box and country, read from a second index, `boxindex.json.gz` beside the corpus (`cached_box_index`): per word and country the people whose given box or family box writes it, each country shown as a share of its people, so a word can be weighed in the country a language pack is for (`--country CC`). It is keyed to the extract's sha256, taken from the bytes as they are read, and to a fingerprint of the reader and the fold, so a refetch rebuilds it. Building it took 2 min 19 s for ORCID's 24,990,909 records (3,780,309 words in 6,660,756 word-and-country cells, 41 MB cached) on 2026-10-28. With both indexes cached a lookup took 10.4 s with `--boxes` against 5.3 s without, the difference nearly all reading the two indexes (the 369 MB extract hashes in a fraction of a second once the system has it cached), which is why the rows are asked for rather than always built; an extract that cannot be read fails its own row, naming the refresh. `fetch --refresh` re-downloads the FEC's zip rather than re-reading the cached one, replacing it only once the new one is whole, and a corpus fetched for another cycle than `FEC_CYCLE` is refused on load. The `fec-individuals` fetch refuses a file whose lines stop matching the 21 columns it reads, or whose names stop holding a comma, rather than read it as a smaller or a different corpus. A `ukec-individuals` record is a distinct name too, not a donation or a `DonorId`: one name often holds several IDs, which seem to come with reports rather than with people (15,214 names held 24,473 on 2026-10-22, the IDs counted in `meta.json`'s detail; 2,663 names held several at one `RegulatedEntityId` alone, counted from the export and not kept, though some of those may be two people of one name), so a count of IDs would weight a name by how often it was reported. Its fetch reads the register's total from the JSON search under the same filter before and after the export, and refuses an export holding another number of rows, or a register that changed in between: the export ignores `rows=`, so the total is what tells a cut or capped export from the whole register. It refuses an export whose last row is cut short (Python's `csv` returns a body cut inside a row as a short last row, which the row count would otherwise take for a whole one), and a header other than the 29 columns `UKEC_COLUMNS` names, and counts into `meta.json`'s detail the rows it skips: rows not 29 fields, rows from a donor that is not an individual (the filter asks the server to leave those out), and individuals with no name. Past `UKEC_MAX_BAD` of either of the first two, or `UKEC_MAX_NAMELESS` of the third (4 of 42,355 rows were nameless on 2026-10-22), it refuses the export. The data date is when the first search answered, in UTC: the register states no date of its own, so the counts above, dated by the day they were fetched (2026-10-22), carry the data date 2026-10-23T03:13:19Z in their header. `tw-donors` keeps one zip per report under `reports/`, whole, its masked ID, address and phone columns included, as the FEC's zip is kept: the platform's download answers a report that does not exist and a fault alike, with a 500 and an incident number, so the fetch reads which reports exist from the platform's listing and refuses a listed report it cannot download. It reads each file's columns by name, since a 2020 report lacks a column the newest ones write, and refuses a column it does not know, a category it does not know, a row whose serial column names another report (the zip is not the one asked for), a listing that changes during the fetch, and a report past `TW_MAX_REPORT_BAD` of whose rows it reads past. It reads back the rows a stray quote took into one field (169 rows in 12 records of three reports on 2026-10-22, 8 of them two rows joined by two stray quotes), counts donor cells that hold no name (匿名, a dash) or a masked one, and caches a downloaded zip only once its rows are read, so a refused zip is asked for again. A zip the platform rebuilt under the name it had is not seen: delete `reports/` to download every report again. A layout check written from one surveyed file meets every other file only at fetch time: `tw-donors`' first three fetches were each refused partway, by a report with no income writing one row of dashes, by a 2020 report with 24 columns where the surveyed one had 25, and by a row with no category. Each refusal cost every download again until the source cached its zips, so a new source that downloads many files caches each one before its checks run. `tse-donors` caches nothing but the corpus: each election's national member (`receitas_candidatos_<year>_BRASIL.csv`) is read from the TSE's CDN in HTTP Range requests, 209 MB for the two elections where their zips are 1.82 GB (2026-10-22), because the TSE regenerates the zips every few days and a cached one would be stale within the week. Every range request carries `If-Range` with the ETag the HEAD gave if it is strong, else its `Last-Modified`, and every part must state the `Content-Range` asked for, so a zip replaced during the read is refused rather than read across two versions; a HEAD that states no length, neither a strong ETag nor a `Last-Modified`, or `Accept-Ranges` other than `bytes` is refused before the read. A fetch took 69s on 2026-10-22. It refuses a zip without the national member, a header that is not 60 columns or lacks its three columns, a `DS_ORIGEM_RECEITA` value it does not know (a renamed category, or the file no longer in Latin-1), malformed rows or lines folded into a field past `TSE_MAX_BAD`, an election with too few rows from individuals (`TSE_MIN_INDIVIDUALS`: a member cut to its header, or the donations moved under another category) too many without a name or registry name (`TSE_MAX_MISSING`, counting a placeholder such as `#NULO` or `***` as none: a masked column) or with a number in one (`TSE_MAX_NUMBERED`: a numeric column moved under a name), too few distinct filed or registry names (`TSE_MIN_DISTINCT`: a column masked with one word), and a corpus fetched for other elections than `TSE_ELECTIONS`. The CPF in each row is unmasked in the file, and like every other column it is read past, never stored or printed; a pair either of whose names holds more than `TSE_MAX_DIGITS` digits is dropped and counted, since campaigns sometimes typed a number, a CPF among them, into the name field. A record is a pair, so the counts in its reports (`tally`, the `name_usage.py` row) are of pairs, and a filed name standing beside two registry names counts twice.

A `govuk-people` record is a distinct name, as a `ukec-individuals` one is, and the people behind it are counted into `meta.json`'s detail (99 names were held by two people or more on 2026-10-30). Every page of the search states its total, and the fetch refuses a page stating another total than the first (a person added or removed during the fetch), a person paged twice (by the page's path, which is read to tell two people of one name apart and then dropped), and a set paged short of the total, an empty page before it among them, so a short page cannot read as a smaller corpus. Paged without an order the search returned one person twice and another not at all across its 6,125 results (2026-10-30), which is why the fetch asks for `order=title`. Results of another document type, which the filter asks the search to leave out, and results with no title, are counted and skipped, and past `GOVUK_MAX_BAD` (1 in 1,000; none of 6,125 was either on 2026-10-30) of either refuse the fetch. The search states no date of its own, so the data date is when the fetch began, in UTC: the counts above, dated by the day they were fetched (2026-10-30), carry the data date 2026-10-31T01:49:34Z in their header. GOV.UK's terms (https://www.gov.uk/help/terms-conditions, last updated 3 September 2024, read 2026-10-30) say "Most content on GOV.UK is subject to Crown copyright protection and is published under the Open Government Licence ( OGL ), which also sets out which content is exempt", and the OGL v3 (https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/, read 2026-10-30) that it "does not cover: personal data in the Information": the caution the name-sources survey of 2026-10-27 recorded for the UK Parliament's MNIS, and why the names stay in the cache. A fetch took 1.7s on 2026-10-30, a second fetch that day giving the same corpus, and recording its snapshot under a second.

`psc-individuals` caches an extract of each of the snapshot's 33 parts rather than the zips: 168 MB against 2.44 GB on 2026-10-22, each extract holding only the records and fields the corpus keeps. A download that fails costs one part, and running the fetch again resumes, keeping the parts already read for the same day; the set replaces the cached one only once every part is read, and a part that disappears mid-fetch (the files are overwritten each morning) is refused naming the refresh. The fetch refuses a snapshot where more than one individual in 10,000 has no `name_elements`, or a display name that is not its four boxes joined by spaces, or where fewer than half of the lines are individuals (87% were on 2026-10-22; a kind Companies House renamed would read as another kind), and counts what it skips into `meta.json`'s detail. It reads the cached extracts only as one whole snapshot of one date, and an extract written by another version of the extraction (its file name carries the version) is neither resumed from nor read. Companies House's data-products guidance says it imposes no rules on how the register is used and leaves data protection to the user; the dataset's data.gov.uk entry gives its licence as "TBD", and gov.uk's footer licenses its own page text under the Open Government Licence. The credit line says the names are personal data.

`orcid-researchers` streams the summaries file in HTTP Range requests through `gzip` and `tarfile`'s stream mode, and keeps nothing of it but the extract: a dropped connection reopens at the byte it reached, with `ORCID_RETRIES` attempts at each read (243 s of waits, about four minutes of outage before each attempt's own 60 s timeout, where the other sources' few attempts suit a small request), every part must be a 206 with the `Content-Range` asked for and the `Last-Modified` the first answer gave (a first answer stating none is refused), and once the tar ends the rest of the gzip is read so its CRC is checked, then the whole body's length and MD5 against the figshare listing's (`ORCID_SIZE`, `ORCID_MD5`). The extract replaces the cached one only after that check and after the fetch has read it back through every check a load makes, so a fetch refused at the end keeps the last good one; reading it back took 2 min 23 s on 2026-10-27. The first draft checked its shares only on load, after the rename, where a file past them would have replaced a good extract with one every load refused (found in review, 2026-10-27): a check a fetch's output must pass belongs before the rename, not only on the read. A fetch took 78 minutes on 2026-10-27, about 10 MB/s, with the XML parsed by a worker per CPU. Its summaries are parsed with `xml.etree` and a summary declaring a DTD or an entity is refused and counted, rather than adding a dependency for a safer parser; the fetch refuses past `ORCID_MAX_BAD` of summaries that do not parse or are refused that way, of tar members that are not summaries, or of countries that are not two capital letters (none of the four on 2026-10-27), and below the `ORCID_MIN_` shares of summaries giving a record, of records holding a family name and of records holding a country (95.8%, 94.8% and 42.8% on 2026-10-27), which catch a release whose layout moved under the reader once the pin moves. The count of summaries is pinned too (`ORCID_SUMMARIES`): `tarfile` ends a stream at a damaged header without raising, so a tar read only in part would pass its MD5. The extract is cut at `"\n"` only (`newline="\n"`), as `corpus_build.jsonl_lines` cuts, and streamed rather than read whole. `tarfile` keeps every member it has read in `TarFile.members`, even reading a stream, so the reader clears it after each one: before it did, the fetch held 2.3 GB a GiB into the file. An extract written by another version of the extraction is not read (`ORCID_EXTRACT_VERSION`, in its file name). Of the extract's records, the country came from the address in 2,842,439, an employment in 7,025,517 and an education in 829,738 (2026-10-27): a country is where a holder works more often than where they come from, so read a country's agreement as its institutions' population, not its nationals'.

`patentsview-inventors` is the one source whose fetch needs a credential: the USPTO Open Data Portal has needed a sign-in for every download since 2026-06-18, and its API answers a request without an API key with a 401 (2026-10-28); a key needs a USPTO.gov account verified through ID.me (data.uspto.gov, My ODP). The fetch reads it from `~/.config/nameparser-tools/uspto-odp-key` (`PV_KEY`), sends it as `X-API-KEY` to https uspto.gov hosts only, and drops it on a redirect anywhere else; a fetch without it is refused naming how to get one, and no test needs it. The portal lists each file's size and date but no checksum, so the release is pinned by those and by the sha256 of the bytes downloaded on 2026-10-28 (`PV_FILES`), and by the rows its inventor tables hold (`PV_ROWS`): every field of the TSVs is quoted, so a stray quote cannot fold rows together, and a count short of the pin is a table read in part. The raw inventor table gives the names as filed and the disambiguated one, row for row the same inventors, the inventor id and location; the reader takes them in step and refuses a pair of rows naming different inventor slots rather than join them. The fetch refuses past `PV_MAX_BAD` of rows not their header's width and below the `PV_MIN_` shares of rows naming a country and filling both boxes, and reads the extract back through every check a load makes before it replaces the cached one; the zips are deleted once it is built, and a run that fails keeps those already whole, so the next downloads only the rest. A download dropped mid-file is tried again from the start under the shared retry policy, and a key the portal refuses (401 or 403) is reported as the key's, naming how to replace it. A fetch took about five minutes on 2026-10-28, the three zips (1.75 GB) downloading in under one; the extract is 60 MB. The disambiguated table's attributed gender is read past.

`nepal-candidates` reads each local body's file through the site's own JSON handler, which asks for the site's double-submit check: the `CsrfToken` cookie a GET of the site sets, echoed in an `X-CSRF-Token` header, with the `Referer` its pages send. The site refuses a User-Agent holding `python` or `curl` with a 403 (2026-10-24), so this source sends a browser's form naming the tool (`NEPAL_USER_AGENT`) where the others send the repository's URL. A 403 mid-fetch is what a lapsed token gets, and renews the session once before it is raised; a 404 counts the file as missing, its id kept in `meta.json`'s detail, and with the empty files (a list of no candidates, as a site that blanked its files would answer) past `NEPAL_MAX_MISSING` of the `NEPAL_BODIES` bodies refuses the fetch, the empty ones' ids kept too. The election is over and its files final, so the candidates are pinned as the bodies are: a fetch reading every file must read exactly `NEPAL_CANDIDATES`, so a site that trimmed its files (to the winners, or to one post) is refused however well formed what is left; with files missing or empty the pin cannot be exact, and a shortfall of up to `NEPAL_MAX_SHORT` of it is accepted, so a few candidates trimmed elsewhere are not seen then. Every listed file answered on 2026-10-24: the 18 a survey on 2026-10-23 saw refused, among them ids 5551 to 5554, answered when asked again. A file is JSON, so a body cut short does not parse, and is retried as one cut in transit rather than read as a body with fewer candidates. The fetch refuses a lookup listing other than `NEPAL_BODIES` bodies (the election is over, so its files are final), a file that is not a list of candidates, too many candidates with no romanized or no Devanagari name (`NEPAL_MAX_NAMELESS`) or with a name in the wrong script (`NEPAL_MAX_WRONG_SCRIPT`: two columns swapped, or a romanization dropped), and too few distinct names in either column (`NEPAL_MIN_DISTINCT`). A record is a distinct pair, as `tse-donors`' are, not a candidate row: a body lists a candidate once per post, and a common name recurs across bodies. The `pairs` view refuses it, its records carrying no reference name: that view compares the letters of two spellings, and a romanization shares none with its Devanagari, so the Devanagari is kept under a key of its own. `meta.json` records the keys the corpus was built from (`corpus_keys`), and a corpus written under other keys is refused on load. A fetch took 28 minutes on 2026-10-24 at `NEPAL_DELAY` (0.3 s) a request.

`cz-candidates` reads each election's index page (`https://volby.gov.cz/opendata/<election>/<election>_opendata.htm`) for the register's CSV zip, whose file name carries a date stamp (`KV2022reg20260328_csv.zip`, `KV2018_reg_20230224_csv.zip`): a guessed stamp answers an HTML 404 page, so the stamp is read off the page, the newest where it links several (ps2021's links a revision), and an answer that is not a zip is retried as a body cut short, then refused. It reads the UTF-8 copy in `csv_od/` (the zip's `csv/` holds one in windows-1250) by column name, since the registers' other columns differ by election, and refuses a register missing a box's column, one whose last row is cut short (the CSV gotcha in AGENTS.md), one holding another number of candidates than `VOLBY_ELECTIONS` pins (a register is not final when its election is held: kv2022's carries the by-elections held through 2024 and was re-issued with a stamp of 2026-03-28, so the pin, not the election's date, is what refuses a changed register), past `VOLBY_MAX_BAD` of rows not the header's width or with no given name or surname, and under `VOLBY_MIN_TITLED` of candidates titled (a title column emptied or moved). A box is kept with its runs of spaces read as one, and a comma typed inside a box before the last (`Dopitová, roz. Lišková` in the surname box, `Ing., Bc.` in the title box: 21 records on 2026-10-30) is kept as filed and counted in `meta.json`'s detail (`records_with_a_comma_inside_a_box`), an accepted cost: the composed name then holds a comma shape nobody wrote, but the score reads the boxes, which say what was meant; the age, occupation, municipality and party columns are read past, and nothing is cached but the corpus. A record is a distinct set of boxes in one election, so a candidate who stood twice in one election under the same boxes, or two people who share them, is one record, which is why the corpus counts records, not candidates: 31,770 of kv2022's rows fold into another. Adding an election is a row in `VOLBY_ELECTIONS`, measured first. `meta.json` holds the elections and `VOLBY_READ_VERSION`, the version of `compose`, and a corpus of other elections, or composed by another version, is refused on load. The data date names each register's stamp. A fetch took 25s on 2026-10-30 (13 MB of zips), and a score 3.4s with a worker per CPU.

Its score reads the title before the name against `TITULPRED`, the given and middle names against `JMENO`, the family against `PRIJMENI` and the suffix against `TITULZA`. It is the one source with a box after the name, so no suffix is compared inside the surname box, and the one that sets nothing aside: its title box holds the degrees the law asks filed there, and the default vocabulary lists few of them (`Bc.` and `Ing.` read as titles by their shape alone, rules/H2), so the set-aside took 1,059 records on 2026-10-30, each the parser's own miss (`Bc. Jan Novák, DiS.` read with the title `Bc. DiS.`; the split by box is in `Fielded`'s docstring). On that fetch every field agreed for 96.96% of the 170,181 records under the default and 96.97% under `cs`, 92.9% and 93.0% of the 61,320 titled ones; the box before the name agreed for 97.7% of the 58,667 filled, the box after it for 56.0% of the 7,687 filled, and the family for 99.0% of all. The misses are, by far, `DiS.` (a diploma written after the name): of the 3,248 records whose box after the name holds it (`re.search(r"\bdis\b", box.replace(".", "").casefold())`), that box disagrees in 3,240, 3,232 of them because the parse reads `DiS.` as a title (its title holding `dis` by the same test) and 8 because it reads the whole name before the comma as the family (`DiS. et DiS.` six times), and a two-word surname read as a middle name and the family, 1,483 under the default and 1,315 under `cs` (with `Policy(two_family_names=True)` the family box's misses fell from 1,683 to 825 under the default and 986 under `cs`, and the given box's from 1,828 and 1,644 to 743 and 732); then a connective between two titles the shape alone reads (`Ing. et Ing.`, `Bc. et Bc.`) read as given names, 164 and 153, where `Mgr. et Mgr.`, whose `Mgr.` is listed, reads as a title in 218 of 223. Under `cs` a generational word typed into the surname box (`Novák ml.`, 177; `st.`, 57) reads as the suffix it is, which the score counts against the empty box after the name: there the box, not the parse, is out of place.

`local_agreement.py` does the SCORE job for a local corpus. It parses each filed display name and compares the parser's roles with the boxes the source states (title, given, middle and family for `psc-individuals`; given and middle joined against the given-names box, then family, for `orcid-researchers`; title, given and middle joined, family and suffix for `cz-candidates`), folding case, periods, commas and spacing. Where the source has no box after the name, a suffix the parser peels is compared inside the surname box: the display name joins the surname last, so a trailing suffix was typed into it whenever it is filled, with or without a comma (`Smith, Jr.`); the fold read the comma as a miss until 2026-10-28, which moved 83 `psc-individuals` records and 561 `orcid-researchers` records to agreeing and none away. Where a source has a title box, and save `cz-candidates` (above), a title the parser reads otherwise, holding a word the vocabulary lists as neither a title nor a connective (a job typed as a title), is set aside as filer error rather than scored, and the report lists the commonest such titles as leads for the vocabulary. The report gives agreement overall and by the group the source states (nationality, country), misses per field, and the commonest disagreement shapes, as counts, word counts and the commonest set-aside titles; `--list N` prints moved records, names and all, for reading locally. Its record, `agreement.jsonl` beside the corpus, holds every record that did not wholly agree, so a re-run reports what moved. As with the local snapshot, check it from the branch against a base you name (`--base <checkout>`, whose record is kept under `agreements/` beside the corpus, keyed by the fetch, the base's `nameparser/` files, the interpreter's minor version and the scorer, the ten most recent kept; the scorer's fingerprint reads only its own source's `FIELDED` entry, so adding a source leaves the others' records standing, which the whole table, hashed until `patentsview-inventors` was added on 2026-10-28, did not), or, alone, record the shared one from the base checkout (`--record --tree <checkout>`) and run it from the branch; it refuses a record from another fetch, or one written by another version of the scorer, whose own change would otherwise read as the parser's moves. `--locale cs` scores the parser of a locale pack, `parser_for(locales.CS)`, against a record of its own (`agreement.cs.jsonl`, and kept records keyed by the locale too), so a pack's score and the default's never stand for each other; `measure.py` runs the default's alone. No CI run sees it.

`pairs` reads a paired source (`tse-donors`, whose records carry the registry's name beside the filed one) as two spellings of one person, and sorts each pair by how the filed name departs from the reference: the first of its shapes that fits, from case, accents (case unchanged) and case and accents together, through words left out, shortened or misspelled, to few words in common. A word left out or added counts once per pair, and is listed only when ten pairs share it. `--agreement` also parses both spellings of every pair with a reference name that differs, and counts the pairs whose two readings end the family name in the same word (two readings with no family name share none). It lists the accents-only pairs read with two surnames by the two spellings' last words, the same ten-pair floor applied.

```
uv run python tools/differential/local_corpora.py pairs tse-donors --agreement
```

On the fetch of 2026-10-22, 205,925 of `tse-donors`' 854,531 pairs differ. The commonest shapes: words left out (22.0%: `DE` left out of 13,412 pairs, `DA` 5,906, `DOS` 3,033, then second surnames, `SILVA` 2,869), accents only (21.1%; 255 of them SÁ / SA pairs read with two surnames until #857), words shortened (15.8%), words misspelled (14.9%) and words left out and shortened (11.8%). Read the agreement per shape, since a shape can change the surname legitimately: a pair that leaves out the last surname ends the family in another word, which is likely most of why only 44% of words left out agree (not measured apart from the other causes). Accents only cannot change the surname, so its 1,304 of 43,552 pairs that disagree are the parser reading one name two ways: by their last words, `JÚNIOR` against `JUNIOR` in 866 (#843) and `SÁ` against `SA` in 255, where `MARIA DE SA` reads `SA` as a credential and `MARIA DE SÁ` as the surname. The run took 39s in one process (15.8s in workers, 2026-10-27).

`jrc-names` reads a gzip downloaded once into the cache, and refuses one whose sha256 is not `JRC_SHA256`: the JRC says the resource is updated daily, but the file served on 2026-10-24 was last modified on 2024-03-15, so a new file is measured and the pin moved by hand rather than read under constants measured on another. A download that is not the pinned file replaces nothing: it is kept beside the cached one as `entities.gzip.new`, to be measured, and adopted without another download once the pin moves to it, since the JRC serves only its current file and the pinned one could not be fetched again. For the same reason `fetch --refresh` downloads only where the cached file is not the pinned one; otherwise it reads the cached file again. `meta.json` records the pin, `JRC_READ_VERSION` and the Unicode version `script()` read, and a corpus fetched under another of any is refused on load, so a change to how a spelling is read or its script labelled is not counted under the old records. It keeps the person rows (`P`, 1,338,463 of 1,445,013 lines) and reads past the organisations (`O`). It drops every row the JRC marks with a language (`ru`, `ar`, `sl`, `et`, `pl` and others, 20,819 of the person rows), counted by language in `meta.json`'s detail, on the JRC's marking alone. Where measured, a marked row is a morphological variant of a spelling the JRC leaves unmarked (`u`): an inflected form, or an Arabic spelling with و, ل or ال glued on. Every marked row's entity held an unmarked spelling, and 18,594 of the 20,819 had as many words as one and differed from it only in endings or in glued fronts of three letters or fewer (the rule is stated exactly at `JRC_UNMARKED` in `local_jrc.py`); the other 2,225, 1,680 of them Arabic, fit neither as stated and were not measured further. The unmarked spellings still hold inflected forms the JRC did not mark (by the same rule, 22,732 of the 66,673 distinct unmarked Cyrillic spellings are another Cyrillic spelling of the same person), which are kept. A name's `+` and whitespace are read as single spaces, and an id is kept as written. A line that is not four well-formed columns (the file's first line, `#`, is one) is counted, and past `JRC_MAX_BAD` refuses the file, as do a gzip cut short, a file ending inside a line, person rows under `JRC_MIN_PERSONS` of the lines (a type renamed), more marked rows than `JRC_MAX_MARKED` (a file that marks every spelling), more persons left with only marked spellings than `JRC_MAX_LOST` (none were), and more repeated spellings than `JRC_MAX_REPEATED` (58 were). 99 spellings hold a replacement character (U+FFFD), damage in the source; they are kept and counted. The licence bars redistributing the resource or anything derived from it, so its snapshot, its views' output and every file derived from it stay in the cache, and what is cited from it is counts and shapes written with made-up names. A snapshot of it (`snapshot.py --local jrc-names`) recorded 1,315,051 names in 30s on 12 CPUs (2026-10-24, 128 MB).

`groups` reads a source whose records carry an entity and a script (`jrc-names`) as several spellings of one person. It parses every spelling of each person with two or more and compares the readings' structure: whether a title, a suffix, a given name and a family name are read, how many words the family is, and where it stands among the given, middle and family words (one run at the front or the end, all of them, none, or otherwise, which 1 of the 1,315,051 distinct spellings is). Words are not compared, so spellings in two scripts can be; but where the family stands moves with a script's order, so a script read family first (Hangul, spaced Han) differs from one read given first in that field by convention, not by error. It counts PERSONS, not pairs, so a person spelled 600 ways weighs what one spelled twice does. A pair of scripts is one row, and a spelling whose letters are in two scripts keys one as `mixed`: within one script (`Latin / Latin`) a field differs where the person's spellings in it read it more than one way, and they read alike where all read one way; across two (`Cyrillic / Latin`) a field differs where no spelling in one reads it as any in the other does, so two Latin spellings that differ between themselves are not counted against the Cyrillic one, and they read alike where some spelling in one reads, in every field, as some spelling in the other. A person across two scripts can be neither: every field has a value in common, yet no one spelling matches; the report counts those as `no one field` (0.4% of Han / Latin, less elsewhere), so each pair's persons are alike, apart in a field, or there. It then lists the title and suffix words of the persons some of whose spellings read one and others none (two spellings with two different titles and no untitled one add nothing), by the persons sharing a word, ten at least: the lead is a word the vocabulary reads as a title or suffix that is a name in some spelling, or a title spelled in a way it does not know.

```
uv run python tools/differential/local_corpora.py groups jrc-names
```

On the fetch of 2026-10-24 (data dated 2024-03-15), 93.7% of the 218,822 persons with two or more spellings read alike in every spelling, and the run took 50s (11.8s in workers, 2026-10-27). Within a script the disagreement is mostly the writing, not the parse. Katakana / Katakana reads alike for 0.2% of its 4,289 persons because the JRC writes a transliterated name three ways: unspaced and undivided, which the parser cannot divide and reads as a given name alone (4,347 of the 13,039 Katakana spellings), divided by `・` with no space (4,337), and spaced (4,355), the last two read given then family. Han / Han, 2.2% of 2,420, holds unspaced Han, read as one family word, beside spaced Han, read family first, and Han divided by `·`, read in its written order. Arabic / Arabic reads alike for 67.8% of 3,329 persons, and the Arabic comma is most of why: each of the 736 persons with a spelling holding one differs, of the 1,072 that differ, since the comma moves the family to the front. Across scripts read in the same order most persons read alike (Cyrillic / Latin 99.3% of 20,837, Arabic / Latin 98.2% of 5,347, Greek / Latin 98.6% of 915); Hangul against a script read given first reads alike for 3% or fewer in every such row `--top 40` lists (Hangul / Latin 2.0% of 1,247), its family standing first, while Han / Hangul, both read family first, is 87.1% of 1,002. The title words read in some spellings only start `sheikh` 50, `bard` 33, `shaikh` 27, `sir` 23, `executive` 22 and include `mahdi` 17, a common given name; the suffix words `jr` 62, `sa` 38, `iii` 27, `ii` 27.

`alike` reads the spelling views as one flag per person, for a source whose records pair spellings (`ALIKE_SOURCES`: `jrc-names`' persons, `nepal-candidates`' romanized and Devanagari pairs, `tse-donors`' filed and registry pairs): whether the person's spellings read alike, as `groups` compares them for a person, the two readings' structure for a Nepali pair, and one shared family last word, as `pairs --agreement` counts it, for a filed pair that differs. With `--base` it prints how many persons (`jrc-names`) or pairs now read alike and how many now apart, the counts phase 2j quoted for each batch. It counts flips only: a person whose spellings all read differently and still alike is no move here, though the local snapshot shows it. The base's flags are kept under `alike/` beside the corpus, keyed like the baselines (the fetch, the base's `nameparser/` files, the interpreter's minor version, and the view's code, `alike_fingerprint`), read in a child process where none is kept, and published under their key only once whole and once the base's digest, taken again, is unchanged. A key holds no name: a person is its entity or its record's place in `raw.jsonl`. With `--languages ne` it reads the tree under that choice of languages (`Locale.languages`) and counts the persons or pairs the choice moves against the default's flags, the tree's own or `--base`'s, as `snapshot.py --languages` does for the names: the pair measure a language pack reads. Both read the choice alone, never a registered pack's lexicon fragment or policy patch, which is the whole of a pack only where the pack is nothing but its choice, as `locales.NE` is, the RFC's "Measuring a pack" (`locales.NE`, 2026-10-30: 211 nepal-candidates pairs now alike, 4 now apart).

```
uv run python tools/differential/local_corpora.py alike jrc-names --base ../master-checkout
```

Measured 2026-10-27 on a 12-CPU machine (load average 3 to 15 from other sessions), each the same output before and after: `local_agreement.py psc-individuals --record` took 88.9s in one process and 15.4s with a worker per CPU; `groups jrc-names` 55.6s and 11.8s; `pairs tse-donors --agreement` 52.1s with `--jobs 1` and 15.8s. A kept `alike` base for `nepal-candidates` was read in 6.8s, and reused in 3.4s.

## Measuring a change

`measure.py --base <checkout>` runs every corpus check of a change, one after another, each but `cldr_agreement.py` parallel inside itself, and writes one summary:

```
uv run python tools/differential/measure.py --base ../master-checkout
```

The steps: the committed snapshot (`snapshot.py`, the check `tests/v2/test_snapshot.py` makes), `cldr_agreement.py`, `snapshot.py --local --base` for every fetched local corpus, `local_agreement.py SOURCE --base` for every fetched source whose records carry their fields (`psc-individuals`, `orcid-researchers`, `patentsview-inventors`, `cz-candidates`), and `local_corpora.py alike --base` for every fetched source that pairs spellings. Only the local steps read `--base`: the first two compare the tree with the records committed on its branch, so on a branch that has re-recorded `snapshot.jsonl` the committed snapshot says no moves and the moves are in the PR's diff of that file, and the summary labels each step with what it compared against. A local corpus that is not fetched gets no step, the summary names it, and a run in which no step read `--base` exits 1. Each step's whole output goes to a file of its own under `--out`, by default a folder named for the time under the cache's `measure/`, outside the repository, since a local snapshot lists its moves by name. The summary, `summary.txt` beside them and printed, gives each step's status (no moves, moves, or failed with its exit code), its time, and its unindented lines (the first few and the last, where the verdicts are, up to `SUMMARY_LINES`, and any line saying part of a check was not measured), never the indented ones where the tools list names; a crash's traceback is indented below a line naming only its type, since its message may hold a name. A step that fails makes the run exit 1; one that finds moves does not. Each tool refuses with `SystemExit("message")`, which exits 1 as a move does, so measure runs every step through its own `--step` wrapper, which turns a message exit or an uncaught exception into exit 2: a refused base or a damaged corpus is reported as a failure, never as moves.

For a vocabulary word whose reading acts on a name position, `tools/vocab/word_report.py` gives the per-word view before and alongside this: the word in a grid of shapes, its incidence in every fetched local corpus, and its `name_usage.py` rows (`nameparser/vocab/README.md`, "Adding a word").

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
`HumanName(...)`'s first argument at a `--ref`, or in the working tree
as `parse(...)`'s and its test helpers' since 3.0 ported the suite, plus string members of list/dict/
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

A second view measures the locale packs (#672). `LOCALE_FILES` in `cldr_agreement.py` maps each CLDR file to the pack for its language (`zh`, `zh_Hant`, `yue`, `yue_Hans` → `ZH`; `ja` → `JA`; `ne` → `NE`; `ru` → `RU`; `tr`, `az` → `TR_AZ`); those renderings are parsed with `parser_for(pack)`, over the same `FAMILY_FIRST` base where CLDR's order is surnameFirst, and their disagreements go to `cldr_agreement_locales.json`, ratcheted per pack by the same test. The native-script Wikidata source's strata of a pack's language are mapped by `NATIVE_LABELS` (`zh-cn`, `zh-tw` → `ZH`; `ja-jp` → `JA`; `ne-np` → `NE`), since their file is a QID that names no language, and the view parses them the same way into `wikidata_native_agreement_locales.json`. Each source's pack is read from its own rendering key (`locale_sources()`: CLDR's file, the native source's stratum), so a recorded rendering that is gone is still checked by its pack. The summary prints, per pack, how many of its renderings agree in every role under the default parser and under the pack, so a pack PR shows what it moved on its own language. A new pack adds its files to `LOCALE_FILES`, or its name to `NO_CLDR`; the test fails on a pack in neither. The modelling differences stay recorded here too: a pack is not meant to agree with CLDR where the models differ by design.

**The GND source.** `build_gnd_corpus.py` writes the GND's name parts in CLDR's field vocabulary (`forename` → `given`, `prefix` → `surname-prefix` with a one-word `surname` as `surname-core`, any other family → `surname` whole, `counting` → `generation`, and a `personalName` -- a person entered under the whole name, with no surname -- as `given` alone, so the family is expected empty), so `cldr_agreement.py` compares `gnd_fields.jsonl` by the same rules and records its disagreements in `gnd_agreement.json`, ratcheted by the same test. The locale view does not read it: no pack covers its names. A composed rendering says so (`composed: true`); where a particle is glued to the surname (`d'Arenberg`, `al-Ǧaʿfarī`) the composed line states the glued word as a whole `surname`, since the comparison matches fields word by word, and the index form, where the particle is a word of its own, keeps the split. A family with no `prefix`, or with a surname of several words, is stated whole for the same kind of reason: GND does not split a particle inside a surname (`Vélez de Guevara`, `Zuylen van Nijevelt`), so what it leaves unsplit means "not stated", not "no particle", and only `family` is compared there. Raw lobid responses are cached outside the tree, in a `gnd/` directory under `$NAMEPARSER_TOOLS_CACHE` (default `~/.cache/nameparser-tools`); `--refresh` fetches them again. The build stops before writing anything when a stratum falls below its floor, a query matches nothing, or a pool pages short, so a lobid change fails it rather than shrinking the corpus; `--record` prints, per source, how many changes of each kind it accepts.

**Adding a source.** Map only what the source states. The comparison reads a missing field as a statement that the role is empty, so a field the source leaves unstated must be mapped so that its role is not compared at all: #688's first build wrote a prefixless GND surname as `surname-core`, and 19 renderings recorded the parser's `de` in `Vélez de Guevara` as a disagreement no fix could clear; its fix then missed the same gap inside a several-word core after a prefix (`Zuylen van Nijevelt, Julius van`), so test each way a field can be left unstated, not the one that was reported. A field must also occur in its rendering's text, word by word (`test_every_committed_field_occurs_in_its_rendering`), or it is expected empty too. Size a stratum from the yield it has in the build, not on its own: strata that share a country take no one an earlier one took, so a yield measured alone overstates what the build gets. #862 measured its India strata one at a time, and Indian Urdu's 17 aligned names of 3,000 were 12 in build order, behind Bengali, Hindi and Marathi, exactly its quota; measure a new stratum with the strata before it filled to their quotas. A build must fail rather than shrink: give every stratum a floor, check a response's shape before caching it (an API error arrives as HTTP 200), and raise on a query that matches nothing. But tell a broken fetch from a fact about the data: #689's first fix raised on any item Wikidata reported missing, so one deleted name-part item anywhere in a pool would have stopped every rebuild, with `--refresh` advice that could not help; a missing part now only refuses the person stating it. A source sampled by script must check each text's script itself: Wikidata's `mul` labels are Latin, and the native-script build's first probe kept `Anushka Sharma` as a Hindi name. And give each refusal a test row that fails for the reason it names, not for another: that build's review found an all-Hebrew text standing for "a Hebrew point is not Arabic", which passed with the mark check deleted. A builder change has one oracle the suite cannot run, since it needs the local cache: rebuild offline from `$NAMEPARSER_TOOLS_CACHE` and diff the result against the committed fields file. The same review's mutation pass scored every surviving mutation that way, and four of them would have moved committed rows or the figures quoted from them with every test passing. The fetch (`fetch_bytes`: User-Agent, timeout, optional POST body and politeness delay), the cache (`cache_dir`, `cached_json`, which checks a response before caching it and writes atomically) and the two output files (`corpus_lines`, `fields_lines`, `write_corpus`) are shared in `corpus_build.py`, and the two Wikidata builders share their stratum loop (`build_strata` in `build_wikidata_corpus.py`: a person taken once across strata, the missing-person stop, the floor stop) as well as the pool check; a new builder imports them rather than copying another builder's, because a guard added to one copy is how #696 happened.

**The Wikidata source.** `build_wikidata_corpus.py` exists for the two fields no other open source labels, and states them in `wikidata_fields.jsonl` as `surname2` (P1950, CLDR's own field name) and `patronymic` (P5056, which CLDR has no field for), beside `given` (P735) and `surname` (P734); its disagreements are in `wikidata_agreement.json`. A person's written names are token-aligned to the parts rather than composed from them: a text is kept only where every word is claimed by exactly one part, a connective (`bin`, `i`, `y`) joining the part after it, and a woman's Russian surname may match the feminine form of its item's label. `cldr_agreement.py` lists `surname2` and `patronymic` in `PENDING_ROLES` and scores them inside `family` and `given_names` respectively -- a patronymic is not a family name, so `Vigdís Finnbogadóttir` expects the family empty -- and also scores each on its own once ParsedName has an attribute of that name: `patronymic` since 3.0's 4c (rules/R9) and `surname2` since 4d (rules/R10), the merged scoring kept. Only `two_family_names` fills `surname2`, so the record holds every stated second surname, CLDR's included, as not read (decisions/R10 measures it with the switch on). A stratum that falls below its floor, a query that matches nothing, a pool short of its size (unless the stratum is marked `whole`, which a full pool then contradicts) and a response that is not what was asked for each stop the build before anything is written; Iceland (270 of a pool of 600 on 2026-10-16, measured in the native paragraph below) and Malaysia are marked `whole`; Malaysia's floor is set below its quota because only 17 Malaysian public figures with a P5056 statement matched the query on 2026-10-16, and 9 of them aligned. Raw responses are cached outside the tree, in a `wikidata/` directory under `$NAMEPARSER_TOOLS_CACHE` (default `~/.cache/nameparser-tools`); `--refresh` fetches them again.

**The native-script Wikidata source.** `build_wikidata_native_corpus.py` exists because every other real-name corpus is Latin script, apart from Wikidata's Russian patronymics, so the script-conditional readings (family-first Han, Hangul and kana; Korean surname segmentation) had been tested only against CLDR's invented names. No text holds an honorific, so the corpus does not exercise the CJK honorific peel; it shows only that the peel leaves plain names alone. It reuses `build_wikidata_corpus.py`'s fetches and token alignment and adds the following. Strata are a country and a language, not a property, and the query keeps people with a label in that language. A text is used only if every letter and combining mark is in the stratum's script (`mul` labels are Latin: `Anushka Sharma` would otherwise pass as a Hindi name). Unspaced text is aligned by character under the same exactly-one-part rule, and nothing is inferred: a Chinese item stating only its surname is left out rather than reading the rest of the text as the given name. Feminine surname forms are kept per language (Greek `Λελούδα` for `Λελούδας`, Bulgarian and Kazakh `-ова`, Ukrainian `-ська`), so the filter does not drop women. A Han, kana or Hangul text carries no shape, since the parser reads those scripts family-first by itself and that is what is being tested; pure katakana keeps the order it is written in, as the parser does. Each person gives one rendering, P1559 first, and its disagreements are in `wikidata_native_agreement.json`. On 2026-10-16 every spaced stratum agreed in every role except seven Arabic surnames of two words (`عبد العزيز`, `عز الدين`, `شكر الله`, `ذو الغنى`: the parser reads the first word as a middle name), a Persian double surname, and a Bulgarian name whose two stated family names include what is probably the father's name (`Динко Цветков Дерменджиев`); Hangul agreed on 120 of 120; on 2026-10-23 the 117 Devanagari and Urdu names then added agreed but for two Urdu surnames of two words (`رضا خان`, `اگنی ہوتری`), the Arabic surnames' class; all 85 new Devanagari names carry combining vowel signs and agreed, though none holds a period, so the gap rules/H2's Accepted clause records (a period-marked abbreviation in an abugida) is out of the corpus's reach, and the 32 Urdu names carry no combining mark at all. One Marathi name is stated with its parts swapped (`राहुल बजाज`, given `बजाज`) and so scores as family-first; Han read by default disagrees on every unspaced Chinese name and 49 of 60 Japanese ones, while the locale view reads 74/80 under `ZH` (six surnames it does not segment: `詹`, `卫`, `柯`, `茅`, `华`, `文`) and 59/60 under `JA`. Wikidata's P734 is a convention, not a fact, where the culture has none: an Arabic nisba (`البغدادي`) is entered as a family name, and the corpus scores it as one. `--lc-check` compares each name with the native-script variants of its Library of Congress record (P244), splitting by LC's comma or, in CJK, a space, and counts an LCCN LC no longer has; it runs after the build has written its files, and adds nothing to them and filters nothing from them. A pool that comes back shorter than its size stops the build unless its stratum is marked as the whole population (Thailand, Kazakhstan, Bangladesh, Hindi in India, Urdu in Pakistan, Nepal), so a query that starts matching less cannot drift the sample unseen; a stratum so marked whose pool comes back full stops it too, since the mark is then stale. The check is `pooled()` in `build_wikidata_corpus.py`, which both Wikidata builders call; re-pooled on 2026-10-16 (#696), the parent's Iceland returned 270 of a pool of 600 and Malaysia 17 of 240, so both are marked whole, and the other six filled their pools (es 900, mx 600, co 480, ru 660, su 360, ri 240). On 2026-10-16, 99 of the 910 names had an LC variant that splits them, and 96 agreed; the other three are Arabic names whose LC record names a person written the other way round (`Ibrāhīm, Ṣāliḥ` for Wikidata's `إبراهيم صالح`), so the P244 link or the order is suspect, not the split. LC writes most Han variants unspaced, so it confirms almost no Chinese or Japanese split. The first build's 907 corpus lines (904 names new to the snapshot; three Ukrainian names were already in `corpus_wikidata.jsonl`; the 2026-10-23 strata added 117 lines, all new to it) cost about 2.9 s in the corpus-reading test modules and about 0.6 s in the agreement tests, measured locally without coverage on 2026-10-16. Raw responses are cached under `$NAMEPARSER_TOOLS_CACHE`, in `wikidata/` and `lc/`.

**The conventions source.** `conventions_fields.jsonl` states the parts of the hand-written conventions corpus, from the `fields` of `conventions.py`'s rows, and its disagreements are in `conventions_agreement.json`. The names are invented, so the record is a worklist of conventions rather than a measure of real data: a patronymic read as a family name (`Hassan bin Yusof`), a title read as a given name (`U Kyaw Win`). It uses the Wikidata source's `patronymic`, written with its connective (`bin Yusof`), and adds `honorific`, a word of address written after the name (`Bey`, `ssi`, `san`), scored inside `suffix` as nameparser reads `さん` (Derek, 2026-10-16). A row no field can state honestly is left out of the fields file and stays in the corpus, which the snapshot still watches: the kunya `Abu Karim`, the `-né` married form `Szabóné Kiss Éva`, and `arap`/`ole`/`wa`, whose last word is a parent's name or a family name depending on the family. Such a row says why in its `unstated`, and the builder refuses a row with neither `fields` nor `unstated`, so this fields file states a subset of its corpus without a row's fields being lost unseen. Being hand-written, it is also held to two checks the generated sources pass anyway: its fields partition each text word for word (`test_the_fields_partition_their_rendering`), and the scorer raises on a field name no rule reads, for every source.

`--record` rewrites every record. `JA` needs the `ja` extra (`namedivider-python`), which only CI's `ja-extra` job installs: without it the `JA` ratchet skips, the summary says `not measured`, and `--record` keeps the recorded `JA` entries of both locale records unchanged. Re-record with the extra installed (`uv sync --group dev --extra ja`) when a change moves Japanese.

`_CORPUS_NAMES` in `tests/v2/_differential_fixtures.py` leaves the file out (2026-10-12): the tests reading it carry counts measured over the names the other corpora held. `corpus_gnd.jsonl`, `corpus_wikidata.jsonl` and `corpus_wikidata_native.jsonl` stay in it (2026-10-16): the counts those tests carry are floors and dated snapshots, which a larger corpus cannot falsify, and their invariants now walk all three files' names too. A release figure counts GND's moved names in, its composed renderings included, since the names are real; AGENTS.md's rule of counting out names only `corpus_cldr.jsonl` holds stays CLDR's alone (Derek, 2026-10-16). Wikidata's moved names, native-script ones included, count in under the same rule, which singles out CLDR alone; they are real and written, not composed. `differential_corpus()` in `tests/v2/conftest.py`, which feeds the property tests, globs `corpus*.jsonl`, so it reads CLDR (since #652), GND and both Wikidata files, and the decomposed-twin test walks all their names.
