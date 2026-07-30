import dataclasses
import pickle
import unicodedata

import pytest

from nameparser import (
    Lexicon, Locale, Parser, Policy, PolicyPatch, locales, parse, parser_for,
)
from nameparser._policy import (
    FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST, PatronymicRule,
)
from nameparser._types import AmbiguityKind, Role, Segmentation


def test_parser_defaults_and_properties() -> None:
    p = Parser()
    assert p.lexicon == Lexicon.default()
    assert p.policy == Policy()


def test_parser_rejects_wrong_types_eagerly() -> None:
    with pytest.raises(TypeError, match="lexicon"):
        Parser(lexicon={"titles": set()})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="policy"):
        Parser(policy="strict")  # type: ignore[arg-type]


def test_parse_end_to_end_with_default_vocabulary() -> None:
    pn = parse("Dr. Juan de la Vega III")
    assert pn.title == "Dr."
    assert pn.given == "Juan"
    assert pn.family == "de la Vega"
    assert pn.suffix == "III"
    assert str(pn) == "Dr. Juan de la Vega III"


def test_parse_rejects_non_str_with_decode_hint() -> None:
    with pytest.raises(TypeError, match="decode"):
        parse(b"John Smith")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="str"):
        parse(None)  # type: ignore[arg-type]


def test_degenerate_inputs_are_total() -> None:
    # spec §5a table
    assert not parse("")
    assert not parse("   ")
    assert parse("").original == ""
    # an input with no alphanumeric character is not a name (v1 kept it)
    assert not parse(".,")
    assert not parse("- -")
    assert parse(".,").original == ".,"     # but the raw input is kept
    single = parse("John")
    assert single.given == "John"
    family_first = Parser(policy=Policy(name_order=FAMILY_FIRST))
    assert family_first.parse("Yamada").family == "Yamada"
    title_only = parse("Dr.")
    assert title_only.title == "Dr." and not title_only.given
    unbalanced = parse('Jon "Nick Smith')
    kinds = {a.kind for a in unbalanced.ambiguities}
    assert AmbiguityKind.UNBALANCED_DELIMITER in kinds
    assert '"Nick' in [t.text for t in unbalanced.tokens]  # literal


def test_parser_is_picklable_and_frozen() -> None:
    p = Parser(policy=Policy(name_order=FAMILY_FIRST))
    loaded = pickle.loads(pickle.dumps(p))
    assert loaded == p
    assert loaded.parse("Yamada Taro").family == "Yamada"
    with pytest.raises(AttributeError):
        p.policy = Policy()  # type: ignore[misc]


def test_parser_repr_composes_component_reprs() -> None:
    assert repr(Parser()) == "Parser(Lexicon(default), Policy())"
    p = Parser(policy=Policy(name_order=FAMILY_FIRST))
    assert repr(p) == "Parser(Lexicon(default), Policy(name_order=FAMILY_FIRST))"


def test_parsedname_repr_includes_ambiguities_line() -> None:
    pn = parse("Van Johnson")
    r = repr(pn)
    assert "given: 'Van'" in r
    assert "ambiguities:" in r and "particle-or-given" in r


def test_module_parse_reuses_the_default_parser() -> None:
    import nameparser._parser as parser_mod
    assert parser_mod._default_parser() is parser_mod._default_parser()


def test_parser_for_stacks_locales() -> None:
    ru = Locale(code="ru",
                lexicon=Lexicon.empty().add(titles={"г-н"}),
                policy=PolicyPatch(patronymic_rules=frozenset(
                    {PatronymicRule.EAST_SLAVIC})))
    p = parser_for(ru)
    assert PatronymicRule.EAST_SLAVIC in p.policy.patronymic_rules
    pn = p.parse("г-н Сидоров Иван Петрович")
    assert pn.title == "г-н"
    assert pn.given == "Иван"
    assert pn.family == "Сидоров"


def test_parser_for_rejects_non_locales() -> None:
    with pytest.raises(TypeError, match="Locale"):
        parser_for("ru")  # type: ignore[arg-type]


