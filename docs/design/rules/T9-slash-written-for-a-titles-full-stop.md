# T9 — a slash written for a title's full stop

**When:** a listed title opens the name, or the given part after a family comma, written with a slash where its full stop would stand, as in "Dr/ Jane Smith" or "د/ أحمد علي".

**Then:** the slash reads as the title's full stop would, a separator: the title is read as it is written without the slash, and the slash is in no field, whether it stands glued to the title before a space, glued to both the title and the name after it, alone between them, or glued to the name.
```
"د/ أحمد علي"               →  title="د"
"د/ أحمد علي"               →  given="أحمد"
"د/أحمد علي حسن"            →  given="أحمد"
"د / أحمد علي"              →  title="د"
"د /أحمد علي"               →  given="أحمد"
"Dr/ Jane Smith"            →  title="Dr"
"Prof/Jane Smith"           →  given="Jane"
"Smith, Dr/ Jane"           →  title="Dr"
"أ.د/ أحمد علي"             →  title="أ.د"
```

- **A listed title** is a title the vocabulary lists that is neither a saint particle, nor a suffix too, nor a given name too (H9).
  ```
  "اللواء/ أحمد علي"          →  title="اللواء"
  ```
- **The name after the slash** is one name word as T8 reads the name after a stop — letters, apostrophes and hyphens, its full stops set aside, so an initial or a name written short counts, with no delimiter, digit or slash of its own — that no title, title modifier or suffix reading claims outright; a title or a suffix that is also a given name is read as it is after the title's full stop, and so is a given name written short that is also a credential, unless written in capitals, where it is the credential. There must be one, so a title and a slash ending the part keep their word.
  ```
  "Dr/ Dean Smith"            →  given="Dean"
  "Dr/ Ed Smith"              →  given="Ed"
  "Dr/ J. Smith"              →  given="J."
  "Dr/ Md. Smith"             →  given="Md."
  ```
- **A title listed with a slash of its own** is the title whole, the slash after it the one read.
  ```
  "mag/judge / Jane Smith"    →  title="mag/judge"
  ```
- **The rendering drops the slash**, the title and the name standing apart as written with a space.
  ```
  "Dr/Jane Smith"             →  str="Dr Jane Smith"
  ```

**Because:** Egypt's parliament writes a title with a slash in place of its full stop as its usual form (`د/`, `أ.د/`, `اللواء/`), ORCID's Arabic-script holders write it too, and a few Latin writers do (`Dr/`, `Prof/`). Read as written, the title was the given name and the slash a word of the name. Elsewhere a slash joins words that are no title — credentials, a Malaysian name's relation, care of, a company's form — so the reading stays at the head, where a listed title says what the slash is.

**Except:**

- **A word the slash joins with no listed title in front** keeps its reading: credentials joined by it, a relation, care of, an abbreviation whose first chunk is no title.
  ```
  "Jane Smith MD/PhD"         →  suffix="MD/PhD"
  "Jane Smith OTR/L"          →  suffix="OTR/L"
  "Kumar a/l Rajan"           →  family="a/l Rajan"
  "A/Prof Jane Smith"         →  given="A/Prof"
  ```
- **A title the slash joins to a title or a credential** keeps the one word, a slash between two titles reading "or" where glued.
  ```
  "Dr/Mrs Jane Smith"         →  given="Dr/Mrs"
  "Dr/MD Jane Smith"          →  given="Dr/MD"
  "Dr/ MD Smith"              →  given="Dr/"
  ```
- **A title with a slash anywhere but the head** is a name word as it was: later in the name, behind another title, or ending it.
  ```
  "Jane Dr/ Smith"            →  middle="Dr/"
  "Mr. Dr/ Jane Smith"        →  given="Dr/"  · boundary
  "Jane Smith Dr/"            →  family="Dr/"
  ```
- **A saint particle, a title that is also a given name and a title that is also a suffix** with a slash keep their word, the last joined so as often in a credential.
  ```
  "St/ John Smith"            →  given="St/"
  "Dean/ Jane Smith"          →  given="Dean/"
  "CPO/L Jane Smith"          →  given="CPO/L"
  "Ms/ Jane Smith"            →  given="Ms/"
  ```
- **The part before a family comma** is a surname, and a slash glued there joins two, a couple's or a person's, so T9 does not read it and the word stays whole.
  ```
  "JURIST/KOVAC, DANIEL/KAREN"  →  family="JURIST/KOVAC"  · boundary
  "Dr/ Smith, Jane"           →  family="Dr/ Smith"
  ```

**Precedence:**

- **A slash standing alone after the first comma** before a credential ("Jane Smith, Dr / PhD"): no name follows it, so C10 reads it as a suffix delimiter.
  ```
  "Jane Smith, Dr / PhD"      →  suffix="PhD"
  ```

**Accepted:**

- The rendering does not keep the slash, where T8 keeps a glued word as written: the slash is a separator, as a delimiter C10 drops is.
- A title behind the title that opens the name stays a name word with its slash ('Mr. Dr/ Jane Smith'), a title run's later words being written so in none of the lists.
- A title standing as its own word after the slash keeps the word whole, though a slash written before a space may join a title run ('Prof/ Dr Jane Smith' → given 'Prof/', as before T9); glued to a name at its own stop it divides as after the full stop ('Dr/Mrs.Jane Smith' → title 'Dr Mrs.', as 'Dr. Mrs.Jane Smith' reads).
- A slash written apart after a title opening the part before a family comma is left where H6's title peel leaves it, in the surname ('Dr / Smith, Jane' → family '/ Smith', as before T9).
- A degree's field glued after the slash divides as a name, as T8 divides it after a stop ('Dr/Med Hans Meier' → given 'Med').
- A title glued at its slash to a name standing alone before a suffix comma is not read ('Dr/Jane, PhD' → family 'Dr/Jane'), the comma's decision being asked of the word undivided, where T8's 'Dr.Jane, PhD' reads title 'Dr.'.
- A given name written short that is also a credential reads as the credential after the slash where written in capitals, though the full stop's spelling reads the name ('Dr/ MD Smith' → given 'Dr/', where 'Dr. MD Smith' reads given 'MD'), so in a name written wholly in capitals it is never the given name ('DR/ MD YUSRI BIN ALI', as before T9).
- Two roles joined by a slash in front of a name read the first as the title and the second as the given name ('Director/Owner Jane Smith' → given 'Owner'), where before T9 the pair was the given name.

---
**Signal:** shape: a slash after a listed title opening the name or the given part after a family comma
**history:** decisions/T9 · **implemented:** nameparser/_pipeline/_script_segment.py
