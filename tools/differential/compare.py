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
import itertools
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
#: (name, old_facade, new_facade, old_v2, new_v2, order,
#: initials_only). Both halves are kept because a diff can exist on
#: the v2 surface alone, and a report that named such a diff without
#: showing it would be unactionable. `order` rides along so the report
#: can say which order produced the diff -- None for the default
#: order. `initials_only` is main()'s own verdict on the diff set
#: (#484): it rides along so _print_field_diffs can be TOLD whether
#: the derived view belongs in the block rather than re-deriving it
#: from the rows, which is the shape two copies of one rule take just
#: before they drift.
_Unexplained = tuple[str, dict[str, str], dict[str, str],
                     dict[str, object], dict[str, object], str | None,
                     bool]


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
    them -- two names match both honorific rules and are labelled by
    whichever comes first (three until the 2026-09-05 narrowing of the
    glued-peel name_regex took '김민준 박사님' off the glued rule;
    measured 2026-09-05 over the corpus*.jsonl union, and the twin
    sentence over that rule in the ledger itself says the same).

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
    # #484: a derived view, compared only where the roles agree
    row["_initials"] = p.initials() or ""
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
    hn = HumanName(name)
    row = {"facade": {k: v or ""
                      for k, v in hn.as_dict().items()
                      if k in V1_FIELDS}}
    # #484: HumanName.initials() exists at every baseline, 1.4.0 included
    row["facade"]["_initials"] = hn.initials() or ""
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
                       order: str | None = None, *,
                       initials_only: bool) -> None:
    """Print each moved field under one name, Role's, whichever
    surface(s) moved it. Shared by the UNEXPLAINED and UNCLASSIFIED
    (radar) blocks in main() -- one copy rather than two that can
    drift apart, the same reason _entry_matches is "one predicate
    rather than three copies".

    Role's names, not the facade's: both report blocks exist to be
    turned into a ledger rule, and a rule naming the facade's `first`
    is rejected by validate_rules at startup. Both surfaces are
    walked, and a ROLE is reported once even when both moved, since
    one rule covers it. `_initials` is the exception, and the last
    paragraph is why.

    `order` is None for a default-order entry, else the order both
    surfaces were read under. The "[v2 surface only]" tag means "the
    facade was compared and agreed" -- untrue for an order-bearing
    entry, whose facade is never consulted at all (main() passes empty
    dicts for it), so the tag is suppressed there rather than printed
    with a meaning it does not have.

    `initials_only` is main()'s VERDICT on the diff set, not a hint:
    the derived `_initials` view is printed only when it is what the
    diff consists of. Taking the answer rather than re-deriving it
    from the rows is the point -- main()'s roles-identical guard and
    this print cannot drift apart, so a block always pastes into a
    rule validate_rules accepts (`fields = ["family", "_initials"]` is
    refused, and a block showing that pair would invite exactly it).

    The facade's initials() and the core's are INDEPENDENT
    implementations -- the facade builds its string from
    `_initials_lists`, not from `_render.initials` -- so unlike a role
    the two can legitimately move to different strings, and the roles'
    print-it-once convention would hide the core's movement behind the
    facade's. So the v2 line is suppressed only when it would REPEAT
    the facade's: it prints whenever the core moved to a different
    (old, new) pair, tagged "[v2 surface]" to say both surfaces were
    compared and moved differently. One rule still covers both, the
    field name being the same -- but a block showing the facade's
    movement alone would have that rule written in the belief the core
    agreed. Read a bare facade line for what it says, then: the
    absence of a v2 line means the core did not move to a DIFFERENT
    pair -- it moved identically, or it did not move at all -- and
    never that the core agreed. The tag needs no order check to stay
    honest, because `facade_moved` can only be true where the facade
    was CONSULTED: main() passes empty dicts for an order-bearing
    entry, so the facade pair is ('', '') there, `facade_moved` is
    False, and the v2 line falls to the order-aware branch, which
    suppresses the tag.
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
    # #484: the derived view, printed exactly as main() compares it --
    # per surface, facade first, and twice when the two surfaces moved
    # DIFFERENTLY, which a role cannot do (see the docstring).
    if initials_only:
        facade_pair = (old_facade.get("_initials", ""),
                       new.get("_initials", ""))
        v2_pair = (old_v2.get("_initials", ""), new_v2.get("_initials", ""))
        facade_moved = facade_pair[0] != facade_pair[1]
        v2_moved = v2_pair[0] != v2_pair[1]
        if facade_moved:
            print(f"    _initials: {facade_pair[0]!r} -> {facade_pair[1]!r}")
        if v2_moved and (not facade_moved or v2_pair != facade_pair):
            if facade_moved:
                tag = "   [v2 surface]"
            else:
                tag = "" if order is not None else "   [v2 surface only]"
            print(f"    _initials: {v2_pair[0]!r} -> {v2_pair[1]!r}{tag}")


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
#: names, plus two pseudo-fields. `_ambiguities` carries reported
#: AmbiguityKinds -- a SEGMENTATION-only diff is facade-identical, so
#: this is the one name that can classify it -- and cannot enter a diff
#: below baseline 2.0. `_initials` (#484) carries the derived
#: initials() view and CAN enter one at 1.4.0, through the facade; it
#: enters only when every role and the ambiguity kinds agree (main()),
#: so a rule listing it lists nothing else (validate_rules).
_RULE_FIELDS = frozenset((*V2_FIELDS, "_ambiguities", "_initials"))
_RULE_KEYS = frozenset((
    "issue", "name_regex", "fields", "dormant", "orders",
    "precedes_narrower"))


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
    "corpus_cjk.jsonl": 67,     # 70 today, generated from the case table.
                                # LOWERED 95 -> 70 on 2026-09-01,
                                # deliberately: the CJK comma demotion
                                # moved 25 tolerated texts out of this
                                # file into corpus_cjk_tolerated.jsonl
                                # below. Nothing left the harness --
                                # the names are compared and classified
                                # exactly as before, on the radar tier.
                                # LOWERED again 70 -> 67 on 2026-09-05,
                                # the same way and for the same class:
                                # the trailing-period honorifics
                                # ('田中さん 様.' and its two twins) are
                                # the listing artifact the first
                                # sweep's criterion could not see
    "corpus_cjk_tolerated.jsonl": 22,  # 29 today, the tolerated half of
                                # the same generator: composed and
                                # wrapped CJK forms (comma listings,
                                # Latin titles and credentials,
                                # trailing ASCII periods) whose
                                # handling the contract stopped
                                # promising on 2026-09-01. 25 on the
                                # day it was created; the 26th is
                                # '지훈, 남궁민수', which had no case
                                # row until rules.md#W3 was demoted
                                # and the rules corpus stopped
                                # carrying it -- the row was written
                                # so the text moved tiers instead of
                                # leaving the harness. 29 since
                                # 2026-09-05, the three period rows.
                                # Floor left at 22: it guards against
                                # the file emptying, and this half only
                                # grows as the contract narrows
    "corpus_issues.jsonl": 370,  # 381 today, harvested and append-only
    "corpus_rules.jsonl": 150,  # 249 today, generated from rules.md.
                                # 248 until 2026-09-05, when W2's
                                # trailing-period example moved into
                                # the tolerated W3 and the builder
                                # stopped harvesting it -- the seventh
                                # text a CJK demotion has taken out of
                                # this file, and (measured 2026-09-05)
                                # the last CJK example anywhere outside
                                # W3 that carried a non-space ASCII
                                # character. 247 -> 249 later the same
                                # day, when the review round restored
                                # W2's second half and witnessed it
                                # with '김민준 박사님' and '선생님' --
                                # both already in corpus_cjk.jsonl, so
                                # the file grew and the deduped pool
                                # did not.
                                # 252 until 2026-09-01, when W3 took
                                # rules.md's `tolerated:` marker and
                                # build_rules_corpus.py stopped
                                # harvesting a marked rule: six comma
                                # texts left (W3's two, W2's two, C1's
                                # two) and two pure ones arrived with
                                # the W2 swap. Every one of the six is
                                # still compared and classified, from
                                # corpus_cjk_tolerated.jsonl above.
                                # Floor left at 150: it guards against
                                # the file emptying, and a demotion
                                # this size is nowhere near it
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
#: hold the names the contract does not answer for (#468) -- scraped
#: and harvested ones, and since 2026-09-01 the deliberately demoted
#: ones too: their diffs still classify against the ledger (release
#: notes want the grouping) but an unmatched one prints under
#: UNCLASSIFIED (radar) and cannot fail the run or demand a rule.
#: Promotion is a cases.py row plus a shape tag -- a name enters the
#: contract by being chosen -- or, for a demoted name that already
#: has rows, clearing `tolerated` on them (a shape tag is not
#: available to it: shapes 6/7 refuse composed and wrapped text, and
#: that refusal is why the name was demoted).
#:
#: A `[[never]]` exclusion is the same kind of choice, and stays fatal
#: on a name in a radar file for exactly that reason: someone wrote
#: the entry, its `why`, and its `examples`, so the shape it refuses
#: was chosen the same way a rule is -- unlike most of a radar file,
#: which nobody has looked at name by name. The tier split governs
#: what the contract answers for; a [[never]] entry declares a shape
#: nobody may explain away, so it outranks the tier the name happens
#: to sit in.
_CORPUS_TIERS = {
    "corpus.jsonl": "radar",
    "corpus_cjk.jsonl": "contract",
    # The one radar file whose names WERE looked at one by one: the
    # 2026-09-01 demotion moved them here by a reviewed flag on their
    # case rows, not by scraping. The tier still fits, and for the
    # reason the flag was written -- these are composed and wrapped
    # CJK forms (a comma listing, a Latin title or credential around a
    # CJK name, and since 2026-09-05 a trailing ASCII period on an
    # honorific) that native CJK writing does not contain, so the
    # differential stops answering for them. Radar is what "we still
    # watch it, we no longer enforce it" costs; the case rows still
    # assert every one of these parses in the suite.
    #
    # This entry demotes the FILE, which is not the same as demoting
    # every text in it: the dedup above loads contract files first and
    # keeps the contract reading, so a text some contract corpus also
    # holds reads contract no matter what this says. Five did on the
    # day this file was created -- rules.md examples, so
    # corpus_rules.jsonl held them too and they went on reading
    # contract. The rules.md edits later the same day took those five
    # out of corpus_rules.jsonl -- W3 marked tolerated, W2's two comma
    # examples swapped for pure ones, C1's two moved into W3 -- so
    # NONE do today and every text in this file reads radar. The rule
    # is stated as a rule, not as a caveat about the five: whatever
    # lands here next is demoted only once no contract corpus holds
    # it. What landed next needed exactly that. '田中さん 様.' was one
    # of the two pure texts the W2 swap brought IN, so the 2026-09-05
    # period-class demotion had to move that example line into the
    # tolerated W3 in the same breath as marking its case row --
    # marking the row alone would have left the name enforced and
    # documented as demoted. Still none today, and asked of every
    # contract file on every run by
    # test_the_tolerated_corpus_is_disjoint_from_the_contract_ones
    # (tests/v2/test_ledger_guards.py) rather than left to a reader.
    "corpus_cjk_tolerated.jsonl": "radar",
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
    for months and then explode mid-run, past the worker pass and deep
    into the comparison, in a traceback naming neither the file nor
    the rule.

    `ledger` is named rather than hardcoded because there is one per
    baseline now: a message naming the wrong file sends the reader to
    edit a rule that is not the broken one.

    The `dormant` check is the one exception to that framing: it is not
    about a rule's matching semantics drifting, but about an opt-out
    carrying a justification someone can review.
    """
    # A dict rather than a set because `precedes_narrower` (#382) needs
    # each rule's POSITION to check that an exemption points forward.
    # The membership test is the same one the dedupe check was written
    # with, and a rule's issue is unique by the time this loop ends, so
    # the index it records is unambiguous.
    positions: dict[str, int] = {}
    for k, rule in enumerate(rules):
        issue = rule.get("issue")
        if not isinstance(issue, str):
            continue  # the per-rule loop below rejects it with a better message
        if issue in positions:
            raise SystemExit(
                f"{ledger} has two rules sharing the issue {issue!r}. The "
                f"dormancy check identifies a rule by its issue, so the "
                f"second would hide behind the first: it could explain "
                f"nothing and never be reported")
        positions[issue] = k
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
        if "precedes_narrower" in rule:
            # #382. Where this rule deliberately outranks a NARROWER one
            # it would otherwise lose nothing by yielding to. Legal, and
            # never silent: `fields` cannot say that a wider rule
            # describes a compound behavior its component rule does
            # not, so the reason is the only place that fact can live.
            #
            # "Sits later in the file" means "loses to this rule" only
            # because #451 and #456 force every rule to carry BOTH
            # narrowing keys, which leaves one tier and makes
            # _sorted_rules the identity on any ledger that validates.
            # Relaxing either ban breaks the forward-only check below
            # rather than merely widening it: a fields-only rule at
            # position 1 could declare precedence over a name_regex rule
            # at position 5 and be accepted here, while _sorted_rules
            # puts the name_regex rule first and it is the one that
            # actually wins.
            declared = rule["precedes_narrower"]
            if not isinstance(declared, list) or not declared \
                    or not all(isinstance(e, dict) for e in declared):
                raise SystemExit(
                    f"{where} has a 'precedes_narrower' that is not a "
                    f"non-empty list of tables ({declared!r}). Write it "
                    f"as [[change.precedes_narrower]] blocks under the "
                    f"rule -- single-bracket [change.precedes_narrower] "
                    f"makes ONE table rather than a list of them -- and "
                    f"delete the key rather than leaving an empty one, "
                    f"which declares nothing")
            for entry in declared:
                unknown = set(entry) - {"issue", "why"}
                if unknown:
                    raise SystemExit(
                        f"{where} has {sorted(unknown)} inside a "
                        f"'precedes_narrower' entry, where only 'issue' "
                        f"and 'why' belong. If that key belongs to the "
                        f"RULE, move it ABOVE the "
                        f"[[change.precedes_narrower]] block: TOML binds "
                        f"every bare key after that header to the "
                        f"exemption, so a rule key written below it is "
                        f"silently dropped from the rule -- an 'orders' "
                        f"landing here deletes the rule's order "
                        f"narrowing and nothing else would notice")
                target, why = entry.get("issue"), entry.get("why")
                if not isinstance(target, str) or not target:
                    raise SystemExit(
                        f"{where} has a 'precedes_narrower' entry with "
                        f"no string 'issue': {entry!r}. An exemption "
                        f"names the ONE rule it outranks -- a blanket "
                        f"opt-out would be inherited by every narrower "
                        f"rule added later, which is the widening this "
                        f"check exists to refuse")
                if not isinstance(why, str) or not why.strip():
                    raise SystemExit(
                        f"{where} declares precedence over {target!r} "
                        f"with no 'why' ({why!r}). The reason is the "
                        f"whole safeguard, as it is for 'dormant': an "
                        f"exemption nobody had to justify is the one "
                        f"nobody reviews")
                if target not in positions:
                    raise SystemExit(
                        f"{where} declares precedence over {target!r}, "
                        f"which names no rule in this ledger. A rule's "
                        f"issue string is its identity here; a renamed "
                        f"or deleted rule leaves an exemption that "
                        f"protects nothing")
                if positions[target] == i:
                    raise SystemExit(
                        f"{where} declares precedence over ITSELF. An "
                        f"exemption names the OTHER rule this one "
                        f"outranks; no rule contests itself, so this is "
                        f"the declaring rule's own issue string copied "
                        f"where the narrower rule's belongs")
                if positions[target] < i:
                    raise SystemExit(
                        f"{where} declares precedence over {target!r}, "
                        f"which sits EARLIER in the file (rule "
                        f"#{positions[target] + 1}). An exemption names "
                        f"the narrower rule this one outranks, and that "
                        f"rule is by definition the later one -- so this "
                        f"is a copy-paste of the wrong issue string, "
                        f"sitting in the file reading as a justification")
            # The same copy-paste slip the `fields` duplicate check
            # refuses, and worse here: the second entry exempts a pair
            # already exempted, so it changes nothing -- but two reasons
            # for one pair means one of them is stale, and a reviewer
            # reading the ledger cannot tell which.
            targets = [e["issue"] for e in declared]
            dups = sorted({t for t in targets if targets.count(t) > 1})
            if dups:
                raise SystemExit(
                    f"{where} declares precedence over {dups} more than "
                    f"once in 'precedes_narrower'. One pair takes one "
                    f"exemption, so the repeat exempts nothing new; keep "
                    f"the reason that is still true and delete the rest")
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
            # `others` rather than len(fields) > 1: fields =
            # ["_initials", "_initials"] is longer than one and yet
            # mixes nothing, so the length test fired and printed an
            # empty list -- a refusal naming no second field, which is
            # the one thing the message exists to name. Nothing here
            # rejects a repeated field name, and this check is not the
            # place to start: it is about the MIX.
            dups = sorted({f for f in fields if fields.count(f) > 1})
            if dups:
                raise SystemExit(
                    f"{where} repeats {dups} in 'fields'. classify() "
                    f"reads 'fields' as a set, so the repeat changes "
                    f"nothing it matches -- it is a copy-paste slip that "
                    f"would otherwise pass every check below silently, "
                    f"and the '_initials' check in particular would read "
                    f"['_initials', '_initials'] as '_initials' alone")
            others = sorted(set(fields) - {"_initials"})
            if "_initials" in fields and others:
                raise SystemExit(
                    f"{where} lists '_initials' beside "
                    f"{others} in 'fields'. "
                    f"'_initials' enters a diff only when every role and "
                    f"the ambiguity kinds agree (#484), so no diff can "
                    f"carry it with another field: the '_initials' half "
                    f"of this rule is silently dead. Give the "
                    f"initials-only shape its own rule with "
                    f"fields = ['_initials']")
            if set(V2_FIELDS) <= set(fields):
                raise SystemExit(
                    f"{where} lists all seven roles in 'fields', so the "
                    f"subset test admits every ROLE diff -- the "
                    f"narrowing is not narrowing anything. Checked "
                    f"against the seven roles rather than against every "
                    f"legal entry, because the roles are the only names "
                    f"that ever co-occur in one diff: '_ambiguities' "
                    f"cannot appear below baseline 2.0, and '_initials' "
                    f"only ever appears alone (#484's roles-identical "
                    f"guard in main()). So all seven is already the "
                    f"widest a rule can be, and that is the widening "
                    f"this check refuses")
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
                f"256 of them from baseline 2.0 on, where `_ambiguities` "
                f"joins the seven roles and `_initials` adds the one "
                f"shape that stands alone, and 128 below it. #452 makes "
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
            # `others` rather than len(fields) > 1, as in
            # validate_rules: a repeated '_initials' is longer than
            # one and mixes nothing, and printed an empty list.
            dups = sorted({f for f in fields if fields.count(f) > 1})
            if dups:
                raise SystemExit(
                    f"{where} repeats {dups} in 'fields'. classify() "
                    f"reads 'fields' as a set, so the repeat changes "
                    f"nothing it matches -- it is a copy-paste slip that "
                    f"would otherwise pass every check below silently, "
                    f"and the '_initials' check in particular would read "
                    f"['_initials', '_initials'] as '_initials' alone")
            others = sorted(set(fields) - {"_initials"})
            if "_initials" in fields and others:
                raise SystemExit(
                    f"{where} lists '_initials' beside "
                    f"{others} in 'fields'. "
                    f"'_initials' enters a diff only when every role and "
                    f"the ambiguity kinds agree (#484), so no diff can "
                    f"carry it with another field: the '_initials' half "
                    f"of this entry is silently dead. Give the "
                    f"initials-only shape its own exclusion with "
                    f"fields = ['_initials']")
            if set(V2_FIELDS) <= set(fields):
                raise SystemExit(
                    f"{where} lists all seven roles in 'fields', which "
                    f"is what omitting the key already means. omit "
                    f"'fields' to exclude any diff on a matching name")


