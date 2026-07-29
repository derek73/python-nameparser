from nameparser._version import VERSION as VERSION
from nameparser._version import __version__ as __version__
from nameparser.parser import HumanName as HumanName
__author__ = "Derek Gulbranson"
__author_email__ = 'derek73@gmail.com'
__license__ = "LGPL"
__url__ = "https://github.com/derek73/python-nameparser"

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale
from nameparser._parser import Parser, parse, parser_for
from nameparser._policy import (
    DEFAULT_NICKNAME_DELIMITERS,
    DEFAULT_SCRIPT_ORDERS,
    FAMILY_FIRST,
    FAMILY_FIRST_GIVEN_LAST,
    GIVEN_FIRST,
    UNSET,
    PatronymicRule,
    Policy,
    PolicyPatch,
    Script,
)
from nameparser._types import (
    STABLE_TAGS,
    Ambiguity,
    AmbiguityKind,
    ParsedName,
    Role,
    Segmentation,
    Segmenter,
    Span,
    Token,
)

__all__ = [
    # v1 (compatibility layer)
    "HumanName",
    # v2 core
    "Span", "Role", "Token", "Ambiguity", "AmbiguityKind", "ParsedName",
    "STABLE_TAGS", "Segmentation", "Segmenter",
    "Lexicon", "Policy", "PolicyPatch", "PatronymicRule", "Script", "UNSET",
    "GIVEN_FIRST", "FAMILY_FIRST", "FAMILY_FIRST_GIVEN_LAST",
    "DEFAULT_NICKNAME_DELIMITERS", "DEFAULT_SCRIPT_ORDERS", "Locale",
    "Parser", "parse", "parser_for",
]
