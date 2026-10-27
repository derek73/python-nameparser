# S8 — the credential's trailing run

**When:** a credential stands after the name core with more words behind it in its part, as in "John Smith PhD Jones".

**Then:** a credential after the name core starts a run to the end of its part (#602): every later word of that part reads as a suffix, except a title word, which reads as a title; a word that may also be a given name (rules/H9) is not a title word here.

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
- **What is a credential here.** A title word never starts the run, and neither does a member of the ambiguous class its writing leaves unsettled, a single letter, a connective, a word that is also particle or bound given-name vocabulary, the capitals of `DO` included: a credential is the writer's mark that the post-nominals have begun, and those carry no such mark. An honorific or a generational word carries it as a credential does, whatever its script.
  ```
  "Mary Jane Pope Smith"      →  family="Smith"
  "Josep Carod i Rovira"      →  family="Carod i Rovira"
  "Mohamed Ali Abd Allah"     →  family="Allah"
  "John Smith Ma Jones"       →  family="Jones"
  "JOHN SMITH MA JONES"       →  family="JONES"
  "John Smith DO Jones"       →  family="DO Jones"
  "Antonio Pavlović mlađi Jones"  →  suffix="mlađi Jones"
  "Pieter Bruegel stariji Jones"  →  suffix="stariji Jones"
  "Ана Хорват старији Џонс"   →  suffix="старији Џонс"
  "Гай Плиний Старший Иванов"  →  suffix="Старший Иванов"
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

- With no family comma, a credential written in capitals with a name word behind it is read as a name word, where the same credential written with its periods starts the run: a name with its credential between its given names and its family name keeps the family name behind the credential, the capitals being read as initials as likely as a credential.
  ```
  "John Smith MA Jones"       →  family="Jones"
  "John Smith MA Jones"       →  middle="Smith MA"
  "John Smith M.A. Jones"     →  suffix="M.A. Jones"
  ```

---
**Signal:** neighbor: an unambiguous credential after the name core, and the rest of its part
**history:** decisions/S8 · **implemented:** nameparser/_pipeline/_assign.py, nameparser/_pipeline/_pieces.py
