# given-name-titles — deliberately unvalidated

Declined (rc1 arc; the full argument is AGENTS.md's gotcha):

- Validating given_name_titles against titles, twice: the whole-entry check rejected legitimate multi-word entries; the per-word check rejected "sir and dame" (a conjunction inside a title run is itself a TITLE token, so the key is matchable while its middle word lives in conjunctions). No static relation over the vocabulary sets decides reachability, and an unreachable entry is inert — each guard cost a working configuration to forbid a condition that costs nothing.

