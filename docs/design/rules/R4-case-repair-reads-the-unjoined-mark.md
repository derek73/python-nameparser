# R4 — case repair reads the unjoined mark

**When:** case repair is asked of a parsed name, as in "juan mcdonald".

**Then:** case repair returns a repaired copy and never mutates the parse, and where it acts at all — R5 decides where — the copy honors the casing a vocabulary entry records (PhD, BSc) and the Mc convention (McDonald), not only ordinary word-by-word casing.

- **Repair changes case and nothing else**: the repaired word is the word as written, recased. A word is read whole however its letters are encoded: a letter written as a base letter followed by its combining accent is repaired as the same letter written whole, and the repaired word keeps the encoding the writer used.
  ```
  "josé garcía"               →  capitalized="Jose\u0301 Garci\u0301a"
  "JOSÉ GARCÍA"               →  capitalized="Jose\u0301 Garci\u0301a"
  ```
- **Each run of letters a full stop divides is written as a word of its own**, so run-together initials keep a capital apiece. A word that opens with a modifier letter that has no case — the ayn and hamza of romanized Arabic, the Hawaiian okina — takes its capital on the letter after that mark, as a word opening with an apostrophe does. A digit is not passed over that way: it stands first in its word.
  ```
  "j.r.r. tolkien"            →  capitalized="J.R.R. Tolkien"
  "A.B. Vajpayee"             →  capitalized_forced="A.B. Vajpayee"
  "AHMAD IBN-ʿALĪ"            →  capitalized="Ahmad Ibn-ʿAlī"
  "Ahmad al-ʿAbbas"           →  capitalized_forced="Ahmad Al-ʿAbbas"
  "ʻIOLANI KAMAKA"            →  capitalized="ʻIolani Kamaka"
  "LT.GOV. JOHN DOE"          →  capitalized="Lt.Gov. John Doe"
  "lt.gov john doe"           →  capitalized="Lt.Gov John Doe"
  "st.john smith"             →  capitalized="St.John Smith"
  "J.Smith"                   →  capitalized_forced="J.Smith"
  "J.MCDONALD SMITH"          →  capitalized="J.McDonald Smith"
  "J.MACDONALD SMITH"         →  capitalized="J.MacDonald Smith"
  "m.ʿali smith"              →  capitalized="M.ʿAli Smith"
  "É.J. DUPONT"               →  capitalized="É.J. Dupont"
  "john 3rd smith"            →  capitalized="John 3rd Smith"  · boundary
  ```
