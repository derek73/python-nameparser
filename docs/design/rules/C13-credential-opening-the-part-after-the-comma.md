# C13 — a credential opening the part after the comma

**When:** the first suffix word of the part after a family comma, with only titles in front of it, is one that starts S8's run, which S8 bounds (the split 'Ph. D.' among them), as in "John Smith, PhD Jones".

**Then:** a credential opening the part after a family comma makes it the postnominal part however it goes on, every word after it reading as that run reads, a title word as a title and any other word as a suffix.

- **The comma has then fixed nothing**, as with a part of no name word (C8), and a part before it holding one name word is the family ('John Smith, PhD Jones', 'Doe, PhD Jones').
  ```
  "John Smith, PhD Jones"     →  given="John"
  "John Smith, PhD Jones"     →  suffix="PhD Jones"
  "Doe, PhD Jones"            →  suffix="PhD Jones"
  "John Smith, Ph. D. Jones"  →  suffix="Ph. D. Jones"
  "Steven Hardman, RN - CRNA" →  given="Steven"
  ```

**Because:** a credential is written after the name it belongs to, so one standing first in the part after a family comma says the part is that name's postnominals and not its given name; a word that is also a title says nothing of the kind, being the listing form's title as often as a credential.

**Except:**

- **A word of both the title and the suffix vocabulary opens nothing, and nor does a credential behind one**: in front of a given name it is the listing form's title ('Smith, Ms Jane'), and no count of the words before the comma tells a surname of two words from a given name and a family name.
  ```
  "John Smith, RA Jones"      →  given="Jones"  · boundary
  "Smith, Ms Jane"            →  title="Ms"  · boundary
  ```

**Precedence:**

- **Under the strict comma-suffix switch** ("Smith, PSM I."): the opened run reads as it does without the switch, taking in the word the switch vetoes; C14 states that veto and this exception to it.

---
**Signal:** neighbor: a credential opening the part after a family comma
**history:** decisions/C13 · **implemented:** nameparser/_pipeline/_comma.py
