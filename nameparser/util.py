import logging
from typing import Literal

# http://code.google.com/p/python-nameparser/issues/detail?id=10
log = logging.getLogger('HumanName')
log.addHandler(logging.NullHandler())
log.setLevel(logging.ERROR)


HumanNameAttributeT = Literal['title', 'first', 'middle', 'last', 'suffix', 'nickname', 'surnames']


def lc(value: str) -> str:
    """Lower case and remove any periods to normalize for comparison."""
    if not value:
        return ''
    return value.lower().strip('.')
