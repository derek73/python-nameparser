"""Parser for the skeleton rule format (#761), the format every rule in
docs/design/rules/ is written in.

A rule file opens with its heading and carries up to seven
bold-labelled fields, When, Then and Because required, in this order,
then a footer under a `---` line::

    # S10 — the trailing roman numeral

    **When:** the situation in the written name, one quoted example.
    **Tolerated:** reason (optional; a tolerated rule, W3)
    **Then:** what results, one sentence; an optional bullet list of detail.
    **Because:** why, three sentences at most.
    ```                      (a bare fence holds examples, one per line)
    "John Smith III"  →  suffix="III"
    ```
    **Except:** / **Precedence:** / **Accepted:**   (each a `- ` bullet list)
    - **A bold lead**, then prose, continued on lines indented two spaces.
      ```                    (a fence indented under a bullet belongs to it)
      "John V"  →  family="V"  · boundary
      ```

    ---
    **Signal:** a tag or `hub of C3, C4`
    **history:** decisions/S10 · **implemented:** nameparser/x.py

Rules the parser holds, all hard errors naming the rule and line: the
rule runs from its heading to the next markdown heading (a `#` run and a
space); a label is exactly `**Name:**` at the start of a line (a near
miss would leave its words as unlabelled prose, so it raises); When,
Then and Because are required and the fields stand in the order above,
each at most once; a fence is a bare ``` line (a language tag or a ~~~
fence raises) holding at least one example; every non-blank line inside
a fence is an example (rules_doc.parse_example_line), and outside one a
line, the text after a label or a bullet's text that parses as an
example or opens with a quote or a bracket (``_EXAMPLE_LEADS``:
straight, curly and guillemet quotes) raises, as does any line holding
an arrow and an assertion (`→  family=`) outside a backtick span, since
prose there would never run; a bullet is `- ` and text (`* `, `+ `, a
numbered item, a glued hyphen or an empty bullet raises, as does a
nested list or a heading in its continuation lines) and an Except,
Precedence or Accepted label has at least one; every Except bullet
carries an example; a Tolerated field is not empty; When, Tolerated and
Then are one paragraph each, Then one sentence, and Because three
sentences at most; a Signal or `no-boundary:` line above the `---`
raises, and below it only Signal, standing directly above the pointer
line, once, and spelled as a hub's where it names one, the pointer line
(every part `history:`, `implemented:` or `tracked:` with a value, none
repeated) and `no-boundary:` may appear, and `interacts:`, the block
format's advisory pointer, is refused. Everything outside a fence, the
footer and `no-boundary:` is quotable (``skeleton_prose``).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from tests.v2.rules_doc import (
    _EXAMPLE_RE, _RETIRED_RULE_RE, ASSERTABLE_FIELDS, NEAR_SIGNAL_RE,
    Example, Rule, _retired, parse_example_line)

HEADING_RE = re.compile(r"^# ([A-Z]\d+) — ")
#: What ends a rule's block: a markdown heading, a `#` run and a space.
#: A prose line opening `#761` is not one.
_ANY_HEADING_RE = re.compile(r"^#+ ")

_ORDER = ("When", "Tolerated", "Then", "Because",
          "Except", "Precedence", "Accepted")
_BULLET_FIELDS = frozenset({"Then", "Except", "Precedence", "Accepted"})
_BULLET_ONLY = frozenset({"Except", "Precedence", "Accepted"})
#: The prose fields refusing a second paragraph; Because is held to its
#: sentence count instead.
_ONE_PARAGRAPH = frozenset({"When", "Tolerated", "Then"})
_BOLD_LABEL_RE = re.compile(r"^\*\*(?P<label>[^*:]+):\*\*")
_NEAR_LABEL_RE = re.compile(
    r"^[*_\s]*(?:when|then|because|except|precedence|accepted|tolerated"
    r"|rationale)[*_\s]*:", re.IGNORECASE)
_NO_BOUNDARY_RE = re.compile(r"^\s*no-boundary:\s+(?P<reason>\S.*)$")
#: A hub's signal: the rules it maps, after any signal it reads itself.
_HUB_RE = re.compile(
    r"(?:(?P<own>\S.*?); )?hub of (?P<ids>[A-Z]\d+(?:, [A-Z]\d+)*)")
#: A signal meant as a hub's: one that does not fullmatch _HUB_RE
#: raises rather than reading as a plain signal, which would leave the
#: hub's rules unchecked. A plain word holding the letters ("Hubert",
#: "a hub-like word") is not one.
_NEAR_HUB_RE = re.compile(r"\bhubs?\b(?!-)", re.IGNORECASE)
_SIGNAL_LINE_RE = re.compile(r"^\*\*Signal:\*\*\s+(?P<text>\S.*?)\s*$")
_POINTER_LINE_RE = re.compile(r"^\s*(history|interacts|implemented|tracked):")
_POINTER_PART_RE = re.compile(
    r"(?P<key>history|interacts|implemented|tracked):\s*(?P<val>\S.*)")
#: A footer line written above the footer, in any spelling: read as
#: prose it would leave the rule's waiver or signal unset.
_NEAR_NO_BOUNDARY_RE = re.compile(r"^\s*[*_]*no-boundary\b", re.IGNORECASE)
#: An example's arrow and assertion, wherever it stands: outside a
#: fence a line holding one is an example that would never run.
_ARROW_FIELD_RE = re.compile(r"\s→\s+(?P<field>[a-z_]+)=")
#: A bullet marker other than `- ` then text: `* `, `+ `, a numbered
#: item (`1. `, `1) `), or a hyphen glued to its text.
_MALFORMED_BULLET_RE = re.compile(r"^(?:[*+](?:\s|$)|-(?! )|\d+[.)](?:\s|$))")
#: A list item in any markdown marker, as a bullet's continuation would
#: hold a nested list: `- `, `* `, `+ ` or a number and `.` or `)`.
_NESTED_ITEM_RE = re.compile(r"^(?:[-*+]|\d+[.)])\s")
_QUOTED_RE = re.compile(r'"[^"]*"')
_CODE_RE = re.compile(r"`[^`]*`")
_SENTENCE_END_RE = re.compile(r"[.?!]\s+[A-Z]")
#: A period after one of these ends no sentence: an initial ("V.
#: Smith") or a title abbreviation.
_NOT_TERMINAL_RE = re.compile(
    r"(?:^|[^\w])(?:[A-Z]|Dr|Mr|Mrs|Ms|St|Prof|Jr|Sr)$")
#: What parse_example_line treats as an attempted example: a line that
#: parses as one, or one opening with a quote or a bracket.
_EXAMPLE_LEADS = ('"', "[", "“", "”", "„", "‘", "’", "«")


def holds_assertion(s: str) -> bool:
    """Whether prose holds an example's assertion, which would never
    run there: a line that parses as an example, or an arrow and an
    assertion anywhere in it. One inside a backtick span is prose
    writing ABOUT the grammar (`` `→  family=` ``), not an example.
    Asked of a section's Background too (rules_doc.parse_rules_doc)."""
    if _EXAMPLE_RE.match(s):
        return True
    return any(m.group("field") in ASSERTABLE_FIELDS
               for m in _ARROW_FIELD_RE.finditer(_CODE_RE.sub("", s)))


