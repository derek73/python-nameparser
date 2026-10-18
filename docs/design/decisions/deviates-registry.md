# deviates-registry — packs stay pure data (option C)

- 2026-07-18 (d4aaafa; the DEVIATES design note) — a `deviates` field ON Locale was rejected: callables break value equality and pickle-by-reference, and DEVIATES is acceptance metadata, not runtime behavior (revisit only if a runtime consumer like explain() appears). The REGISTRY became the contract instead: test_registry_is_the_pack_contract fails structurally unless every registered pack ships DEVIATES and its rotator list. This is why LOCALE-PACKS-PURE-DATA can promise "no code paths of their own" and mean it.

