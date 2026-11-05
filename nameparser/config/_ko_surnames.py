from nameparser.config._invariants import assert_normalized

# Born a frozenset (#293's convention: a mutable module constant would
# silently desync the cached ``Lexicon.default()`` from the shim's
# per-construction copies).
#
# Single-syllable surnames in census rank order, 10 per row; the cut is
# the top ~94 -- append new entries at the tail, do not alphabetize
# (rank order is the only in-file record of where the coverage floor
# sits).
KOREAN_SURNAMES = frozenset({
    "김", "이", "박", "최", "정", "강", "조", "윤", "장", "임",
    "한", "오", "서", "신", "권", "황", "안", "송", "전", "홍",
    "유", "고", "문", "양", "손", "배", "백", "허", "남", "심",
    "노", "하", "곽", "성", "차", "주", "우", "구", "민", "류",
    "나", "진", "지", "엄", "채", "원", "천", "방", "공", "현",
    "함", "변", "염", "여", "추", "도", "소", "석", "선", "설",
    "마", "길", "연", "위", "표", "명", "기", "반", "왕", "금",
    "옥", "육", "인", "맹", "제", "모", "탁", "국", "은", "편",
    "용", "예", "경", "봉", "사", "부", "가", "복", "태", "목",
    "형", "계", "피", "두",
    # the two-syllable surnames in current use (census-complete);
    # longest-first matching splits 남궁민수 as 남궁+민수, not 남+궁민수
    "남궁", "황보", "제갈", "사공", "선우", "서문", "독고", "동방",
    "망절",
})
"""
Korean surnames (#271), used by the 2.0 API's unspaced-name
segmentation (``Lexicon.default().surnames``): a hangul token like
"김민준" splits into surname + given name by longest match. This ships
as DEFAULT vocabulary because it is self-selecting -- a hangul entry
can only ever match hangul text -- and hangul text is unambiguously
Korean. Chinese surnames deliberately live in ``nameparser.locales.zh``
instead (Han segmentation is opt-in; a zh list corrupts Japanese kanji
names).

Source: the 2015 South Korean census surname tables -- the most common
single-syllable surnames (Kim/Lee/Park alone cover ~45% of the
population) plus the two-syllable surnames in current use. A coverage
floor, not the complete census roster: extend with
``Lexicon.default().add(surnames={...})``.

Consumed by the 2.0 parser's default lexicon. The 1.x parser does not
read this module.
"""


assert_normalized("KOREAN_SURNAMES", KOREAN_SURNAMES)
