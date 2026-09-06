from nameparser import HumanName

from tests.base import HumanNameTestBase


class SuffixesTestCase(HumanNameTestBase):

    def test_suffix(self) -> None:
        hn = HumanName("Joe Franklin Jr")
        self.m(hn.first, "Joe", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.suffix, "Jr", hn)

    def test_suffix_with_periods(self) -> None:
        hn = HumanName("Joe Dentist D.D.S.")
        self.m(hn.first, "Joe", hn)
        self.m(hn.last, "Dentist", hn)
        self.m(hn.suffix, "D.D.S.", hn)

    def test_two_suffixes(self) -> None:
        hn = HumanName("Kenneth Clarke QC MP")
        self.m(hn.first, "Kenneth", hn)
        self.m(hn.last, "Clarke", hn)
        # The writer spaced "QC MP", so #436 renders it as written
        # (rules.md#R1). A deliberate deviation from 1.4.0, which added a
        # comma the original format did not have.
        self.m(hn.suffix, "QC MP", hn)

    def test_two_suffixes_lastname_comma_format(self) -> None:
        hn = HumanName("Washington Jr. MD, Franklin")
        self.m(hn.first, "Franklin", hn)
        self.m(hn.last, "Washington", hn)
        # The writer spaced "Jr. MD", so #436 renders it as written
        # (rules.md#R1). This name HAS a writer's comma, but it stands
        # between MD and Franklin -- it parts the family from the run, not
        # the run from itself. A deliberate deviation from 1.4.0, which
        # added a comma the original format did not have.
        self.m(hn.suffix, "Jr. MD", hn)

    def test_roman_numeral_v_suffix_comma_format(self) -> None:
        # suffix-comma position is unambiguous: 'V' must be a suffix, not a single-letter initial
        hn = HumanName("John W. Ingram, V")
        self.m(hn.first, "John", hn)
        self.m(hn.middle, "W.", hn)
        self.m(hn.last, "Ingram", hn)
        self.m(hn.suffix, "V", hn)

    def test_roman_numeral_i_suffix_comma_format(self) -> None:
        # 'I' has the same single-letter ambiguity as 'V'
        hn = HumanName("John W. Smith, I")
        self.m(hn.first, "John", hn)
        self.m(hn.middle, "W.", hn)
        self.m(hn.last, "Smith", hn)
        self.m(hn.suffix, "I", hn)

    def test_suffix_not_acronym_then_acronym_suffix_comma_format(self) -> None:
        # single-letter suffix_not_acronyms entry followed by an acronym suffix
        hn = HumanName("John Smith, V MD")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Smith", hn)
        self.m(hn.suffix, "V MD", hn)

    def test_two_suffix_not_acronyms_suffix_comma_format(self) -> None:
        hn = HumanName("John Smith, V Jr.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Smith", hn)
        self.m(hn.suffix, "V Jr.", hn)

    def test_two_suffixes_suffix_comma_format(self) -> None:
        hn = HumanName("Franklin Washington, Jr. MD")
        self.m(hn.first, "Franklin", hn)
        self.m(hn.last, "Washington", hn)
        self.m(hn.suffix, "Jr. MD", hn)

    def test_suffix_containing_periods(self) -> None:
        hn = HumanName("Kenneth Clarke Q.C.")
        self.m(hn.first, "Kenneth", hn)
        self.m(hn.last, "Clarke", hn)
        self.m(hn.suffix, "Q.C.", hn)

    def test_suffix_containing_periods_lastname_comma_format(self) -> None:
        hn = HumanName("Clarke, Kenneth, Q.C. M.P.")
        self.m(hn.first, "Kenneth", hn)
        self.m(hn.last, "Clarke", hn)
        self.m(hn.suffix, "Q.C. M.P.", hn)

    def test_suffix_containing_periods_suffix_comma_format(self) -> None:
        hn = HumanName("Kenneth Clarke Q.C., M.P.")
        self.m(hn.first, "Kenneth", hn)
        self.m(hn.last, "Clarke", hn)
        self.m(hn.suffix, "Q.C., M.P.", hn)

    def test_suffix_with_single_comma_format(self) -> None:
        hn = HumanName("John Doe jr., MD")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "jr., MD", hn)

    def test_suffix_with_double_comma_format(self) -> None:
        hn = HumanName("Doe, John jr., MD")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "jr., MD", hn)

    def test_phd_with_erroneous_space(self) -> None:
        hn = HumanName("John Smith, Ph. D.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Smith", hn)
        self.m(hn.suffix, "Ph. D.", hn)

    def test_phd_extracted_without_comma(self) -> None:
        hn = HumanName("John Smith Ph. D.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Smith", hn)
        self.m(hn.suffix, "Ph. D.", hn)

    def test_phd_conflict(self) -> None:
        hn = HumanName("Adolph D")
        self.m(hn.first, "Adolph", hn)
        self.m(hn.last, "D", hn)

    # http://en.wikipedia.org/wiki/Ma_(surname)

    def test_potential_suffix_that_is_also_last_name(self) -> None:
        hn = HumanName("Jack Ma")
        self.m(hn.first, "Jack", hn)
        self.m(hn.last, "Ma", hn)

    def test_potential_suffix_that_is_also_last_name_comma(self) -> None:
        hn = HumanName("Ma, Jack")
        self.m(hn.first, "Jack", hn)
        self.m(hn.last, "Ma", hn)

    def test_potential_suffix_that_is_also_last_name_with_suffix(self) -> None:
        hn = HumanName("Jack Ma Jr")
        self.m(hn.first, "Jack", hn)
        self.m(hn.last, "Ma", hn)
        self.m(hn.suffix, "Jr", hn)

    def test_potential_suffix_that_is_also_last_name_with_suffix_comma(self) -> None:
        hn = HumanName("Ma III, Jack Jr")
        self.m(hn.first, "Jack", hn)
        self.m(hn.last, "Ma", hn)
        self.m(hn.suffix, "III, Jr", hn)

    # https://github.com/derek73/python-nameparser/issues/27
    def test_king(self) -> None:
        # v1 aspired to read "Dr King Jr" as title 'Dr', family 'King',
        # suffix 'Jr', and shipped this as an xfail.
        # Two halves, and this pin means different things about each.
        # DECIDED 2026-09-01 (v1-xfail triage, decisions.md#v1-xfail-triage):
        # 'king' stays in the titles vocabulary, because removing it breaks
        # the addressing forms it is there for ("King Charles").
        # decisions.md#vocabulary-collisions cuts toward keeping it, so the
        # title chain takes 'Dr King'. The comma format is the road to the
        # surname reading, pinned below.
        # RECORDED, NOT ENDORSED: what becomes of the leftover 'Jr'.
        # rules.md#S2 has a trailing suffix-vocabulary word read as a suffix,
        # and its Accepted clause consumes one even when that leaves no family
        # at all, so S2 predicts suffix 'Jr', family ''. Once the title
        # chain has eaten two words, H1 claims the one that remains and it
        # reads family 'Jr' instead. Compare 'Dr Smith Jr', which reads
        # family 'Smith', suffix 'Jr' exactly as S2 states. A change moving
        # this toward S2's prediction is an IMPROVEMENT that updates this
        # pin, not a regression.
        hn = HumanName("Dr King Jr")
        self.m(hn.title, "Dr King", hn)
        self.m(hn.first, "", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Jr", hn)
        self.m(hn.suffix, "", hn)

    def test_king_as_a_family_name_via_the_comma_format(self) -> None:
        # The workaround test_king's decision rests on: writing the family
        # first defeats the title chain and reads 'King' as the family.
        hn = HumanName("King, Dr Jr")
        self.m(hn.title, "Dr", hn)
        self.m(hn.last, "King", hn)
        self.m(hn.suffix, "Jr", hn)

    def test_multiple_letter_suffix_with_periods(self) -> None:
        hn = HumanName("John Doe Msc.Ed.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "Msc.Ed.", hn)

    def test_suffix_with_periods_with_comma(self) -> None:
        hn = HumanName("John Doe, Msc.Ed.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "Msc.Ed.", hn)

    def test_suffix_with_periods_with_lastname_comma(self) -> None:
        hn = HumanName("Doe, John Msc.Ed.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "Msc.Ed.", hn)

    def test_roman_numeral_i_lastname_comma_format(self) -> None:
        # 'I' is in suffix_not_acronyms; trailing suffix_not_acronyms members in
        # "Lastname, First Middle Suffix" format (no comma-suffix segment) must
        # parse as suffix, not middle initial (issue #144)
        hn = HumanName("Maier, Amy Lauren I")
        self.m(hn.first, "Amy", hn)
        self.m(hn.middle, "Lauren", hn)
        self.m(hn.last, "Maier", hn)
        self.m(hn.suffix, "I", hn)

    def test_roman_numeral_v_lastname_comma_format(self) -> None:
        # 'V' shares the same suffix_not_acronyms ambiguity as 'I' (issue #144)
        hn = HumanName("Smith, John V")
        self.m(hn.first, "John", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Smith", hn)
        self.m(hn.suffix, "V", hn)

    def test_roman_numeral_i_no_middle_lastname_comma_format(self) -> None:
        # no middle name: trailing 'I' must still be a suffix (issue #144)
        hn = HumanName("Smith, John I")
        self.m(hn.first, "John", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Smith", hn)
        self.m(hn.suffix, "I", hn)

    def test_roman_numeral_i_after_single_initial_lastname_comma_format(self) -> None:
        # single-letter middle initial followed by trailing 'I' (reporter pattern, issue #144)
        hn = HumanName("Chang, Andy C I")
        self.m(hn.first, "Andy", hn)
        self.m(hn.middle, "C", hn)
        self.m(hn.last, "Chang", hn)
        self.m(hn.suffix, "I", hn)

    def test_roman_numeral_i_with_explicit_suffix_comma_stays_a_middle_initial(self) -> None:
        # v1 aspired to read the trailing 'I' as an ordinal joining the explicit
        # suffix ("I, Jr."), and shipped this as an xfail.
        # NOT FIXED, decided 2026-09-01 (v1-xfail triage,
        # decisions.md#v1-xfail-triage): a middle initial 'I' is far more common
        # than an ordinal I borne without a Sr./Jr.-style companion, so when an
        # explicit suffix comma has already named the suffix, the trailing 'I'
        # stays a middle initial. The commonality reasoning is the
        # vocabulary-collision criterion (decisions.md#vocabulary-collisions)
        # applied to a shape rather than to a word.
        # Contrast test_roman_numeral_i_after_single_initial_lastname_comma_format
        # above, where no explicit suffix comma is present and the 'I' does go to
        # suffix.
        # rules.md#C1 gained a qualifier with this triage: where a further
        # comma has already named the suffix, the trailing single letter has
        # no generation left to be. C1 carries no example line for it (see the
        # Accepted note there), so this pair of tests is its witness.
        hn = HumanName("Maier, Amy I, Jr.")
        self.m(hn.first, "Amy", hn)
        self.m(hn.middle, "I", hn)
        self.m(hn.last, "Maier", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test_suffix_delimiter_default_on_constants(self) -> None:
        from nameparser.config import CONSTANTS
        self.assertIs(CONSTANTS.suffix_delimiter, None)

    def test_suffix_delimiter_kwarg_accepted(self) -> None:
        hn = HumanName("Steven Hardman, RN - CRNA", suffix_delimiter=" - ")
        self.assertEqual(hn.suffix_delimiter, " - ")

    def test_suffix_delimiter_basic(self) -> None:
        hn = HumanName("Steven Hardman, RN - CRNA", suffix_delimiter=" - ")
        self.m(hn.first, "Steven", hn)
        self.m(hn.last, "Hardman", hn)
        self.m(hn.suffix, "RN, CRNA", hn)

    def test_suffix_delimiter_multiple(self) -> None:
        hn = HumanName("John Doe, MD - PhD - FACS", suffix_delimiter=" - ")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "MD, PhD, FACS", hn)

    def test_suffix_delimiter_no_effect_without_comma(self) -> None:
        # suffix_delimiter only applies after the comma split; space-separated
        # suffixes already work via the no-comma parse path. Since #436 the
        # run renders with the space the writer typed, so the row shows the
        # knob is inert rather than showing a comma nobody asked for -- a
        # deliberate deviation from 1.4.0, which added that comma.
        hn = HumanName("John Doe MD PhD", suffix_delimiter=" - ")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "MD PhD", hn)

    def test_suffix_delimiter_constants_level(self) -> None:
        # ran on the shared CONSTANTS in v1; 2.0 deprecates shared mutation,
        # so the config-level (non-kwarg) path is exercised on a private
        # Constants passed as constants=
        from nameparser.config import Constants
        c = Constants()
        c.suffix_delimiter = " - "
        hn = HumanName("Steven Hardman, RN - CRNA", constants=c)
        self.m(hn.first, "Steven", hn)
        self.m(hn.last, "Hardman", hn)
        self.m(hn.suffix, "RN, CRNA", hn)

    def test_suffix_delimiter_none_by_default_known_limitation(self) -> None:
        # Without suffix_delimiter set, " - " between suffixes breaks parsing.
        # This test documents the known limitation — do not "fix" it.
        hn = HumanName("Steven Hardman, RN - CRNA")
        self.m(hn.first, "RN", hn)
        self.m(hn.last, "Steven Hardman", hn)
        self.m(hn.suffix, "CRNA", hn)

    def test_suffix_delimiter_trailing_delimiter_ignored(self) -> None:
        # Trailing delimiter must not defeat suffix detection. Using a
        # non-whitespace-terminated delimiter so stripping doesn't consume it.
        hn = HumanName("John Doe, MD-PhD-", suffix_delimiter="-")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        # 2.0: fix(suffix-delimiter-rendering) -- v1 split the token and
        # rendered 'MD, PhD'; v2 keeps a no-space delimiter-core token whole
        # (anti-#100), same rule as the pinned 'RN/CRNA' case row.
        self.m(hn.suffix, "MD-PhD-", hn)

    def test_suffix_delimiter_comma_space_is_noop(self) -> None:
        hn = HumanName("John Doe, MD, PhD", suffix_delimiter=", ")
        self.m(hn.suffix, "MD, PhD", hn)

    def test_suffix_delimiter_inverted_format_not_misparsed(self) -> None:
        # The delimiter only expands parts once they're identified as a
        # suffix group, so a hyphenated given name in inverted format isn't
        # mistaken for a suffix split.
        hn = HumanName("Doe, Mary - Kate, RN", suffix_delimiter=" - ")
        self.m(hn.first, "Mary", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "RN", hn)
        # "Kate" stays in the given-name segment rather than being pulled
        # into the suffix, since it's separated from "RN" by its own comma.
        # The bare "-" landing in middle is a pre-existing, delimiter-
        # independent quirk of tokenizing a lone hyphen (reproducible with
        # suffix_delimiter unset), not something this fix is responsible for.
        self.m(hn.middle, "- Kate", hn)

    def test_suffix_delimiter_expands_each_comma_segment(self) -> None:
        # parts[1:] holds two separate comma segments here ("MD - PhD" and
        # "FACS"); each must be expanded on its own, not just the first.
        hn = HumanName("John Doe, MD - PhD, FACS", suffix_delimiter=" - ")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "MD, PhD, FACS", hn)

    def test_suffix_delimiter_detection_with_multi_word_side(self) -> None:
        # The suffix-comma detection check flattens on spaces after
        # expanding on the delimiter, so a multi-word token on one side of
        # the delimiter is still tokenized correctly.
        hn = HumanName("Doe, John, MD PhD - FACS Fellow", suffix_delimiter=" - ")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "MD PhD, FACS Fellow", hn)

    def test_suffix_delimiter_no_effect_when_not_suffix_comma(self) -> None:
        # When the comma format isn't recognized as suffix-comma (here the
        # last-name part is a single word), the delimiter must not affect
        # parsing at all: output should match the no-delimiter baseline.
        with_delim = HumanName("Smith, MD - PhD - FACS", suffix_delimiter=" - ")
        without_delim = HumanName("Smith, MD - PhD - FACS")
        self.assertEqual(
            (with_delim.first, with_delim.middle, with_delim.last, with_delim.suffix),
            (without_delim.first, without_delim.middle, without_delim.last, without_delim.suffix),
        )

    def test_suffix_acronyms_ambiguous_is_customizable(self) -> None:
        from nameparser.config import Constants
        custom = Constants(suffix_acronyms_ambiguous=['xyz'])
        self.assertEqual(set(custom.suffix_acronyms_ambiguous), {'xyz'})
        # Constructing without the kwarg still works and uses the module default.
        default = Constants()
        self.assertIn('jd', default.suffix_acronyms_ambiguous)

    def test_suffix_in_parenthesis_with_other_suffixes(self) -> None:
        hn = HumanName("Andrew Perkins, Jr., Col. (Ret)")
        self.m(hn.first, "Andrew", hn)
        self.m(hn.last, "Perkins", hn)
        self.assertIn("Ret", hn.suffix)
        self.m(hn.nickname, "", hn)

    def test_suffix_in_parenthesis_mid_name(self) -> None:
        # "Jr." is suffix-shaped, so parse_nicknames() no longer treats it as
        # a nickname. But it isn't in trailing position, and parse_full_name's
        # suffix detection only recognizes a trailing run of suffix-shaped
        # pieces -- so it lands wherever normal parsing would put a bare
        # mid-name "Jr." token, exactly as if the parens were never there
        # (verified: HumanName("Lon Jr. Williams") parses identically).
        # Known limitation: making this land in `suffix` would require
        # changing parse_full_name's suffix detection, out of scope here --
        # issue #111 is specifically about the nickname misclassification.
        hn = HumanName("Lon (Jr.) Williams")
        self.m(hn.first, "Lon", hn)
        self.m(hn.middle, "Jr.", hn)
        self.m(hn.last, "Williams", hn)
        self.m(hn.suffix, "", hn)
        self.m(hn.nickname, "", hn)

    def test_suffix_in_parenthesis_with_period(self) -> None:
        # Same known limitation as above: "Ret." is mid-name (no comma), so
        # it's outside the trailing run parse_full_name's suffix detection
        # requires. It parses exactly as bare "Col. Ret. Smith" would: since
        # "Ret." is an unrecognized period-abbreviation appearing before the
        # first name is set, is_leading_title() treats it as a second title
        # token (see #109), joining "Col." into a single title string.
        hn = HumanName("Col. (Ret.) Smith")
        self.m(hn.title, "Col. Ret.", hn)
        self.m(hn.first, "", hn)
        self.m(hn.last, "Smith", hn)
        self.m(hn.suffix, "", hn)
        self.m(hn.nickname, "", hn)

    def test_acronym_suffix_in_parenthesis(self) -> None:
        hn = HumanName("Andrew Perkins (MBA)")
        self.m(hn.first, "Andrew", hn)
        self.m(hn.last, "Perkins", hn)
        self.m(hn.suffix, "MBA", hn)
        self.m(hn.nickname, "", hn)

    def test_acronym_suffix_with_internal_periods_in_parenthesis(self) -> None:
        # "M.D" has a non-trailing period between every letter -- unlike
        # is_suffix(), handle_match()'s suffix_acronyms check must also strip
        # internal periods (not just rely on the trailing content.endswith('.')
        # heuristic, which doesn't fire here since "M.D" has no trailing period).
        hn = HumanName("Andrew Perkins (M.D)")
        self.m(hn.first, "Andrew", hn)
        self.m(hn.last, "Perkins", hn)
        self.m(hn.suffix, "M.D", hn)
        self.m(hn.nickname, "", hn)

    def test_period_terminated_content_in_parenthesis_not_forced_either_way(self) -> None:
        # "Mgr." isn't in any suffix list, but it ends in a period, so the
        # period heuristic (rule 2) excludes it from nickname_list. It flows
        # into normal parsing instead of being force-classified as a suffix.
        hn = HumanName("Andrew Perkins (Mgr.)")
        self.m(hn.nickname, "", hn)
        self.m(hn.suffix, "", hn)

    def test_suffix_in_single_quotes(self) -> None:
        # handle_match() is shared across all three delimiter regexes, not
        # just parenthesis -- confirm suffix-shaped single-quoted content
        # routes the same way.
        hn = HumanName("Andrew Perkins 'MBA'")
        self.m(hn.first, "Andrew", hn)
        self.m(hn.last, "Perkins", hn)
        self.m(hn.suffix, "MBA", hn)
        self.m(hn.nickname, "", hn)

    def test_suffix_in_double_quotes(self) -> None:
        hn = HumanName('Andrew Perkins "MBA"')
        self.m(hn.first, "Andrew", hn)
        self.m(hn.last, "Perkins", hn)
        self.m(hn.suffix, "MBA", hn)
        self.m(hn.nickname, "", hn)

    def test_suffix_acronyms_ambiguous_custom_entry_stays_nickname(self) -> None:
        # A custom suffix_acronyms_ambiguous entry keeps a suffix_acronyms
        # member classified as a nickname instead of a suffix, confirming
        # the exception list -- not a hardcoded check -- drives the behavior.
        from nameparser.config import Constants
        C = Constants(
            suffix_acronyms=['xyz'],
            suffix_acronyms_ambiguous=['xyz'],
        )
        hn = HumanName("Andrew Perkins (XYZ)", constants=C)
        self.m(hn.nickname, "XYZ", hn)
        self.m(hn.suffix, "", hn)

    def test_suffix_acronyms_ambiguous_removal_routes_to_suffix(self) -> None:
        # Removing 'jd' from a custom suffix_acronyms_ambiguous flips JD
        # from nickname to suffix. Uses a trailing-position name (unlike the
        # JEFFREY (JD) BRICKEN regression guard in test_nicknames.py) so
        # parse_full_name's trailing-run suffix detection actually picks it
        # up -- see the known mid-name limitation noted on the tests above.
        from nameparser.config import Constants
        C = Constants(suffix_acronyms_ambiguous=[])
        hn = HumanName("Andrew Perkins (JD)", constants=C)
        self.m(hn.nickname, "", hn)
        self.m(hn.suffix, "JD", hn)

    def test_empty_comma_segment_does_not_drop_following_suffix(self) -> None:
        # Regression: "Doe, John,, Jr." produced an empty third segment, and
        # the old `if parts[2]:` guard skipped every remaining segment --
        # silently dropping the trailing suffix. Empty segments should be
        # skipped individually.
        hn = HumanName("Doe, John,, Jr.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "Jr.", hn)
        # each empty segment is skipped individually; segments after a later
        # empty must survive too (guards against a break-instead-of-continue
        # regression that the single-empty case above would not catch)
        hn = HumanName("Doe, John,, Jr.,, III")
        self.m(hn.suffix, "Jr., III", hn)

    def test_suffix_comma_empty_segment_not_added_to_suffix_list(self) -> None:
        # Regression: in suffix-comma format ("John Doe, Jr.,," -- one
        # trailing comma survives collapse_whitespace), the unguarded
        # parts[1:] loop leaked '' into suffix_list via
        # expand_suffix_delimiter('') returning [''].
        hn = HumanName("John Doe, Jr.,,")
        self.assertEqual(hn.suffix_list, ["Jr."])
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