- **An apostrophe between a Cyrillic letter and one of the vowels я, ю, є, ї, е, ё or і is part of the word's spelling**: it is the Ukrainian and Belarusian apostrophe, which marks the vowel as pronounced apart and never divides a prefix from a name, so the vowel keeps the word's lowercase. Any other apostrophe written as a punctuation mark (', ‘ or ’) divides the word, and the letter after it takes a capital, as in O'Brien and its Cyrillic spelling; the modifier letter apostrophe ʼ is a letter of the word and divides nothing.
  ```
  "БЕЗУГЛА МАР'ЯНА"           →  capitalized="Безугла Мар'яна"
  "ІВАН П'ЯТАК"               →  capitalized="Іван П'ятак"
  "ДЗМІТРЫЙ ЮР’ЕВІЧ"          →  capitalized="Дзмітрый Юр’евіч"
  "Мар’яна Безугла"           →  capitalized_forced="Мар’яна Безугла"
  "ЛЮДМИЛА О'КОННОР"          →  capitalized="Людмила О'Коннор"  · boundary
  "DEM'YAN SMITH"             →  capitalized="Dem'Yan Smith"  · boundary
  ```
- **A script that writes no initial capital is written in its lower case throughout**: Georgian writes its Mtavruli capitals only for a whole word set in capitals, so a name written in them repairs to plain Mkhedruli.
  ```
  "ᲜᲘᲜᲝ ᲑᲣᲠᲯᲐᲜᲐᲫᲔ"            →  capitalized="ნინო ბურჯანაძე"
  "Ნინო Ბურჯანაძე"            →  capitalized_forced="ნინო ბურჯანაძე"
  ```
- **A vocabulary entry records casing as a mask** — its word's letters, each in the case it takes — and repair lays it over the word as the writer punctuated it, so the one entry for phd repairs phd to PhD and ph.d. to Ph.D.; the mask applies wherever the word stands, whatever the parse read it as. A run of two or more letters beside a full stop takes the mask's case letter by letter and is never an initial.
  ```
  "john smith phd"            →  capitalized="John Smith PhD"
  "john smith ph.d."          →  capitalized="John Smith Ph.D."
  "JOHN SMITH PH.D."          →  capitalized="John Smith Ph.D."
  "john smith ph. d."         →  capitalized="John Smith Ph. D."
  "john smith bsc"            →  capitalized="John Smith BSc"
  "john smith psyd"           →  capitalized="John Smith PsyD"
  "SIG.RA MARIA ROSSI"        →  capitalized="Sig.ra Maria Rossi"
  "dott.ssa anna bianchi"     →  capitalized="Dott.ssa Anna Bianchi"
  "Dr. med. univ. Margit Popp, MSc"  →  capitalized_forced="Dr. Med. Univ. Margit Popp, MSc"
  "MSc Dr. med. univ."        →  capitalized_forced="MSc Dr. Med. Univ."
  ```
- **A particle is written in lowercase**, but a particle the vocabulary records a casing for takes that casing, the entry being how the word is written wherever it stands, and a particle of a kind written with a capital is written as a name word is: a saint's name (`St Clair`, `San Martín`) and a rank written inside the surname (`Freiherr von Richthofen`) take their capital in every convention that writes them. So is a particle opening a hyphenated word, which the hyphen joins to the name after it (`Ter-Petrosyan`, `Al-Ahmari`): it is written as a name word is, while a particle standing apart keeps its lowercase, save one R12 gives a capital as it opens the family name (`Ter Petrosyan`).
  ```
  "SEÁN Ó MURCHÚ"             →  capitalized="Seán Ó Murchú"
  "IVOI, PAUL D'"             →  capitalized="Paul d' Ivoi"
  "zaʿīm, ḥusnī az-"          →  capitalized="Ḥusnī az- Zaʿīm"
  "jacobus henricus van 't hoff"  →  capitalized="Jacobus Henricus van 't Hoff"
  "maria da-silva"            →  capitalized="Maria Da-Silva"
  "LEVON TER-PETROSYAN"       →  capitalized="Levon Ter-Petrosyan"
  "JAN VAN TER HORST"         →  capitalized="Jan van ter Horst"  · boundary
  "JOHN ST CLAIR"             →  capitalized="John St Clair"
  "JEAN ST-PIERRE"            →  capitalized="Jean St-Pierre"
  "JOSE SAN MARTIN"           →  capitalized="Jose San Martin"
  "JUAN STA. MARIA REYES"     →  capitalized="Juan Sta. Maria Reyes"
  "MANFRED FREIHERR VON RICHTHOFEN"  →  capitalized="Manfred Freiherr von Richthofen"
  "OTTO GRAF LAMBSDORFF"      →  capitalized="Otto Graf Lambsdorff"
  "ina binti navalamar"       →  capitalized="Ina binti Navalamar"  · boundary
  "juan de la vega"           →  capitalized="Juan de la Vega"  · boundary
  ```
- **A connective the parse placed among the name words** keeps its lowercase wherever it stands there, including inside a part whose other words the unjoined mark has turned into ordinary name words. That is this rule's own reading and not a borrowing from R3: a connective that initials because it joins nothing is still not written the way a name is written, while a generation is written the way a generation is written. The GENERATION is what the generation exception (Except) turns on and not the field: a connective the suffix field merely holds, which the suffix vocabulary does not know, was read as no generation and keeps its lowercase there like any other connective — the third part of a comma form is the shape that puts one there.
  ```
  "Smith, John, and"          →  capitalized_forced="John Smith and"
  "Doe, Jane, and Jr."        →  capitalized_forced="Jane Doe and Jr."
  ```
- **A name already written the way repair would write it comes back unchanged**, measured by repair's own conventions rather than by the bearer's. A spelling written in a single case is repaired even where its bearer meant it, because nothing in the text marks it as a choice; where the text does mark one, R5 defers to it.
  ```
  "Juan McDonald"             →  capitalized_forced="Juan McDonald"
  ```
- **A name opening Mac takes an inner capital only from a mask**: Mac opens names that are not Gaelic (Machado, Macías) and Gaelic names written both ways (Mackenzie, MacKenzie), so its spelling does not say which, and repair title-cases it unless a vocabulary entry records its casing. Mc keeps its convention, the names it opens being nearly all written McX, at the cost of the few that are not (Mchunu, written McHunu).
  ```
  "JOHN MACHADO"              →  capitalized="John Machado"
  "ROB ROY MACGREGOR"         →  capitalized="Rob Roy MacGregor"
  "Ronald Macdonald"          →  capitalized_forced="Ronald MacDonald"
  "JAMES MACKENZIE"           →  capitalized="James Mackenzie"  · boundary
  ```
- **A credential acronym the exceptions map does not carry is an initialism**, so a single-case word the parse put in the suffix role from the acronym vocabulary (written whole across any hyphen or slash it holds, `OTR/L`, not as two name words), or read as a credential by its dotted shape alone (S3) or by its capitals (S9), repairs to its all-caps spelling rather than a title-cased one, and that repair outranks the Mc convention where a word fits both (MCSE, not McSe). A roman numeral the parse put in the suffix role is written in capitals the way a generation is written, whether or not the vocabulary lists it (VI as well as III). A suffix word that is neither an acronym, a numeral nor an exceptions-map entry -- the generational `jr`, `sr` -- keeps its title case.
  ```
  "john smith md"             →  capitalized="John Smith MD"
  "john smith m.d."           →  capitalized="John Smith M.D."
  "john smith iii."           →  capitalized="John Smith III."
  "john smith x.y.z."         →  capitalized="John Smith X.Y.Z."
  "John Smith R.A.I."         →  capitalized_forced="John Smith R.A.I."
  "john doe q.c."             →  capitalized="John Doe Q.C."
  "john smith ed"             →  capitalized="John Smith ED"
  "john smith vi"             →  capitalized="John Smith VI"
  "john smith ix"             →  capitalized="John Smith IX"
  "john smith iii"            →  capitalized="John Smith III"
  "john smith, v"             →  capitalized="John Smith, V"
  "john smith mba"            →  capitalized="John Smith MBA"
  "john smith mcse"           →  capitalized="John Smith MCSE"
  "john smith, otr/l"         →  capitalized="John Smith, OTR/L"
  "JOHN SMITH, FNP-BC"        →  capitalized="John Smith, FNP-BC"
  "john smith pa-c"           →  capitalized="John Smith PA-C"
  "john smith jr"             →  capitalized="John Smith Jr"  · boundary
  "John Smith, otr/l"         →  capitalized="John Smith, otr/l"  · boundary
  "John Smith, otr/l"         →  capitalized_forced="John Smith, OTR/L"  · boundary
  "john smith-jones"          →  capitalized="John Smith-Jones"  · boundary
  "jean-luc picard"           →  capitalized="Jean-Luc Picard"  · boundary
  "dipl.-ing john smith"      →  capitalized="Dipl.-Ing John Smith"  · boundary
  "Md Abdul Karim"            →  capitalized_forced="Md Abdul Karim"
  ```
- **Inside a hyphenated word, a part that is connective vocabulary with a worded part on each side of it keeps its lowercase**, the hyphens being the writer joining the name around it (Ortega-y-Gasset); at either end of the hyphenated word it is repaired as ordinary name text. A single letter marked with a period is read as an initial there, as the parse reads it, never as the connective. A bare letter is not: the hyphen is the writer's join, so the interior connective is read as one even in a name written wholly in one case, where the same letter spaced reads as an initial if the vocabulary marks it as reading both ways (P8).
  ```
  "jose ortega-y-gasset"      →  capitalized="Jose Ortega-y-Gasset"
  "JOSE ORTEGA-Y-GASSET"      →  capitalized="Jose Ortega-y-Gasset"
  "maria silva-e-sousa"       →  capitalized="Maria Silva-e-Sousa"
  "Jose Ortega-Y-Gasset"      →  capitalized_forced="Jose Ortega-y-Gasset"
  "juan e-f smith"            →  capitalized="Juan E-F Smith"  · boundary
  "juan y-garcia"             →  capitalized="Juan Y-Garcia"  · boundary
  "juan y-garcia-lopez"       →  capitalized="Juan Y-Garcia-Lopez"  · boundary
  "j.-e.-p. dupont"           →  capitalized_forced="J.-E.-P. Dupont"  · boundary
  ```

**Because:** case repair is a display concern, applied only on request and never destructively.

```
"juan mcdonald"             →  capitalized="Juan McDonald"
"donovan mcnabb-smith"      →  capitalized="Donovan McNabb-Smith"
```

**Except:**

- **A part whose every word is particle vocabulary** is repaired as ordinary name words, since none of them is doing a particle's work there (R2). A connective that is not also particle vocabulary, standing between two of its words, is set aside in asking it, as R2 sets it aside.
  ```
  "ANH DO"                    →  capitalized="Anh Do"
  "anh van do"                →  capitalized="Anh Van Do"
  "FRITZ FREIHERR UND VON BAR"  →  capitalized="Fritz Freiherr und Von Bar"
  ```
- **An elided particle opening a hyphenated word** — one whose listed spelling opens with an apostrophe, the Dutch 's (des) and 't (het) — keeps its lowercase, as it does spaced: Dutch writes the article lowercase whether a space or a hyphen joins it to the name, and it is the particle written whole that the hyphen clause gives a capital.
  ```
  "WILLEM 'S-GRAVESANDE"      →  capitalized="Willem 's-Gravesande"
  "ARENT VAN 'S-GRAVESANDE"   →  capitalized="Arent van 's-Gravesande"
  "PIETER 'T-HART"            →  capitalized="Pieter 't-Hart"
  "Willem 'S-Gravesande"      →  capitalized_forced="Willem 's-Gravesande"
  "'S-JACOB SMIT"             →  capitalized="'S-Jacob Smit"  · boundary
  ```
- **A connective the parse read as the generation it also spells** is not a connective of this name at all, and is repaired as the generation it was read as.
  ```
  "John Quincy Smith i"       →  capitalized_forced="John Quincy Smith I"
  "Carod i"                   →  capitalized_forced="Carod I"
  ```
- **A single letter split off alone beside a full stop is written as an initial** and takes capitals whatever the mask says there — but only where the mask itself writes that letter inside a run of two or more letters: the writer split a chunk the mask keeps together, so the split-off letter is an initial. A run is of LETTERS only, so a digit ends one exactly as a full stop does. Where the mask writes the letter as a run of one too, there is no split to repair, and the mask's own case stands. So ph.d. is Ph.D. under the phd mask, and p.h.d. — three initials, not the mask's one run 'PhD' — is P.H.D.; but h.c. under a caller's own h.c mask, which spells each letter alone, stays h.c.
  ```
  "john smith p.h.d."         →  capitalized="John Smith P.H.D."
  ```
- **A word of the acronym or numeral class that parsed as an ordinary name word** repairs as that name word unless the exceptions map carries it (qc mp gives Qc MP, phd smith gives PhD Smith): those two classes read the role and the mask does not.
  ```
  "qc mp"                     →  capitalized="Qc MP"  · boundary
  "Jack XY.ZW."               →  capitalized_forced="Jack Xy.Zw."  · boundary
  "john smith xi"             →  capitalized="John Smith Xi"  · boundary
  "john smith, vi"            →  capitalized="Vi John Smith"  · boundary
  ```

**Accepted:**

- A Cyrillic spelling of an elided prefix before е or і, such as French d' (Д'Естен), loses the capital after its apostrophe, since the Belarusian apostrophe stands before those vowels inside a word and nothing in the letters tells the two apart.
  ```
  "ВАЛЕРІ Д'ЕСТЕН"            →  capitalized="Валері Д'естен"  · boundary
  ```
