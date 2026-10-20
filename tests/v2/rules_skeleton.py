"""Parser for the skeleton rule format (#761), the readable sibling of
the block format rules_doc.py defines.

A rule file opens with its heading and carries seven bold-labelled
fields in this order, then a footer under a `---` line::

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

Rules the parser holds, all hard errors naming the rule and line: a
label is exactly `**Name:**` at the start of a line (a near miss would
leave its words as unlabelled prose, so it raises); When, Then and
Because are required and the fields stand in the order above, each at
most once; every non-blank line inside a fence is an example
(rules_doc.parse_example_line); every Except bullet carries one;
Because is three sentences at most and Then's paragraph one; below the
`---` only Signal, the pointer line and `no-boundary:` may appear, and
`interacts:` is retired. Everything outside a fence, the footer and
`no-boundary:` is quotable (``skeleton_prose``).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from tests.v2.rules_doc import (
    _HUB_RE, _NEAR_HUB_RE, _NO_BOUNDARY_RE, _POINTER_PART_RE, Example,
    Rule, parse_example_line)

HEADING_RE = re.compile(r"^# ([A-Z]\d+) — ")

_ORDER = ("When", "Tolerated", "Then", "Because",
          "Except", "Precedence", "Accepted")
_BULLET_FIELDS = frozenset({"Then", "Except", "Precedence", "Accepted"})
_BULLET_ONLY = frozenset({"Except", "Precedence", "Accepted"})
_BOLD_LABEL_RE = re.compile(r"^\*\*(?P<label>[^*:]+):\*\*")
_NEAR_LABEL_RE = re.compile(
    r"^[*_\s]*(?:when|then|because|except|precedence|accepted|tolerated"
    r"|rationale)[*_\s]*:", re.IGNORECASE)
_SKELETON_START_RE = re.compile(
    r"^[*_]*(?:when|then|because)[*_]*\s*:", re.IGNORECASE)
_SIGNAL_LINE_RE = re.compile(r"^\*\*Signal:\*\*\s+(?P<text>\S.*?)\s*$")
_POINTER_LINE_RE = re.compile(r"^\s*(history|interacts|implemented|tracked):")
_QUOTED_RE = re.compile(r'"[^"]*"')
_CODE_RE = re.compile(r"`[^`]*`")
_SENTENCE_END_RE = re.compile(r"[.?!]\s+[A-Z]")


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
    whitespace and a capital."""
    text = _CODE_RE.sub("", _QUOTED_RE.sub("", text))
    text = text.replace("e.g.", "eg").replace("i.e.", "ie")
    return len(_SENTENCE_END_RE.findall(text)) + 1


def is_skeleton_block(lines: list[str]) -> bool:
    """True when the block holds a line opening a When, Then or Because
    field, in any spelling: a near miss must reach the skeleton parser
    to raise, not fall to the block parser, which would skip it."""
    return any(_SKELETON_START_RE.match(ln) for ln in lines)


def skeleton_block_at(
        lines: list[str], i: int) -> tuple[str, list[tuple[int, str]], int] | None:
    """If lines[i] is a skeleton rule's heading: (rule ID, the block's
    (line number, text) pairs after it, the last line number of the
    block). Else None."""
    m = HEADING_RE.match(lines[i])
    if m is None:
        return None
    j = i + 1
    while j < len(lines) and not lines[j].startswith("#"):
        j += 1
    body = lines[i + 1:j]
    if not is_skeleton_block(body):
        return None
    return m.group(1), [(i + 2 + k, ln) for k, ln in enumerate(body)], j


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
                for key, val in _POINTER_PART_RE.findall(strip_bold(body)):
                    items = tuple(
                        v.strip() for v in val.split(",") if v.strip())
                    if key == "interacts":
                        raise err(
                            lineno, "interacts: is retired in the skeleton "
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
            continue
        if line.strip() == "---" and line == "---":
            footer = True
            cur = None
            continue
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
            raise err(lineno, "looks like a field label but is not "
                      f"spelled `**Label:**` (bold, capitalized, colon "
                      f"inside the bold): {line.strip()!r}")

        if line.rstrip() == "```":
            if cur is None:
                raise err(lineno, "a fence outside any field")
            fence, fence_at = [], lineno
            mode = "closed"
            continue
        if line.startswith("- "):
            if cur not in _BULLET_FIELDS:
                raise err(lineno, f"a bullet outside a field that takes "
                          f"them (Then, Except, Precedence, Accepted): "
                          f"{line.strip()!r}")
            bullets[cur].append(_Bul(lineno, line[2:].strip()))
            mode = "bullets"
            continue
        if line.startswith("  ") and mode == "bullets" and bullets.get(
                cur or ""):
            last = bullets[cur or ""][-1]
            inner = line.strip()
            if inner == "```":
                fence, fence_at = last.examples, lineno
                continue
            if inner.startswith(("- ", "#")):
                raise err(lineno, f"a nested list is not part of the "
                          f"grammar: {inner!r}")
            last.parts.append(inner)
            continue
        if cur is not None and mode == "prose" and not line.startswith(" "):
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
    rule.tolerated = rule.skeleton.tolerated
    return rule


def skeleton_prose(sk: Skeleton) -> list[str]:
    """The quotable lines, in file order. Accepted bullets read as
    `Accepted: ` clauses so split_accepted counts them unchanged."""
    out = [sk.when]
    if sk.tolerated is not None:
        out.append(sk.tolerated)
    out.append(sk.then)
    out += [b.text for b in sk.then_bullets]
    out.append(sk.because)
    out += [b.text for b in sk.excepts]
    out += [b.text for b in sk.precedence]
    out += ["Accepted: " + b.text for b in sk.accepted]
    return out
