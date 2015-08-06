import logging

# http://code.google.com/p/python-nameparser/issues/detail?id=10
log = logging.getLogger('HumanName')
try:
    log.addHandler(logging.NullHandler())
except AttributeError:
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass
    log.addHandler(NullHandler())
log.setLevel(logging.ERROR)


import sys
if sys.version < '3':

    text_type = unicode
    binary_type = str

    def u(x, encoding=None):
        if encoding:
            return unicode(x, encoding)
        else:
            return unicode(x)

else:
    text_type = str
    binary_type = bytes

    def u(x, encoding=None):
        return text_type(x)

text_types = (text_type, binary_type)
def lc(value):
    """Lower case and remove any periods to normalize for comparison."""
    if not value:
        return ''
    return value.lower().strip('.')
