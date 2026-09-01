#: Release version parts (major, minor, micro). VERSION stays a pure
#: numeric tuple so `nameparser.VERSION >= (2, 0, 0)` keeps working; the
#: pre-release segment lives separately.
#:
#: Bumped when a cycle OPENS, not when it ships, so the tree says what
#: it is building. Note the cost of the tuple being purely numeric: it
#: cannot carry the dev marker, so `VERSION >= (2, 2, 0)` is already
#: true here while 2.2.0 is unreleased. Compare `__version__` instead
#: where that distinction matters.
VERSION = (2, 2, 0)
#: PEP 440 pre-release/dev segment appended to the numeric version, or
#: "" for a final release. Joined WITHOUT a dot ("2.0.0rc1", not
#: "2.0.0.rc1"); setuptools reads __version__ as the package version.
#:
#: "dev" through the cycle, cleared at release. It normalizes to
#: 2.2.0.dev0, which sorts above 2.1.0 and BELOW 2.2.0, so an install
#: from master can never masquerade as the release it precedes.
PRE_RELEASE = ""
__version__ = ".".join(map(str, VERSION)) + PRE_RELEASE
