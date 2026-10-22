# A2 — the empty name

## Standing

- An input with no letter or digit parses to the empty name, where v1 kept `parse(".")` as given '.': `.` and `.,` read every field empty — 2026-07 PR #288.
- A report born from the punctuation survives the emptying, so malformed input stays distinguishable from blank input: `(` reports `unbalanced-delimiter` — 2026-07 PR #288.

Elsewhere: #629's declined field-naming report would have withdrawn a report from a name emptied of content (`", , -"`), against this rule; decisions/A1's 2026-10-10 #629 entry.

Open: none in this file.

## Log

- 2026-07 (v2 core, PR #288) — v1 kept parse(".") as first="."; 2.0 empties content-free input instead. The born-empty-ambiguity survival was a review fix in the rc1 arc: an unbalanced-delimiter report must outlive the emptying, or malformed input becomes indistinguishable from blank input.

