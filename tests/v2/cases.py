"""THE shared behavior case table (core spec §7.2).

Format is fixed here, in the first pipeline PR, and never per-PR:
one Case per input, expected values for exactly the non-empty fields,
optional Policy/Locale context, and a mandatory classification --
"parity" (matches v1.4.0, pinned live 2026-07-12) or "fix(#N)" /
"fix(<slug>)" (an intentional 2.0 behavior change, annotated with its
issue or a design-decision slug). No silent expectation edits:
changing a row means changing its classification.

The v1 suite's full corpus is extracted into this table by the
migration plan (facade runner consumes the same rows); this file seeds
it with the pinned battery.
"""
from __future__ import annotations

from dataclasses import dataclass

from nameparser import Policy
from nameparser._policy import PatronymicRule


@dataclass(frozen=True)
class Case:
    id: str
    text: str
    expect: dict[str, str]          # field -> value; absent fields == ""
    policy: Policy | None = None
    locale: str | None = None       # locale CODE (keeps this table
                                     # import-light); mutually exclusive
                                     # with policy
    classification: str = "parity"
    ambiguities: tuple[str, ...] = ()   # expected AmbiguityKind values
    notes: str = ""

    def __post_init__(self) -> None:
        if self.policy is not None and self.locale is not None:
            raise ValueError(
                f"{self.id}: policy and locale are mutually exclusive")


_ES = Policy(patronymic_rules=frozenset({PatronymicRule.EAST_SLAVIC}))
_TK = Policy(patronymic_rules=frozenset({PatronymicRule.TURKIC}))
_SD = Policy(extra_suffix_delimiters=frozenset({" - "}))

