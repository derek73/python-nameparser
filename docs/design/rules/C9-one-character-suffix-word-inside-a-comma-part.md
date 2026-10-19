# C9 — a one-character suffix word inside a comma part

C9. Rationale: one letter is the shape a middle initial is written
    in, so only what stands before it says whether it is a
    generation.
    A one-character suffix word — the only kind a reader could take
    for an initial — is read by what stands before it. Behind
    another suffix it is describing that suffix and continues the
    run, written with a period or without, an initial being no shape
    anyone writes there; behind a name word it is the generation
    only when written bare, a period marking it the abbreviation of
    a name and so a middle initial. Both branches then ask that the
    generation slot still be open: where a further comma has already
    named the suffix, a single letter ending the GIVEN part has no
    generation left to be, and stays a middle initial — with a
    period or without, and whether a name word or another suffix
    word stands before it. Only the given part is touched; a part
    after the comma that is nothing but suffix words is the
    credential run, and a letter in it continues that run up to the
    further comma. Longer suffix words are not in question either
    way, and the strict knob (C1) still vetoes the initial-shaped
    ones, so the run ends at them there unless a credential opened
    the part (C8).
      "Smith, PSM I"              →  suffix="PSM I"
      "Smith, PSM I."             →  suffix="PSM I."
      "Smith, John V."            →  middle="V."
      "Smith, John PhD I."        →  suffix="PhD I."
      "Smith, John V"             →  suffix="V"  · boundary
    Accepted: the further-comma qualifier carries no example line of
    its own. It discriminates PAIRS and spans both branches, so
    exemplifying it means a with-comma partner for each — every one
    of them a promise about behavior that has not moved since v1.
    Its executable witness is instead the pair
    already standing in the v1-style bank,
    tests/test_suffixes.py's
    test_roman_numeral_i_after_single_initial_lastname_comma_format
    and test_roman_numeral_i_with_explicit_suffix_comma_stays_a_middle_initial.
    Read the examples above with the qualifier in hand: `Smith, John
    V` reads the suffix and `Smith, John PhD I.` continues the run,
    while adding a suffix comma after either turns that same letter
    into the middle initial.
    history: decisions/C9 · interacts: C1, C8, S5, S10, T4 · implemented: nameparser/_pipeline/_assign.py
