# N1 — the default delimiter pairs

**When:** a configured nickname delimiter pair encloses a clause beside a name, as in "Andrew (Andy) Perkins".

**Then:** a clause enclosed by a configured nickname delimiter pair reads as the nickname and is lifted out of the name.

- **A comma inside the clause is kept as written:** the comma divides nothing there, though the dots T2 and T3 name still divide a clause as they divide a name.
  ```
  "Jane (Janey, Jo) Smith"    →  nickname="Janey, Jo"
  ```

**Because:** a quoted or bracketed clause beside a name is an informal alias, not part of the name.

```
"Andrew (Andy) Perkins"     →  nickname="Andy"
"Jean 'JD' Smith"           →  nickname="JD"
"John ｢Jack｣ Smith"         →  nickname="Jack"
```

**Except:**

- **An empty enclosure is simply dropped**, there being no clause to read.
  ```
  "Anna () Smith"             →  nickname=""  · boundary
  ```

---
**Signal:** neighbor
**history:** decisions/N1 · **implemented:** nameparser/_pipeline/_extract.py, nameparser/_pipeline/_tokenize.py
