# M2 — the maiden-marker rule

M2. Rationale: a maiden marker announces that what follows it is the
    former family name; the marker is an announcement, not a name.
    A recognized maiden marker counts only in the part of the name
    that holds the family name — the whole name where no comma
    divides it or before a suffix comma, the part before a family
    comma — and only with a
    name word straight before it. A word of the leading title run is
    no name word there, a lone title included; neither is a word of
    the unambiguous suffix vocabulary, unless it opens the name (S2),
    nor a connective. A particle
    is one: with nothing after it to attach to, it is no particle
    there. In the given part after a family comma, in a part after a
    suffix comma, and behind a title, a suffix word or a connective,
    the marker is an ordinary word; a name standing somewhere before
    it is not enough.
    A marker that counts takes the words after it as the maiden name,
    and is itself dropped. It takes them up to the trailing run of
    post-nominals and titles that the end of the name reads as if the
    clause were not written — the trailing rules (S2, H5) asked over
    the words before the marker and the post-nominal or title words
    that end it, before any join — and always takes the first word
    after it, the marker having announced a name. A suffix word
    straight after the marker announces nothing, and the marker is
    then a word. The run so found ends the name: its words are the
    suffixes and titles that reading makes them, and no join reaches
    into it. Before a family comma no trailing rule reads the part, so
    the clause ends at the first suffix word, and the words from it
    on read as that part reads them.
    Where a trailing rule reads the part, a member of the ambiguous
    class (S4) that ends the maiden name is reported where the clause
    keeps it, and one in the run is reported where the run is read,
    so no word is reported twice and none goes unreported. Before a
    family comma no rule reads it, and the member the clause keeps
    there is reported nowhere.
    Delimiters outrank every reading inside them. Where a recognized
    marker stands inside a delimited clause, the whole span is the
    maiden name whatever its last word is, and whether or not the
    pair is a configured maiden delimiter (M3): the writer drew the
    boundary, so no fork is called and nothing is reported. A word
    the writer left OUTSIDE the span is outside the clause and reads
    as it would anywhere else. Bracketed content ending in a period
    is the exception, because it never reaches this rule as a
    delimited clause: a trailing period makes the content
    suffix-shaped (M3 states this), so the brackets are dropped (S1)
    and the clause is read as if written bare.
    A marker
    with nothing after it, or nothing before it, is just a word.
    A marker may be more than one word, and is then recognized only
    whole and only where its words stand together: its own first word
    standing without the rest is not that marker, and neither is one
    the writer divided from the rest by a bracketed clause or by a
    comma. Whether the first word takes anything on its own is a
    separate question with a separate answer — it does exactly when it
    is a recognized marker in its own right, and the longer entry wins
    wherever both could match.
    A marker taken this way also bounds a particle join arriving from
    its left (P2), so the family name's particles stop at the marker
    instead of absorbing it; a marker left as a word bounds nothing.
    Where the bound leaves a family of nothing but particles, they
    are not in particle position and read as ordinary words (R2).
      "Jane Smith née Jones"        →  maiden="Jones"
      "Maria López née García Pérez"  →  maiden="García Pérez"
      "Jane Smith née Jones PhD"    →  suffix="PhD"
      "Jane Doe née Jones Smith V"  →  maiden="Jones Smith"
      "Jane Doe née Jones Smith V"  →  suffix="V"
      "John née Jones Smith V"      →  maiden="Jones Smith V"  · boundary
      "Doe nee Smith, Jane"         →  maiden="Smith"
      "Doe, Jane nee Smith"         →  maiden=""
      "Doe, Jane nee Smith"         →  middle="nee Smith"
      "Jane Smith, née Jones"       →  maiden=""
      "Smith, John, PhD née Jones"  →  maiden=""
      "Jane Doe PhD nee Smith"      →  maiden=""
      "Jane and née Jones"          →  maiden=""
      "Dr. nee Smith PhD Prof."     →  maiden=""  · boundary
      "Dr. nee Smith PhD Prof."     →  family="Smith"  · boundary
      "Mai Le née Nguyen"           →  maiden="Nguyen"
      "abd née Jones"               →  maiden="Jones"
      "Jane née Jr y Jones"         →  maiden=""
      "Jane Doe nee Smith MA"       →  maiden="Smith"
      "Jane Doe nee Smith MA"       →  suffix="MA"
      "Jane Doe nee Smith Ma"       →  maiden="Smith Ma"  · boundary
      "Jane Doe nee MA"             →  maiden="MA"  · boundary
      "Jane Doe nee MA Smith"       →  maiden="MA Smith"  · boundary
      "John née Jones Smith Ma"     →  maiden="Jones Smith Ma"
      "John nee Prof. ba MA"        →  maiden="Prof. ba"  · boundary
      "Jane Doe nee Puig i Soler"   →  maiden="Puig i Soler"
      "Jane Doe nee Puig i"         →  maiden="Puig"  · boundary
      "Jane Doe nee Puig i"         →  suffix="i"  · boundary
      "Jane Doe nee Smith Prof."    →  maiden="Smith"
      "Jane Doe nee Smith Prof."    →  title="Prof."
      "Jane Doe nee Smith MA Prof."  →  suffix="MA"
      "Jane Doe nee Smith Prof. MA"  →  maiden="Smith"
      "Jane Doe nee Smith V Prof."  →  suffix="V"
      "Jane Doe nee Smith VI Prof." →  suffix="VI"
      "Jane Doe nee King."          →  maiden="King."  · boundary
      "Jane Doe nee Prof. Dr."      →  maiden="Prof."  · boundary
      "Jane van der Berg nee Smith Prof."  →  title="Prof."
      "Jane van der Berg nee Prof. King. MA"  →  maiden="Prof."  · boundary
      "Jane Doe nee Smith PhD Smith"  →  maiden="Smith"
      "Jane Doe nee Smith PhD Smith"  →  suffix="PhD Smith"
      "Doe nee Smith Jr. Prof., Jane"  →  family="Doe Prof."  · boundary
      "Jane Doe (nee Smith MA)"     →  maiden="Smith MA"
      "Jane Doe (nee Smith Ma)"     →  maiden="Smith Ma"
      "Jane Doe (nee Smith) MA"     →  suffix="MA"
      "Jones née"                   →  family="née"  · boundary
      "née Jones"                   →  family="Jones"  · boundary
      "Jane van der Berg née Jones"  →  maiden="Jones"
      "Jane de la née Jones"        →  maiden="Jones"
      "Jane de la née Jones"        →  family="de la"
      "Jane van der Berg née"       →  family="van der Berg née"
      "Jane van der Berg née PhD"   →  family="van der Berg née"
      "Jane van der Berg née y Jones"  →  maiden="y Jones"
      "Maria Kowalska z domu Nowak"  →  maiden="Nowak"
      "Anna z Nowak"                →  family="Nowak"  · boundary
      "Anna z (domu) Nowak"         →  family="Nowak"  · boundary
    Accepted: the fullwidth-colon spelling arrives as one word, so
    the marker inside it goes unrecognized; #317 tracks whether it
    should peel.
      "山田 花子 旧姓：佐藤"                 →  maiden=""
    Accepted: a given name with no current surname beside a maiden
    name reads by M4's lone-word rule, the lone name word before the
    marker being the family. A writer giving a given name with its
    birth name writes the clause delimited.
      "Jane née Jones Smith"        →  maiden="Jones Smith"  · boundary
    Accepted: the run is what the trailing rules read, before any
    join — not the whole reading of the clause-free name. Where a
    particle chain would take the words of the run in that name, the
    run keeps them suffixes and titles.
      "Jane Doe nee Smith DO DO"    →  suffix="DO DO"  · boundary
    Accepted: the first word after the marker is the maiden name
    whatever it is unless it is a suffix word, and a lone roman
    numeral is not one — it is shaped like an initial — so it is the
    maiden name where the clause-free name would read it as the
    suffix. Decided with #601 (decisions/M2, 2026-10-04).
      "Jane Smith née V"            →  maiden="V"  · boundary
    Accepted: bracket content ending in a period is suffix-shaped
    (M3), so the brackets are dropped (S1) and the clause is read as
    if written bare — the delimiter precedence above does not reach
    it.
      "Jane Doe (nee Smith Prof.)"  →  title="Prof."
    Accepted: a marker behind a credential is an ordinary word, and
    the credential's run (S8) takes it in with everything after it.
      "Jane Doe Jr. nee Smith"      →  suffix="Jr. nee Smith"  · boundary
    history: decisions/M2 · interacts: P2, P3, P5, P6, R1, R2, M1, S1, S2, H1, H5, C1, C10, S4, S8 · implemented: nameparser/_pipeline/_group.py, nameparser/_pipeline/_pieces.py

