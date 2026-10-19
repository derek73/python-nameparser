# C2 — parts past the second comma

C2. Rationale: text beyond the recognized comma parts should be
    taken in without silent guessing.
    Parts beyond the second are consumed as suffixes either way,
    except that a word of the title vocabulary there that is not also
    suffix vocabulary is a title: a part past the second comma holds
    no name word, so the surnames H5 keeps a bare trailing title word
    from misreading are not there to protect, and a piece holding a
    suffix word, a title/suffix dual among them, stays the postnominal
    the slot makes it (#603). A non-empty extra part that
    is not entirely suffix words is flagged as a structural ambiguity
    rather than rejected — parsing never fails on content — unless
    its words are title words and suffix words, one title word at
    least, a word whose period-joined chunks read as a title
    ('Lt.Gov.') counting as one. That is asked word by word, so a part
    a connective joins into one title ('Secretary of State') keeps
    the flag. An empty
    part between doubled commas is consumed silently.
    A part the parse reads as a credential run by some route other
    than the suffix vocabulary is recognized and is not flagged: a
    run of ambiguous acronyms whose written case leans credential
    (S6), and a run every word of which is an unlisted DOTTED word
    the position reads as a credential (S3). This is the one place
    the ambiguous class QUIETS a report rather than adding one, and
    it is narrow in two ways that the examples below pin. A member
    whose written case does not lean CREDENTIAL keeps the flag,
    whether the name is written in one case so that nothing leans at
    all, or the member is written the way a name is written. And
    S9's other by-shape half, the unlisted all-caps word, does not
    reach here in any setting: the shape a tail segment is
    recognized by is the dotted one alone.
    A part the parse consumes wholly as suffixes raises no report
    that a word of it was read as a name, whether it is the part
    after a suffix comma (C1) or a part beyond the second: nothing
    in it is read as one, a maiden marker there being an ordinary
    word (M2), and no particle chain (P2) is made in it, so a title
    word behind a particle run there is a title like any other, and
    the part reports neither a particle chained onto a name word nor
    an acronym taken into the name. What such a part reports is its
    own — C11's report of the decision at its comma (the flip, or the
    first word after the comma), S8's and S7's reports on each word a credential
    in front of it reads as a suffix although it may be a name word (a
    name word the run absorbs, a member the company decides), and this
    rule's flag.
      "John Smith, MD, Bart"      →  suffix="MD, Bart"
      "Eric H. Holder, Jr., Attorney General"  →  title="Attorney General"
      "Eric H. Holder, Jr., Attorney General"  →  ambiguities=()
      "Eric H. Holder, Jr., Secretary of State"  →  ambiguities=("comma-structure",)  · boundary
      "Smith, John, Prof."        →  title="Prof."
      "John Smith, Jr., van der Berg Prof."  →  title="Prof."
      "John Smith, Jr., van der Berg Prof."  →  suffix="Jr., van der Berg"
      "John Smith, Jr., Lt.Gov."  →  ambiguities=()
      "John Smith, MD, Ms"        →  suffix="MD, Ms"  · boundary
      "John Smith, MD,, Jr."      →  suffix="MD, Jr."  · boundary
      "John Smith, MD, R.A.I."    →  suffix="MD, R.A.I."
      "John Smith, MD, R.A.I."    →  ambiguities=()
      "John Smith, MD, R.A.I."  unlisted_dotted_suffixes-off  →  ambiguities=("comma-structure",)
      "John Smith, MD, Ma"        →  ambiguities=("comma-structure",)  · boundary
      "Steven Hardman, MD, DO, DDS"  →  ambiguities=()
      "STEVEN HARDMAN, MD, DO, DDS"  →  ambiguities=("comma-structure",)  · boundary
      "John Smith, MD, XYZ"  unlisted_caps_suffixes-everywhere  →  ambiguities=("comma-structure",)
    Accepted: the no-name-reading clause's REPORT half carries no
    example line of its own. What it moves is a report with no field
    beside it, and an example line would promise that report alone;
    its title half is witnessed by the two `John
    Smith, Jr., van der Berg Prof.` lines above, and its report half's
    executable witnesses are the case rows
    a_credential_run_after_the_comma_reports_no_chain_fork and
    a_part_past_the_second_reports_no_particle_fork in
    tests/v2/cases.py, read beside the two rows the chain still
    reports on outside a tail:
    the_chain_reports_the_acronym_it_takes and
    titled_particle_chain_survives_a_title_that_is_also_a_particle.
    Signal: a position: a part past the second comma
    history: decisions/C7, decisions/C8, decisions/C11, decisions/S6, decisions/S9 · interacts: C1, C7, C8, C11, H5, P2, P5, S3, S6, S8, S9 · implemented: nameparser/_pipeline/_segment.py, nameparser/_pipeline/_assign.py, nameparser/_pipeline/_group.py

