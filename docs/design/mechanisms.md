# Mechanisms

How this codebase solves recurring problem shapes. Before proposing
a design, check whether an entry already fits — the catalog is keyed
by problem shape, because that is what you have in hand when
searching.

Entry format: an `## UPPER-KEBAB-SLUG — one-line slogan` heading,
then **Problem shape** (the situation that should trigger recall),
**Contract statement** (one or two sentences stating what the
mechanism promises — the citable line), **How it works**, **Lives
in**, and **Reach for it when** (the tell-tale sign you should be
using this instead of inventing something).

The Contract statement is citable under the same discipline as
rules: a committed comment making a mechanism claim — including any
claim about which stage or layer does something — cites the slug and
quotes a verbatim excerpt (`# mechanisms.md#SPANS: ...`), checked by
the citation-integrity test. Free-prose restatements of mechanism
claims are how one wrong sentence has shipped six times.

This catalog converts discovery into a one-time cost — it does not
remove discovery. What nobody knows yet still has to be found the
hard way, once; the promise is that found things stay found.

## SPANS — position is identity, text is not

Problem shape. A later stage needs to refer to "that word."
Contract statement. Every token carries its (start, end) character
span in the original string, and stages refer to tokens by index,
never by searching for matching text.
How it works. v1 re-found pieces by value, so a name with a repeated
word could rewrite the wrong occurrence (#100 and relatives); a
position cannot be confused with a look-alike. Every parsed part is
an exact slice of the input (rule T1's Background).
Lives in. nameparser/_types.py (Span), threaded through every
_pipeline/ stage.
Reach for it when. New code is about to do `if token.text == ...` to
LOCATE rather than to classify.

## FOLDED_TAG — reorder at render time, not parse time

Problem shape. A rule wants words to RENDER in a different order
than they sit in the string.
Contract statement. Tokens never move: a rule that needs different
rendering order tags the token, and the rendering views consult the
tag — family views order folded tokens first.
How it works. Reordering the token tuple would break span math and
reintroduce the #100 family. Parse state stays in string order; only
the view reorders (rule R1, rule O3's render clause).
Lives in. nameparser/_types.py (FOLDED_TAG, the family view),
nameparser/_pipeline/_post_rules.py (the one producer today), and
one deliberate CONSUMER-side strip: Parser.revise removes the tag
from harvested tokens (a revised value must not inherit fold
ordering) — losing that strip is this mechanism's measured hazard,
a family rendering "García Gabriel Márquez".
Reach for it when. A new rule needs "X renders before Y" and you are
tempted to swap tokens. Don't swap. Tag.

## VOCAB-TAGS — the vocabulary layer speaks once

Problem shape. A later stage needs to know what the vocabulary knew
about a word.
Contract statement. classify tags every token with what the
vocabulary knows about it, and later stages test tags — they never
re-look a word up.
How it works. One lookup site means one answer: a stage that
re-derived vocabulary facts could disagree with the stage before it.
Stable tags ("particle", "conjunction", "initial") are API;
"vocab:"-namespaced ones are not.
Lives in. nameparser/_pipeline/_classify.py (producer); consumers
throughout _group/_assign/_post_rules.
Reach for it when. A stage is about to import Lexicon to ask about a
word classify already saw.

## PIECES — joining structure survives assignment

Problem shape. A rule needs to know how words were JOINED (chained
titles, particle groups), not just what roles they got.
Contract statement. group records the joining structure as pieces —
runs of token indices per segment — and that structure remains
readable after roles are assigned.
How it works. Roles alone lose the grouping ("who chained with
whom"); #359's fix made the particle fold read the opening PIECE
rather than the assigned role, which is what makes rule P1 hold
under every name_order.
Lives in. nameparser/_pipeline/_group.py (producer),
_pipeline/_state.py (ParseState.pieces), _post_rules.py (reader).
Reach for it when. A rule keyed on assigned roles behaves
differently under different name_order values — the stable thing to
read is usually the structure.

## STRUCTURE-GATES — comma shape as an explicit state

Problem shape. A rule should fire only under one comma convention.
Contract statement. segment decides the comma structure once
(NO_COMMA, FAMILY_COMMA, SUFFIX_COMMA) and every later stage gates
on that single decision rather than re-inspecting commas.
Lives in. nameparser/_pipeline/_state.py (Structure),
_pipeline/_segment.py (the one decider).
Reach for it when. New code is about to count commas.

## TWO-LAYER-ASSIGN — vocabulary claims, position takes the rest

Problem shape. Where should a new "recognize X" behavior live?
Contract statement. A vocabulary layer first claims words for what
they ARE, wherever they sit; a positional layer then reads every
unclaimed word by where it STANDS. Every rule belongs to exactly one
layer — with one named exception: the leading-abbreviation shape
(rule H2) fires before the suffix vocabulary is consulted, so
"Esq. Smith" reads title, not suffix.
How it works. The two layers compose without ordering bugs because
the positional layer never overrides a vocabulary claim (rule O4 is
the positional layer's contract).
Lives in. _classify/_group (vocabulary side), _assign (positional
side).
Reach for it when. A proposed rule wants a word's identity AND its
position at once — split it, or it will fight both layers.

## STATE-OFFSET-CHANNELS — early facts ride the state

Problem shape. A fact known during tokenization matters to a much
later stage.
Contract statement. A pre-token fact is recorded as offsets on the
ParseState (comma_offsets, interpunct_offsets) and consulted later
by position — or by presence alone where the fact is name-level, as
both interpunct consumers do — rather than re-derived from text.
How it works. The offsets survive every intermediate stage
untouched; #298's transcription marker rides this channel from
tokenize to order resolution (rules T3/W4).
Lives in. nameparser/_pipeline/_state.py, produced in _tokenize.
Reach for it when. You are about to re-scan the original string in a
late stage to rediscover something tokenize already knew.

## PIPELINE-STAGE-CONTRACTS — the ownership map

Problem shape. "Which stage does X?" — asked before attributing
behavior in prose, comments, or fixes.
Contract statement. Each stage's docstring header declares what it
consumes, produces and reads, and ParseState's docstring holds the
cross-stage map, pinned by tests/v2/pipeline/test_state.py.
How it works. A claim about which stage or layer does something is
CHECKABLE — `parse(s).tokens` prints every token's role and tags —
so check it before writing it; one plausible attribution sentence
once shipped six times wrong (AGENTS.md's stage-attribution note).
Lives in. nameparser/_pipeline/_state.py and every stage header.
Reach for it when. Writing any sentence of the form "X happens
before Y sees it."

## CLAUSE-CONTENT-OVERRULES-DELIMITER — content wins

Problem shape. A bracketed clause should be treated as something
other than what its delimiter pair says.
Contract statement. extract may inspect a clause's content against
the lexicon and, when it matches, mask only the two delimiter spans
so the inner content rejoins the main token stream for ordinary
downstream parsing.
How it works. "Andrew Perkins (MBA)" is not a nickname (rule S1):
the parens are masked away and MBA is classified by the normal
machinery — reusing the downstream path, so the delimited and bare
forms cannot drift.
Lives in. nameparser/_pipeline/_extract.py (_suffix_shaped and the
inner-span branch).
Reach for it when. About to add a second code path that duplicates
what the bare form already does — #335's fix is this shape (a
_maiden_marked sibling predicate).

## CURATED-VOCABULARY-ALTERNATION — the config already splits them

Problem shape. Two string shapes collide — the same written form
means two different things — and no predicate separates them.
Contract statement. A curated vocabulary that OMITS the ambiguous
entries is itself the separator: membership is the license, and the
per-entry vetting reasons live beside the set.
How it works. GLUED_HONORIFICS is the exemplar (rule W2): 씨 peels
because it can never end a name; 양 stays out because 김지양 is a
given name. The set, not a regex, draws the line.
Lives in. nameparser/config/suffixes.py (the vetting block).
Reach for it when. Arguing that "no regex can separate X from Y" —
check whether a config set already splits them by listing one side.
The second half of the pattern: to USE the set in a regex, hand-copy
the alternation and pin the copy with a sync roster
(_HONORIFIC_SOURCES) — the 2.0.0 ledger has done exactly this since
#308, which is why #376's fix was copying its twin verbatim rather
than inventing one.

## RECORDED-ROSTERS — record the answer, don't re-derive it

Problem shape. A guard needs to know what the answer WAS, so it can
detect the answer changing.
Contract statement. Store the measured answer as literal data (a
roster) and compare against it; never re-derive the expectation from
the same inputs the check reads, because a derivation from the same
data always agrees with itself.
Lives in. tests/v2/test_ledger_guards.py (_CORPUS_CLAIMS,
_EXCLUSION_EFFECT, _CROSS_RULE_WINNERS, _SPAN_BEARING_RULES,
_HONORIFIC_SOURCES, _LATIN_ALTERNATION_SOURCES),
tools/differential/compare.py (_CORPUS_FLOORS),
tests/v2/test_facade_cases.py (_CORE_ONLY_IDS).
Reach for it when. Writing a check whose expected value is computed
by the code under test, or a comment that enumerates ids/counts —
make it data the suite asserts.

## LEDGER-RULE-SEPARATION — fields separate rules, file order doesn't

Problem shape. Two differential-ledger rules claim overlapping
names.
Contract statement. Fields subsets and matching predicates separate
ledger rules BETWEEN tiers; within a tier, file order decides and
the narrower rule must be written first. A fields-only rule sorts
last unconditionally and takes what nothing narrower named.
How it works. Detail is owned by tools/differential/README.md. The
within-tier clause is measured, not theoretical: in the 1.4 ledger
the comma-honorific-peel rule's fields are a strict subset of the
comma-compound rule's, both carry a name_regex, and a pure reorder
reattributes seven names — caught by _CROSS_RULE_WINNERS and by
nothing else in the suite (#375's mutation). Whether that pair
should be separated by a predicate instead of by order is
[#382](https://github.com/derek73/python-nameparser/issues/382). One standing constraint worth repeating
here: sync-pinned rosters select rules by issue-string substring, so
a new rule's issue slug must avoid the literal #271/#272 substrings
unless it means to be selected.
Lives in. tools/differential/compare.py, the expected_since_*.toml
ledgers.
Reach for it when. A ledger rule's behavior seems to depend on where
it sits in the file — within a tier it does, and the reorder
mutation is the test (run twice in #375; it fails
_CROSS_RULE_WINNERS). History: #372 (closed) measured the
fields-only rule owning 1639 of 5257 name×field pairs as filed
(2026-08-10); #375/#376 then cut its classifier-of-record share
sharply, and the residual pair ownership is the last-resort tier
working as designed, not a defect. #372's two proposed mechanical
checks were DECLINED with measurements (see
decisions.md#differential-ledger), not left open.

## CANONICAL-VOCABULARY-AT-THE-BOUNDARY — one vocabulary at the comparison

Problem shape. Two surfaces name the same concept differently
(first/last vs given/family), and a matcher needs to compare across
them.
Contract statement. Canonicalize at the point of comparison: every
compared surface's output is converted to one vocabulary before
matching, and the canonical choice is the one the codebase already
derives everywhere else.
How it works. Teaching the matcher both vocabularies doubles every
rule silently; canonicalizing means existing rules keep matching
when a second surface joins. The ledger canonicalizes v1 field
names to Role's before matching.
Lives in. tools/differential/compare.py (_canonical_field,
_V1_TO_ROLE).
Reach for it when. A second surface joins an existing matcher —
without this, every existing rule silently stops matching the new
surface, which looks like added coverage.

## VOCABULARY-OVERLAP-AS-PRECONDITION — assert the intersection you stand on

Problem shape. A test's input depends on two config sets
intersecting (a word that is both a title and a particle), and a
vocabulary edit could quietly unground it.
Contract statement. Assert the intersection as a precondition and
distinguish the two failure modes: word moved (pick another member;
the message prints what is left) versus intersection empty (the
code under test is unreachable — delete it rather than repointing
the test).
Lives in. tests/v2/test_parser.py
(test_the_chained_emitter_is_still_reachable).
Reach for it when. Any config-coupled fixture — a test input chosen
because of what a vocabulary happens to contain.

## CROSS-RULE-OUTCOME-PINS — pin who wins the contest

Problem shape. Every per-rule roster measures a rule alone and the
gate total is per-corpus, but WHICH rule wins a contested name is
neither — and it is exactly what a reorder or a narrowing changes.
Contract statement. Contested outcomes are pinned as data: a roster
records which rule classifies which contested name, so a change in
the winner fails the suite even when every total is unchanged.
How it works. A pure file reorder in the 1.4 ledger fails
_CROSS_RULE_WINNERS and nothing else in the suite — the pin is the
only guard at that granularity.
Lives in. tests/v2/test_ledger_guards.py (_CROSS_RULE_WINNERS).
Reach for it when. Two rules can claim the same name and you are
about to change either one, or their order.

## VOCABULARY-FEEDS-STRUCTURE — a wordlist edit can move the comma decision

Problem shape. Editing suffix vocabulary looks field-local, but the
comma-structure decision (rule C1) reads that vocabulary, so a
removal can flip which segment is the family name.
Contract statement. Suffix-set membership is an input to the
structure decision: removing a word from the suffix vocabulary can
change a suffix-comma name into a listing-form name, relocating the
family.
How it works. Measured in the comma-suffix arc: dropping "dr" from
the suffix vocabulary flips "John Smith, Dr." from family="Smith"
suffix="Dr." to family="John Smith" — three individually correct
documented facts composing into a family-name loss.
Lives in. nameparser/_pipeline/_segment.py (the C1 decision) reading
the suffix sets through _vocab.is_wholly_suffix.
Reach for it when. Editing suffix membership for any word that
occurs after a comma in real data — check the structure flip, not
just the field.

## WARN-AT-THE-CALLER — walk out of the library, don't count frames

Problem shape. A warning should point at the caller's code, but the
entry depth varies (constructor, add(), unpickle,
dataclasses.replace, the shim snapshot), so any fixed stacklevel
lands on library internals for most paths.
Contract statement. The warner walks the stack outward until the
first frame outside the library's own modules and warns there,
instead of counting frames.
Lives in. nameparser/_lexicon.py (_warn_dead_entry), and the
related but distinct per-read-location choice is in the #293/#354
bridge (decisions.md#3-0-reevaluations).
Reach for it when. Adding any warning reachable through more than
one public entry point.

## LEGACY-STATE-SIGNATURE — subtract legacy defaults only as a complete set

Problem shape. A retired default rides in on old pickles, but a
user may have deliberately re-added one of the same entries.
Contract statement. Known-dead legacy defaults are subtracted from
restored state only when the state carries ALL of them — the
complete pre-retirement signature — so real legacy blobs clean up
silently while a deliberate single re-add survives round-trips.
Lives in. nameparser/_lexicon.py / _config_shim.py
(_LEGACY_DEAD_ENTRIES).
Reach for it when. Retiring any default vocabulary entry that
existing pickles may carry.

## AMBIGUITY-AT-THE-DECISION-SITE — emit where the branch is taken

Problem shape. An ambiguity report should fire exactly when the
parse chose between live readings — no more, no less — and the
choosing happens in code, not in vocabulary.
Contract statement. Emit at the site that takes the branch, not
where an ambiguous tag sits; when a fork's two branches are decided
in different stages, EVERY deciding stage carries an emitter; and a
branch that runs but changes nothing is not a decision and must not
report.
How it works. PARTICLE_OR_GIVEN fires from assignment for a lone
leading particle and from grouping when a title shifts it off the
front — for two years only the first site emitted. And keying on
"the code got here" instead of "the outcome differed" once reported
a fork for all 39 ambiguous particles on "Dr. Van Jr.".
Lives in. The AmbiguityKind emitters across _pipeline/ (rule A1 is
the observable contract).
Reach for it when. Adding any ambiguous vocabulary or any new fork
— count the deciding sites, then count the emitters.

## MAKE-WRONG-STATES-UNREPRESENTABLE — the house meta-pattern

Problem shape. A convention keeps being violated no matter how
clearly it is written down.
Contract statement. Convert the consistency problem into a
referential-integrity problem: make the wrong state impossible to
express, or mechanically checked, rather than merely documented.
How it works. Three instances built this documentation system:
_CORE_ONLY_IDS replaced an enumerating comment; verbatim-excerpt
citations replaced paraphrase; no-boundary: markers replaced silent
omission. The executable examples in rules.md are the same move at
document scale.
Lives in. tests/v2/test_doc_citations.py, tests/v2/test_rules_doc.py,
and every recorded roster.
Reach for it when. Tempted to write "remember to keep X in sync
with Y."

## LOCALE-PACKS-PURE-DATA — packs configure, they never compute

Problem shape. Language-specific behavior needs a home that cannot
drift from the core.
Contract statement. A locale pack is pure data — a Policy patch and
Lexicon ADDITIONS, add-only: a pack unions vocabulary in and can
never remove a base entry — applied by parser_for; packs contain no
code paths of their own, and each pack's docstring declares its
deviations from the defaults.
How it works. What is policy for every language (an order constant)
is policy, not pack data; packs are lowercase modules exposing
uppercase constants; a pack error is wrapped with the pack's code
(rule D2). Pure data means a pack can be audited by reading it —
and add-only means a bad DEFAULT can never be routed around by a
pack, which is why #342-class fixes must change shipped
vocabulary.
Lives in. nameparser/locales/ (packs), nameparser/_parser.py
(parser_for, the one applier).
Reach for it when. A language fix wants an if-statement — make it
vocabulary or policy in a pack instead.

## FACADE-CONTRACT — HumanName wraps the core; 1.4-warning-free code keeps working

Problem shape. Where does v1-compatibility behavior live, and what
may it do?
Contract statement. HumanName is a mutable facade over the immutable
core: code that runs warning-free on 1.4 keeps working through 2.x
with identical results EXCEPT release-log-classified fixes, each
verified in the differential ledger (the RFC's compatibility promise
carries the same carve-out) — via validating setters, dirty-tracked
re-parses, and pickle round-trips — and the facade never calls the
v1 parsing hooks it still carries. "Warning-free" describes the
code's 1.4 behavior, not a promise it STAYS warning-free: 2.x adds
deliberate warnings (the multi-word-vocabulary and field-assignment
ones), each release-log-classified, always with identical results.
Lives in. nameparser/_facade.py; v1 import paths preserved by
nameparser/parser.py and nameparser/config/.
Reach for it when. A core change needs a v1-visible behavior —
the facade, not the core, is where parity lives (and cite
decisions.md#3-0-reevaluations when parity is the only reason).

## CONFIG-SHIM-SNAPSHOT — v1 config mutations reach the core by snapshot

Problem shape. v1 code mutates CONSTANTS at runtime; the core is
immutable.
Contract statement. nameparser.config re-exports mutable managers
whose contents are converted to immutable core objects through a
dirty-tracked snapshot: mutations mark the snapshot stale, and the
next parse rebuilds it, so v1 mutation semantics survive over an
immutable core.
Lives in. nameparser/_config_shim.py, nameparser/config/.
Reach for it when. Wiring any new v1 config surface — it must go
through the snapshot, never sideways into a Lexicon.

## Verification shapes

How to measure in this codebase without fooling yourself. The
inert-measurement class — checks that run, print plausible results,
and measure nothing — has recurred double-digit times; these shapes
are its known antidotes. Convention (AGENTS.md): guard tests SHOULD
carry a RECORDED negative control, the _EXCLUSION_EFFECT shape — the
answer with the guard off, stored as data. Honest limit, precisely drawn: these
reduce the inert-measurement class. Mutation testing reaches part
of the wrong-predicate class too — mutating the thing a guard
watches exposes a guard that never depended on it (the #329
survivors: deleting the tag check left the suite green while every
multi-word maiden clause lost its first word, after adversarial
review had passed that code twice) — but a predicate wrong in a way
the fixture happens to satisfy still needs adversarial review.

### VERSION-TELL — know who answered

Contract statement. A subprocess that speaks for a pinned version
writes its __version__ and __file__ as its first output line, and
the caller aborts before comparing anything if either half disagrees
with what was requested.
Both halves are load-bearing: an editable install reports the tree's
version (agreement proves nothing when tree and baseline share a
number); a genuine wheel at the wrong version passes any path check.
Lives in tools/differential/compare.py (_check_tell).

### GENERATED-SCRIPT-OUTSIDE-THE-WORKTREE — escape the shadow

Contract statement. A worker that must run under a pinned dependency
is rendered to a temp directory outside the worktree and spawned by
absolute path, so sys.path[0] contains no copy of the package and
the inline pin is genuine.
Sentinel substitution (@@VERSION@@), not str.format — the worker
body is mostly literal braces. Lives in
tools/differential/compare.py (_worker_source, _run_worker).

### SENTINEL-SET-OVER-MATCH-CHECK — catching match-everything

Contract statement. A user-supplied pattern is rejected as
over-matching by probing it against a small set of inputs sharing no
script, vocabulary or punctuation; matching all of them means it
targets no behavior family.
Measured: `.`, `.+`, `\b` and `[\s\S]` all decline the empty string
— the naive probe — and still match every corpus name. Lives in
tools/differential/compare.py (_SENTINELS).

### FORCE-A-DECISION-TABLE — no silent defaults on growth

Contract statement. Where adding an enum member or a file must not
silently inherit a default, a local table's key set is asserted
equal to the population, so growth fails the suite until someone
decides — against a local table, not the constant under test.
Exemplar: tests/v2/pipeline/test_vocab.py's per-script initials
check; reused for _CORPUS_FLOORS in tools/differential/compare.py,
and for the pack registry (test_registry_is_the_pack_contract:
every registered pack must ship DEVIATES and its rotator list or
the suite fails structurally — decisions.md#deviates-registry).
Known gap it exposes: DEFAULT_SCRIPT_ORDERS has no such guard.

### SELF-EXPIRING-GUARD — a decline keyed to a measured defect

Contract statement. A workaround keyed to a third-party library's
measured defect carries a canary test that pins the defect itself,
so the workaround cannot outlive its reason: when the library fixes
it, the canary fails and the decline gets revisited rather than
fossilizing.
Exemplar: tests/v2/test_locales.py's namedivider shime canary pins
0.4.x cutting 〆木太郎 at offset 1 with confidence 1.0, guarding the
adapter's 〆 decline (#303 arc); its comment says to revisit the
decline, not delete the test.

### Field notes — the traps themselves

- Assert which tree you imported, on BOTH sides of a comparison.
  `python -c` puts CWD on sys.path; a script's own directory holds
  no nameparser in tools/differential/, so a stray PYTHONPATH
  outranks the editable install — measured: 89 diffs became 0, exit
  0, both tell halves passing, because both sides had become the
  shadow.
- Never pipe a gate's output. Under zsh, `compare.py | tail` makes
  `$?` tail's status. Redirect to a file and read the file.
- Mutation-test a new guard before believing it, and mutate the
  thing the guard watches — a survivor usually means the fixture
  satisfies the invariant for free.
- Verify the restore, not just the mutation: diff against the
  pre-mutation copy; do not trust the harness's own restore report.
- Run all the gates, not the ones you remember: ruff runs before
  mypy and pytest in CI, and each has caught what the others
  passed.
- Purge __pycache__ between same-length source mutations; stale
  bytecode makes a changed file measure as unchanged.
- After NARROWING a rule, check the receiver: the names a narrowed
  rule sheds land on a neighbour, and nothing guarantees the
  neighbour's prose describes what it inherited — #375 fixed an
  over-claiming rule and relocated the bug onto its neighbour.
- A skip is indistinguishable from "correctly declined": pytest
  turns an empty parametrize into a skip, and a filter that widens
  its own skip set cannot fail. After changing any selection shape,
  verify the guard still REACHES the code it watches — assert the
  selected set is non-empty, or force-a-decision on its size.
- A differential corpus cannot evidence behavior keyed to
  OUT-of-vocabulary shapes: it holds only names someone wrote
  down, and an unrecognized word is by definition outside the
  vocabulary — a green run over the corpus proves nothing about
  such a rule.
- Guard the whole family, parametrize over it: a defect on one of
  N parallel entry points hides behind a per-example test — three
  times in one session (a guard on one class of two, a decode hint
  on 3 of 5 entry points, a sync roster missing 4 copies) — and a
  {class}×{field}×{bad-value} parametrization is what caught each.
- A growth guard needs calibration, not just existence: benchmark
  guards that compare n vs 4n catch the quadratic the absolute-time
  tests are blind to, but calibrate against the WEAKEST signal you
  must detect and confirm a planted regression fails across
  repeated runs, not once — a stochastic check "verified" on one
  sample verifies nothing.
- Mind the optional-extra environment split: a local venv's
  incidental namedivider makes `if available` branches run PRESENT
  locally and ABSENT in CI, so a locally-green suite proves nothing
  about the no-extra path (this broke #337's first landing). Run
  the decisive check in both states or gate the example.
