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

**Both** sides are proved, not just the baseline. `compare.py` also
checks that its own `nameparser` is this checkout's source package and
prints it on a `tree:` line — see the third trap below for why a bare
import was not enough.

A rule's `fields` names roles the way `Role` does, whichever surface
the diff came from, plus the pseudo-field `_ambiguities` for a change
in reported `AmbiguityKind`s. The roster is not restated here: it is
`Role`'s members, `validate_rules` rejects anything outside them, and
a copy in prose is a copy that goes stale when a role is added. The
facade reports `first`/`last`; those are canonicalized on the way in,
and the `UNEXPLAINED` block prints the canonical name so what you read
is what you write.

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

## The three corpora

`compare.py` reads **every** `corpus*.jsonl` beside it by default
(deduped), because a corpus you have to ask for by name is a corpus
that stops being run. Pass `--corpus PATH` (repeatable) to narrow it.

| File | Source | Blind to |
|---|---|---|
| `corpus.jsonl` | v1's own test suite at a pinned ref | anything 2.0 added — v1's authors had no reason to test a typographic nickname delimiter or a Cyrillic title |
| `corpus_issues.jsonl` | name-like strings harvested from the GitHub issue tracker | anything nobody ever reported |
| `corpus_cjk.jsonl` | the CJK-bearing rows of `tests/v2/cases.py`, via `build_cjk_corpus.py` (#295) | anything the case table itself missed — it re-witnesses reviewed expectations at the baseline boundary rather than discovering new shapes |
| `corpus_rules.jsonl` | every example in `docs/design/rules.md`, via `build_rules_corpus.py` (#414) | anything the rules doc has no example for — it re-witnesses the normative examples at the baseline boundary |

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
appears in no name across all four corpora, and accounts for three
error messages and a PyPI trove classifier), and a short list of English function words
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

Rules are sorted most-specific-first before matching: a `name_regex`
rule outranks a `fields`-only one (which is broad by construction)
wherever both match. **Within a tier, file order decides.** That is
not a detail -- every rule in `expected_since_2.0.0.toml` carries a
`name_regex`, so they all sit in one tier and the order they are
written in settles every tie between them. Append a rule to the bottom
of a file only after checking that nothing above it already claims the
diff you meant it for.

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
that has a ledger with rules -- a ledger left out of the checklist gets no
dynamic dormancy check at all, and a `dormant` declaration in it goes
unaudited. Adding a new ledger means adding its baseline to the checklist.

The static tier still exempts a rule on the mere PRESENCE of `dormant`; it
never asks whether the reason is still true. Only the dynamic check can
catch a `dormant` that quietly stops being true, which is why every ledger
with rules needs one.

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
test the rules use.

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
run in any position -- 34 corpus names. It was medial-only for three
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
names = [json.loads(l) for f in glob.glob('tools/differential/corpus*.jsonl') for l in open(f, encoding='utf-8') if l.strip()]
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
