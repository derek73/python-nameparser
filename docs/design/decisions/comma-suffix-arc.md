# comma-suffix-arc — #291/#296/#316 (2026-07-26 → 2026-08-01)

#291 was filed 2026-07-26 out of the 2.0 vocabulary cleanup, with
its decline-by-measurement evidence in the issue body; "z domu" folded into it 2026-07-27 (see Excluded, MAIDEN_MARKERS). Intent for #291 and #296 is settled by the approved bundle spec; #296 (with #325) SHIPPED 2026-08-23 as the bundle's first three commits, with one deviation from the audit table recorded at decisions/C8 ('md' keeps dual membership — bare 'Md' is Muhammad); #291 was UNSHIPPED then, carried as a deviates: marker on C1 (#291 closed 2026-08-24; the marker came off with #564 in 2.4). The arc's bookkeeping: #291/#296 moved milestone v2.1 → v2.2 on 2026-08-01 (with #289/#293); the 2026-07-30 design doc was amended in place 2026-08-01 (A1–A6); its durable content is HERE rather than in the gitignored doc; #316 (trailing titles) was filed the same day, carrying the esq cleanup as a Related section.

## Standing

- The multi-word suffix entries v1 shipped unmatchable were removed in 2.0 rather than split into single-word entries, which would cost `Smith, A.P.` its given initials and `John Leed` and `Mary Nicet` their family names, all three reading as before today — 2026-07-26 #291.
- A multi-word credential is reached from its component words by the run predicate, so the shipped vocabulary carries no phrase entries and a caller adds a missing component word to a `Lexicon`: `John Smith, MD PhD` → suffix 'MD PhD', `John Smith, PSM I` → suffix 'PSM I'. `SUFFIX_PHRASES` and segment-level matching are declined, and amendment A6's glued-peel question with them, there being no phrase unit for the peel to step over — 2026-08-23 #291.
- Multi-word vocabulary merges where the render tag is applied, not where the role is assigned, since the suffix view comma-joins suffix words not tagged `joined`: `John Smith, LEED AP` renders suffix 'LEED AP' — 2026-07-26 #291.
- An unlisted abbreviation ending a name gets no structural fallback, the corpora being blind to it, and reads as a name word (`John Smith Xyz.` → family 'Xyz.'); written as two or more dotted chunks it is the exception, S9's shape class (`John Smith X.Y.Z.` → suffix 'X.Y.Z.') — 2026-07-26 #291.

Not standing: plan amendment 1's repair, carried out by #296's first commit and its condition widened from all titles to no name word by the #428 review (decisions/C8) — 2026-08-01.

Elsewhere: the audit table's dispositions as shipped, `md` kept a dual and `ms` and `sa` kept out of the ambiguous set — decisions/C8's 2026-08-23 #296 and 2026-08-23 #428 Standing lines; the trailing slot read by vocabulary, a period-marked title word there a title (`John Smith Prof.` → title 'Prof.') — decisions/H5's 2026-09-08 #316 entry; the dotted shape class — decisions/S9's 2026-09-14 (Derek) entry headed #516's DOTTED HALF IS A SWITCH.

Open: none in this file.

## Log

- 2026-07-26 #291/#296/#316 (its audit table's `ms` and `sa` joining the ambiguous set superseded by decisions/C8's 2026-08-23 (review of PR #428, four reviewers) entry; its trailing-abbreviation decline superseded for the dotted spelling by decisions/S9's 2026-09-14 (Derek) entry headed #516's DOTTED HALF IS A SWITCH) — THE COMMA-SUFFIX ARC, 2026-07-26 → 2026-08-01: the paragraph, the plan amendment and the Declined entries below.

The approved 19-word TITLES∩suffix audit table (2026-07-30/08-01, intent for the unshipped bundle): jr, junior, phd, md, do and se DROP from TITLES (se: Structural Engineer is the PE/SE post-nominal pair, no prenominal convention — v1 residue); dr drops from SUFFIX_WORDS and sra from the suffix sets (v1 residue); sr, lt, cpl, cpt, cpo, csm, sgm, ra and vc KEEP dual membership (position decides); ms and sa keep dual membership AND join the ambiguous set (the periods gate). Derek's framing thesis for the whole table: v1's sets encoded where the v1 PARSER needed words to be, not where words can occur. Amendment A6: once SUFFIX_PHRASES ships, the glued peel's token-level post-nominal test cannot step over a phrase segment ("김민준씨, LEED AP" will not peel) — #291 owns deciding that, with a case row either way.

- 2026-08-01 (plan amendment 1, Derek's call: "ship + repair the merge") — dropping dr/ms from the suffix vocabulary flips segment() to FAMILY_COMMA and degrades "John Smith, Dr." to family="John Smith" (mechanisms.md#VOCABULARY-FEEDS-STRUCTURE is this shape); the approved repair, ordered FIRST in the bundle so no commit introduces a regression a later one heals: assign segment 0 positionally when segment 1 is nothing but titles.

- 2026-08-23 #291 — #291 CLOSED WORKING AS DESIGNED: the `Amended 2026-08-23` paragraph under the first Declined entry below.

Declined:

- Splitting the dead multi-word suffix entries into single-word entries (2026-07-26, the evidence in #291's body) — measured:
  "Smith, A.P." has the suffix steal the given initials; "John
  Leed" and "Mary Nicet" lose family names; and the period-gate escape is equivalent to removal because nobody writes "L.E.E.D.". This decline is why the seven removable entries were REMOVED in 2.0 rather than split, and it is the missing history behind C1's
  #291 marker.

  Amended 2026-08-23 (#291 closed working-as-designed): the decline stands as measured — splitting into single words does cost `Smith, A.P.`, `John Leed` and `Mary Nicet` — but the inference drawn from it did not. "A multi-word *entry* is inert" was read as "a multi-word *credential* is unreachable", and that is false: the run predicate `is_wholly_suffix` reassembles adjacent suffix tokens, so `parse("John Smith, MD PhD").suffix` has been `'MD PhD'` since 1.4.0, and `psm i`/`psm ii` — two of the seven entries called dead — parse today from their component words. The third option neither the issue nor the spec considered is to leave the shipped vocabulary alone and let callers add the component words to a `Lexicon`, which is what was chosen.

  Also declined with it: `SUFFIX_PHRASES` and segment-level matching (unnecessary once the run predicate is measured), and amendment A6's glued-peel question (no phrase-matching unit, so `_is_post_nominal`'s token-level test stays correct by construction).
- The trailing-abbreviation structural fallback — with a measurement LIMIT rather than a measurement: the differential corpora structurally cannot evidence it, because they hold only names someone wrote down, and an unrecognized abbreviation is by definition outside the vocabulary. A green run there proves nothing (the reusable harness fact is in mechanisms.md's field notes).
- SUFFIX_PHRASES matching in assignment — measured cost: it renders suffix="LEED, AP", because the suffix view comma-joins suffix words unless they carry the stable "joined" tag, which grouping applies within a piece and — since #436/#437, 2026-09-06 — post_rules applies between two post-nominals the writer did not comma-separate. The general form: multi-word vocabulary must merge where the render tag is applied, not where the role is assigned.