class _Contest(NamedTuple):
    """Two rules that file order alone separates (#382).

    `earlier` outranks `later` purely by position: there are diffs
    both rules admit, so `classify()` returns the first one it reaches.
    """
    #: issue of the earlier, WIDER rule -- the one that wins today
    earlier: str
    #: issue of the later, NARROWER rule
    later: str
    #: corpus names both `name_regex`es reach, sorted
    names: tuple[str, ...]


class _Reach(NamedTuple):
    """What one rule may claim, on each key _entry_matches narrows by."""
    issue: str
    fields: frozenset[str]
    #: corpus names its `name_regex` reaches
    names: frozenset[str]
    #: the orders it admits, or None when it declares none and so
    #: admits every order. _legal_orders() IS the set of every order,
    #: and substituting it here would still be wrong: _entry_matches
    #: reads an absent `orders` off the key's ABSENCE rather than off a
    #: member list, so on a rule list validate_rules never saw -- the
    #: hand-built ones the tests pass in -- the two readings diverge. A
    #: rule with `orders = ["MADE_UP"]` intersects _legal_orders() to
    #: the empty set and would stop being a contest, where classify()
    #: would happily run it against a real comparison and it IS one.
    orders: frozenset[str] | None


def _rule_reach(rules: list[dict[str, object]],
                names: list[str]) -> list[_Reach | None]:
    """Per rule: its issue, and what it may claim on each narrowing key.

    None for a rule this check cannot reason about -- a missing or
    mistyped `name_regex` or `fields`, or an empty `fields`. Every one
    of those is already refused by validate_rules with a better
    message; skipping rather than raising keeps this function usable on
    the hand-built rule lists the tests pass it, and an empty `fields`
    is skipped for a second reason: the empty set is a strict subset of
    every other, so admitting it would report a contest against every
    rule in the file.

    A mistyped `orders` is read as ABSENT rather than skipping the
    rule, which is what _entry_matches does with one: it tests
    `isinstance(orders, list)` and so returns a non-list rule to
    claiming every order. validate_rules rejects that shape too, and
    an empty `orders` besides -- so a frozenset here is never empty,
    and "declares orders" always means a real restriction.
    """
    out: list[_Reach | None] = []
    for rule in rules:
        pattern, fields = rule.get("name_regex"), rule.get("fields")
        if (not isinstance(pattern, str) or not isinstance(fields, list)
                or not fields or not all(isinstance(f, str) for f in fields)):
            out.append(None)
            continue
        orders = rule.get("orders")
        matcher = re.compile(pattern)
        out.append(_Reach(
            str(rule.get("issue", "")), frozenset(fields),
            frozenset(n for n in names if matcher.search(n)),
            frozenset(orders) if isinstance(orders, list) else None))
    return out


