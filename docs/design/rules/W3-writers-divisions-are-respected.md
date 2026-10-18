# W3 — the writer's divisions are respected

W3. Rationale: a family name declared by a comma is the writer's
    own division, and re-dividing it would invent a boundary nobody
    drew — but none of the East Asian writing systems declares a
    family name that way (the Background above), so every input this
    rule reads is a listing convention wrapped around a name whose
    own script has already arranged it — the comma that declares the
    family name, and the punctuation such a listing carries in with
    it. What follows describes what the parser does with such input;
    it does not promise it.
    Under a family comma the pre-comma text is the family by
    declaration and never divides, and the post-comma side is given
    text with no family to find. A title run opening the pre-comma
    text is H6's title, not family text. Only the honorific
    split-off (W2)
    crosses the comma, an honorific being no part of the name on
    either side — the crossing is stated here rather than in W2
    because it is a claim about the comma, and the comma is the part
    nobody's writing system produces. Behind a part C1 reads as
    postnominal there is no family comma, and the name before it
    divides as it would with no comma ('마틴 킹, MA' as '마틴 킹');
    the division, and with it the split-off below, follows C1's own
    reading of the comma, taken on the name as written before the
    division ('Dr 김민준, MA' divides as 'Dr 김민준' does). Which side
    the split-off takes
    it from is decided by the SHAPE of the part after the comma, not
    by which of C1's two readings that part selects — a one-word
    family reads the listing form either way. A part that is nothing
    but suffix words is not the name's end: it is declined as the
    site, and the split-off falls back to the part before the comma
    and takes the honorific there, provided that part offers a site
    of its own. Any other part — a title, a name word — IS the
    name's end, and a glued honorific before the comma stays glued.
    The vocabulary question is C1's own, asked without C1's
    word-count condition: the two differ in what else they require,
    not in what they ask of the words — the written-case evidence
    S2 reads included, so a post-comma acronym the case leans
    credential declines the side it stands on here exactly as it
    reads as the credential there, and the honorific comes off the
    part before the comma as it does behind a settled credential.
    A period the listing leaves
    behind is not what licenses the step past a post-nominal word,
    and it is not ignored either. The step is W2's, taken on the
    vocabulary alone and taken with no punctuation anywhere in the
    input; a period on a SEPARATE post-nominal word rides along into
    the suffix and moves no division (田中さん 様. divides where
    田中さん 様 does). A period glued to the honorific's OWN word
    rides with the honorific: the split-off matches the listed tail
    through it and cuts before it, so 田中さん. and 김민준씨. divide
    where 田中さん and 김민준씨 do (#323; until 2026-09-10 each read
    as a title, measured 2026-09-05 and pinned by nothing, which is
    why the move was free), and a period-marked Han opener divides
    as its stop-less spelling does, 田中. 太郎 reading family-first
    — the reading H2's Accepted clause vetoes a title into, carried
    here because an edge full stop makes it tolerated input like the
    rest of this block. All three are case rows now, tolerated, and
    the sentence reports them rather than promising them, even by
    this rule's standard.
    decisions/cjk-comma-demotion carries the parses.
      "남궁민수"                  →  family="남궁"
      "지훈, 남궁민수"            →  given="남궁민수"
      "남궁민수, 지훈"            →  family="남궁민수"  · boundary
      "田中さん, Dr."             →  family="田中さん"
      "田中さん, PhD"             →  suffix="さん, PhD"
      "Kim김민준씨, MA"           →  suffix="씨, MA"
      "田中さん 様."              →  suffix="さん 様."
      "김민준씨."                 →  suffix="씨."
      "田中. 太郎"                →  family="田中."
    tolerated: native CJK writing has neither a family-comma convention nor an edge full stop of any width on a name word, so the five comma lines above and the three period lines under them illustrate current behavior — changeable without notice — rather than promise it; the line carrying neither, beside them, is W1's claim, which is normative. All eight stay watched by the snapshot (tools/differential/snapshot.jsonl, over corpus_rules.jsonl and corpus_cjk.jsonl), and the `tolerated` rows of tests/v2/cases.py pin them at HEAD.
    history: decisions/W3 · interacts: W1, W2, C1, H2, H6 · implemented: nameparser/_pipeline/_script_segment.py

