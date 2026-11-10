# C16 — initials spelling a credential after one word and a comma

**When:** a run of two or more single letters joined by full stops that spells a listed credential opens the part after a family comma, alone or behind titles, and one word stands before the comma ('Jansen, J.P.', 'Smith, M.D.').

**Then:** behind one word, initials run together are the given name whatever they spell: the run reads as a run spelling nothing reads there (C4's count, C5), parted by T7, and the report names the credential as the other reading.

- **Every letter is a capital, or the name is written in one case**: lower case among capitals is no initials' writing, as T7 has it, and a letter with no case is none ('김민준씨, J.씨', a glued honorific).
  ```
  "Jansen, J.P."              →  given_names="J.P."  · boundary
  "Jansen, J.P."              →  ambiguities=("suffix-or-name",)
  "jansen, j.p."              →  given_names="j.p."
  "Jansen, j.p."              →  suffix="j.p."  · boundary
  ```
- **One word is C4's count of one name word, and one word as written too**: a title word the count passes over is a word here, and a capitalized particle is a word, since before another word it may be the given name; a particle in lower case before a word with a capital, in a name of mixed case, is the Dutch tussenvoegsel's writing and no word; and a suffix word of two or more letters ending the head behind a word is none, as is a numeral written in capitals, as C3 counts it; a single letter there ends a whole name (C1), and a title alone is no surname. An empty head reads as C15 has it, as a one-word head less the surname.
  ```
  "de Waart, J.P."            →  given_names="J.P."
  "Le, J.P."                  →  given_names="J.P."
  "Jansen Jr., J.P."          →  given_names="J.P."
  "Jansen VI, J.P."           →  given_names="J.P."
  "Bin Zhang, M.D."           →  suffix="M.D."  · boundary
  "Ashley Knight, M.S. BME"   →  suffix="M.S. BME"
  "Le Vi, M.D."               →  suffix="M.D."
  "Smith V, M.D."             →  given="Smith"
  ", J.P."                    →  given_names="J.P."
  ```
- **Titles in front of the run leave it the given name, and a particle behind it joins the family** as behind any given part.
  ```
  "Jansen, Ir. J.P. van"      →  family="van Jansen"
  "Jansen, Ir. J.P. van"      →  given_names="J.P."
  ```

**Because:** behind one word C4's count already reads the part as a name, and a person's initials spell a listed credential as often as letters fall together ('J.P.', 'R.A.', 'M.A.'), so what they spell says nothing about which they are. Dutch lists write every name 'Surname, Initials', and the bibliographies do too.

**Except:**

- **A suffix word in front of the run, or credentials as the only other words of the part, make it the credential run**: a credential, a word of the ambiguous class, a title/suffix dual written in capitals or an unlisted capitals word C6 admits, the name carrying C6's contrast, behind the run speaks for it, a spaced delimiter counting as none, unlike a run spelling nothing, which C5's speaker reads only in front of it. The letters spell a listed credential, so a credential beside them is company; a generation is not, being a name's, nor a dual written as the title it also is.
  ```
  "Smith, M.D. Ph.D."         →  suffix="M.D. Ph.D."
  "Smith, M.D. MS"            →  suffix="M.D. MS"
  "Smith, M.D. / PhD"         →  suffix="M.D. / PhD"
  "Smith, PhD J.P."           →  suffix="PhD J.P."
  "Rinehart, J.D. Jr."        →  given="J."  · boundary
  "Smith, J.P. Ms."           →  given="J."  · boundary
  "Jansen, J.P., M.D."        →  suffix="M.D."  · boundary
  ```

**Precedence:**

- **A credential opening the part** ("Smith, J.P. Jones"): this rule governs over C13, and the run is the given name with the words behind it, as its twin of unlisted letters reads.
  ```
  "Smith, J.P. Jones"         →  given="J."
  ```

**Accepted:**

- A one-word surname before a credential written as dotted initials reads as a name with no given name written out ('Smith, M.D.' → given 'M.', middle 'D.'), the credential named in the report; a credential then a given name past a second comma ('Arenas, M.D., Magdalena C.') reads as its twin of unlisted letters does. The undotted spelling is the credential's own and is unchanged ('Smith, MD').
  ```
  "Smith, M.D."               →  given="M."
  "Smith, MD"                 →  suffix="MD"
  ```

---
**Signal:** shape: a run of single letters joined by full stops after a family comma, behind one word as written
**history:** decisions/C16 · **implemented:** nameparser/_pipeline/_comma.py, nameparser/_pipeline/_pieces.py