def order_contests(rules: list[dict[str, object]],
                   names: list[str]) -> list[_Contest]:
    """Every pair whose winner file order decides, exemptions IGNORED (#382).

    The predicate needs no diff shapes and that is what makes it cheap.
    It asks the three questions _entry_matches asks, one per narrowing
    key, and a pair is a contest only where all three overlap:

    `fields` -- where the later rule's are a STRICT subset of the
    earlier one's, every diff D fitting the narrower set passes both
    rules' subset test. The nesting supplies the contested shape's
    EXISTENCE, which is why no diff has to be computed: doing that
    properly would need the pinned-wheel worker pass, and could only
    ever remove pairs from this list, never add one.

    `name_regex` -- some corpus name must reach both, which the corpus
    supplies.

    `orders` -- some order must reach both. Two rules scoped to
    disjoint orders never see the same comparison, so file order
    decides nothing between them however nested their `fields` are,
    and calling that a contest would demand a justification for a
    hazard that cannot occur. A rule declaring no `orders` is
    order-blind and overlaps every other, which is every rule in every
    shipped ledger today.

    Equal `fields` are deliberately not a contest: neither rule is
    narrower, so "narrow-first" says nothing about the pair and
    _CROSS_RULE_WINNERS stays the instrument there.

    Read `precedes_narrower` through undeclared_contests, not here.
    This function is what the recorded negative control measures, and a
    control that consulted the mechanism it controls for measures
    nothing.
    """
    reach = _rule_reach(rules, names)
    found: list[_Contest] = []
    for i, j in itertools.combinations(range(len(rules)), 2):
        a, b = reach[i], reach[j]
        if a is None or b is None:
            continue
        if not b.fields < a.fields:
            continue
        if a.orders is not None and b.orders is not None \
                and not a.orders & b.orders:
            continue
        shared = a.names & b.names
        if shared:
            found.append(_Contest(a.issue, b.issue, tuple(sorted(shared))))
    return found


def _declared_over(rule: dict[str, object]) -> frozenset[str]:
    """Issues this rule declares precedence over (#382).

    Shape is validate_rules' business and this reader TRUSTS that it
    ran: main() validates every ledger before reaching any of this, and
    test_validate_rules_accepts_the_shipped_ledgers covers the files on
    disk. The leniency exists so the function stays usable on the
    hand-built rule lists the tests pass it. It is tempting to write
    it up as a safety property; it is not one. Of the shapes
    validate_rules refuses, four are refused toward REPORTING the
    contest -- a non-list value, an EMPTY list, an entry that is not a
    table, and an entry whose `issue` is not a string -- since each
    leaves that entry out of the set and a smaller set declares less.
    Two go the other way. An entry naming a real rule with a missing or
    blank `why` reads here as a perfectly good declaration and retires
    the pair; so does one whose `issue` is the EMPTY string, which
    validate_rules refuses as a blanket opt-out but the
    `isinstance(str)` test here admits -- and which retires the pair
    against any rule whose own issue reads as "", the shape
    `str(rule.get("issue", ""))` gives an issue-less hand-built rule.
    The blank `why` is the likeliest hand-edit slip in a ledger, and
    nothing in this function catches either of the two.

    So the guarantee is borrowed, not intrinsic. Reading strictly here
    would be no less safe -- a stricter reader declares LESS and so can
    only report MORE -- and the reason not to is convenience for
    callers, which is a much smaller claim than "the safe direction".
    """
    declared = rule.get("precedes_narrower")
    if not isinstance(declared, list):
        return frozenset()
    return frozenset(
        e["issue"] for e in declared
        if isinstance(e, dict) and isinstance(e.get("issue"), str))


def undeclared_contests(rules: list[dict[str, object]],
                        names: list[str]) -> list[_Contest]:
    """Contests whose earlier rule does not declare the later one (#382).

    The declaration is read off the rule that WINS the pair, which is
    the earlier one: an exemption is that rule saying it means to
    outrank its narrower neighbour, so it is the only rule whose word
    can retire the pair.

    `by_issue` is last-wins, so two rules sharing an issue string would
    let a declaration on the second copy retire a contest the first
    copy owns. validate_rules refuses duplicate issues, which is the
    only reason that is unreachable -- the same borrowed guarantee
    main()'s `rules_by_issue` leans on, and the same one _declared_over
    leans on for shape.
    """
    by_issue = {str(r.get("issue", "")): r for r in rules}
    return [c for c in order_contests(rules, names)
            if c.later not in _declared_over(by_issue.get(c.earlier, {}))]


class _Vacancy(NamedTuple):
    """An exemption whose pair stopped being a contest (#382).

    Named rather than a bare pair for _Dormancy's reason: the caller
    formats these into a message, and `v.earlier`/`v.later` says which
    end is which where `v[0]`/`v[1]` would not.
    """
    #: issue of the rule carrying the declaration
    earlier: str
    #: issue it declares precedence over
    later: str


def vacant_exemptions(rules: list[dict[str, object]],
                      names: list[str]) -> list[_Vacancy]:
    """Declared precedences over a pair that is NOT a contest (#382).

    A rule narrowed until it no longer overlaps its neighbour leaves
    its exemption behind, and the file then carries a justification for
    a hazard that is gone -- indistinguishable, to a reader, from one
    that is live. Same shape as `dormant`'s awake check: the ledger
    states a condition, and the harness refuses to let it go on
    standing after the condition stops holding.
    """
    live = {(c.earlier, c.later) for c in order_contests(rules, names)}
    return [_Vacancy(str(rule.get("issue", "")), later)
            for rule in rules
            for later in sorted(_declared_over(rule))
            if (str(rule.get("issue", "")), later) not in live]


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


class _ShapeMismatch(NamedTuple):
    """A recorded diff shape the run disagrees with (#497).

    Named rather than a bare triple for _Vacancy's reason: the caller
    formats these into a message, and `m.recorded`/`m.measured` says
    which side is which where `m[1]`/`m[2]` would not.
    """
    name: str
    #: the shape the roster records. Sorted HERE, at construction, like
    #: `measured` beside it -- a property of the instance and NOT a
    #: requirement on the literal row: a row spelled in any other order
    #: sorts to the same tuple and compares equal, so a sortedness
    #: guard over _RECORDED_DIFFS would refuse nothing and pin nothing.
    #: test_a_recorded_shape_matching_the_run_is_no_mismatch pins both
    #: sides of that.
    recorded: tuple[str, ...]
    #: what this run measured, sorted; None when the run produced no
    #: default-order diff of the name at all -- TWO states reach that,
    #: deliberately collapsed, and the docstring says what a message
    #: over one may and may not claim
    measured: tuple[str, ...] | None


