## Rendering & views (R)

Background: parsing produces words with roles; every string a caller reads is assembled from those words on request. Nothing about rendering changes the parse, and nothing about reading a field mutates anything. The default view renders '{title} {given} "{nickname}" {middle} {family} ({maiden}) {suffix}' — the choice and its declined née-template alternative are decisions/render-default.

