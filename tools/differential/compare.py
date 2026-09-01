"""Differential harness: a released baseline vs
the working tree over the corpora. Every diff on a CONTRACT corpus
must classify against that baseline's ledger or the run fails; a
RADAR corpus reports its unmatched diffs instead of failing on them.
A `[[never]]` exclusion is fatal on EITHER tier -- it was chosen, the
same way a rule was, so it belongs to the contract regardless of
which corpus the name it refuses happens to sit in.

    uv run python tools/differential/compare.py [--baseline VERSION]

--baseline 1.4.0 answers the v1 compat contract; the default answers
what changes for a user upgrading from the previous minor.

Redirect to a file rather than piping: under zsh, `| tail` replaces the
exit code with tail's, so a failing run reads as a passing one.
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import tempfile
import tomllib
from collections import Counter
from pathlib import Path
from typing import Literal, NamedTuple

HERE = Path(__file__).resolve().parent
FIELDS = ("title", "first", "middle", "last", "suffix", "nickname",
          "maiden")

DEFAULT_BASELINE = "2.2.0"
REPO_ROOT = HERE.parents[1]
#: The v2 API's names for the same seven roles FIELDS names in v1
#: vocabulary. Both are compared from baseline 2.0 on.
V2_FIELDS = ("title", "given", "middle", "family", "suffix", "nickname",
             "maiden")
#: The two roles the FACADE names differently from Role. Diffs from
#: both surfaces canonicalize to Role's names before classification, so
#: a ledger rule names a role once -- and names it the way the codebase
#: already does everywhere else (AGENTS.md, "canonical field order").
#: The facade's vocabulary is the one that expires, at 3.0.
_V1_TO_ROLE = {"first": "given", "last": "family"}

#: An unclassified diff, carrying BOTH surfaces' before/after:
#: (name, old_facade, new_facade, old_v2, new_v2, order). Both halves
#: are kept because a diff can exist on the v2 surface alone, and a
#: report that named such a diff without showing it would be
#: unactionable. `order` rides along so the report can say which
#: order produced the diff -- None for the default order.
_Unexplained = tuple[str, dict[str, str], dict[str, str],
                     dict[str, object], dict[str, object], str | None]


def _parse_version(text: str) -> tuple[int, int, int]:
    """The numeric release tuple, padded to three parts. Every version
    comparison in this file goes through it.

    Explicit because string comparison is wrong twice over here: it
    orders '1.4.0' < '2.0.0' by luck and would misorder a future
    '10.0.0', and it would call a requested '2.0' unequal to a wheel
    reporting '2.0.0' -- turning a correct run into a spurious tell
    mismatch, which is an abort on a run that was fine.

    A prerelease segment is ignored: '2.0.0rc1' is release (2, 0, 0),
    because what is being asked is which RELEASE answered.
    """
    m = re.match(r"\s*(\d+)(?:\.(\d+))?(?:\.(\d+))?", text)
    if not m:
        raise SystemExit(
            f"cannot parse a version from {text!r}: expected a numeric "
            f"release like '2.0.0'")
    major, minor, micro = (int(p) if p else 0 for p in m.groups())
    return (major, minor, micro)


def _surfaces_for(version: str) -> frozenset[str]:
    """Which output surfaces a baseline can be compared on.

    1.4 has no v2 API, so a pre-2.0 baseline compares the facade
    alone. From 2.0 on both are compared: the v2 API is the primary
    surface for 2.x users, and its ambiguity kinds catch a change the
    field diff cannot see -- a parse that starts or stops reporting
    SEGMENTATION while every field stays byte-identical.
    """
    if _parse_version(version) >= (2, 0, 0):
        return frozenset({"facade", "v2"})
    return frozenset({"facade"})


def _allowlist_for(version: str) -> Path:
    """The ledger for a baseline, one file per baseline so each
    release's classified changes stay as history.

    A missing file is a hard error rather than an empty rule set: an
    empty set classifies nothing, so every diff reports UNEXPLAINED and
    the run reads as a catastrophic regression instead of as a missing
    file.
    """
    path = HERE / f"expected_since_{version}.toml"
    if not path.exists():
        raise SystemExit(
            f"no allowlist for baseline {version!r}: expected {path}. "
            f"Create it before running this baseline -- an absent "
            f"ledger cannot classify anything, so every diff would "
            f"report as unexplained.")
    return path


_SHAPES_PATH = Path(__file__).resolve().parent / "shapes.py"


def _load_shapes() -> dict:
    """SHAPES from shapes.py beside this script, loaded by path so it
    works both run-as-script and under tests' load_tool. Resolved
    against the script's own directory, not HERE: shapes.py is code,
    not corpus data -- a --corpus override or a test's HERE patch must
    not change which inventory loads."""
    spec = importlib.util.spec_from_file_location(
        "differential_shapes", _SHAPES_PATH)
    assert spec is not None and spec.loader is not None, _SHAPES_PATH
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SHAPES


def _sorted_rules(rules: list[dict[str, object]]) -> list[dict[str, object]]:
    """Most-specific-first: a name_regex rule outranks a fields-only
    rule wherever both match, so file order does not decide BETWEEN THE
    TIERS.

    Within a tier it still decides everything, because the sort is
    stable. That is not a footnote: every rule in
    expected_since_2.0.0.toml carries a name_regex, so they all sit in
    one tier and the order they are written in settles every tie among
    them -- three names match both honorific rules and are labelled by
    whichever comes first.

    SINCE #451 THAT IS EVERY LEDGER, and this function is the identity
    on all of them. validate_rules now rejects a rule carrying `fields`
    and no `name_regex`, which is the only shape that could occupy the
    second tier -- so no ledger that loads can reach it, and file order
    settles every tie there is. Verified against all three shipped
    ledgers at the time of writing.

    Kept rather than deleted, deliberately. It is the defence that
    makes the ban SAFE to state: a ledger read by anything that does
    not call validate_rules first -- a future tool, a REPL session, a
    test fixture -- still gets the tier ordering rather than silently
    letting a regexless rule shadow the file. Deleting it would move
    the guarantee from the code into a convention, which is the trade
    #451 was filed to undo.
    """
    return sorted(rules, key=lambda r: not isinstance(r.get("name_regex"), str))


_WORKER_TEMPLATE = '''\
# /// script
# requires-python = ">=3.9"
# dependencies = ["nameparser==@@VERSION@@"]
# ///
"""GENERATED by tools/differential/compare.py -- edit the template
there, not a copy of this.

Writes a VERSION TELL as its first stdout line, then one result per
input entry. The tell exists because the alternative failure is
invisible: a worker that silently resolved to the checkout answers
every query as the working tree while the run is labelled with the
baseline, so every diff vanishes and the run reports parity -- the
precise opposite of the truth.