def test_parser_for_wraps_pack_errors_with_identity() -> None:
    # PolicyPatch validates lazily (by design), so an invalid value sits
    # latent in a perfectly constructible Locale until apply time
    bad = Locale(code="xx", lexicon=Lexicon.empty(),
                 policy=PolicyPatch(name_order=(1, 2, 3)))  # type: ignore[arg-type]
    # the rewrap preserves the taxonomy's exception type (here the
    # non-Role element TypeError) while adding the pack identity
    with pytest.raises(TypeError, match="while applying locale 'xx'"):
        parser_for(bad)


def test_parser_for_warns_on_scalar_conflict() -> None:
    a = Locale(code="aa", lexicon=Lexicon.empty(),
               policy=PolicyPatch(strip_emoji=False))
    b = Locale(code="bb", lexicon=Lexicon.empty(),
               policy=PolicyPatch(strip_emoji=True))
    with pytest.warns(UserWarning, match="strip_emoji"):
        p = parser_for(a, b)
    assert p.policy.strip_emoji is True  # later wins


def test_matches_component_wise_case_insensitive() -> None:
    pn = parse("John Smith")
    assert pn.matches("JOHN SMITH")
    assert pn.matches(parse("john smith"))
    assert not pn.matches("John Smythe")
    with pytest.raises(TypeError, match="str or ParsedName"):
        pn.matches(42)  # type: ignore[arg-type]


def test_family_first_given_last_places_middle_between() -> None:
    # T1: the three-piece FAMILY_FIRST_GIVEN_LAST assignment -- family
    # from the front, given from the END, middle between (not a rotation
    # of FAMILY_FIRST)
    p = Parser(policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST))
    pn = p.parse("Zeng Xiao Long")
    assert (pn.family, pn.middle, pn.given) == ("Zeng", "Xiao", "Long")


def test_multiple_unbalanced_delimiters_each_reported() -> None:
    # T4: the extract scan continues past the first unmatched opener;
    # each one is reported and treated as literal text
    pn = parse('John "Jack (Smith')
    unbalanced = [a for a in pn.ambiguities
                  if a.kind is AmbiguityKind.UNBALANCED_DELIMITER]
    assert len(unbalanced) == 2
    assert pn.given == "John" and pn.family == "(Smith"
    assert not pn.nickname


def test_matches_accepts_explicit_parser() -> None:
    family_first = Parser(policy=Policy(name_order=FAMILY_FIRST))
    pn = family_first.parse("Yamada Taro")
    assert pn.matches("Yamada Taro", parser=family_first)
    assert not pn.matches("Yamada Taro")  # default parser reads given-first


def test_phd_split_heals_in_the_suffix_view() -> None:
    # v1 parity via fix_phd: the split credential renders as one suffix
    assert parse("John Ph. D.").suffix == "Ph. D."
    assert parse("John Smith PhD MD").suffix == "PhD, MD"  # unchanged


def test_phd_split_mid_name_is_a_suffix() -> None:
    # v1 parity: fix_phd extracted the credential BEFORE parsing, so
    # position never mattered; the merged piece is a suffix anywhere
    pn = parse("Dr. John Ph. D. Smith")
    assert pn.suffix == "Ph. D."
    assert pn.family == "Smith"
    assert pn.middle == ""


def test_ambiguous_acronym_reports_the_reading_it_took() -> None:
    # 'ma' is both a post-nominal and a surname, so whichever way the
    # peel resolves it is a guess -- the same shape as the leading
    # ambiguous particle that already reports PARTICLE_OR_GIVEN
    took_suffix = parse("John Smith MA")
    assert took_suffix.suffix == "MA"
    assert [a.kind for a in took_suffix.ambiguities] == \
        [AmbiguityKind.SUFFIX_OR_NAME]
    assert [t.text for t in took_suffix.ambiguities[0].tokens] == ["MA"]

    took_family = parse("Jack MA")
    assert took_family.family == "MA"
    assert [a.kind for a in took_family.ambiguities] == \
        [AmbiguityKind.SUFFIX_OR_NAME]