CASES: tuple[Case, ...] = (
    Case("plain", "John Smith", {"given": "John", "family": "Smith"}),
    Case("family_comma", "Smith, John",
         {"given": "John", "family": "Smith"}),
    Case("suffix_comma", "John Smith, PhD",
         {"given": "John", "family": "Smith", "suffix": "PhD"}),
    Case("bound_given_pairwise_only", "Salem, Abdul Rahman Ahmed",
         {"given": "Abdul Rahman", "middle": "Ahmed", "family": "Salem"},
         notes="the bound-given join is PAIRWISE (one merge, v1 "
               "parity): the third piece stays a middle name"),
    Case("family_comma_three_part_trailing_strict", "Smith, John V, Jr.",
         {"given": "John", "middle": "V", "family": "Smith",
          "suffix": "Jr."},
         notes="the lenient trailing test applies only to TWO-part "
               "names; a third comma part makes the trailing token a "
               "middle initial (v1 parity, pinned live 2026-07-17)"),
    Case("triple_trailing_commas", "Doe,,,",
         {"family": "Doe"},
         notes="one trailing comma is cosmetic; the rest are "
               "structural empties (pinned live 2026-07-17)"),
    Case("paren_suffix_word_escapes_nickname", "John Smith (Esq)",
         {"given": "John", "family": "Smith", "suffix": "Esq"},
         notes="the suffix_words branch of the delimited-content "
               "escape (v1 parity, pinned live 2026-07-17)"),
    Case("suffix_acronym_multidot_spelling", "John Smith E.S.Q.",
         {"given": "John", "family": "Smith", "suffix": "E.S.Q."},
         notes="'esq' is in BOTH suffix_acronyms and suffix_words on "
               "purpose, and the two are not redundant: the word test "
               "strips only EDGE periods, the acronym test strips all "
               "of them, so only the acronym membership matches the "
               "multi-dot spelling (v1 parity, pinned live 2026-07-19)"),
    Case("bound_given_whole_segment", "salem, abdul salam",
         {"given": "abdul salam", "family": "salem"},
         notes="v1 joins bound given names freely in the post-comma "
               "segment (reserve_last=False, parser.py:1366) -- even "
               "when the join consumes the whole segment"),
    Case("middle_as_family_fold_order", "Hassan, Mohamad Ahmad Ali",
         {"given": "Mohamad", "family": "Ahmad Ali Hassan"},
         policy=Policy(middle_as_family=True),
         notes="v1 PREPENDED middle_list to last_list; folded tokens "
               "carry vocab:folded-middle and the family view orders "
               "them first (spans cannot reorder)"),
    Case("ambiguous_surname_acronyms", "Jack MA",
         {"given": "Jack", "family": "MA"},
         ambiguities=("suffix-or-name",),
         notes="'ma'/'do' joined suffix_acronyms_ambiguous: with only "
               "two pieces, 'one of them is a credential' is the less "
               "likely reading, so the ambiguous acronym stays the "
               "family name (v1 parity via its reserve_last)"),
    Case("ambiguous_surname_acronym_with_suffix", "Jack MA Jr",
         {"given": "Jack", "family": "MA", "suffix": "Jr"},
         ambiguities=("suffix-or-name",),
         notes="'Jr' peels first; 'MA' would then be the only piece "
               "left beside the given name, so it stays family"),
    Case("ambiguous_acronym_is_a_suffix_when_a_family_name_remains",
         "John Smith MA",
         {"given": "John", "family": "Smith", "suffix": "MA"},
         ambiguities=("suffix-or-name",),
         notes="the other half of the same rule: three pieces means "
               "peeling 'MA' still leaves given+family, so the "
               "credential reading wins (v1 parity)"),
    Case("ambiguous_acronym_suffix_with_middle", "John Q Smith MA",
         {"given": "John", "middle": "Q", "family": "Smith",
          "suffix": "MA"},
         ambiguities=("suffix-or-name",)),
    Case("titled_ambiguous_particle_chains", "Dr. Van Johnson",
         {"title": "Dr.", "family": "Van Johnson"},
         ambiguities=("particle-or-given",),
         notes="the other branch of 'Van Johnson': a leading title "
               "shifts Van off the given position, the prefix chain "
               "fires, and the fork is reported from group rather than "
               "assign (v1 parity on the fields)"),
    Case("titled_ambiguous_particle_no_op_chain", "Dr. Van Jr.",
         {"title": "Dr.", "given": "Van", "suffix": "Jr."},
         notes="the piece after the particle is a suffix, so the chain "
               "scan never advances and the merge is a no-op -- nothing "
               "was chained, so there is no fork to report (the emitter "
               "fired here for all 39 ambiguous particles, and _assign "
               "double-reported the same token)"),
    Case("initial_shaped_not_conjunction", "john e. smith",
         {"given": "john", "middle": "e.", "family": "smith"},
         notes="v1 is_conjunction excludes initials at classify too"),
    Case("family_comma_lenient_trailing", "Smith, John V",
         {"given": "John", "family": "Smith", "suffix": "V"},
         notes="v1 #144: the trailing piece of a two-part comma name "
               "takes the lenient suffix test"),
    Case("family_comma_first_piece_is_given", "Steven Hardman, RN - CRNA",
         {"given": "RN", "middle": "-", "family": "Steven Hardman",
          "suffix": "CRNA"},
         notes="v1 walk order: the first post-comma piece is the given "
               "before any suffix check (the delimiter is UNSET here "
               "-- v1's documented limitation, kept)"),
    Case("family_comma_lone_suffix_piece", "Andrews, M.D.",
         {"family": "Andrews", "suffix": "M.D."},
         classification="fix(comma-family)",
         notes="v1 made the lone post-comma strict-suffix piece the "
               "given; 2.0 routes it to suffix (same family as the "
               "'Smith, Dr.' row)"),
    Case("period_joined_ambiguous_chunk", "John Doe, Msc.Ed.",
         {"given": "John", "family": "Doe", "suffix": "Msc.Ed."},
         notes="chunk-level suffix membership is v1's is_suffix: bare "
               "ambiguous acronyms count within period-joined tokens"),
    Case("suffix_comma_split_phd", "John Smith, Ph. D.",
         {"given": "John", "family": "Smith", "suffix": "Ph. D."},
         notes="the adjacent Ph./D. pair counts as one suffix unit in "
               "the suffix-comma detection (v1 fix_phd parity)"),
    Case("tail_segment_entry_space_joined", "John Smith, V MD",
         {"given": "John", "family": "Smith", "suffix": "V MD"},
         notes="v1 renders each tail comma segment as ONE suffix "
               "entry; words within an entry space-join via the "
               "'joined' tag"),
    Case("maiden_delimiters_win_when_shared",
         'Baker (Johnson), Jenny',
         {"given": "Jenny", "family": "Baker", "maiden": "Johnson"},
         policy=Policy(maiden_delimiters=frozenset({("(", ")")})),
         notes="listing a pair in maiden_delimiters drops it from the "
               "effective nickname set (maiden wins, 2026-07-19) -- the "
               "one-liner replaces the bucket-move idiom; the v1 facade "
               "keeps v1's nickname-wins precedence via the shim's "
               "pre-subtraction (pinned in test_config_shim)"),
    # #269 follow-up: Arabic-script bound given names, mirroring the
    # Latin transliterations' behavior (probed live 2026-07-19: bound
    # join fires only with 3+ tokens, eats the NEXT token into given;
    # two-token kunya stays split -- 'أبو مازن' pinned in test_locales;
    # non-leading أبو still prefix-chains onto family).
    Case("arabic_bound_given_abd", 'عبد الرحمن محمد',
         {"given": "عبد الرحمن", "family": "محمد"},
         classification="feat(#269)",
         notes="script twin of 'Abdul Rahman Mohammed'; عبد was the "
               "missing bound entry -- 1.x split it into given عبد + "
               "middle الرحمن"),
    Case("arabic_bound_given_kunya", 'أبو بكر أحمد',
         {"given": "أبو بكر", "family": "أحمد"},
         classification="feat(#269)"),
    Case("arabic_bound_given_kunya_hamzaless", 'ابو بكر احمد',
         {"given": "ابو بكر", "family": "احمد"},
         classification="feat(#269)",
         notes="both kunya spellings ship, like the أبو/ابو prefix pair"),
    Case("arabic_bound_given_umm", 'أم كلثوم إبراهيم',
         {"given": "أم كلثوم", "family": "إبراهيم"},
         classification="feat(#269)"),
    # #273: typographic nickname delimiters ship as defaults -- one row
    # per new pair; expectations verified live 2026-07-19 before the
    # pairs were added to DEFAULT_NICKNAME_DELIMITERS.
    Case("smart_double_quotes_nickname", 'John “Jack” Kennedy',
         {"given": "John", "family": "Kennedy", "nickname": "Jack"},
         classification="feat(#273)"),
    Case("low_high_quotes_nickname", 'Hans „Hansi“ Müller',
         {"given": "Hans", "family": "Müller", "nickname": "Hansi"},
         classification="feat(#273)",
         notes="the closing '“' doubles as the English pair's opener; "
               "no spurious unbalanced-delimiter ambiguity (pinned in "
               "test_extract)"),
    Case("guillemets_nickname_inner_spaces", 'Jean « Petit » Dupont',
         {"given": "Jean", "family": "Dupont", "nickname": "Petit"},
         classification="feat(#273)",
         notes="French spacing: inner padding is trimmed from the "
               "extracted nickname"),
    Case("reversed_guillemets_nickname", 'Hans »Hansi« Müller',
         {"given": "Hans", "family": "Müller", "nickname": "Hansi"},
         classification="feat(#273)"),
    Case("swedish_right_quotes_nickname", 'Anna ”Ann” Larsson',
         {"given": "Anna", "family": "Larsson", "nickname": "Ann"},
         classification="feat(#273)"),
    Case("cjk_corner_bracket_nickname", '山田「タロ」太郎',
         {"given": "山田", "family": "太郎", "nickname": "タロ"},
         classification="feat(#273)",
         notes="extraction also splits the unspaced remainder -- the "
               "masked region acts as a token boundary"),
    Case("cjk_white_corner_bracket_nickname", '田中『ハナ』花子',
         {"given": "田中", "family": "花子", "nickname": "ハナ"},
         classification="feat(#273)"),
    Case("fullwidth_paren_nickname", 'John （Jack） Kennedy',
         {"given": "John", "family": "Kennedy", "nickname": "Jack"},
         classification="feat(#273)"),
    Case("curly_apostrophe_stays_literal", 'Sean O’Connor',
         {"given": "Sean", "family": "O’Connor"},
         notes="U+2019 is the typographic apostrophe; curly single "
               "quotes are deliberately NOT delimiters (#273 excludes "
               "them)"),
    Case("family_segment_trailing_suffix", "Smith Jr., John",
         {"given": "John", "family": "Smith", "suffix": "Jr."},
         notes="v1: the family part may have suffixes in it "
               "(parser.py:1368); the first piece is always the family "
               "(pinned live 2026-07-17)"),
    Case("family_segment_multiple_suffixes", "Smith Jr. MD, John",
         {"given": "John", "family": "Smith", "suffix": "Jr., MD"}),
    Case("family_segment_particle_chain_suffix", "de la Vega III, Juan",
         {"given": "Juan", "family": "de la Vega", "suffix": "III"}),
    Case("interior_periods_block_vocab", "Smith, J.R.",
         {"given": "J.R.", "family": "Smith"},
         notes="v1's lc() keeps interior periods: 'J.R.' is not the "
               "title 'jr' (pinned live 2026-07-17)"),
    Case("dotted_acronym_suffix", "John Smith M.D.",
         {"given": "John", "family": "Smith", "suffix": "M.D."},
         notes="suffix-ACRONYM membership alone strips periods (v1 "
               "is_suffix parity)"),
    Case("nickname_rule_counts_whole_segment", "Xyz. (Bud) Smith",
         {"title": "Xyz.", "given": "Smith", "nickname": "Bud"},
         notes="v1's lone-piece nickname rule counts the segment "
               "BEFORE title peeling (parser.py:1285, pinned live "
               "2026-07-17)"),
    Case("suffix_comma_decided_by_first_segment",
         "Dr. John P. Doe-Ray, CLU, CFP, LUTC",
         {"title": "Dr.", "given": "John", "middle": "P.",
          "family": "Doe-Ray", "suffix": "CLU, CFP, LUTC"},
         ambiguities=("comma-structure",),
         notes="only parts[1] decides the suffix-comma structure "
               "(v1 parser.py:1318); 'lutc' is not in the vocabulary "
               "but rides along (v1 parity, pinned live 2026-07-16)"),
    Case("suffix_comma_nonsuffix_tail_flagged", "John Smith, MD, Xyzzy",
         {"given": "John", "family": "Smith", "suffix": "MD, Xyzzy"},
         ambiguities=("comma-structure",),
         notes="the unrecognized tail is consumed best-effort with the "
               "flag (v1 consumed it silently)"),
    Case("period_joined_titles", "Lt.Gov. John Doe",
         {"title": "Lt.Gov.", "given": "John", "family": "Doe"},
         notes="v1 derived-title rule: ANY period chunk being a title "
               "makes the token a title (pinned live 2026-07-16)"),
    Case("period_joined_suffixes", "John Doe JD.CPA",
         {"given": "John", "family": "Doe", "suffix": "JD.CPA"}),
    Case("period_joined_any_rule", "Mr.Smith",
         {"title": "Mr.Smith"},
         notes="the ANY rule is deliberate v1 parity: one title chunk "
               "claims the whole token"),
    Case("doubled_comma_suffix", "Doe,, Jr.",
         {"family": "Doe", "suffix": "Jr."},
         notes="the EMPTY given segment keeps its position: 'Jr.' is a "
               "tail suffix, not a lone post-comma title (v1 parity, "
               "pinned live 2026-07-16)"),
    Case("doubled_comma_given_kept", "Doe, John,, Jr.",
         {"given": "John", "family": "Doe", "suffix": "Jr."}),
    Case("single_trailing_comma_cosmetic", "John,",
         {"given": "John"},
         notes="v1 collapse_whitespace strips exactly ONE trailing "
               "comma before parsing"),
    Case("double_trailing_comma_structural", "Doe,,",
         {"family": "Doe"},
         notes="one trailing comma is cosmetic, the second is "
               "structural: an empty given segment makes this a "
               "family-comma parse (v1 parity, pinned live 2026-07-16)"),
    Case("doubled_comma_blocks_suffix_comma", "John Smith,, MD",
         {"family": "John Smith", "suffix": "MD"},
         notes="an empty segment 1 fails the suffix-comma detection "
               "(v1 parity)"),
    Case("suffix_delimiter_tail_segment", "Doe, John, RN - CRNA",
         {"given": "John", "family": "Doe", "suffix": "RN, CRNA"},
         policy=_SD,
         notes="v1 suffix_delimiter parity (#191): the delimiter token "
               "is dropped from consumed tail segments (pinned live "
               "2026-07-16)"),
    Case("suffix_delimiter_detection", "Doe, John RN - CRNA",
         {"given": "John", "middle": "-", "family": "Doe",
          "suffix": "RN, CRNA"},
         policy=_SD,
         notes="the delimiter fires only at suffix sites; the stray "
               "token keeps its per-piece walk role (v1 parity, pinned "
               "live 2026-07-16)"),
    Case("suffix_delimiter_suffix_comma", "John Smith, RN - CRNA",
         {"given": "John", "family": "Smith", "suffix": "RN, CRNA"},
         policy=_SD,
         notes="delimiter transparency in the SUFFIX_COMMA "
               "determination: the post-comma segment counts as "
               "all-suffix (v1 parity, pinned live 2026-07-16)"),
    Case("suffix_delimiter_no_space_core", "John Smith, RN/CRNA",
         {"given": "John", "family": "Smith", "suffix": "RN/CRNA"},
         policy=Policy(extra_suffix_delimiters=frozenset({"/"})),
         classification="fix(suffix-delimiter-rendering)",
         notes="v1 split 'RN/CRNA' and rendered 'RN, CRNA'; v2 keeps "
               "the token whole (anti-#100) with Role.SUFFIX -- role "
               "assignment matches, rendering differs (migration plan "
               "deviation 5, release-log classified)"),
    Case("suffix_delimiter_name_segment_untouched", "Doe, Mary - Kate, RN",
         {"given": "Mary", "middle": "- Kate", "family": "Doe",
          "suffix": "RN"},
         policy=_SD,
         notes="a delimiter token in a NAME segment is kept (v1 parity, "
               "pinned live 2026-07-16)"),
    Case("comma_extras_become_suffixes", "Smith, John, Extra, Jr.",
         {"given": "John", "family": "Smith", "suffix": "Extra, Jr."},
         ambiguities=("comma-structure",),
         notes="post-comma segments land in suffix even when not "
               "suffix-shaped; the ambiguity flags the guess (v1 "
               "parity, pinned live 2026-07-13)"),
    Case("delavega", "Dr. Juan de la Vega III",
         {"title": "Dr.", "given": "Juan", "family": "de la Vega",
          "suffix": "III"}),
    Case("prefix_chain_to_end", "Juan de la Vega Martinez",
         {"given": "Juan", "family": "de la Vega Martinez"}),
    Case("van_johnson", "Van Johnson",
         {"given": "Van", "family": "Johnson"},
         ambiguities=("particle-or-given",),
         notes="v2 surfaces #121's irreducible ambiguity"),
    Case("family_comma_particles", "de la Vega, Juan",
         {"given": "Juan", "family": "de la Vega"}),
    Case("paren_suffix_escapes_nickname", "Andrew Perkins (MBA)",
         {"given": "Andrew", "family": "Perkins", "suffix": "MBA"},
         notes="v1 parse_nicknames: suffix-shaped delimited content is "
               "left in place for normal parsing (pinned live "
               "2026-07-17)"),
    Case("paren_period_escapes_nickname", "Andrew Perkins (Ret.)",
         {"given": "Andrew", "family": "Perkins", "suffix": "Ret."}),
    Case("nickname_quotes", 'John "Jack" Kennedy',
         {"given": "John", "family": "Kennedy", "nickname": "Jack"}),
    Case("nickname_parens", "John (Jack) Kennedy",
         {"given": "John", "family": "Kennedy", "nickname": "Jack"}),
    Case("sir_bob", "Sir Bob Andrew Dole",
         {"title": "Sir", "given": "Bob", "middle": "Andrew",
          "family": "Dole"}),
    Case("long_title", "President of the United States Barack Obama",
         {"title": "President of the United States",
          "given": "Barack", "family": "Obama"}),
    Case("secretary", "The Secretary of State Hillary Clinton",
         {"title": "The Secretary of State", "given": "Hillary",
          "family": "Clinton"}),
    Case("comma_middle_initial", "Doe, John A.",
         {"given": "John", "middle": "A.", "family": "Doe"}),
    Case("single", "John", {"given": "John"}),
    Case("title_only", "Dr.", {"title": "Dr."}),
    Case("double_comma_suffix", "Smith, John, Jr.",
         {"given": "John", "family": "Smith", "suffix": "Jr."}),
    Case("bound_given_two", "abdul rahman",
         {"given": "abdul", "family": "rahman"}),
    Case("bound_given_three", "abdul rahman al-said",
         {"given": "abdul rahman", "family": "al-said"}),
    Case("mr_and_mrs", "Mr. and Mrs. John Smith",
         {"title": "Mr. and Mrs.", "given": "John", "family": "Smith"}),
    Case("roman_suffix", "John Smith V",
         {"given": "John", "family": "Smith", "suffix": "V"},
         ambiguities=("suffix-or-name",),
         notes="a trailing single letter is a name part unless it is a "
               "roman numeral; V/X/I are also ordinary middle initials, "
               "so the reading is reported"),
    Case("initial_not_suffix", "John V. Smith",
         {"given": "John", "middle": "V.", "family": "Smith"}),
    Case("lenient_after_comma", "John Ingram, V",
         {"given": "John", "family": "Ingram", "suffix": "V"}),
    Case("comma_then_title", "Smith, Dr. John",
         {"title": "Dr.", "given": "John", "family": "Smith"}),
    Case("nickname_single_name", "John (Jack)",
         {"family": "John", "nickname": "Jack"}),
    Case("nickname_only", "(Jack)", {"nickname": "Jack"}),
    Case("suffix_run", "John Jack Kennedy PhD MD",
         {"given": "John", "middle": "Jack", "family": "Kennedy",
          "suffix": "PhD, MD"}),
    Case("maiden_marker", "Jane Smith née Jones",
         {"given": "Jane", "family": "Smith", "maiden": "Jones"},
         classification="fix(#274)",
         notes="v1 mangles to middle='Smith née'"),
    Case("east_slavic", "Сидоров Иван Петрович",
         {"given": "Иван", "middle": "Петрович", "family": "Сидоров"},
         policy=_ES),
    Case("turkic", "Mammadova Aygun Ali kizi",
         {"given": "Aygun", "middle": "Ali kizi", "family": "Mammadova"},
         policy=_TK),
    Case("ru_pack_formal_rotation", "Сидоров Иван Петрович",
         {"given": "Иван", "middle": "Петрович", "family": "Сидоров"},
         locale="ru",
         notes="the RU pack end-to-end: same expectation as the "
               "east_slavic synthetic row, through parser_for"),
    Case("ru_pack_transliterated", "Petrov Ivan Sergeyevich",
         {"given": "Ivan", "middle": "Sergeyevich", "family": "Petrov"},
         locale="ru"),
    Case("ru_pack_comma_untouched", "Петров, Иван",
         {"given": "Иван", "family": "Петров"},
         locale="ru",
         notes="a comma is an explicit signal that suppresses the "
               "rotation (spec §1)"),
    Case("tr_az_pack_marker", "Mammadova Aygun Ali kizi",
         {"given": "Aygun", "middle": "Ali kizi", "family": "Mammadova"},
         locale="tr_az",
         notes="the TR_AZ pack end-to-end: same expectation as the "
               "turkic synthetic row (pinned live during Plan 3), "
               "through parser_for"),
    Case("empty", "", {}),
    Case("whitespace", "   ", {}),
    Case("bare_ambiguous_acronym", "John Ed",
         {"given": "John", "family": "Ed"},
         ambiguities=("suffix-or-name",),
         notes="'ed' is an ambiguous acronym; bare form is a name (C1), "
               "and the parse reports which reading it took"),
    Case("comma_ambiguous_acronym", "Smith, Ed",
         {"given": "Ed", "family": "Smith"}),
    Case("ambiguous_acronym_with_suffix", "John Ed III",
         {"given": "John", "family": "Ed", "suffix": "III"},
         ambiguities=("suffix-or-name",)),
    Case("phd_split", "John Ph. D.",
         {"given": "John", "suffix": "Ph. D."},
         notes="v1 fix_phd; healed via the stable 'joined' tag"),
    Case("phd_split_mid_name", "Dr. John Ph. D. Smith",
         {"title": "Dr.", "given": "John", "family": "Smith",
          "suffix": "Ph. D."}),
    Case("leading_never_given_particle", "de la Vega",
         {"family": "de la Vega"},
         notes="v1 handle_non_first_name_prefix: never-given leading "
               "particle folds the whole name into family"),
    Case("unbalanced_quote", 'Jon "Nick Smith',
         {"given": "Jon", "middle": '"Nick', "family": "Smith"},
         ambiguities=("unbalanced-delimiter",),
         notes="quote char stays literal (spec §5a)"),
    Case("suffix_stays_suffix", "Johnson PhD",
         {"given": "Johnson", "suffix": "PhD"},
         classification="fix(suffix-routing)",
         notes="v1 routes a lone trailing suffix to family "
               "(first=Johnson last=PhD); v2 keeps recognized "
               "suffixes in suffix"),
    Case("suffix_stays_suffix_title", "Mr. Johnson PhD",
         {"title": "Mr.", "given": "Johnson", "suffix": "PhD"},
         classification="fix(suffix-routing)",
         notes="v1 routes a lone trailing suffix to family "
               "(title=Mr. first=Johnson last=PhD); v2 keeps "
               "recognized suffixes in suffix"),
    Case("family_comma_lone_title", "Smith, Dr.",
         {"title": "Dr.", "family": "Smith"},
         classification="fix(comma-family)",
         notes="pre-comma is definitionally family; v1 put it in first"),
)