Input lines are {"name": ..., "order": null | "<CONSTANT>"}. An order
names a public nameparser constant; only workers whose baseline
supports it are ever sent one (compare.py skips below the shape's
min_baseline), and an order-bearing entry is compared on the v2
surface alone -- the facade is the v1-compat surface, and a
family-first name is not a v1 contract.
"""
import json
import sys

import nameparser
from nameparser import HumanName

V1_FIELDS = ("title", "first", "middle", "last", "suffix", "nickname",
             "maiden")
V2_FIELDS = ("title", "given", "middle", "family", "suffix", "nickname",
             "maiden")
WANT_V2 = @@WANT_V2@@

print(json.dumps({"__version__": nameparser.__version__,
                  "__file__": nameparser.__file__}), flush=True)

if WANT_V2:
    from nameparser import Parser, Policy, parse
    _parsers = {}

    def _parser_for(order):
        if order not in _parsers:
            _parsers[order] = Parser(policy=Policy(
                name_order=getattr(nameparser, order)))
        return _parsers[order]


def _v2_row(p):
    # must stay identical to main()'s tree-side row (compare.py) --
    # duplicated rather than shared across the process boundary
    row = {f: (getattr(p, f, "") or "") for f in V2_FIELDS}
    row["_ambiguities"] = sorted(
        {a.kind.name for a in getattr(p, "ambiguities", ())})
    return row


for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    entry = json.loads(line)
    name = entry["name"]
    order = entry.get("order")
    if order is not None:
        # never reaches a worker without WANT_V2; see the docstring
        print(json.dumps(
            {"v2": _v2_row(_parser_for(order).parse(name))},
            ensure_ascii=False), flush=True)
        continue
    row = {"facade": {k: v or ""
                      for k, v in HumanName(name).as_dict().items()
                      if k in V1_FIELDS}}
    if WANT_V2:
        row["v2"] = _v2_row(parse(name))
    print(json.dumps(row, ensure_ascii=False), flush=True)
'''


def _worker_source(version: str, want_v2: bool) -> str:
    """Render the worker with its dependency pin substituted.

    Sentinel replacement rather than str.format or f-strings: the
    worker body is mostly literal braces, and escaping every one of
    them is a defect waiting to happen in a file whose silent
    misbehavior is the thing this harness exists to prevent.
    """
    return (_WORKER_TEMPLATE
            .replace("@@VERSION@@", version)
            .replace("@@WANT_V2@@", "True" if want_v2 else "False"))


def _check_tell(tell: dict[str, str], version: str) -> None:
    """Abort before comparing anything if the wrong library answered.

    This is the check the README's trap sections exist for. Both halves
    matter and neither implies the other: an editable install reports
    the TREE's version, so version-only agreement proves nothing when
    the tree and the baseline share a number, while a genuine wheel at
    the wrong version passes any path check.
    """
    got = tell.get("__version__", "")
    where = tell.get("__file__", "")
    if not got or not where:
        raise SystemExit(
            f"baseline worker produced no usable version tell "
            f"({tell!r}); comparison aborted")
    if _parse_version(got) != _parse_version(version):
        raise SystemExit(
            f"baseline worker reports nameparser {got!r}, not the "
            f"requested {version!r} (loaded from {where}). See the "
            f"invocation traps in tools/differential/README.md; "
            f"comparison aborted.")
    if Path(where).resolve().is_relative_to(REPO_ROOT):
        raise SystemExit(
            f"baseline worker loaded nameparser from the CHECKOUT "
            f"({where}), so it answers as the working tree while "
            f"reporting {got!r} -- every diff would vanish and the run "
            f"would read as parity. Comparison aborted.")


def _worker_env() -> dict[str, str]:
    """The child's environment, with the import-path overrides stripped.

    PEP 723 isolation does NOT survive PYTHONPATH: it precedes
    site-packages, so a directory named there shadows the pinned wheel
    inside uv's own environment. Measured 2026-08-05 -- with a released
    2.0.0 on PYTHONPATH the run reported `intentional diffs: 0` and
    exited 0, both halves of the tell passing (the version matched, and
    the path was outside REPO_ROOT because it was outside the repo).
    That is the README's catastrophic failure by a third road, and it
    needs no exotic setup: a stale PYTHONPATH entry or a sibling
    checkout is enough.
    """
    return {k: v for k, v in os.environ.items()
            if k not in ("PYTHONPATH", "PYTHONHOME")}


def _check_tree(module_file: str) -> Path:
    """Prove the OTHER side of the comparison is the working tree.

    The baseline side gets a version tell, a pinned wheel and a temp
    dir; the tree side was a bare import trusted on sight. It is
    reachable by the same road: run as a script, sys.path[0] is
    tools/differential/ -- which holds no nameparser -- so PYTHONPATH
    outranks the editable install and compare.py imports a wheel while
    believing it read the checkout. Two wheels agree on everything, so
    the run reports parity.

    (The reason this is easy to miss when probing by hand: from the
    repo root, `python -c` puts the CWD on sys.path first, so the
    checkout wins there and the trap does not reproduce. Only the
    script invocation shows it.)

    The test is "is this the SOURCE PACKAGE", not "is this somewhere
    under the repo". The weaker form was written first and was wrong:
    the checkout also contains .venv/, build/lib/ and dist/, any of
    which can hold a released wheel, so `PYTHONPATH=<repo>/build/lib`
    is the same trap with the shadowing directory moved one level to
    the left -- and uv never touches build/, so nothing self-heals it.
    Note the asymmetry the weak form created: <repo>/.venv/.../
    nameparser is REJECTED as a baseline by _check_tell and would have
    been ACCEPTED as the tree here.
    """
    at = Path(module_file).resolve()
    source = REPO_ROOT / "nameparser"
    if not at.is_relative_to(source):
        raise SystemExit(
            f"the tree side imported nameparser from {at}, not from "
            f"this checkout's source package ({source}) -- so this run "
            f"would compare that module against the baseline instead of "
            f"the working tree. Unset PYTHONPATH; uninstall a "
            f"non-editable nameparser from the active environment; or, "
            f"in a git worktree, check that the editable install points "
            f"at THIS worktree rather than the main checkout. "
            f"Comparison aborted.")
    return at


def _run_worker(version: str, want_v2: bool,
                entries: list[dict]) -> tuple[dict[str, str], list[dict]]:
    """Run the baseline worker from a temp dir OUTSIDE the worktree.

    The placement is the safety mechanism, not plumbing. uv reads
    genuine PEP 723 metadata from a real script path, and sys.path[0]
    is the script's directory -- a temp dir holding no nameparser -- so
    the checkout cannot shadow the pinned wheel. The README notes that
    an absolute script path from outside the project is the one
    invocation variant that does not lie; this makes it the only one
    reachable.
    """
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "baseline_worker.py"
        script.write_text(_worker_source(version, want_v2), encoding="utf-8")
        proc = subprocess.Popen(
            ["uv", "run", "--no-project", str(script)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
            cwd=tmp, env=_worker_env())
        payload = "".join(
            json.dumps({"name": e["name"], "order": e.get("order")},
                       ensure_ascii=False) + "\n"
            for e in entries)
        out, _ = proc.communicate(payload)
    # hard checks, not asserts: -O must not turn a crashed worker into
    # a truncated-but-green comparison
    if proc.returncode != 0:
        raise SystemExit(
            f"baseline worker exited {proc.returncode}; comparison aborted")
    lines = out.splitlines()
    if not lines:
        raise SystemExit(
            "baseline worker produced no output, not even a version "
            "tell; comparison aborted")
    tell = json.loads(lines[0])
    _check_tell(tell, version)
    results = [json.loads(x) for x in lines[1:]]
    if len(results) != len(entries):
        raise SystemExit(
            f"worker returned {len(results)} results for {len(entries)} "
            f"corpus entries; comparison aborted")
    return tell, results


def _canonical_field(field: str) -> str:
    """A role's canonical name: Role's, not the facade's. Applied to
    diffs from BOTH surfaces, so it must be a no-op on names that are
    already canonical."""
    return _V1_TO_ROLE.get(field, field)


def _order_tag(order: str | None) -> str:
    """The `   [order: X]` header suffix, or "" for a default-order
    entry. Shared by the UNEXPLAINED and UNCLASSIFIED (radar) headers
    in main() -- one copy for the same reason _print_field_diffs is:
    two copies can drift."""
    return f"   [order: {order}]" if order is not None else ""


def _print_field_diffs(old_facade: dict[str, str], new: dict[str, str],
                       old_v2: dict[str, object],
                       new_v2: dict[str, object],
                       order: str | None = None) -> None:
    """Print each moved field under one name, Role's, whichever
    surface(s) moved it. Shared by the UNEXPLAINED and UNCLASSIFIED
    (radar) blocks in main() -- one copy rather than two that can
    drift apart, the same reason _entry_matches is "one predicate
    rather than three copies".

    Role's names, not the facade's: both report blocks exist to be
    turned into a ledger rule, and a rule naming the facade's `first`
    is rejected by validate_rules at startup. Both surfaces are
    walked, and a field is reported once even when both moved, since
    one rule covers it.

    `order` is None for a default-order entry, else the order both
    surfaces were read under. The "[v2 surface only]" tag means "the
    facade was compared and agreed" -- untrue for an order-bearing
    entry, whose facade is never consulted at all (main() passes empty
    dicts for it), so the tag is suppressed there rather than printed
    with a meaning it does not have.
    """
    seen: set[str] = set()
    for f in FIELDS:
        if old_facade.get(f, "") != new.get(f, ""):
            seen.add(_canonical_field(f))
            print(f"    {_canonical_field(f)}: "
                  f"{old_facade.get(f, '')!r} -> {new.get(f, '')!r}")
    for f in (*V2_FIELDS, "_ambiguities"):
        if old_v2.get(f, "") != new_v2.get(f, "") \
                and _canonical_field(f) not in seen:
            tag = "" if order is not None else "   [v2 surface only]"
            print(f"    {_canonical_field(f)}: "
                  f"{old_v2.get(f, '')!r} -> {new_v2.get(f, '')!r}"
                  f"{tag}")


def _is_latin_only(name: str) -> bool:
    """Every character below U+0250 -- Latin, ASCII punctuation and
    Latin-1 accents.

    The partition is by SCRIPT OF THE INPUT, not by which issue claimed
    the diff, because the question it answers is whether a user parsing
    Western names sees any change at all. That number goes into the
    release notes.
    """
    return all(ord(ch) < 0x250 for ch in name)


#: Every legal entry in a rule's `fields`: the seven roles under Role's
#: names, plus the pseudo-field carrying reported AmbiguityKinds. The
#: ambiguity entry is legal and load-bearing -- a SEGMENTATION-only diff
#: is facade-identical, so this is the one name that can classify it.
_RULE_FIELDS = frozenset((*V2_FIELDS, "_ambiguities"))
_RULE_KEYS = frozenset(("issue", "name_regex", "fields", "dormant", "orders"))


#: The `orders` member naming the DEFAULT order -- the comparison whose
#: `order` is None, run under no declared name_order at all. A sentinel
#: rather than a constant name because there is no constant to borrow:
#: the default order is the absence of one, no shape declares it, and
#: TOML has no null to put inside an array. Without it a rule that
#: explains only default-order diffs cannot say so and has to stay
#: order-blind, which is the leak running the OTHER way from the one
#: `orders` was added for: an order-blind rule sorted ahead of the
#: scoped ones absorbs a family-first regression on a name its regex
#: happens to reach.
_DEFAULT_ORDER = "DEFAULT"


def _legal_orders() -> frozenset[str]:
    """The names a rule's `orders` may carry: every order shapes.py's
    inventory declares, plus the "DEFAULT" sentinel.

    The constants are borrowed rather than hand-copied, the same way
    build_cjk_corpus.py borrows the script table: an order no shape
    declares is an order no comparison can run under, so a rule scoped
    to it could only ever be dormant, and a typo in one would be a rule
    that silently explains nothing.

    "DEFAULT" is the one member that cannot be borrowed, since it names
    the absence of a declared order rather than a shape.
    """
    return frozenset(shape.order for shape in _load_shapes().values()
                     if shape.order is not None) | {_DEFAULT_ORDER}


#: Probe names for the over-match check, chosen to share no script, no
#: vocabulary and no punctuation. A `name_regex` matching ALL of them is
#: not targeting a behavior family, it is matching everything -- and
#: since name_regex rules sort first, one such rule shadows the ledger.
#: Probing the empty string instead (the first attempt) tested the wrong
#: property: '.', '.+', r'\b' and '[\s\S]' all decline "" and still
#: match every name in every corpus.
_SENTINELS = ("John Smith", "田中さん", "Хосе Сантос", "x")

#: Per-corpus size floors. The existing empty-file guard only catches a
#: corpus that lost EVERY name; one truncated to a handful sails past
#: it, and the run then exits 0 having compared a fraction of what its
#: own summary line reports -- green, and quietly meaningless.
#:
#: Floors, not counts, because corpus_issues.jsonl grows whenever it is
#: regenerated from the tracker and pinning it exactly would fail on
#: every legitimate harvest. Set a little under the real size, and
#: ratchet up only deliberately. A file with no entry here is a hard
#: error rather than an unguarded default: the point is to force a
#: decision when a corpus is added, the way the Script tables do.
_CORPUS_FLOORS = {
    "corpus.jsonl": 480,        # 486 today, from v1's banks at a pinned ref
    "corpus_cjk.jsonl": 95,     # 98 today, generated from the case table
    "corpus_issues.jsonl": 370,  # 381 today, harvested and append-only
    "corpus_rules.jsonl": 150,  # 252 today, generated from rules.md
    "corpus_shapes.jsonl": 35,  # 37 today, generated from shape-tagged
                                # case rows. Ratcheted 27 -> 35 on
                                # 2026-09-01 with the shape 6/7
                                # exemplars (7 CJK names, already in
                                # corpus_cjk.jsonl and deduped against
                                # it by (name, order) -- the file grew,
                                # the comparison did not)
}

#: Tier per corpus file, fail-closed like the floors above. CONTRACT
#: corpora hold names someone chose -- an unmatched diff on one is
#: UNEXPLAINED and fails the run, today's discipline. RADAR corpora
#: hold scraped/harvested names (#468): their diffs still classify
#: against the ledger (release notes want the grouping) but an
#: unmatched one prints under UNCLASSIFIED (radar) and cannot fail
#: the run or demand a rule. Promotion is a cases.py row plus a
#: shape tag -- a name enters the contract by being chosen.
#:
#: A `[[never]]` exclusion is the same kind of choice, and stays fatal
#: on a name in a radar file for exactly that reason: someone wrote
#: the entry, its `why`, and its `examples`, so the shape it refuses
#: was chosen the same way a rule is -- unlike the rest of a radar
#: file, which nobody has looked at name by name. The tier split
#: governs names nobody chose; a [[never]] entry is the opposite of
#: that, so it outranks the tier the name happens to sit in.
_CORPUS_TIERS = {
    "corpus.jsonl": "radar",
    "corpus_cjk.jsonl": "contract",
    "corpus_issues.jsonl": "radar",
    "corpus_rules.jsonl": "contract",
    "corpus_shapes.jsonl": "contract",
}


def validate_rules(rules: list[dict[str, object]], ledger: str) -> None:
    """Reject malformed allowlist rules LOUDLY at startup.

    Every check below is a way a rule can silently stop meaning what
    its author wrote. Most of them catch a rule matching MORE than
    intended, which is the dangerous direction: it converts a real
    regression into a classified diff and a green run. Two catch the
    opposite -- an empty `fields`, or one naming something that is not
    a role, makes a rule that can never match, and its diff then
    surfaces as UNEXPLAINED. That failure is loud, so those two checks
    buy a precise message rather than safety; they are here because the
    family is easier to reason about whole than split by direction.

    Two checks belong to the dangerous direction and are the family's
    sharpest examples, one per missing key -- #451 for a `fields` with
    no `name_regex`, #456 for a `name_regex` with no `fields`. An
    earlier version of this paragraph said the first was the only shape
    that could widen invisibly; #456 falsified that, and worse, since
    over_declared_rules skips a fieldless rule so nothing narrows it
    either. #451 is the rule that lived
    it -- no name narrowing, so it claimed every name whose diff fit
    its `fields`, and _CORPUS_CLAIMS (the guard tracking each rule's
    reach) recorded that reach as the whole corpus from the start, so
    growth could never trip it. It grew from 4 explained names to 14
    across six unrelated behavior families before anyone noticed, with
    every guard green throughout. A specificity FLOOR on role count was
    proposed and declined as vacuous (#372/#373): that one rule named
    3 of 7 roles, and no floor rejecting it matches anything else. This
    check rejects the SHAPE instead -- no name narrowing at all -- which
    is a different proposal and costs no migration, since no rule in
    any shipped ledger has it.

    The TYPE and VALUE checks are the quiet ones, not the presence
    check: `classify` skips a `name_regex` that is not a str and a
    `fields` that is not a list, so a mistyped or misspelled key does
    not fail -- it deletes that half of the rule's narrowing and the
    rule matches on the other half alone.

    Rules are also compiled here, not at match time. `classify` returns
    on the first match, so an uncompilable pattern at position k only
    raises once a diff gets past rules 1..k-1: a ledger can run green
    for months and then explode mid-run, after the multi-minute worker
    pass, in a traceback naming neither the file nor the rule.

    `ledger` is named rather than hardcoded because there is one per
    baseline now: a message naming the wrong file sends the reader to
    edit a rule that is not the broken one.

    The `dormant` check is the one exception to that framing: it is not
    about a rule's matching semantics drifting, but about an opt-out
    carrying a justification someone can review.
    """
    seen: set[str] = set()
    for rule in rules:
        issue = rule.get("issue")
        if not isinstance(issue, str):
            continue  # the per-rule loop below rejects it with a better message
        if issue in seen:
            raise SystemExit(
                f"{ledger} has two rules sharing the issue {issue!r}. The "
                f"dormancy check identifies a rule by its issue, so the "
                f"second would hide behind the first: it could explain "
                f"nothing and never be reported")
        seen.add(issue)
    for i, rule in enumerate(rules):
        where = f"{ledger} rule #{i + 1}"
        issue = rule.get("issue")
        if not isinstance(issue, str) or not issue:
            raise SystemExit(
                f"{where} has no string 'issue': {rule!r}")
        where = f"{where} ({issue!r})"
        unknown = set(rule) - _RULE_KEYS
        if unknown:
            raise SystemExit(
                f"{where} has unknown key(s) {sorted(unknown)}; expected "
                f"only {sorted(_RULE_KEYS)}. A misspelled key is not "
                f"ignored -- it drops that half of the rule's narrowing "
                f"and the rule matches on the other half alone")
        if "dormant" in rule:
            reason = rule["dormant"]
            if not isinstance(reason, str) or not reason:
                raise SystemExit(
                    f"{where} has a 'dormant' that is not a non-empty "
                    f"string ({reason!r}). 'dormant' declares that a rule "
                    f"is expected to explain nothing, and the reason is "
                    f"the whole safeguard -- an exemption nobody can "
                    f"justify means the rule should be deleted instead")
        if "orders" in rule:
            orders = rule["orders"]
            if not isinstance(orders, list) \
                    or not all(isinstance(o, str) for o in orders):
                raise SystemExit(
                    f"{where} has an 'orders' that is not a list of "
                    f"strings ({orders!r}); _entry_matches would ignore "
                    f"it and the rule would go back to claiming a diff "
                    f"under EVERY order, which is the scoping this key "
                    f"exists to undo")
            if not orders:
                raise SystemExit(
                    f"{where} has an empty 'orders', which no comparison "
                    f"can be run under -- a rule that can never match. "
                    f"Omit the key to stay order-blind")
            legal = _legal_orders()
            bad = sorted(set(orders) - legal)
            if bad:
                raise SystemExit(
                    f"{where} names {bad} in 'orders', which shapes.py "
                    f"declares for no shape and which is not the "
                    f"{_DEFAULT_ORDER!r} sentinel; expected from "
                    f"{sorted(legal)}. No comparison runs under an order "
                    f"no shape asks for, so the rule would explain "
                    f"nothing and report as dormant instead of saying "
                    f"the name is wrong")
        has_regex, has_fields = "name_regex" in rule, "fields" in rule
        if not has_regex and not has_fields:
            raise SystemExit(
                f"{where} has neither 'name_regex' nor 'fields' -- it "
                f"would match every diff and shadow every later rule")
        if has_regex:
            pattern = rule["name_regex"]
            if not isinstance(pattern, str):
                raise SystemExit(
                    f"{where} has a non-string 'name_regex' "
                    f"({pattern!r}); classify would skip it and the rule "
                    f"would match on 'fields' alone")
            try:
                compiled = re.compile(pattern)
            except re.error as exc:
                raise SystemExit(
                    f"{where} has an invalid 'name_regex' "
                    f"({pattern!r}): {exc}") from None
            if all(compiled.search(s) for s in _SENTINELS):
                raise SystemExit(
                    f"{where} has a 'name_regex' ({pattern!r}) that "
                    f"matches every one of {list(_SENTINELS)} -- names "
                    f"with no script, vocabulary or punctuation in "
                    f"common, so a rule targeting one behavior family "
                    f"cannot match them all. name_regex rules sort "
                    f"FIRST, so this one would shadow the whole ledger")
        if has_fields:
            fields = rule["fields"]
            if not isinstance(fields, list) \
                    or not all(isinstance(f, str) for f in fields):
                raise SystemExit(
                    f"{where} has a 'fields' that is not a list of "
                    f"strings ({fields!r}); classify would skip it and "
                    f"the rule would match on 'name_regex' alone")
            if not fields:
                raise SystemExit(
                    f"{where} has an empty 'fields', which can never "
                    f"match any diff -- a rule that does nothing")
            bad = sorted(set(fields) - _RULE_FIELDS)
            if bad:
                raise SystemExit(
                    f"{where} names {bad} in 'fields', which are not "
                    f"roles; expected from {sorted(_RULE_FIELDS)}. A "
                    f"name outside that set never matches, so the rule "
                    f"is silently dead")
            if set(V2_FIELDS) <= set(fields):
                raise SystemExit(
                    f"{where} lists all seven roles in 'fields', so the "
                    f"subset test admits every diff -- the narrowing is "
                    f"not narrowing anything. Checked against the seven "
                    f"roles rather than against every legal entry, "
                    f"because '_ambiguities' cannot enter a diff at all "
                    f"below baseline 2.0: there the seven ARE the whole "
                    f"vocabulary, and a rule listing them would have "
                    f"claimed every diff in the 1.4 ledger")
        # LAST of the family, deliberately. This rejects a
        # WELL-FORMED `fields` that simply has no name beside it, so it
        # must not pre-empt the three checks above, each of which buys a
        # precise message for a `fields` that is malformed -- empty, not
        # a list, not roles. Written directly under the neither-key
        # check (where the shapes are cousins) it did exactly that: an
        # empty `fields` reported #451 instead of "empty 'fields'", and
        # the parametrized cases pinning those messages had to grow a
        # name_regex to keep reaching them (#453 review).
        if has_fields and not has_regex:
            raise SystemExit(
                f"{where} has 'fields' but no 'name_regex' (#451). With "
                f"no name narrowing, the rule claims every name whose "
                f"diff fits its 'fields' -- and no guard can see that "
                f"grow: _CORPUS_CLAIMS records a regexless rule's reach "
                f"as the WHOLE CORPUS, so it starts at its maximum and "
                f"arrivals never move it. The one rule ever shaped this "
                f"way grew from 4 explained names to 14, across six "
                f"unrelated behavior families, with every guard green "
                f"the whole time. Narrow by name instead, or split this "
                f"into the rules the diffs actually need")
        if has_regex and not has_fields:
            raise SystemExit(
                f"{where} has 'name_regex' but no 'fields' (#456). It "
                f"narrows by name and by nothing else, so on any name "
                f"its regex reaches it claims EVERY diff shape there is -- "
                f"255 of them from baseline 2.0 on, where `_ambiguities` "
                f"joins the seven roles, and 127 below it. #452 makes "
                f"that worse than it looks: "
                f"over_declared_rules skips a rule with no 'fields', "
                f"correctly, since one declaring no roles cannot "
                f"over-declare them -- so deleting the line is the "
                f"cheapest way to silence an OVER-DECLARED failure and "
                f"the most permissive thing you can do to the rule at "
                f"the same time. Name the roles the diffs actually "
                f"move. Do NOT reach for the other shape instead: a "
                f"'fields' with no 'name_regex' is banned by #451 for "
                f"the mirror-image reason, and the two bans are each "
                f"other's obvious wrong answer")


def validate_exclusions(entries: list[dict[str, object]],
                        ledger: str) -> None:
    """Reject malformed [[never]] entries LOUDLY at startup.

    An exclusion is the absorption bug pointed the other way. A rule
    that matches too widely turns a regression into a classified diff;
    an exclusion that matches too widely turns a legitimate
    classification into UNEXPLAINED, which reads as a catastrophic
    regression rather than as a bad exclusion. So the checks mirror
    validate_rules', with one addition: an entry whose `examples` do
    not match its own `name_regex` protects nothing while looking
    complete. Nothing else says so at startup, which is where a
    silently-inert entry most needs saying.

    `fields` is optional and narrows WHICH READING is protected, the
    same subset test the rules use. It exists because ASCII parens mark
    nicknames, maiden names, suffixes and credentials alike -- a
    name-only exclusion for the nickname promise would also silence
    every diff on 'Jenny (Johnson) Baker' and 'Lon (Jr.) Williams',
    whose parens are a maiden name and a suffix. That does not HIDE a
    regression there -- an excluded name reports UNEXPLAINED, which
    exits non-zero -- it makes those names permanently unexplainable,
    so an intended change in an area under active development can
    never be recorded and every release blocks on the same false
    alarm. Typographic delimiters carry no such ambiguity, which is
    why feat(#273)'s own rule can be a bare character class.
    """
    allowed = {"why", "name_regex", "examples", "fields"}
    for index, entry in enumerate(entries):
        where = f"{ledger} exclusion #{index + 1}"
        unknown = set(entry) - allowed
        if unknown:
            raise SystemExit(
                f"{where} has unknown key(s) {sorted(unknown)}; expected "
                f"{sorted(allowed)}. A misspelled key is silently ignored, "
                f"which deletes whatever it was meant to declare.")
        why = entry.get("why")
        if not isinstance(why, str) or not why:
            raise SystemExit(
                f"{where} has no string 'why'. An exclusion nobody can "
                f"justify is one nobody can safely delete.")
        pattern = entry.get("name_regex")
        if not isinstance(pattern, str) or not pattern:
            raise SystemExit(f"{where} has no string 'name_regex'")
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            raise SystemExit(
                f"{where} has an invalid 'name_regex' ({exc})") from None
        if all(compiled.search(s) for s in _SENTINELS):
            raise SystemExit(
                f"{where}'s 'name_regex' matches every one of "
                f"{list(_SENTINELS)} -- it would silence the whole ledger, "
                f"reporting every diff as unexplained.")
        examples = entry.get("examples")
        if examples is None or examples == []:
            raise SystemExit(
                f"{where} has no 'examples'. They are the entry's test "
                f"data: a protected shape need not be in any corpus, so "
                f"nothing else can supply one.")
        if (not isinstance(examples, list)
                or not all(isinstance(e, str) for e in examples)):
            raise SystemExit(
                f"{where}'s 'examples' is not a list of strings")
        stray = [e for e in examples if not compiled.search(e)]
        if stray:
            raise SystemExit(
                f"{where} lists {stray} which does not match its own "
                f"'name_regex' -- the entry would protect nothing while "
                f"looking complete.")
        if "fields" in entry:
            fields = entry["fields"]
            if not isinstance(fields, list) \
                    or not all(isinstance(f, str) for f in fields):
                raise SystemExit(
                    f"{where} has a 'fields' that is not a list of "
                    f"strings ({fields!r}); classify would ignore it and "
                    f"the entry would silence EVERY diff on a matching "
                    f"name, not the reading it names")
            if not fields:
                raise SystemExit(
                    f"{where} has an empty 'fields', which can never "
                    f"match any diff -- an exclusion that protects "
                    f"nothing")
            bad = sorted(set(fields) - _RULE_FIELDS)
            if bad:
                raise SystemExit(
                    f"{where} names {bad} in 'fields', which are not "
                    f"roles; expected from {sorted(_RULE_FIELDS)}")
            if set(V2_FIELDS) <= set(fields):
                raise SystemExit(
                    f"{where} lists all seven roles in 'fields', which "
                    f"is what omitting the key already means. omit "
                    f"'fields' to exclude any diff on a matching name")


def _entry_matches(rule: dict[str, object], name: str,
                   diff_fields: set[str], order: str | None = None) -> bool:
    """Does this entry's narrowing admit this diff?

    Called twice in classify() -- once for exclusions, once for rules --
    and again in dormant_rules(). All three narrow on the same keys,
    and the dormancy diagnosis is only meaningful if it asks the
    question classify asks, so there is one predicate rather than three
    copies of it.

    `order` is the name_order the COMPARISON ran under (None = the
    default order), and a rule carrying `orders` admits only the orders
    it lists. A comparison under the default order is matched by the
    "DEFAULT" sentinel, there being no constant to name and no null to
    put in a TOML array. Without that narrowing a rule is order-blind,
    which is what every rule written before shape-tagged entries
    existed is: the key is optional and its absence is today's
    behavior -- and the absence is not free, since an order-blind rule
    reaching an order-bearing name absorbs that name's order-only
    regressions (main() prints an ORDER-BLIND notice where it sees
    that happen). It matters
    because a name can be compared twice, once per order, and the two
    diffs can have the SAME fields for opposite reasons -- the
    feat(#395) fold moving {family, given, middle} under a declared
    family-first order is intended, and the same three roles moving on
    the same string under the DEFAULT order would be that fold leaking
    where it must not, which an order-blind rule would absorb and call
    intentional (#372's failure mode, on the most plausible regression
    of the very change the rule describes).

    A non-str `name_regex`, non-list `fields` or non-list `orders` is
    IGNORED rather than rejected here: validate_rules and
    validate_exclusions reject them at startup, and duplicating that
    judgement in the hot path would put the two in a position to
    disagree.
    """
    name_regex = rule.get("name_regex")
    if isinstance(name_regex, str) and not re.search(name_regex, name):
        return False
    fields = rule.get("fields")
    if isinstance(fields, list) and not diff_fields <= set(fields):
        return False
    orders = rule.get("orders")
    if isinstance(orders, list) \
            and (_DEFAULT_ORDER if order is None else order) not in orders:
        return False
    return True


def classify(name: str, diff_fields: set[str],
             rules: list[dict[str, object]],
             exclusions: list[dict[str, object]] | None = None,
             order: str | None = None) -> str | None:
    """Which rule explains this diff, or None if nothing does.

    Exclusions are consulted FIRST and win outright. They are the
    ledger's way of saying a shape must never be explained, which the
    rule vocabulary cannot express: a rule says "this diff is intended
    and here is why", and there is no rule meaning "whatever happens
    here is a regression". Two comments in expected_since_1.4.0.toml
    promised exactly that in prose and could not keep it (#328).

    Consulting them first also makes them MONOTONE -- an exclusion only
    ever removes a name from classification, never moves it between
    rules -- so a new entry's blast radius is exactly the set of names
    it captures, independent of rule order.

    An exclusion narrows by `name_regex` and optionally by `fields`.
    The optionality is the exclusion's alone since #456: a RULE must
    now carry both. Without `fields` it refuses any diff on a
    matching name; with them it refuses only the reading it names, so a
    name whose parens mark a nickname to one rule and a suffix to
    another stays classifiable on the reading the exclusion is not
    about.

    `order` is the name_order this comparison ran under and narrows the
    RULES alone: exclusions have no `orders` key (validate_exclusions
    rejects one as unknown), so they stay order-blind, deliberately.
    An over-wide exclusion is loud rather than silent -- refusal is
    monotone, so the widest thing it can do is make a name report
    UNEXPLAINED and fail the run -- and no exclusion on the books
    protects a shape that reads differently under a declared order. The
    key can be given to them the day one does.
    """
    for entry in exclusions or ():
        if _entry_matches(entry, name, diff_fields):
            return None
    for rule in rules:
        if _entry_matches(rule, name, diff_fields, order):
            return rule["issue"]  # type: ignore[return-value]
    return None


#: How each `_Dormant.kind` reads in the report. Here rather than in
#: dormant_rules so the computation never has to know the wording, and
#: rephrasing one is a change to output alone.
_DORMANT_WHY = {
    "reverted": ("matched no diffing name -- the behavior it describes "
                 "may have been reverted"),
    "shadowed": "shadowed by {by}",
    "excluded": ("every diffing name it matches is refused by a "
                 "[[never]] exclusion"),
}


class _Dormant(NamedTuple):
    """One rule that explained nothing, and why.

    `kind` rather than a sentence because the three have three different
    fixes, and a caller that wants to tell them apart should not have to
    parse prose to do it. The wording lives in main(), which is the only
    place that renders it -- so rephrasing a diagnosis stays a change to
    output alone, and the tests that pin the DISTINCTION keep working.
    """
    issue: str
    kind: Literal["reverted", "shadowed", "excluded"]
    #: the issue that claimed it, when `kind` is "shadowed"; else ""
    detail: str


class _Dormancy(NamedTuple):
    """What a run found out about rules that explained nothing."""
    #: every rule that explained nothing and does not declare `dormant`
    undeclared: tuple[_Dormant, ...]
    #: issues declaring `dormant` that explained at least one diff
    awake: tuple[str, ...]


def dormant_rules(rules: list[dict[str, object]], explained: set[str],
                  diffing: list[tuple[str, set[str], str | None]],
                  exclusions: list[dict[str, object]] | None = None,
                  ) -> _Dormancy:
    """Which rules explained nothing, and which kind of nothing.

    A rule going inert is invisible to every other guard here.
    _CORPUS_CLAIMS records what a rule's REGEX reaches, which is
    parser-independent, so reverting the fix a rule describes leaves the
    rule matching exactly as many names as before while it explains no
    diff at all -- and the run exits 0 (#372).

    Pure on purpose: it needs only values main() already derives per
    name, and no second baseline run. Wiring it in means threading the
    diff-fields set through the existing loop, not adding new I/O. A
    check reachable only through a full baseline run is a check nobody
    mutates, and this tree has a long list of measurements that ran,
    printed a plausible number, and measured nothing.

    Three diagnoses, because they have three different fixes:
      reverted  -- matches no diffing name; the behavior is likely gone
      shadowed  -- an earlier rule claimed every diff it would have
      excluded  -- a [[never]] entry refuses every name it matches
    """
    # classify() must be asked in the order main() asked it, or the
    # shadower named here is not the rule that actually won. Sorting
    # internally makes that true whatever the caller passes; the sort is
    # stable and idempotent, so doing it twice costs nothing.
    ordered = _sorted_rules(rules)
    undeclared: list[tuple[str, str]] = []
    awake: list[str] = []
    for rule in ordered:
        issue = str(rule["issue"])
        declared = "dormant" in rule
        if issue in explained:
            if declared:
                awake.append(issue)
            continue
        if declared:
            continue
        # each diff carries the ORDER its comparison ran under, so a
        # rule scoped by `orders` is asked the question classify asks
        # it: a rule that would claim a name only under FAMILY_FIRST is
        # not "shadowed" by whatever explains that name's default-order
        # diff
        matched = [(n, d, o) for n, d, o in diffing
                   if _entry_matches(rule, n, d, o)]
        winners = Counter(
            c for c in (classify(n, d, ordered, exclusions, o)
                        for n, d, o in matched) if c is not None)
        if not matched:
            undeclared.append(_Dormant(issue, "reverted", ""))
        elif winners:
            undeclared.append(
                _Dormant(issue, "shadowed", winners.most_common(1)[0][0]))
        else:
            undeclared.append(_Dormant(issue, "excluded", ""))
    return _Dormancy(tuple(undeclared), tuple(awake))


class _OverDeclared(NamedTuple):
    """One rule declaring a role nothing it explains moves.

    `unused` is the defect. `observed` is the repair -- the union of the
    diffs the rule explained, which is what `fields` should say.
    """
    issue: str
    #: declared roles no explained diff moves, sorted
    unused: tuple[str, ...]
    #: the union of the diffs it explains, sorted; the correct `fields`
    observed: tuple[str, ...]


def over_declared_rules(
        rules: list[dict[str, object]],
        roles_by_issue: dict[str, set[str]]) -> tuple[_OverDeclared, ...]:
    """Rules whose declared `fields` exceed every diff they explain.

    classify() takes the first rule whose `fields` are a SUPERSET of the
    observed diff, so a rule keeps matching when the diff beneath it
    SHRINKS -- and shrinking is the common direction, most parser fixes
    moving fewer roles rather than more. #410 narrowed
    'Freiherr von Richthofen V' from three roles to two while the
    fix(#424) rule declaring all three kept claiming it, and no run
    named the movement (decisions.md#H1). That rule was narrowed by
    hand; this is what would have said so.

    The statement is exact rather than heuristic. classify() REQUIRES
    `declared >= union(explained diffs)` -- declaring less would stop
    the rule matching a name it explains -- so the only possible error
    is the other direction, and `declared == union` is the whole check.
    The union is also the repair, and narrowing to it cannot orphan a
    name: every name the rule explains contributed to it.

    Three rules are skipped, none as an exemption. A rule declaring
    `dormant` is dormant_rules' finding in BOTH directions -- including
    when it has explained a diff, which that check reports as NO LONGER
    DORMANT: one defect with one remedy (remove the key), where
    reporting it here too would demand a second, contradictory one.
    (Do not say "a dormant rule has no union to compare against" -- it
    can have one, and the test that pins this skip uses exactly that
    input, because the empty-union input cannot discriminate.) A rule
    with no `fields` declares no roles and so has nothing to
    over-declare -- and cannot exist since #456, which banned that
    shape precisely because this skip made deleting `fields` the
    cheapest way to silence the check. One with `fields` and no
    `name_regex` cannot exist since #451. And a rule that explained nothing is dormant_rules'
    too, which is the third `continue` below.

    What this does NOT bound is a diff shape no single name produced.
    A rule declaring {family, suffix} where one name moves `family`
    and another moves `suffix` passes -- the union is both -- while
    still standing ready to claim a name diffing the two together. The
    union is a per-RULE bound, not a per-name one, and narrowing
    further would orphan one of the two. The #452 hazard survives in
    that reduced form by choice.

    One caveat for a partial run: under `--corpus` the union is
    computed over the names actually compared, so a subset run can
    report a rule that is correctly declared for the full gate, with a
    `observed` repair that would orphan a name on the next full run.
    The report says so.

    Pure, like dormant_rules: it needs only values main() already
    derives, so it is testable without a corpus or a baseline worker.
    """
    found: list[_OverDeclared] = []
    for rule in rules:
        declared = rule.get("fields")
        if "dormant" in rule or not isinstance(declared, list):
            continue
        moved = roles_by_issue.get(str(rule["issue"]))
        if moved is None:
            # explains nothing -- dormant_rules owns that finding.
            # `is None` rather than falsy: an empty union cannot reach
            # this dict today (main() skips a name with no diff), and if
            # that ever changes an empty one should be REPORTED rather
            # than silently skipped.
            continue
        unused = tuple(sorted(set(declared) - moved))
        if unused:
            found.append(_OverDeclared(
                str(rule["issue"]), unused, tuple(sorted(moved))))
    return tuple(found)


def _load_entries(path: Path) -> list[dict[str, object]]:
    """Corpus lines as entry dicts. A line is either a bare JSON
    string (the original format) or an object with a "name" plus
    optional metadata -- "tests" labels from build_corpus.py, and a
    "shape" id from build_shapes_corpus.py (#469). Tolerating both
    means compare.py itself never needs a flag day across its five
    corpus files: corpus.jsonl and corpus_shapes.jsonl carry object
    lines, the other three are still bare strings, and both shapes
    stay legal everywhere a corpus line is read.

    A "tests" label is read only when the radar block prints, well
    after the multi-minute worker pass, so a malformed one left
    unchecked would crash there rather than here -- exactly what
    validate_rules' compile-at-startup paragraph exists to prevent.

    "shape" is checked for a different hazard. main() resolves it
    against shapes.py into the "order" the worker protocol sends, and
    that loop runs BEFORE the worker, so a bad id is not a late crash:
    it is a wrong comparison that reports as a passing one. `true`
    passes isinstance(shape, int) and hash(True) == hash(1), so an
    unchecked one resolves against shapes.py's entry 1 and the line is
    compared under that shape's order, silently. Only the TYPE is
    checked here; an unresolvable id is main()'s to catch, since only
    it has shapes.py loaded.

    Unknown keys are rejected the way validate_rules rejects them, and
    for the same reason: a misspelled key is not ignored, it drops the
    narrowing the line meant to declare, and the line then compares
    under the default order with nothing saying so. "order", "tier" and
    "file" are rejected rather than obeyed -- the comparison computes
    all three per entry and overwrites whatever a line said, so a line
    writing one would be silently discarded. "order" in particular is
    the key the WIRE protocol documents, which makes it the one a
    corpus author is likeliest to reach for.
    """
    allowed = {"name", "tests", "shape"}
    entries: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        if isinstance(raw, str):
            entries.append({"name": raw})
        elif isinstance(raw, dict) and isinstance(raw.get("name"), str):
            unknown = sorted(set(raw) - allowed)
            if unknown:
                raise SystemExit(
                    f"{path.name}: a corpus line has unknown key(s) "
                    f"{unknown}; expected only {sorted(allowed)}: "
                    f"{line!r}. A misspelled key is not ignored -- it "
                    f"drops the narrowing the line declares, and the "
                    f"name is then compared under the default order "
                    f"with nothing saying so. 'order', 'tier' and "
                    f"'file' are computed by the comparison itself, so "
                    f"a line writing one would be overwritten")
            tests = raw.get("tests")
            if tests is not None and (
                    not isinstance(tests, list)
                    or not all(isinstance(t, str) for t in tests)):
                raise SystemExit(
                    f"{path.name}: a corpus line's 'tests' must be a "
                    f"list of strings, not {tests!r}: {line!r}")
            shape = raw.get("shape")
            # bool is an int subclass in Python, and hash(True) == hash(1)
            # -- unexcluded, {"shape": true} would pass isinstance(shape,
            # int) and silently resolve to shape 1's order
            if shape is not None and (
                    not isinstance(shape, int) or isinstance(shape, bool)):
                raise SystemExit(
                    f"{path.name}: a corpus line's 'shape' must be an "
                    f"int naming a shapes.py entry, not {shape!r}: "
                    f"{line!r}")
            entries.append(dict(raw))
        else:
            raise SystemExit(
                f"{path.name}: corpus line is neither a JSON string "
                f"nor an object with a string 'name': {line!r}")
    return entries


def main() -> int:
    ap = argparse.ArgumentParser()
    # Every corpus by default: they have different blind spots (see
    # build_issues_corpus.py), and one that has to be asked for by name
    # is one that stops being run. Deliberately a glob rather than a
    # list, so adding a corpus file is enough to put it in the gate.
    ap.add_argument("--corpus", action="append", metavar="PATH",
                    help="corpus file; repeatable. Defaults to every "
                         "corpus*.jsonl beside this script.")
    ap.add_argument("--baseline", default=DEFAULT_BASELINE, metavar="VERSION",
                    help=f"released version to compare the tree against "
                         f"(default {DEFAULT_BASELINE}). Use 1.4.0 for the "
                         f"v1 compat contract, the previous minor for a "
                         f"release's blast radius.")
    args = ap.parse_args()
    baseline = args.baseline
    surfaces = _surfaces_for(baseline)
    paths = ([Path(p) for p in args.corpus] if args.corpus
             else sorted(HERE.glob("corpus*.jsonl")))
    ledger = _allowlist_for(baseline)
    parsed = tomllib.loads(ledger.read_text())
    rules = parsed.get("change", [])
    validate_rules(rules, ledger.name)
    rules = _sorted_rules(rules)
    exclusions = parsed.get("never", [])
    validate_exclusions(exclusions, ledger.name)
    # A glob that matches nothing must not read as "everything passed".
    # Comparing zero names would print 0 unexplained and exit 0 -- the
    # harness's own stated nightmare (see validate_rules), and a
    # regression from the single hard-coded path this replaced, which
    # raised FileNotFoundError.
    if not paths:
        raise SystemExit(
            f"no corpus files found in {HERE}: expected corpus*.jsonl")
    # A file that DISAPPEARS is the same nightmare one step smaller:
    # the glob simply finds fewer files, and the run compares less
    # while printing a summary that reads exactly like a full one. The
    # floors already name every corpus that is supposed to exist, so
    # ask them. Skipped under --corpus, where narrowing is the point.
    if not args.corpus:
        missing = sorted(set(_CORPUS_FLOORS) - {p.name for p in paths})
        if missing:
            raise SystemExit(
                f"corpus files named in _CORPUS_FLOORS are not on disk: "
                f"{missing}. A corpus that vanishes shrinks the "
                f"comparison silently -- restore it, or drop its floor "
                f"if it is meant to be gone")
    # Contract files load FIRST so the (name, order) dedup below keeps
    # the contract reading of a string both tiers hold.
    paths = sorted(paths, key=lambda p: (
        _CORPUS_TIERS.get(p.name) != "contract", p.name))
    per_file = {}
    entries: list[dict[str, object]] = []
    for path in paths:
        tier = _CORPUS_TIERS.get(path.name)
        if tier is None:
            raise SystemExit(
                f"{path.name} has no entry in _CORPUS_TIERS. Every "
                f"corpus must choose: 'contract' (an unmatched diff "
                f"fails the run) or 'radar' (an unmatched diff is "
                f"reported and cannot fail). A default here would let "
                f"a new corpus pick one by accident")
        file_entries = _load_entries(path)
        if not file_entries:
            raise SystemExit(f"{path.name} is empty; comparison aborted")
        floor = _CORPUS_FLOORS.get(path.name)
        if floor is None:
            raise SystemExit(
                f"{path.name} has no entry in _CORPUS_FLOORS. Add one at "
                f"a little under its size: without a floor a corpus can "
                f"shrink to a handful of names and the run still exits "
                f"0, having compared far less than it reports")
        if len(file_entries) < floor:
            raise SystemExit(
                f"{path.name} holds {len(file_entries)} names, below its "
                f"floor of {floor} -- it has shrunk or been truncated. "
                f"The run would still exit 0 while comparing a fraction "
                f"of what it claims. Restore the file, or lower the "
                f"floor deliberately if names were removed on purpose")
        per_file[path.name] = len(file_entries)
        for e in file_entries:
            e["tier"] = tier
            e["file"] = path.name
        entries.extend(file_entries)
    # resolve each entry's optional "shape" to the "order" the worker
    # protocol actually sends -- a public nameparser constant name, or
    # None for the default order
    shapes_by_id = _load_shapes()
    for e in entries:
        shape = e.get("shape")
        if shape is None:
            e["order"] = None
            continue
        if shape not in shapes_by_id:
            raise SystemExit(
                f"corpus entry {e['name']!r} declares shape {shape!r}, "
                f"which shapes.py does not define")
        e["order"] = shapes_by_id[shape].order
    # dedupe on (name, order): the same string tagged with two shapes
    # is two comparisons, not a duplicate -- each order is compared
    # under its own reading. First-seen wins, and contract files were
    # loaded first. The min-baseline skip below reads the SURVIVOR's
    # shape, which is safe only while min_baseline is a function of
    # order alone (true today, since every order-bearing shape's
    # minimum is 2.0.0) -- a future order-None shape carrying a higher
    # minimum than an order-bearing duplicate would make survival, and
    # so the skip decision, depend on which file loaded first. That
    # future is now real -- shapes 6/7 are order-None with a later
    # minimum (2.1.0) than shapes 1-3's (1.4.0) -- but still
    # unreachable as an actual duplicate: shapes 1-5's purity check
    # refuses CJK text and shapes 6/7's requires it, so no string can
    # ever carry two order-None shape tags with different minimums,
    # whichever file loaded first.
    by_key: dict[tuple[str, str | None], dict[str, object]] = {}
    for e in entries:
        by_key.setdefault((e["name"], e.get("order")), e)
    entries = list(by_key.values())
    # an ORDER-BEARING entry must never reach a worker whose baseline
    # cannot honor it (no Policy below 2.0.0) -- skip it and say so,
    # rather than shrink the comparison silently. An order-NONE
    # shape's min_baseline is documentary, not a skip trigger: the
    # default policy exists at every baseline, so a name tagged with
    # such a shape compares just fine below its min_baseline -- the
    # resulting diff (if any) is an ordinary classified one, not a gap
    # the skip needs to hide. Only an unhonorable ORDER forces a skip
    # (shapes.py's docstring states the same asymmetry against shapes
    # 4/5). Skips are also counted PER FILE: per_file above records
    # pre-skip counts, so a shapes corpus fully skipped at an old
    # baseline would otherwise print at full size while contributing
    # nothing.
    kept = []
    dropped = 0
    dropped_by_file: dict[str, int] = {}
    dropped_shape_ids: set[int] = set()
    dropped_minimums: set[str] = set()
    for e in entries:
        shape = e.get("shape")
        if (shape is not None
                and shapes_by_id[shape].order is not None
                and _parse_version(baseline)
                < _parse_version(shapes_by_id[shape].min_baseline)):
            dropped += 1
            dropped_by_file[e["file"]] = dropped_by_file.get(e["file"], 0) + 1
            dropped_shape_ids.add(shape)
            dropped_minimums.add(shapes_by_id[shape].min_baseline)
            continue
        kept.append(e)
    if dropped:
        ids = ", ".join(str(i) for i in sorted(dropped_shape_ids))
        minimums = ", ".join(sorted(dropped_minimums, key=_parse_version))
        print(f"skipped {dropped} name{'s' if dropped > 1 else ''} "
              f"tagged shape(s) [{ids}]: baseline {baseline} predates "
              f"their minimum ({minimums})")
    entries = kept
    corpus = [e["name"] for e in entries]
    # per-file counts, not just the total: a corpus that shrinks or
    # vanishes is only visible if its own number is printed. A file
    # with skips ALSO prints its skip count, not just its final size --
    # otherwise a shapes corpus skipped to zero reads as a corpus that
    # was simply never that large. N is pre-dedup and K counts only
    # the baseline-minimum skip, so N - K is NOT "how many from this
    # file were compared" -- an entry the cross-file dedup dropped is
    # in neither number.
    print("corpora: " + ", ".join(
        f"{name} ({n}, {dropped_by_file[name]} skipped)"
        if dropped_by_file.get(name) else f"{name} ({n})"
        for name, n in per_file.items()))

    # The tree is checked BEFORE the worker runs. It depends on nothing
    # the worker produces, and validate_rules' own reasoning applies: a
    # misconfiguration that aborts after a full uv-install-plus-751-name
    # pass costs minutes to learn what costs a second here.
    import nameparser  # the working tree -- verified, not assumed
    from nameparser import HumanName
    tree_at = _check_tree(nameparser.__file__)
    print(f"tree:     nameparser {nameparser.__version__} ({tree_at})")

    want_v2 = "v2" in surfaces
    if want_v2:
        from nameparser import Parser, Policy, parse
    tree_parsers: dict[str, object] = {}

    def _tree_parse(name: str, order: str | None) -> object:
        if order is None:
            return parse(name)
        if order not in tree_parsers:
            tree_parsers[order] = Parser(policy=Policy(
                name_order=getattr(nameparser, order)))
        return tree_parsers[order].parse(name)

    tell, old_rows = _run_worker(baseline, want_v2, entries)
    print(f"baseline: nameparser {tell['__version__']} ({tell['__file__']})")
    #: (name, order) pairs, not names: one string compared under two
    #: orders is two entries, and the report renders the order tag from
    #: the pair. Rendering at print time rather than storing the line
    #: keeps the bare name available to the Latin-only stat below,
    #: which would otherwise need a second list to drift out of step
    #: with this one.
    by_issue: dict[str, list[tuple[str, str | None]]] = {}
    #: the union of the diffs each rule explained, for over_declared_rules.
    #: Kept beside by_issue rather than inside it: the summary printout
    #: reads by_issue as a list of pairs.
    roles_by_issue: dict[str, set[str]] = {}
    # BOTH surfaces' old/new are retained, not just the facade's. A diff
    # can exist on the v2 surface alone -- an _ambiguities-only change is
    # facade-identical by construction, and is the case _surfaces_for
    # names as the whole reason to compare v2 -- and keeping only the
    # facade dicts would print such a name under UNEXPLAINED with no
    # field lines under it at all: a failure nobody can act on.
    unexplained: list[_Unexplained] = []
    # radar-tier equivalent of unexplained: reported, never fatal (#468)
    radar: list[tuple[dict, _Unexplained]] = []
    # every name that diffed, with its diff AND the order its
    # comparison ran under, so dormant_rules can ask which rule WOULD
    # have claimed one that no rule did -- the same question classify
    # asks, order included
    diffing: list[tuple[str, set[str], str | None]] = []
    #: (issue, name, order) for each diff an order-blind rule explained
    #: under a declared order. Informational, never fatal.
    order_blind: list[tuple[str, str, str]] = []
    #: classify() returns an issue; the notice needs the rule behind it.
    #: Keyed by issue because validate_rules has already refused two
    #: rules sharing one.
    rules_by_issue = {str(r["issue"]): r for r in rules}
    for entry, old in zip(entries, old_rows):
        name = entry["name"]
        order = entry.get("order")
        if order is None:
            new = {k: v or "" for k, v in HumanName(name).as_dict().items()
                   if k in FIELDS}
            # canonicalized on the way in: the ledger speaks Role's
            # names, and the facade is the surface whose vocabulary
            # differs
            diff = {_canonical_field(f) for f in FIELDS
                    if old["facade"].get(f, "") != new.get(f, "")}
        else:
            # order-bearing entries are compared on the v2 surface
            # alone -- the facade is the v1-compat surface, and a
            # family-first name is not a v1 contract
            new = {}
            diff = set()
        new_v2: dict[str, object] = {}
        if want_v2:
            p = _tree_parse(name, order)
            # must stay identical to the worker template's _v2_row
            # (_WORKER_TEMPLATE, this file) -- duplicated rather than
            # shared across the process boundary
            new_v2 = {f: (getattr(p, f, "") or "") for f in V2_FIELDS}
            new_v2["_ambiguities"] = sorted(
                {a.kind.name for a in getattr(p, "ambiguities", ())})
            diff |= {_canonical_field(f)
                     for f in (*V2_FIELDS, "_ambiguities")
                     if old.get("v2", {}).get(f, "") != new_v2.get(f, "")}
        if not diff:
            continue
        diffing.append((name, diff, order))
        issue = classify(name, diff, rules, exclusions, order)
        if issue is None:
            row = (name, old.get("facade", {}), new, old.get("v2", {}),
                   new_v2, order)
            # classify() returns None for two different reasons: no
            # rule matched, or a [[never]] entry refused the name --
            # and only the first belongs to the tier split. An
            # exclusion was chosen (see _CORPUS_TIERS), so it is fatal
            # on a radar name exactly as it is on a contract one.
            excluded = any(_entry_matches(x, name, diff)
                           for x in exclusions)
            if entry["tier"] == "radar" and not excluded:
                radar.append((entry, row))
            else:
                unexplained.append(row)
        else:
            by_issue.setdefault(issue, []).append((name, order))
            roles_by_issue.setdefault(issue, set()).update(diff)
            if order is not None and "orders" not in rules_by_issue[issue]:
                order_blind.append((issue, name, order))

    # the bare halves of by_issue's pairs: _is_latin_only reads the
    # string as a name, so it must never see the rendered order tag. A
    # string compared under two orders counts twice here, accepted.
    changed = [n for pairs in by_issue.values() for n, _ in pairs] \
        + [row[0] for row in unexplained] \
        + [e["name"] for e, _ in radar]
    latin = sum(1 for n in changed if _is_latin_only(n))
    print(f"corpus: {len(corpus)} names; "
          f"intentional diffs: {sum(map(len, by_issue.values()))}; "
          f"unexplained: {len(unexplained)}; "
          f"radar unclassified: {len(radar)}; "
          f"{latin} of {len(changed)} changed names are Latin-only\n")
    for issue, names in sorted(by_issue.items()):
        print(f"## {issue} ({len(names)})")
        for n, o in names[:10]:
            print(f"  {n!r}{_order_tag(o)}")
        print()
    # Informational, and deliberately outside the exit code: an
    # order-blind rule is legal, and every rule written before shape
    # tags is one. What the block buys is that the absorption stops
    # being invisible -- a rule sorted ahead of the scoped ones can
    # reach an order-bearing name its author never considered, and an
    # order-only regression on that name would then classify as an
    # intentional change.
    if order_blind:
        print("ORDER-BLIND (informational, not in the exit code): a rule "
              "carrying no `orders` key explained a diff from an "
              "order-bearing comparison. Consider scoping it with "
              "`orders` -- including the \"DEFAULT\" sentinel if it "
              "explains default-order diffs too.\n")
        for issue, name, tagged in order_blind:
            print(f"  {issue!r} explained {name!r}{_order_tag(tagged)}")
        print()
    dormancy = dormant_rules(rules, set(by_issue), diffing, exclusions)
    for dormant in dormancy.undeclared:
        print(f"EXPLAINED NOTHING {dormant.issue!r}\n    "
              f"{_DORMANT_WHY[dormant.kind].format(by=repr(dormant.detail))}")
    for issue in dormancy.awake:
        print(f"NO LONGER DORMANT {issue!r}\n    it explained a diff in "
              f"this run, so its `dormant` reason is now false -- remove "
              f"the key")
    if dormancy.undeclared or dormancy.awake:
        print()
    overwide = over_declared_rules(rules, roles_by_issue)
    for wide in overwide:
        # The ledger is NAMED, unlike the two blocks above, because this
        # rule's correct `fields` differ per baseline -- fix(#296) is
        # exactly exercised at 1.4.0 and over-declared at both 2.x -- so
        # a message without the file sends the reader to edit a rule
        # that is not the broken one, which is validate_rules' own
        # stated reason for carrying `ledger`.
        print(f"OVER-DECLARED {ledger.name}: {wide.issue!r}\n    "
              f"declares {list(wide.unused)}, which no diff it explains "
              f"moves; every one fits {list(wide.observed)}. Narrow "
              f"`fields` to that. classify() matches by SUBSET, so the "
              f"excess is not inert -- it lets this rule keep claiming a "
              f"name whose diff shrinks out of the extra role, with "
              f"nothing to say so (#452)."
              + (" NOTE: this run used --corpus, so the union above is "
                 "over a SUBSET and the repair may orphan a name the "
                 "full gate compares -- confirm before narrowing."
                 if args.corpus else ""))
    if overwide:
        print()
    # the radar rows below print the same Role-named field lines, so
    # the legend belongs to both blocks or the radar reader is told
    # nothing about the vocabulary they are reading
    if unexplained or radar:
        print("Field names below are Role's, matching what a ledger "
              "`fields` rule must say.\n")
    for name, old_facade, new, old_v2, new_v2, order in unexplained:
        # the order tag distinguishes a family-first regression from a
        # default-order one on the same name -- otherwise indistinguishable
        # in the report
        print(f"UNEXPLAINED {name!r}{_order_tag(order)}")
        _print_field_diffs(old_facade, new, old_v2, new_v2, order)
    if radar:
        print("\nRadar tier (scraped/harvested names, #468): shown, "
              "never blocking. Promote a name that matters via a "
              "cases.py row + shape tag.\n")
    for entry, (name, old_facade, new, old_v2, new_v2, order) in radar:
        labels = entry.get("tests")
        tag = f"   [v1: {', '.join(labels)}]" if labels else ""
        print(f"UNCLASSIFIED (radar) {name!r}{tag}{_order_tag(order)}")
        _print_field_diffs(old_facade, new, old_v2, new_v2, order)
    # A rule explaining nothing is as much a broken contract as an
    # unexplained diff: both mean the ledger no longer describes what the
    # code does. A rule explaining LESS than it declares is the third
    # way that happens -- it still matches, so nothing here looks
    # broken, but the `fields` it names are no longer what the code
    # moves. Same exit code for all three, so none of them is the one
    # nobody noticed.
    return 1 if unexplained or dormancy.undeclared or dormancy.awake \
        or overwide else 0


if __name__ == "__main__":
    raise SystemExit(main())
