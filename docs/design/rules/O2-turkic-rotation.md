# O2 — Turkic rotation

**When:** Turkic patronymic handling is active, the default given-first order stands, and the last name word of a name with no comma is a standalone patronymic marker, as in "Ali Ahmad Vali oglu".

**Then:** a name of exactly four name words — titles, suffixes and nicknames aside — ending in a standalone patronymic marker reads family-first: the first name word is the family name, and the marker stays beside the father's name in the middle.

- **A name of exactly three name words** ending in a standalone patronymic marker reads the father's name and the marker together as the family name, the first name word the given name.
- **The scope is O1's**: the restoration recovers the default reading, so a declared family-first order stands in its place.

**Because:** a Turkic patronymic marker is a separate word that follows the father's name; a four-word name ending in one is a family-first listing, and a three-word name ending in one has no surname, the father's name and the marker standing where the surname would, as Kyrgyz documents write it and as the convention files the bearer.

```
"Ali Ahmad Vali oglu"  [tr_az]  →  family="Ali"
"Ali Ahmad Vali oglu Jr."  [tr_az]  →  family="Ali"
"Sa'dullayev Alisher Zafar o‘g‘li"  [tr_az]  →  family="Sa'dullayev"
"Бекмырза Чолпонбай уулу"  [tr_az]  →  family="Чолпонбай уулу"
"Ali Ahmad oglu"  [tr_az]  →  family="Ahmad oglu"
"Dr. Ali Ahmad oglu Jr."  [tr_az]  →  family="Ahmad oglu"
```

**Precedence:**

- **Over two family names** (O6): the three-word reading takes the middle word into the family first, so O6 finds no middle to take and the family is one unit, the father's name with its marker: under `two_family_names` `Ali Ahmad oglu` reads surname2 empty.

**Accepted:**

- Any other count of name words keeps its positional reading, even when that leaves the marker itself in a name field.
  ```
  "Ali oglu"  [tr_az]  →  family="oglu"  · boundary
  "Ali Ahmad Vali Hasan oglu"  [tr_az]  →  family="oglu"  · boundary
  ```
- A given name P5 binds from two words (`Abdul Rahman`) makes three name units of four name words, which neither shape reads: the four-word rotation needs a given name of one word, and the three-word reading three words.
  ```
  "Abdul Rahman Ahmad oglu"  [tr_az]  →  family="oglu"  · boundary
  ```
- A suffix comma keeps the positional reading where the same name without it reads the three-word way, the rule reading only a name with no comma.
  ```
  "Aidai Mederbek kyzy, PhD"  [tr_az]  →  family="kyzy"  · boundary
  "Aidai Mederbek kyzy PhD"  [tr_az]  →  family="Mederbek kyzy"
  ```
- A surname spelled as the marker, ending a three-word name, joins the word before it, as a father's name would.
  ```
  "Ali Ahmad Oğlu"  [tr_az]  →  family="Ahmad Oğlu"
  ```
- The order scope has this rule's own consequence reached by a second route — with Turkic handling active and FAMILY_FIRST_GIVEN_LAST declared, Ali Ahmad Vali oglu reads given oglu, the marker standing in a name field because the declaration put the name's last word there (#384).

---
**Signal:** neighbor: a standalone patronymic marker ending a name of exactly three or four name words
**history:** decisions/O2 · **implemented:** nameparser/_pipeline/_post_rules.py
