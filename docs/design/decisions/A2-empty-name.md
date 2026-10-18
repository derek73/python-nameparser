# A2 — the empty name

- 2026-07 (v2 core, PR #288) — v1 kept parse(".") as first="."; 2.0 empties content-free input instead. The born-empty-ambiguity survival was a review fix in the rc1 arc: an unbalanced-delimiter report must outlive the emptying, or malformed input becomes indistinguishable from blank input.

