# T3 — the interpunct's flank guard

- 2026-07-30 #298 — codepoint scope, chosen over a blanket
  "dot = transcription" rule that would have flipped 高橋・一郎, a
  correct and deliberately pinned #272 reading: U+00B7 records the transcription fact and suppresses division; U+30FB/U+FF65 stay pure separators whose pieces the script license reads (rule W4's Accepted pair demonstrates both). Cross-convention input reads by the codepoint it was actually typed with — a chosen limitation, recorded in #298's comments.

Declined:

- Ambiguity emission on a half-flanked interpunct ("王·Smith") — proposed in the 2.1 PR review, declined because the dot decides silently under the no-emission decision; the undivided-dot-stays-in-the-word behavior went to docs instead.


- 2026-07-30 #298 — U+00B7 divides only between classified-script characters because it is also the Catalan punt volat, interior to legitimate names (Gal·la). The nakaguro (T2) needs no such guard: its codepoints are CJK-only and appear in no other script's names, which is what licenses an unconditional rule.

