# initials-repertoire — is_initial across scripts (#320)

## Standing

- Whether a script has initials is decided from CLDR's locale-authored name patterns and not from the script's typology, so Han, Hangul, Hiragana and Katakana are the scripts with none (`ja` and `ko` author 29 and 32 patterns and use an initial in none, where `ru` uses one in 7 of 39), listed by enumeration in `_policy._NO_INITIALS` so that a new Script member forces a decision and never inherits an answer — 2026-08-02 #320.
- A character of one of those scripts with a period is no initial, so `김민준 씨.` reads suffix '씨.' and `김민준, 씨.` family '김민준', suffix '씨.', while Cyrillic, Greek, Arabic and Hebrew initials stay initials (`Іван Й. Петренко` reads middle 'Й.') — 2026-08-02 #320.
- `is_initial` is not narrowed to `[A-Za-z]`, a narrowing declined on the measurement that `Й.` would regress to the #267 Ukrainian-conjunction misreading and the `initial` tag would be stripped from every non-Latin initial — 2026-08-02 #320.

Open: none in this file.

## Log

- 2026-08-02 #320 — IS_INITIAL ACROSS SCRIPTS: the principle bullet below and the Declined line after it, dated by the commit that recorded the CLDR criterion (373846b8).

- The principle: decided per script from CLDR's LOCALE-AUTHORED name patterns rather than from the script's typology — ja and ko author 29 and 32 patterns and use an initial in none of them, while ru uses one in 7 of 39 (`_policy._NO_INITIALS`' comment carries the counting recipe and the trap: `initialPattern` alone reports a period convention for locales that have none). Corrected 2026-09-10, #cjk-full-stops: this read "alphabetic-vs-CJK, not Latin-vs-non-Latin — Han, kana and hangul characters are morphemes or syllables, so a single one cannot stand in for a name word", which is the phonological restatement that comment forbids in as many words — Devanagari is an abugida and Arabic an abjad, neither has letters in that sense and both abbreviate, so a rule keyed on typology would put them here and their initials are real. _NO_INITIALS is ENUMERATED per script rather than derived from the script ranges, so a new Script member forces a decision instead of silently deciding Thai has no initials.

Declined:

- Narrowing is_initial to [A-Za-z] — measured: "Й." regresses to the #267 Ukrainian-conjunction misreading (the exact regression 2.1.0's release log claims to prevent), and the stable "initial" tag silently strips from every Cyrillic, Greek, Arabic and Hebrew initial, invisibly to the fields.

