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
(a patronymic, a name with no family name, an honorific that is not a
title). Nothing scores the parser against it (#686 decided against a
fields file). Today's reading is deliberately not recorded here either:
snapshot.jsonl holds it, and a second copy would go stale. A row whose
reading is settled can graduate to tests/v2/cases.py, where it becomes a
contract.

`order` is a public nameparser constant name, as in shapes.py; None is
the default order.
"""
from typing import NamedTuple


class Convention(NamedTuple):
    tradition: str
    convention: str
    name: str
    order: str | None
    expect: str


CONVENTIONS: tuple[Convention, ...] = (
    Convention("Somali", "given + father's + grandfather's name, no family name",
               "Hodan Farah Warsame", None,
               "given Hodan; Farah and Warsame are her father's and grandfather's "
               "given names, not a family name"),
    Convention("Sikh", "religious name between given and family name",
               "Harpreet Kaur Dhillon", None,
               "given Harpreet; Kaur is the religious name every Sikh woman bears, "
               "written as a surname when no family name is; family Dhillon"),
    Convention("Tamil", "father's given name as a leading initial",
               "K. Sivakumar", None,
               "K. is the father's given name; Sivakumar is the person's own given "
               "name; no family name"),
    Convention("Spanish", "H. (hijo) as the Jr. equivalent",
               "Pedro López Ruiz H.", None,
               "given Pedro; family López Ruiz (paternal and maternal surnames); "
               "H. a generational suffix"),
    Convention("Spanish", "Vda. de (widow of) before the late husband's surname",
               "Carmen Díaz Vda. de Mora", None,
               "given Carmen; her own family name Díaz; Vda. de Mora marks her as "
               "the widow of a Mora"),
    Convention("Turkish", "oğlu ('son of') written apart, part of the family name",
               "Ali Kara Oğlu", None,
               "given Ali; family Kara Oğlu, the separated spelling of Karaoğlu"),
    Convention("Turkish", "honorific after the given name",
               "Murat Bey", None,
               "given Murat; Bey an honorific, not a family name"),
    Convention("Hungarian", "title after the name",
               "Szabó Péter úr", "FAMILY_FIRST",
               "family Szabó, given Péter; úr ('Mr.') a title written last"),
    Convention("Hungarian", "married form: -né on the husband's given name",
               "Szabó Péterné", "FAMILY_FIRST",
               "family Szabó; Péterné ('wife of Péter') stands where her given "
               "name would"),
    Convention("Korean", "two-syllable given name written as two words",
               "Kim Min Ho", "FAMILY_FIRST",
               "family Kim; given Min Ho, one name in two words"),
    Convention("Vietnamese", "Thi as the female middle name",
               "Tran Thi Mai", "FAMILY_FIRST",
               "family Tran; middle Thi; given Mai, which the convention writes "
               "last (the order FAMILY_FIRST_GIVEN_LAST names)"),
    Convention("Bulgarian", "patronymic between given and family name",
               "Ivan Petrov Dimitrov", None,
               "given Ivan; Petrov his patronymic, from his father Petar; family "
               "Dimitrov"),
    Convention("Filipino", "Ma. for María, maternal surname in the middle",
               "Ma. Teresa Cruz Bautista", None,
               "given Ma. Teresa (Ma. is María, not a title); Cruz the mother's "
               "surname; family Bautista"),
    Convention("Korean", "romanized honorific, spaced",
               "Park Ji-hoon ssi", "FAMILY_FIRST",
               "family Park; given Ji-hoon; ssi (씨) an honorific"),
    Convention("Japanese", "romanized honorific, spaced",
               "Suzuki san", "FAMILY_FIRST",
               "family Suzuki; san an honorific; no given name"),
    Convention("Japanese", "romanized honorific, hyphenated",
               "Suzuki-san", "FAMILY_FIRST",
               "family Suzuki; -san an honorific glued to it"),
    Convention("Burmese", "no family name; honorific U for a man",
               "U Kyaw Win", None,
               "U an honorific; Kyaw Win the whole personal name; no family name"),
    Convention("Burmese", "honorific Daw for a woman",
               "Daw Thida", None,
               "Daw an honorific; Thida the whole personal name"),
    Convention("Thai", "Khun before the given name",
               "Khun Malee", None,
               "Khun a polite title; Malee the given name, which Thai address uses"),
    Convention("Malay", "bin ('son of') patronymic, no family name",
               "Hassan bin Yusof", None,
               "given Hassan; bin Yusof his patronymic; no family name"),
    Convention("Malay", "bin abbreviated B.",
               "Hassan B. Yusof", None,
               "as Hassan bin Yusof: B. is bin, not a middle initial"),
    Convention("Malaysian Indian", "a/l (anak lelaki, 'son of')",
               "Suresh a/l Muthu", None,
               "given Suresh; a/l Muthu his patronymic; no family name"),
    Convention("Malaysian Indian", "a/p (anak perempuan, 'daughter of')",
               "Kavitha a/p Raman", None,
               "given Kavitha; a/p Raman her patronymic; no family name"),
    Convention("Indonesian", "H. (Haji), a title shaped like an initial",
               "H. Budi Santoso", None,
               "H. a title (one who has made the hajj); given Budi; Santoso a "
               "second given name or a family name"),
    Convention("Kalenjin", "arap ('son of')",
               "David arap Kirui", None,
               "given David; arap Kirui, used as a family name"),
    Convention("Maasai", "ole ('son of')",
               "Joseph ole Sankale", None,
               "given Joseph; ole Sankale, used as a family name"),
    Convention("Kikuyu", "wa ('of')",
               "Wanjiru wa Kamau", None,
               "given Wanjiru; wa Kamau names her father"),
    Convention("Hong Kong", "English given name before the Chinese name",
               "Michael Wong Kar Ming", None,
               "given Michael; family Wong; Kar Ming the Chinese given name"),
    Convention("Singapore", "English given name after the Chinese name",
               "Lim Mei Ling Jessica", "FAMILY_FIRST",
               "family Lim; Mei Ling the Chinese given name; Jessica the English "
               "given name"),
    Convention("Cantonese", "given name that is also a title modifier",
               "Wing Lau", None,
               "given Wing, not a title; family Lau"),
    Convention("Hungarian", "married form on the husband's family name",
               "Szabóné Kiss Éva", "FAMILY_FIRST",
               "Szabóné ('wife of Szabó') a married form; family Kiss; given Éva"),
    Convention("Afrikaans/Dutch", "capitalized particle, no given name",
               "Van der Walt", None,
               "family Van der Walt; no given name"),
    Convention("Arabic", "kunya ('father of')",
               "Abu Karim", None,
               "a kunya, 'father of Karim', used as a name of address; not a given "
               "name plus a family name"),
    Convention("Iranian", "-zadeh written as a separate word",
               "Reza Hossein Zadeh", None,
               "given Reza; family Hossein Zadeh, the separated spelling of "
               "Hosseinzadeh"),
    Convention("French", "index form, elided particle after the given name",
               "Orval, Pierre d'", None,
               "family d'Orval; given Pierre; d' belongs to the family"),
)
