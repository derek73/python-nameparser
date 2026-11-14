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

- **A credential that is also a given name written short opens the given part** where the writing says it is the name, behind no whole name (C3's count, a title counting as a word): alone in the part with no title in front, in a name of mixed case, written with a lower-case letter its credential's own case mask does not write ('Rahman, Md'); or with a name word behind it, behind titles or not ('Rahman, Md Abdul', 'Uddin, Mr Md Karim'), a name word being one with no suffix or title reading of any kind, no half of a split credential, a letter, and in a name of mixed case no word in capitals but an initial. Elsewhere the run stands: capitals alone are the degree's own writing ('Novak, MD'); a credential, a title or a word in capitals behind it may be the degree's company; and alone behind a title it would leave the title as the only name word, so it stays the postnominal part. The fork is reported where it is taken, as a word of the ambiguous class reports it (C4).
  ```
  "Rahman, Md Abdul"          →  given="Md"
  "Rahman, Md."               →  given="Md."
  "RAHMAN, MD ABDUL"          →  given="MD"
  "Uddin, Mr Md Karim"        →  given="Md"
  "Smith, MD J"               →  given="MD"
  "RAHMAN, MD"                →  suffix="MD"  · boundary
  "rahman, md."               →  suffix="md."  · boundary
  "Smith, MD PhD"             →  suffix="MD PhD"  · boundary
  "Smith, Md PhD"             →  suffix="Md PhD"  · boundary
  "SMITH, MD DEAN"            →  suffix="MD DEAN"  · boundary
  "Smith, Md XYZ"             →  suffix="Md XYZ"  · boundary
  "Smith, Dr. Md"             →  suffix="Md"  · boundary
  "Uddin, Mr Md"              →  title="Mr"  · boundary
  "Dr. Rahman, Md"            →  suffix="Md"  · boundary
  "Rahman Khan, Md Abdul"     →  suffix="Md Abdul"  · boundary
  ```

**Precedence:**

- **Initials spelling a credential behind one word** ("Smith, J.P. Jones"): C16 governs, and the run opens the given part rather than the postnominal part.
- **Under the strict comma-suffix switch** ("Smith, PSM I."): the opened run reads as it does without the switch, taking in the word the switch vetoes; C14 states that veto and this exception to it.

**Accepted:**

- **A mixed-case `Md` before a title that may also be a name stays the credential**: a word with a title reading of any kind is no name word to the given-name Except, a title only inside a phrase included, so the part reads as before the Except, the postnominal one. No fetched corpus writes the shape.
  ```
  "Rahman, Md Sheikh Karim"   →  suffix="Md Sheikh Karim"
  "Rahman, Md Dean"           →  suffix="Md Dean"
  ```
- **A mixed-case `Md` before a name written in capitals stays the credential**: in a name of mixed case a word in capitals may be a credential, so it is no name word, and the part reads as before the Except. A strict choice that reads no other vocabulary for the word had read it as the given name, and now reads it as the default does.
  ```
  "Rahman, Md KARIM"          →  suffix="Md KARIM"
  ```
- **A lone `Md` behind a title stays the credential**, the given part's walk otherwise leaving the title as the only name word; so the comma's side has no given name, and the name match reads it against a `Md.` that is a given name as one-sided. Reading `Md` as the given name there needs a change in the given part's walk, which is not built.
  ```
  "Rahman, Mr Md"             →  suffix="Md"
  ```

---
**Signal:** neighbor: a credential opening the part after a family comma + case contrast: the given-name Except's own writing + neighbor: the word behind it
**history:** decisions/C13 · **implemented:** nameparser/_pipeline/_comma.py