- A word of a kind written with a capital is a name word wherever it stands as a particle, so a romanized honorific spelled as a saint particle and joined to the name by a hyphen takes the capital too, as the same word spaced already does: the vocabulary records no romanized honorific, and the kind cannot tell the two apart.
  ```
  "Suzuki-san"  family-first  →  capitalized_forced="Suzuki-San"  · boundary
  ```
- A middle word written in one case that opens with an elided particle and a hyphen is repaired as the particle it spells, though the writer may mean a nickname: nothing in the letters of `'T-BONE` tells it from `'T-HART`. Written in mixed case it is left as written (R5).
  ```
  "AARON 'T-BONE WALKER"      →  capitalized="Aaron 't-Bone Walker"  · boundary
  "Aaron 'T-Bone Walker"      →  capitalized="Aaron 'T-Bone Walker"  · boundary
  ```
- An abbreviation the vocabulary does not list, whose letters after a full stop are the word's own ending rather than a word, is written as two words: the shape that divides run-together initials and joined words cannot tell an ending from either, and only a listed casing can.
  ```
  "DUT.RA MARIA SILVA"        →  capitalized="Dut.Ra Maria Silva"  · boundary
  ```
- A name written in one case whose hyphenated bare initials spell a connective pays for the hyphen clause — its interior letter is lowered as the connective though the writer meant an initial, where the same letters spaced keep their capitals. The hyphen is the writer's join, and reading the one shape both ways would need the case evidence a one-case name does not carry.
  ```
  "J-E-P DUPONT"              →  capitalized="J-e-P Dupont"  · boundary
  ```
