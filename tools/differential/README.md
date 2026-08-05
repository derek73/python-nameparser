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
uv run python tools/differential/compare.py --baseline 2.0.0
```

`compare.py` spawns the worker as a subprocess, feeds it every corpus
name as a line of JSON, and diffs the two sides field by field. Every
diff is checked against that baseline's ledger:

- Matches a rule -> counted as an intentional, classified change.
- Matches no rule -> printed under `UNEXPLAINED` and the run exits 1.

An unexplained diff means either a real parity bug (fix it, don't
allowlist it) or a known change whose ledger rule needs widening. The
run must exit 0 at every baseline you claim before a release; the
classified summary it prints is the source for the "Behavior Changes"
section of `docs/release_log.rst`.

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

A rule's `fields` names roles the way `Role` does — `title`, `given`,
`middle`, `family`, `suffix`, `nickname`, `maiden` — whichever surface
the diff came from. The facade reports `first`/`last`; those are
canonicalized on the way in, and the `UNEXPLAINED` block prints the
canonical name so what you read is what you write.

## The two invocation traps the temp dir closes

Neither trap below is hypothetical -- the second was reproduced twice
while working on #320 -- and they are recorded here because the
generated worker's placement is the thing that disarms them. A later
change that moves the worker back inside the worktree, or invokes it
from a cwd inside the project, reopens both. The analysis is the
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

## The three corpora

`compare.py` reads **every** `corpus*.jsonl` beside it by default
(deduped), because a corpus you have to ask for by name is a corpus
that stops being run. Pass `--corpus PATH` (repeatable) to narrow it.

| File | Source | Blind to |
|---|---|---|
| `corpus.jsonl` | v1's own test suite at a pinned ref | anything 2.0 added — v1's authors had no reason to test a typographic nickname delimiter or a Cyrillic title |
| `corpus_issues.jsonl` | name-like strings harvested from the GitHub issue tracker | anything nobody ever reported |
| `corpus_cjk.jsonl` | the CJK-bearing rows of `tests/v2/cases.py`, via `build_cjk_corpus.py` (#295) | anything the case table itself missed — it re-witnesses reviewed expectations at the baseline boundary rather than discovering new shapes |

They are deliberately separate rather than merged: `corpus.jsonl` is
reproducible forever from an immutable git ref, while the issue
tracker is mutable, so regenerating `corpus_issues.jsonl` is an
explicit, reviewable act that can only add names — and the CJK corpus
exists because BOTH of those are structurally blind to unspaced CJK (v1's
banks never tested it; `build_issues_corpus.py` requires an internal
space, which unspaced names never have). It regenerates from the case
table, and `tests/v2/test_regex_sync.py` pins the checked-in file
against the generator's selection, so a CJK case row added without
regenerating fails the suite instead of silently narrowing this gate.

The issue corpus earned its place on the first run — 166 of its 198
names were not in `corpus.jsonl`, and it immediately surfaced five
intended-but-unclassified 2.0 behaviors (#273 typographic delimiters,
#269 non-Latin vocabulary) plus one shape no test had considered: a
**leading** `"Ph. D."`, which v1 split into title `Ph.` + given `D.`.

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
`HumanName(...)`'s first argument, plus string members of module-level
list/dict/tuple banks that contain a space) -- more candidate strings
is more coverage, and the corpus is deduplicated. Obvious non-names
(strings containing `{`, `@`, or a backslash -- format placeholders,
decorator/email-shaped fixtures, escape sequences) are dropped.

Regenerate the corpus only if the v1 test banks are revisited again at
a still-earlier point in history; otherwise leave the checked-in file
alone so the harness stays comparable run to run.

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

## The ledgers (`expected_since_<VERSION>.toml`)

One ledger per baseline, so each release's classified changes stay as
history rather than being edited into the next one's.

Each `[[change]]` entry needs `issue` (a short label, ideally an
issue number or `fix(<slug>)` matching a `tests/v2/cases.py`
classification) and may narrow its match with `name_regex` (searched
against the raw input string) and/or `fields` (the diffing rule
matches only if the observed diff fields are a subset of this list).
Keep both as tight as the actual diff allows -- a loose rule can mask
a real regression.

Rules are sorted most-specific-first before matching -- a `name_regex`
rule outranks a `fields`-only one (which is broad by construction)
wherever both match -- so file order does not decide which rule claims
a diff.

Some entries in the seed list are for behavior families that a
particular corpus happens not to contain any example of (e.g. custom
suffix-delimiter rendering, which only fires under a non-default
`Policy` -- see the ceiling below). They're kept in the file anyway,
matching the family documented in `tests/v2/cases.py`, so the rule is
ready the moment a matching string is added to the corpus.

## What this gate does not cover

The corpora run under the **default policy**, so any behavior gated
behind a non-default `Policy` field is invisible here. Default
*vocabulary*, by contrast, is fully exercised.

Two independent mechanisms put a birth surname in `maiden`, and only
one is opt-in (measured 2026-08-05):

| input | default policy | `maiden_delimiters={("(", ")")}` |
|---|---|---|
| `Jane Smith (Jones)` | nickname `Jones` | maiden `Jones` |
| `Jane Smith née Jones` | maiden `Jones` | maiden `Jones` |

Row 1 carries no marker word, so it isolates the delimiter: the
brackets alone route their content to `maiden`, and only once the
policy says they do. Row 2 carries no brackets, so it isolates the
marker: `Lexicon.maiden_markers` ships 17 entries by default, `nee`
among them, and the bare form needs no configuration at all.

So what is opt-in is not the marker words — it is only the delimited
path. #329 changed what happens when both are in play (the marker
inside a delimited clause is now dropped from the value), and this
gate cannot see it, because the corpora never configure the delimiter.
Opt-in behavior is covered by `tests/v2/cases.py`, whose rows carry
their own `policy=`.
