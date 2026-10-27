# H8 — a salutation ending the given part

**When:** a family comma divides the name, and the given part after it ends in a word whose title reading is a salutation, written bare or with a stop at its edge that H5's abbreviation shape does not take (a doubled stop, as in "Mr.."), with a name word in front of it, as in "Doe, Jane Mrs".

**Then:** the word joins the title field, and the given part reads as it would without it.

- **It reads as the period-marked spelling reads.** The salutation chains into the trailing title run (H5) as a period-marked title word does, so the bare and the period-marked spellings read alike in every comma shape and under every name order: behind a post-nominal or in front of one, and behind another title.
  ```
  "Doe, John Mr Jr"           →  title="Mr"
  "Doe, John Mr Jr"           →  suffix="Jr"
  "Doe, John Jr Mr"           →  title="Mr"
  "Doe, Jane Mrs, PhD"        →  title="Mrs"
  "Doe, Jane Mr Mrs"          →  title="Mr Mrs"
  "Doe, Jane Mr.."            →  title="Mr.."
  ```

**Because:** H5 keeps a bare title word ending a name as a name word because the title vocabulary holds ordinary surnames, and after a family comma that reason is gone, the comma having marked the surname's place. What is left is the middle-name reading, and a salutation is a form of address, not a rank or office someone could be named after. Filers' software writes this order in volume (`DOE, JOHN Q MR`), the period as often left off as written.

```
"Doe, Jane Mrs"             →  title="Mrs"
"Doe, Jane Mrs"             →  given="Jane"
"DOE, JOHN Q MR"            →  middle="Q"
"van Doe, Jane Mrs"         →  family="van Doe"
"Doe, Mrs"                  →  family="Doe"  · boundary
"Jane Doe Mrs"              →  family="Mrs"  · boundary
```

**Except:**

- **A salutation that is also borne as a name stays a name word.** A middle name may be a given name or a surname, so the vocabulary marks only the salutations borne as neither, and goodman, master, herr and fru are left out with their counts, as is a non-Latin salutation whose romanization is borne where that script is written (बाबू, Babu).
  ```
  "Doe, John Goodman"         →  middle="Goodman"
  "Doe, John Master"          →  middle="Master"
  "Doe, Jane Fru"             →  middle="Fru"
  "शर्मा, राम बाबू"           →  middle="बाबू"
  ```
- **A title of any other kind stays a name word.** Office, rank and religious words are borne as middle names, and an academic title is not a salutation, so Dr written bare there stays one too.
  ```
  "Doe, John Pope"            →  middle="Pope"
  "Doe, Jane Dr"              →  middle="Dr"
  ```
- **A title/suffix dual stays with the suffix run** (S2): Ms and Sr are post-nominals as well, and the suffix reading takes them before any title reading is asked.
  ```
  "Doe, Jane Ms"              →  suffix="Ms"
  ```

**Precedence:**

- **A bare title word ending the name** (H5): H5 reads one as a name word, and after a family comma a salutation is this rule's, so H5's chain takes it as it takes a period-marked title.
  ```
  "Doe, Jane Mrs"             →  middle=""
  ```
- **A bound given-name word in front of the salutation** (P5): the join declines a salutation this rule reads, as it declines a trailing title H5 takes, so the bound word stands alone as the given name.
  ```
  "Doe, abdul Mrs"            →  given="abdul"
  ```
- **A particle in front of the salutation** (P6): the attachment reads the particle as though the salutation were absent, as it does in front of a period-marked title.
  ```
  "Doe, Jane van Mrs"         →  family="van Doe"
  ```

**Accepted:**

- A salutation that is someone's middle name, after a family comma, reads as the title. Miss is the nearest case the vocabulary keeps, borne as a surname by about 160 people in the US Census 2010.
  ```
  "Doe, Jane Miss"            →  title="Miss"
  ```
- With nothing before the comma, the one given word the salutation leaves reads as a title's lone name word reads (H1, C15's one exception), the family, as the period-marked spelling has read it since H5 (2.3.0, #316); written alone, that word is the given name.
  ```
  ", Jane Mrs"                →  family="Jane"
  ", Jane"                    →  given="Jane"
  ```
- The comma-less writing keeps the salutation a name word under a declared family-first order, though the declared order fixes the surname as a comma does: the rule reads the comma written in the name, not the order declared for it, so the two writings decisions/two-input-invariants pairs read this salutation differently.
  ```
  "Doe Jane Mrs" family-first →  middle="Mrs"
  ```

---
**Signal:** comma: a family comma dividing the name, with listed salutation vocabulary ending the given part
**history:** decisions/H8 · **implemented:** nameparser/_pipeline/_assign.py, nameparser/_pipeline/_classify.py, nameparser/_pipeline/_pieces.py
