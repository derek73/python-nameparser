"""THE shared behavior case table (core spec §7.2).

Format is fixed here, in the first pipeline PR, and never per-PR:
one Case per input, expected values for exactly the non-empty fields,
optional Policy/Locale context, and a mandatory classification --
"parity" (matches v1.4.0, pinned live 2026-07-12) or "fix(#N)" /
"fix(<slug>)" (an intentional 2.0 behavior change, annotated with its
issue or a design-decision slug). No silent expectation edits:
changing a row means changing its classification.

"UNDETERMINED" is a fourth value and a TEMPORARY one: a row added
before anyone has run its input against 1.4.0 carries it until the
comparison is made and it resolves to one of the three above. It is
not a standing category, and nothing enforces its removal -- a row
still wearing it is a row whose parity is simply unknown.

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
         notes="the spaced 様 of forms and databases, which whole-token "
               "matching reaches on its own; the glued "
               "mail-addressing form is ja_sama_glued below, reached "
               "by #308's peel instead"),
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
    Case("ja_honorific_glued_before_a_roman_suffix", "田中さん II",
         {"family": "田中", "suffix": "さん, II"},
         classification="fix(#308)",
         notes="an unrelated trailing suffix does not hide the peel "
               "site: the scan-back steps over II and peels さん off "
               "the token behind it. Half of the pair that pins "
               "_is_post_nominal's use of is_suffix_STRICT -- the "
               "other half is the row below, and swapping in "
               "is_suffix_lenient changes that one and not this one"),
    Case("ja_honorific_glued_before_an_initial", "田中さん V.",
         {"given": "田中さん", "family": "V."},
         notes="the strict/lenient discriminator, and the reason "
               "_is_post_nominal reads is_suffix_strict. Bare 'v' is "
               "a suffix word, but 'V.' is an initial and the strict "
               "test vetoes it -- so the scan-back stops HERE rather "
               "than stepping over it, finds no tail on 'V.', and "
               "does not peel. Under is_suffix_lenient it would step "
               "over and give given 田中, middle さん, family 'V.'. "
               "Parity besides: 1.4.0 read this first 田中さん / last "
               "'V.', which is these fields under the 2.0 names. "
               "Classification agrees with what classify does with "
               "the same token downstream -- 'V.' is a middle "
               "initial, not a post-nominal"),
    Case("ja_honorific_with_a_period_no_comma", "田中さん 様.",
         {"family": "田中", "suffix": "さん, 様."},
         classification="fix(#320)",
         notes="the SPACED form, and the example _vocab.is_initial's "
               "own docstring cites as what #320 cost. Same fields as "
               "the comma row below, reached without a comma: the peel "
               "scans segment 0 either way, and with '様.' no longer "
               "vetoed the scan-back steps over it onto 田中さん and "
               "peels さん. Worth its own row because it is the only "
               "one of the pair where the SCAN-BACK is what #320 "
               "fixes, and since #319 the only one where the PEEL "
               "depends on #320 at all: here '様.' shares the run with "
               "田中さん and has to be stepped over, while the comma "
               "form declines its post-comma run and never looks at "
               "'様.' in the peel. That decline does not carry the "
               "veto over -- is_wholly_suffix asks is_suffix_lenient "
               "under the default policy, which takes '様.' whether "
               "the veto is in place or not (see the row below) -- so "
               "restoring the veto strands さん HERE and nowhere else "
               "in the pair, giving given '田中さん', family '様.'. "
               "(Before #319 the distinction was structural -- "
               "FAMILY_COMMA flattened TWO runs before scanning where "
               "this has one -- which is no longer what separates "
               "them.) 1.4.0 read this first "
               "田中さん / last '様.', which is what 2.0 produced until "
               "#320: parity before, a classified change after"),
    Case("ja_honorific_period_does_not_stop_the_peel", "田中さん, 様.",
         {"family": "田中", "suffix": "さん, 様."},
         classification="fix(#320)",
         notes="the comma spelling of the row above, and since #319 a "
               "DIFFERENT dependence on #320. At #320 this row was "
               "about the peel: the veto made _is_suffix_strict say "
               "no of '様.', so the #312 scan-back stopped AT it as "
               "the site, found no listed tail there and abandoned, "
               "leaving さん glued to 田中 over one period. #319 then "
               "declined the post-comma run outright, and what is "
               "left here for #320 to fix is the ASSIGNMENT -- with "
               "the veto restored the peel still fires (family 田中, "
               "suffix さん) and only '様.' moves, to given. The "
               "fields and the classification are unchanged either "
               "way. CORRECTION, recorded here because commit "
               "4aff219's message claims otherwise and cannot be "
               "amended: the veto does NOT reach is_wholly_suffix "
               "under this row's DEFAULT policy, so it is not true "
               "that #319 merely handed the same veto to a different "
               "predicate. is_wholly_suffix selects is_suffix_lenient "
               "there, whose contract is suffix_words accepted "
               "unconditionally, BYPASSING the initial veto, and "
               "_normalize('様.') is '様', a suffix word -- so "
               "is_wholly_suffix(['様.']) is True veto or no veto, "
               "the run is declined either way, and simulating the "
               "veto PEELS さん here rather than stranding it. The "
               "is_wholly_suffix route to an abandoned peel exists "
               "only under Policy(lenient_comma_suffixes=False), "
               "which drops the call to is_suffix_strict and gives "
               "family '田中さん', given '様.'; this row does not set "
               "that knob, and "
               "ko_honorific_period_under_strict_comma_suffixes is "
               "the table's row for it. Was the "
               "shape of "
               "ja_honorific_glued_before_an_initial above, except "
               "that here the token stopping the scan is a real "
               "honorific rather than an initial, which is what makes "
               "it a bug rather than the intended veto. The structure "
               "is FAMILY_COMMA throughout -- SUFFIX_COMMA needs more "
               "than one word ahead of the comma and 田中さん is one -- "
               "so at #320 both runs were in the peel's reach and "
               "only the strict test's answer moved. "
               "1.4.0 read "
               "this first '様.' / last 田中さん, which is exactly what "
               "2.0 produced before this change -- the row sat at "
               "parity until #320 moved it"),
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
    Case("ko_honorific_written_with_a_period", "김민준, 씨.",
         {"family": "김민준", "suffix": "씨."},
         classification="fix(#320)",
         notes="the period-written form of ko_honorific_after_comma "
               "('김민준, 씨'), whose field ASSIGNMENT it must match "
               "and before #320 did not -- same roles, the suffix "
               "VALUE differing by the period it was written with. "
               "_normalize strips the trailing period, "
               "so the vocabulary sees 씨 either way -- the initial "
               "veto was the only thing rejecting the written form, "
               "and literally the veto: _is_suffix_piece is "
               "'vocab:suffix' in tags and 'initial' not in tags, and "
               "'씨.' carried both, so the suffix-shaped piece went to "
               "the given. 1.4.0 read this first '씨.' / last 김민준 -- "
               "the same fields 2.0 gave before this change, so the row "
               "was at parity and #320 is what moves it"),
    Case("ko_honorific_period_under_strict_comma_suffixes", "김민준, 씨.",
         {"family": "김민준", "suffix": "씨."},
         policy=Policy(lenient_comma_suffixes=False),
         classification="fix(#320)",
         notes="the row above under the knob that governs exactly this "
               "shape, and one of the table's three exercises of it "
               "(ja_honorific_glued_family_comma_strict_knob is the "
               "second, on the initial-shaped side of the same gap; "
               "ja_honorific_glued_family_comma_credential_pair_strict_"
               "knob is the third, showing where the knob changes "
               "nothing). "
               "lenient_comma_suffixes=False drops segment's post-comma "
               "test to the strict one, so a 'Family, Suffix' input "
               "whose suffix is INITIAL-SHAPED reads as a given-name "
               "initial instead ('John Smith, V' -> given 'V'). '씨.' "
               "is a single character plus a period, so it was in that "
               "class by shape, and before #320 the knob decided it: "
               "given '씨.' / family 김민준. It is out of the class now, "
               "and the honorific parses identically under both "
               "settings -- which is the claim this row exists to "
               "hold, since the knob's own documentation scopes it to "
               "the initial-shaped suffix words ('John Smith, V') and "
               "_script_segment names it as the setting that keeps a "
               "glued honorific inside the name in a neighbouring "
               "shape ('田中さん, V.' gives family '田中さん' under "
               "it). No v1 spelling exists for the knob "
               "(the facade runner skips this row), so the "
               "classification compares against 1.4.0's single "
               "reading, first '씨.' / last 김민준 -- the same fields "
               "2.0 gave under EITHER setting before this change"),
    Case("ko_honorific_with_a_period_no_comma", "김민준 씨.",
         {"given": "민준", "family": "김", "suffix": "씨."},
         classification="fix(#320)",
         notes="the period-written ko_honorific_ssi ('김민준 씨'), and "
               "#320 by a different route than the row above: the veto "
               "left '씨.' a NAME piece, and effective_script('씨.') is "
               "None because the trailing period defeats the "
               "wholly-one-script test, so script_orders declined for "
               "the whole name and the three pieces fell back to "
               "name_order -- given 김, middle 민준, family '씨.'. "
               "Hangul segmentation is NOT what moves: it divides "
               "김민준 identically either way, and only the order the "
               "pieces are read in changes. 1.4.0 read this first "
               "김민준 / last '씨.' -- undivided, no suffix. The only "
               "row of the three that already differed from 1.4.0 "
               "before this change, but it differed as given 김 / "
               "middle 민준 / family '씨.'; the fields above are #320's, "
               "not the segmenter's, so the row is classified to it -- "
               "as ko_honorific_ssi is classified to #307 without "
               "naming the same segmentation it also depends on"),
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
    Case("ko_honorific_glued_doctor", "김민준박사님",
         {"family": "김", "given": "민준", "suffix": "박사님"},
         classification="fix(#308)",
         notes="박사님 is one honorific, not 박사 plus 님, and ships "
               "as one entry: 선생님, 교수님 and 박사님 are the three "
               "standard -님 professional honorifics and the first two "
               "shipped without it, which stranded 박사 in the given "
               "name here and rendered the spaced 김민준 박사님 as two "
               "suffixes. This row USED to pin the one-peel rule "
               "(named ko_glued_stack_peels_once) on the reading that "
               "left 박사 behind; no shipped vocabulary now has that "
               "shape, so the pin lives at stage level with a "
               "synthetic lexicon -- test_script_segment.py's "
               "test_one_peel_never_a_stack"),
    Case("ko_honorific_glued_doctor_spaced", "김민준 박사님",
         {"family": "김", "given": "민준", "suffix": "박사님"},
         classification="fix(#308)",
         notes="the spaced twin, and the second half of the same gap: "
               "without a 박사님 entry the peel cut this token too -- "
               "it is not a whole-token suffix word, so 박사 + 님 came "
               "back as two suffixes for one honorific"),
    Case("ko_glued_tail_alone_never_peels", "씨",
         {"family": "씨"},
         classification="fix(#271)",
         notes="a token that IS a tail is not a peel site at all -- "
               "every tail is a suffix word, so the site scan steps "
               "past it and finds nothing else. NOT the length cap, "
               "which is never reached here. Classified to #271 "
               "because that is what moves the lone token from first "
               "to family; the row exists for the guard"),
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
         notes="the kana twin of ko_glued_tail_alone_never_peels, and "
               "of that row only: a lone さん carries none of "
               "ko_honorific_token_alone_stays_whole's risk, since no "
               "surname vocabulary is written in kana. The field "
               "placement is the kana-licensed order default, not the "
               "peel"),
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
         notes="likewise unpeeled: 君 is a common Chinese given-name "
               "final, so 王君 is a complete name, not Mr. Wang. "
               "Unlike its neighbours here, 君 is in NEITHER set -- "
               "there is no spaced entry to fall back on either, and "
               "only its kana spelling くん peels"),
    Case("zh_glued_shi_stays", "王氏",
         {"family": "王氏"},
         classification="fix(#271)",
         notes="likewise: 王氏 is a historical name form ('the Wang "
               "woman'). The spaced 田中氏 keeps its entry"),
    Case("ja_glued_dono_stays", "鵜殿",
         {"family": "鵜殿"},
         classification="fix(#271)",
         notes="the exclusion with the longest argument behind it and, "
               "until this row, the only one nothing held: adding 殿 "
               "back to GLUED_HONORIFICS passed the whole suite. 鵜殿 "
               "(Udono) is a real surname, one of roughly ninety "
               "Japanese surnames ending in 殿 (真殿, 大殿, ...), and a "
               "peeled 殿 would give family 鵜 with 殿 in suffix. It "
               "has to be the BARE surname: in a two-token 真殿 太郎 "
               "the site scan lands on 太郎 and the exclusion is never "
               "consulted, so only a lone surname discriminates. "
               "Classified to #271 like its neighbours, not parity: "
               "1.4 gave first 鵜殿 and no last, and it is the CJK "
               "order flip that makes the one token a family name"),
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
         notes="the one glued shape that was already reachable before "
               "#308, which is why this row stays fix(#307) where its "
               "neighbours are fix(#308): stage order alone delivered "
               "it, since segmentation split 김 off the front and the "
               "honorific was whatever remained. The peel now takes 씨 "
               "off the END before segmentation is consulted, so the "
               "route changed and these fields did not. The glued "
               "shapes that needed the peel to be reached at all are "
               "the rows around it (김민준씨 below)"),
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
    Case("ko_honorific_glued_given_suffix_comma", "Dr 김민준씨, Jr.",
         {"title": "Dr", "family": "김", "given": "민준",
          "suffix": "씨, Jr."},
         classification="fix(#308)",
         notes="the peel scans the NAME's runs, not the token stream: "
               "under a suffix comma that is segments[0] alone, a "
               "strict subset, and the peel site is found within it "
               "(a FAMILY comma is the one structure that splits the "
               "name across two runs, #312). Pairs with "
               "ko_honorific_glued_given_trailing_suffix, whose "
               "comma-less spelling of the same name reaches the same "
               "answer by the scan-back instead"),
    Case("ko_honorific_glued_given_nickname", "김민준씨 (Jimmy)",
         {"family": "김", "given": "민준", "suffix": "씨",
          "nickname": "Jimmy"},
         classification="fix(#308)",
         notes="the other half of scanning the NAME's runs: extracted "
               "content is still in the token stream at this stage but "
               "in NO segment, so the scan-back never reaches "
               "Jimmy. Scanning the tokens instead would take Jimmy as "
               "the site -- it is no post-nominal -- and lose the peel "
               "entirely, with 씨 back in the given name. Nothing else "
               "pins that choice: under NO_COMMA the two are otherwise "
               "the same run"),
    Case("ko_honorific_glued_given_nickname_family_comma",
         "김, 민준씨 (Jimmy)",
         {"family": "김", "given": "민준", "suffix": "씨",
          "nickname": "Jimmy"},
         classification="fix(#312)",
         notes="the family-comma half of the same argument, which the "
               "row above cannot make: there the two runs are one, so "
               "'flatten the name's segments' and 'take segments[0]' "
               "agree. Here the peel has to cross the comma AND still "
               "not reach Jimmy, so declining to cross whenever "
               "extract_delimited claimed something passes the row "
               "above and fails only here"),
    Case("ja_honorific_glued_family_comma", "田中さん, PhD",
         {"title": "PhD", "family": "田中", "suffix": "さん"},
         classification="fix(#312)",
         notes="the peel reaches 田中さん across the comma, though no "
               "longer by crossing it: since #319 is_wholly_suffix "
               "declines the post-comma run outright (PhD is suffix "
               "vocabulary and it is the whole run), so the scan never "
               "leaves segments[0] and never examines PhD at all. It "
               "did cross before, stepping OVER PhD because that "
               "spelling satisfies _is_post_nominal's strict test -- "
               "the same fields by the older route. The spaced "
               "田中さん PhD still peels that way, its single run "
               "holding both tokens, so the two spellings now agree on "
               "the outcome through DIFFERENT mechanisms; "
               "ja_honorific_glued_family_comma_suffixy_second_run "
               "cites this row for the outcome, not the route. Where "
               "PhD itself lands still differs "
               "between the two spellings -- suffix spaced, title "
               "post-comma -- and that is fix(comma-family)'s, not "
               "the peel's. The expectation bakes in TWO deviations "
               "from 1.4.0 and only one of them is #312's: the peel "
               "is, while first -> family is comma-family's, witnessed "
               "on pure Latin by family_comma_lone_title (1.4.0 first "
               "Smith, here family Smith) -- so no script-conditional "
               "rule is reaching that half"),
    Case("ja_honorific_glued_family_comma_suffixy_second_run",
         "田中さん, V.",
         {"given": "V.", "family": "田中", "suffix": "さん"},
         classification="fix(#319)",
         notes="under a family comma the peel scanned both runs on "
               "the premise that segments[1] is name text, and here it "
               "is not: segment picks FAMILY_COMMA when the pre-comma "
               "part is a single word, even where the post-comma part "
               "is entirely suffix-shaped, so the scan reached 'V.' -- "
               "which is_suffix_strict rejects as an initial where "
               "segment admitted the run on is_suffix_lenient. 'V.' "
               "was therefore the site, ended in no tail, and the peel "
               "was abandoned with さん still in the family name. #319 "
               "asks segment's own predicate (_vocab.is_wholly_suffix) "
               "instead of inferring name text from the structure: the "
               "run is declined, the scan stays inside segments[0], "
               "and さん peels off 田中さん as it always did without a "
               "second run. Same credential, three spellings, ONE "
               "answer FROM THE PEEL now -- this, '田中さん, PhD' "
               "above and '田中さん, Ph. D.' in "
               "ja_honorific_glued_family_comma_credential_pair below "
               "all reach 田中さん. Where the credential itself LANDS "
               "still differs by spelling (title 'PhD', given 'V.', "
               "suffix 'さん, Ph. D.'); that is assign's question, not the "
               "peel's, and this row is not a claim about it. Nor does "
               "the comma form now agree with its SPACED twin: "
               "ja_honorific_glued_before_an_initial ('田中さん V.') "
               "still does not peel, because under NO_COMMA there is "
               "one run and 'V.' is inside the name's own tokens where "
               "the scan-back legitimately stops -- declining a "
               "post-comma run does not reach it. Parity with 1.4.0 "
               "(first V., last 田中さん) until this change, which is "
               "what moves it; the 1.4.0 fields are still reachable "
               "through Policy(lenient_comma_suffixes=False), pinned "
               "by ja_honorific_glued_family_comma_strict_knob below"),
    Case("ja_honorific_glued_family_comma_credential_pair",
         "田中さん, Ph. D.",
         {"family": "田中", "suffix": "さん, Ph. D."},
         classification="fix(#319)",
         notes="the third of the three spellings #319 named, and the "
               "only one the Ph./D. merge reaches: is_wholly_suffix "
               "folds the adjacent pair into the single unit 'phd' "
               "(v1's fix_phd extracted the credential pre-parse), so "
               "the run counts as wholly suffix, the peel declines it, "
               "and さん comes off 田中さん exactly as in "
               "ja_honorific_glued_family_comma_suffixy_second_run "
               "above. The merge is also why this spelling is NOT the "
               "one to reach for when exercising "
               "Policy(lenient_comma_suffixes=False): 'phd' satisfies "
               "is_suffix_strict as readily as is_suffix_lenient, so "
               "the run is declined under EITHER setting and this row "
               "is identical under the knob, which "
               "ja_honorific_glued_family_comma_credential_pair_strict_"
               "knob below holds rather than leaving to the claim -- "
               "ja_honorific_glued_family_comma_strict_knob below uses "
               "'V.' because the initial-shaped words are where the "
               "two predicates actually part. Where the credential "
               "lands is a separate question and answers differently "
               "again: suffix here, title for 'PhD', given for 'V.' "
               "Measured: 1.4.0 gave first 田中さん / suffix 'Ph. D.' "
               "(fix_phd lifted the credential pre-parse, leaving a "
               "lone pre-comma word), so like "
               "ja_honorific_glued_family_comma above the expectation "
               "carries TWO deviations -- the peel is #319's, first -> "
               "family is comma-family's, which 2.0 already had before "
               "this change (family 田中さん / suffix 'Ph. D.')"),
    Case("ja_honorific_glued_family_comma_strict_knob", "田中さん, V.",
         {"family": "田中さん", "given": "V."},
         policy=Policy(lenient_comma_suffixes=False),
         classification="parity",
         notes="the same input as "
               "ja_honorific_glued_family_comma_suffixy_second_run "
               "above under the knob that keeps the pre-#319 answer, "
               "and one of the table's three exercises of it "
               "(ko_honorific_period_under_strict_comma_suffixes and "
               "ja_honorific_glued_family_comma_credential_pair_strict_"
               "knob are the others). The knob drops is_wholly_suffix "
               "to the "
               "strict predicate, which rejects 'V.' as an initial, so "
               "the post-comma run reads as name text after all, the "
               "scan crosses into it, 'V.' is the site, it ends in no "
               "listed tail and the peel is abandoned -- さん stays in "
               "the family name. Not a blanket freeze of pre-#319 "
               "behavior, and the row must not be read as one: it "
               "holds for the INITIAL-shaped suffix words ('V.', 'V', "
               "'I'), which is the whole of where the strict/lenient "
               "gap lives. The counterexample is the row above, "
               "ja_honorific_glued_family_comma_credential_pair: its "
               "Ph./D. pair merges to a form strict accepts too, so "
               "that run is "
               "declined and the peel fires under this setting as "
               "well -- pinned, not merely stated, by "
               "ja_honorific_glued_family_comma_credential_pair_strict_"
               "knob above. No v1 spelling exists for the knob, so the "
               "facade runner skips this row and the classification "
               "compares against 1.4.0's single reading of the same "
               "text, as the other exercise of the knob named above "
               "does: measured, 1.4.0 gave first 'V.' / last "
               "田中さん, which is field for field what the knob holds "
               "here -- parity, and the point of the knob"),
    Case("ja_honorific_glued_family_comma_credential_pair_strict_knob",
         "田中さん, Ph. D.",
         {"family": "田中", "suffix": "さん, Ph. D."},
         policy=Policy(lenient_comma_suffixes=False),
         classification="fix(#319)",
         notes="the counterexample the two rows above assert and "
               "neither measured: the knob does NOT freeze the "
               "pre-#319 reading in general, only for the "
               "initial-shaped suffix words. Here the Ph./D. merge "
               "folds the run into 'phd', which is_suffix_strict "
               "accepts as readily as is_suffix_lenient, so the run is "
               "declined and さん peels under this setting exactly as "
               "under the default -- field for field the same "
               "expectation as "
               "ja_honorific_glued_family_comma_credential_pair, which "
               "is the whole claim. Cheap to hold and worth holding "
               "separately, because the two rows differ only in the "
               "policy and a knob that started gating the decline "
               "wholesale would move this one alone. Same "
               "classification and the same two deviations as its "
               "default-policy twin (1.4.0: first 田中さん / suffix "
               "'Ph. D.'), which is also why the knob cannot be judged "
               "against a v1 spelling here -- there is none, so the "
               "facade runner skips this row as it does the other two "
               "knob rows"),
    Case("ko_honorific_glued_family_comma_suffixy_second_run",
         "김민준씨, V.",
         {"given": "V.", "family": "김민준", "suffix": "씨"},
         classification="fix(#319)",
         notes="ja_honorific_glued_family_comma_suffixy_second_run in "
               "hangul, and pinned because the decline reads no script "
               "at all: it asks is_wholly_suffix about the post-comma "
               "run and the peel's own scan-back about segments[0], "
               "both vocabulary questions, so a script-conditional "
               "regression would be invisible in a table whose every "
               "other witness to #319 is written in kana. The family "
               "stays 김민준 undivided -- the FAMILY comma gates the "
               "surname split off, so hangul segmentation never runs "
               "here and only the peel acts. 1.4.0 gave first 'V.' / "
               "last 김민준씨, peeling nothing"),
    Case("zh_honorific_glued_family_comma_suffixy_second_run",
         "王先生, V.",
         {"given": "V.", "family": "王", "suffix": "先生"},
         classification="fix(#319)",
         notes="the Han spelling of the row above, and the third "
               "script. 先生 is a shipped tail, so the peel fires with "
               "no locale opted in -- honorific_tails is licensed by "
               "the entries themselves rather than by "
               "Policy.segment_scripts, and HAN is not activated here "
               "(the family is what the peel left behind, not a "
               "vocabulary split). 1.4.0 gave first 'V.' / last "
               "王先生"),
    Case("ko_honorific_glued_family_comma_site_only_beyond_the_comma",
         "이, J.씨",
         {"given": "J.", "family": "이", "suffix": "씨"},
         classification="fix(#312)",
         notes="the limit of #319's decline, and the row that says why "
               "it carries a second condition. is_wholly_suffix reaches "
               "period_joined_vocab, which calls an interior-period "
               "token a suffix when ANY chunk is suffix vocabulary -- "
               "and every honorific tail is a suffix WORD by the "
               "Lexicon invariant, so 'J.씨' reads as suffix-shaped "
               "BECAUSE of the 씨 the peel exists to remove. Declining "
               "on that evidence does not move the peel elsewhere the "
               "way 田中さん, V. does: segments[0] is the lone 이, which "
               "ends in no tail, so the scan finds no site at all, "
               "nothing peels, and the given name goes to suffix "
               "glued to its honorific ('J.씨'). So the gate declines "
               "only where segments[0] holds a peel site of its own, "
               "and this input reaches the pre-#319 fields by having "
               "none. Not rescued by "
               "Policy(lenient_comma_suffixes=False) either, unlike the "
               "strict-knob row above: the knob picks between "
               "is_suffix_lenient and is_suffix_strict per token and "
               "period_joined_vocab is downstream of neither, so both "
               "settings call this run wholly suffix. 1.4.0 gave first "
               "'J.씨' / last 이 -- it peels nothing, so the deviation "
               "here is #312's crossing, which is what puts the site on "
               "'J.씨' in the first place"),
    Case("ko_honorific_glued_family_comma_site_in_both_runs",
         "김민준씨, J.씨",
         {"family": "김민준", "suffix": "씨, J.씨"},
         classification="fix(#319)",
         notes="the two-honorific input, where both runs hold a site "
               "and the decline therefore stands -- a deliberate choice "
               "between two readings rather than a fallout. Pre-#319 "
               "the scan crossed and took the LAST site, peeling the 씨 "
               "off the junk 'J.씨' and leaving the person's own "
               "honorific glued in the family name (given 'J.', family "
               "김민준씨, suffix 씨); now 씨 comes off 김민준씨 and "
               "'J.씨' is consumed whole as a suffix. It is also the "
               "row that rules out the narrower gate: declining only "
               "where the SECOND run has no peel site fixes "
               "ko_honorific_glued_family_comma_site_only_beyond_the_"
               "comma above and reverts this input to the pre-#319 "
               "reading, which is the worse of the two -- the same "
               "junk-tail reach "
               "ko_honorific_glued_given_suffix_comma_initial's note "
               "names under a suffix comma. 1.4.0 gave first 'J.씨' / "
               "last 김민준씨, peeling neither"),
    Case("ko_honorific_glued_family_comma_lone_post_nominal_before_it",
         "선생님, J.씨",
         {"given": "J.", "family": "선생님", "suffix": "씨"},
         classification="fix(#312)",
         notes="segments[0] is a single token that IS a listed tail "
               "entire, which the site scan skips as a post-nominal "
               "(the same guard that keeps 선생님 from being peeled to "
               "선생 + 님) -- so there is no site before the comma, the "
               "run beyond it is scanned after all, and the fields are "
               "the pre-#319 ones as in the 이 row above. Pinned "
               "because it separates asking for the site with the "
               "peel's own scan-back from asking the cheaper question, "
               "whether any token ENDS in a tail: the cheaper one "
               "counts 선생님, declines, and then finds nothing to cut "
               "-- 씨 lost into suffix 'J.씨'. Only the lone-token "
               "shape of that divergence is reachable, because the "
               "gate is asked only where the second run is ALREADY "
               "suffix-shaped, and SUFFIX_COMMA wants that plus more "
               "than one word before the comma -- so a FAMILY_COMMA "
               "reaching the gate failed on the word count. The count "
               "alone would not say it ('Dr 김민준, 지훈' has two words "
               "before the comma and is FAMILY_COMMA). "
               "1.4.0 gave first 'J.씨' / last 선생님"),
    Case("ko_honorific_glued_given_after_family_comma", "김, 민준씨",
         {"family": "김", "given": "민준", "suffix": "씨"},
         classification="fix(#312)",
         notes="under a family comma the name spans both segments and "
               "the honorific is on the GIVEN side, where the peel "
               "never looked before #312. Agrees with the spaced "
               "김 민준씨"),
    Case("ja_honorific_glued_given_after_family_comma", "田中, 太郎さん",
         {"family": "田中", "given": "太郎", "suffix": "さん"},
         classification="fix(#312)",
         notes="the Han twin of the row above"),
    Case("zh_interpunct_transcription_glued_honorific", "威廉·莎士比亚さん",
         {"given": "威廉", "family": "莎士比亚", "suffix": "さん"},
         classification="fix(#312)",
         notes="the dot still gates the surname split -- a "
               "transcription's pieces are syllable groups -- but an "
               "honorific glued to a transcribed name is still an "
               "honorific, so the peel crosses it. Agrees with the "
               "spaced 威廉·莎士比亚 さん"),
    Case("ja_honorific_glued_family_comma_no_site", "田中さん, 太郎",
         {"family": "田中さん", "given": "太郎"},
         notes="unchanged, and pinned because a naive fix breaks it: "
               "the site is the last NON-POST-NOMINAL token, which is "
               "太郎, so nothing peels -- exactly as in the spaced "
               "田中さん 太郎. #312 was originally filed naming this "
               "pair as a disagreement; it never was one"),
    Case("ko_honorific_glued_given_suffix_comma_initial", "Dr 김민준씨, V.",
         {"title": "Dr", "family": "김", "given": "민준",
          "suffix": "씨, V."},
         classification="fix(#308)",
         notes="fix(#308) rather than fix(#312) because the fields do "
               "not move in this change -- a SUFFIX comma keeps the "
               "whole name in segments[0], which is what the peel "
               "already scanned. The row is here as the end-to-end "
               "guard for the scoping #312 introduced: widen the scan "
               "to every segment and 'V.' becomes the site, since "
               "segment admits a post-comma run on is_suffix_lenient "
               "while the site scan asks is_suffix_strict and an "
               "initial fails it. 'V.' then ends in no tail, the peel "
               "is abandoned, and 씨 is back in the given name -- the "
               "original bug. It was the table's only witness to that "
               "widening until #319; ja_honorific_glued_family_comma_"
               "suffixy_second_run and "
               "ja_honorific_glued_family_comma_credential_pair notice "
               "it as well now, but from the FAMILY_COMMA side, where "
               "the guard is is_wholly_suffix rather than this "
               "structural scoping. Their strict-knob sibling does NOT "
               "join them: under the knob is_wholly_suffix is False on "
               "the same run, so the scan was already crossing into "
               "segments[1] and widening past it changes nothing. This "
               "row is still the only SUFFIX comma among the three. "
               "Its comma-less twin ja_honorific_glued_before_an_initial "
               "shows the same veto from the other side, where 'V.' is "
               "in the name's own run and so IS the site"),
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
         classification="fix(#271)",
         notes="지양 ENDS with the honorific 양 but is a given name: "
               "suffix matching is whole-token, never endswith -- the "
               "pin the differential rule's anchor mirrors at the "
               "name-string level. #308 leaves it alone too: 양 is "
               "excluded from the glued tail set for exactly this "
               "name. Classified to #271, not parity: 1.4 gave first "
               "김지양 and no last, and it is #271's hangul "
               "segmentation plus the CJK order flip that produces "
               "these two fields"),
    Case("ko_surname_yang_leads", "양 미선",
         {"family": "양", "given": "미선"},
         classification="fix(#271)",
         notes="양 is both a top-tier surname (Yang) and a shipped "
               "honorific: position decides, and a surname LEADS -- "
               "the trailing-only suffix gate never sees it here. "
               "Classified to #271, not parity: 1.4 gave first 양, "
               "last 미선, and it is the CJK order flip that swaps "
               "them"),
    Case("ko_honorific_yang_trails", "김민준 양",
         {"family": "김", "given": "민준", "suffix": "양"},
         classification="fix(#307)",
         notes="the other side of ko_surname_yang_leads: the same "
               "token trailing a name is 'Miss', and that is the whole "
               "argument shipping it -- suffixes.py singles 양 out "
               "(with 군) as the risk class it takes, a top-tier "
               "surname admitted to the vocabulary on the strength of "
               "position alone. Nothing pinned the trailing reading "
               "before this row, so the leading rows carried the pair "
               "by themselves. Classified to #307 like ko_honorific_ssi "
               "(1.4 gave first 김민준, last 양; the recognition and "
               "the order flip both move it) -- the point of the row "
               "is the twin below"),
    Case("ko_honorific_yang_written_with_a_period", "김민준 양.",
         {"family": "김", "given": "민준", "suffix": "양."},
         classification="fix(#320)",
         notes="the period-written twin, whose fields must equal the "
               "row above and before #320 did not (given 김, middle "
               "민준, family '양.' -- the veto kept '양.' a name piece, "
               "exactly ko_honorific_with_a_period_no_comma's route). "
               "The pair is the point: 양 is the shipped vocabulary's "
               "acknowledged risk, so if the 양/군 policy is ever "
               "tightened or withdrawn, both spellings have to move "
               "together and neither row can be adjusted alone. 군 "
               "gets no pair of its own -- it parses identically and "
               "is the SAFER half (no surname reading), so it would "
               "pin nothing these two do not. Classified to #320 like "
               "its 씨 counterpart: 1.4.0 read this first 김민준 / last "
               "'양.', and the fields above are the ones this change "
               "produced, not the segmenter's"),
    Case("ko_surname_yang_leads_a_segmentable_given", "양 지훈",
         {"family": "양", "given": "지훈"},
         classification="fix(#271)",
         notes="양 is a surname AND a shipped honorific, and 지 is a "
               "listed surname too -- so this is the name that "
               "catches a segmentation site scanning PAST the "
               "honorific reading of 양 into the given name. The "
               "first script-written token decides, and deciding "
               "includes deciding there is no surname site. "
               "Classified to #271, not parity: 1.4 gave first 양, "
               "last 지훈, and it is the CJK order flip that puts 양 "
               "in family -- nothing in #308 moves these fields"),
    Case("ko_honorific_stack", "김민준 박사 씨",
         {"family": "김", "given": "민준", "suffix": "박사, 씨"},
         classification="fix(#307)",
         notes="a trailing RUN of honorifics peels whole, like "
               "'Smith PhD MD' -- the multi-suffix loop the peel "
               "shares with Latin suffixes"),
)
