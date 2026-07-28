#: Release version parts (major, minor, micro). VERSION stays a pure
#: numeric tuple so `nameparser.VERSION >= (2, 0, 0)` keeps working; the
#: pre-release segment lives separately.
VERSION = (2, 0, 0)
#: PEP 440 pre-release/dev segment appended to the numeric version, or
#: "" for a final release. Joined WITHOUT a dot ("2.0.0rc1", not
#: "2.0.0.rc1"); setuptools reads __version__ as the package version.
PRE_RELEASE = ""
__version__ = ".".join(map(str, VERSION)) + PRE_RELEASE
