# T3 — the interpunct's flank guard

## Standing

- U+00B7 divides only between classified-script characters, being also the Catalan punt volat interior to names (`Gal·la Smith` → given 'Gal·la'), while the nakaguro needs no such guard — 2026-07-30 #298, U+00B7 divides only
- The scope is the codepoint, not a blanket "dot = transcription" rule: U+00B7 records the transcription fact and suppresses the surname split, the name keeping the declared order rather than the script's (by default `威廉·莎士比亚` → given '威廉', family '莎士比亚'), and U+30FB and U+FF65 stay pure separators whose pieces the script licence reads (`高橋・一郎` → family '高橋'); cross-convention input reads by the codepoint it was typed with — 2026-07-30 #298, codepoint scope
- A decomposed hangul syllable flanks the interpunct as its composed twin does, the script table holding the conjoining jamo (decisions/nfd-shapes): decomposed `이서연·김민준` → given '이서연', family '김민준' — 2026-11-05 #1087
- The fullwidth full stop U+FF0E takes the same flank guard and the same transcription record as U+00B7, so `台邦．撒沙勒` → given '台邦', family '撒沙勒'; the ideographic full stop U+3002 stays out, being the sentence stop — 2026-11-10 #1312

The Declined line below stands as written: a half-flanked interpunct (`王·Smith`) stays in its word and reports nothing of its own.

Open: none in this file.

## Log

- 2026-07-30 #298 — codepoint scope, chosen over a blanket
  "dot = transcription" rule that would have flipped 高橋・一郎, a
  correct and deliberately pinned #272 reading: U+00B7 records the transcription fact and suppresses division; U+30FB/U+FF65 stay pure separators whose pieces the script license reads (rule W4's interpunct Except and its katakana-middle-dot Then bullet demonstrate both). Cross-convention input reads by the codepoint it was actually typed with — a chosen limitation, recorded in #298's comments.

- 2026-11-05 #1087 — A DECOMPOSED HANGUL SYLLABLE IS A CLASSIFIED FLANK. The guard reads raw characters, and the script table's HANGUL held only the precomposed syllables, so decomposed `이서연·김민준` kept the interpunct in one word where its composed twin divides; widening HANGUL to the conjoining jamo makes the two read alike. The measurement and the choice of blocks are decisions/nfd-shapes' entry of the same date.

- 2026-11-10 #1312 — THE FULLWIDTH FULL STOP IS A TRANSCRIPTION DOT BETWEEN CLASSIFIED CHARACTERS. Taiwan writes Indigenous names in Han with a dot between the given name and the family name, and some writers type U+FF0E where others type U+00B7; tw-donors writes it 16 times and jrc-names once (measured 2026-11-10), each read as one given name with a `given-or-family` report. It takes T3's guard whole, dividing and recording only between two classified characters, so the transcription keeps its declared order (W4) as the 间隔号 reading does. In Latin names it occurs once in the same corpora (`Wenzhao Zhong, Ph。D`), which the guard leaves alone, and `Kilang．Ｍanah` stays one word. The ideographic full stop U+3002 was left out as the sentence stop, between two Han names far likelier a typo than a dot; no measurement of it between names was taken.

Declined:

- Ambiguity emission on a half-flanked interpunct ("王·Smith") — proposed in the 2.1 PR review, declined because the dot decides silently under the no-emission decision; the undivided-dot-stays-in-the-word behavior went to docs instead.


- 2026-07-30 #298 — U+00B7 divides only between classified-script characters because it is also the Catalan punt volat, interior to legitimate names (Gal·la). The nakaguro (T2) needs no such guard: its codepoints are CJK-only and appear in no other script's names, which is what licenses an unconditional rule.