@pytest.mark.parametrize("text", [
    "John Smith M.A.",                   # periods decide it; no guess
    "Ma, Jack",                          # a comma fixes the family
    "Joao da Silva do Amaral de Souza",  # 'do' mid-name, never at the peel
    "John Smith PhD",                    # unambiguous vocabulary
])
def test_no_suffix_ambiguity_when_nothing_was_guessed(text: str) -> None:
    assert [a for a in parse(text).ambiguities
            if a.kind is AmbiguityKind.SUFFIX_OR_NAME] == []


def test_delimited_ambiguous_acronym_reports_suffix_or_nickname() -> None:
    # inside delimiters the competing readings are suffix and nickname:
    # "(MBA)" is unambiguously a credential and escapes to suffix, while
    # "(JD)" could be either, so it keeps the nickname reading -- a
    # guess, and until now a silent one
    n = parse("JEFFREY (JD) BRICKEN")
    assert n.nickname == "JD"
    assert [a.kind for a in n.ambiguities] == \
        [AmbiguityKind.SUFFIX_OR_NICKNAME]
    assert [t.text for t in n.ambiguities[0].tokens] == ["JD"]
    # the unambiguous one decided on vocabulary, so it is not a guess
    assert parse("Andrew Perkins (MBA)").ambiguities == ()


def test_every_ambiguous_acronym_in_a_name_is_reported() -> None:
    # one coin-flip per acronym: a single-slot record dropped all but
    # the last, which defeats the point of reporting at all
    n = parse("John Smith MA JD")
    assert n.suffix == "MA, JD"
    assert [a.kind for a in n.ambiguities] == \
        [AmbiguityKind.SUFFIX_OR_NAME] * 2
    assert sorted(t.text for a in n.ambiguities for t in a.tokens) == \
        ["JD", "MA"]


def test_ambiguous_acronym_detail_names_the_role_it_got() -> None:
    # the unpeeled piece is the last NAME piece, which is the family
    # name only under GIVEN_FIRST -- FAMILY_FIRST puts it in given, so
    # the detail has to follow the role actually assigned
    fam_first = Parser(policy=Policy(name_order=FAMILY_FIRST))
    n = fam_first.parse("Jack MA")
    assert (n.family, n.given) == ("Jack", "MA")
    assert "given name" in n.ambiguities[0].detail
    assert "family name" not in n.ambiguities[0].detail


def test_trailing_roman_numeral_reports_the_fork() -> None:
    # a trailing single letter is a name part unless it happens to be a
    # roman numeral, in which case it is silently reclassified -- and
    # V/X/I are common middle initials, so this is a real coin-flip
    numeral = parse("John Smith V")
    assert numeral.suffix == "V"
    assert [a.kind for a in numeral.ambiguities] == \
        [AmbiguityKind.SUFFIX_OR_NAME]
    assert [t.text for t in numeral.ambiguities[0].tokens] == ["V"]
    # the same shape with a non-numeral letter faces no fork
    assert parse("John Smith B").ambiguities == ()
    # and a numeral after an initial is not treated as a suffix at all
    assert parse("John Q. V").ambiguities == ()


def test_ambiguous_particle_reports_both_branches_of_its_fork() -> None:
    # "Van Johnson" reads Van as a given name and says so. A leading
    # title shifts Van off index 0, the prefix-chain merge fires, and
    # Van becomes a particle instead -- the SAME fork, called the other
    # way. The two branches are taken in different stages (_assign vs
    # _group), so only the one with an emitter used to report.
    given_reading = parse("Van Johnson")
    assert given_reading.given == "Van"
    assert [a.kind for a in given_reading.ambiguities] == \
        [AmbiguityKind.PARTICLE_OR_GIVEN]

    particle_reading = parse("Dr. Van Johnson")
    assert particle_reading.family == "Van Johnson"
    assert [a.kind for a in particle_reading.ambiguities] == \
        [AmbiguityKind.PARTICLE_OR_GIVEN]
    assert [t.text for t in particle_reading.ambiguities[0].tokens] == ["Van"]