#: The recorded diff shape of every name _CROSS_RULE_WINNERS pins
#: (tests/v2/test_ledger_guards.py), per ledger (#497).
#:
#: Baseline-relative by construction, which is why it is keyed per
#: ledger rather than once by name: a string moves a different set of
#: roles against different baselines, and decisions.md (2026-08-28
#: #452) records `fix(#296) a lone post-comma credential is a suffix`
#: moving four roles at 1.4.0 and two at both 2.x baselines. Since #501
#: the keying carries its own witness rather than resting on that
#: argument alone: 'MD, PHD' has a row in three sections, diffing
#: {family, given, suffix, title} at 1.4.0 and {suffix, title} at both
#: 2.x baselines, so one by-name keying could not hold what it does.
#:
#: A recorded shape that MOVES is a FINDING, not a number to update,
#: and it names no cause because it cannot: the parser may have changed
#: what that name does, or the row may have been wrong when it was
#: recorded, which is what the provenance below found four times.
#: Either way the winner pinned beside it in _CROSS_RULE_WINNERS was
#: recorded for the OLD shape, so both want reading before either is
#: edited.
#:
#: Every row here HAS such a winner, and this dict and
#: _CROSS_RULE_WINNERS are held to name the same strings. A shape
#: measured for a name nothing pins a winner for does not go here:
#: _WATCHED_DIFFS below is the roster for a shape with no argument
#: behind it, and this dict and that one are kept disjoint.
#:
#: HERE rather than beside the roster because this is where the
#: measurement happens. main() computes every name's real diff, so a
#: run can check these; the unit suite cannot, and deliberately -- it
#: spawns no uv and no network -- tests/v2/test_differential.py says
#: so in its own header, and the ones that need a baseline fake
#: _run_worker or fake Popen beneath it rather than installing a
#: wheel. Not "every test monkeypatches _run_worker": most never
#: mention it, and that loose paraphrase is #497's own subject
#: arriving inside #497's evidence. Same
#: direction as _CORPUS_FLOORS above, which lives here and is read from
#: there.
#:
#: Default-order shapes only, because the roster classifies with no
#: order. recorded_diff_mismatches below says what that leaves out.
#:
#: PROVENANCE. The 31 rows at 1.4.0 are measured against the 1.4.0
#: wheel, as the roster always claimed, and all 31 still agree --
#: re-measured 2026-09-03 by driving main() at all four baselines and
#: feeding its `diffing` and its post-skip corpus to
#: recorded_diff_mismatches, which is the recompute: wrap _run_worker to
#: capture the post-skip entries and dormant_rules to capture `diffing`,
#: since both receive exactly what main() built.
#:
#: The 2.x sections were EMPTY until #501, which is the question the
#: position recorded there was waiting on: contests were measured to
#: exist and nobody had argued a winner for one. Six are argued now
#: (2026-09-05), five at 2.0.0 and one at 2.1.0, and their shapes moved
#: in from _WATCHED_DIFFS unchanged -- a watched row is measured by a
#: run in the first place, which is what makes the move a move rather
#: than a fresh recording. _CROSS_RULE_WINNERS carries the argument per
#: row.
#:
#: The four rows #452 put in these sections, two per 2.x ledger, are a
#: different story and stay deleted. #497 ran that recompute against
#: them and all four recorded a shape no run makes:
#:   'Nguyen, Van' produces no diff at ANY of the four baselines. It is
#:   compared under the default order out of corpus_rules.jsonl every
#:   time, and the tree agrees with all four wheels on it, so {family}
#:   is a shape no run makes and no run ever asked classify() about the
#:   name at all. That is the position 'Doe,, Jr.' is in, which the
#:   roster gives no row precisely because it does not diff.
#:   'Jane née and Jones Smith' diffs {family, given, maiden, middle} at
#:   1.4.0, 2.0.0 and 2.1.0, and not at all at 2.2.0 -- never the
#:   {family, maiden, middle} recorded. Its shape WAS correctable, and
#:   the rows went anyway: the string is a malformed harvest from
#:   corpus_issues.jsonl (radar), the tree reads it family 'Jane' /
#:   maiden 'and Jones Smith', and nobody can state what it ought to
#:   parse to, so a pin on it defends no boundary anyone would argue
#:   for. In both 2.x ledgers fix(#445) is the only rule admitting it at
#:   either shape, measured, so no pin moved either way.
#: Deleting a row removes a PIN, not a name: corpus_issues.jsonl is
#: append-only and both strings are still compared, and classified, on
#: every run. 'Nguyen, Van' is classified by nothing only because it
#: diffs from nothing.
_RECORDED_DIFFS: dict[str, dict[str, tuple[str, ...]]] = {
    # open cycle: one rule, so nothing for a second one to contest
    "expected_since_2.2.0.toml": {},
    "expected_since_1.4.0.toml": {
        "Andrews, M.D.": ("given", "suffix"),
        "田中, 太郎さん": ("given", "suffix"),
        "김, 민준씨": ("given", "suffix"),
        "김, 민준씨 (Jimmy)": ("given", "suffix"),
        "김민준, 씨": ("given", "suffix"),
        "김민준, 씨.": ("given", "suffix"),
        "선생님, J.씨": ("given", "suffix"),
        "이, J.씨": ("given", "suffix"),
        "Dr 김민준씨, V.": ("family", "given", "suffix"),
        "田中さん, PhD": ("family", "given", "suffix", "title"),
        "田中さん, V.": ("family", "suffix"),
        "Bob Jones, author": ("family", "given"),
        "MD, PHD": ("family", "given", "suffix", "title"),
        "Smith Jr.": ("family", "suffix"),
        "Carod i": ("family", "suffix"),
        "田中さん II": ("family", "given", "suffix"),
        "de los Santos": ("_initials",),
        "van Berg Jan de": ("_initials",),
        "van ma van": ("_initials",),
        "Andersonさん": ("given", "suffix"),
        "김민준씨": ("family", "given", "suffix"),
        "김민준 씨.": ("family", "given", "suffix"),
        ".,": ("given",),
        "田中さん, Ph. D.": ("family", "given", "suffix"),
        "Kim, Jr.": ("family", "given", "suffix", "title"),
        "Smith, Jr.": ("family", "given", "suffix", "title"),
        "김민준씨 Jr.": ("family", "given", "suffix"),
        "de la Vega y Santos Juan": ("_initials",),
        "Abu Bakr Al Baghdadi, MD": ("_initials",),
        "abu bakr al baghdadi": ("_initials",),
        "Berg, abdul van": ("_initials",),
    },
    # #501's six, moved here from _WATCHED_DIFFS with their shapes
    # unchanged. The four CJK rows sit at 2.0.0 alone: the honorific
    # and order rules that contest them are 2.1 behavior, so those
    # names diff at 1.4.0 and 2.0.0 and not against the 2.1.0 wheel at
    # all. 'MD, PHD' diffs at all three and now carries a row at each.
    #
    # FOUR of the six ROWS sit on RADAR-tier names, and they are THREE
    # distinct names -- '田中さん 様.' and '田中さん, 様.' in
    # corpus_cjk_tolerated.jsonl and 'MD, PHD' in corpus_issues.jsonl,
    # the last carrying a row at each 2.x baseline and so counting
    # twice among the rows and once among the names (measured
    # 2026-09-05) -- so a moved shape on them is fatal where a watched
    # row would only have printed. That is the SEVERITY rule
    # below applied as written and accepted deliberately (#501): a
    # contest row is fatal on either tier because it carries an
    # argument, and a moved shape has made that argument's premise
    # false. The precedent is the section above, where 22 of the 31
    # rows are radar-tier names on exactly those terms (measured
    # 2026-09-05).
    "expected_since_2.0.0.toml": {
        "田中さん 様.": ("family", "given", "suffix"),
        "田中さん, 様.": ("family", "given", "suffix"),
        "김민준 박사님": ("family", "given", "suffix"),
        "선생님": ("family", "given"),
        "MD, PHD": ("suffix", "title"),
    },
    "expected_since_2.1.0.toml": {
        "MD, PHD": ("suffix", "title"),
    },
}


