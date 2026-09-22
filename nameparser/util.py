"""v1 normalization, kept for the 1.x compatibility layer.

Removed in 3.0 with the rest of that layer. The 2.0 core does NOT use
this: :func:`nameparser._lexicon._normalize` is its fold, which
NFC-composes and strips edge full stops to a fixed point where
``lc()`` strips ASCII periods once.
"""


def lc(value: str) -> str:
    """Lowercase and strip leading/trailing periods to normalize for comparison."""
    if not value:
        return ''
    return value.lower().strip('.')
