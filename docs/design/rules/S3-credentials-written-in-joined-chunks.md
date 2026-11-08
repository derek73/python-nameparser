# S3 — credentials written in joined chunks

**When:** a word written in chunks, joined by interior periods or by a hyphen or a slash, stands in a name, as in "John Smith Msc.Ed.".

**Then:** a word with interior periods reads as a suffix when every one of its period-separated chunks counts as a suffix as written, a word joined by a hyphen or a slash the same way, and a word of two or more period-separated chunks that the chunks do not make a suffix is read by POSITION instead, as a bare ambiguous acronym is (S4).

- **An ambiguous acronym written with its periods**, one after each letter or one after each of two or more letter chunks, counts unambiguously; a single trailing period is the abbreviation shape any word can wear and does not. Written so, it is not the bare acronym S4 counts words to spare for: the periods are how a credential is written and a name is not.
  ```
  "John Smith M.A."           →  suffix="M.A."
  "Wang M.Eng."               →  suffix="M.Eng."
  ```
- **Every chunk counts, the periods' as a slash's do**: a chunk counts as a suffix as written, or is a member of the ambiguous class (S4) another chunk settles, as in a word a slash joins (below), and a chunk of no letter or digit is no chunk. A word with a chunk that does not count is read by position, so a name glued to a credential by a period is no credential by that credential alone, and where it is the suffix the reading is reported. In brackets the same word is set apart as the slash's is (S1), and a word holding a member is a member itself there (below).
  ```
  "John Smith Msc.Ed"         →  suffix="Msc.Ed"
  "John Smith JD.CPA"         →  suffix="JD.CPA"
  "John Smith Bob.PhD"        →  suffix="Bob.PhD"
  "John Smith Bob.PhD"        →  ambiguities=("suffix-or-name",)
  "John Smith (Msc.Ed)"       →  suffix="Msc.Ed"
  "John (Msc.Ed) Smith"       →  nickname="Msc.Ed"
  "John (Msc.Ed) Smith"       →  ambiguities=("suffix-or-nickname",)
  "John Smith (Bob.PhD)"      →  nickname="Bob.PhD"  · boundary
  "John Smith [Msc.Ed]"       →  family="[Msc.Ed]"  · boundary
  "John Smith Jr.; MD"        →  suffix="Jr.; MD"
  "John Smith, Dr. J.씨"       →  suffix="J.씨"
  ```
- **A word no vocabulary claims, read by position**, is a credential where the name has words to spare, a name word where it does not, either reading reported at the slots S4 reports at, and the same at a comma — which means the FIRST piece after a family comma, the word trailing the given part after one, the word ending a maiden marker's clause (M2), and the part before a SUFFIX comma. The part before a FAMILY comma never reports, the comma having already named it the family.
  ```
  "John Smith J.u.n.i.o.r."   →  suffix="J.u.n.i.o.r."
  "John Smith Q.W.E.R.T."     →  suffix="Q.W.E.R.T."
  "John Smith X.Y.Z."         →  suffix="X.Y.Z."
  "Doe, John X.Y.Z."          →  suffix="X.Y.Z."
  "Jane Doe nee Smith X.Y.Z." →  suffix="X.Y.Z."
  ```
- **What the position reading reads.** Case says nothing here — the periods are the evidence — and three shapes are outside it: a single trailing period is not this shape at all, a chunk that is not wholly alphabetic is no acronym letter, and a word carrying a script that writes no abbreviations is not wearing an abbreviation's periods (H2 refuses the same word for the same reason).
  ```
  "john smith x.y.z."         →  suffix="x.y.z."
  "John Smith 1.4"            →  family="1.4"  · boundary
  ```
