# deviates-registry — packs stay pure data (option C)

## Standing

- A locale pack declares its deviations from the defaults as a module-level `DEVIATES` callable, acceptance metadata kept off `Locale`, whose value equality and pickling a callable field would break; `test_registry_is_the_pack_contract` fails unless every registered pack ships `DEVIATES` and a rotator list, which is what lets mechanisms.md#LOCALE-PACKS-PURE-DATA promise packs no code paths of their own. A field on `Locale` is to be revisited only if a runtime consumer of the declaration, such as an `explain()`, appears, and none has — 2026-07-18.

Open: none in this file.

## Log

- 2026-07-18 (d4aaafa; the DEVIATES design note) — a `deviates` field ON Locale was rejected: callables break value equality and pickle-by-reference, and DEVIATES is acceptance metadata, not runtime behavior (revisit only if a runtime consumer like explain() appears). The REGISTRY became the contract instead: test_registry_is_the_pack_contract fails structurally unless every registered pack ships DEVIATES and its rotator list. This is why LOCALE-PACKS-PURE-DATA can promise "no code paths of their own" and mean it.