#: The recorded diff shape of a name NO WINNER IS PINNED FOR, per
#: ledger. A second roster under a different contract from the one
#: above, and the difference is the whole reason it is a second dict
#: rather than more rows in the first: a shape beside a winner
#: ADJUDICATES a contest -- _RECORDED_DIFFS records what a name diffs
#: so that _CROSS_RULE_WINNERS can ask classify() which rule wins it
#: -- where a shape alone WATCHES the name without adjudicating it.
#: "No winner pinned" is the property every row here has and two
#: checks enforce -- the disjointness guard in
#: tests/v2/test_ledger_guards.py and main()'s `both` refusal; it is
#: not "nothing else watches" -- though since #501 took the five
#: contested rows to _RECORDED_DIFFS, every row here is in fact
#: sole-watched, and the roster and the population the sweep drew
#: (POPULATION below) are the same set. That is a fact about today's
#: rows and NOT a second contract: a name whose parse a Case(...) row
#: already pins is welcome here the day it is measured and no winner
#: is argued for it, which is the position all five held from
#: 2026-09-03 until #501 argued one. What sole-watched means: a radar
#: name that no test names and no
#: contract corpus holds is watched only by the classification rule
#: that explains its diff, and a rule is a weak watcher, asserting
#: that a diff here is intended and not what the diff IS, so a diff
#: that changes shape while staying inside the rule's `fields` moves
#: silently. A row here says what the diff is, and the move becomes
#: a finding.
#:
#: Four things follow from the split, and each is checked rather than
#: stated:
#:   DISJOINT from _RECORDED_DIFFS, per ledger. A name is one kind of
#:   row or the other. A name with BOTH an argument and no other
#:   watcher belongs above, since the argument is the stronger claim.
#:   test_the_watched_roster_is_disjoint_and_names_every_ledger
#:   (tests/v2/test_ledger_guards.py) refuses an overlap at pytest
#:   speed, and main() refuses it again pre-worker, because this tool
#:   may not assume the suite ran.
#:   NO WINNER, ever. A winner pin asserts an argument about which rule
#:   should explain a name, and no row here carries one -- which is
#:   what lets a row here be recorded from a measurement where a winner
#:   cannot be. The day someone argues a winner, the row MOVES to
#:   _RECORDED_DIFFS and the pin goes beside it there; it does not gain
#:   a partner here.
#:   MEASURED, from a run, and re-measured by every run. Everything
#:   in main() that reads _RECORDED_DIFFS reads this dict too (the two
#:   winner guards in tests/v2/test_ledger_guards.py read that dict
#:   alone, correctly): the missing-section refusal pre-worker asks
#:   each dict for a section, the departed-name refusal beside it and
#:   the NOT CHECKED note read the literal UNION of the two, and the
#:   shape comparison calls recorded_diff_mismatches once PER dict,
#:   because the two halves carry different severities and the exit
#:   code reads only one of them. A row in either dict that no run
#:   can contradict is the defect #497 is about, whichever dict it
#:   sits in.
#:   SEVERITY follows the row's kind first and the name's tier second.
#:   A contest row is fatal on either tier: it carries an argument, and
#:   a moved shape has made that argument's premise false. A watched
#:   row on a CONTRACT-tier name fails the run, as an unexplained diff
#:   on that name would; on a RADAR-tier name it prints under MOVED
#:   SHAPE (radar) and feeds no exit code. Fatal-on-radar is reserved
#:   for a per-name deliberate choice -- a [[never]] entry with its
#:   `why` (_CORPUS_TIERS), or a contest row with its pinned winner --
#:   and a measured snapshot is neither: the
#:   only repair a fired snapshot admits is to re-snapshot, and a gate
#:   whose repair is "record whatever it does now" is a changelog entry
#:   in a gate's clothing. The tier is the DEFAULT-ORDER entry's when
#:   the name has one, and the first-loaded entry's (contract whenever
#:   any is) only when it does not -- a shape here is measured on the
#:   default-order comparison, so that comparison's entry is the one
#:   whose tier says whether the shape was promised, and a
#:   baseline-scoped tier is a property of the ENTRY compared, not of
#:   the files the string sits in (decisions.md, the rule-order arc).
#:   So a name that is contract only under a declared order and radar
#:   under the default reads radar here, and the declared-order promise
#:   is untouched.
#:
#: POPULATION, measured 2026-09-05. A name has a row here where it is
#: SOLE-WATCHED at that baseline: held by a radar corpus and by no
#: contract corpus; named by no string literal anywhere under tests/
#: outside test_ledger_guards.py -- every string ast.Constant, by exact
#: equality, since substring matching would score 'A. D.' a watcher of
#: every longer name containing it; diffing under the DEFAULT order at
#: that baseline AND explained by a ledger rule there -- a diff no
#: rule explains is already printed by every run as unclassified, so
#: a rule is the only weak watcher a row here is needed for (a
#: definition clause, not a live count: `radar unclassified` is 0 at
#: every baseline today, so the two sets coincide); and not already
#: keyed in _RECORDED_DIFFS for that
#: ledger. The last clause is the one a scan of tests/ cannot supply,
#: because that scan cannot see this file, and it excludes four names
#: that carry contest rows: 'Bob Jones, author', 'Carod i', 'MD, PHD',
#: 'van ma van'. TWO of them return at a 2.x baseline where they have
#: no contest row. The other two have no row in this dict at all:
#: 'Carod i' diffs under the default order at 1.4.0 only, where its
#: contest row stands, and 'MD, PHD' carries a contest row at every one
#: of the three baselines it diffs at since #501 pinned its 2.x pair.
#: That is why the population is 50 names where the tests/-only scan
#: says 52.
#: The counts: 41 / 31 / 30 / 5 rows, 107 in all, over those 50 names
#: -- and the roster is now exactly the population, the five contest
#: rows beyond it having gone to _RECORDED_DIFFS with #501.
#: 48 of the 50 sit in corpus_issues.jsonl and 3 in corpus.jsonl, with
#: 'dr Vincent van Gogh dr' in both, so the per-file counts overlap by
#: one and are not a partition. Every row is a default-order shape,
#: as the roster above's are, so no row here is a declared-order-only
#: diff for NOT CHECKED to name.
#:
#: RECOMPUTE: wrap classify() and drive main() unchanged at each
#: baseline, recording (name, order, diff, rule) per call; keep the
#: calls whose order is None and whose rule is not None; apply the
#: four clauses above with the literal set from ast.walk over
#: tests/**/*.py EXCLUDING test_ledger_guards.py, as the POPULATION
#: clause says -- run over every file it yields 38 / 28 / 27 / 4 rows
#: rather than 41 / 31 / 30 / 5, since _CROSS_RULE_WINNERS' keys and
#: a few guard literals then score as watchers -- the tier sets from
#: _load_entries over corpus*.jsonl
#: through _CORPUS_TIERS, and that ledger's _RECORDED_DIFFS keys. Not
#: by replaying the corpus load by hand: the (name, order) dedup, the
#: baseline-minimum skip and the tier stamp all happen inside main(),
#: and a name's membership is a property of the entry that run
#: compared.
#:
#: Two limits. The population is a LOWER bound: a literal in a test
#: that is not about parsing -- 'John Smith' in a TypeError test --
#: scores as a watcher, so a name a test merely mentions has no row
#: here although nothing checks its parse. And nothing notices a NEW
#: sole-watched name arriving with no row. A completeness guard has
#: to answer "what else watches this name" mechanically, and its
#: other half, "diffs at some baseline", only a run with the wheel
#: knows -- so that guard is a run-time NOTE in the NOT CHECKED family
#: by necessity, not a pytest-speed roster check, and it is not here.
_WATCHED_DIFFS: dict[str, dict[str, tuple[str, ...]]] = {
    "expected_since_1.4.0.toml": {
        "1 & 2, 3 4 5, Mr.": ("_initials",),
        "Aishwarya Rai": ("family", "suffix"),
        "Anh do": ("_initials",),
        "Anna Müller (geb. Schmidt)": ("maiden", "nickname"),
        "Anna Müller geb. Schmidt": ("family", "maiden", "middle"),
        "Attorney General of Minnesota": ("_initials",),
        "Bob Jones, compositeur": ("family", "given"),
        "Dean of Chemistry": ("_initials",),
        "Dean of Chemistry Robert Johns": ("_initials",),
        "Deputy Secretary of State": ("_initials",),
        "Do Quang Minh": ("given", "middle", "title"),
        "Donald mc": ("family", "suffix"),
        "Dr 田中さん, V.": ("family", "given", "suffix"),
        "Dr. Do Van Johnson, MD": ("family", "given"),
        "Duke of Edinburgh": ("_initials",),
        "Esq. van Gogh": ("family", "given"),
        "Jack M.A.": ("family", "suffix"),
        "Jane van der Berg 旧姓 Jones": ("family", "maiden"),
        "Janey née Jones": ("family", "given", "maiden", "middle"),
        "John V": ("family", "suffix"),
        "John of the Doe": ("_initials",),
        "Jong van der": ("_initials",),
        "Jong, van der": ("_initials",),
        "Jose e Maria Santos": ("_initials",),
        "Juan Garcia y Lopez": ("_initials",),
        "MD, DO, DDS": ("given", "title"),
        "Mesnil Garcia van": ("_initials",),
        "Mohamad X": ("family", "suffix"),
        "Ph. D., Jr.": ("family", "given"),
        "QC MP": ("family", "suffix"),
        "Sander van": ("_initials",),
        "Smith Jones, Ph. D. Jr.": ("suffix",),
        "Smith, Ph. D.": ("family", "given"),
        "Smith, Ph. D. Jr. MD": ("given", "suffix", "title"),
        "Smith, Ph. D. MD": ("suffix", "title"),
        "Smith, Ph.D. Jr.": ("given", "suffix"),
        "Smith, Prof.": ("family", "given"),
        "Ursula von der Leyen (geb. Albrecht)": ("maiden", "nickname"),
        "dr Vincent James van Gogh dr": ("family", "suffix"),
        "dr Vincent van Gogh dr": ("family", "suffix"),
        "dr Vincent van der Gogh dr": ("family", "suffix"),
    },
    "expected_since_2.0.0.toml": {
        "Anh do": ("_initials",),
        "Anna Müller (geb. Schmidt)": ("maiden", "nickname"),
        "Bob Jones, author": ("family", "given"),
        "Bob Jones, compositeur": ("family", "given"),
        "Do Quang Minh": ("_ambiguities", "given", "middle", "title"),
        "Dr 田中さん, V.": ("family", "given", "suffix"),
        "Dr. Do Van Johnson, MD": ("family", "given"),
        "E Anne D,Leonardo": ("_initials",),
        "Esq. van Gogh": ("_ambiguities", "family", "given"),
        "JOSE E MARIA SANTOS": ("_initials",),
        "Jane van der Berg 旧姓 Jones": ("family", "maiden"),
        "Janey née Jones": ("family", "given"),
        "Joe E. Smith": ("_initials",),
        "John, Smith, Dr.": ("_ambiguities",),
        "Jong van der": ("_initials",),
        "Jong, van der": ("_initials",),
        "Jose E. Maria Santos": ("_initials",),
        "MD, DO, DDS": ("given", "title"),
        "Mesnil Garcia van": ("_initials",),
        "Ph. D., Jr.": ("family", "suffix", "title"),
        "Sander van": ("_initials",),
        "Smith Dr": ("family", "suffix"),
        "Smith, John E, III, Jr": ("_initials",),
        "Smith, Ph. D. Jr. MD": ("given", "suffix"),
        "Smith, Ph. D. MD": ("given", "suffix"),
        "Smith, Ph.D. Jr.": ("given", "suffix"),
        "Ursula von der Leyen (geb. Albrecht)": ("maiden", "nickname"),
        "dr Vincent James van Gogh dr": ("family", "suffix"),
        "dr Vincent van Gogh dr": ("family", "suffix"),
        "dr Vincent van der Gogh dr": ("family", "suffix"),
        "van ma van": ("_initials",),
        # The four #501 contests that closed this section, and 'MD, PHD'
        # beside them, are GONE from it: #501 argued a winner for each
        # on 2026-09-05 and the five rows moved to _RECORDED_DIFFS with
        # their shapes unchanged, which is what this dict's NO WINNER
        # clause says happens the day one is argued. Nothing about them
        # is left here to go stale, the tier note included -- what a
        # contest row costs is _RECORDED_DIFFS' subject now.
    },
    "expected_since_2.1.0.toml": {
        "Anh do": ("_initials",),
        "Anna Müller (geb. Schmidt)": ("maiden", "nickname"),
        "Bob Jones, author": ("family", "given"),
        "Bob Jones, compositeur": ("family", "given"),
        "Do Quang Minh": ("_ambiguities", "given", "middle", "title"),
        "Dr. Do Van Johnson, MD": ("family", "given"),
        "E Anne D,Leonardo": ("_initials",),
        "Esq. van Gogh": ("_ambiguities", "family", "given"),
        "JOSE E MARIA SANTOS": ("_initials",),
        "Jane van der Berg 旧姓 Jones": ("family", "maiden"),
        "Janey née Jones": ("family", "given"),
        "Joe E. Smith": ("_initials",),
        "John, Smith, Dr.": ("_ambiguities",),
        "Jong van der": ("_initials",),
        "Jong, van der": ("_initials",),
        "Jose E. Maria Santos": ("_initials",),
        "MD, DO, DDS": ("given", "title"),
        "Mesnil Garcia van": ("_initials",),
        "Ph. D., Jr.": ("family", "suffix", "title"),
        "Sander van": ("_initials",),
        "Smith Dr": ("family", "suffix"),
        "Smith, John E, III, Jr": ("_initials",),
        "Smith, Ph. D. Jr. MD": ("given", "suffix"),
        "Smith, Ph. D. MD": ("given", "suffix"),
        "Smith, Ph.D. Jr.": ("given", "suffix"),
        "Ursula von der Leyen (geb. Albrecht)": ("maiden", "nickname"),
        "dr Vincent James van Gogh dr": ("family", "suffix"),
        "dr Vincent van Gogh dr": ("family", "suffix"),
        "dr Vincent van der Gogh dr": ("family", "suffix"),
        "van ma van": ("_initials",),
    },
    "expected_since_2.2.0.toml": {
        "E Anne D,Leonardo": ("_initials",),
        "JOSE E MARIA SANTOS": ("_initials",),
        "Joe E. Smith": ("_initials",),
        "Jose E. Maria Santos": ("_initials",),
        "Smith, John E, III, Jr": ("_initials",),
    },
}


def recorded_diff_mismatches(
        recorded: dict[str, tuple[str, ...]],
        diffing: list[tuple[str, set[str], str | None]],
        compared: set[str]) -> list[_ShapeMismatch]:
    """Recorded shapes this run contradicts (#497).

    The roster in tests/v2/test_ledger_guards.py pins WHICH RULE wins a
    contested name, and to ask that question it needs the diff shape --
    which it reads from _RECORDED_DIFFS above and feeds to classify() as
    an input. Nothing checks the shape itself, so a guessed one agrees
    with itself forever. This is the half only a run can do: main() has
    already measured every name's real diff by the time it calls this.
    `recorded` is whichever roster the caller hands over -- nothing
    here knows a contest row from a watched one, and main() calls this
    once per dict and applies the severity to what comes back, since
    the two kinds differ in what a mismatch means and not in how one is
    found.

    Only the order-None comparison is read. The roster calls classify()
    with no order, so the shape it records is the default-order one; a
    string also compared under a declared order is a different question
    and its own row would be needed to ask it.

    `compared` is the names this run actually compared: the entry list
    AFTER the baseline-minimum skip -- main()'s `corpus`, NOT the
    `corpus_names` the contest checks read, which is built before that
    skip runs. The two differ by exactly the entries an old baseline
    cannot honor -- 7 of them at 1.4.0, where 1120 load and 1113
    compare; re-measure by running this file with `--baseline 1.4.0`
    and reading its `skipped` and `corpus:` lines. Those are ENTRY
    counts. The paragraph further down counts NAMES, which is why the
    same skip reads as 7 here and as 3 there: an entry is a (name,
    order) pair, so the 1120 deduped entries carry 1116 distinct
    strings -- three strings are compared under more than one order
    ('de la Cruz Juan Carlos' under three, 'John Smith, Dr.' and 'de
    la Cruz née Vega' under two) -- and four of the seven skipped
    entries are the whole of the three names named below, while the
    other three have a same-name twin that survives the skip.
    decisions.md, "the rule-order arc", records the same trap for the
    contest checks,
    which read the pre-skip list on purpose. Pass that list here and a
    roster row whose only entry was skipped reports as a name that
    stopped diffing, when it was never compared at all.

    A name absent from `compared` is SKIPPED rather than reported. Under
    `--corpus` the name set is narrowed, and absence is then a fact
    about the run rather than about the roster. That is only the SUBSET
    half of what the vacancy check's caller does with the same
    asymmetry (#382): under a FULL run that caller refuses a
    declaration whose pair is gone, and nothing here refuses a recorded
    name no corpus holds any more -- forgiving forever the very shape
    #497 is about. That half belongs to the caller, the only side that
    knows whether this run read every corpus; main() does it, under a
    full run alone, asking `set(recorded) - set(corpus_names)`: the
    PRE-skip list, which is the opposite of what `compared` takes in
    the paragraph above, and deliberately so.
    Two different questions. "Was this name compared?" is about the
    RUN, and an entry the baseline skipped was not; "does any corpus
    still hold this name?" is about the FILES, and the skip removes a
    name from no file. Measured at --baseline 1.4.0, the two lists
    differ by three names -- 'de Mesnil Jean, Dr.', 'de la Cruz Juan
    Carlos, Dr.' and 'de la Cruz née Vega', each order-bearing with no
    order-None twin to keep it in `compared`, and each sitting in
    corpus_shapes.jsonl the whole time. Refusing off the post-skip list
    would tell a contributor to delete a roster row for a name that is
    right there, at the compat baseline. `full_corpus` does not screen
    that: it is _CORPUS_FLOORS against the files on disk and knows
    nothing about the skip. It is the earlier-draft `vacant` bug
    recorded below, one baseline over.
    Those three names are the WINDOW between the two halves, and not
    refusing is not the same decision as saying nothing: a row on one
    of them is checked by neither side, so main() prints a NOT CHECKED
    note over `set(recorded) & set(corpus_names) - compared` -- naming
    them, claiming nothing about them, and feeding no exit code. That
    note is the caller's too, for the reason this whole paragraph is:
    only the caller holds both lists.

    A name that IS compared and produces no default-order diff is
    reported with `measured` None, and two states reach that: the
    parser stopped diffing a name recorded as diffing, or the name is
    compared under a declared order ALONE, so no default-order
    comparison of it exists to have a shape. They are collapsed because
    nothing in these arguments separates them. main() appends to
    `diffing` only where a comparison DIFFED, so a name compared under
    the default order that produces no diff leaves no row at all, and
    the two states hand this function byte-identical `diffing` and
    `compared` -- constructed and run, not reasoned about. The
    distinction lives in the ORDERS each name was compared under, which
    is main()'s `entries` and would be a fourth argument here. So a
    message over these rows may say the run measured no default-order
    diff, and must NOT say the name stopped diffing; and a caller must
    not try to label them off `diffing`, which cannot answer it.
    _Dormant's `kind` is the shape to copy if that fourth argument is
    ever added and the two are told apart.
    """
    measured = {name: tuple(sorted(diff))
                for name, diff, order in diffing if order is None}
    out: list[_ShapeMismatch] = []
    for name, shape in recorded.items():
        if name not in compared:
            continue
        got = measured.get(name)
        want = tuple(sorted(shape))
        if got != want:
            out.append(_ShapeMismatch(name, want, got))
    return out


