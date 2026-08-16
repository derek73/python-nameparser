"""Parser and annotation registry for docs/design/rules.md example lines.

The grammar (described for humans in rules.md's preamble; this module
is its executable definition):

    "INPUT" [annotation] →  field=VALUE  [· boundary]
                            [deviates: #N (today: field=VALUE)]

plus per-rule ``no-boundary: reason`` lines and the trailing pointer
line ``history: ... · interacts: A1, B2 · implemented: path, path``.

Inside a rule block, any line whose first non-space character is a
double quote (or an opening bracket, the D-section subject form) is an
example line and MUST parse — a silent skip would un-execute a claim,
so a malformed example is a hard error naming the rule.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field as dc_field
from pathlib import Path

RULES_DOC = Path(__file__).resolve().parents[2] / "docs" / "design" / "rules.md"

_RULE_RE = re.compile(r"^([A-Z])(\d+)\.\s")
_VALUE = r"\"[^\"]*\"|\([^)]*\)|\[(?:[^\[\]]|\[[^\]]*\])*\]"
_EXAMPLE_RE = re.compile(
    r'^\s*(?:"(?P<text>[^"]*)"|\[(?P<subject>[a-z][a-z0-9_+-]*)\])'
    r"(?:\s+(?P<annot>[a-z][a-z0-9_+-]*|\[[a-z][a-z0-9_+-]*\]))?"
    r"\s+→\s+"
    rf"(?P<field>[a-z_]+)=(?P<value>{_VALUE})"
    r"(?:\s+·\s+boundary)?"
    r"(?:\s+deviates:\s+#(?P<issue>\d+)\s+\(today:\s+"
    rf"[a-z_]+=(?P<today>{_VALUE})\))?"
    r"\s*$")
_NO_BOUNDARY_RE = re.compile(r"^\s*no-boundary:\s+(?P<reason>\S.*)$")
_POINTER_RE = re.compile(r"^\s*(history|interacts|implemented):")
_POINTER_PART_RE = re.compile(r"(history|interacts|implemented):\s*([^·]+)")

ASSERTABLE_FIELDS = frozenset({
    "title", "given", "middle", "family", "suffix", "nickname", "maiden",
    "family_base", "family_particles", "surnames", "given_names",
    "initials", "capitalized",
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

    def has_boundary_or_waiver(self) -> bool:
        return self.no_boundary is not None or any(
            e.boundary for e in self.examples)


from nameparser._policy import (  # noqa: E402
    FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST, Policy)

#: Named policies example annotations may reference. Grown as
#: extraction demands; each addition is a diff to this dict only.
POLICIES: dict[str, Policy] = {
    "family-first": Policy(name_order=FAMILY_FIRST),
    "family-first-given-last": Policy(name_order=FAMILY_FIRST_GIVEN_LAST),
    "middle_as_family": Policy(middle_as_family=True),
    "maiden-parens": Policy(maiden_delimiters=frozenset({("(", ")")})),
    "keep-emoji": Policy(strip_emoji=False),
    "strict-comma-suffixes": Policy(lenient_comma_suffixes=False),
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
    for lineno, line in enumerate(text.splitlines(), 1):
        m = _RULE_RE.match(line)
        if m:
            current = Rule(rule_id=m.group(1) + m.group(2))
            rules.append(current)
            continue
        if current is None:
            continue
        stripped = line.lstrip()
        em = _EXAMPLE_RE.match(line)
        if em:
            fieldname = em.group("field")
            if fieldname not in ASSERTABLE_FIELDS:
                raise ValueError(
                    f"{current.rule_id}: line {lineno}: field "
                    f"{fieldname!r} not assertable")
            current.examples.append(Example(
                text=em.group("text") or "",
                annotation=em.group("annot"),
                field=fieldname,
                value=_literal(em.group("value")),
                boundary=" · boundary" in line,
                deviates_issue=(int(em.group("issue"))
                                if em.group("issue") else None),
                today_value=(_literal(em.group("today"))
                             if em.group("today") else None),
                subject=em.group("subject")))
            continue
        if stripped.startswith(('"', "[")):
            raise ValueError(
                f"{current.rule_id}: line {lineno} looks like an example "
                f"but does not parse: {stripped!r}")
        nb = _NO_BOUNDARY_RE.match(line)
        if nb:
            current.no_boundary = nb.group("reason")
            continue
        if _POINTER_RE.match(line):
            for key, val in _POINTER_PART_RE.findall(line):
                items = tuple(v.strip() for v in val.split(",") if v.strip())
                if key == "interacts":
                    current.interacts = items
                elif key == "implemented":
                    current.implemented = items
    return rules
