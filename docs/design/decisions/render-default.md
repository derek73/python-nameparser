# render-default — the default view's format

## Standing

- The default spec is '{title} {given} "{nickname}" {middle} {family} ({maiden}) {suffix}', and a parenthesized maiden re-parsing as a nickname is its accepted cost (`Jane (nee Jones) Smith` renders 'Jane Smith (Jones)', which reads back with nickname 'Jones'); a née template that round-tripped losslessly was declined on presentation grounds — 2026-07-18.

Elsewhere: the v1 facade's own default `string_format`, which omits the maiden name, so `str()` of a `HumanName` cannot show it — decisions/R5's 2026-08-29 WHAT THE OVERRIDE DOES AND DOES NOT PROMISE entry.

Open: none in this file.

## Log

- 2026-07-18 (bf1141c) — the default spec is '{title} {given} "{nickname}" {middle} {family} ({maiden}) {suffix}'. Declined the same day: a née-template maiden ('née {maiden}') that round-tripped LOSSLESSLY (née is a maiden marker), rejected on presentation grounds. Accepted cost of the shipped form: a parenthesized maiden re-parses as a nickname.