def test_unambiguous_particle_chain_reports_nothing() -> None:
    # 'de' is never a given name, so merging it is not a fork
    assert parse("Dr. de la Vega").ambiguities == ()


@pytest.mark.parametrize("text", [
    "Dr. Van Jr.",      # the piece after the particle is a suffix, so
    "Dr. Van MD",       # the chain scan never advances and merge() is
    "Dr. Do Jr.",       # a no-op -- nothing was chained, no fork taken
])
def test_no_op_prefix_chain_is_not_a_fork(text: str) -> None:
    assert parse(text).ambiguities == ()


def test_a_fork_is_reported_by_exactly_one_stage() -> None:
    # the no-op merge left the particle a lone leading piece, which is
    # _assign's trigger, so both stages reported the same token
    n = parse("Dr. Van Jr Smith")
    assert n.given == "Van"
    assert len(n.ambiguities) == 1


def test_chained_particle_detail_does_not_claim_a_role() -> None:
    # _group runs before assignment, so it cannot know which field the
    # chained piece lands in -- "Dr. Van Johnson de la Cruz" puts it in
    # GIVEN. The detail must describe the decision, not guess a role.
    n = parse("Dr. Van Johnson de la Cruz")
    assert n.given == "Van Johnson"
    (amb,) = n.ambiguities
    assert "family name" not in amb.detail


def test_each_suffix_or_name_branch_describes_itself() -> None:
    # one kind, two causes: the acronym branch turns on periods, the
    # roman-numeral branch turns on the letter being a numeral. Sharing
    # one template made "V written without periods" -- a distinction
    # that does not exist for V -- and hid which branch fired.
    acronym = parse("John Smith MA").ambiguities[0].detail
    assert "periods" in acronym and "post-nominal" in acronym

    numeral = parse("John Smith V").ambiguities[0].detail
    assert "periods" not in numeral
    assert "numeral" in numeral and "initial" in numeral


def test_parser_matches_uses_its_own_config() -> None:
    p = Parser(lexicon=Lexicon.default().add(titles=["moff"]))
    a = p.parse("Moff Tarkin")
    # ParsedName.matches falls back to the DEFAULT parser for the str
    # argument, which reads "Moff" as a given name -- mismatch.
    assert not a.matches("Moff Tarkin")
    # Parser.matches parses the str with the same config -- match.
    assert p.matches(a, "Moff Tarkin")
    assert p.matches("Moff Tarkin", "MOFF TARKIN")


def test_parser_matches_rejects_wrong_types() -> None:
    p = Parser()
    with pytest.raises(TypeError, match="takes str or ParsedName"):
        p.matches(42, "John Smith")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="takes str or ParsedName"):
        p.matches("John Smith", 42)  # type: ignore[arg-type]


def test_parser_capitalized_uses_its_own_lexicon() -> None:
    # pair-tuples, not a dict: the field is tuple-annotated and typed
    # call sites pass canonical pairs (see _default_lexicon's note)
    exceptions = dict(
        Lexicon.default().capitalization_exceptions_map) | {"zqx": "ZqX"}
    lex = dataclasses.replace(
        Lexicon.default(),
        capitalization_exceptions=tuple(sorted(exceptions.items())))
    p = Parser(lexicon=lex)
    n = p.parse("john zqx")
    assert p.capitalized(n).family == "ZqX"
    # ParsedName.capitalized() with no argument uses the DEFAULT
    # lexicon, which has no such exception.
    assert n.capitalized().family == "Zqx"


def test_parser_capitalized_rejects_non_parsed_name() -> None:
    with pytest.raises(TypeError, match="takes a ParsedName"):
        Parser().capitalized("john smith")  # type: ignore[arg-type]


def test_revise_preserves_particle_tags() -> None:
    p = Parser()
    n = p.parse("Juan de la Vega")
    r = p.revise(n, family="de la Vega Smith")
    assert r.family == "de la Vega Smith"
    assert r.family_particles == "de la"
    assert r.initials() == "J. V. S."   # particles contribute no initial


