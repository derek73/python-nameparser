from nameparser import PatronymicRule, parse
from tests.base import FlaggedPolicyTestBase, ParsedNameTestBase


class MiddleNameAsLastFoldTests(FlaggedPolicyTestBase):

    policy_kwargs = {"middle_as_family": True}

    def test_fold_no_comma(self) -> None:
        n = self.hn("Mohamad Ahmad Ali Hassan")
        self.m(n.given, "Mohamad", n)
        self.m(n.middle, "", n)
        self.m(n.family, "Ahmad Ali Hassan", n)

    def test_fold_comma_converges(self) -> None:
        no_comma = self.hn("Mohamad Ahmad Ali Hassan")
        comma = self.hn("Hassan, Mohamad Ahmad Ali")
        self.m(comma.given, no_comma.given, comma)
        self.m(comma.family, no_comma.family, comma)

    def test_title_and_suffix_preserved(self) -> None:
        n = self.hn("Dr. Mohamad Ahmad Hassan Jr")
        self.m(n.title, "Dr.", n)
        self.m(n.family, "Ahmad Hassan", n)
        self.m(n.suffix, "Jr", n)

    def test_suffix_preserved_comma_format(self) -> None:
        # Comma-delimited suffix takes a different code path than the
        # title/suffix no-comma case above; the fold must still apply.
        n = self.hn("Hassan, Mohamad Ahmad Ali, Jr.")
        self.m(n.given, "Mohamad", n)
        self.m(n.middle, "", n)
        self.m(n.family, "Ahmad Ali Hassan", n)
        self.m(n.suffix, "Jr.", n)

    def test_nickname_preserved(self) -> None:
        # Nicknames are extracted before the fold runs.
        n = self.hn('Mohamad "Mo" Ahmad Ali Hassan')
        self.m(n.nickname, "Mo", n)
        self.m(n.middle, "", n)
        self.m(n.family, "Ahmad Ali Hassan", n)

    def test_no_middle_is_noop(self) -> None:
        n = self.hn("John Doe")
        self.m(n.given, "John", n)
        self.m(n.middle, "", n)
        self.m(n.family, "Doe", n)

    def test_single_token_is_noop(self) -> None:
        n = self.hn("Cher")
        self.m(n.given, "Cher", n)
        self.m(n.middle, "", n)
        self.m(n.family, "", n)

    def test_given_names_and_surnames_track_fold(self) -> None:
        n = self.hn("Mohamad Ahmad Ali Hassan")
        self.m(n.given_names, n.given, n)
        self.m(n.surnames, n.family, n)

    def test_particle_views_after_fold(self) -> None:
        # The folded family's particle and base views, as the core reads
        # them: every particle of the family is set apart, not only the
        # leading run -- a general reading, the same with no fold
        # (`da Silva do Amaral, Miguel` gives base 'Silva Amaral'), and
        # one rules/R2's "without its leading particles" does not
        # describe. The 2.x facade's last_prefixes read 'da' here; this
        # pins the core's reading until that is settled.
        n = self.hn("Miguel da Silva do Amaral de Souza")
        self.m(n.family, "da Silva do Amaral de Souza", n)
        self.m(n.family_particles, "da do de", n)
        self.m(n.family_base, "Silva Amaral Souza", n)


class MiddleNameAsLastFlagOffTests(ParsedNameTestBase):

    def test_default_constants_unaffected(self) -> None:
        n = parse("Mohamad Ahmad Ali Hassan")
        self.m(n.middle, "Ahmad Ali", n)
        self.m(n.family, "Hassan", n)


class MiddleNameAsLastWithPatronymicOrderTests(FlaggedPolicyTestBase):
    """Both localization flags on: patronymic reordering must settle
    given/middle/family before the fold collapses middle into family, per
    the design's stated ordering rationale (the patronymic rules run before
    middle_as_family)."""

    policy_kwargs = {
        "middle_as_family": True,
        "patronymic_rules": {PatronymicRule.EAST_SLAVIC, PatronymicRule.TURKIC},
    }

    def test_rotate_then_fold_no_comma(self) -> None:
        # The patronymic rule rotates "Ivanov Petr Sergeyevich" to
        # given=Petr, middle=Sergeyevich, family=Ivanov; the fold then
        # collapses that settled middle into family.
        n = self.hn("Ivanov Petr Sergeyevich")
        self.m(n.given, "Petr", n)
        self.m(n.middle, "", n)
        self.m(n.family, "Sergeyevich Ivanov", n)

    def test_fold_applies_even_when_comma_suppresses_rotation(self) -> None:
        # A comma suppresses the patronymic rotation, so middle stays
        # "Sergeyevich" unrotated going into the fold. The fold still
        # absorbs it into family, producing the same given/family as the no-comma case above via a different mechanism.
        n = self.hn("Ivanov, Petr Sergeyevich")
        self.m(n.given, "Petr", n)
        self.m(n.middle, "", n)
        self.m(n.family, "Sergeyevich Ivanov", n)
