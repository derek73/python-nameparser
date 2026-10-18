# D2 — construction raises, parse never does

- 2026-07 (v2 core, PR #288) — every raise in the locale-apply path is a plain TypeError/ValueError so the wrap-with-locale-code rewrap cannot break on exotic exception signatures.

Declined (ambiguity kinds for script-resolved names, 2026-07-27):

- A "han-script" zh-vs-ja kind — applying the ZH pack IS the disambiguation; per-name flags after an explicit opt-in are noise.
- ORDER emission for script-resolved names — native-script order is convention, not a guess; the reserved kind stays unemitted. SEGMENTATION fires only on a genuine multi-split vocabulary fork (夏侯惇, 남궁민수).