def test_revise_keeps_multiword_suffix_one_credential() -> None:
    p = Parser()
    n = p.parse("John Smith Ph.D.")
    r = p.revise(n, suffix="Ph. D.")
    assert r.suffix == "Ph. D."         # replace() would render "Ph., D."


def test_revise_views_match_a_fresh_parse() -> None:
    p = Parser()
    r = p.revise(p.parse("John Smith"), family="de la Vega")
    f = p.parse("John de la Vega")
    for view in ("given", "family", "family_particles", "family_base"):
        assert getattr(r, view) == getattr(f, view)
    assert r.initials() == f.initials()


def test_revise_replace_shared_semantics() -> None:
    p = Parser()
    n = p.parse("Dr. Juan de la Vega Jr.")
    r = p.revise(n, given="José", suffix="")
    assert r.given == "José"
    assert r.suffix == ""               # empty value clears the field
    assert p.revise(n, suffix="()").suffix == ""   # punctuation-only too
    assert r.original == n.original     # provenance unchanged
    assert all(t.span is None for t in r.tokens_for("given"))
    assert r.title == "Dr."             # untouched fields keep spans


def test_revise_validation_matches_replace() -> None:
    p = Parser()
    n = p.parse("John Smith")
    with pytest.raises(TypeError, match="takes a ParsedName"):
        p.revise("John Smith", family="Doe")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="unknown field 'last'"):
        p.revise(n, last="Doe")
    with pytest.raises(TypeError, match="must be a str"):
        p.revise(n, family=None)  # type: ignore[arg-type]


def test_revise_strips_the_fold_marker() -> None:
    # middle_as_family's fold tag must not survive the harvest: a
    # carried tag would make the family view reorder the value.
    p = Parser(policy=Policy(middle_as_family=True))
    r = p.revise(p.parse("Juan Perez"), family="Gabriel García Márquez")
    assert r.family == "Gabriel García Márquez"


def test_revise_sub_parse_structural_behavior() -> None:
    # the docstring's three structural promises, pinned: delimiters
    # never become tokens, marker words are consumed as in parsing,
    # and the sub-parse's ambiguities are discarded.
    p = Parser()
    n = p.parse("John Smith")
    assert p.revise(n, family="Smith (Jones)").family == "Smith Jones"
    revised = p.revise(n, family="Mary née Smith")
    assert revised.family == "Mary Smith"
    assert revised.maiden == ""
    assert p.revise(n, given="J.R. 'Bob'").given == "J.R. Bob"
    assert p.revise(n, family="Smith (Jones").ambiguities == ()


def test_revise_forces_the_named_role_on_every_harvested_token() -> None:
    # the sub-parse reads "Dr." as a title and "Jr." as a suffix; the
    # named field's role must win for every token or the family view
    # silently drops them
    p = Parser()
    r = p.revise(p.parse("John Smith"), family="Dr. Vega Jr.")
    assert r.family == "Dr. Vega Jr."
    assert all(t.role is Role.FAMILY for t in r.tokens_for(Role.FAMILY))


def test_wholly_cjk_names_read_family_first_by_default() -> None:
    # the 2026-07-27 amendment: script determines the convention, so
    # no pack is needed -- release-log-classified fix (#271)
    n = parse("毛 泽东")
    assert (n.family, n.given) == ("毛", "泽东")
    n = parse("김 민준")
    assert (n.family, n.given) == ("김", "민준")
    # a lone wholly-CJK token takes the script order's first role: Han
    # segmentation is opt-in (locales.ZH), so the default parser leaves
    # this one token whole and reads it as the family name
    assert parse("毛泽东").family == "毛泽东"


