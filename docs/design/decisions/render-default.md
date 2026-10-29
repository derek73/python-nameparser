# render-default — the default view's format

## Standing

- The given-first layout of the default rendering is '{title} {given} "{nickname}" {middle} {family} ({maiden}) {suffix}' (since 3.0 the default follows the order a name was read in and its written separators, rules/R6 and decisions/R6, and this is the layout of a name read given-first), and a parenthesized maiden re-parsing as a nickname is its accepted cost (`Jane (nee Jones) Smith` renders 'Jane Smith (Jones)', which reads back with nickname 'Jones'); a née template that round-tripped losslessly was declined on presentation grounds — 2026-07-18.

Elsewhere: the v1 facade's own default `string_format`, which omitted the maiden name, so `str()` of a `HumanName` could not show it until #357 removed the facade — decisions/R5's 2026-08-29 WHAT THE OVERRIDE DOES AND DOES NOT PROMISE entry.

Open: none in this file.

## Log

- 2026-07-18 (bf1141c) — the default spec is '{title} {given} "{nickname}" {middle} {family} ({maiden}) {suffix}'. Declined the same day: a née-template maiden ('née {maiden}') that round-tripped LOSSLESSLY (née is a maiden marker), rejected on presentation grounds. Accepted cost of the shipped form: a parenthesized maiden re-parses as a nickname.

