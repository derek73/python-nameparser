# script-table-placement — a recorded reversal

## Standing

- The script range tables live in `_policy`, not `_vocab` as #271 documented, because packs cannot import the pipeline, and a pack's compiled pattern is held in a closure rather than at module level — 2026-07-29.
- U+3006 〆 is in the HAN span, beyond UAX #24, for the Japanese surnames it appears in: `〆木 太郎` → family '〆木', given '太郎' — 2026-07-29.

Open: none in this file.

## Log

- 2026-07-29 (script-ranges relocation) — REVERSES #271's documented choice ("tables deliberately live in _vocab"): the tables moved to _policy because packs cannot import the pipeline, evidenced by two hand copies with sync tests and a blocked 16–30× compiled-regex optimization (a module-level re.Pattern in a pack would flip its classification, hence the closure-held-pattern convention). Rider: U+3006 〆 joined the HAN span on a justification deliberately beyond UAX #24 — it is Script=Common but appears solely in Japanese surnames (〆木, 〆谷, 〆野).