def test_nfd_korean_input_still_reads_family_first() -> None:
    # fix(#271) classification, landed via the #272 NFC-classification
    # amendment: NFD decomposes each Hangul syllable onto bare jamo,
    # entirely outside the HANGUL range, so raw NFD input used to miss
    # script_orders' family-first rule and fall back to the positional
    # default -- a live gap in #294's shipped behavior until
    # single_script started classifying an NFC-normalized copy.
    n = parse(unicodedata.normalize("NFD", "김 민준"))
    # classification-only: the rendered text is exactly what was
    # typed (still NFD, spans untouched), so compare NFC-normalized --
    # the point under test is the ORDER (family first), not encoding
    assert (unicodedata.normalize("NFC", n.family),
            unicodedata.normalize("NFC", n.given)) == ("김", "민준")
    # pinned, not just stated: a future tokenize-level normalize (the
    # tempting over-fix, and an anti-#100 violation) must fail here
    assert n.family == unicodedata.normalize("NFD", "김")


def test_kana_licensed_names_read_family_first_by_default() -> None:
    # the #272 amendment: hiragana identifies Japanese as certainly
    # as hangul identifies Korean -- release-log-classified fix
    n = parse("高橋 みなみ")
    assert (n.family, n.given) == ("高橋", "みなみ")
    n = parse("山田 エミ")    # kanji piece + katakana piece: native
    assert (n.family, n.given) == ("山田", "エミ")
    # lone kana-licensed token takes the family role, unsplit
    assert parse("高橋みなみ").family == "高橋みなみ"


def test_iteration_mark_counts_as_han() -> None:
    # 々 (U+3005) repeats the preceding kanji. It is Script=Han under
    # UAX #24 already, but it lives outside every CJK ideograph BLOCK,
    # and the classifier is a block table -- so without its singleton
    # entry a 佐々木 token was in no script at all: the name reversed,
    # and the token never reached the segmentation gate. The Script
    # property would have got this one right unaided; the block table
    # is what needed the special case.
    n = parse("佐々木 太郎")
    assert (n.family, n.given) == ("佐々木", "太郎")
    n = parse("野々村 真")
    assert (n.family, n.given) == ("野々村", "真")
    # and a lone one takes the family role like any other Han token
    assert parse("奈々").family == "奈々"


def test_pure_katakana_stays_positional() -> None:
    # transcribed foreign names keep their original (usually Western)
    # order; katakana alone licenses nothing
    n = parse("マイケル ジャクソン")
    assert (n.given, n.family) == ("マイケル", "ジャクソン")


def test_katakana_transcription_parses_by_its_divider() -> None:
    # the dot tells us where the parts meet; transcriptions keep the
    # source language's order, which the positional default provides
    n = parse("マイケル・ジャクソン")
    assert (n.given, n.family) == ("マイケル", "ジャクソン")


def test_nakaguro_split_han_tokens_take_the_han_order() -> None:
    # different code path from the katakana case above: splitting on
    # the dot here produces two PURE-HAN tokens (no kana involved), so
    # script_orders' family-first HAN entry fires, same as any other
    # two-token Han name -- the dot only decides where the split falls
    n = parse("高橋・一郎")
    assert (n.family, n.given) == ("高橋", "一郎")


def test_halfwidth_nakaguro_splits_at_parse_level_too() -> None:
    # decision, not accident: halfwidth kana classify as no script at
    # all (_SCRIPT_RANGES only covers the fullwidth blocks), so this
    # is order-agnostic positional fallback, not a script-order rule --
    # the dot still divides the tokens regardless
    text = "ﾏｲｹﾙ･ｼﾞｬｸｿﾝ"
    n = parse(text)
    assert (n.given, n.family) == (
        "ﾏｲｹﾙ", "ｼﾞｬｸｿﾝ")


def test_nakaguro_inside_a_nickname_still_splits() -> None:
    # decision, not accident: delimited content tokenizes under the
    # same separator rules as the main stream, so a dot inside a
    # nickname still divides it -- and re-rendering a token stream
    # necessarily uses the render join, so the dot comes back as a
    # space, same as any other separator
    n = parse("山田 太郎 (マイケル・ジャクソン)")
    assert n.nickname == "マイケル ジャクソン"
    assert (n.family, n.given) == ("山田", "太郎")


def test_latin_names_are_untouched_by_script_orders() -> None:
    n = parse("John Smith")
    assert (n.given, n.family) == ("John", "Smith")
    # mixed-script names fall back to name_order too
    n = parse("John 王")
    assert (n.given, n.family) == ("John", "王")


