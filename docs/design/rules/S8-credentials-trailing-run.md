# S8 — the credential's trailing run

**When:** a credential stands after the name core with more words behind it in its part, as in "John Smith PhD Jones".

**Then:** a credential after the name core starts a run to the end of its part (#602): every later word of that part reads as a suffix, except a title word, which reads as a title; a word that may also be a given name (rules/H9) is a title word here only inside a title phrase.

- **Where the run starts.** An unambiguous suffix word of two or more letters, in any script, standing after two name words where no comma divides the name or before a suffix comma, or after the given word in the part after a family comma, makes every later word of that part a suffix. So does a roman numeral of two or more letters that reads as the generation (S10), whether the vocabulary lists it or its shape alone reads it, and so does a listed member of the ambiguous class its writing settles as the credential, written in capitals in a name of mixed case (S6) — after the given word in the part after a family comma wherever it stands, and elsewhere not where a name word stands behind it: a particle (a particle run or a joined surname counting by its first word), a word in a script with no case, or a word in Title case or in capitals that is no credential, which makes the capitals as likely the writer's own initials (`Maria Ana MA Silva`), or a family name written in capitals, as a credential.
  ```
  "John Smith VI Jones"       →  suffix="VI Jones"
  "Smith, John MA Jones"      →  suffix="MA Jones"
  "John Smith MA JD Jones"    →  suffix="MA JD Jones"
  "Maria Ana MA Silva"        →  family="Silva"
  "Jean Pierre MA DUPONT"     →  family="DUPONT"
  "Mary Jane MA Pope"         →  family="Pope"
  "Maria Ana MA de la Vega"   →  family="de la Vega"
  "Maria Ana MA Ortega y Gasset"  →  family="Ortega y Gasset"
  "Smith, John VI Jones"      →  suffix="VI Jones"
  "Smith, John PhD Jones"     →  suffix="PhD Jones"
  "John Smith PhD Prof. Ma"   →  suffix="PhD Ma"
  "Eric H. Holder Jr. Attorney General"  →  title="Attorney General"
  "John Smith Ph. D. Jones"   →  suffix="Ph. D. Jones"
  ```
- **How the name words are counted.** A lone particle is not a name word for the count, 'de Mesnil' being one surname, unless the credential stands right behind it, leaving it nothing to join: then it counts as a name word of its own ('John von PhD Jones'). A particle run with the words the chain joins to it is one name word, 'der la' and 'la Smith Secretary' each counting once (P2).
  ```
  "John von PhD Jones"        →  family="von"
  "John von PhD Jones"        →  suffix="PhD Jones"
  ```
- **What is a credential here.** A title word never starts the run, and neither does a member of the ambiguous class its writing leaves unsettled, a single letter, a connective, a word that is also particle or bound given-name vocabulary, the capitals of `DO` included: a credential is the writer's mark that the post-nominals have begun, and those carry no such mark. Where no family comma divides the name, nor does a credential acronym written in Title case with a name word behind it, as a settled member does not: Title case is how a name word is written, and `Md` is how Muhammad is written short; the acronyms whose own writing is Title case (`Bt`, `Kt`, `Knt`) read so too. Where no family comma divides the name, nor does a generation word written out, a numeral aside, with a name word behind it: a word that is no suffix word, numeral read as the generation (S10), initial, connective, title word or maiden marker, and is a particle or is written in Title case, in a script with no case, or in a name of one case. A generation word there was typed into the middle of a name written given name first, where a filer's form puts it, or is the given name Junior, and the family name stands behind it. Capitals behind it in a name of mixed case are no name word here, where behind a member its capitals settle they are one: behind that member capitals are as likely a family name or the writer's own initials as a credential, the member itself being capitals that may be initials, while a generation word is written out, so capitals behind it read as the credential that follows it as likely as a name. An honorific or a generational word otherwise carries it as a credential does, whatever its script.
  ```
  "Mary Jane Pope Smith"      →  family="Smith"
  "Josep Carod i Rovira"      →  family="Carod i Rovira"
  "Mohamed Ali Abd Allah"     →  family="Allah"
  "John Smith Ma Jones"       →  family="Jones"
  "JOHN SMITH MA JONES"       →  family="JONES"
  "John Smith DO Jones"       →  family="DO Jones"
  "Badrul Akmal Hisham Md Yusoff"  →  family="Yusoff"
  "John Smith Md Phd"         →  suffix="Md Phd"
  "John Smith MD Jones"       →  suffix="MD Jones"
  "Smith, John Md Jones"      →  suffix="Md Jones"
  "Guy Andre Junior Francois"  →  family="Francois"
  "John Smith Jr. Jones"      →  middle="Smith Jr."
  "JOHN SMITH JR JONES"       →  family="JONES"
  "Antonio Pavlović mlađi Jones"  →  family="Jones"
  "Pieter Bruegel stariji Jones"  →  family="Jones"
  "Ана Хорват старији Џонс"   →  family="Џонс"
  "Гай Плиний Старший Иванов"  →  family="Иванов"
  "John Smith Jr. PhD Jones"  →  suffix="Jr. PhD Jones"
  "John Smith Jr. CF"         →  suffix="Jr. CF"
  "Smith, John Jr. Jones"     →  suffix="Jr. Jones"
  "John Smith Esq Jones"      →  suffix="Esq Jones"
  "राम शर्मा साहब मोहन"          →  suffix="साहब मोहन"
  ```
- **What reports.** A name word the run absorbs is reported `suffix-or-name`.
  ```
  "John Smith PhD Jones"      →  ambiguities=("suffix-or-name",)
  "राम शर्मा साहब मोहन"          →  ambiguities=("suffix-or-name",)
  ```

**Because:** a credential is the writer's mark that the post-nominals have begun, so what follows it in its part is post-nominal too.

```
"John Smith PhD Jones"      →  suffix="PhD Jones"
"John PhD Smith"            →  family="Smith"  · boundary
```

**Except:**

- **After a family comma, the particles ending the given part**, behind any post-nominals, are not the run's: P6 attaches them to the family — other than a lone member of the ambiguous class, which reads as the credential.
  ```
  "Smith, John PhD de Jr."    →  family="de Smith"  · boundary
  ```

**Precedence:**

- **A credential split across a space** ("John Smith Pharm D Jones"): it is a member of the ambiguous class and starts the run all the same, behind the two name words its own count asks for (S12).
  ```
  "John Smith Pharm D Jones"  →  suffix="Pharm D Jones"
  ```
- **An ambiguous acronym written with its periods** ("John Smith M.A. Jones"): writing the periods makes it unambiguously a credential (S3), so it is no member of the ambiguous class here and starts the run, as its capitals in a name of mixed case make it start it (S6).

**Accepted:**

- Under the family-first orders the clause holds as written, so the word behind the generation word reads as a middle or given name, where the same name after a family comma reads it as the suffix; the filers' boxes that ground the clause are given-first, and no order is asked.
  ```
  "Smith John Jr. Jones"  family-first  →  middle="Jr. Jones"
  "Smith, John Jr. Jones"  family-first  →  suffix="Jr. Jones"
  ```
- With no family comma, a generation word written before the family name reads as a word of the middle name, not as the suffix it may be: the run does not start there, and lifting a post-nominal out of the middle of a name was declined for every credential (decisions/S8, #602).
  ```
  "Mr Robert Alexander (Jnr) Halliday"  →  middle="Alexander Jnr"
  ```
- With no family comma, a credential written in capitals with a name word behind it is read as a name word, where the same credential written with its periods starts the run: a name with its credential between its given names and its family name keeps the family name behind the credential, the capitals being read as initials as likely as a credential.
  ```
  "John Smith MA Jones"       →  family="Jones"
  "John Smith MA Jones"       →  middle="Smith MA"
  "John Smith M.A. Jones"     →  suffix="M.A. Jones"
  ```
- With no family comma, a credential acronym written in Title case is read as a name word before any word that reads as one, an unlisted credential and a title included: a run of Title-case credentials written without commas gives its last word to the family where that word is unlisted, and a title written after the credential becomes the family name. Neither shape was found in the local corpora (decisions/S8).
  ```
  "Jane Doe Rn Bsn"           →  family="Bsn"
  "John Smith Md Dr"          →  family="Dr"
  ```

---
**Signal:** neighbor: an unambiguous credential after the name core, and the rest of its part + case contrast: a credential acronym in Title case before a name word
**history:** decisions/S8 · **implemented:** nameparser/_pipeline/_assign.py, nameparser/_pipeline/_pieces.py
