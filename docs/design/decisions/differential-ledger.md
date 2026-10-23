# differential-ledger — the differential ledger's arcs

The differential ledgers were the classified gate 2.0 shipped behind: `tools/differential/compare.py` ran every corpus name through a released wheel and through the tree, and every name that read differently had to be claimed by a rule in one `tools/differential/expected_since_<version>.toml` ledger per baseline (a `name_regex`, the `fields` it may move, an issue and a `why`), or the run failed. They proved what they were built to prove, that 2.0 changed nothing against 1.4 except the fixes the release log lists. As a standing check they made every later behavior change classify itself once per ledger, and the guards that policed the ledgers (`tests/v2/test_ledger_guards.py`, the contest pins, the recorded and watched diff rosters) outgrew them. #664 retired them for a committed snapshot on 2026-10-13.

Archived 2026-10-19 under rule 3 of the decisions folder's entry conventions (#759): eleven arcs of entries, about 33,000 words, were cut to the tombstones below, every one superseded by the retirement. The full text is in git — `git show fe85bb3d:docs/design/decisions/differential-ledger.md` — and in the PRs each tombstone names. The retirement entry is the one decision in force and stands in full; the passages other entries cite stand as one line each, and three Declined entries about surviving code stand as written.

## Standing

- `tools/differential/snapshot.jsonl` records every corpus name's reading, one line per (name, order): the seven role fields, the ambiguity kinds, `initials()`, the two case-repair views since #826 (decisions/R4), and what `HumanName` reads differently, under `facade`; `tests/v2/test_snapshot.py` fails on drift and prints the moves grouped by changed field, and a change that moves readings re-records, so the PR diff of the snapshot is the list of names it moved. Nothing is classified, and a reviewer can approve a large diff without reading it, the grouping being the mitigation; the ledgers, their guards and the contract/radar tiers are gone, trimming them having been declined — 2026-10-13 #664, a committed snapshot.
- `compare.py` stays, unclassified: it runs a released wheel against the tree behind the version tell, the tree-side path check and a stripped `PYTHONPATH`, prints the snapshot's grouped report and exits 0. It answers how a release tagged before the snapshot read the corpus names, and the 1.4 promise is a question asked of it (`--baseline 1.4.0`), not a gate; for a later release `snapshot.py --since <tag>` is the cheaper answer — 2026-10-13 #664, `compare.py` stays.
- The CLDR agreement ratchet stays beside the snapshot, answering agreement with a corpus's stated fields rather than stability (`tests/v2/test_cldr_agreement.py`) — 2026-10-13 #664, the CLDR agreement ratchet.
- `Policy`'s fields are annotated with what they store, not widened to every input the constructor accepts, since every reader would see the union; a `.pyi` stub typing `__init__` wide and the attributes narrow is a 3.0 candidate (decisions/3-0-reevaluations) — 2026-07-24 #332.
- The tree side of a comparison must import this checkout's source package, `is_relative_to(<repo> / "nameparser")` and not anywhere under the repository, whose `.venv/`, `build/` and `dist/` can hold a released wheel; `compare.py` asks `snapshot.check_source` for it — 2026-07-24 #332.
- `DEFAULT_BASELINE` rotates at every release as a step of the AGENTS.md release checklist, not as an issue — 2026-07-24 #332.

Open: none in this file.

## Log

### differential-ledger, the arcs before retirement (2026-07-24 to 2026-09-05)

