## Rendering & views (R)

Background: parsing produces words with roles; every string a caller reads is assembled from those words on request. Nothing about rendering changes the parse, and nothing about reading a field mutates anything. The default view lays a name out in the order it was read in and keeps its written separators (R6); a name read given-first renders '{title} {given} "{nickname}" {middle} {family} ({maiden}) {suffix}' — that choice and its declined née-template alternative are decisions/render-default.

