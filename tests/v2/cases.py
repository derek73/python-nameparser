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
         {"family": "山田", "given": "太郎", "nickname": "タロ"},
         classification="feat(#273) + fix(#271)",
         notes="extraction also splits the unspaced remainder -- the "
               "masked region acts as a token boundary. Both name "
               "pieces are then wholly Han, so script_orders reads "
               "them family-first; the nickname's kana is outside the "
               "name pieces and does not enter that test"),
    Case("cjk_white_corner_bracket_nickname", '田中『ハナ』花子',
         {"family": "田中", "given": "花子", "nickname": "ハナ"},
         classification="feat(#273) + fix(#271)"),
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
    Case("phd_split_leading", "Ph. D. John Smith",
         {"given": "John", "family": "Smith", "suffix": "Ph. D."},
         classification="fix",
         notes="v1 healed 'Ph.'+'D.' only when trailing; leading it "
               "split them (title 'Ph.', given 'D.', real given name "
               "pushed to middle). Surfaced by the issue-tracker "
               "corpus, which is where this shape existed at all."),
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

    # -- #271: script-scoped order + segmentation (amendment 2026-07-27)
    Case("ko_unspaced_default", "김민준",
         {"family": "김", "given": "민준"},
         classification="fix(#271)",
         notes="hangul is unambiguously Korean: census surnames ship "
               "as default vocabulary and HANGUL segmentation is "
               "default-on"),
    Case("ko_two_syllable_surname_default", "남궁민수",
         {"family": "남궁", "given": "민수"},
         classification="fix(#271)",
         ambiguities=("segmentation",),
         notes="남 is itself a shipped surname; longest-first takes "
               "남궁 and records the decided fork"),
    Case("ko_bare_two_syllable_surname", "남궁",
         {"family": "남궁"},
         classification="fix(#271)",
         notes="a token that IS a surname never splits by its "
               "shorter prefix (남+궁); whole token takes the script "
               "order's first role; nothing was split, so no fork is "
               "recorded"),
    Case("ko_family_comma_stays_whole", "남궁민수, 지훈",
         {"family": "남궁민수", "given": "지훈"},
         classification="fix(#271)",
         notes="the comma already decided the family: segmentation "
               "is inert under FAMILY_COMMA (comma doctrine -- see "
               "the script_segment stage docstring, which uses this "
               "exact example)"),
    Case("ko_suffix_comma_name_part_splits", "Dr 김민준, Jr.",
         {"title": "Dr", "family": "김", "given": "민준", "suffix": "Jr."},
         classification="fix(#271)",
         notes="the one comma structure where segmentation still "
               "fires: a second word before the comma makes it "
               "SUFFIX_COMMA, and the name part is a full positional "
               "name"),
    Case("ko_spaced_family_first_default", "김 민준",
         {"family": "김", "given": "민준"},
         classification="fix(#271)",
         notes="script_orders, no segmentation involved"),
    Case("han_spaced_family_first_default", "毛 泽东",
         {"family": "毛", "given": "泽东"},
         classification="fix(#271)",
         notes="Han ORDER is default-safe without knowing zh from ja "
               "(both write family-first natively); only "
               "SEGMENTATION needs the zh opt-in"),
    Case("han_unspaced_unsegmented_default", "毛泽东",
         {"family": "毛泽东"},
         classification="fix(#271)",
         notes="no default Han segmentation: one token, and a lone "
               "wholly-Han token takes the script order's first "
               "role = family"),
    Case("mixed_script_untouched_by_script_orders", "John 王",
         {"given": "John", "family": "王"},
         notes="effective_script is None for a mixed name: script_orders "
               "declines and the positional default governs"),
    Case("two_han_scripts_untouched_by_script_orders", "毛 김",
         {"given": "毛", "family": "김"},
         notes="two scripts also decline -- the rule is one script, or "
               "the Han/kana repertoire the #272 license covers"),

    Case("zh_unspaced", "毛泽东",
         {"family": "毛", "given": "泽东"},
         locale="zh", classification="fix(#271)"),
    Case("zh_unspaced_two_char", "张伟",
         {"family": "张", "given": "伟"},
         locale="zh", classification="fix(#271)"),
    Case("zh_compound_tie_break", "夏侯惇",
         {"family": "夏侯", "given": "惇"},
         locale="zh", classification="fix(#271)",
         ambiguities=("segmentation",),
         notes="夏 (rank 65) is itself listed, so longest-first "
               "decides a real fork here and records it; most "
               "compounds' first chars are NOT listed"),
    Case("zh_compound_two_char_given", "司马相如",
         {"family": "司马", "given": "相如"},
         locale="zh", classification="fix(#271)"),
    Case("zh_traditional_compound", "諸葛亮",
         {"family": "諸葛", "given": "亮"},
         locale="zh", classification="fix(#271)"),
    Case("zh_no_surname_match", "阿明",
         {"family": "阿明"},
         locale="zh", classification="fix(#271)",
         notes="no surname prefix in the vocabulary: the token stays "
               "whole and takes the script order's first role"),
    Case("zh_japanese_kanji_tradeoff", "高橋一郎",
         {"family": "高", "given": "橋一郎"},
         locale="zh", classification="fix(#271)",
         notes="the RECORDED tradeoff, not a bug: applying the zh "
               "pack declares the data Chinese, so Japanese kanji "
               "names mis-split (高橋 is the real surname). This is "
               "why Han segmentation is opt-in and why the gate "
               "cannot guard it (DEVIATES declares all Han); "
               "Japanese data belongs under locales.JA and its "
               "segmenter instead"),

    # -- #272: the kana license + nakaguro (amendment 2026-07-29).
    # Segmenter-dependent divisions cannot live here (Case has no
    # segmenter field); they are pinned in test_locales.py's
    # integration tests instead.
    Case("ja_kana_spaced_family_first", "高橋 みなみ",
         {"family": "高橋", "given": "みなみ"},
         classification="fix(#272)",
         notes="hiragana identifies Japanese as certainly as hangul "
               "identifies Korean; kana-licensed names read "
               "family-first by default"),
    Case("ja_kanji_katakana_pieces", "山田 エミ",
         {"family": "山田", "given": "エミ"},
         classification="fix(#272)",
         notes="a kanji piece + a katakana piece cannot be a foreign "
               "transcription (those are katakana-only): native, "
               "licensed"),
    Case("ja_unspaced_unsegmented_default", "高橋みなみ",
         {"family": "高橋みなみ"},
         classification="fix(#272)",
         notes="no segmenter by default: one token, family role via "
               "the kana license"),
    Case("ja_pure_katakana_positional", "マイケル ジャクソン",
         {"given": "マイケル", "family": "ジャクソン"},
         notes="parity row guarding the license's boundary: "
               "pure-katakana is predominantly transcribed foreign "
               "names in original order -- never licensed"),
    Case("ja_nakaguro_divides_the_transcription", "マイケル・ジャクソン",
         {"given": "マイケル", "family": "ジャクソン"},
         classification="fix(#272)",
         notes="the katakana middle dot is the transcription's own "
               "part divider: it separates like whitespace, the "
               "license declines each katakana token, and the "
               "positional default keeps the source-language order"),
    Case("ja_nakaguro_han_takes_the_han_order", "高橋・一郎",
         {"family": "高橋", "given": "一郎"},
         classification="fix(#272)",
         notes="the dot splits; both tokens are pure Han, so the HAN "
               "family-first entry fires -- the katakana row's sibling "
               "through the other outcome"),
    Case("ja_lone_hiragana_takes_family", "みなみ",
         {"family": "みなみ"},
         classification="fix(#272)",
         notes="hiragana earns a script_orders entry in its own right: "
               "a lone token takes the entry's first role"),
    Case("ja_lone_katakana_stays_given", "マイケル",
         {"given": "マイケル"},
         notes="parity: katakana deliberately has no entry, so the "
               "positional default holds -- transcribed foreign names "
               "keep source order"),
    Case("ja_iteration_mark_is_han", "佐々木 太郎",
         {"family": "佐々木", "given": "太郎"},
         classification="fix(#272)",
         notes="々 (U+3005, the ideographic iteration mark) repeats "
               "the preceding kanji and is Script=Han under UAX #24, "
               "but sits outside every CJK ideograph BLOCK -- and the "
               "classifier is a block table, so it needs its own "
               "entry to count as Han; without one 佐々木 -- a top-20 "
               "Japanese surname -- would be a mixed-script token and "
               "reverse"),
    Case("ja_shime_mark_is_han", "〆木 太郎",
         {"family": "〆木", "given": "太郎"},
         classification="fix(shime-mark)",
         notes="〆 (U+3006, the shime mark) opens real Japanese "
               "surnames -- 〆木 Shimeki, 〆谷 Shimetani, 〆野 -- but "
               "carries Script=Common under UAX #24; the table counts "
               "it as Han anyway (a deliberate step PAST the Script "
               "property, unlike 々's), else 〆木 is a mixed-script "
               "token and the name reverses"),
    Case("ja_shime_lone_token_takes_family", "〆木太郎",
         {"family": "〆木太郎"},
         classification="fix(shime-mark)",
         notes="wholly-Han lone token under the family-first entry: "
               "the whole token lands in family, unsegmented by "
               "default"),
    Case("ja_shime_with_kana_given", "〆木 ひろ",
         {"family": "〆木", "given": "ひろ"},
         classification="fix(shime-mark)",
         notes="the kana license composes with the widened Han span: "
               "〆木 reads as kanji beside a kana given name"),
    Case("ja_nakaguro_inside_a_nickname",
         "山田 太郎 (マイケル・ジャクソン)",
         {"family": "山田", "given": "太郎",
          "nickname": "マイケル ジャクソン"},
         classification="fix(#272)",
         notes="delimited content tokenizes under the same separator "
               "rules: the dot renders back as a space in the nickname "
               "join -- a decision, not an accident"),
    Case("zh_interpunct_transcription_source_order", "威廉·莎士比亚",
         {"given": "威廉", "family": "莎士比亚"},
         classification="fix(#298)",
         notes="间隔号-divided Han is a transcribed foreign name and "
               "keeps source order -- the B7 is the transcription "
               "marker, playing the role pure katakana plays in the "
               "kana license; it divides only between classified "
               "characters"),
    Case("zh_interpunct_nakaguro_typed_stays_roster", "威廉・莎士比亚",
         {"given": "莎士比亚", "family": "威廉"},
         classification="fix(#272)",
         notes="the SAME transcription typed with the Japanese "
               "nakaguro reads as the dot's own typography says -- a "
               "姓・名 roster pair, family-first (#272) -- because the "
               "nakaguro records nothing (spec 2026-07-30 decision 5: "
               "codepoint-scoped; only the Chinese B7 marks a "
               "transcription). A limitation row: chosen, not "
               "accidental -- cross-convention input reads by the "
               "convention of the codepoint it was typed with"),
    Case("ja_interpunct_b7_katakana", "マイケル·ジャクソン",
         {"given": "マイケル", "family": "ジャクソン"},
         classification="fix(#298)",
         notes="sloppy-IME B7 between katakana divides like the "
               "nakaguro; katakana was never licensed, so order was "
               "already positional -- the split is the fix"),
    Case("latin_punt_volat_is_name_interior", "Gal·la Marcet",
         {"given": "Gal·la", "family": "Marcet"},
         notes="the Catalan punt volat: U+00B7 with Latin neighbors "
               "is interior to the name, never a divider -- the flank "
               "guard's whole reason"),
    Case("zh_interpunct_suppresses_segmentation", "马丁·路德·金",
         {"given": "马丁", "middle": "路德", "family": "金"},
         locale="zh",
         classification="fix(#298)",
         notes="马 is a listed zh surname, but a 间隔号-divided name "
               "is a transcription: the dot gates segmentation off, "
               "so 马丁 stays whole and the positional read stands"),
    Case("ko_interpunct_transcription_source_order", "마이클·잭슨",
         {"given": "마이클", "family": "잭슨"},
         classification="fix(#298)",
         notes="Korean writes transcribed foreign names with the "
               "interpunct too: the dot suppresses the hangul "
               "family-first entry AND the default segmentation -- 마 "
               "is a listed census surname, and the spaced form "
               "마이클 잭슨 really does mis-split 마|이클 today, so "
               "the dot is what rescues the ko transcription"),
    Case("zh_interpunct_with_suffix_comma", "威廉·莎士比亚, PhD",
         {"given": "威廉", "family": "莎士比亚", "suffix": "PhD"},
         classification="fix(#298)",
         notes="the transcription reading composes with a suffix "
               "comma: the marker is structure-independent"),
    Case("zh_interpunct_half_flanked_stays", "王·Smith",
         {"given": "王·Smith"},
         notes="one classified neighbor is not enough: the guard "
               "requires both, so the undivided dot remains part of "
               "the word -- declining, not deciding"),
    Case("zh_honorific_suffix_spaced", "王小明 先生",
         {"family": "王小明", "suffix": "先生"},
         classification="fix(#307)",
         notes="CJK honorifics FOLLOW the name; a spaced 先生 (Mr.) is "
               "a suffix, and recognizing it must come before the "
               "family-first order hands it a role -- unrecognized it "
               "read as the GIVEN name under the 2.1 defaults"),
    Case("ko_honorific_ssi", "김민준 씨",
         {"family": "김", "given": "민준", "suffix": "씨"},
         classification="fix(#307)",
         notes="Korean orthography standardly SPACES 씨, so the "
               "whole-token suffix machinery reaches it; the name "
               "still segments (suffix classification runs after the "
               "script_segment stage, which only ever saw 김민준)"),
    Case("ko_degree_baksa", "김민준 박사",
         {"family": "김", "given": "민준", "suffix": "박사"},
         classification="fix(#307)",
         notes="박사 (doctorate) is the ko analogue of a trailing "
               "PhD: fix(suffix-routing)'s two-token shape, one "
               "script over"),
    Case("ja_sama_spaced", "田中 太郎 様",
         {"family": "田中", "given": "太郎", "suffix": "様"},
         classification="fix(#307)",
         notes="the spaced 様 of forms and databases; the glued "
               "mail-addressing form 山田太郎様 is #308's mechanism, "
               "out of reach of whole-token matching"),
    Case("ja_san_spaced", "田中 さん",
         {"family": "田中", "suffix": "さん"},
         classification="fix(#308)",
         notes="the kana honorifics ship as suffix vocabulary so the "
               "glued peel has somewhere to hand its tail; spaced "
               "recognition falls out of the same entry -- until this "
               "change さん read as the given name under the "
               "family-first default"),
    Case("ja_san_glued", "田中さん",
         {"family": "田中", "suffix": "さん"},
         classification="fix(#308)",
         notes="the everyday glued form, and the one that also "
               "corrupted classification: 田中さん is Han plus "
               "hiragana, so the kana license read the whole string "
               "as a Japanese name. The peel runs before the license "
               "is consulted, so it now sees 田中 alone"),
    Case("ja_sama_glued", "山田太郎様",
         {"family": "山田太郎", "suffix": "様"},
         classification="fix(#308)",
         notes="the mail-addressing form. Undivided without a "
               "segmenter -- no surname list divides a kanji name -- "
               "so the family name is the whole 山田太郎; "
               "tests/v2/test_locales.py pins the divided twin under "
               "locales.JA"),
    Case("ko_honorific_nim_glued", "김민준님",
         {"family": "김", "given": "민준", "suffix": "님"},
         classification="fix(#308)",
         notes="the online/formal glued address form, 씨's twin"),
    Case("ko_honorific_glued_teacher", "김선생님",
         {"family": "김", "suffix": "선생님"},
         classification="fix(#307)",
         notes="longest-first, end to end: 선생님 peels whole where "
               "님 alone would have left 김선생 to segment into a "
               "family 김 and a given 선생. Classified to #307 "
               "because the fields do not move in this change -- "
               "segmentation already delivered this shape (김 is a "
               "listed surname, so the split reached it); #308 "
               "changes which mechanism gets there first"),
    Case("latin_stem_glued_kana_honorific", "Andersonさん",
         {"given": "Anderson", "suffix": "さん"},
         classification="fix(#308)",
         notes="no script precondition on the remainder -- the tail "
               "is the license. Japanese text about a foreigner, and "
               "the Latin remainder keeps the positional default"),
    Case("latin_stem_glued_hangul_honorific", "Anderson선생님",
         {"given": "Anderson", "suffix": "선생님"},
         classification="fix(#308)",
         notes="the hangul twin of latin_stem_glued_kana_honorific, "
               "and the one that shows why a post-nominal is not a "
               "surname site: 선 is a listed census surname, so the "
               "peeled 선생님 would otherwise be split into 선 + 생님 "
               "-- the stage dissecting the honorific it had just "
               "manufactured"),
    Case("ko_glued_stack_peels_once", "김민준박사님",
         {"family": "김", "given": "민준박사", "suffix": "님"},
         classification="fix(#308)",
         notes="one peel, no recursion -- and the remainder 김민준박사 "
               "ends in a listed tail of its own, so this is the "
               "shape that would recurse if anything did. 님 comes "
               "off, the glued 박사 stays in the given name. Accepted "
               "and pinned rather than chased"),
    Case("ko_glued_tail_alone_never_peels", "씨",
         {"family": "씨"},
         classification="fix(#271)",
         notes="the empty-remainder guard: a token that IS a tail has "
               "nothing to peel off. Classified to #271 because that "
               "is what moves the lone token from first to family; "
               "the row exists for the guard"),
    Case("ko_honorific_token_alone_stays_whole", "선생님",
         {"family": "선생님"},
         classification="fix(#308)",
         notes="a lone honorific is not a name to be taken apart: it "
               "is not a peel site (every tail is a suffix word) and "
               "not a surname site, though 선 is listed and the "
               "default segmentation split it 선 + 생님 before this "
               "change"),
    Case("ja_glued_tail_alone_never_peels", "さん",
         {"family": "さん"},
         classification="fix(#272)",
         notes="the kana twin of the row above; the field placement "
               "is the kana-licensed order default, not the peel"),
    Case("ja_glued_degree_stays", "田中博士",
         {"family": "田中博士"},
         classification="fix(#271)",
         notes="the exclusion pinned: glued 田中博士 IS Tanaka "
               "Hiroshi, an attested given name, so 博士 never peels "
               "-- it stays recognized in the SPACED position only, "
               "where the writer's own token boundary settles it"),
    Case("zh_glued_jun_stays", "王君",
         {"family": "王君"},
         classification="fix(#271)",
         notes="likewise: 君 is a common Chinese given-name final, so "
               "王君 is a complete name, not Mr. Wang"),
    Case("zh_glued_shi_stays", "王氏",
         {"family": "王氏"},
         classification="fix(#271)",
         notes="likewise: 王氏 is a historical name form ('the Wang "
               "woman'). The spaced 田中氏 keeps its entry"),
    Case("ja_dono_spaced", "田中 殿",
         {"family": "田中", "suffix": "殿"},
         classification="fix(#308)",
         notes="殿 waited on an argument in #307 and gets one here: "
               "spaced it is safe for the reason 양/군 are -- a "
               "殿-surnamed person's name LEADS, and the suffix gate "
               "is trailing-only -- while glued it would cut 鵜殿 and "
               "真殿 in two, so it ships spaced only"),
    Case("ko_honorific_nim_spaced", "김민준 님",
         {"family": "김", "given": "민준", "suffix": "님"},
         classification="fix(#308)",
         notes="님 is new in both sets -- #307 shipped only the -님 "
               "compounds 선생님/교수님. Standardly glued in online "
               "address, spaced too, and never the end of a Korean "
               "given name, which is what qualifies it for the "
               "harsher glued vetting as well"),
    Case("ko_honorific_glued_via_segmentation", "김씨",
         {"family": "김", "suffix": "씨"},
         classification="fix(#307)",
         notes="glued hangul is reached ONLY in the surname+honorific "
               "shape: default segmentation splits off the surname, "
               "and the honorific is what remains -- a partial "
               "delivery of #308 that falls out of stage order. A "
               "glued honorific after a GIVEN name (김민준씨, the row "
               "below) stays out of reach"),
    Case("ko_honorific_after_comma", "김민준, 씨",
         {"family": "김민준", "suffix": "씨"},
         classification="fix(#307)",
         notes="the post-comma lenient gate admits the honorific too; "
               "the comma disables segmentation per the comma "
               "doctrine, so 김민준 stays whole"),
    Case("ko_honorific_glued_given", "김민준씨",
         {"family": "김", "given": "민준", "suffix": "씨"},
         classification="fix(#308)",
         notes="the common full-name glued shape, and the row this "
               "replaces (ko_honorific_glued_given_stays) pinned the "
               "old boundary: 씨 peels off the last token first, and "
               "the remainder 김민준 then segments as usual -- peel "
               "and split compose, in that order"),
    Case("ko_honorific_glued_given_trailing_suffix", "김민준씨 Jr.",
         {"family": "김", "given": "민준", "suffix": "씨, Jr."},
         classification="fix(#308)",
         notes="the peel site is the last token that is not itself a "
               "post-nominal, so an unrelated trailing suffix cannot "
               "hide it -- this now agrees with the comma-written "
               "'Dr 김민준씨, Jr.', where the suffix comma had "
               "already put 씨 within reach"),
    Case("zh_honorific_glued_surname", "王先生",
         {"family": "王", "suffix": "先生"},
         locale="zh",
         classification="fix(#307)",
         notes="the Han twin of 김씨: the zh pack's segmentation "
               "splits off the surname and the remaining 先生 is the "
               "honorific token"),
    Case("zh_honorific_glued_given", "王小明先生",
         {"family": "王", "given": "小明", "suffix": "先生"},
         locale="zh",
         classification="fix(#308)",
         notes="the Han twin, replacing zh_honorific_glued_given_stays: "
               "先生 peels, and the zh pack's surname vocabulary then "
               "divides the remainder 王小明"),
    Case("zh_honorific_glued_given_default", "王小明先生",
         {"family": "王小明", "suffix": "先生"},
         classification="fix(#308)",
         notes="the same input WITHOUT the pack: the peel is default-on "
               "and script-independent, so the honorific still routes "
               "to suffix -- only the surname split needs the opt-in, "
               "so the undivided 王小明 stays one family name"),
    Case("ko_suffix_matching_is_whole_token", "김지양",
         {"family": "김", "given": "지양"},
         notes="지양 ENDS with the honorific 양 but is a given name: "
               "suffix matching is whole-token, never endswith -- the "
               "pin the differential rule's anchor mirrors at the "
               "name-string level. #308 leaves it alone too: 양 is "
               "excluded from the glued tail set for exactly this "
               "name"),
    Case("ko_surname_yang_leads", "양 미선",
         {"family": "양", "given": "미선"},
         notes="양 is both a top-tier surname (Yang) and a shipped "
               "honorific: position decides, and a surname LEADS -- "
               "the trailing-only suffix gate never sees it here"),
    Case("ko_honorific_stack", "김민준 박사 씨",
         {"family": "김", "given": "민준", "suffix": "박사, 씨"},
         classification="fix(#307)",
         notes="a trailing RUN of honorifics peels whole, like "
               "'Smith PhD MD' -- the multi-suffix loop the peel "
               "shares with Latin suffixes"),
)