def test_script_order_survives_latin_titles_and_suffixes() -> None:
    # The script test runs on the NAME pieces, after both peels, so a
    # Latin title or post-nominal cannot make the name look mixed.
    n = parse("Dr. 毛 泽东")
    assert (n.title, n.family, n.given) == ("Dr.", "毛", "泽东")
    n = parse("毛 泽东, PhD")
    assert (n.family, n.given, n.suffix) == ("毛", "泽东", "PhD")


def test_a_comma_still_decides_the_family_name_for_cjk() -> None:
    # The family-comma structure fixes the family before any positional
    # read, so the table is never consulted -- same rule name_order has.
    n = parse("泽东, 毛")
    assert (n.family, n.given) == ("泽东", "毛")


def test_three_cjk_pieces_take_the_script_order_middles() -> None:
    n = parse("毛 泽东 泽民")
    assert (n.family, n.given, n.middle) == ("毛", "泽东", "泽民")


def test_two_cjk_scripts_fall_back_even_though_both_read_family_first() -> None:
    # The rule is one script, or the Han/kana repertoire the #272
    # license covers -- not "the entries agree": Han+Hangul is written
    # in neither tradition, so it takes the positional default.
    n = parse("毛 김")
    assert (n.given, n.family) == ("毛", "김")


def test_a_hyphen_in_a_name_piece_declines_the_script_order() -> None:
    # Documenting the conservative direction, not proposing it: ANY
    # non-CJK character in a name piece (here the hyphen) puts that
    # piece in no script, so the piece set has two members and
    # script_orders declines in favour of the positional default.
    n = parse("毛 泽东-泽民")
    assert (n.given, n.family) == ("毛", "泽东-泽民")


def test_script_orders_opt_out_restores_positional_reading() -> None:
    p = Parser(policy=Policy(script_orders={}))  # type: ignore[arg-type]
    n = p.parse("毛 泽东")
    assert (n.given, n.family) == ("毛", "泽东")


def test_script_order_beats_explicit_global_name_order() -> None:
    # the script entry is the more specific rule; opting out means
    # script_orders={}, not a different name_order
    p = Parser(policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST))
    n = p.parse("김 민준")
    assert (n.family, n.given) == ("김", "민준")


def test_unspaced_korean_names_parse_by_default() -> None:
    # the whole point of shipping the census list as default
    # vocabulary (#271): no pack, no config
    n = parse("김민준")
    assert (n.family, n.given) == ("김", "민준")
    n = parse("남궁민수")     # two-syllable surname beats single 남
    assert (n.family, n.given) == ("남궁", "민수")


# -- the segmenter hook (#272) ------------------------------------------


def _module_level_decline(text: str) -> Segmentation | None:
    return None   # module-level so pickle can find it


# Inert sentinels for the plumbing tests below, which only ever compare
# identity. Two of them, because the override test needs the loser and
# the winner to be DISTINCT objects or its assertion is vacuous.
def _decline_a(text: str) -> Segmentation | None:
    return None


def _decline_b(text: str) -> Segmentation | None:
    return None


def test_parser_segmenter_is_keyword_only_and_validated() -> None:
    assert Parser().segmenter is None
    with pytest.raises(TypeError, match="callable"):
        Parser(segmenter=5)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="positional"):
        Parser(Lexicon.default(), Policy(), None)  # type: ignore[misc]  # positional: rejected


def test_parser_for_carries_the_base_segmenter() -> None:
    # not given: the base's carries through unchanged
    p = parser_for(locales.get("zh"), base=Parser(segmenter=_decline_a))
    assert p.segmenter is _decline_a


def test_parser_for_rejects_a_non_parser_base() -> None:
    with pytest.raises(TypeError, match="base must be a Parser"):
        parser_for(locales.get("zh"), base=5)  # type: ignore[arg-type]


def test_parser_for_takes_a_segmenter_keyword() -> None:
    p = parser_for(locales.get("zh"), segmenter=_decline_a)
    assert p.segmenter is _decline_a
    assert parser_for(locales.get("zh")).segmenter is None