- **A word joined by a hyphen or a slash** is read by the periods' test: a word whose chunks are joined by a hyphen or a slash reads as a suffix when every chunk counts as a suffix as written, which is to say listed and not a bare member of the ambiguous class (S4), save a member another chunk settles (below), a chunk's own periods counting as they do in a word of its own. One chunk that does not count leaves the word as it would be without this bullet, and a joiner standing alone or glued to one side joins nothing, as do the dash characters other than the hyphen-minus and a split credential's halves (`MD/Ph. D.`).
  ```
  "John Smith, MD/PhD"        →  suffix="MD/PhD"
  "John Smith MD-PhD"         →  suffix="MD-PhD"
  "Smith, John MD/PhD"        →  suffix="MD/PhD"
  ", MD/PhD"                  →  suffix="MD/PhD"
  "John Smith, M.D./Ph.D."    →  suffix="M.D./Ph.D."
  "john smith, ms-pt"         →  suffix="ms-pt"
  "John Smith, PhD-Md"        →  suffix="PhD-Md"
  "John Smith, md-phd"        →  suffix="md-phd"
  "John Smith-Jones, MD-PhD"  →  family="Smith-Jones"
  "John Smith-Jones"          →  family="Smith-Jones"  · boundary
  "Smith, Mary-Jane"          →  given="Mary-Jane"  · boundary
  "John Smith MD-Jones"       →  family="MD-Jones"  · boundary
  ```
- **A run of chunks the vocabulary lists whole, its slash or hyphen included, is one credential**: the word reads as a suffix where it can be cut at some of its joiners, slashes and hyphens alike, into chunks that each count, a run the vocabulary lists whole counting as one chunk, so a listed `NP-C` or `OTR/L` inside a longer word is asked what it is asked written alone, whichever joiner stands beside it. A word with no such cut, a chunk neither listed nor made of listed pieces, still refuses it, and a word written as a hyphenated name is read by its writing before any cut.
  ```
  "Jane Smith PhD/NP-C"       →  suffix="PhD/NP-C"
  "Jane Smith, PhD/NP-C"      →  suffix="PhD/NP-C"
  "Jane Smith (PhD/NP-C)"     →  suffix="PhD/NP-C"
  "Smith, Jane PhD/NP-C"      →  suffix="PhD/NP-C"
  "Jane Smith MS/CCC-A"       →  suffix="MS/CCC-A"
  "Jane Smith CCC-SLP/L"      →  suffix="CCC-SLP/L"
  "Jane Smith MS/OTR/L"       →  suffix="MS/OTR/L"
  "Jane Smith CCC/SLP/L"      →  suffix="CCC/SLP/L"
  "Jane Smith MS-OTR/L"       →  suffix="MS-OTR/L"
  "Jane Smith APRN-FNP-C"     →  suffix="APRN-FNP-C"
  "Jane Smith CPNP-PC/AC"     →  family="CPNP-PC/AC"  · boundary
  "Jane Smith OTR/L/X"        →  family="OTR/L/X"  · boundary
  "Jane Smith-NP-C"           →  family="Smith-NP-C"  · boundary
  ```
- **A member of the ambiguous class (S4) is a chunk too, however it is written, where the word holds a chunk that settles it**: a credential that is no name, or a member written with a period inside it, and not a generation, a numeral, an honorific or a word that is a title too, which say nothing about the member, as in a clause (S1), nor a member's case, which a chunk cannot be read by. Written alone, such a member may be a name or the initials it looks like (`John Smith MA` and `John Smith M.A` keep the family), but a credential joined to it says what the whole word is, since nobody joins a name or initials to a credential. A word of bare members alone has nothing to settle it, and a name word beside a member still refuses the word.
  ```
  "John Smith MA/PhD"         →  suffix="MA/PhD"
  "John Smith M.A/PhD"        →  suffix="M.A/PhD"
  "Smith, John MA/PhD"        →  suffix="MA/PhD"
  "John Smith, MA/PhD"        →  suffix="MA/PhD"
  "Jane Smith MA/CCC-SLP"     →  suffix="MA/CCC-SLP"
  "Jane Smith MA-CCC-SLP"     →  suffix="MA-CCC-SLP"
  "Jane Smith SLP-M.A"        →  suffix="SLP-M.A"
  "John Smith J.D/MBA"        →  suffix="J.D/MBA"
  "John Smith MA/MBA"         →  family="MA/MBA"  · boundary
  "John Smith MA/Jr"          →  family="MA/Jr"  · boundary
  "John Smith Ma/Ms"          →  family="Ma/Ms"  · boundary
  "John Smith MA/Jones"       →  family="MA/Jones"  · boundary
  ```
