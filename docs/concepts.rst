How the parser works
====================

``parse()`` turns a name string into a
:class:`~nameparser.ParsedName`. This page explains the model behind
that call: how a string becomes tokens and tokens become fields,
where configuration lives and why it is split the way it is, why
parsers are plain values, and what happens when a name is genuinely
ambiguous. The task pages all build on these four ideas.

From string to name
--------------------

Every parse follows the same path: the input string is split into
:class:`tokens <nameparser.Token>`, each token is assigned one of the seven roles — ``title``,
``given``, ``middle``, ``family``, ``suffix``, ``nickname``,
``maiden`` — and every string you read off the result is computed
from those tokens at read time.

Parsing ``"Dr. Juan Q. Xavier de la Vega III"`` produces eight
tokens. The first is ``Dr.`` with the ``title`` role; ``de``, ``la``,
and ``Vega`` each carry the ``family`` role, which is why
``name.family`` returns ``"de la Vega"`` — the field is a view that
joins the family-role tokens in order, not a stored string.

Each token also records where it came from. A :class:`~nameparser.Span` is a pair of
character positions bounding the token in the original string:
``Dr.`` has span ``(0, 3)``, and ``name.original[0:3]`` is exactly
``"Dr."``. Internally, spans let the pipeline refer to a token by
position instead of by text. v1 re-found name pieces by searching for
matching text, so a name with a repeated word could make the parser
rewrite the wrong occurrence (`issue #100
<https://github.com/derek73/python-nameparser/issues/100>`_ and its
relatives); a position cannot be confused with a look-alike.

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

* :class:`~nameparser.Lexicon` holds everything that varies by
  **language**: the vocabulary — titles, particles, suffixes,
  conjunctions, and the rest of the word lists the parser matches
  against.
* :class:`~nameparser.Policy` holds everything that varies by
  **data source or application**: the behavior switches — name order,
  patronymic rules, delimiters, strip flags — anything that changes
  how the pipeline runs, not what words it recognizes.
* :ref:`Rendering arguments <rendering-arguments>` cover everything
  that varies by **output destination**: the ``spec`` you pass to
  ``render(spec)``, or a keyword to ``initials()``/``capitalized()``.

"Dean" is a common given name, so it is not in the default titles
vocabulary — but in some data it is more common as a title. Which
reading is right is a fact about the language and domain the names
come from, not about any one dataset or report: that makes it a
:class:`~nameparser.Lexicon` entry. A CRM that always exports "Family, Given" strings is a fact
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

:class:`Tokens <nameparser.Token>` also carry tags — a second, independent label alongside their
role, recording how a token was classified rather than what part of
the name it belongs to — but only a handful of them are part of the
stable API: ``particle``, ``conjunction``, ``initial``, and ``joined``.
Any tag written with a namespace prefix, like ``vocab:...``, is
provenance information for debugging how a token got classified — it
can change shape between releases and isn't something to match against
in your own code. If you need to branch on how a token was
classified, branch on role or on one of the four stable tags above,
not on a namespaced one.