def test_parser_for_segmenter_keyword_overrides_the_base() -> None:
    # later wins, the same rule scalar policy fields follow
    p = parser_for(locales.get("zh"), base=Parser(segmenter=_decline_a),
                   segmenter=_decline_b)
    assert p.segmenter is _decline_b


def test_parser_for_segmenter_none_clears_the_base() -> None:
    # the third state UNSET buys (#272 review): None is a VALUE here,
    # not an absence, so passing it explicitly drops the base's
    # segmenter instead of inheriting the very thing it was asked to
    # remove. Omitting the keyword is what carries the base's through
    # (the test above), and this is how you derive an unsegmented
    # parser from a segmented one without rebuilding its lexicon and
    # policy by hand.
    base = Parser(segmenter=_decline_a)
    pack = locales.get("zh")
    assert parser_for(pack, base=base, segmenter=None).segmenter is None
    # ...and the base is untouched: parser_for builds a fresh Parser
    assert base.segmenter is _decline_a


def test_parser_picklability_is_conditional_on_the_segmenter() -> None:
    # declared contract (locales spec section 4): Parser pickles iff
    # its segmenter does -- like any callable-holding object
    p = pickle.loads(pickle.dumps(Parser(segmenter=_module_level_decline)))
    assert p.segmenter is _module_level_decline
    unpicklable = Parser(segmenter=lambda t: None)  # constructs fine
    with pytest.raises(Exception):   # pickle's exception type varies
        pickle.dumps(unpicklable)    # only pickling fails


def test_segmenter_exceptions_propagate() -> None:
    # the ONE exception to parse-totality (locales spec section 4,
    # declared 2026-07-11): a user-supplied callable's own error is a
    # user-code error, not a content error, and must not be swallowed
    def boom(text: str) -> Segmentation | None:
        raise RuntimeError("segmenter bug")

    p = parser_for(locales.get("zh"), base=Parser(segmenter=boom))
    with pytest.raises(RuntimeError, match="segmenter bug"):
        p.parse("阿明")   # zh pack active, 阿 unmatched by vocabulary ->
                          # the stage consults the segmenter


def test_the_segmenter_sees_only_an_undivided_name() -> None:
    # its precondition (#272 Task 5): a segmenter answers where an
    # UNDIVIDED name divides, so a name part carrying a second
    # script-written token is already divided and the segmenter is not
    # consulted -- otherwise "山田 太郎" would have its family divided
    # again. A Latin title/suffix is not such a boundary.
    def always(text: str) -> Segmentation | None:
        return Segmentation((1,), confidence=1.0)

    p = parser_for(locales.get("zh"), base=Parser(segmenter=always))
    assert p.parse("阿明").family == "阿"          # one token: consulted
    n = p.parse("阿明 日月")                        # already divided
    assert (n.family, n.given) == ("阿明", "日月")
    assert p.parse("Dr 阿明").family == "阿"       # a title is not a split


def test_a_segmenter_split_reaches_the_fields() -> None:
    # end to end: the sub-slices the stage makes are ordinary tokens
    # from there on, so the pack's family-first order reads them like
    # any vocabulary split, and a low-confidence answer surfaces
    def two(text: str) -> Segmentation | None:
        return Segmentation((1,), confidence=0.5)

    p = parser_for(locales.get("zh"), base=Parser(segmenter=two))
    n = p.parse("阿明")
    assert (n.family, n.given) == ("阿", "明")
    assert [a.kind for a in n.ambiguities] == [AmbiguityKind.SEGMENTATION]

    # two cuts, three pieces -- and the token indices the comma
    # structure recorded still name the right words afterwards
    def three(text: str) -> Segmentation | None:
        return Segmentation((1, 2))

    q = parser_for(locales.get("zh"), base=Parser(segmenter=three))
    n3 = q.parse("Dr 阿明日, Jr.")
    assert (n3.title, n3.family, n3.given, n3.middle, n3.suffix) == (
        "Dr", "阿", "明", "日", "Jr.")