def _looks_like_example(s: str) -> bool:
    """holds_assertion, or a line opening with a quote or a bracket,
    which a rule's prose may not: a Background may, since its wrapped
    lines do."""
    return holds_assertion(s) or s.lstrip().startswith(_EXAMPLE_LEADS)


@dataclass(frozen=True)
class Bullet:
    text: str
    examples: tuple[Example, ...]


@dataclass(frozen=True)
class Skeleton:
    when: str
    tolerated: str | None
    then: str
    then_bullets: tuple[Bullet, ...]
    because: str
    excepts: tuple[Bullet, ...]
    precedence: tuple[Bullet, ...]
    accepted: tuple[Bullet, ...]


def strip_bold(s: str) -> str:
    return s.replace("**", "")


def count_sentences(text: str) -> int:
    """Sentences in prose: quoted spans and backtick spans removed,
    `e.g.`/`i.e.` not terminal, a split being a `.?!` followed by
    whitespace and a capital, except a period after an initial (a lone
    capital, "V. Smith") or after Dr, Mr, Mrs, Ms, St, Prof, Jr or Sr.

    Not detected, so undercounted: a sentence that opens with anything
    but a capital (lowercase, a digit, a quote or backtick span, which
    is removed first), and a sentence that ENDS in an initial or one of
    those abbreviations, since the next one's capital reads as the name
    the initial belongs to ("It ends in V. Then more." is one)."""
    text = _CODE_RE.sub("", _QUOTED_RE.sub("", text))
    text = text.replace("e.g.", "eg").replace("i.e.", "ie")
    return 1 + sum(
        1 for m in _SENTENCE_END_RE.finditer(text)
        if not (text[m.start()] == "."
                and _NOT_TERMINAL_RE.search(text, 0, m.start())))


