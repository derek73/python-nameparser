"""Hand-written names for naming conventions the other corpora barely
cover (#686): traditions with no family name, religious names,
patronymics placed by position, honorifics written after the name.

Every name here is INVENTED, patterned on a convention documented in
naming-practice references (a 2006 UK government guide distributed by
Interpol among them, which carries no licence notice), never copied from
one. build_conventions_corpus.py writes corpus_conventions.jsonl from
this table, and the snapshot watches those names like every other
corpus's.

`expect` is a NOTE, not a pin: what a reader who knows the convention
would take each part to be, often in terms the model cannot express yet
(a father's or grandfather's name, an honorific that is not a title, a
married form). Nothing scores the parser against it.

`fields` states the parts in CLDR's field vocabulary, as
cldr_agreement.py compares them, wherever a field can: `patronymic` is
scored inside the given names and `surname2` inside the family, as for
the Wikidata source, and `honorific` (a word of address written after
the name: Bey, ssi, san) inside the suffix. A row no field can state is
left without one rather than stated wrongly, since the comparison reads
an unstated part as an empty role, and says why in `unstated`; every
row carries `fields` or `unstated`, so neither can be left out by
accident. build_conventions_corpus.py writes conventions_fields.jsonl
from the `fields`.

Today's reading is deliberately not recorded here: snapshot.jsonl holds
it, and conventions_agreement.json holds it where it disagrees with
`fields`. A second copy would go stale. A row whose
reading is settled can graduate to tests/v2/cases.py, where it becomes a
contract.

`order` names an order some shapes.py shape declares, `"FAMILY_FIRST"`
or `"FAMILY_FIRST_GIVEN_LAST"`; the default order is None, not
`"GIVEN_FIRST"`, which no shape declares.
"""
from typing import NamedTuple


class Convention(NamedTuple):
    tradition: str
    convention: str
    name: str
    order: str | None
    expect: str
    fields: dict[str, str] | None = None
    unstated: str | None = None