- The all-particle clause reaches a part the parser read. A field spliced in as raw text after the parse carries no reading of its own, so a family set that way to "de la" stays lowercase where those same two words parsed from a name are repaired to "De La". The acronym repair is the contrast: it asks the role and the vocabulary and not a reading, so a suffix spliced in as "mba" is repaired to "MBA" exactly as a parsed one is. That is the boundary between splicing text into a field and revising a field through the parser — revise() classifies the value, so the repair follows it — rather than a gap between them. It is also a limit and not a regression: a spliced-in family was repaired exactly this way before the clause existed. (The shape needs a field edited after the parse, so no example line.)
- The boundary is drawn per question rather than per field: the conjunction carve-out reaches a word the parse read as a conjunction, and where the parse read nothing at all it reaches what the vocabulary says. A word of that vocabulary standing at either end of a longer written word is not a conjunction there, because the hyphen clause reaches only a worded part with a worded part on each side, and an edge part is outside that reach — but a field spliced in as raw text was read by nobody, so repair asks the vocabulary and a family set to "de y" keeps its "y" lowercase. Whether a word is the conjunction or an initial is a property of the word, which a vocabulary can answer; whether a particle is acting as a particle is a property of the whole part, which the parse settles and records; re-deriving it needs a reading on every word of the part, and a spliced field has none on any, so that half falls through to particle treatment and the spliced "de la" boundary of the bullet before stands. Initials are the contrast worth knowing, and R3 states it: that view is handed no vocabulary at all, so it falls back on neither question and a spliced field's every word initials. revise() classifies the value and crosses both questions, in both of the parsed name's views: a middle revised to "e-f" repairs to "E-F" as the parsed name does, where splicing the same text in gives "e-F".

---
**Signal:** shape + script: a word's own spelling: its recorded casing, the Mc convention and its punctuation, and the script it is written in, which decides whether an apostrophe divides it and whether it takes an initial capital at all
**history:** decisions/R4 · **implemented:** nameparser/_render.py, nameparser/_lexicon.py
