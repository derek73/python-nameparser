# N4 — the alias marker

**When:** a recognized alias marker stands as a word in a name, as in "Rahim @ Jaki bin Osman".

**Then:** a marker that counts takes the words after it as the nickname, and is itself dropped.

- **Where a marker counts.** Where M2's maiden marker counts, with a name word straight before it, but in any part that may hold a name word: the whole name where no comma divides it, the part before a suffix comma or a family comma, and the given part after a family comma. A part after a suffix comma holds no name word (C2), and a marker there is an ordinary word.
  ```
  "Ravi Kumar urf Raju"         →  nickname="Raju"
  "Osman, Rahim @ Jaki"         →  nickname="Jaki"
  "Wang @ Chan, Chris"          →  nickname="Chan"
  "Wang @ Chan, Chris"          →  family="Wang"
  "Rahim Osman @ Jaki, PhD"     →  nickname="Jaki"
  "Smith, John, Jr. @ Jack"     →  nickname=""  · boundary
  ```
- **It takes the words up to the first boundary:** a word read as a patronymic particle, another marker of either kind, or a comma. With none, it takes as far as M2's clause would in that part: up to the trailing run of post-nominals and titles in the part holding the family name, and up to the first suffix word before a family comma or in the given part after one. The words the boundary leaves are read as the name.
  ```
  "Rahim @ Jaki bin Osman"      →  nickname="Jaki"
  "Rahim @ Jaki bin Osman"      →  family="bin Osman"
  "Rahim bin Osman @ Usman"     →  family="bin Osman"
  "Rahim @ Jaki a/l Osman"      →  family="a/l Osman"
  "Rahim Osman @ Jaki PhD"      →  suffix="PhD"
  "Smith, John @ Jack Jr."      →  suffix="Jr."
  "Jane Smith @ Janey née Jones"  →  maiden="Jones"
  "Jane Smith née Jones @ JJ"   →  nickname="JJ"
  ```
- **Several words with no boundary among them are all taken**, so a whole second name is the nickname, and so is a byname of two words.
  ```
  "Tan Wei Keong @ Daniel Tan"  →  nickname="Daniel Tan"
  "Rahim Osman @ Tok Ben"       →  nickname="Tok Ben"
  ```
- **Two aliases join into one nickname**, as two bracketed nicknames do.
  ```
  "Mohd @ Ali bin Abu @ Bakar"  →  nickname="Ali Bakar"
  ```
- **A bracketed or quoted clause whose content opens with a recognized alias marker and carries a word after it reads as the nickname**, whichever bucket the enclosing pair sits in, the marker dropped as M3 drops it.
  ```
  "Ravi Kumar (urf Raju)"       →  nickname="Raju"
  "Ravi (urf Raju) Kumar"       →  family="Kumar"
  "Ravi Kumar (urf Raju)"  maiden-parens  →  nickname="Raju"
  ```

**Because:** an alias marker announces a second name the person is also known by; the marker is an announcement, not a name.

```
"Rahim Osman @ Jaki"          →  nickname="Jaki"
```

**Except:**

- **The at sign is a marker only written as a word of its own.** Glued to a word it is part of that word, as in an e-mail address or a handle.
  ```
  "Rahim Osman@Usman"           →  nickname=""  · boundary
  "Rahim Osman@Usman"           →  family="Osman@Usman"  · boundary
  "Rahim @Usman"                →  nickname=""  · boundary
  ```
- **The English alias and aka are recognized only where a caller lists them**, each being a given name or a surname more often than a marker.
  ```
  "Ravi Kumar alias Raju"       →  nickname=""  · boundary
  "Ravi Kumar alias Raju"  aka+alias  →  nickname="Raju"
  "Boscia, Frank aka Francis"  aka+alias  →  nickname="Francis"
  ```
- **A marker with nothing after it or no name word before it is just a word**, and so is one behind a title, a suffix word or a connective, as M2 says of its marker.
  ```
  "Rahim Osman @"               →  family="@"  · boundary
  "Osman, @ Jaki"               →  nickname=""  · boundary
  "Sir @ Jaki Osman"            →  nickname=""  · boundary
  ```
- **A suffix word, a patronymic particle or another marker straight after the marker announces nothing**, and the marker is then a word.
  ```
  "Rahim Osman @ Jr"            →  nickname=""  · boundary
  ```
- **A marker followed by a comma in a delimited clause is no marker**, as M3 says of its marker.
  ```
  "Ravi Kumar (urf, Raju)"      →  nickname="urf, Raju"  · boundary
  ```

**Precedence:**

- **A maiden marker in the same part:** the alias ends at it, and the maiden clause then reads as M2 reads it without the alias, so either may come first.

**Accepted:**

- A one-word alias followed by the family name takes the family name with it, the two shapes being written alike: the whole second name reads right and the one-word alias loses its family name to the nickname.
  ```
  "Rahim @ Jaki Osman"          →  nickname="Jaki Osman"
  "Rahim @ Jaki Osman"          →  family=""
  ```
- Where a particle ends the words before the marker, it bounds the particle join as M2's marker does, and the particle is left as the family name.
  ```
  "Rahim de la @ Jaki Vega"     →  family="de la"
  ```

---
**Signal:** neighbor
**history:** decisions/N4 · **implemented:** nameparser/_pipeline/_group.py, nameparser/_pipeline/_extract.py, nameparser/_pipeline/_classify.py