- **A joined word holding a member is a member itself** in brackets or quotes: the chunk beside the member has settled it, whatever the name's case, and S13's position decides the rest, so after the name it is the suffix, and inside the name or before it the nickname, reported, as its words written apart are (S1).
  ```
  "John Smith (MA/PhD)"       →  suffix="MA/PhD"
  "John Smith (M.A/PhD)"      →  suffix="M.A/PhD"
  "JOHN SMITH (MA/PHD)"       →  suffix="MA/PHD"
  "John (MA/PhD) Smith"       →  nickname="MA/PhD"
  "John (MA/PhD) Smith"       →  ambiguities=("suffix-or-nickname",)
  "John (M.A/PhD) Smith"      →  nickname="M.A/PhD"
  "John (MBA, PhD) Smith"     →  nickname="MBA, PhD"
  ```

**Because:** credentials are often written run together, with periods between their parts or a hyphen or a slash between two of them, and the chunks are what carry the vocabulary. A word of several chunks that no vocabulary knows is still written the way a credential is written. An acronym that is also an ordinary name is unmistakably a credential when its periods are written.

```
"John Smith Msc.Ed."        →  suffix="Msc.Ed."
"Doe, John Msc.Ed."         →  suffix="Msc.Ed."
"John Smith Msc.Ed."  unlisted_dotted_suffixes-off  →  suffix="Msc.Ed."
"Jack Ma."                  →  family="Ma."  · boundary
"John Smith Xyz."           →  family="Xyz."  · boundary
"Ram Bahadur PhD B.K."      →  suffix="PhD B.K."
"สมชาย ใจดี พ.บ."             →  suffix="พ.บ."
```

**Except:**

- **A word joined by a hyphen and written the way a hyphenated name is, its first chunk in Title case and every other in Title case or lower case, is a name word**, whatever its chunks are listed as: that is how a hyphenated given name is written (`Ae-Ra`, `Ae-ra`, the Korean syllables `ae` and `ra` both being listed credentials), and a credential's chunks are written otherwise. A chunk with a capital past its first letter (`PhD`), a chunk in capitals, a word opening in lower case and a slash anywhere in the word, a slash joining no name, leave the word to the joined reading's every-chunk test, and a word holding an interior period is read by its periods first.
  ```
  "Kim, Ae-Ra"                →  given="Ae-Ra"
  "Shin Ae-ra"                →  family="Ae-ra"
  "John Smith, Md-Rn"         →  given="Md-Rn"
  ```
- **Every chunk the vocabulary matches is a single ASCII character**, the roman numerals and the lone digit the vocabulary lists, which are about generations rather than credentials: those chunks do not make the word a suffix.
  ```
  "Jack X.Y.I."               →  family="X.Y.I."  · boundary
  "Jack I-V"                  →  family="I-V"  · boundary
  "Jack I.-V."                →  family="I.-V."  · boundary
  "John Smith, MS-V"          →  suffix="MS-V"
  ```
