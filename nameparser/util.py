"""v1 normalization, kept for the 1.x compatibility layer.

Removed in 3.0 with the rest of that layer; reading ``lc`` from here
warns since 2.8. The 2.0 core does NOT use this:
:func:`nameparser._lexicon._normalize` is its fold, which NFC-composes
and strips edge full stops to a fixed point where ``lc()`` strips ASCII
periods once.
"""
import warnings
from typing import TYPE_CHECKING

#: the message ``lc`` warns with; tests and pyproject's filterwarnings
#: match it
LC_DEPRECATION = (
    "nameparser.util.lc is deprecated and will be removed in 3.0 with the "
    "1.x compatibility layer; use value.lower().strip('.') instead"
)


def _lc(value: str) -> str:
    """Lowercase and strip leading/trailing periods to normalize for comparison."""
    if not value:
        return ''
    return value.lower().strip('.')


if TYPE_CHECKING:
    # what __getattr__ hands back, typed for a caller's checker
    lc = _lc


def __getattr__(name: str) -> object:
    # PEP 562, so the shim's own import of _lc stays quiet while every
    # caller's read of lc warns, per read rather than once per process
    if name == "lc":
        warnings.warn(LC_DEPRECATION, DeprecationWarning, stacklevel=2)
        return _lc
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