def _two_causes(rows: list[_ShapeMismatch]) -> str:
    """The MOVED SHAPE blocks' disclaimer over a row with no measured
    shape. One-time like the lead it follows, and conditional as well:
    a block whose rows all carry a measured shape would otherwise print
    repair advice for a case that did not occur, which is what
    OVER-DECLARED's `--corpus` NOTE is conditional to avoid. Shared by
    the three blocks because the two causes are a property of
    recorded_diff_mismatches, not of the roster a row came from."""
    return ("\n  A row reading 'measured no default-order diff' "
            "names no cause because TWO reach it and this check "
            "cannot separate them: the parser may have stopped "
            "moving the name, or the name may be compared under a "
            "declared order alone, leaving no default-order "
            "comparison to have a shape. Read the corpus entry "
            "before you read the parser."
            if any(m.measured is None for m in rows) else "")


def _print_moved_rows(rows: list[_ShapeMismatch], roster: str) -> None:
    """The rows under a MOVED SHAPE lead, naming the dict each lives in
    so the reader edits the right one. Trailing blank line included:
    the caller prints a lead only when it has rows, so the two are one
    unit."""
    for m in rows:
        measured = (f"measured {list(m.measured)}"
                    if m.measured is not None
                    else "measured no default-order diff of it")
        print(f"  {m.name!r}\n    {roster} records "
              f"{list(m.recorded)}; this run {measured}")
    print()


