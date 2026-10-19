# C10 — a declared delimiter parts a trailing suffix part

C10. Rationale: a caller who declares a suffix delimiter means it to
    separate suffixes as a comma does, and the simplest reading that
    honours that is one where it is a comma there.
    A delimiter the policy declares parts a trailing suffix part as a
    comma would: the words on each side of it read exactly as the
    parts of the same text written with a comma in its place, so no
    join, maiden clause or connective reaches across it, and the
    delimiter itself is dropped, unless it stands alone as the whole
    of its part. Only a trailing part is parted: in the part before
    the first comma, or in the given part of the listing form, the
    delimiter is a word (the Accepted entry below).
      "Smith, John, Puig - i Soler" extra_suffix_delimiters-dash →  suffix="Puig, i Soler"
      "Smith, John, PhD - and MD" extra_suffix_delimiters-dash →  suffix="PhD, and MD"
    Accepted: a maiden marker in a part a declared delimiter
    separates takes no clause, as no marker in a part after a suffix
    comma does, the marker being an ordinary word there (M2).
    Releases 2.0 through 2.3 read past the delimiter and took the
    clause; the comma reading is accepted as the cost of one rule
    for a declared separator.
      "Smith, John, MD - née Jones Smith" extra_suffix_delimiters-dash →  suffix="MD, née Jones Smith"
    Accepted: a delimiter core the policy names (T1) is a word here,
    not structure — v1 applied the delimiter to the suffix-comma
    form alone, and that limitation is kept as parity: the core in
    'Smith, RN - CRNA' is a word under the policy as without it.
    Since #603 it is a word of the run the credential opens, so the
    part reads suffix "RN - CRNA" where 2.0 through 2.3, like v1,
    read given "RN".
      "Smith, RN - CRNA"          →  suffix="RN - CRNA"
      "Smith, RN - CRNA" extra_suffix_delimiters-dash →  suffix="RN - CRNA"  · boundary
    history: decisions/C10 · interacts: C1, C2, C8, M2, T1 · implemented: nameparser/_pipeline/_comma.py, nameparser/_pipeline/_group.py
