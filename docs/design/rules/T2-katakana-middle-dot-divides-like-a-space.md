# T2 — the katakana middle dot divides like a space

T2. Rationale: the katakana middle dot exists to divide name parts
    and appears in no native name.
    The katakana middle dot and its halfwidth twin divide a name
    like whitespace, always.
      "マイケル・ジャクソン"        →  given="マイケル"
      "高橋・一郎"                 →  family="高橋"
    no-boundary: the separation is unconditional; the
    context-sensitive interpunct is T3's subject.
    implemented: nameparser/_pipeline/_tokenize.py

