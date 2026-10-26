# S13 — a bracketed member settled by its writing

**When:** a clause that is one member of the ambiguous class (S4) stands in brackets or quotes after the name, with no name word after it, though a suffix, a title or a maiden clause may follow however each is written, as in "John Smith (MA)".

**Then:** where the member's writing settles it as the credential, the way the rules that read the writing say a credential is written, it is no nickname but the suffix, and the clash is not reported.

- **Written with a period inside it**, whatever case the name is in: the periods are how a credential is written and a name is not (S3).
- **Written in capitals in a name written in more than one case**: the case is asked of the name's own words and never of the clause's, so capitals settle nothing in a name written wholly in one case, and Title case leans to the name (S6).
- **It is the suffix, not the word read as if written bare** (S1): the brackets have already set it apart from the name's words, and bare, two letters each followed by a period but the last read as initials (S3). The rest of the name is read as beside a nickname, which is where it can differ from a bracketed unambiguous credential in the same place, its twin, as the Accepted bullets record.

**Because:** after the name, brackets hold either a credential or the name the person goes by, and the writing tells the two apart where the count of words cannot: credentials are written in capitals and with their periods, and names are not. Inside the name the same word let out of the brackets would read as a middle name, where the brackets more likely hold the name the person goes by. So only the clause after the name is settled.

```
"John Smith (MA)"           →  suffix="MA"
"John Smith (MA)"           →  ambiguities=()
"John Smith (M.A)"          →  suffix="M.A"
"JOHN SMITH (M.A)"          →  suffix="M.A"
"Smith, John (MA)"          →  suffix="MA"
"John Smith PhD (MA)"       →  suffix="PhD MA"
"John Smith (MA), PhD"      →  suffix="MA, PhD"
"John Smith (MA) Ph. D."    →  suffix="MA Ph. D."
"John Smith (MA) Dr."       →  title="Dr."
"John Smith (MA) Dr."       →  suffix="MA"
"John Smith «MA»"           →  suffix="MA"
"Jack (M.A)"                →  suffix="M.A"
"John Smith 「MA」"          →  suffix="MA"
"John Smith (Ed)"           →  nickname="Ed"  · boundary
```

**Except:**

- **A member in a name written in one case, or not in capitals**, is settled only by a period inside it: its case says nothing (S6), and it stays the nickname S1 reads.
  ```
  "JOHN SMITH (MA)"           →  nickname="MA"
  "JOHN SMITH (MA)"           →  ambiguities=("suffix-or-nickname",)
  "john smith (MA)"           →  nickname="MA"
  "John Smith (Ma)"           →  nickname="Ma"
  ```
- **A member standing inside the name or before it** stays the nickname, however it is written.
  ```
  "Jeffrey (JD) Bricken"      →  nickname="JD"
  "JEFFREY (JD) BRICKEN"      →  nickname="JD"
  "Jean 'JD' Smith"           →  nickname="JD"
  "Jean (M.A) Smith"          →  nickname="M.A"
  "Jean (M.A) Smith"          →  ambiguities=("suffix-or-nickname",)
  "Smith (MA), John"          →  nickname="MA"
  "(MA) John Smith"           →  nickname="MA"
  "John Smith (MA) Ma"        →  nickname="MA"
  ```

**Precedence:**

- **Two letters each followed by a period but the last** ("John Smith (J.D)"): this rule reads the credential where S3 reads the same word bare as paired initials ("John Smith J.D" gives family 'J.D'), the brackets having already set it apart from the name's words.

**Accepted:**

- A lone name word beside a settled member stays the family name it is beside a nickname (N3), where beside its twin, "(PhD)", it is the given name, reported.
  ```
  "Jack (MA)"                 →  family="Jack"
  "Jack (MA)"                 →  ambiguities=()
  ```
- A maiden clause after a settled member stays the maiden name, where after its twin the credential's trailing run takes it (S8).
  ```
  "John Smith (MA) née Jones" →  maiden="Jones"
  ```
- The case is asked once, of the name's own words without any clause, so a member in capitals beside a settled one in a name otherwise written in one case stays the nickname, where its twin, joining the name's words, makes the name mixed and settles the other too.
  ```
  "JOHN SMITH (m.a) (MA)"     →  nickname="MA"
  "JOHN SMITH (m.a) (MA)"     →  suffix="m.a"
  ```
- A part past the second comma is weighed without the member, so what stands beside it decides whether the part reports, and the report names that alone, where its twin is weighed as a credential of the part.
  ```
  "Smith, John, X.Y.Z. (MA)"  →  ambiguities=()
  "Smith, John, Bob (MA)"     →  ambiguities=("comma-structure",)
  ```

---
**Signal:** position: a member of the ambiguous class alone in brackets or quotes after the name; hub of S1, S3, S6
**history:** decisions/S13 · **implemented:** nameparser/_pipeline/_post_rules.py