def skeleton_block_at(
        lines: list[str], i: int) -> tuple[str, list[tuple[int, str]], int] | None:
    """If lines[i] is a rule's heading: (rule ID, the block's (line
    number, text) pairs after it, the last line number of the block).
    Else None. Every block under a rule heading goes to parse_skeleton,
    which refuses one holding no field."""
    m = HEADING_RE.match(lines[i])
    if m is None:
        return None
    j = i + 1
    while j < len(lines) and not _ANY_HEADING_RE.match(lines[j]):
        j += 1
    body = lines[i + 1:j]
    return m.group(1), [(i + 2 + k, ln) for k, ln in enumerate(body)], j


_OUTSIDE_FENCE = (
    "an example line outside a fence: examples stand inside a bare ``` "
    "fence, where they run; outside one they would be read as prose: ")


class _Bul:
    def __init__(self, lineno: int, text: str) -> None:
        self.lineno = lineno
        self.parts = [text]
        self.examples: list[Example] = []

    def freeze(self) -> Bullet:
        return Bullet(strip_bold(" ".join(self.parts)), tuple(self.examples))


def parse_skeleton(rule_id: str, lines: list[tuple[int, str]]) -> Rule:
    rule = Rule(rule_id=rule_id)

    def err(lineno: int, msg: str) -> ValueError:
        return ValueError(f"{rule_id}: line {lineno}: {msg}")

    texts: dict[str, list[str]] = {}
    bullets: dict[str, list[_Bul]] = {}
    seen: list[str] = []            # labels in file order
    cur: str | None = None          # the open field
    mode = "closed"                 # prose | bullets | closed
    fence: list[Example] | None = None
    fence_at = 0
    fence_len = 0                   # len(fence) when it opened
    gap = False                     # a blank line since the last line
    footer = False
    signal_at: int | None = None

    for lineno, line in lines:
        if footer:
            body = line.strip()
            if signal_at is not None:
                if not _POINTER_LINE_RE.match(strip_bold(line)):
                    raise err(signal_at,
                              "a `**Signal:**` line must stand directly "
                              "above the rule's pointer line, on one line; "
                              f"the next line is {body!r}")
                signal_at = None
            if not body:
                continue
            sm = _SIGNAL_LINE_RE.match(body)
            nb = _NO_BOUNDARY_RE.match(body)
            if sm:
                if rule.signal is not None:
                    raise err(lineno, "a second `**Signal:**` line; "
                              "a rule states one")
                rule.signal = sm.group("text")
                hub = _HUB_RE.fullmatch(rule.signal)
                if hub is None and _NEAR_HUB_RE.search(rule.signal):
                    raise err(
                        lineno, "a hub's signal is `**Signal:** hub of "
                        "C3, C4` or `**Signal:** <own signals>; hub of "
                        "C3, C4`, rule IDs joined by a comma and a "
                        f"space: {body!r}")
                rule.hub = tuple(hub.group("ids").split(", ")) if hub else ()
                signal_at = lineno
            elif nb:
                rule.no_boundary = nb.group("reason")
            elif _POINTER_LINE_RE.match(strip_bold(body)):
                keys: list[str] = []
                for part in strip_bold(body).split("·"):
                    pm = _POINTER_PART_RE.fullmatch(part.strip())
                    if pm is None:
                        raise err(
                            lineno, "every part of the pointer line is "
                            "`history:`, `implemented:` or `tracked:` and "
                            f"a value, joined by ` · `: {part.strip()!r}")
                    key, val = pm.group("key"), pm.group("val")
                    if key in keys:
                        raise err(lineno, f"`{key}:` is repeated in the "
                                  "pointer line")
                    keys.append(key)
                    items = tuple(
                        v.strip() for v in val.split(",") if v.strip())
                    if key == "interacts":
                        raise err(
                            lineno, "interacts: is retired with the block "
                            "format; name the rule in Except or Precedence")
                    if key == "implemented":
                        rule.implemented = items
                    elif key == "tracked":
                        rule.tracked = items
            else:
                raise err(
                    lineno, "below the `---` footer only `**Signal:**`, "
                    f"the pointer line and `no-boundary:` may appear: "
                    f"{body!r}")
            continue

        if fence is not None:
            if line.strip() == "```":
                if len(fence) == fence_len:
                    raise err(fence_at, "an empty fence: a fence holds "
                              "examples, one per line")
                fence = None
                continue
            if not line.strip():
                continue
            ex = parse_example_line(line, rule_id, lineno)
            if ex is None:
                raise err(lineno, "every line inside a fence is an "
                          f"example and this is not one: {line.strip()!r}")
            fence.append(ex)
            rule.examples.append(ex)
            continue

        if not line.strip():
            gap = True
            continue
        after_gap, gap = gap, False
        if line.strip() == "---" and line == "---":
            footer = True
            cur = None
            continue
        if _RETIRED_RULE_RE.match(line):
            raise _retired(rule_id, lineno, line)
        if NEAR_SIGNAL_RE.match(line) or _NEAR_NO_BOUNDARY_RE.match(line):
            raise err(lineno, "a `**Signal:**` or `no-boundary:` line "
                      "belongs below the `---` footer; above it, it "
                      f"would be read as prose: {line.strip()!r}")
        bm = _BOLD_LABEL_RE.match(line)
        if bm:
            label = bm.group("label")
            rest = line[bm.end():]
            if label not in _ORDER:
                raise err(lineno, f"unknown field label {line.strip()!r}; "
                          f"the labels are {', '.join(_ORDER)}")
            if rest and not rest[0].isspace():
                raise err(lineno, f"a label is followed by a space: "
                          f"{line.strip()!r}")
            if label in seen:
                raise err(lineno, f"field {label} is repeated")
            if seen and _ORDER.index(label) < _ORDER.index(seen[-1]):
                raise err(lineno, f"field {label} is out of order after "
                          f"{seen[-1]}; the order is {', '.join(_ORDER)}")
            if not seen and label != "When":
                raise err(lineno, f"field {label} is out of order: "
                          "a rule opens with **When:**")
            seen.append(label)
            cur = label
            text = rest.strip()
            if _looks_like_example(text):
                raise err(lineno, _OUTSIDE_FENCE + repr(text))
            if label in _BULLET_ONLY:
                if text:
                    raise err(lineno, f"{label} takes a `- ` bullet list "
                              "under the label, not text on it")
                mode = "bullets"
            else:
                mode = "prose"
                texts[label] = [text] if text else []
            bullets.setdefault(label, [])
            continue
        if _NEAR_LABEL_RE.match(line):
            if re.match(r"^\*\*[^*:]+\*\*\s*:", line):
                how = "the colon goes inside the bold"
            elif "*" not in line.split(":", 1)[0]:
                how = "a label is bold"
            else:
                how = "a label is spelled exactly so"
            raise err(lineno, "looks like a field label but is not "
                      f"spelled `**Label:**` ({how}, capitalized): "
                      f"{line.strip()!r}")

        inner = line.strip()
        if _looks_like_example(inner):
            raise err(lineno, _OUTSIDE_FENCE + repr(inner))
        if inner.startswith(("```", "~~~")) and inner != "```":
            raise err(lineno, "a fence is a bare ``` line, no language "
                      f"tag and no ~~~: {inner!r}")
        if line.rstrip() == "```":
            if cur is None:
                raise err(lineno, "a fence outside any field")
            fence, fence_at, fence_len = [], lineno, 0
            mode = "closed"
            continue
        if line.startswith("- ") and line[2:].strip():
            if cur not in _BULLET_FIELDS:
                raise err(lineno, f"a bullet outside a field that takes "
                          f"them (Then, Except, Precedence, Accepted): "
                          f"{line.strip()!r}")
            text = line[2:].strip()
            if _looks_like_example(text):
                raise err(lineno, _OUTSIDE_FENCE + repr(text))
            bullets[cur].append(_Bul(lineno, text))
            mode = "bullets"
            continue
        if line.rstrip() == "-":
            raise err(lineno, "an empty bullet: a bullet is `- ` and text")
        if _MALFORMED_BULLET_RE.match(line):
            raise err(lineno, "a bullet is `- ` then text, a hyphen and "
                      f"one space: {line.strip()!r}")
        if line.startswith("  ") and mode == "bullets" and bullets.get(
                cur or ""):
            last = bullets[cur or ""][-1]
            inner = line.strip()
            if inner == "```":
                fence, fence_at = last.examples, lineno
                fence_len = len(fence)
                continue
            if _NESTED_ITEM_RE.match(inner):
                raise err(lineno, f"a nested list is not part of the "
                          f"grammar: {inner!r}")
            if _ANY_HEADING_RE.match(inner):
                raise err(lineno, f"a heading inside a bullet is not part "
                          f"of the grammar: {inner!r}")
            last.parts.append(inner)
            continue
        if cur is not None and mode == "prose" and not line.startswith(" "):
            if cur in _ONE_PARAGRAPH and after_gap and texts[cur]:
                raise err(lineno, f"{cur} is one paragraph"
                          + (" (detail goes in a bullet list under it)"
                             if cur == "Then" else "")
                          + f": {line.strip()!r}")
            texts[cur].append(line.strip())
            continue
        raise err(lineno, "a line outside a field (prose belongs in a "
                  "labelled field; a bullet continues on lines indented "
                  f"two spaces): {line.strip()!r}")

    if fence is not None:
        raise err(fence_at, "unclosed fence")
    if signal_at is not None:
        raise err(signal_at, "a `**Signal:**` line must stand directly "
                  "above the rule's pointer line; the text ends after it")
    for need in ("When", "Then", "Because"):
        if need not in seen:
            raise ValueError(f"{rule_id}: missing the **{need}:** field")
    for label in ("When", "Then", "Because"):
        if not texts[label]:
            raise ValueError(f"{rule_id}: the **{label}:** field is empty")

    def joined(label: str) -> str:
        return strip_bold(" ".join(texts[label]))

    then, because = joined("Then"), joined("Because")
    if count_sentences(then) > 1:
        raise ValueError(
            f"{rule_id}: Then is one sentence (detail goes in a bullet "
            f"list under it): {then!r}")
    if count_sentences(because) > 3:
        raise ValueError(
            f"{rule_id}: Because is three sentences at most: {because!r}")
    if "Tolerated" in seen and not texts["Tolerated"]:
        raise ValueError(f"{rule_id}: the **Tolerated:** field is empty; "
                         "a tolerated rule states why")
    for label in _BULLET_ONLY:
        if label in seen and not bullets[label]:
            raise ValueError(f"{rule_id}: the **{label}:** field has no "
                             "bullets; it is a `- ` bullet list, or absent")
    for b in bullets.get("Except", []):
        if not b.examples:
            raise err(b.lineno, "an Except bullet carries an example "
                      "(a fenced block under it): there is no example "
                      f"here: {b.parts[0]!r}")
    rule.skeleton = Skeleton(
        when=joined("When"),
        tolerated=joined("Tolerated") if "Tolerated" in texts else None,
        then=then,
        then_bullets=tuple(b.freeze() for b in bullets["Then"]),
        because=because,
        excepts=tuple(b.freeze() for b in bullets.get("Except", [])),
        precedence=tuple(b.freeze() for b in bullets.get("Precedence", [])),
        accepted=tuple(b.freeze() for b in bullets.get("Accepted", [])))
    return rule


def skeleton_parts(sk: Skeleton) -> list[tuple[str, str]]:
    """Every quotable field's text, tagged with its field (``Then
    bullet`` for a bullet under Then), in file order: the one list the
    quotable prose, the ID check and the size budget all read."""
    out = [("When", sk.when)]
    if sk.tolerated is not None:
        out.append(("Tolerated", sk.tolerated))
    out.append(("Then", sk.then))
    out += [("Then bullet", b.text) for b in sk.then_bullets]
    out.append(("Because", sk.because))
    out += [("Except", b.text) for b in sk.excepts]
    out += [("Precedence", b.text) for b in sk.precedence]
    out += [("Accepted", b.text) for b in sk.accepted]
    return out


def skeleton_prose(sk: Skeleton) -> list[str]:
    """The quotable lines, in file order: each field's text, its label
    left out."""
    return [text for _field, text in skeleton_parts(sk)]
