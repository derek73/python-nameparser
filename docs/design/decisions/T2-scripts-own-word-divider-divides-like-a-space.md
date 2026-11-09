# T2 — a script's own word divider divides like a space

## Standing

- The katakana middle dot and its halfwidth twin divide unconditionally, in tokenize, beyond the reach of either script opt-out; how they differ from the interpunct is decisions/T3's 2026-07-30 #298 codepoint-scope entry — 2026-07-29 #272
- The Ethiopic wordspace U+1361 divides as they do, on the same ground: it is Ethiopic-only and exists to divide words, so `አበበ፡ከበደ፡ተሰማ` reads given 'አበበ', middle 'ከበደ', family 'ተሰማ' — 2026-11-08 #1202.

Open: none in this file.

## Log

- 2026-07-29 #272 (811ec547; recorded here 2026-11-08, when this file opened) — the katakana middle dot U+30FB and its halfwidth twin U+FF65 became token separators, unconditionally: they divide transcribed foreign names (`マイケル・ジャクソン`) and kanji roster pairs (`高橋・一郎`), and appear in no native name. The history of their scope beside the interpunct is decisions/T3's 2026-07-30 #298 codepoint-scope entry.
- 2026-11-08 #1202 — THE ETHIOPIC WORDSPACE DIVIDES LIKE THE NAKAGURO. U+1361 ETHIOPIC WORDSPACE, the two-dot divider traditional and formal Ge'ez writing puts between words, joins the katakana middle dot and its twin in `_tokenize._NAME_DOT_SEPARATORS`: a character of one script that marks nothing but a word boundary, the not-a-guess standard root AGENTS.md's scoped exception asks for, since the codepoint itself settles it. Like the nakaguro it records no offset and is written back alone, with no space around it (`_render._DOT_SEPARATORS`, rules/R6), so `str(parse("አበበ፡ከበደ፡ተሰማ"))` keeps the wordspace and the spaced `አበበ፡ ከበደ፡ ተሰማ` renders `አበበ፡ከበደ፡ተሰማ`. 1.4.0 and every 2.x and 3.0 release read the unspaced form as one given name. No real list writing it between names was found: the House of Peoples' Representatives list (OpenSanctions `et_hopr`) and Wikidata's Amharic labels write a space; it shipped on the certainty T2 already gave the nakaguro, as the issue's question offered.
  - Declined, for now: the Ethiopic semicolon U+1364 as a `;` delimiter (#871's shape) — no source writes one in a name, and the issue left it a question.
