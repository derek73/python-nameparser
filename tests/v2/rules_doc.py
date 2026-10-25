"""Parser and annotation registry for docs/design/rules/ example lines.

Every rule is written in the skeleton format (#761): a heading
`# ID — name`, bold-labelled fields, fenced examples and a footer, up
to the next markdown heading. ``rules_skeleton.py`` defines and parses
the format; this module splits the rules text into rule blocks and
section Backgrounds, and owns what the skeleton parser builds on: the
example-line grammar, the ``Example`` and ``Rule`` records, and the
registries an example's annotation resolves through.

Outside a rule the text holds only section headings (``## Name (X)``),
each letter once and each followed by one ``Background:`` paragraph,
and blank lines; any other line there is refused, since read as
nothing it would neither run nor be quotable -- a subheading inside a
rule file, a misspelled rule heading, a fence in a section file, and
those glued to a Background paragraph too.

The example-line grammar (described for humans in the rules README;
this module is its executable definition):

    "INPUT" [annotation] →  field=VALUE  [· boundary]
                            [deviates: #N (today: field=VALUE)]

or, for a D-section subject, ``[subject]`` in place of the quoted
input. A line that looks like an example but does not parse is a hard
error naming the rule: a silent skip would un-execute a claim.

The block format the rules were written in before #761 is retired: a
line opening ``ID.`` at the start of a line is refused wherever it
stands, outside any rule here and inside one by parse_skeleton, rather
than skipped or read as prose, since its examples would never run.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field as dc_field
from collections.abc import Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.v2.rules_skeleton import Skeleton


#: The opening line of a block-format rule (``X1. Statement.``), the
#: format #761 retired.
_RETIRED_RULE_RE = re.compile(r"^[A-Z]\d+\.\s")
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
#: Any line meant to be a signal line, in any spelling (``signal:``,
#: ``Signal :``, bold or not): above a rule's footer, or outside any
#: rule, it would be read as prose or as nothing, leaving the rule with
#: no signal.
NEAR_SIGNAL_RE = re.compile(r"^\s*[*_]*signals?[*_]*\s*[:\uff1a]",
                            re.IGNORECASE)
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
    implemented: tuple[str, ...] = ()
    #: Issues that would ship a rule nothing implements yet. Mutually
    #: exclusive with ``implemented:`` -- a rule points at code or at
    #: the issues that will produce it, never at neither.
    tracked: tuple[str, ...] = ()
    #: The ``**Signal:**`` line's text: what in the written name the
    #: rule reads. None only where the line is missing, which the doc
    #: tests refuse for the real rules.
    signal: str | None = None
    #: For a hub (``**Signal:** [<own signals>; ]hub of C3, C4``), the
    #: rules whose signals it combines; () for a rule that is no hub.
    hub: tuple[str, ...] = ()
    #: The rule's parsed fields (rules_skeleton.py), None only while
    #: parse_skeleton is building it. ``examples`` above is the list
    #: that runs; a skeleton's
    #: ``Bullet.examples`` is a placement view of the same objects (which
    #: bullet's fence an example stands in), not a second set, and an
    #: example sits under one bullet at most.
    skeleton: Skeleton | None = None

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
    #: rules/O6's switch (#754), named after its Policy FIELD for the
    #: reason the by-shape switches below give, and with each order and
    #: with middle_as_family, which the rule states its reading under.
    "two_family_names": Policy(two_family_names=True),
    "family-first+two_family_names": Policy(
        name_order=FAMILY_FIRST, two_family_names=True),
    "family-first-given-last+two_family_names": Policy(
        name_order=FAMILY_FIRST_GIVEN_LAST, two_family_names=True),
    "two_family_names+middle_as_family": Policy(
        two_family_names=True, middle_as_family=True),
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


def parse_example_line(line: str, rule_id: str,
                       lineno: int) -> Example | None:
    """The example a line holds, None for a line that is no example,
    and a ValueError for one that looks like an example but does not
    parse (a silent skip would un-execute a claim). Called for each
    line in a rule's fences (rules_skeleton.py)."""
    em = _EXAMPLE_RE.match(line)
    if em:
        fieldname = em.group("field")
        if fieldname not in ASSERTABLE_FIELDS:
            raise ValueError(
                f"{rule_id}: line {lineno}: field "
                f"{fieldname!r} not assertable")
        if em.group("tfield") and em.group("tfield") != fieldname:
            raise ValueError(
                f"{rule_id}: line {lineno}: deviates "
                f"today-field {em.group('tfield')!r} differs from "
                f"the asserted field {fieldname!r}")
        return Example(
            text=em.group("text") or "",
            annotation=em.group("annot"),
            field=fieldname,
            value=_literal(em.group("value")),
            boundary=bool(em.group("boundary")),
            deviates_issue=(int(em.group("issue"))
                            if em.group("issue") else None),
            today_value=(_literal(em.group("today"))
                         if em.group("today") else None),
            subject=em.group("subject"))
    if line.lstrip().startswith(('"', "[", "“", "”", "„",
                                 "‘", "’", "«")):
        raise ValueError(
            f"{rule_id}: line {lineno} looks like an example "
            f"but does not parse: {line.strip()!r}")
    return None


