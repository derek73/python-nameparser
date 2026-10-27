# H3 — the title run's floor

**When:** title words stand in a name, as in "Asst. Vice Chancellor John Smith".

**Then:** successive title words at the start of the part carrying the given name chain into one title; a title word elsewhere in the name does not.

- **The run leaves one NAME word standing**, and a word of the suffix vocabulary is not that word: where everything behind the run is post-nominal, the run gives its last word back to the name, provided that word stands alone and is not itself suffix vocabulary.
  ```
  "Dr Pope Jr"                →  family="Pope"
  "Dr Pope Jr"                →  suffix="Jr"
  "RA DDS"                    →  family="DDS"
  ```

**Because:** compound titles are written as a run of title words, connectives included; a title word standing inside the name is just a name word. And a title addresses somebody, so the run leaves somebody there to address: a post-nominal is written about a name rather than being one, so it cannot be the name the run left.

```
"Asst. Vice Chancellor John Smith"  →  title="Asst. Vice Chancellor"
"Marquess of Bath"          →  title="Marquess of Bath"
"Morse, Det. Insp. Jane"    →  title="Det. Insp."
"John Doctor Smith"         →  middle="Doctor"  · boundary
```

**Accepted:**

- Before a family comma the run is H6's, which stops where nothing but post-nominals follows for the reason this one gives a word back, and always leaves the family one word, whatever that word is.
  ```
  "Dr. Jr., John"             →  family="Dr."
  ```
- The word given back must stand alone, so a title written as one joined unit stays whole and the post-nominal behind it is the name — turning the unit into a name and leaving no title at all is the worse of the two readings.
  ```
  "Prince of Wales Jr"        →  title="Prince of Wales"
  ```
- Where the run's whole content is the word given back, no title is left to make the reading H1's, so the word stands as the name and the parse reports the doubt (H4).
  ```
  "Dr Jr"                     →  given="Dr"
  "Dr Jr"                     →  ambiguities=("title-or-name",)
  ```

---
**Signal:** neighbor: title words in succession at the head of the given-name part, and what stands behind them
**history:** decisions/H3 · **implemented:** nameparser/_pipeline/_pieces.py
