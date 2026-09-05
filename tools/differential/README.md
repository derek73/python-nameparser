# Differential harness (a released baseline vs the working tree)

Dev-only tooling for the 2.x line (migration plan S5). Not shipped
(excluded from the wheel by the packaging config -- only `nameparser/`
is packaged) and not CI-gated. Run it by hand when touching parsing
behavior, and before cutting a release.

Two processes, two environments:

- A **baseline worker** runs under a pinned nameparser installed fresh
  from PyPI via a PEP 723 inline script. It is not a checked-in file:
  `compare.py` renders it from a template with the version pin
  substituted and writes it to a temp directory outside the worktree.
  That placement is a safety mechanism rather than plumbing -- it is
  what makes the invocation traps below unreachable rather than merely
  documented.
- `compare.py` runs in the project's own dev environment and imports
  `nameparser` normally: the working tree, on whichever surfaces the
  baseline supports.

## Running it

```
uv run python tools/differential/build_corpus.py --ref <ref> > tools/differential/corpus.jsonl   # only when regenerating
uv run python tools/differential/compare.py --baseline 1.4.0
uv run python tools/differential/compare.py   # bare = DEFAULT_BASELINE, the last release
```

`compare.py` spawns the worker as a subprocess, feeds it every corpus
entry as a line of JSON -- `{"name": ..., "order": ...}`, where `order`
names the `name_order` constant the entry is parsed under on both
sides and is `null` for an entry carrying no order -- and diffs the two
sides field by field. Every diff is checked against that baseline's
ledger:

- Matches a rule -> counted as an intentional, classified change.
- Matches no rule -> reported, and what happens next depends on the
  name's tier (see below): on a CONTRACT corpus it prints under
  `UNEXPLAINED` and the run exits 1; on a RADAR corpus it prints under
  `UNCLASSIFIED (radar)` and the run keeps exiting 0.

