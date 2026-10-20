# M1 — delimited maiden names

**When:** a delimiter pair the caller configured for maiden names encloses a clause, as in "Jane Smith (née Jones)".

**Then:** its enclosed clause reads as the maiden name, and a leading recognized marker is dropped where the clause holds a word past it.

- **Clauses are independent:** two enclosures read as one maiden name, each dropping or keeping its own marker.
  ```
  "Jane Smith (Nee) (Jones)"  maiden-parens  →  maiden="Nee Jones"
  ```
- **Configuring the pair is what this rule needs for a clause that does not announce itself** — markerless content, and a lone marker alike, whether that marker is one word or several. A clause holding a word past its marker reads as the maiden name inside a nickname pair as well (M3), the suffix-shaped content S1 takes excepted there as it is here.

**Because:** an enclosure the caller has declared to mean maiden holds the former family name. A recognized marker word inside it marks the clause and is not itself part of the name.

```
"Jane Smith (née Jones)"  maiden-parens  →  maiden="Jones"
```

**Except:**

- **A clause of nothing but its marker keeps its words**, which may themselves be a surname (Nee).
  ```
  "Jane Smith (Nee)"  maiden-parens        →  maiden="Nee"  · boundary
  "Maria Kowalska (z domu)"  maiden-parens  →  maiden="z domu"  · boundary
  ```
- **A phrase marker the writer divided with a comma is not that marker**, so the clause keeps all its words.
  ```
  "Maria Kowalska (z, domu Nowak)"  maiden-parens  →  maiden="z, domu Nowak"  · boundary
  ```

**Precedence:**

- **Suffix-shaped content** ("Andrew Perkins (MBA)"): S1 takes it first, and the clause is no maiden name.
  ```
  "Andrew Perkins (MBA)"  maiden-parens  →  suffix="MBA"  · boundary
  ```
- **A pair configured for both maiden and nickname names** reads maiden: this rule wins over N1.

---
**Signal:** neighbor
**history:** decisions/M1 · **implemented:** nameparser/_pipeline/_extract.py, nameparser/_pipeline/_group.py