def _walk(text: str) -> Iterator[
        tuple[int, str, tuple[str, list[tuple[int, str]], int] | None]]:
    """Each line outside a rule, as (line number, line, None), and each
    rule's heading as (line number, line, its block), the block's lines
    then skipped (rules_skeleton.skeleton_block_at)."""
    from tests.v2 import rules_skeleton
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        block = rules_skeleton.skeleton_block_at(lines, i)
        yield i + 1, lines[i], block
        i = block[2] if block is not None else i + 1


_SECTION_RE = re.compile(r"## .*\(([A-Z])\)\s*$")
#: Lines at the start of a line that are structure, never a Background
#: paragraph's wrapped prose: a fence, a heading, a field label, a list
#: item (only an item numbered 1 can interrupt a paragraph in
#: CommonMark, so "2026. Then" stays prose). Column 0 only: an indented
#: fence, a setext underline or a blockquote is not read. A wrapped
#: line may open with a quote (the H and N Backgrounds do).
_STRUCTURE_RE = re.compile(
    r"^(?:```|~~~|#+ |\*\*[^*]+:\*\*|(?:[-*+]|1[.)])(?:\s|$))")


def _retired(rid: str, lineno: int, line: str) -> ValueError:
    return ValueError(
        f"{rid}: line {lineno} opens a rule in the block format, which "
        f"#761 retired: {line.strip()!r}. Write the rule as a skeleton "
        f"(docs/design/rules/README.md): a `# ID — name` heading, then "
        f"**When:**, **Then:** and **Because:**, examples in fences and "
        f"a `---` footer")


def parse_rules_doc(text: str) -> list[Rule]:
    from tests.v2 import rules_skeleton
    rules: list[Rule] = []
    section: str | None = None      # a section heading awaits its Background
    background = False              # inside a Background paragraph
    letters: set[str] = set()

    def unresolved(lineno: int) -> ValueError:
        return ValueError(
            f"line {lineno}: section {section}'s heading has no "
            f"`Background:` paragraph after it")

    for lineno, line, block in _walk(text):
        if block is None:
            after = rules[-1].rule_id if rules else "the start"
            sm = _SECTION_RE.match(line)
            if _RETIRED_RULE_RE.match(line):
                raise _retired(line.split(".")[0], lineno, line)
            if NEAR_SIGNAL_RE.match(line):
                raise ValueError(
                    f"line {lineno}, after {after}: a signal line outside "
                    f"any rule; it belongs in its rule's footer, directly "
                    f"above the pointer line: {line.strip()!r}")
            if not line.strip():
                background = False
            elif sm:
                if section is not None:
                    raise unresolved(lineno)
                if sm.group(1) in letters:
                    raise ValueError(
                        f"line {lineno}: section {sm.group(1)} is headed "
                        f"twice; its first Background would stop being "
                        f"quotable")
                letters.add(sm.group(1))
                section, background = sm.group(1), False
            elif background and rules_skeleton.holds_assertion(line) or (
                    section is not None and line.startswith("Background:")
                    and rules_skeleton.holds_assertion(line)):
                raise ValueError(
                    f"line {lineno}, after {after}: an example in a "
                    f"Background, where it would never run; examples "
                    f"stand in a rule's fences: {line.strip()!r}")
            elif section is not None and line.startswith("Background:"):
                section, background = None, True
            elif not background or _STRUCTURE_RE.match(line):
                raise ValueError(
                    f"line {lineno}, after {after}: text outside any rule. "
                    f"A rule opens with a `# ID — name` heading, and a "
                    f"section file holds its `## Name (X)` heading and one "
                    f"`Background:` paragraph; read as nothing, this line "
                    f"would neither run nor be quotable: {line.strip()!r}")
            continue
        if section is not None:
            raise unresolved(lineno)
        background = False
        rid, numbered, _ = block
        if any(r.rule_id == rid for r in rules):
            raise ValueError(f"duplicate rule ID {rid} at line {lineno}")
        rules.append(rules_skeleton.parse_skeleton(rid, numbered))
    if section is not None:
        raise unresolved(len(text.splitlines()))
    return rules


def prose_blocks(text: str) -> dict[str, list[str]]:
    """The quotable lines of each rule, keyed by its ID, and of each
    section's Background paragraph, keyed by the section letter: for a
    rule, the text of its fields (rules_skeleton.skeleton_prose); for a
    section, the Background paragraph's lines, unjoined. What a citation
    may quote (test_doc_citations.py), read by one function."""
    from tests.v2 import rules_skeleton
    out: dict[str, list[str]] = {}
    section: str | None = None
    background: list[str] | None = None
    for _lineno, line, block in _walk(text):
        if block is not None:
            section = background = None
            parsed = rules_skeleton.parse_skeleton(block[0], block[1])
            assert parsed.skeleton is not None
            out[block[0]] = rules_skeleton.skeleton_prose(parsed.skeleton)
            continue
        hm = _SECTION_RE.match(line)
        if background is not None:
            if line.strip() and not hm:
                background.append(line)
                continue
            background = None
        if hm:
            section = hm.group(1)
        elif section and line.startswith("Background:"):
            background = out[section] = [line]
            section = None
    return out
