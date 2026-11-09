# rules-size-record — rule sizes are a report, not a record

## Standing

- A rule's size is measured on demand against the branch's merge-base (`uv run python -m tests.v2.rules_size --since origin/master`) and is held by no test; the guards on a rule's shape are its `Signal:` line, the hub map check, the skeleton's sentence limits and review axis 12 — 2026-11-09 #PRNUM.

Open: none in this file.

## Log

- 2026-11-09 (#PRNUM) — THE COMMITTED RULE-SIZE RECORD IS RETIRED FOR A REPORT AGAINST THE MERGE-BASE. PR #745 (2026-10-19) recorded each rule's seven measures in `tests/v2/rules_budget.json`, one line per rule in ID order, and failed the suite on any move until the author re-recorded, so that a rule's growth showed in the record's diff (mechanisms.md#RECORDED-ROSTERS). Two things retired it. First, every rules PR rewrote that one file, and git's merge conflicts on adjacent changed lines, so branches editing neighbouring rules (C2 and C3) conflicted there though their rule files did not overlap: 115 commits touched the record through b76f2784, 58 of them moving two rows or more (`git log --format=%h b76f2784 -- tests/v2/rules_budget.json`, counting the `-  "` lines each commit's diff of the file removes). Second, it did not act as a brake: it was never a cap, a failing test was always answered by `--record`, and the rules grew from 17,306 words in 64 rules at d3730550 to 36,950 in 90 at b76f2784, summing each record's `words` (dated snapshot). A reviewer already sees a rule's growth in the rule file's own diff, so the record repeated it in a shared place; what it added was the counts, which `tests/v2/rules_size.py` now prints for the branch against the merge-base of `--since` and HEAD, with nothing committed. The splits that have happened (S2 by #682, C1 by #728, the 2026-10-19 splits #755/#756) were driven by a rule's signals, not its word count, and those checks stay.

Declined: a fixed cap per rule (a word or Except count past which the suite fails). With 26 rules over 500 words on 2026-11-09 a cap would fail at once or be set where it bounds nothing, and length is not the signal for a split ("Length is still not the signal; count the signals", docs/design/AGENTS.md). Declined: a union merge driver for the record, which keeps both sides' lines and so a duplicated key; GitHub's merge does not run a custom driver either.
