# W4 — script-scoped order

W4. Rationale: Chinese, Japanese and Korean all write the family
    name first in native script — the script settles the order
    without knowing the language — while a wholly-katakana name may
    be a transcribed foreign name already in its source order or a
    Japanese reading written family-first, so its script settles
    nothing.
    A name written wholly in one East Asian script, or in the
    kana-licensed Japanese repertoire, reads family-first whatever
    order the caller declared; a wholly-katakana name keeps the
    declared order.
      "김 민준"                   →  family="김"
      "山田 太郎"                 →  family="山田"
      "高橋 みなみ"               →  family="高橋"
      "山田 ﾀﾛｳ"                  →  family="山田"
      "マイケル ジャクソン"        →  given="マイケル"  · boundary
      "ﾔﾏﾀﾞ ﾀﾛｳ"                  →  given="ﾔﾏﾀﾞ"  · boundary
      "ア゙イ タロウ"                 →  given="ア\u3099イ"  · boundary
    Accepted: a name the interpunct divides keeps the declared order
    — the divider itself marks a transcription (T3) — so the override
    stands down there, and the name reads as a wholly-katakana one
    does: in its written order by default, reversed by a declared
    family-first order like any other name; the katakana middle dot
    (T2) carries no such signal, so a name it divides still reads by
    the script license.
      "毛·泽东"                   →  given="毛"
      "威廉·莎士比亚"  family-first  →  family="威廉"
      "威廉・莎士比亚"            →  family="威廉"
    history: decisions/W4 · interacts: T3 · implemented: nameparser/_pipeline/_assign.py

