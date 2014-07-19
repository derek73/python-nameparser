
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

def lc(value):
    """Lower case and remove any periods to normalize for comparison."""
    if not value:
        return ''
    return value.lower().strip('.')