- **Paired initials are the exception**, as C5 defines them, in a script that writes capitals: where S4 would count words to spare for them they are the name word they are written as, as the switch off reads every such word, and the fork is still reported. Two dotted single letters is how initials are written in such a script, and how some surnames are (Nepali B.K., K.C.), while a script without capitals writes its abbreviations that way, degrees among them; behind an unambiguous suffix word the pair joins the credential run that word starts (S8).
  ```
  "Ram Bahadur B.K."          →  family="B.K."
  "Ram Bahadur B.K."          →  middle="Bahadur"
  "Sita Kumari K.C"           →  family="K.C"
  "RAM BAHADUR B.K."          →  family="B.K."
  "Bahadur, Ram B.K."         →  middle="B.K."
  "Ram Bahadur B.K., PhD"     →  family="B.K."
  "Jane Doe nee Smith B.K."   →  maiden="Smith B.K."
  ```
- **A word with interior periods that the vocabulary does not list whole, and any of whose chunks is title vocabulary, is a title** where a title stands before the name or after a comma, and ending the name or the given part after a family comma where it ends in a period or every chunk is a title (H5), its title chunks read before its suffix chunks, so a degree written joined to its field (`Dipl.Ing.`, `Dipl.-Psych.`) reads as the title its first chunk is, the field's own chunk a credential or no word; a word listed whole, its periods removed, is read as its listing, title chunk or not.
  ```
  "John Smith, Dipl.Ing."     →  title="Dipl.Ing."
  "Maxie Bunz, Dipl.Psych."   →  title="Dipl.Psych."
  "Dipl.-Kfm. Dalimil Ospalý" →  title="Dipl.-Kfm."
  "John Smith Dipl.Ing."      →  title="Dipl.Ing."
  "Smith, John Dipl.Ing."     →  title="Dipl.Ing."
  "John Smith, Dr.PH"         →  suffix="Dr.PH"  · boundary
  ```
- **The position reading is a caller switch, ON by default**, and the example lines name it; turned off, such a word is name material and the chunk rule still decides the rest.
  ```
  "John Smith X.Y.Z."  unlisted_dotted_suffixes-off  →  family="X.Y.Z."
  ```

**Precedence:**

- **A joined word in capitals with a chunk the stricter test refuses** ("John Smith, MA/MBA"): S9's caps shape reads it, as it reads any unlisted word written in capitals, so after a comma where the name carries C6's case contrast it joins the ambiguous class, where the same word with a lowercase letter stays the name word this rule leaves it.
  ```
  "John Smith, MA/MBA"        →  suffix="MA/MBA"
  ```
- **An ambiguous credential between an unambiguous one and paired initials** ("Jane Doe PhD MA R.T."): the unambiguous word starts the run and the run takes both, the pair included (S8).
- **An ambiguous credential its capitals settle, in front of paired initials** ("Jane Doe MA R.T."): it starts the run as an unambiguous one does, and the run takes the pair (S6, S8).
  ```
  "Jane Doe MA R.T."          →  suffix="MA R.T."
  ```
- **Paired initials at the first slot after a comma** ("García Márquez, G.J."): they read as the given name unless something in the part speaks for them (C5).
- **A flip to the credential run at the first slot after a comma** ("John Smith, X.Y.Z."): where no listed member of the class takes part it is not reported, unless paired initials speak only for each other (C11).

**Accepted:**

- A joined word of nothing but bare members of the ambiguous class, one written with a lowercase letter among them, keeps the reading it had before joined chunks were read, where a name in front of a comma is reversed: no chunk settles the others, and each may be a name.
  ```
  "John Smith, MA/Mba"        →  given="MA/Mba"
  "John Smith, MA/Mba"        →  family="John Smith"
  ```
- A joined word of members alone in brackets after the name stays the nickname, where its words written apart are the suffix when the name's case settles each of them (S13): a joined chunk is never read by its case.
  ```
  "John Smith (MA/MBA)"       →  nickname="MA/MBA"
  "John Smith (MA, MBA)"      →  suffix="MA, MBA"
  ```
