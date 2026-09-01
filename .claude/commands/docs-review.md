---
description: Review docs/design/ changes for the failure modes the doc tests cannot catch
argument-hint: "[base-ref, default master]"
allowed-tools: Bash, Read, Grep, Glob, Agent
---

Review this branch's changes to `docs/design/` using the
`design-docs-reviewer` agent.

Base ref: `${1:-master}`

1. Check there is something to review:
   `git diff ${1:-master}...HEAD --stat -- docs/design/` plus
   `git diff HEAD --stat -- docs/design/` for uncommitted work. If
   both are empty, say so and stop — do not review an empty diff.
2. Confirm the suite is green first, so the agent can assume the
   machine-checked layer holds: `uv run --frozen pytest -q`. If it
   fails, report that and stop; a red suite makes the agent's
   "assume these pass" section false and it will waste effort
   rediscovering known breakage.
3. Dispatch the `design-docs-reviewer` agent with the base ref and
   the changed-file list. Let it run its own axes — do not
   pre-summarize the diff for it, and do not tell it what you think
   the issues are. Its value is reading what is written rather than
   what was meant, and a primed agent loses exactly that.
4. Relay its findings verbatim in your reply — the agent's report is
   not shown to the user. Add your own assessment of each: agree,
   disagree with reasoning, or need-more-information. You are not
   obliged to accept a finding, but you are obliged to say why you
   reject one.

Do not apply fixes as part of this command. Report, then let the user
decide what lands.
