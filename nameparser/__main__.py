"""Command-line debug helper: parse a name and print the result.

Usage:

    python -m nameparser "Dr. Juan Q. Xavier de la Vega III"
"""
import logging
import sys

from nameparser import HumanName


def main() -> None:
    if len(sys.argv) <= 1:
        print('Usage: python -m nameparser "Name String"')
        raise SystemExit(1)
    log = logging.getLogger('HumanName')
    log.setLevel(logging.ERROR)
    log.addHandler(logging.StreamHandler())
    name_string = sys.argv[1]
    hn = HumanName(name_string, encoding=sys.stdout.encoding)
    print(repr(hn))
    hn.capitalize()
    print(repr(hn))
    print("Initials: " + hn.initials())


if __name__ == '__main__':
    main()