An unexplained diff on the contract tier means either a real parity
bug (fix it, don't allowlist it) or a known change whose ledger rule
needs widening. The run must exit 0 at every baseline you claim before
a release; the classified summary it prints is the source for the
"Behavior Changes" section of `docs/release_log.rst`.

## Baselines

`--baseline VERSION` chooses what the tree is compared against, and
two things follow from it: which ledger is read
(`expected_since_<VERSION>.toml`, a hard error if absent) and which
surfaces are compared (the facade alone below 2.0, which has no v2
API; both from 2.0 on, ambiguity kinds included).

Run both before cutting a release:

- `--baseline 1.4.0` — the v1 compat contract.
- `--baseline <previous minor>` — what changes for a user upgrading.

The worker is generated per run, with the pin substituted, into a temp
directory outside the worktree. Its first output line is a version
tell, and `compare.py` aborts before comparing anything if the wrong
version answered or if the module resolved inside the checkout.

**Both** sides are proved, not just the baseline. `compare.py` also
checks that its own `nameparser` is this checkout's source package and
prints it on a `tree:` line — see the third trap below for why a bare
import was not enough.

A rule's `fields` names roles the way `Role` does, whichever surface
the diff came from, plus two pseudo-fields. `_ambiguities` carries a
change in reported `AmbiguityKind`s. `_initials` (#484) carries a
change in `initials()` -- the facade's at every baseline, the core's
from 2.0 on -- and enters a name's diff ONLY when every role and the
ambiguity kinds agree on every compared surface: a role move drags
its initials with it, so that movement is the role diff's consequence
and is neither compared nor printed, while an initials change with
the fields identical is render-layer drift the field comparison
cannot see. A rule that lists `_initials` therefore lists nothing
else; `validate_rules` refuses the mix as silently dead. The roster is
not restated here: it is `Role`'s members, `validate_rules` rejects
anything outside them, and a copy in prose is a copy that goes stale
when a role is added. The facade reports `first`/`last`; those are
canonicalized on the way in, and the `UNEXPLAINED` block prints the
canonical name so what you read is what you write.

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

One shell note while you are here: `compare.py | tail` swallows the
exit code under zsh. `$?` after a pipeline is `tail`'s status, and
`PIPESTATUS` is a bash array zsh does not define at all -- zsh's own
is the 1-indexed `pipestatus`, so `${PIPESTATUS[0]}` is the empty
string and a failing run reads as a passing one. Redirect to a file
and read the file instead of piping.

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

Two things close it. `_worker_env()` strips `PYTHONPATH`/`PYTHONHOME`
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

## The corpora and their tiers

`compare.py` reads **every** `corpus*.jsonl` beside it by default
(deduped), because a corpus you have to ask for by name is a corpus
that stops being run. Pass `--corpus PATH` (repeatable) to narrow it.
The run's `corpora:` line names each file with its entry count, and
with `(N, K skipped)` where K entries were left out of this baseline's
comparison (see the shape key below). Each file also needs an entry in
`_CORPUS_FLOORS`, a minimum set a little under its real size: a corpus
that silently shrinks to nothing would otherwise report a green run.

| File | Source | Tier | Blind to |
|---|---|---|---|
| `corpus.jsonl` | v1's own test suite at a pinned ref | radar | anything 2.0 added — v1's authors had no reason to test a typographic nickname delimiter or a Cyrillic title |
| `corpus_issues.jsonl` | name-like strings harvested from the GitHub issue tracker | radar | anything nobody ever reported |
| `corpus_cjk.jsonl` | the CJK-bearing rows of `tests/v2/cases.py` that do not declare `tolerated`, via `build_cjk_corpus.py` (#295) | contract | anything the case table itself missed — it re-witnesses reviewed expectations at the baseline boundary rather than discovering new shapes |
| `corpus_cjk_tolerated.jsonl` | the `tolerated` CJK rows of `tests/v2/cases.py`, via the same `build_cjk_corpus.py` run (2026-09-01) | radar | any composed or wrapped CJK form nobody wrote a case row for — it holds demoted names, and demotion presupposes admission |
| `corpus_rules.jsonl` | every example of every NORMATIVE rule in `docs/design/rules.md`, via `build_rules_corpus.py` (#414) — a rule carrying that doc's `tolerated:` marker is skipped whole, its examples illustrating rather than promising | contract | anything the rules doc has no example for, and anything a tolerated rule's examples are the only witness of |
| `corpus_shapes.jsonl` | shape-tagged rows of `tests/v2/cases.py`, via `build_shapes_corpus.py` (#468) | contract | anything no one has tagged a row for |

Since the v2.3 tier split (#468), a corpus is CONTRACT or RADAR --
the roster is `_CORPUS_TIERS` in compare.py, fail-closed like the
floors. Contract corpora hold names someone chose, and an unmatched
diff on one is UNEXPLAINED and fails the run. Radar corpora hold the
names the contract does not answer for -- the scraped and harvested
ones, and since 2026-09-01 the deliberately demoted ones too: their
diffs still classify against the ledger, so intended changes keep
their release-note grouping, but an unmatched radar diff prints under
UNCLASSIFIED (radar) and cannot fail the run or demand a ledger rule. Nothing is deleted to keep the
gate quiet -- a meaningless string in radar costs one parse and a
report line. To promote a radar name, give it a tests/v2/cases.py row
and a shape tag: it enters the contract by being chosen. A
name can also travel the other way, and one file records it:
`corpus_cjk_tolerated.jsonl` holds names that WERE chosen and were
then demoted, one reviewed row at a time, by the `tolerated` flag on
their case rows (the 2026-09-01 CJK demotion — composed and wrapped
CJK forms, read best-effort). Radar is what "we still watch it, we no
longer enforce it" costs: the diffs still classify and still group in
the release notes, the case rows still assert every one of these
parses in the suite, and clearing the flag promotes the name back.
What the flag moves is the file, which is not quite the same as the
tier: contract files load first and the dedup keeps the contract
reading, so a text another contract corpus also holds stays contract
until it leaves there too. Five of these were `rules.md` examples in
`corpus_rules.jsonl` when the file was created, and the same day's
rules.md edits took all five out of it — W3 marked `tolerated:`,
W2's two comma examples swapped for pure ones, C1's two moved into
W3 — so every text in the file reads radar today, and the sentence
above is the standing rule the next demotion has to satisfy rather
than a note about those five. A
`[[never]]` exclusion outranks the tier either way: it was chosen too
-- someone wrote its `why` and its `examples` -- so a name it refuses
stays UNEXPLAINED and fails the run even when the name itself sits in
a radar file.

A CONTEST row -- a recorded diff shape with a winner pinned beside it
(`MOVED SHAPE`, below) -- is the second thing that outranks the tier,
and the rule is stated rather than inherited: it is fatal on both
tiers because it carries an argument, and a moved shape has made that
argument's premise false. A WATCHED row -- a shape recorded alone, in
`_WATCHED_DIFFS` -- does not outrank the tier: it follows the tier of
the default-order entry it was measured on, fatal on a contract name
and printed under `MOVED SHAPE (radar)` on a radar one. Measured
2026-09-03, before the rule was written, MOST of the contest rows in
`_RECORDED_DIFFS['expected_since_1.4.0.toml']` sat on radar-tier names
-- 21 of 31 -- so radar PARSER DRIFT could already fail the run
wherever someone had pinned a winner (RECOMPUTE: for each row, take
the tier of the first corpus file holding the name with contract files
sorted first, as `main()` loads them -- a NAME's tier, which is the
unit this count needs and not the one a watched row's severity reads:
that reads the default-order ENTRY's tier, per the `MOVED SHAPE`
section below, and the two recipes agree on every name that has no
declared-order entry); the rule keeps that, on the
ground that it is the argument and not the tier a contest row defends.
Which of the two outranks the tier more WIDELY is
deliberately not claimed here, because the answer inverts with the unit
and neither unit is the point: the exclusions number two against 31
rows, while the two `[[never]]` patterns reach 60 corpus names between
them, 37 of those radar-tier -- more radar names than the roster pins
(measured 2026-09-03 by matching each `name_regex` against every name
in the `corpus*.jsonl` glob, tiers read the same way). That is a pin
doing what pins do --
someone wrote the row by hand and it says what the name does -- but it
is not what "a radar diff can never fail the run" leads a reader to
expect. Read the tier rule as being about UNMATCHED diffs, which is
the only thing it was ever measured over.

A corpus line is a bare JSON string or an object carrying `name` and,
optionally, `tests` or `shape` -- the input-shape id from
`tools/differential/shapes.py`, which is where each shape's notation,
the `name_order` it is an input shape FOR, and the oldest baseline
whose worker can honor that order are written down. `compare.py`
resolves every entry's shape through that table: an entry whose shape
declares an order is parsed under that order on both sides and
compared on the v2 surface alone (the facade is the v1-compat surface,
and a family-first name is not a v1 contract), and an entry whose run
predates its shape's `min_baseline` is left out of the comparison --
reported as `skipped N names tagged shape(s) [...]` and counted in the
`corpora:` line, so a shrunken comparison is never silent. That a
family-first name is not compared under the default order is
structural, not a ledger exception: its shape says what the name is an
input FOR.

`corpus_shapes.jsonl` is the corpus of those entries: every distinct
(shape, name) pair from the shape-tagged rows of the case table, so a
name tagged under two orders is two entries and two comparisons.
Regenerate it after tagging or editing a tagged row; `--coverage`
prints names-per-shape instead of writing, which is the "which shapes,
how many names deep" answer:

```
uv run python tools/differential/build_shapes_corpus.py
uv run python tools/differential/build_shapes_corpus.py --coverage
```

It is pinned exactly as the CJK corpus is -- `tests/v2/test_ledger_guards.py`
holds the checked-in file equal to the generator's selection, so a row
tagged without regenerating fails the suite instead of leaving the
contract tier narrower than the case table says it is.

They are deliberately separate rather than merged: `corpus.jsonl` is
reproducible forever from an immutable git ref, while the issue
tracker is mutable, so regenerating `corpus_issues.jsonl` is an
explicit, reviewable act that can only add names while the harvester is unchanged (changing its screens, as #413 did, can remove one) — and the CJK corpus
exists because BOTH of those are structurally blind to unspaced CJK (v1's
banks never tested it; `build_issues_corpus.py` requires an internal
space, which unspaced names never have). It regenerates from the case
table, and `tests/v2/test_ledger_guards.py` pins the checked-in file
against the generator's selection, so a CJK case row added without
regenerating fails the suite instead of silently narrowing this gate.

The rules corpus answers a different question from the doc tests that
already execute those examples. Those pin an example against an
expectation stored beside it, so a deliberate behavior change edits
both in one commit and the test stays green — a doc example cannot
warn about the change that edited it. Parsing the same name with a
*released* baseline can, because no commit can edit 1.4.0. It is
generated and pinned the same way the CJK corpus is.

The issue corpus earned its place on the first run — 166 of its 198
names were not in `corpus.jsonl`, and it immediately surfaced five
intended-but-unclassified 2.0 behaviors (#273 typographic delimiters,
#269 non-Latin vocabulary) plus one shape no test had considered: a
**leading** `"Ph. D."`, which v1 split into title `Ph.` + given `D.`.

It earned it again at #413. The harvester matched names in quotes
only, while this tracker writes them in backticks, so the corpus whose
purpose is "what users reported" was blind to how this project
reports — 200 names became 381. Among the arrivals were the headline
example of nearly every issue that fixed them, including
`Ursula von der Leyen geb. Albrecht`, which sat in #399's own title
while that issue shipped noting the class was invisible to this
harness. Classifying the arrivals widened `fix(#367)`, which had
asked in writing to be widened, added six rules, gave
`fix(leading-credential)` the `family` role its own shape always moved,
and narrowed the trailing-`Ph. D.` exclusion as its comment instructed
the moment a `<suffix> Ph. D.` name appeared.

Backticks prompted a second look at prose, and the same change added
two screens neither branch had: `:` joins the structural characters (it
appears in no name in any corpus, and accounted for three error
messages and a PyPI trove classifier), and a short list of English function words
rejects capitalized sentences the character screen cannot see —
`What this gate does not cover` is well-formed as a phrase. That list
is narrow on purpose: `and`, `the`, `of`, `will`, `can` and `do` all
stay out of it, because `Rob And Beth Edmunds`, `The Hon`, `Duke of
Wellington` and `Anh Do` are real corpus names.

The rules corpus earned its place the same way — 113 of its 155 names
were in no other corpus, and on its first run 12 of them turned out to
have moved during the 2.2 cycle with nothing observing it. Classifying
them surfaced an unlogged behavior change (`mc` moving into the
never-given particles, which moves `Mc Donald`), two rules broad
enough to absorb a regression once a name of the right shape existed
(`fix(#274)`'s marker matching a *parenthesized* `Nee`, which is a
nickname under the default facade, and the acronym rule's dotted
`m\.?a\.?` reaching the real name `John Smith M.A.`), and two
pre-existing behaviors that had never had a corpus name to exercise
them.

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
the merged labels still describe the same string. `compare.py`
surfaces these as `[v1: ...]` tags on radar rows.

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

`corpus_cjk.jsonl` and `corpus_cjk_tolerated.jsonl` are the two halves
of ONE projection of the case table, written by one run:

```
uv run python tools/differential/build_cjk_corpus.py
```

Every distinct CJK-bearing `text` in `tests/v2/cases.py` goes to the
first file, or to the second when its rows declare `tolerated`. The
flag is read per TEXT, not per row, because a corpus line is a name
string: a text carried by a default row and a policy/locale fork of it
is one line in one file. A text marked on one of its rows and not
another is a hard error rather than a silent choice — the generator
refuses the run, since either answer puts a name on a tier half its
rows deny.

## The ledgers (`expected_since_<VERSION>.toml`)

One ledger per baseline, so each release's classified changes stay as
history rather than being edited into the next one's.

Each `[[change]]` entry needs `issue` (a short label, ideally an
issue number or `fix(<slug>)` matching a `tests/v2/cases.py`
classification) and `name_regex` (searched against the raw input
string) AND `fields` (the diffing rule matches only if the observed
diff fields are a subset of this list), which since #452 must also
name EXACTLY the roles that rule's own diffs move -- see below. Keep both as tight as the actual diff allows -- a loose
rule can mask a real regression. **Both keys are REQUIRED**, and each
ban has its own issue: `validate_rules` rejects a rule carrying
neither (it would match every diff), one carrying `fields` and no
`name_regex` (#451 -- no name narrowing, so it claims every name whose
diff fits its roles), and one carrying `name_regex` and no `fields`
(#456 -- no role narrowing, so on any name its regex reaches it claims
every diff shape there is, measured, 256 of them from baseline 2.0 on and 128 below it). The three are one
rule with one reason: a rule narrows by name AND by role, or it is not
a rule. Note the two bans are each other's obvious wrong answer --
deleting `fields` to silence an over-declaration failure lands on
#456's, and adding `fields` while dropping the regex lands on #451's.

**`fields = ["_initials"]` is a rule of its own kind** (#484). It
classifies a change in the derived `initials()` view on a name whose
seven roles did not move, and nothing else -- `main()` never puts
`_initials` into a diff beside a role, so a rule mixing the two is
refused at startup. Such rules close the 1.4.0 ledger, and each 2.x
ledger carries the subset visible from its baseline; their comments
say which view change each one names.

**`orders` is the optional third narrowing** (#468). A rule may carry
`orders = ["FAMILY_FIRST", ...]` -- public order-constant names, taken
from the ones `shapes.py` declares, so `validate_rules` rejects a name
no shape asks for rather than letting the rule sit dormant. A rule
carrying it matches only diffs from comparisons run under one of those
orders. Omit the key and the rule is order-blind, which is what every
rule written before shape-tagged entries existed is.

`"DEFAULT"` is the one member `shapes.py` does not supply, and cannot:
it names the comparison run under no declared order (`order` is
`None`), which is the absence of a shape rather than one of them. It
exists because TOML has no null to put inside an array, so without it
a rule explaining only default-order diffs had no way to SAY so and
had to stay order-blind -- and an order-blind rule leaks the other
way from the leak the key was added for, absorbing an order-bearing
diff on any name its regex happens to reach. `orders = ["DEFAULT"]`
is a default-order-only rule; `orders = ["DEFAULT", "FAMILY_FIRST"]`
is a rule that genuinely explains both and stops there.

A run PRINTS the order-blind absorptions it sees: when a rule with no
`orders` key explains a diff from an order-bearing comparison, the
report carries an `ORDER-BLIND` block naming the issue, the name and
the order. It is informational and outside the exit code -- order-blind
rules stay legal -- but the absorption is no longer invisible.

It exists because a name can now be compared more than once, and the
two diffs can move the SAME roles for opposite reasons.
`de la Cruz Juan Carlos` is compared under both family-first orders
from `corpus_shapes.jsonl`, where #395's fold reads family
`de la Cruz` and distributes the leftovers, and under the default
order from `corpus_rules.jsonl`, where rules.md#P1 says the whole
string is the family. If that fold ever leaked into the default order
it would move `{family, given, middle}` -- exactly what the
`feat(#395)` rule declares -- so an order-blind rule would claim the
leak, label it intentional and exit 0: #372's failure mode aimed at
the most plausible regression of the very change the rule describes.
Exclusions stay order-blind for now; refusal is monotone, so the worst
an over-wide one can do is make a name report `UNEXPLAINED`, which is
loud.

**That closes the SHAPE, not the property.** A required `name_regex`
is not a bound on how much a rule reaches: the only width check is the
sentinel probe, which rejects a pattern matching all four of
`_SENTINELS` and nothing narrower. Measured over the 1090-name corpus,
`name_regex = "[a-z]"` passes validation and reaches 941 names, `" "`
reaches 1027 -- the old catch-all with a fig leaf. What #451 changed is
that such a rule now has a `_CORPUS_CLAIMS` reach and digest to record,
so its breadth is visible ONCE, to whoever reviews that number, instead
of being invisible forever. That roster is by its own docstring "inert
for a brand-new rule", so the review is the check. A reach ceiling is
the mechanism that would bound this; it is still proposed on
[#452](https://github.com/derek73/python-nameparser/issues/452), whose
other half -- the declared-fields check below -- has landed.

**`fields` must be EXACT, not merely a bound.** A rule's declaration
must equal the union of the diffs it actually explains, and
`compare.py` recomputes that union at the end of every run: a rule
declaring a role none of its diffs moves is reported `OVER-DECLARED`
and exits the run non-zero, like an unexplained diff or a dormant rule
that explained one. The excess is not inert. `classify()` admits a
rule when the observed diff is a SUBSET of `fields`, so a role nothing
moves is a standing claim on every future diff that shrinks into it --
which is how `fix(#424)` kept explaining 'Freiherr von Richthofen V'
after #410 narrowed that diff from three roles to two, with no run
ever naming it (see decisions.md#H1). The check is exact rather than
heuristic, and cheap for the same reason: `classify()` already
requires `declared >= union` for the rule to match the names it
matches, so the only possible error is the other direction, and the
union is simultaneously the check and the repair. Narrowing a rule to
it cannot orphan a name, since every name the rule explains
contributed to it.

Width is BASELINE-RELATIVE, so measure each ledger on its own run
rather than copying an edit across the three. `fix(#296) a lone
post-comma credential is a suffix` declares all four of `{family,
given, suffix, title}` at 1.4.0, where v1 reads the pre-comma word as
`first` and every one of those roles moves, and only `{suffix, title}`
at both 2.x baselines, where the same behaviour moves nothing else.
One rule with two different field lists across the three files is
correct there, not drift.

Two shapes are skipped, neither as an exemption: a rule declaring
`dormant` explains nothing by declaration, and the dormancy check
below owns that finding in both directions; a rule with no `fields`
declares no roles to exceed. There is no third way out, by decision
rather than by omission -- a rule that genuinely needs a wider
declaration must argue for a key of its own, the way `dormant` was
argued for in #373.

**File order decides.** That is not a detail -- every rule in every
ledger carries a `name_regex`, so they all sit in one tier, the sort
is stable, and the order they are written in settles every tie between
them. Append a rule to the bottom of a file only after checking that
nothing above it already claims the diff you meant it for. Where the
EARLIER rule of such a tie is the wider one, the pair must say so --
see "Declaring a wide-first pair" below.

`_sorted_rules` still sorts `name_regex` rules ahead of `fields`-only
ones, and is now the identity on every ledger that loads. It is kept
as a defence for a reader that does not call `validate_rules` first --
a future tool, a REPL, a test fixture -- rather than as a second tier
any ledger can reach; its docstring in `compare.py` says why.

Some entries in `expected_since_1.4.0.toml` are for behavior families that
a corpus happens to contain no example of (e.g. custom suffix-delimiter
rendering, which only fires under a non-default `Policy` -- see the ceiling
below). They're kept in the file anyway, matching the family documented in
`tests/v2/cases.py`, so the rule is ready the moment a matching string is
added to the corpus.

Such a rule must say so, with `dormant = "<reason>"`. Without it a rule
that explains nothing is indistinguishable from one that has stopped
explaining anything -- which is how a reverted fix leaves its rule inert
and the run still exits 0 (#372). Two tiers ask:

- `tests/v2/test_ledger_guards.py` fails, in CI, when a rule's
  `name_regex` reaches no corpus name and no `dormant` reason is given. It
  needs no baseline wheel, so it is cheap and early.
- `compare.py` fails the run when a rule explained no diff, and equally
  when a rule declaring `dormant` explained one -- a declaration that
  stopped being true is a false statement in the ledger. It reports which
  kind of nothing: **reverted** (matched no diffing name), **shadowed by
  `<issue>`** (an earlier rule claimed every diff it would have), or
  refused by a `[[never]]` exclusion. The three have three different fixes.

One limit worth knowing. Only the ledger for the baseline being run gets the
dynamic check, so the release checklist runs `compare.py` at every baseline
that has a ledger with rules -- a ledger the checklist does not reach gets no
dynamic dormancy check at all, and a `dormant` declaration in it goes
unaudited. The root `AGENTS.md` checklist DERIVES its baselines from the
`expected_since_*.toml` glob, so a new ledger is reached at the next release
without a line being added; it enumerated three commands against four
ledgers until #503 replaced the list with the loop (the dated record is in
`AGENTS.md`, at the step). The over-declaration check (#452) and the
recorded-shape check (#497) are per-ledger for the same reason the dormancy
one is -- the latter reads `_RECORDED_DIFFS[ledger.name]` and
`_WATCHED_DIFFS[ledger.name]`, and refuses pre-worker a ledger either dict
has no section for -- so a ledger the loop did not reach would get none of
the three.

The static tier still exempts a rule on the mere PRESENCE of `dormant`; it
never asks whether the reason is still true. Only the dynamic check can
catch a `dormant` that quietly stops being true, which is why every ledger
with rules needs one.

### Declaring a wide-first pair (`precedes_narrower`)

File order deciding is safe while the earlier rule is the NARROWER
one, and narrow-first is a default rather than a law (#382). A wider
rule can be the better classifier where it describes a compound
behavior its component rule does not: `马丁·路德·金씨` divides on the
nakaguro AND peels its glued hangul honorific, so `fix(#272/#308)`
describes what happens to the name and
`fix(cjk-glued-honorific-peel)` describes half of it -- and the wider
rule wins, correctly, by sitting first. `fields`-subset is a proxy
for specificity and the wrong one there, which is why the ordering
cannot simply be enforced.

Such a pair is legal, and must be DECLARED on the rule that WINS it
-- the earlier one, which is the only rule whose word can retire the
contest:

```toml
[[change]]
issue = "fix(#272/#308) nakaguro division and a glued hangul honorific in one name"
name_regex = "..."
fields = ["family", "given", "middle", "suffix"]
[[change.precedes_narrower]]
issue = "fix(cjk-glued-honorific-peel) glued honorific peels into suffix"
why = """
`middle` is the discriminator and the nakaguro is where it comes
from. ...
"""
```

DOUBLE brackets: a rule may outrank more than one neighbour, so the
key is an array of tables. Single-bracket
`[change.precedes_narrower]` makes ONE table rather than a list of
them and is refused, as is an empty list -- deleting the key says the
same thing in one place.

Each block names ONE later rule, by its exact `issue` string, and
gives a `why`. Both are required, and each ban has its reason. The
named rule is the one and only rule this one outranks: a blanket
"may outrank anything narrower" would be inherited by every narrower
rule added afterwards, which is the widening this check exists to
refuse. The `why` is the whole safeguard, as it is for `dormant` --
`fields` cannot say that a wider rule describes a compound behavior
its component does not, so the reason is the only place that fact can
live, and an exemption nobody had to justify is the one nobody
reviews. `validate_rules` also refuses a target naming no rule in
this ledger, a rule naming ITSELF, a target sitting EARLIER in the
file (the narrower rule of a declared pair is by definition the later
one, so an earlier one is a copy-paste of the wrong issue string),
and the same target twice (one pair takes one exemption, so a repeat
exempts nothing new and means one of the two reasons is stale, with
nothing to tell a reader which).

**The trap: nothing may follow the block inside a rule.** TOML binds
every later bare `key = value` to the table the last header opened,
so a rule key written BELOW `[[change.precedes_narrower]]` leaves the
rule and joins the exemption. Put the block LAST in the rule.
`validate_rules` rejects any key inside an exemption other than
`issue` and `why` for exactly this reason: an `orders` landing there
deletes the rule's order narrowing, and nothing else would notice.

**What counts as a contest.** `order_contests` asks the three
questions `_entry_matches` asks, one per narrowing key, and a pair is
a contest only where all three overlap. `fields`: the later rule's
are a STRICT subset of the earlier one's, so every diff fitting the
narrower set passes both rules' subset test. `name_regex`: some
corpus name reaches both. `orders`: some order reaches both -- two
rules scoped to disjoint orders never see the same comparison, so
file order decides nothing between them however nested their `fields`
are, and calling that a contest would demand a justification for a
hazard that cannot occur. No diff is computed, which is what makes
the check cheap enough to run before the worker spawns -- the nesting
supplies the contested shape's EXISTENCE, and computing real diffs
could only ever remove pairs from THIS list, never add one to it.

**Nesting is SUFFICIENT for a contest and not necessary**, so read
that last sentence as a statement about the nested pairs and not
about contests in general. Two rules whose `fields` merely INTERSECT
both admit any diff inside that intersection, so `classify()` hands
such a name to whichever of them is written first, exactly as it does
for a nested pair -- and this check cannot see it. That class is
outside the check by REASONING and not by oversight, and the
reasoning is the one `order_contests`' docstring gives for EQUAL
`fields`: neither rule is narrower, so "narrow-first" says nothing
about the pair, `precedes_narrower` has no narrower rule to name, and
`_CROSS_RULE_WINNERS` stays the instrument there. That argument
covers every pair where neither `fields` set contains the other, and
equal `fields` is its special case. Measured 2026-09-02 over the four
ledgers -- pairs sharing a corpus name whose `orders` are not disjoint
-- 11 are strictly nested wide-first, which is what this check
refuses; 40 nest in either direction, 11 have equal `fields`, and 111
have any non-empty intersection, so 60 overlap without nesting or
equality. Read the gap and not the digits, and recompute before
quoting any of them: decisions.md#differential-ledger carries the same
five figures with the recipe, and #498's body the loop.
Widening the predicate to that general case would demand 111 written
justifications where the real number is eleven -- the same argument
decisions.md already makes about the 657 figure, that a predicate
nobody can answer is not a usable one. The worked blind spot is real
and filed as
[#498](https://github.com/derek73/python-nameparser/issues/498):
`fix(#271/#272/#298)` and `fix(cjk-delimited-nickname)` intersect in
{`family`, `given`} without nesting, and swapping them reattributes
three contract-tier names this check never mentions in either
arrangement.

Two questions, in both tiers, as for `dormant`. Is every contest
DECLARED, and does every declaration still stand over a contest? The
second matters as much: a rule narrowed until it no longer overlaps
its neighbour leaves its exemption behind, and a justification for a
hazard that is gone reads exactly like one for a hazard that is live.
`tests/v2/test_ledger_guards.py` asks both over every corpus on disk
with no baseline wheel, so a rule added by a later bundle is checked
at pytest speed; `compare.py` asks both over the entries the run
actually loaded, before it spawns the worker. Do NOT answer either
failure by reordering: that moves which rule classifies a name and
breaks `_CROSS_RULE_WINNERS`.

**Under `--corpus` the two checks are NOT symmetric**, which is why
only one of them refuses there. A smaller name set removes contests.
For the undeclared check that can only UNDER-REPORT, never
false-alarm -- fewer contests, fewer things to declare -- so
`--corpus` is only ever more lenient. Not "fail-closed": this file
uses that for the `_CORPUS_TIERS` and floor rosters, which REFUSE on
a missing entry, and a check that errs toward not refusing is the
opposite of one that errs toward refusing. For the vacancy check it
INVERTS: a live declaration whose contested names
all sit outside the subset reads as vacant, and following the advice
would delete an exemption the full gate needs and then fail the full
run for the undeclared contest that reappears. So a vacancy is a hard
failure on a full run and a printed NOTE under `--corpus`.

Four checks now read the flag differently, and the differences are deliberate rather than untidy -- read them together before making any of them uniform. The corpus-floor roster is SKIPPED entirely under `--corpus`, because narrowing is the point of the flag. `over_declared_rules` still FAILS the run and appends a NOTE saying the union it computed is over a subset, so its repair advice is not followed blindly. The vacancy check does not fail at all, because its verdict INVERTS under narrowing rather than merely its evidence. The departed-name half of the recorded-shape check (below) inverts the same way and goes one step further, printing nothing at all under `--corpus`: a NOTE there would name most of the roster and tell the reader nothing, where the vacancy NOTE names a handful. The shape blocks themselves -- `MOVED SHAPE` on either roster, and `MOVED SHAPE (radar)` -- read no flag at all, and the section below says why that is deliberate rather than a fifth difference.

### `MOVED SHAPE`: the two rosters' recorded diffs, checked against a run

`tests/v2/test_ledger_guards.py` carries `_CROSS_RULE_WINNERS`, a roster pinning which rule should win a contested name. To ask that question it needs the name's diff SHAPE, which it feeds to `classify()` as an input -- so the shape is never itself checked, and a guessed one agrees with itself forever. That is how `田中さん II` sat recorded as `{given, suffix}` under a docstring promising the shapes were measured; the real diff is `{family, given, suffix}` (#497). The unit suite cannot catch it: it spawns no worker, deliberately, so it has no measured diff to compare against.

So the shapes live in `compare.py`, keyed per ledger (a string moves a different set of roles against different baselines), in TWO dicts under two contracts, and every run checks both. `_RECORDED_DIFFS` is the CONTEST roster: a shape beside a winner ADJUDICATES a contest -- it records what a name diffs so that `_CROSS_RULE_WINNERS` can ask `classify()` which rule wins it, and every row has a partner pin there (the guard holds `set(winners) == set(shapes)` per ledger, in both directions). `_WATCHED_DIFFS` is the WATCHED roster: a shape alone, for a name NO WINNER IS PINNED FOR. Most of its rows are also sole-watched -- radar names that no test names and no contract corpus holds, whose only other watcher is the classification rule explaining their diff, and a rule asserts that a diff is intended, not what it IS, so a shape moving inside the rule's `fields` moved silently before the row existed. The rest are the four #501 contests at 2.0.0, measured and unadjudicated: a `Case(...)` row in `tests/v2/cases.py` already pins each one's PARSE, and what nobody has argued is which RULE explains its diff, so read the case row before the roster. The two dicts are disjoint per ledger, and a name in both is refused pre-worker, beside the departed-name refusal, as the guard refuses it at pytest speed: a row is one kind or the other, and the run reads a row's severity and its repair text off the dict it sits in. The day a winner is argued for a watched name, the row MOVES to `_RECORDED_DIFFS` and the pin goes beside it there; nothing relaxes the equality. Out of the pair come two findings, a non-fatal block and a note, and they behave differently on purpose.

- **`MOVED SHAPE`** -- a recorded shape the run contradicts. Printed after the comparison, alongside `EXPLAINED NOTHING` and `OVER-DECLARED`, and it feeds the exit code the same way. It does not raise: a refusal there would land mid-report and take the `UNEXPLAINED` block down with it, and a stale roster row must never hide an unexplained diff. A moved shape is a FINDING, not a number to update, and it names no cause because it cannot: the parser may have changed what the name does, or the row may have been wrong when it was recorded -- which is what #497 found, four rows recording a shape no run makes under a roster promising the shapes were measured. SEVERITY follows the row's kind first and the tier second, and the run prints one block per case, contest first. A CONTEST row is fatal on both tiers: it carries an argument, and the winner pinned beside it in `_CROSS_RULE_WINNERS` was recorded against the OLD shape, so read both before editing either. A WATCHED row on a contract-tier name is fatal too, as an unexplained diff on that name would be; its block names no partner, because no winner is pinned for it, and the repair it gives is the only one a snapshot admits -- if the move is intended, re-record the shape in `_WATCHED_DIFFS` in the commit that moved it and say why there. A WATCHED row on a radar-tier name prints under **`MOVED SHAPE (radar)`**, parallel to `UNCLASSIFIED (radar)`, and feeds no exit code: fatal-on-radar is reserved for a per-name deliberate choice -- a `[[never]]` entry with its `why`, or a contest row with its pinned winner -- and a measured snapshot is neither; a gate whose repair is "record whatever it does now" is a changelog entry in a gate's clothing. The tier a watched row follows is the DEFAULT-ORDER ENTRY's where the name has one, since that is the comparison the shape was measured on, and the first-loaded (contract-first) entry's only where it has none. `'John Smith, Dr.'` is the case that separates the two readings: contract in `corpus_shapes.jsonl` only as shape 4 (`FAMILY_FIRST`) and radar in `corpus_issues.jsonl` under the default order. It carries no watched row today -- a test names it, so it is not sole-watched -- but a watched row on it would print and not fail, and the family-first promise would be untouched. Where the run measured no default-order diff at all, the report says so and names no cause: two states reach it (the parser stopped moving the name, or the name is compared only under a declared order) and the check cannot separate them.
- **A row naming a name no corpus holds** -- refused, before the worker runs, on a FULL run only, over the UNION of the two dicts: a watched row is measured by nothing else either. Nothing measures such a row, so it agrees with itself forever, which is the defect above in a second form. The repair is not mechanical: ask first whether the name left deliberately (`git log -S'<name>' -- tools/differential/corpus*.jsonl`), then either delete the row -- and, for a contest row only, its `_CROSS_RULE_WINNERS` partner; the message lists the two kinds apart so that a watched-row reader is not sent to delete a partner that does not exist -- or restore the name to the corpus that lost it. Under `--corpus` this prints nothing, since a narrowed run legitimately holds almost none of either roster.
- **`NOT CHECKED`** -- a NOTE rather than a finding, printed after the comparison and deliberately outside the exit code (#497, `9360919`). It names rows in either dict whose corpus entry THIS BASELINE SKIPPED: an order-bearing entry a baseline with no `Policy` cannot honor is dropped before the comparison runs, so there is no measured diff to check the row against. Such a row falls between the two checks above -- `MOVED SHAPE` skips a name it did not compare, and the departed-name refusal passes it because the skip takes a name out of the RUN and out of no file -- and without the note it is checked by neither and reported by neither. So the note says which rows the shape report is silent about and claims nothing else. Do NOT delete a row over it: the name is in a corpus this run read. Re-run at a baseline that can honor its order to check it. Measured at 1.4.0, which is the only baseline where the skip fires, the window is `de Mesnil Jean, Dr.`, `de la Cruz Juan Carlos, Dr.` and `de la Cruz née Vega` -- none carrying a row in either roster today, so the note prints on no run yet. "Do not refuse" and "say nothing" are two decisions, and only the first was ever argued.

The two CHECKS read opposite name lists, and swapping them is the live hazard. "Was this name compared?" is about the RUN, so the shape check reads the list AFTER the baseline-minimum shape skip. "Does any corpus still hold this name?" is about the FILES, and the skip empties no file, so the departed-name check reads the list BEFORE it. The note reads both, being exactly the difference: the union of the rosters intersected with the pre-skip list, minus the post-skip one. Of these, the departed-name refusal is the only one that reads `full_corpus`: the note's intersection already narrows itself under `--corpus`, and `MOVED SHAPE` never asks the flag, on either roster and in its `(radar)` form alike -- it is silent under `--corpus` only about rows whose name this run did not compare, so a narrowed run holding a pinned name still reports and, where the row is fatal, still FAILS. Measured 2026-09-03: `--corpus corpus_issues.jsonl` at 1.4.0 with a corrupted shape on `Carod i` prints `MOVED SHAPE` and exits 1 (RECOMPUTE by corrupting that row in `compare._RECORDED_DIFFS` in memory around `main()`). Do not read the departed-name suppression across to it -- a `MOVED SHAPE` from a narrowed run is a real finding, and a `full_corpus` gate added here would be a behavior change and not a restoration. `compare.py`'s comment at the note says the note parts "from the two checks that do read that flag", counting `vacant` and `gone` -- its own frame, and a different pair from the three listed here. `recorded_diff_mismatches`' docstring in `compare.py` carries the measurement and the recompute for the two lists.

### Shapes that must never be explained (`[[never]]`)

A `[[change]]` rule says "this diff is intended, and here is what
changed". There was no rule meaning "whatever happens here is a
regression", so two comments in `expected_since_1.4.0.toml` promised
exactly that in prose while rules in the same file claimed those
shapes anyway -- both false from the day they were written until #328
found them. A `[[never]]` entry is that promise made executable: it
names a shape that must stay unexplained.

An entry needs `why` -- an exclusion nobody can justify is one nobody
can safely delete -- plus `name_regex` and `examples`. The examples are
required, not decoration: a protected shape need not appear in any
corpus, so the entry has to carry its own test data. `fields` is
optional and narrows WHICH READING is protected, by the same subset
test the rules use -- but only that test. An exclusion explains no
diff, so the exactness requirement above is not asked of it.

That last key earns its keep on the ASCII pairs. Parens mark nicknames,
maiden names, suffixes and credentials alike, and no regex tells them
apart, so a name-only exclusion for the nickname promise would also
silence every diff on `Jenny (Johnson) Baker` and `Lon (Jr.) Williams`,
whose parens are a maiden name and a suffix. Nothing is hidden by that
-- an excluded name reports UNEXPLAINED, which exits non-zero -- but
those names become permanently unexplainable, so an intended change
there could never be recorded. Typographic delimiters carry no such
ambiguity, which is why `feat(#273)`'s own rule can be a bare character
class and its exclusion cannot.

The ASCII-pairs entry is narrowed by role ALONE, and covers a delimited
run in any position; how many corpus names that reaches is pinned as
its `captures` in `tests/v2/test_ledger_guards.py`'s
`_EXCLUSION_EFFECT`, which is the one place the number is checked and
so the one place it is worth reading. It was medial-only for three
rounds on the theory that trailing parens are credentials to be kept
out; 1.4.0 says otherwise, reading a trailing `(JD)` as a nickname just
as it reads `(Ben)`. Where 1.4 did read parens as a credential it put
them in `suffix`, outside this entry's `fields`, so the parser
discriminates by vocabulary where no delimiter regex could. Measured,
the widening lost zero classifications.

`classify()` consults exclusions BEFORE the rules, and a match returns
`None`, so an excluded shape reports UNEXPLAINED however many rules
would claim it. That order is also what makes exclusions monotone: an
entry only ever removes a name from classification, never moves it
between rules, so its blast radius is exactly the names it captures, on
the readings it names -- there is no rule ordering to reason about.

`tests/v2/test_ledger_guards.py` records what each entry silences and
holds it there. Asking whether a rule claims a protected shape *with*
the exclusion active answers nothing -- `classify()` returns `None`
before the rules are reached, so the answer is `None` however the rules
change. The pin therefore asks with exclusions switched OFF and records
which rules WOULD claim each protected reading. A rule widened to reach
one changes that record and fails in CI, rather than being invisible
until someone reasons about it. It records the FIRST rule matching each
subset, so a rule shadowed on every subset it claims by one already
sitting ahead of it does not move the record; a rule reaching a
protected reading does. The same record carries the number and
digest of the corpus names an entry captures, which is the opposite
drift: an over-wide exclusion silences real classifications, and that
is loud at release but otherwise silent on a push.

## What this gate does not cover

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
substring of `née`, never as a token. The convention matters because the neighbouring guard
`tests/v2/test_ledger_guards.py::_carries` deliberately asks a wider
question -- it also matches a non-ASCII entry anywhere inside a name,
since 旧姓 is written flush against the name it marks -- and under that
reading the marker count is 6, not 5: it adds `né`, which occurs only
as a substring of `née` and never as a token of its own. Both are right
about different questions. Recompute:

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
          '| _carries reading:', len(carries), sorted(carries))
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
(`rules.md#M3`), so `Jane Smith (née Jones)` needs no configuration
either. A word past the MARKER, not a second word in the clause: since
#434 a marker may be a phrase, and `Maria Kowalska (z domu)` is a
two-word clause that stays a nickname because both its words are the
marker. Row 1 is exactly the shape that still does — a markerless
clause — along with a one-word clause like `Jane Smith (Nee)`, where
nothing in the content says maiden and only a caller who knows the
data can.

It does NOT put #329 within reach of this gate, and the reason
generalizes past this one change. #329 governs what a delimited maiden
clause CONTAINS -- the marker word is dropped from the value -- while
a ledger rule narrows by which FIELDS move, never by what they hold.
The six names the 2.1.0 ledger classifies under `fix(#335)` move
`{nickname, maiden}` whether the marker is dropped or not, so that rule
absorbs a #329 regression in silence. The field sets are per baseline
and only that ledger's are uniform: at 2.0.0 the CJK name declares four
fields and has a rule to itself, and at 1.4.0 it is not a `fix(#335)`
name at all. Measured 2026-08-26 by reverting the drop pass
in `_group.py`: `Jane Smith (née Jones)` reads maiden `née Jones`, and
all three gates still report 0 unexplained. #329 was out of reach
before #335 too, for a different reason -- under the default policy no
corpus name reached the drop at all, so the movement on
`山田 花子（旧姓 佐藤）` between 2.0.0 and 2.1.0 was the East Asian order
flip rather than #329 (`decisions.md#M1`'s 2026-08-05 entry calls that
change gate-visible; the 2026-08-26 entry beside it records the
correction). Value-level coverage for both is `tests/v2/cases.py`,
whose rows assert values, and whose opt-in rows carry their own
`policy=`.
