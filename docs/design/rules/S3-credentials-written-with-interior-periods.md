# S3 — credentials written with interior periods

S3. Rationale: credentials are often written run together with
    periods; the chunks between the periods are what carry the
    vocabulary, and a word of several chunks that no vocabulary
    knows is still written the way a credential is written.
    A word with interior periods reads as a suffix when any of its
    period-separated chunks is suffix vocabulary — except where
    every chunk the vocabulary matches is a single ASCII character,
    the roman numerals and the lone digit the vocabulary lists,
    which are about generations rather than credentials.
    A word of two or more period-separated chunks that no
    vocabulary claims is read by POSITION instead, as a bare
    ambiguous acronym is (S4): a credential where the name has words
    to spare, a name word where it does not, either reading
    reported at the slots S4 reports at, and the same at a comma —
    which means the FIRST piece after a family comma, the word
    trailing the given part after one, the word ending a maiden
    marker's clause (M2), and the part before a SUFFIX
    comma. The part before a FAMILY comma never reports, the comma
    having already named it the family. Two exceptions hold at the
    first slot after a comma: paired initials ('M.J.') read as the
    given name unless something in the part speaks for them (C5),
    and a flip to the credential run in which no listed member of
    the class takes part is not reported, unless paired initials
    speak only for each other (C11). Case says nothing here — the
    periods are the evidence — and three shapes are outside it: a
    single trailing period is not this shape at all, a chunk that is
    not wholly alphabetic is no acronym letter, and a word carrying
    a script that writes no abbreviations is not wearing an
    abbreviation's periods (H2 refuses the same word for the same
    reason). This second half is a caller switch, ON by default, and
    the example lines name it; turned off, such a word is name
    material and the chunk rule above still decides the rest.
      "John Smith Msc.Ed."        →  suffix="Msc.Ed."
      "John Smith Msc.Ed."  unlisted_dotted_suffixes-off  →  suffix="Msc.Ed."
      "Doe, John Msc.Ed."         →  suffix="Msc.Ed."
      "John Smith J.u.n.i.o.r."   →  suffix="J.u.n.i.o.r."
      "John Smith Q.W.E.R.T."     →  suffix="Q.W.E.R.T."
      "John Smith X.Y.Z."         →  suffix="X.Y.Z."
      "john smith x.y.z."         →  suffix="x.y.z."
      "John Smith X.Y.Z."  unlisted_dotted_suffixes-off  →  family="X.Y.Z."
      "Jack X.Y.I."               →  family="X.Y.I."  · boundary
      "John Smith Xyz."           →  family="Xyz."  · boundary
      "John Smith 1.4"            →  family="1.4"  · boundary
      "Doe, John X.Y.Z."          →  suffix="X.Y.Z."
      "Jane Doe nee Smith X.Y.Z." →  suffix="X.Y.Z."
    Accepted: the initialless-script clause carries no example line
    of its own. Every input that exercises it composes a script that
    writes no abbreviations with a period that only a Latin
    convention writes — `John Smith 田.中.` is the shape — and a
    composed form no writing system produces is tolerated input
    rather than contract, which an example of a normative rule would
    promise. So the witnesses are the tolerated row
    tests/v2/cases.py's
    an_initialless_script_glued_into_periods_is_not_this_shape and
    the CJK assertions in tests/v2/pipeline/test_vocab.py's
    test_period_joined_vocab_retires_the_single_character_chunk.
    W3 states the same precedence for the same reason.
    Signal: a shape: a word with interior periods, read by its chunks
    history: decisions/S3 · interacts: C4, C5, C11, H2, W3, S4 · implemented: nameparser/_pipeline/_vocab.py

