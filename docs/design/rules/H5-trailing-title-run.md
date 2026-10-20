# H5 — the trailing title run

**When:** a period-marked word stands at the end of a name, behind any trailing suffix run, as in "John Smith Prof.".

**Then:** after the trailing suffix run has been taken, successive single words that wear the abbreviation shape and are title vocabulary chain into the title from the end, leaving one name word standing; a bare title word there is a name word, and an unlisted abbreviation there is a name word.

- **The title is transparent to the suffix reading**: where two or more name words stand, what stands once the chain is taken reads exactly as it would read written without the title, plus the title. Where the chain leaves ONE name word and no title run stands in front of it, there is no second reading for it to be transparent to, and the title behind that word decides its field as a title in front of it would (H1). Where a run DOES stand in front, that run addresses and the chained title only joins the title field, so the transparency holds for the one-word name too.
  ```
  "Smith Prof."               →  family="Smith"
  "Dr. John Smith Prof."      →  title="Dr. Prof."
  ```
- **Input order.** The trailing title words join the title field in input order after any leading run, because the title view reads the tokens in the order they were written.
  ```
  "Dr. John Smith Prof."      →  family="Smith"
  ```
- **A title among the post-nominals.** Transparency is what makes the suffix reading proof against a title standing among the post-nominals — a title AHEAD of a suffix word is taken all the same, and the suffix reading is then taken over what stands, not over what stood.
  ```
  "John Smith Prof. Jr."      →  suffix="Jr."
  "John Smith Jr. Prof."      →  suffix="Jr."
  "John Prof. MA"             →  suffix="MA"
  "JOHN PROF. MA"             →  family="MA"
  ```
- **What reports.** No fork is reported. Under the premise that the input is a name, a period-marked word the title vocabulary knows is not a reading a reader would hesitate over — where the doubt is real it is the word left STANDING that carries it, which is H4's report and not this rule's.

**Because:** a word abbreviated with a period at the END of a name is standing where a post-nominal stands, and the parts of a name that get abbreviated are the ones outside it. There is no shape rule there — H2's belongs to the front slot — so only a word the vocabulary knows as a title is one, and a bare title word is a name word, TITLES holding ordinary surnames.

```
"John Smith Prof."          →  title="Prof."
"John Smith Prof."          →  family="Smith"
"John Smith Prof. Dr."      →  title="Prof. Dr."
"Smith, John Prof."         →  title="Prof."
"John Smith Sir"            →  family="Sir"
"Mary Jane King"            →  family="King"
"John Smith Esq."           →  suffix="Esq."
"John Smith Xyz."           →  family="Xyz."  · boundary
```

**Precedence:**

- **A particle chain in front of a trailing title** ("John van der Berg Prof."): the title chain is read together with the trailing suffix run (S2), once the connectives have joined (P3) and before the particle chain is made, so a particle chain (P2) stops in front of a trailing title rather than taking it into the family name. A title word a connective joined into a longer unit is no single word for the title chain to take.
  ```
  "John van der Berg Prof."   →  title="Prof."
  "John van der Berg Prof."   →  family="van der Berg"
  ```
- **After a family comma** ("Smith, John van der Berg Prof."): the given part's particle chain stops in front of the trailing run of suffixes and titles, read as the comma-less name reads it, so there too a trailing title is the title and P6's attachment reads the particle in front of it as though the title were absent.
  ```
  "Smith, John van der Berg Prof." →  title="Prof."
  "Smith, John van der Berg Prof." →  middle="van der Berg"
  "Smith, Jan van Prof."      →  family="van Smith"
  ```
- **A maiden clause in front of a trailing title** ("Mary Smith née Jones Prof."): a maiden clause ends where the run the end of the name reads without it begins (M2), so where a trailing rule reads the part a trailing title ends the clause and is a title.
  ```
  "Mary Smith née Jones Prof." →  title="Prof."
  ```
- **A bound given-name word beside a trailing title** (P5): what the title chain leaves is also what counts as a name word to spare (P5). A trailing title word is not one, so a bound given-name word behind one joins exactly as it joins with the title absent — and lands in the same field, the run in FRONT of the joined pair being the run H1 asks about. Said of the comma-less writing, which is where the title chain runs before the reserve is read. After a family comma the reserve reads no peel, but the join declines a trailing title word the title chain takes (P5), so the title is read there too, save the shapes P5's Accepted clause records, as the segment written with an ordinary given name reads it.
  ```
  "Berg, abdul Prof."         →  title="Prof."
  ```

**Accepted:**

- The reach is the whole title vocabulary, the ordinary surnames in it included. TITLES holds king, judge and bishop, and a period written behind one of them is enough to make it the title and take it out of the name: `Mary Jane King.` reads title `King.` with family `Jane`, where the bare spelling keeps family `King`. That is a cost accepted under the premise that the input is a name (H Background), not a case this rule prevents — the period is a writing convention rather than evidence about the word, so every title whose spelling wears the abbreviation shape is reachable this way, and the BARE spelling is what the trailing slot is protected from.
  ```
  "Mary Jane King."           →  title="King."
  "Mary Jane King."           →  family="Jane"
  ```

---
**Signal:** shape: period-marked title vocabulary at the end of the name, behind the trailing suffix run
**history:** decisions/H5 · **implemented:** nameparser/_pipeline/_assign.py, nameparser/_pipeline/_group.py, nameparser/_pipeline/_pieces.py