- 2026-07-24 to 2026-08-07, the tooling arc (#332, #333, #334) — harvested 2026-08-15 from the release-arc session; measurements are that session's, spot-checked at landing. The two-corpus design (corpus_issues.jsonl beside the v1-test-bank corpus, since v1 test banks are blind to anything 2.0 added), ledger fields named by `Role`, and the sentinel-set over-match check (mechanisms.md#SENTINEL-SET-OVER-MATCH-CHECK). SUPERSEDED by 2026-10-13 #664 — except three of its Declined entries, below, which are about code and process that survive the ledgers.
- 2026-08, the dormancy arc (#328–#376) — measurements are that session's, the machinery verified present at landing. `[[never]]` exclusions sorted ahead of the rules, so an exclusion only ever removes a name; a rule that claims nothing is dormant and is refused. SUPERSEDED by 2026-10-13 #664 —
- 2026-08-27, the fields-only arc (#451) — `validate_rules` refuses a rule with `fields` and no `name_regex`, the one such rule having drifted from four names to seventeen with every guard green. SUPERSEDED by 2026-10-13 #664 —
- 2026-09-01, the corpus-tier arc (#468/#469) — every corpus carries a tier, and only the contract tier can fail the run. SUPERSEDED by 2026-10-13 #664 —
- 2026-09-01, the initials view (#484/#462) — `_initials` is a pseudo-field on both surfaces that enters a name's diff only when the seven roles and `_ambiguities` agree, so `initials()` is the one render view the gate compares and `capitalized()` stays invisible to it; it found #462 and the 2.0.0 per-word initials change, classified late in the 2.3.0 log. SUPERSEDED by 2026-10-13 #664 — the snapshot records `initials()` for every name. The 2.3.0 release log's per-word initials bullet points here; its evidence (the three clusters, 27 / 14 / 98 names, and the RECOMPUTE) is in the full text at fe85bb3d.
- 2026-09-02, the rule-order arc (#382) — an order-decided contest between two rules must be declared (`precedes_narrower`), narrow-first being the declaration-free default. SUPERSEDED by 2026-10-13 #664 —
- 2026-09-03, the recorded-shapes arc (#497) — the recorded diff shapes live in `compare._RECORDED_DIFFS`, where a run verifies them, and `_CROSS_RULE_WINNERS` keeps only the winner. SUPERSEDED by 2026-10-13 #664 —
- 2026-09-05, the watched-shapes arc (#501) — a shape may be recorded without a winner, in a second roster (`compare._WATCHED_DIFFS`). SUPERSEDED by 2026-10-13 #664 —
- 2026-09-05, the #501 adjudication — a contest row is owed wherever its boundary is argued, the ledger's own comments included. SUPERSEDED by 2026-10-13 #664 —
- 2026-09-05, the #498 completeness check — the declared-contest check extends from nested `fields` to intersecting and equal ones. SUPERSEDED by 2026-10-13 #664 —
- 2026-09-05, a pin names one rule (#508) — a `_CROSS_RULE_WINNERS` pin resolves to exactly one rule's issue and is compared by equality. SUPERSEDED by 2026-10-13 #664 —

Cited elsewhere, kept as one line each:

- The fields-only arc declined extending its rule to `'Donald mc'` (2026-08-27): `mc` is both particle and suffix vocabulary, so the comma-less name loses its family to `suffix` under rules/S2's Accepted clause, and P6's Accepted clause, which claimed the comma-less shapes keep their positional reading, was a rules defect, fixed 2026-09-07 under #454 (decisions/suffix-acronym-collisions).
- The initials view added `initials()` alone, deliberately (2026-09-01 #484); `family_base` was considered as a second derived view and not added.

Declined (the tooling arc's, harvested as above, kept because they are not about the ledgers):

- Policy annotations widened to input unions (2026-08-05 #334) — five documented spellings fail mypy and every one has a type-clean equivalent; widening would make every READER see a union, and reading is the commoner operation. A .pyi stub typing __init__ wide and attributes narrow was deferred as a 3.0 candidate (needs a parallel signature list with its own sync test).
- `_check_tree` as is_relative_to(REPO_ROOT) (2026-08-05 #332) — accepts .venv/, build/ and dist/ copies inside the repo; the invariant is "is the source package", so the predicate is is_relative_to(REPO_ROOT / "nameparser").
- An issue for rotating DEFAULT_BASELINE (2026-08-07) — it recurs every release; it lives in the AGENTS.md release checklist beside the VERSION bump instead (#333 must land first).

### differential-ledger, retired for a snapshot (2026-10-13, #664)

The ledgers' last arc. They were built to show that 2.0 changed nothing against 1.4 except fixes the release log lists, and they did; as a standing check every later behavior change had to be classified once per ledger, and the guards policing the ledgers outgrew the ledgers.

Decisions that landed:

- 2026-10-13 #664 — **a committed snapshot replaces the classified gate.** `tools/differential/snapshot.jsonl` records every corpus name's reading (the seven role fields, ambiguity kinds, `initials()`, and the facade where it differs), one line per (name, order); `tests/v2/test_snapshot.py` fails on drift and prints the moves grouped by changed field. A change that moves readings re-records, and the PR diff of the snapshot is the list of names it moved. Nothing is classified: what a reviewer reads in the diff is what a ledger rule used to say in a regex. The six `expected_since_*.toml` ledgers and `tests/v2/test_ledger_guards.py` are deleted, and with them the contract/radar tiers, so the CJK corpus is one file again and the rules corpus harvests tolerated rules' examples too.
- 2026-10-13 #664 — **`compare.py` stays, unclassified.** It keeps the released-wheel runner and its checks against comparing one tree with itself (the version tell, the tree-side path check, the stripped `PYTHONPATH`; mechanisms.md#VERSION-TELL, #GENERATED-SCRIPT-OUTSIDE-THE-WORKTREE), prints the same grouped report as the snapshot and exits 0. It answers "how did release X read these names" for a release tagged before the snapshot existed; after that, `snapshot.py --since <tag>` is the cheaper answer.
- 2026-10-13 #664 — **the CLDR agreement ratchet stays** (#654). It answers a different question, agreement with CLDR's stated fields rather than stability.

Measured 2026-10-12, before the change, over the 40 first-parent commits ending at 04cc0814: 5,236 of 25,226 changed lines (21%) were ledger, `compare.py` or harness-test edits, and 21 of the 40 commits touched them. The share is uneven rather than steady: across the 29 of those commits that touch `nameparser/` it runs from 0% to 82%, median 11%, above 30% on 11 of them (#655: 236 of 448). Run against the code before and after #655, the snapshot reports five moved names, against that PR's 236 lines of ledger and guard edits; merging master afterwards, it reported #663's one new corpus name where #663 had added the same ten lines to each of six ledgers. RECOMPUTE (shares): `git log --first-parent -40 --format=%h 04cc0814`, and for each commit sum `git show --numstat` over every path except `*.jsonl` and `cldr_agreement.json`, the harness share over paths matching `expected_since|compare\.py|ledger_guards|test_differential|_differential_fixtures`; a commit "touches `nameparser/`" when any path starts with it.

Accepted costs:

- No forced explanation per moved name. A reviewer can approve a large snapshot diff without reading it; the grouping by changed fields is the mitigation.
- No bound on what a change may reach. `_CORPUS_CLAIMS`, the dormancy checks and the contest pins existed only to police ledgers; the two mechanisms entries that described them (LEDGER-RULE-SEPARATION and CROSS-RULE-OUTCOME-PINS) are retired with them.
- The 1.4 compatibility promise is a question asked when needed (`compare.py --baseline 1.4.0`), not a gate at every release. The facade is deleted in 3.0.

Declined:

- Trimming the ledgers rather than retiring them (2026-10-13). The radar tier (#468, 2026-09-01) was that attempt: it stopped new corpora from failing the run, but every contract name still needed a rule in every ledger, and the cost grew by one ledger per release.
