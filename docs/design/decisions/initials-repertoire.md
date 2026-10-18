# initials-repertoire — is_initial across scripts (#320)

- The principle: decided per script from CLDR's LOCALE-AUTHORED name patterns rather than from the script's typology — ja and ko author 29 and 32 patterns and use an initial in none of them, while ru uses one in 7 of 39 (`_policy._NO_INITIALS`' comment carries the counting recipe and the trap: `initialPattern` alone reports a period convention for locales that have none). Corrected 2026-09-10, #cjk-full-stops: this read "alphabetic-vs-CJK, not Latin-vs-non-Latin — Han, kana and hangul characters are morphemes or syllables, so a single one cannot stand in for a name word", which is the phonological restatement that comment forbids in as many words — Devanagari is an abugida and Arabic an abjad, neither has letters in that sense and both abbreviate, so a rule keyed on typology would put them here and their initials are real. _NO_INITIALS is ENUMERATED per script rather than derived from the script ranges, so a new Script member forces a decision instead of silently deciding Thai has no initials.

Declined:

- Narrowing is_initial to [A-Za-z] — measured: "Й." regresses to the #267 Ukrainian-conjunction misreading (the exact regression 2.1.0's release log claims to prevent), and the stable "initial" tag silently strips from every Cyrillic, Greek, Arabic and Hebrew initial, invisibly to the fields.

