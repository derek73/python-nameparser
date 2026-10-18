# removed-v1-surface

- empty_attribute_default: removed in 2.0 (#255; deprecated in 1.4 per the bridge discipline). Origin #44 (2016): a DB-NULL convenience whose first answer — `name.title or None` — became the migration path. The in-band-signaling bug that sealed it (#254): the 2016 `.replace('None','')` scrub could not tell interpolated None from name text, so "Nonez Smith" rendered
  "z Smith" — the fix shape, worth keeping as a one-liner, is
  SUBSTITUTE BEFORE FORMAT, never scrub after. Two removal cautions shaped the implementation: tombstone-not-deletion (a plain deleted attribute would make assignment silently accepted-and-ignored, the #241 failure family) and readers-not-just-writers (#44's own thread advised asserting against the attribute, so reads existed downstream). The tombstone and pickle-tolerant load die with the shim. (An earlier 3-0-reevaluations bullet said "left untyped, typeable in 3.0" — promoted from a memory that was already three days stale when written; nothing is left to type.)
- bytes input: removed in 2.0 (#245; decode-first DeprecationWarnings shipped 1.3.0 per the bridge discipline); the shipped TypeError carries the decode hint.
- no_vowels: removed in 2.0 (#268, filed 2026-07-07, closed 2026-07-28) — never consulted by any parser version, ASCII-only; the facade carries no replacement because there was nothing to replace.