- A Korean given name romanized with a hyphen between two syllables the vocabulary lists as credentials, one of them no name and no title, written in capitals or opening in lower case, reads as the credential, unreported after a comma: a name in capitals has no Title case for the writing to show, and `ae` and `ra` are such credentials, `ae` settling `ma`, a member, beside it.
  ```
  "KIM, AE-RA"                →  suffix="AE-RA"
  "KIM, MA-AE"                →  suffix="MA-AE"
  "Kim, AE-RA"                →  suffix="AE-RA"
  "kim, ae-ra"                →  suffix="ae-ra"
  ```
- A credential whose chunks are all typed in Title case reads as the name word its writing shows, since the writing is the cue and it cannot tell the two apart; after a comma the name is reversed around it.
  ```
  "John Smith, Phd-Md"        →  given="Phd-Md"
  ```
- An unlisted credential of two letters written with its periods behind a full name reads as the family name, and the reading is reported: King's Counsel, which the vocabulary lists only as the bare word, is the case, the dotted pair being the Nepali surname too (S11).
  ```
  "John Smith K.C."           →  family="K.C."
  ```
- Paired initials behind an ambiguous credential that no unambiguous suffix word stands in front of, a listed one or one admitted by its shape (this rule's dotted words, S9's capitals where the caller admits them), and whose own writing does not settle it (S6), end the name and take the credential into it: the reading 1.4.0 through 2.3.0 gave, where a run of credentials is the likelier writing.
  ```
  "Jane Doe Ma R.T."          →  family="R.T."
  "Jane Doe Ma R.T."          →  middle="Doe Ma"
  "JANE DOE MA R.T."          →  family="R.T."
  ```
- A word with interior periods and a title chunk that the vocabulary does not list whole, standing inside a name or ending one without a period of its own, reads as a name word: the suffix reading has given way to the title, and the trailing title run (H5) takes such a word without a final period only where the vocabulary lists it whole or every chunk is a title, so at the end of a name the surname before it reads as a middle name.
  ```
  "John Dipl.Ing. Smith"      →  middle="Dipl.Ing."
  "John Smith Dr.PhD"         →  family="Dr.PhD"
  "John Smith Dr.PhD"         →  middle="Smith"
  ```
- A credential written with periods between chunks the vocabulary does not list, single letters or an unlisted abbreviation beside a listed one, is read by position, as the shape is, though one listed chunk would say it is a credential: after a family comma it is the given name, reported, as a name glued to a credential by a period is.
  ```
  "Whinnett, BM.BS"           →  given="BM.BS"
  "Whinnett, BM.BS"           →  ambiguities=("suffix-or-name",)
  ```
- The title chunk is any title, so the readings it gives beyond the degrees are its too: a credential run whose one title chunk is a title that is also a credential (`ms`, `sr`, `lt`) reads as a title, and so does a given name glued to Saint, with no given name left.
  ```
  "Jane Roe, MD.MS"           →  title="MD.MS"
  "St.John Smith"             →  title="St.John"
  ```
- The initialless-script clause carries no example line of its own. Every input that exercises it composes a script that writes no abbreviations with a period that only a Latin convention writes — `John Smith 田.中.` is the shape — and a composed form no writing system produces is tolerated input rather than contract, which an example of a normative rule would promise. So the witnesses are the tolerated row tests/v2/cases.py's an_initialless_script_glued_into_periods_is_not_this_shape and the CJK assertions in tests/v2/pipeline/test_vocab.py's test_period_joined_vocab_retires_the_single_character_chunk. W3 states the same precedence for the same reason.

---
**Signal:** shape: a word in chunks joined by interior periods, a hyphen or a slash, read by its chunks or as the acronym its letters spell, for paired initials whether its script writes capitals, and for a hyphen-joined word whether it is written as a hyphenated name is
**history:** decisions/S3 · **implemented:** nameparser/_pipeline/_classify.py, nameparser/_pipeline/_comma.py, nameparser/_pipeline/_pieces.py, nameparser/_pipeline/_vocab.py
