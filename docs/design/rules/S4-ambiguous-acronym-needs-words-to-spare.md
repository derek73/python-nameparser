# S4 — the ambiguous acronym needs words to spare

**When:** a bare acronym that is also an ordinary name (MA, Ma) stands at a slot where a suffix may stand, as in "John Ma".

**Then:** a BARE ambiguous acronym is consumed only when the name has words to spare — as the second of two words it stays the family name — and at the slots that report, either reading carries the ambiguity flag, unless the word's writing has settled it (S6).

- **The slots that report** are the trailing slot of a name, the first slot after a family comma, the trailing slot of the GIVEN part after that comma, and the trailing slot of a maiden marker's clause (M2). A part beyond the second comma is not one of them; what such a part does report is C2's to say.
- **A word this document says is READ at one of those slots is not always a word one of them reports**: where a reading moves a word out of the slot that asked about it, what reports is the slot it lands in, and that may be none — M2 states the case where a clause does it.

**Because:** an acronym that is also an ordinary name is given up to the credential reading by position only where the name keeps a word for its family. A name of two words has none to spare.

```
"John Ma"                   →  family="Ma"  · boundary
"wang meng"                 →  family="meng"  · boundary
"tran lac"                  →  family="lac"
"john smith meng"           →  suffix="meng"
"JOHN SMITH MA"             →  suffix="MA"
"Nguyen Van Lac"            →  family="Van Lac"
```

**Precedence:**

- **The given part's trailing slot after a family comma** ("Doe, John MA"): the count is one piece of evidence among several, and the given part's trailing slot after a family comma is read without it (S5).
- **Written case in a mixed-case name** ("Jack MA"): written case outranks the count everywhere but the first slot after a comma, where the count decides first (S6, C4).
- **An unambiguous credential in front** ("John Smith PhD MEng"): it outranks both the count and the case (S7).

---
**Signal:** count: name words to spare beside a bare ambiguous acronym
**history:** decisions/S4 · **implemented:** nameparser/_pipeline/_classify.py, nameparser/_pipeline/_group.py, nameparser/_pipeline/_pieces.py
