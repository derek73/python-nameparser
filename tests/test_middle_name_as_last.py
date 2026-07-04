from nameparser import HumanName
from nameparser.config import Constants
from tests.base import FlaggedConstantsTestBase, HumanNameTestBase


class MiddleNameAsLastFlagTests(HumanNameTestBase):

    def test_default_is_false(self) -> None:
        C = Constants()
        assert C.middle_name_as_last is False

    def test_can_set_true_via_constructor(self) -> None:
        C = Constants(middle_name_as_last=True)
        assert C.middle_name_as_last is True

    def test_does_not_affect_other_instance(self) -> None:
        C1 = Constants(middle_name_as_last=True)
        C2 = Constants()
        assert C1.middle_name_as_last is True
        assert C2.middle_name_as_last is False


class MiddleNameAsLastFoldTests(FlaggedConstantsTestBase):

    constants_kwargs = {"middle_name_as_last": True}

    def test_fold_no_comma(self) -> None:
        n = self.hn("Mohamad Ahmad Ali Hassan")
        self.m(n.first, "Mohamad", n)
        self.m(n.middle, "", n)
        self.m(n.last, "Ahmad Ali Hassan", n)

    def test_fold_comma_converges(self) -> None:
        no_comma = self.hn("Mohamad Ahmad Ali Hassan")
        comma = self.hn("Hassan, Mohamad Ahmad Ali")
        self.m(comma.first, no_comma.first, comma)
        self.m(comma.last, no_comma.last, comma)

    def test_title_and_suffix_preserved(self) -> None:
        n = self.hn("Dr. Mohamad Ahmad Hassan Jr")
        self.m(n.title, "Dr.", n)
        self.m(n.last, "Ahmad Hassan", n)
        self.m(n.suffix, "Jr", n)

    def test_suffix_preserved_comma_format(self) -> None:
        # Comma-delimited suffix takes a different code path than the
        # title/suffix no-comma case above; the fold must still apply.
        n = self.hn("Hassan, Mohamad Ahmad Ali, Jr.")
        self.m(n.first, "Mohamad", n)
        self.m(n.middle, "", n)
        self.m(n.last, "Ahmad Ali Hassan", n)
        self.m(n.suffix, "Jr.", n)

    def test_nickname_preserved(self) -> None:
        # Nicknames are stripped in pre_process(), before the fold runs.
        n = self.hn('Mohamad "Mo" Ahmad Ali Hassan')
        self.m(n.nickname, "Mo", n)
        self.m(n.middle, "", n)
        self.m(n.last, "Ahmad Ali Hassan", n)

    def test_no_middle_is_noop(self) -> None:
        n = self.hn("John Doe")
        self.m(n.first, "John", n)
        self.m(n.middle, "", n)
        self.m(n.last, "Doe", n)

    def test_single_token_is_noop(self) -> None:
        n = self.hn("Cher")
        self.m(n.first, "Cher", n)
        self.m(n.middle, "", n)
        self.m(n.last, "", n)

    def test_given_names_and_surnames_track_fold(self) -> None:
        n = self.hn("Mohamad Ahmad Ali Hassan")
        self.m(n.given_names, n.first, n)
        self.m(n.surnames, n.last, n)

    def test_last_prefixes_still_split_after_fold(self) -> None:
        # Unfolded this is first="Miguel", middle="da Silva do Amaral",
        # last="de Souza" (last_prefixes="de"). Folded, last_list becomes
        # ["da","Silva","do","Amaral","de","Souza"]; _split_last() strips
        # leading contiguous prefix words from the start, so only the
        # leading "da" is stripped ("Silva" is not a prefix, so scanning
        # stops there) — last_prefixes="da", not "de".
        n = self.hn("Miguel da Silva do Amaral de Souza")
        self.m(n.last_prefixes, "da", n)


class MiddleNameAsLastFlagOffTests(HumanNameTestBase):

    def test_default_constants_unaffected(self) -> None:
        n = HumanName("Mohamad Ahmad Ali Hassan")
        self.m(n.middle, "Ahmad Ali", n)
        self.m(n.last, "Hassan", n)


class MiddleNameAsLastWithPatronymicOrderTests(FlaggedConstantsTestBase):
    """Both localization flags on: patronymic reordering must settle
    first/middle/last before the fold collapses middle into last, per the
    design's stated ordering rationale (post_process() runs the patronymic
    hook before the middle_name_as_last hook)."""

    constants_kwargs = {"middle_name_as_last": True, "patronymic_name_order": True}

    def test_rotate_then_fold_no_comma(self) -> None:
        # patronymic_name_order rotates "Ivanov Petr Sergeyevich" to
        # first=Petr, middle=Sergeyevich, last=Ivanov; the fold then
        # collapses that settled middle into last.
        n = self.hn("Ivanov Petr Sergeyevich")
        self.m(n.first, "Petr", n)
        self.m(n.middle, "", n)
        self.m(n.last, "Sergeyevich Ivanov", n)

    def test_fold_applies_even_when_comma_suppresses_rotation(self) -> None:
        # A comma suppresses patronymic_name_order's rotation (_had_comma
        # guard), so middle stays "Sergeyevich" unrotated going into the
        # fold. The fold still absorbs it into last, producing the same
        # first/last as the no-comma case above via a different mechanism.
        n = self.hn("Ivanov, Petr Sergeyevich")
        self.m(n.first, "Petr", n)
        self.m(n.middle, "", n)
        self.m(n.last, "Sergeyevich Ivanov", n)
