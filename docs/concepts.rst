How the parser works
====================

``parse()`` turns a name string into a
:class:`~nameparser.ParsedName`. This page explains the model behind
that call: how a string becomes tokens and tokens become fields, how
those tokens get their roles, where configuration lives and why it is
split the way it is, why parsers are plain values, and what happens
when a name is genuinely ambiguous. The task pages all build on these
five ideas.

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

:class:`Tokens <nameparser.Token>` also carry tags — a second, independent label alongside their
role, recording how a token was classified rather than what part of
the name it belongs to — but only a handful of them are part of the
stable API, collected in :data:`~nameparser.STABLE_TAGS`: ``particle``,
``conjunction``, ``initial``, and ``joined``.
Any tag written with a namespace prefix, like ``vocab:...``, is
provenance information for debugging how a token got classified — it
can change shape between releases and isn't something to match against
in your own code. If you need to branch on how a token was
classified, branch on role or on one of the stable tags above,
not on a namespaced one.

:class:`~nameparser.ParsedName` is frozen: there is no attribute
assignment, ever. If a parse is almost right and you want to fix one
field, you call ``.replace()``, which returns a new
:class:`~nameparser.ParsedName` with that field changed and everything
else — tokens, spans, the rest of the roles — carried over unchanged
(``replace()`` tokens carry no vocabulary classification;
:meth:`Parser.revise <nameparser.Parser.revise>` classifies the new
value the way a parse of that value on its own would).
``str()`` renders the default view; nothing about calling it mutates
the value you called it on.

How roles are decided
---------------------

Roles are not assigned in one pass, and two layers do most of the
work. A vocabulary layer runs first and
claims words for what they *are*, wherever they sit: titles, particles,
conjunctions, recognized suffixes, and anything set off by nickname or
maiden delimiters. Titles chain, so ``"Asst. Vice Chancellor"`` is one
title; particles join forward, so ``de la`` attaches to ``Vega``.

Whatever the vocabulary layer has not claimed is left to a positional
layer, which assigns purely by where a word sits: the first unclaimed
word is the given name, the last is the family name, and anything
between them is the middle name. ``name_order``, an explicit comma
and ``script_orders`` change what "first" and "last" mean here.
``script_orders`` covers the East Asian writing that settles its own
order: a name wholly in Han or hangul, or a Japanese name in kanji and
kana — any of them, hiragana alone included — unless it is katakana
alone, which is how a foreign name is transcribed. The Chinese
interpunct ``·`` dividing such a name walks that back, marking a
transcription that follows ``name_order`` like any other name. Two rules can still
override the arrangement: a particle that can never be a given name,
opening the name, opens the surname under every order rather than
becoming the given name (:ref:`order-vocabulary-first`), and the
opt-in ``patronymic_rules`` reorder, under the default order, a name
whose patronymic marks its parts.

A few words are read by how they are written, which is neither a list
lookup nor position alone: the writing proposes a reading, and where
the word stands decides whether it lands. An unlisted word of two or
more letters with a single period at its end, at the front of the
given-name part, is a title though no list holds it (``"Insp. Jane Morse"``; see
:ref:`abbreviated-titles`). Since 2.4, an unlisted acronym written in
periods (``X.Y.Z.``) is a credential behind a name that can spare it,
and one written in capitals (``XYZ``) is, by default, right after a
comma behind a full name that writes a word of its own in mixed case,
as ``Smith`` is (:ref:`unlisted-credentials`).

That is the whole parser in outline, and it explains its
character. A word nameparser has never seen still gets a sensible role,
because the positional layer does not need to recognize anything. The
same word can play different parts in different places — ``Lt.`` is a
title before a name and a post-nominal after it, which is why the field
names ``title`` and ``suffix`` are really "pre-nominal" and
"post-nominal".
And nothing is statistical: there is no model and no training data, so
the same input always parses the same way, and a parse that is wrong is
wrong reproducibly, which is what makes it fixable by configuration.

The split also tells you which container a setting belongs in, before
you look anything up: if you are teaching the parser a *word*, it goes
in the :class:`~nameparser.Lexicon`; if you are changing how unclaimed
words are *arranged*, or choosing where the unlisted-credential
readings apply, it goes in the :class:`~nameparser.Policy`.

.. _config-containers:

Configuration lives in three containers
----------------------------------------

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
vocabulary. But in some data it is more common as a title. The right
reading is a fact about the domain the names come from: that makes it a
:class:`~nameparser.Lexicon` entry. A CRM that wraps nicknames in
square brackets — ``John [Johnny] Smith`` — instead of quotes is a
fact about that one data source's export format, not about the
language of the names in it — that's a
:class:`~nameparser.Policy`
(``nickname_delimiters=frozenset({('[', ']')})``).
One particular report
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
call on real-world text, not to reject it. The single exception is
code you supplied yourself: a :data:`~nameparser.Segmenter` passed to
``Parser(segmenter=...)`` runs inside the parse, and its own
exceptions propagate rather than being swallowed — a failure there is
a bug in your callable, not a fact about the name.

Some calls are irreducibly ambiguous — both readings are legitimate,
and no amount of rule-tuning resolves them without breaking some other
name. Those surface as entries on ``ParsedName.ambiguities`` instead
of being silently guessed away. The canonical example: a leading "Van"
reads as a name of its own rather than as the start of a surname —
the right call for the actor Van Johnson, the wrong one for a bare
"Van Buren", and nothing in the two-word shape distinguishes them — so
the parse records a ``particle-or-given`` ambiguity alongside its
answer. (Which name that piece then becomes is a separate question,
and ``name_order``'s: the given name under the default.) You can
inspect ``ambiguities`` to decide, case by case, whether your data
needs a second look.

An ambiguity records a *decision*, not a word. The same token in a
different position may present no fork at all: ``do`` is in the
ambiguous post-nominal vocabulary, but in ``"Joao da Silva do Amaral
de Souza"`` it sits mid-name, where nothing has to choose between
readings — so nothing is recorded. A comma can settle the question
before it arises, too: ``"Ma, Jack"`` fixes the family name, so the
credential reading never comes up, while ``"John Smith MA"`` has to
call it and says so. Some decisions are conventions rather than
readings — a name whose one name word nothing else decides (such as
a title, a family comma, a nickname or maiden name beside it, a
script that settles its own order, or the word's own vocabulary or
shape) has nothing to compare,
and an
input the title peel eats down to one last title word reads that word
as the name for want of anything else — and since 2.3 those are
reported too, so a field the library merely had to pick is a field you
can see it picked. A title standing entirely alone reports nothing:
``"Dr."``, ``"Sir"`` and ``"Prince of Wales"`` are all title and no
name, so there is no reading to have doubted.

An empty ``ambiguities`` is therefore not a certificate of certainty.
Reporting is deliberately partial: :class:`~nameparser.AmbiguityKind`
lists the forks worth flagging, and even those are not reported
everywhere they occur. What a comma buys is narrower than it looks —
it names which words are the surname, and stays quiet about that
much, but it leaves the rest of the name to be read as usual, so
``"Beethoven, Ludwig van"`` still reports the trailing ``van`` it had
to call. Coverage grows over releases. Treat a non-empty
``ambiguities`` as a signal to act on; do not read an empty one as a
guarantee.
