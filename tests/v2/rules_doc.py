"""Parser and annotation registry for docs/design/rules/ example lines.

The grammar (described for humans in the rules README's preamble; this module
is its executable definition):

    "INPUT" [annotation] →  field=VALUE  [· boundary]
                            [deviates: #N (today: field=VALUE)]

plus per-rule ``no-boundary: reason`` lines and the trailing pointer
line ``history: ... · interacts: A1, B2 · implemented: path, path``.
A rule nothing implements yet carries ``tracked: #N, #M`` in place of
``implemented:`` — the issues that would ship it. Exactly one of the
two is required, so a normative rule always points either at the code
that honors it or at the work that will.

A rule may also carry ``tolerated: <reason>``, which takes it out of
the document's normative reading: its statement DESCRIBES what the
parser does with input no writing convention produces (W3: a comma
between a CJK family name and given name), and does not promise it.
The line changes nothing a test or tool does with the rule: the
examples parse, test_rules_doc.py still executes them, and
tools/differential/build_rules_corpus.py harvests them like any
other's, so the snapshot still shows their reading move (#664). What
it changes is the promise, for the reader. The reason is free text,
but it must be there: a marker with no reason is a hard error, the
same way a malformed example is. A near miss on the spelling —
``Tolerated:``, ``tolerated :``, a bare ``tolerated:`` — fails loudly
too: read as prose, it would leave the rule reading as a promise its
author meant to withdraw, and put the line into the statement a
citation quotes and the size budget counts.

Every rule also states its ``Signal:`` -- what in the written name it
reads, for example a count, a case contrast, a shape, a neighbor, a
position, or ``none in the name: ...`` for a rule reading configuration
or the parsed words; the kinds are not a closed set. The line is one
line, never wrapped, and stands directly above the rule's pointer line;
the parser refuses one that does not, because a wrapped continuation
would read as statement prose, quotable by a citation. A hub, a rule
deciding by several signals each stated by a rule of its own, writes
``Signal: hub of C3, C4, ...``, naming those rules, after any signal
it reads itself (``Signal: <own signals>; hub of C3, C4``); the doc
tests hold each named rule to the hub's ``interacts:`` and to one
sentence of its statement, so the hub's map cannot leave one out. A
line naming two signals joins them with `` + ``, which marks the rule
a split candidate (docs/design/AGENTS.md, "One rule per piece of
evidence"). A condition the rule cites to the rule stating it stays
off the line, and a gate on the name's size ("exactly three name
words", "a word to spare") is part of the signal it gates.
The line is metadata, not statement prose: a citation cannot quote it
and the size budget (tests/v2/rules_budget.py) does not count it.

Inside a rule block, any line whose first non-space character is a
double quote (or an opening bracket, the D-section subject form) is an
example line and MUST parse — a silent skip would un-execute a claim,
so a malformed example is a hard error naming the rule.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field as dc_field


_RULE_RE = re.compile(r"^([A-Z])(\d+)\.\s")
_VALUE = r"\"[^\"]*\"|\([^)]*\)|\[(?:[^\[\]]|\[[^\]]*\])*\]"
_EXAMPLE_RE = re.compile(
    r'^\s*(?:"(?P<text>[^"]*)"|\[(?P<subject>[a-z][a-z0-9_+-]*)\])'
    r"(?:\s+(?P<annot>[a-z][a-z0-9_+-]*|\[[a-z][a-z0-9_+-]*\]))?"
    r"\s+→\s+"
    rf"(?P<field>[a-z_]+)=(?P<value>{_VALUE})"
    r"(?P<boundary>\s+·\s+boundary)?"
    r"(?:\s+deviates:\s+#(?P<issue>\d+)\s+\(today:\s+"
    rf"(?P<tfield>[a-z_]+)=(?P<today>{_VALUE})\))?"
    r"\s*$")
_NO_BOUNDARY_RE = re.compile(r"^\s*no-boundary:\s+(?P<reason>\S.*)$")
_TOLERATED_RE = re.compile(r"^\s*tolerated:\s+(?P<reason>\S.*)$")
#: A line that was MEANT to be the marker above. Everything the strict
#: form rejects -- any casing of the word, a space before the colon, a
#: reason that is empty or all whitespace -- lands here and raises,
#: because the silent alternative is the dangerous one (see the raise
#: below). Case-insensitive rather than just `[Tt]`: an author
#: shouting the word is making the same mistake as one capitalizing
#: it, and no line in a rule block legitimately opens with it.
_NEAR_TOLERATED_RE = re.compile(r"^\s*tolerated\b", re.IGNORECASE)
_SIGNAL_RE = re.compile(r"^\s*Signal:\s+(?P<text>\S.*?)\s*$")
#: Any line meant to be the signal line, the strict form's near misses
#: included (``signal:``, ``Signal :``, an empty one): a near miss read
#: as prose would leave the rule with no signal and put the line into
#: the quotable statement.
NEAR_SIGNAL_RE = re.compile(r"^\s*[*_]*signals?[*_]*\s*[:\uff1a]",
                            re.IGNORECASE)
#: A hub's signal: the rules it maps, after any signal it reads itself.
_HUB_RE = re.compile(
    r"(?:(?P<own>\S.*?); )?hub of (?P<ids>[A-Z]\d+(?:, [A-Z]\d+)*)")
#: A signal line meant as a hub's: one that does not fullmatch _HUB_RE
#: raises rather than reading as a plain signal, which would leave the
#: hub's rules unchecked. A plain word holding the letters ("Hubert",
#: "a hub-like word") is not one.
_NEAR_HUB_RE = re.compile(r"\bhubs?\b(?!-)", re.IGNORECASE)
#: The line opening an Accepted clause, in either spelling the rules
#: write ("Accepted:", "Accepted, and the reason ...:"); a line that
#: merely begins with the word ("Accepted rather than repaired:",
#: mid-clause in P3) is not one.
ACCEPTED_RE = re.compile(r"^\s*Accepted[:,]")
#: A line meant to open an Accepted clause but spelled otherwise
#: (``Accepted :``, ``Accepted --``, ``Accepted (2026):``, lowercase):
#: read as statement, its words would land in the wrong measure and a
#: hub's map sentence could hide in it. "Accepted" followed by a word
#: is prose and passes.
_NEAR_ACCEPTED_RE = re.compile(r"^\s*accepted\s*(?:[:,(]|--|—)",
                               re.IGNORECASE)
_POINTER_RE = re.compile(r"^\s*(history|interacts|implemented|tracked):")
_POINTER_PART_RE = re.compile(
    r"(history|interacts|implemented|tracked):\s*([^·]+)")

ASSERTABLE_FIELDS = frozenset({
    "title", "given", "middle", "family", "suffix", "nickname", "maiden",
    "family_base", "family_particles", "surnames", "given_names",
    "initials", "capitalized", "capitalized_forced",
    "ambiguities", "pieces", "warns", "raises"})


@dataclass(frozen=True)
class Example:
    text: str
    annotation: str | None
    field: str
    value: object
    boundary: bool
    deviates_issue: int | None
    today_value: object
    subject: str | None = None


@dataclass
class Rule:
    rule_id: str
    examples: list[Example] = dc_field(default_factory=list)
    no_boundary: str | None = None
    interacts: tuple[str, ...] = ()
    implemented: tuple[str, ...] = ()
    #: Issues that would ship a rule nothing implements yet. Mutually
    #: exclusive with ``implemented:`` -- a rule points at code or at
    #: the issues that will produce it, never at neither.
    tracked: tuple[str, ...] = ()
    #: The ``tolerated:`` line's reason, or None for a normative rule.
    #: A tolerated rule's examples illustrate what the parser does
    #: today rather than promise it; no tool treats them differently.
    tolerated: str | None = None
    #: The ``Signal:`` line's text: what in the written name the rule
    #: reads. None only where the line is missing, which the doc tests
    #: refuse for the real rules.
    signal: str | None = None
    #: For a hub (``Signal: [<own signals>; ]hub of C3, C4``), the
    #: rules whose signals it combines; () for a rule that is no hub.
    hub: tuple[str, ...] = ()

    def has_boundary_or_waiver(self) -> bool:
        return self.no_boundary is not None or any(
            e.boundary for e in self.examples)


from nameparser._policy import (  # noqa: E402
    FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST, CapsSuffixes, Policy)

#: Named policies example annotations may reference. Grown as
#: extraction demands; each addition is a diff to this dict only.
POLICIES: dict[str, Policy] = {
    "family-first": Policy(name_order=FAMILY_FIRST),
    "family-first-given-last": Policy(name_order=FAMILY_FIRST_GIVEN_LAST),
    "middle_as_family": Policy(middle_as_family=True),
    "family-first+middle_as_family": Policy(
        name_order=FAMILY_FIRST, middle_as_family=True),
    "maiden-parens": Policy(maiden_delimiters=frozenset({("(", ")")})),
    "keep-emoji": Policy(strip_emoji=False),
    "strict-comma-suffixes": Policy(lenient_comma_suffixes=False),
    #: The two switches over the by-shape credential class (#516).
    #: Named after the Policy FIELD rather than after the behavior,
    #: which is deliberate: the rules' statements stay
    #: implementation-free, so the annotation slot is the one place
    #: the doc can put the caller-facing name of the switch its prose
    #: describes. The suffix says which way the field is set, since
    #: one is on by default and the caps field (#564) has three values,
    #: so its suffix names the value set.
    "unlisted_dotted_suffixes-off": Policy(unlisted_dotted_suffixes=False),
    "unlisted_caps_suffixes-everywhere": Policy(
        unlisted_caps_suffixes=CapsSuffixes.EVERYWHERE),
    "unlisted_caps_suffixes-off": Policy(
        unlisted_caps_suffixes=CapsSuffixes.OFF),
    #: The delimiter switch (#206), named after its Policy FIELD for
    #: the reason above and carrying the DELIMITER in the suffix,
    #: because this field's value is a set rather than a flag: a rule
    #: reached only under a configured separator has to say which one,
    #: and " - " is the spelling docs/customize.rst teaches and the
    #: one the group tests configure.
    "extra_suffix_delimiters-dash": Policy(
        extra_suffix_delimiters=frozenset({" - "})),
}
#: D-section subjects: zero-arg constructions whose diagnostics the
#: warns=/raises= assertion forms exercise.
def _segmenterless_ja() -> object:
    from nameparser import locales, parser_for
    return parser_for(locales.get("ja"))


def _bad_name_order() -> object:
    return Policy(name_order=("given",))  # type: ignore[arg-type]


def _bad_order_none() -> object:
    return Policy(name_order=None)  # type: ignore[arg-type]


SUBJECTS: dict[str, object] = {
    "segmenterless-ja": _segmenterless_ja,
    "bad-name-order": _bad_name_order,
    "bad-order-none": _bad_order_none,
}

#: Extras gates: locale requiring an optional dependency; the examples
#: runner skips these when the import is absent (CI's ja-extra job
#: exercises them).
GATES: dict[str, tuple[str, str]] = {"[ja+segmenter]": ("ja", "namedivider")}

_LOCALE_ANNOT_RE = re.compile(r"\[[a-z_]{2,5}\]")


def resolve_annotation(annot: str) -> tuple[str, object]:
    if annot in POLICIES:
        return "policy", POLICIES[annot]
    if annot in GATES:
        return "gated_locale", GATES[annot][0]
    if _LOCALE_ANNOT_RE.fullmatch(annot):
        return "locale", annot[1:-1]
    raise KeyError(annot)


def _literal(tok: str) -> object:
    return ast.literal_eval(tok)


def parse_rules_doc(text: str) -> list[Rule]:
    rules: list[Rule] = []
    current: Rule | None = None
    signal_at: int | None = None    # the line a pointer must follow
    for lineno, line in enumerate(text.splitlines(), 1):
        if signal_at is not None and not _POINTER_RE.match(line):
            raise ValueError(
                f"{current.rule_id if current else '?'}: line {signal_at}: "
                f"a `Signal:` line must stand directly above the rule's "
                f"pointer line, on one line; the next line is "
                f"{line.strip()!r}")
        signal_at = None
        if line.startswith("#"):        # a heading ends any rule block
            current = None
            continue
        m = _RULE_RE.match(line)
        if m:
            rid = m.group(1) + m.group(2)
            if any(r.rule_id == rid for r in rules):
                raise ValueError(f"duplicate rule ID {rid} at line {lineno}")
            current = Rule(rule_id=rid)
            rules.append(current)
            continue
        if current is None:
            if NEAR_SIGNAL_RE.match(line):
                after = rules[-1].rule_id if rules else "the start"
                raise ValueError(
                    f"line {lineno}, after {after}: a `Signal:` line "
                    f"outside any rule block; it belongs directly above "
                    f"its rule's pointer line: {line.strip()!r}")
            continue
        stripped = line.lstrip()
        em = _EXAMPLE_RE.match(line)
        if em:
            fieldname = em.group("field")
            if fieldname not in ASSERTABLE_FIELDS:
                raise ValueError(
                    f"{current.rule_id}: line {lineno}: field "
                    f"{fieldname!r} not assertable")
            if em.group("tfield") and em.group("tfield") != fieldname:
                raise ValueError(
                    f"{current.rule_id}: line {lineno}: deviates "
                    f"today-field {em.group('tfield')!r} differs from "
                    f"the asserted field {fieldname!r}")
            current.examples.append(Example(
                text=em.group("text") or "",
                annotation=em.group("annot"),
                field=fieldname,
                value=_literal(em.group("value")),
                boundary=bool(em.group("boundary")),
                deviates_issue=(int(em.group("issue"))
                                if em.group("issue") else None),
                today_value=(_literal(em.group("today"))
                             if em.group("today") else None),
                subject=em.group("subject")))
            continue
        if stripped.startswith(('"', "[", "“", "”", "„",
                                "‘", "’", "«")):
            raise ValueError(
                f"{current.rule_id}: line {lineno} looks like an example "
                f"but does not parse: {stripped!r}")
        nb = _NO_BOUNDARY_RE.match(line)
        if nb:
            current.no_boundary = nb.group("reason")
            continue
        tol = _TOLERATED_RE.match(line)
        if tol:
            current.tolerated = tol.group("reason")
            continue
        if _NEAR_TOLERATED_RE.match(line):
            raise ValueError(
                f"{current.rule_id}: line {lineno} looks like a "
                f"`tolerated:` marker but does not parse: {stripped!r}. "
                f"The spelling is `tolerated: <reason>` -- lowercase, "
                f"no space before the colon, and a reason that is not "
                f"empty. Read as prose, a near miss would leave the "
                f"rule reading as a PROMISE -- the opposite of what the "
                f"line was written to say, and green in every suite -- "
                f"and put the line into the statement a citation quotes "
                f"and the size budget counts. The reason is unvalidated "
                f"free text but required, because a demotion nobody had "
                f"to justify is the one nobody reviews")
        sig = _SIGNAL_RE.match(line)
        if sig:
            if current.signal is not None:
                raise ValueError(
                    f"{current.rule_id}: line {lineno}: a second "
                    f"`Signal:` line; a rule states one")
            current.signal = sig.group("text")
            hub = _HUB_RE.fullmatch(current.signal)
            if hub is None and _NEAR_HUB_RE.search(current.signal):
                raise ValueError(
                    f"{current.rule_id}: line {lineno}: a hub's signal "
                    f"line is `Signal: hub of C3, C4`, or `Signal: <its own "
                    f"signals>; hub of C3, C4` -- rule IDs joined by a "
                    f"comma and a space; read as a plain signal, "
                    f"its rules would go unchecked: {stripped!r}")
            current.hub = tuple(hub.group("ids").split(", ")) if hub else ()
            signal_at = lineno
            continue
        if NEAR_SIGNAL_RE.match(line):
            raise ValueError(
                f"{current.rule_id}: line {lineno} looks like a `Signal:` "
                f"line but does not parse: {stripped!r}. The spelling is "
                f"`Signal: <what the rule reads>` -- capitalized, no "
                f"space before the colon, and not empty")
        if _POINTER_RE.match(line):
            for key, val in _POINTER_PART_RE.findall(line):
                items = tuple(v.strip() for v in val.split(",") if v.strip())
                if key == "interacts":
                    current.interacts = items
                elif key == "implemented":
                    current.implemented = items
                elif key == "tracked":
                    current.tracked = items
            continue
        if _NEAR_ACCEPTED_RE.match(line) and not ACCEPTED_RE.match(line):
            raise ValueError(
                f"{current.rule_id}: line {lineno} looks like an Accepted "
                f"clause but does not open one: {stripped!r}. The "
                f"spelling is `Accepted:` or `Accepted, and ...:`")
        if line.strip() and not (line.startswith("    ")
                                 and line[4] != " "):
            # Neither example, marker, pointer nor 4-space prose: read
            # as nothing, it would fall out of the statement a citation
            # quotes and the size budget counts without a word.
            raise ValueError(
                f"{current.rule_id}: line {lineno} is no line a rule block "
                f"holds -- statement and Accepted prose is indented four "
                f"spaces, an example six: {line!r}")
    if signal_at is not None:
        raise ValueError(
            f"{current.rule_id if current else '?'}: line {signal_at}: a "
            f"`Signal:` line must stand directly above the rule's pointer "
            f"line; the text ends after it")
    return rules


def prose_blocks(text: str) -> dict[str, list[str]]:
    """The prose lines of each rule and section Background, unjoined:
    for a rule, its statement and Accepted: clauses -- everything in
    the block but example, pointer, marker and Signal: lines, the
    rule's ID stripped from its first line; for a section letter, its
    Background paragraph. What a citation may quote
    (test_doc_citations.py) and what the size budget counts
    (rules_budget.py), read by one function so the two cannot
    disagree about where a statement ends."""
    out: dict[str, list[str]] = {}
    current: list[str] | None = None
    background: list[str] | None = None
    section = None
    marker = False          # inside a wrapped no-boundary: marker
    for line in text.splitlines():
        m = _RULE_RE.match(line)
        hm = re.match(r"## .*\(([A-Z])\)\s*$", line)
        if background is not None:
            if line.strip():
                background.append(line)
                continue
            background = None
        if hm:
            section = hm.group(1)
        elif section and line.startswith("Background:"):
            background = out[section] = [line]
            section = None
            continue
        if NEAR_SIGNAL_RE.match(line):  # metadata: not quotable
            continue
        if re.match(r"\s*(no-boundary|tolerated):", line):
            marker = True
            continue
        if marker and (_POINTER_RE.match(line) or not line.strip()
                       or line.startswith("      ") or m):
            marker = False
        if m:
            current = out.setdefault(m.group(1) + m.group(2), [])
            current.append(line[m.end():])
        elif line.startswith("#"):
            current = None
        elif current is not None and line.startswith("    ") and not (
                marker or line.startswith("      ")
                or _POINTER_RE.match(line)):
            current.append(line)
    return out


def split_accepted(lines: list[str]) -> tuple[list[str], list[list[str]]]:
    """A rule's prose lines (prose_blocks) as its statement -- the
    Rationale included -- and its Accepted clauses, each clause running
    to the next."""
    starts = [i for i, ln in enumerate(lines) if ACCEPTED_RE.match(ln)]
    if not starts:
        return list(lines), []
    bounds = [*starts, len(lines)]
    return (lines[:starts[0]],
            [lines[a:b] for a, b in zip(bounds, bounds[1:])])
