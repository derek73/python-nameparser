How the parser thinks
======================

Four short essays on the model behind the 2.0 API: how a string
becomes a :class:`~nameparser.ParsedName`, why configuration lives in
exactly three places sorted by what varies, why parsers are plain
values, and what the parser does when a name is genuinely ambiguous.

From string to name
--------------------

The pipeline, in one breath: the original string becomes a sequence of
tokens with spans (character positions into the original string),
each span gets assigned a role — ``title``, ``given``, ``middle``,
``family``, ``suffix``, ``nickname``, ``maiden`` — and every string you
read off a :class:`~nameparser.ParsedName` (``.given``, ``.family``,
``str(name)``, and so on) is a view computed over those roles at read
time, not stored text.

Spans matter because of what they replace. v1's ``HumanName`` worked
on plain lists of strings and re-found pieces by searching the list
for a matching value — so a name with a repeated word could make the
parser rewrite the wrong occurrence. That whole bug family (starting
with `issue #100 <https://github.com/derek73/python-nameparser/issues/100>`_)
traces back to value-based lookup. A token's span is a position, not a
value, so nothing in the 2.0 pipeline is ever re-found by scanning for
a string that looks like it.

:class:`~nameparser.ParsedName` is frozen: there is no attribute
assignment, ever. If a parse is almost right and you want to fix one
field, you call ``.replace()``, which returns a new
:class:`~nameparser.ParsedName` with that field changed and everything
else — tokens, spans, the rest of the roles — carried over unchanged.
``str()`` renders the default view; nothing about calling it mutates
the value you called it on.

The three containers
---------------------

Every piece of nameparser configuration falls into exactly one of
three places, and which one is decided by a single question: what does
this setting vary with?

* varies by **language** → :class:`~nameparser.Lexicon` (vocabulary:
  titles, particles, suffixes, conjunctions, and the rest of the
  word lists the parser matches against)
* varies by **data source or application** → :class:`~nameparser.Policy`
  (behavior switches: name order, patronymic rules, delimiters, strip
  flags — anything that changes how the pipeline runs, not what words
  it recognizes)
* varies by **output destination** → a rendering argument (the
  ``spec`` you pass to ``render(spec)``, or a keyword to
  ``initials()``/``capitalized()``)

"Dean" being a title in your data is a fact about the language and
domain the names come from (academic rosters, say), not about any one
dataset or report — that's a :class:`~nameparser.Lexicon` entry. A CRM that always exports "Family, Given" strings is a fact
about that one data source, not about the language of the names in
it — that's a :class:`~nameparser.Policy`. One particular report
wanting names formatted as "Family, Given" while every other consumer
of the same parsed data wants "Given Family" is a fact about where the
string is going next, decided at the moment you render it — that's a
rendering argument, not something baked into how the name was parsed.

This replaces v1's single ``Constants`` object, which mixed all three
concerns — vocabulary, behavior, and output formatting — into one
mutable bag plus a ``string_format`` template string. Sorting a
setting into the right container is largely mechanical once you ask
the "varies by what?" question above; see :doc:`migrate` for the
attribute-by-attribute mapping from the old ``Constants`` to the new
containers.

Parsers are values
--------------------

``parse()`` is a convenience function over a module-level default
:class:`~nameparser.Parser`. You only need to build your own
:class:`~nameparser.Parser` (directly, or via
:func:`~nameparser.parser_for`) when you want non-default vocabulary
or behavior — and when you do, build it once and reuse it. Constructing
a :class:`~nameparser.Parser` validates its configuration up front, so
it's cheap but not free; parsing individual names is the hot path, and
a :class:`~nameparser.Parser` is designed to be called many times
without reconstruction.

:class:`~nameparser.Lexicon`, :class:`~nameparser.Policy`,
:class:`~nameparser.Parser`, and :class:`~nameparser.ParsedName` are
all frozen and hashable. That means they're safe to share across
threads without locking, safe to use as dict keys or cache keys, and
equality means exactly what it says — two :class:`~nameparser.Parser`
instances built from equal configuration are equal values, not merely
two objects that happen to behave the same. Every piece of
configuration in the 2.0 API is a frozen value — including the
module-level default parser itself.

Honest ambiguity
------------------

Parsing never raises. Pass in a string that doesn't look like a name
at all, and you get back a :class:`~nameparser.ParsedName` with empty
fields, not an exception. The parser's job is to make a reasonable
call on real-world text, not to reject it.

Some calls are irreducibly ambiguous — both readings are legitimate,
and no amount of rule-tuning resolves them without breaking some other
name. Those surface as entries on ``ParsedName.ambiguities`` instead
of being silently guessed away. The canonical example: a leading "Van"
in "Van Johnson" reads as a given name (that's the common case for
that shape), but "Van" is also a family-name particle in plenty of
other names, so the parse records a ``particle-or-given`` ambiguity
alongside its answer. You can inspect ``ambiguities`` to decide, case
by case, whether your data needs a second look.

Tokens also carry tags — a second, independent label alongside their
role, recording how a token was classified rather than what part of
the name it belongs to — but only a handful of them are part of the
stable API: ``particle``, ``conjunction``, ``initial``, and ``joined``.
Any tag written with a namespace prefix, like ``vocab:...``, is
provenance information for debugging how a token got classified — it
can change shape between releases and isn't something to match against
in your own code. If you need to branch on how a token was
classified, branch on role or on one of the four stable tags above,
not on a namespaced one.
