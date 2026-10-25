# S8 — the credential's trailing run

**When:** a credential stands after the name core with more words behind it in its part, as in "John Smith PhD Jones".

**Then:** a credential after the name core starts a run to the end of its part (#602): every later word of that part reads as a suffix, except a title word, which reads as a title.

- **Where the run starts.** An unambiguous suffix word of two or more letters, in any script, standing after two name words where no comma divides the name or before a suffix comma, or after the given word in the part after a family comma, makes every later word of that part a suffix. So does a roman numeral of two or more letters that reads as the generation (S10), whether the vocabulary lists it or its shape alone reads it.
  ```
  "John Smith VI Jones"       →  suffix="VI Jones"
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
- **What is a credential here.** A title word never starts the run, and neither does a member of the ambiguous class, a single letter, a connective, a word that is also particle or bound given-name vocabulary: a credential is the writer's mark that the post-nominals have begun, and those carry no such mark. An honorific or a generational word carries it as a credential does, whatever its script.
  ```
  "Mary Jane King Smith"      →  family="Smith"
  "Josep Carod i Rovira"      →  family="Carod i Rovira"
  "Mohamed Ali Abd Allah"     →  family="Allah"
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
- **An ambiguous acronym written with its periods** ("John Smith M.A. Jones"): writing the periods makes it unambiguously a credential (S3), so it is no member of the ambiguous class here and starts the run.

---
**Signal:** neighbor: an unambiguous credential after the name core, and the rest of its part
**history:** decisions/S8 · **implemented:** nameparser/_pipeline/_assign.py, nameparser/_pipeline/_pieces.py