CONVENTIONS: tuple[Convention, ...] = (
    Convention("Somali", "given + father's + grandfather's name, no family name",
               "Hodan Farah Warsame", None,
               "given Hodan; Farah and Warsame are her father's and grandfather's "
               "given names, not a family name",
               fields={'given': 'Hodan', 'patronymic': 'Farah Warsame'}),
    Convention("Sikh", "religious name between given and family name",
               "Harpreet Kaur Dhillon", None,
               "given Harpreet; Kaur is the religious name Sikh women traditionally "
               "take, written as a surname when no family name is; family Dhillon",
               fields={'given': 'Harpreet', 'given2': 'Kaur', 'surname': 'Dhillon'}),
    Convention("Tamil", "father's given name as a leading initial",
               "K. Sivakumar", None,
               "K. is the father's given name; Sivakumar is the person's own given "
               "name; no family name",
               fields={'patronymic': 'K.', 'given': 'Sivakumar'}),
    Convention("Spanish", "H. (hijo) as the Jr. equivalent",
               "Pedro López Ruiz H.", None,
               "given Pedro; family López Ruiz (paternal and maternal surnames); "
               "H. a generational suffix",
               fields={'given': 'Pedro', 'surname': 'López', 'surname2': 'Ruiz', 'generation': 'H.'}),
    Convention("Spanish", "Vda. de (widow of) before the late husband's surname",
               "Carmen Díaz Vda. de Mora", None,
               "given Carmen; her own family name Díaz; Vda. de Mora marks her as "
               "the widow of a Mora",
               fields={'given': 'Carmen', 'surname': 'Díaz Vda. de Mora'}),
    Convention("Turkish", "oğlu ('son of') written apart, part of the family name",
               "Ali Kara Oğlu", None,
               "given Ali; family Kara Oğlu, the separated spelling of Karaoğlu",
               fields={'given': 'Ali', 'surname': 'Kara Oğlu'}),
    Convention("Turkish", "honorific after the given name",
               "Murat Bey", None,
               "given Murat; Bey an honorific, not a family name",
               fields={'given': 'Murat', 'honorific': 'Bey'}),
    Convention("Hungarian", "title after the name",
               "Szabó Péter úr", "FAMILY_FIRST",
               "family Szabó, given Péter; úr ('Mr.') a word of address written last",
               fields={'surname': 'Szabó', 'given': 'Péter', 'honorific': 'úr'}),
    Convention("Hungarian", "married form: -né on the husband's given name",
               "Szabó Péterné", "FAMILY_FIRST",
               "family Szabó; Péterné ('wife of Péter') stands where her given "
               "name would",
               fields={'surname': 'Szabó', 'given': 'Péterné'}),
    Convention("Korean", "two-syllable given name written as two words",
               "Kim Min Ho", "FAMILY_FIRST",
               "family Kim; given Min Ho, one name in two words",
               fields={'surname': 'Kim', 'given': 'Min Ho'}),
    Convention("Vietnamese", "Thi as the female middle name",
               "Tran Thi Mai", "FAMILY_FIRST",
               "family Tran; middle Thi; given Mai, which the convention writes "
               "last (the order FAMILY_FIRST_GIVEN_LAST names; read under "
               "FAMILY_FIRST as the issue measured it); Mai is also a "
               "suffix acronym, so either order reads it as a suffix",
               fields={'surname': 'Tran', 'given2': 'Thi', 'given': 'Mai'}),
    Convention("Bulgarian", "patronymic between given and family name",
               "Ivan Petrov Dimitrov", None,
               "given Ivan; Petrov his patronymic, from his father Petar; family "
               "Dimitrov",
               fields={'given': 'Ivan', 'patronymic': 'Petrov', 'surname': 'Dimitrov'}),
    Convention("Filipino", "Ma. for María, maternal surname in the middle",
               "Ma. Teresa Cruz Bautista", None,
               "given Ma. Teresa (Ma. is María, not a title); Cruz the mother's "
               "surname; family Bautista",
               fields={'given': 'Ma. Teresa', 'surname2': 'Cruz', 'surname': 'Bautista'}),
    Convention("Korean", "romanized honorific, spaced",
               "Park Ji-hoon ssi", "FAMILY_FIRST",
               "family Park; given Ji-hoon; ssi (씨) an honorific",
               fields={'surname': 'Park', 'given': 'Ji-hoon', 'honorific': 'ssi'}),
    Convention("Japanese", "romanized honorific, spaced",
               "Suzuki san", "FAMILY_FIRST",
               "family Suzuki; san an honorific; no given name",
               fields={'surname': 'Suzuki', 'honorific': 'san'}),
    Convention("Japanese", "romanized honorific, hyphenated",
               "Suzuki-san", "FAMILY_FIRST",
               "family Suzuki; -san an honorific glued to it",
               fields={'surname': 'Suzuki', 'honorific': '-san'}),
    Convention("Burmese", "no family name; honorific U for a man",
               "U Kyaw Win", None,
               "U an honorific; Kyaw Win the whole personal name; no family name",
               fields={'title': 'U', 'given': 'Kyaw Win'}),
    Convention("Burmese", "honorific Daw for a woman",
               "Daw Thida", None,
               "Daw an honorific; Thida the whole personal name",
               fields={'title': 'Daw', 'given': 'Thida'}),
    Convention("Thai", "Khun before the given name",
               "Khun Malee", None,
               "Khun a polite title; Malee the given name, which Thai address uses",
               fields={'title': 'Khun', 'given': 'Malee'}),
    Convention("Malay", "bin ('son of') patronymic, no family name",
               "Hassan bin Yusof", None,
               "given Hassan; bin Yusof his patronymic; no family name",
               fields={'given': 'Hassan', 'patronymic': 'bin Yusof'}),
    Convention("Malay", "bin abbreviated B.",
               "Hassan B. Yusof", None,
               "as Hassan bin Yusof: B. is bin, not a middle initial",
               fields={'given': 'Hassan', 'patronymic': 'B. Yusof'}),
    Convention("Malaysian Indian", "a/l (anak lelaki, 'son of')",
               "Suresh a/l Muthu", None,
               "given Suresh; a/l Muthu his patronymic; no family name",
               fields={'given': 'Suresh', 'patronymic': 'a/l Muthu'}),
    Convention("Malaysian Indian", "a/p (anak perempuan, 'daughter of')",
               "Kavitha a/p Raman", None,
               "given Kavitha; a/p Raman her patronymic; no family name",
               fields={'given': 'Kavitha', 'patronymic': 'a/p Raman'}),
    Convention("Indonesian", "H. (Haji), a title shaped like an initial",
               "H. Budi Santoso", None,
               "H. a title (one who has made the hajj); given Budi Santoso, "
               "the whole personal name: Indonesian law recognizes no surname",
               fields={'title': 'H.', 'given': 'Budi Santoso'}),
    Convention("Kalenjin", "arap ('son of')",
               "David arap Kirui", None,
               "given David; arap Kirui, used as a family name",
               unstated="arap Kirui is a patronymic or a family name by family"),
    Convention("Maasai", "ole ('son of')",
               "Joseph ole Sankale", None,
               "given Joseph; ole Sankale, used as a family name",
               unstated="ole Sankale is a patronymic or a family name by family"),
    Convention("Kikuyu", "wa ('of')",
               "Wanjiru wa Kamau", None,
               "given Wanjiru; wa Kamau names a parent, her father or her mother",
               unstated="wa Kamau is a patronymic, a matronymic or a family name "
                        "by family"),
    Convention("Hong Kong", "English given name before the Chinese name",
               "Michael Wong Kar Ming", None,
               "given Michael; family Wong; Kar Ming the Chinese given name",
               fields={'given': 'Michael', 'surname': 'Wong', 'given2': 'Kar Ming'}),
    Convention("Singapore", "English given name after the Chinese name",
               "Lim Mei Ling Jessica", "FAMILY_FIRST",
               "family Lim; Mei Ling the Chinese given name; Jessica the English "
               "given name",
               fields={'surname': 'Lim', 'given': 'Mei Ling', 'given2': 'Jessica'}),
    Convention("Cantonese", "given name that is also a title modifier",
               "Wing Lau", None,
               "given Wing, not a title; family Lau",
               fields={'given': 'Wing', 'surname': 'Lau'}),
    Convention("Hungarian", "married form on the husband's family name",
               "Szabóné Kiss Éva", "FAMILY_FIRST",
               "Szabóné ('wife of Szabó') a married form; family Kiss; given Éva",
               unstated="no field states a married form on the husband's family name"),
    Convention("Afrikaans/Dutch", "capitalized particle, no given name",
               "Van der Walt", None,
               "family Van der Walt; no given name",
               fields={'surname-prefix': 'Van der', 'surname-core': 'Walt'}),
    Convention("Arabic", "kunya ('father of')",
               "Abu Karim", None,
               "a kunya, 'father of Karim', used as a name of address; not a given "
               "name plus a family name",
               unstated="no field states a kunya"),
    Convention("Iranian", "-zadeh written as a separate word",
               "Reza Hossein Zadeh", None,
               "given Reza; family Hossein Zadeh, the separated spelling of "
               "Hosseinzadeh",
               fields={'given': 'Reza', 'surname': 'Hossein Zadeh'}),
    Convention("French", "index form, elided particle after the given name",
               "Orval, Pierre d'", None,
               "family d'Orval; given Pierre; d' belongs to the family",
               fields={'surname-prefix': "d'", 'surname-core': 'Orval', 'given': 'Pierre'}),
)