def _load_entries(path: Path) -> list[dict[str, object]]:
    """Corpus lines as entry dicts. A line is either a bare JSON
    string (the original format) or an object with a "name" plus
    optional metadata -- "tests" labels from build_corpus.py, and a
    "shape" id from build_shapes_corpus.py (#469). Tolerating both
    means compare.py itself never needs a flag day as corpora are
    added or converted: corpus.jsonl and corpus_shapes.jsonl carry
    object lines, the rest are still bare strings, and both shapes
    stay legal everywhere a corpus line is read. Counting the files
    here said five over six, and the object/string split three over
    four, which is the "all five corpora" claim #497 swept out of
    three other files -- it survived because that sweep never
    reached compare.py. The glob is the count.

    A "tests" label is read only when the radar block prints, at the
    very end of the run and well past the worker pass, so a malformed
    one left unchecked would crash there rather than here -- exactly
    what validate_rules' compile-at-startup paragraph exists to
    prevent.

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
    #
    # The same question, asked of the names rather than of the flag,
    # answers "is this run over the FULL corpus" for the two checks
    # below whose verdict inverts under narrowing -- the vacancy check
    # and the departed-name half of the recorded-shape check (#497).
    # That is what both need, and it is not the same as "was --corpus
    # omitted": the flag is `action="append"`, so naming every corpus
    # explicitly narrows nothing.
    missing = sorted(set(_CORPUS_FLOORS) - {p.name for p in paths})
    full_corpus = not missing
    if not args.corpus:
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
        # The VALUE too, not only the key's presence: every tier read
        # downstream is a comparison against one of the two literals,
        # and a misspelled value passes each of them on the side its
        # `!=` happens to fall -- fatal in the comparison loop and in
        # the watched-shape split, which is the safe direction there,
        # but by accident rather than by choice, and nothing would
        # ever name the misspelling.
        if tier not in ("contract", "radar"):
            raise SystemExit(
                f"{path.name} has tier {tier!r} in _CORPUS_TIERS, which "
                f"is neither 'contract' nor 'radar'. Every tier read "
                f"below compares against those two literals, so a third "
                f"value is not a third tier but whichever side of each "
                f"comparison the misspelling falls on")
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
    # Order checks here rather than beside validate_rules, which runs
    # before any corpus is read: whether two rules CONTEST a diff is a
    # question about NAMES -- both regexes have to reach one -- and the
    # names arrive at this line. Before the worker pass, deliberately:
    # a ledger refused after the worker runs has already installed the
    # pinned wheel and parsed the whole corpus for a comparison that
    # will never be made, and it refuses below its own published
    # `baseline:` header (#382). It is the ORDER of the two that earns
    # this placement and not the wait -- the worker pass is a fraction
    # of a second, and the "multi-minute" this comment used to argue
    # from was withdrawn as unmeasured (#497, and decisions.md, "the
    # rule-order arc", which carries the dated figures).
    #
    # The names are the LOADED entries, not the corpus*.jsonl glob the
    # unit guard in tests/v2/test_ledger_guards.py reads: `--corpus`
    # narrows what this run compares, and a run is judged on the names
    # it read, while the guard judges every corpus on disk.
    #
    # LOADED, precisely -- this sits ahead of the baseline-minimum
    # shape skip below, so `corpus_names` holds names an old baseline
    # will not actually compare (1120 here against the 1113 the 1.4.0
    # run reports; the 7 are order-bearing shape-4/5 names). Kept ahead
    # of it on purpose: the check then asks the same question at every
    # baseline, as the unit guard does, and moving it after `kept`
    # would make a ledger's acceptability depend on which release it is
    # being compared against.
    #
    # THE TWO CHECKS READ A SMALLER NAME SET IN OPPOSITE DIRECTIONS,
    # which is the whole reason only one of them refuses below. Dropping
    # names can only remove contests. For `undeclared` that can only
    # UNDER-REPORT, never false-alarm: fewer contests is fewer pairs
    # anyone owes a declaration, so a partial run is strictly more
    # lenient and can never invent a refusal. (Not "fail-closed" --
    # this file uses that term above for the _CORPUS_FLOORS and
    # _CORPUS_TIERS rosters, which REFUSE on a missing entry, and a
    # check that errs toward not refusing is the opposite of that.)
    # For `vacant` it INVERTS -- a live declaration whose contested
    # names are outside this run reads exactly like a stale one. Measured: every one of the six corpora,
    # run alone against expected_since_1.4.0.toml, reports vacancies --
    # 11 of the 11 exemptions for corpus.jsonl, corpus_cjk.jsonl and
    # corpus_shapes.jsonl, and 8, 7 and 5 for the other three. So a
    # partial run NOTES that count and does not act on it.
    #
    # FOUR CHECKS READ THE NARROWING AT FOUR DIFFERENT STRENGTHS, and
    # the differences are the point rather than an inconsistency to
    # tidy. The corpus-floor roster above is SKIPPED entirely, because
    # narrowing is what the flag is for. over_declared_rules still
    # FAILS the run -- `overwide` feeds the exit code on every run --
    # and only appends a NOTE that the union it computed is over a
    # subset, so its repair advice is not followed blindly. `vacant`
    # does not fail, because its VERDICT inverts under narrowing rather
    # than merely its evidence. `gone` below -- the roster rows naming
    # a departed name (#497) -- inverts the same way and goes one step
    # further, staying SILENT: `vacant` prints a count a reader might
    # act on, and there recorded_diff_mismatches has already dropped
    # those names without reporting one, so a NOTE would carry noise
    # and no information. Its own comment measures how much.
    # Do not fold the two branches below back into one
    # shape, and do not level the four checks onto one strength: an
    # earlier draft of `vacant` refused under `--corpus` and told the
    # contributor to delete legitimate exemptions. The shape comparison
    # after the worker -- MOVED SHAPE at either severity, and MOVED
    # SHAPE (radar) -- reads the flag not at all: recorded_diff_mismatches
    # skips a name outside `compared`, and that skip is the whole of
    # its narrowing, in both modes.
    #
    # `full_corpus`, not `args.corpus`: the question the inversion
    # turns on is whether this run read every corpus, and `--corpus` is
    # `action="append"`, so a run naming all six of them narrows
    # nothing and must refuse a stale exemption exactly as a flagless
    # run does. A genuine subset still only NOTEs, which is the whole
    # of the argument above.
    #
    # `rules` here is _sorted_rules' output, which is intentional and
    # harmless: since #451 every rule carries a name_regex, so the sort
    # is the identity on every ledger that loads and positions are
    # unchanged. Verified against all four shipped ledgers -- element
    # identity, not just equality -- at the time of writing.
    corpus_names = [str(e["name"]) for e in entries]
    undeclared = undeclared_contests(rules, corpus_names)
    if undeclared:
        raise SystemExit("\n".join(
            [f"{ledger.name} has {len(undeclared)} order-decided "
             f"contest(s) nobody declared. Where the later rule's "
             f"'fields' are a strict subset of the earlier one's and "
             f"both regexes reach one name, file order alone picks the "
             f"winner. Declare it on the EARLIER rule with a "
             f"[[change.precedes_narrower]] block naming the later one "
             f"and saying what it describes that the later one does "
             f"not -- do NOT reorder, which moves which rule classifies "
             f"a name and breaks _CROSS_RULE_WINNERS:"]
            + [f"  {c.earlier!r}\n  outranks {c.later!r}\n"
               f"  on {len(c.names)} name(s), e.g. {list(c.names[:3])}"
               for c in undeclared]))
    vacant = vacant_exemptions(rules, corpus_names)
    if vacant and not full_corpus:
        print(f"NOTE: this run used --corpus, and over that SUBSET "
              f"{len(vacant)} exemption(s) in {ledger.name} declare "
              f"precedence over a pair nothing here contests. That "
              f"count is not evidence of a stale exemption -- narrowing "
              f"removes contests, so a declaration the full gate needs "
              f"reads the same way. Re-run without --corpus before "
              f"touching any of them.\n")
    elif vacant:
        raise SystemExit("\n".join(
            [f"{ledger.name} carries {len(vacant)} exemption(s) over a "
             f"pair that is not contested over the full corpus. A rule "
             f"was narrowed or a corpus name left. Delete the exemption "
             f"-- a justification for a hazard that is gone reads "
             f"exactly like one for a hazard that is live:"]
            + [f"  {v.earlier!r}\n  declares precedence over {v.later!r}"
               for v in vacant]))
    # A recorded diff shape naming a string no corpus holds any more
    # (#497). _RECORDED_DIFFS pins the shape _CROSS_RULE_WINNERS feeds
    # to classify() as an input, and a row nothing measures agrees with
    # itself forever -- the exact shape of the defect that roster's
    # shapes were found in. recorded_diff_mismatches cannot ask it: it
    # skips a name it did not compare, which is right under `--corpus`
    # and forgiving forever under the full gate, so this half is the
    # caller's -- the only side that knows whether this run read every
    # corpus.
    #
    # HERE, beside `vacant`, for the reason the block above gives: it
    # reads the ledger and the loaded names and nothing the worker
    # produces, and a refusal raised after the worker has installed the
    # pinned wheel and compared the whole corpus prints below the run's
    # own published `baseline:` header, for a comparison that will
    # never be reported (#382). Not "disowning a comparison it just
    # published": measured print order is `baseline:` at the tell,
    # then the comparison loop, which prints nothing, then `corpus:
    # ... intentional diffs:`, so at that later point the header
    # would have printed and no line of the comparison would have. It
    # is the ORDER of the two that earns the placement, as it does at
    # the twin comment above. HERE, nothing has printed at all.
    # The measured half of this check is the opposite case and
    # sits after the comparison, where the diff it reads exists.
    #
    # PRE-skip `corpus_names`, where the measured half takes the
    # POST-skip `corpus`. The two questions, why they take opposite
    # lists, the three names they differ by at 1.4.0 and the recompute
    # are recorded ONCE, in recorded_diff_mismatches' docstring -- read
    # it before touching either line. One thing is not there and lives
    # here, because it is an argument about THIS placement and not
    # about that function: none of those three names carries a roster
    # row today, so the post-skip reading would refuse nothing YET. It
    # would wait for the first row on a shape-tagged name and then tell
    # a contributor to delete a row for a name the run had just read
    # past, which is why the hazard is invisible to the gate and has to
    # be argued rather than measured.
    #
    # `full_corpus`, not `args.corpus`, for the same reason `vacant`
    # reads it. Under a narrowing this is SILENT rather than a NOTE,
    # which is where the two checks part: `vacant` prints a count a
    # reader might act on, and here recorded_diff_mismatches has
    # already dropped those names without reporting one, so a NOTE
    # would add noise and no information. Measured 2026-09-03, it would
    # name 18 to 30 of the 31 rows depending on which corpus was asked
    # for (30 for corpus_shapes.jsonl) against `vacant`'s 5 to 11 of
    # 11. Recompute, from the worktree root:
    #   uv run python -c "import sys;sys.path.insert(0,'tools/\
    #   differential');import compare,pathlib;r=set(compare.\
    #   _RECORDED_DIFFS['expected_since_1.4.0.toml']);[print(p.name,\
    #   len(r-{str(e['name']) for e in compare._load_entries(p)}),\
    #   'of',len(r)) for p in sorted(pathlib.Path('tools/differential')\
    #   .glob('corpus*.jsonl'))]"
    # `ledger` is a Path, so the key is `ledger.name` -- as the line
    # below has it, and as an earlier draft of this recipe did not.
    #
    # BOTH rosters, because a watched row (_WATCHED_DIFFS) is measured
    # by nothing else either: the two differ in what a mismatch means,
    # not in whether a departed name can be measured, so the union is
    # the population every check here reads.
    #
    # FAIL-CLOSED on a missing section, and indexed rather than
    # `.get(ledger.name, {})` below for that reason. An empty section
    # is a statement -- this ledger has no row of that kind -- where a
    # missing one is nobody having looked, and a `.get` default reads
    # the two alike: with the 1.4.0 key deleted from _WATCHED_DIFFS,
    # a full run at that baseline checks 41 rows fewer, prints the
    # same 375 lines (differing only in the worker environment's path
    # on the `baseline:` line, as any two runs do) and exits 0. The
    # pytest-speed guards hold
    # each dict's keys equal to the ledgers on disk
    # (test_the_watched_roster_is_disjoint_and_names_every_ledger, and
    # test_every_pinned_winner_has_a_recorded_shape through
    # _CROSS_RULE_WINNERS); this refuses again because the tool may
    # not assume the suite ran -- _CORPUS_TIERS' stance, applied to
    # the rosters.
    unsectioned = [dict_name for dict_name, roster in (
        ("_RECORDED_DIFFS", _RECORDED_DIFFS),
        ("_WATCHED_DIFFS", _WATCHED_DIFFS)) if ledger.name not in roster]
    if unsectioned:
        raise SystemExit(
            f"tools/differential/compare.py: {' and '.join(unsectioned)} "
            f"carry no section for {ledger.name!r}. A ledger needs an "
            f"explicit section in each shape roster, mapped to {{}} "
            f"while it has no row of that kind: an empty section is a "
            f"statement, a missing one is nobody having looked, and a "
            f"default would read the two alike and check nothing for "
            f"this ledger. tests/v2/test_ledger_guards.py holds every "
            f"ledger on disk to the same key equality at pytest speed")
    recorded = _RECORDED_DIFFS[ledger.name]
    watched = _WATCHED_DIFFS[ledger.name]
    # A name in BOTH dicts has not chosen which kind of row it is, and
    # the two kinds carry different severities and different repairs,
    # so the run cannot pick one for it. The pytest-speed guard in
    # tests/v2/test_ledger_guards.py refuses the same overlap; this
    # refuses it again because the tool may not assume the suite ran
    # -- _CORPUS_TIERS is fail-closed here for the same reason.
    both = sorted(set(recorded) & set(watched))
    if both:
        raise SystemExit("\n".join(
            [f"tools/differential/compare.py: {len(both)} name(s) sit in "
             f"both _RECORDED_DIFFS[{ledger.name!r}] and "
             f"_WATCHED_DIFFS[{ledger.name!r}]. A row is one kind or "
             f"the other: a shape beside a winner adjudicates a "
             f"contest, a shape alone watches a name no winner is "
             f"pinned for. A name with an argument behind it belongs in "
             f"_RECORDED_DIFFS alone -- delete its _WATCHED_DIFFS row:"]
            + [f"  {n!r}" for n in both]))
    gone = sorted((set(recorded) | set(watched)) - set(corpus_names))
    if gone and full_corpus:
        # The repair differs by roster and the message says so per
        # list rather than once: a contest row has a partner pin in
        # _CROSS_RULE_WINNERS to delete with it, a watched row has no
        # partner, and one sentence covering both would tell a
        # watched-row reader to delete something that does not exist.
        contest_gone = [n for n in gone if n in recorded]
        watched_gone = [n for n in gone if n in watched]
        raise SystemExit("\n".join(
            [f"tools/differential/compare.py: {len(gone)} recorded diff "
             f"shape(s) for {ledger.name!r} name a string no corpus "
             f"holds any more, over the FULL corpus. Nothing measures "
             f"such a row, so it agrees with itself forever -- the shape "
             f"of the defect #497 is about. Settle the question that "
             f"picks the repair first: did the name leave DELIBERATELY? "
             f"`git log -S'<name>' -- tools/differential/corpus*.jsonl` "
             f"answers it. If it did, delete the row. If it did not, "
             f"restore the name to a corpus -- the corpus is what "
             f"regressed. Both can be true of one name, which is why "
             f"the question comes before the edit:"]
            + (["  in _RECORDED_DIFFS, each with a partner in "
                "_CROSS_RULE_WINNERS (tests/v2/test_ledger_guards.py) "
                "that pins a winner for a contest nothing raises now "
                "-- a deletion takes both:"]
               + [f"    {n!r}" for n in contest_gone]
               if contest_gone else [])
            + (["  in _WATCHED_DIFFS, pinning no winner, so the row is "
                "the whole of the deletion:"]
               + [f"    {n!r}" for n in watched_gone]
               if watched_gone else [])))
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
    # misconfiguration that aborts after the whole install-and-compare
    # pass is one the run reports below its own published `baseline:`
    # line, having installed the wheel and compared the whole corpus
    # for a report it will never make -- not "disowning a comparison it
    # published", since nothing of the comparison prints until the
    # `corpus: ... intentional diffs:` line further down. It
    # is the ORDER that earns the placement, not the clock. This
    # comment used to say that pass
    # "costs minutes" -- a magnitude nobody had measured, and wrong:
    # every baseline runs in well under a second. Withdrawn by #497.
    # The figures, both recompute recipes, and the trap in timing
    # _run_worker directly are in decisions.md, "the rule-order arc",
    # kept in that one place because they carry a date there and a
    # second copy is the copy that does not get updated.
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
            hn = HumanName(name)
            new = {k: v or "" for k, v in hn.as_dict().items()
                   if k in FIELDS}
            # must stay identical to the worker template's facade row
            new["_initials"] = hn.initials() or ""
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
            new_v2["_initials"] = p.initials() or ""
            diff |= {_canonical_field(f)
                     for f in (*V2_FIELDS, "_ambiguities")
                     if old.get("v2", {}).get(f, "") != new_v2.get(f, "")}
        # #484: initials() is a DERIVED view. It enters the diff only
        # when every role and the ambiguity kinds agree on every
        # compared surface -- render-layer drift, the one shape the
        # field comparison cannot see. When a role moved, the initials
        # movement is that move's consequence, not drift: it is neither
        # compared nor printed, and the rule that explains the role
        # diff explains it (decisions.md, "the initials view"). Strict
        # subset semantics were measured and rejected there: they would
        # have put `_initials` onto a long tail of existing rules for
        # no added discrimination.
        if not diff and (
                old.get("facade", {}).get("_initials", "")
                != new.get("_initials", "")
                or old.get("v2", {}).get("_initials", "")
                != new_v2.get("_initials", "")):
            diff = {"_initials"}
        if not diff:
            continue
        diffing.append((name, diff, order))
        issue = classify(name, diff, rules, exclusions, order)
        if issue is None:
            row = (name, old.get("facade", {}), new, old.get("v2", {}),
                   new_v2, order, diff == {"_initials"})
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
    # The measured half of the recorded-shape check (#497): the shape
    # _CROSS_RULE_WINNERS pins against the diff this run actually made,
    # and the shape _WATCHED_DIFFS records against the same diff.
    # HERE because this is the only place both exist -- validate_rules
    # runs before any corpus is read, and the unit suite spawns no
    # worker, deliberately, so neither can ask it. Its absent-name half
    # needs none of that and refuses up beside `vacant`, pre-worker.
    #
    # PRINTS and feeds the exit code rather than raising, like
    # over_declared_rules below -- its structural sibling, the other
    # post-worker check on recorded data. A raise lands MID-REPORT and
    # takes the rest of the run's output with it: measured, a
    # `--corpus corpus.jsonl` run at 1.4.0 prints 62 EXPLAINED NOTHING
    # lines, and 0 of them with one _RECORDED_DIFFS row corrupted,
    # because the raise preceded dormancy, OVER-DECLARED, UNEXPLAINED
    # and the radar block. A stale roster row must not hide an
    # unexplained diff, which is the gate's primary output. The two
    # pre-worker refusals raise before anything has printed, which is
    # why they may; this one cannot.
    #
    # `compared` is the POST-skip name set -- main()'s `corpus` --
    # because the question is "was this name compared?", and a shape
    # cannot be read off a comparison that never ran. The absent-name
    # half reads the PRE-skip list, for the opposite reason spelled out
    # there, and `recorded` is the per-ledger row dict both halves read,
    # bound up beside it.
    compared = {str(n) for n in corpus}
    # THE WINDOW BETWEEN THE TWO HALVES, and it is not empty. A name can
    # sit in a corpus file this run READ and still be outside `compared`,
    # because the baseline-minimum skip above drops an order-bearing
    # entry the baseline cannot honor. Such a row falls between both
    # checks: recorded_diff_mismatches skips a name outside `compared`,
    # and the `gone` refusal passes it because the skip takes a name out
    # of the RUN and out of no file. Measured 2026-09-03 by putting a
    # deliberately wrong shape on 'de la Cruz née Vega' over the FULL
    # corpus at 1.4.0, and BOTH sides of the note are stated because
    # only the pair says what the note bought: before `9360919` that
    # run exited 0 in 375 stdout lines naming the name in none of them,
    # and it now exits 0 in 378, the three added lines being the NOT
    # CHECKED note below naming it. Re-measure by corrupting the row in
    # _RECORDED_DIFFS in memory around main(), which leaves the
    # worktree alone. The window is co-located with the only populated
    # section, since 1.4.0 is both where the roster's rows live and the
    # only baseline where the skip fires (every order-bearing shape's
    # min_baseline is 2.0.0).
    #
    # A NOTE. Not a refusal, not in the exit code, and the distinction
    # is the whole of it: recorded_diff_mismatches' docstring argues
    # that refusing off the POST-skip list would tell a contributor to
    # delete a row for a name sitting in corpus_shapes.jsonl at the
    # compat baseline, and that argument stands. It is an argument
    # against REFUSING, not against SAYING, and only the first of those
    # was ever made.
    #
    # Intersected with `corpus_names` rather than gated on
    # `full_corpus`, which is where this parts from the two checks that
    # do read that flag. Under `--corpus` the pre-skip list is already
    # narrowed to what this run loaded, so the intersection names only
    # rows this run READ and then dropped -- a fact about the run in
    # both modes, and never the departed-name question the `gone` half
    # owns. Nothing else stands between the two lists: `entries` is
    # rebuilt exactly once between them, by that skip.
    #
    # The UNION of the two rosters, like `gone` above: a watched row on
    # a skipped entry is checked by neither half for exactly the same
    # reason a contest row is, and which dict it sits in changes what
    # a mismatch would mean, not whether one could be measured.
    unchecked = sorted(((set(recorded) | set(watched)) & set(corpus_names))
                       - compared)
    if unchecked:
        print(f"NOT CHECKED {ledger.name}: {len(unchecked)} recorded "
              f"diff shape(s) name an entry this baseline skipped, so "
              f"this run measured no diff to check them against. "
              f"Informational, outside the exit code, and NOT a stale "
              f"row: each name is in a corpus this run read -- the "
              f"skip takes an order-bearing entry out of the RUN and "
              f"out of no file -- so do not delete one over this. The "
              f"shape report below speaks for every other row and for "
              f"none of these; re-run at a baseline that can honor "
              f"their order to check them:")
        for n in unchecked:
            print(f"  {n!r}")
        print()
    # The severity split for a WATCHED row reads the compared entry's
    # tier, and the entry is the post-skip one -- the same list
    # `compared` was built from, so every name in `compared` has a key
    # here and the lookups below index rather than `.get`: a miss would
    # mean `compared` and `entries` had parted, which nothing between
    # them can do. Not the order-None entries alone: a name compared
    # under a declared order ALONE is in `compared` with no
    # default-order entry, and a watched row on it reports with
    # `measured` None (recorded_diff_mismatches' second cause), which
    # is a mismatch owed a tier like any other -- read off only its
    # order-None entry it would fall out of both lists below and
    # print nowhere. So an order-None entry decides when there is one,
    # since the shape recorded is the default-order shape, and the
    # first-loaded entry decides otherwise, which is a contract one
    # whenever any is: the (name, order) dedup loaded contract files
    # first, and at most one order-None entry survives per name (a
    # declared-order-only name has none), so the tier is unambiguous
    # in both cases.
    tier_of: dict[str, str] = {}
    for e in entries:
        if e["order"] is None or str(e["name"]) not in tier_of:
            tier_of[str(e["name"])] = str(e["tier"])
    contest_bad = recorded_diff_mismatches(recorded, diffing, compared)
    watched_bad = recorded_diff_mismatches(watched, diffing, compared)
    # `== "radar"` and its complement rather than `== "contract"`, the
    # reading the comparison loop above uses: a tier that is neither
    # fails, which is the fail-closed direction. Defense in depth
    # only, since the corpus load refuses any value outside the two
    # literals -- so every tier that reaches this line IS one of them,
    # and the watched block's "because the name is contract tier" is
    # true of every value that lands on its side.
    watched_contract = [m for m in watched_bad
                        if tier_of[m.name] != "radar"]
    watched_radar = [m for m in watched_bad if tier_of[m.name] == "radar"]
    # What the exit code reads. A contest row is fatal on either tier
    # because it carries an argument; a watched row follows its name's
    # tier, and _WATCHED_DIFFS' header carries why the radar half does
    # not fail.
    shape_bad = contest_bad + watched_contract
    if contest_bad:
        # The instruction and the disclaimer are properties of the
        # CHECK, not of a row, so they lead the block once instead of
        # riding every line -- the shape the Role-vocabulary legend
        # below uses for the two blocks that share it. A real parser
        # move lands on many of these rows at once, and per-row
        # repetition would bury the names under its own advice.
        # (OVER-DECLARED repeats its shared text per row and is not
        # the precedent for doing so here: measured 2026-09-03 its
        # row-invariant text is three sentences and 47 words, against
        # this lead's two and 39, so it is the LONGER of the two -- it
        # gets away with the repetition because its rows come one per
        # over-declared RULE, where these come one per name and a real
        # parser move lands on many at once. An earlier draft of this
        # parenthetical called that text one sentence and cited it as
        # the model.) No cause is
        # named for a row with no measured
        # shape: the check cannot tell the two apart --
        # recorded_diff_mismatches' docstring says why they are
        # collapsed -- and naming one would send half the readers to
        # the wrong file.
        print(f"MOVED SHAPE {ledger.name}: {len(contest_bad)} recorded "
              f"diff shape(s) disagree with this run. Each is a "
              f"FINDING, not a number to update: the winner pinned "
              f"beside the shape in _CROSS_RULE_WINNERS "
              f"(tests/v2/test_ledger_guards.py) was recorded for the "
              f"OLD shape, so read both before editing either."
              + _two_causes(contest_bad))
        _print_moved_rows(contest_bad, "_RECORDED_DIFFS")
    # The two watched blocks share a lead and differ in the last
    # sentence, which is the severity and its reason. Neither names
    # _CROSS_RULE_WINNERS: no row in them has a partner there, and a
    # reader sent to that roster would find nothing to read.
    if watched_contract:
        print(f"MOVED SHAPE {ledger.name}: {len(watched_contract)} watched "
              f"diff shape(s) disagree with this run. No winner is "
              f"pinned for these names, so each is a FINDING, not a "
              f"number to update: if the move is intended, re-record the shape "
              f"in _WATCHED_DIFFS in the commit that moved it and say "
              f"why there. This fails the run because the name is "
              f"contract tier (_CORPUS_TIERS)."
              + _two_causes(watched_contract))
        _print_moved_rows(watched_contract, "_WATCHED_DIFFS")
    if watched_radar:
        print(f"MOVED SHAPE (radar) {ledger.name}: {len(watched_radar)} "
              f"watched diff shape(s) disagree with this run. No winner "
              f"is pinned for these names, so each is a FINDING, not a "
              f"number to update: if the move is intended, re-record "
              f"the shape in _WATCHED_DIFFS in the commit that moved it "
              f"and say why there. This does not fail the run because "
              f"the name is radar tier (_CORPUS_TIERS), which watches "
              f"without promising."
              + _two_causes(watched_radar))
        _print_moved_rows(watched_radar, "_WATCHED_DIFFS")
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
    for (name, old_facade, new, old_v2, new_v2, order,
         initials_only) in unexplained:
        # the order tag distinguishes a family-first regression from a
        # default-order one on the same name -- otherwise indistinguishable
        # in the report
        print(f"UNEXPLAINED {name!r}{_order_tag(order)}")
        _print_field_diffs(old_facade, new, old_v2, new_v2, order,
                           initials_only=initials_only)
    if radar:
        print("\nRadar tier (names the contract does not answer for, "
              "#468): shown, never blocking. Promote a name that "
              "matters via a cases.py row + shape tag, or -- for a "
              "demoted one -- by clearing `tolerated` on its rows.\n")
    for entry, (name, old_facade, new, old_v2, new_v2, order,
                initials_only) in radar:
        labels = entry.get("tests")
        tag = f"   [v1: {', '.join(labels)}]" if labels else ""
        print(f"UNCLASSIFIED (radar) {name!r}{tag}{_order_tag(order)}")
        _print_field_diffs(old_facade, new, old_v2, new_v2, order,
                           initials_only=initials_only)
    # A rule explaining nothing is as much a broken contract as an
    # unexplained diff: both mean the ledger no longer describes what
    # the code does. A rule that has STOPPED explaining nothing is the
    # same statement inverted -- its `dormant` reason is now false. A
    # rule explaining LESS than it declares is a fourth way, and the
    # quietest: it still matches, so nothing looks broken, but the
    # `fields` it names are no longer what the code moves. A recorded
    # shape the run contradicts is the fifth, and it reaches furthest:
    # _CROSS_RULE_WINNERS feeds that shape to classify() as an input, so
    # a wrong one takes the roster's verdict with it. One exit code for
    # all five terms below, so none of them is the one nobody noticed.
    # `shape_bad` is the contest rows plus the watched rows on contract
    # names; a watched row on a radar name printed above and is not in
    # it, by the severity rule _WATCHED_DIFFS' header argues.
    return 1 if unexplained or dormancy.undeclared or dormancy.awake \
        or overwide or shape_bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
