# Working in nameparser/

Loaded when a session reads or edits anything under `nameparser/`: the pipeline, the vocabulary TOML, the config shim. The root AGENTS.md carries the sweeps every behavior change runs (comma shapes, then `name_order`, under Architecture) and the 2.0 conventions; `nameparser/_pipeline/AGENTS.md` carries the ambiguity-report rules. This file holds the third sweep, which a vocabulary-only change needs as much as a code change does.

## Sweep the spellings: a class reached by vocabulary is also reached by SHAPE

A test that uses only the listed spelling of a word class walks only the vocabulary path, and the shape path is a separate branch that can be missing while every test passes. When a change touches a word class, test one spelling from each path. Each subsection below is a class where a path was missed, with the PR that found it; add a new class here when a review finds one (root AGENTS.md's Workflow section says how).

### Roman numerals

Roman numerals are the sharpest case: `ii`, `iii` and `iv` are suffix vocabulary; `i` and `v` are vocabulary too but initial-shaped, so `is_suffix_piece` vetoes them and only the numeral fork reads them; and `vi` through `x` are in no list at all, read by the fork's shape test alone (checked 2026-10-04 against `Lexicon.default()`) -- which stops at `x`: `_vocab._ROMAN` matches I to X, so `John Smith XI` reads `XI` as a name word (re-checked 2026-10-07, #614's /simplify, which found a docstring claiming "any length").

And the fork counts a ONE-letter numeral besides, since #718 (rules/S10): it is the suffix only where the name has a word to spare, so `John V` and `John Smith V` take different branches of one fork, a one-case name being counted like capitals whatever the letter -- since #721 a one-case one-letter numeral carries the `initial` tag its capital does, and since #723 every one-case bare letter does (rules/T4), and a bare letter in front of the numeral is initial-shaped as its capital is, so `john v` reads as `JOHN V` does over `test_a_one_case_name_reads_as_its_capitals`'s grid (comma shapes, orders, a maiden clause, a particle chain, a bare letter in front, a trailing title, a non-ASCII letter in front: 315 of its then 1,872 pairs disagreed at 2bfa9533, before #721, and none after). Its first version claimed "every shape" with no bare letter in front and no trailing title in the grid, and #721's reviews found both broken; a grid's claim is the grid -- put a head-plus-numeral row beside every words-to-spare row.

So a change that handles `V` and `III` can still miss `VI` — #610 found exactly that, the maiden take's candidate loop admitting a shape-only numeral in one position where the peel reads it in two (`Jane Doe nee Smith VI Prof.` kept maiden `Smith VI` while `V` and `III` worked). #656's sweep found the same class from the other side: C12 takes the word ending the name before a comma as EVIDENCE, and its first draft asked the suffix-word tag, so `John Smith VI, AD` missed the rule `III` reached, and then counted the whole part, so `Smith VI, AD` fired with `VI` as its own name word and `Smith V, AD` with a `V` that S10 reads as the family. A rule that weighs a numeral as a generation must ask the predicate that READS it as one (the trailing fork, `_vocab.reads_as_generation`, and its words-to-spare count), not the vocabulary that lists some of its spellings.

### Credentials and titles

The same split runs through the credentials (`MA` listed, `X.Y.Z.` by the dotted shape, `XYZ` by the caps shape, `MD/PhD` by its listed chunks and `PU-PH` by the caps shape's joined spelling, #752, each with its joiner glued, spaced and glued to one side, which are three token streams -- and a new chunk reading inherits the old one's exceptions, which #752's first draft did not (`Jack I-V` lost its family to the listed numerals, and the fix's length test counted a chunk's period, so `Jack I.-V.` did too, found by the second review), and `Ph. D.` merged by group into one flagged piece the peel's walk never holds -- #603 found #602's run-start predicate refusing it too, so `Smith, John Ph. D. Jones` kept middle 'Jones' where `Smith, John PhD Jones` read suffix 'PhD Jones') and the titles (`Prof.` period-marked and read at the end of a name, `Prof` bare and a name word there, and `Mr. and Mrs.` a run P3 joins, carrying a piece tag a one-word vocabulary test never sees -- PR #735's review found C12's hand copy of C13's title test (C8's until its 2026-10-19 split) reading `John Smith Jr., Mr. and Mrs. AD` as all suffix; ask C13's predicates in C13's order, `not is_suffix_piece` then `is_title_piece`, not the token tags, since `is_title_piece` alone reads the duals `Ms` and `Sr.` as titles).

### A word a rule only asks ABOUT

That holds for a word a rule only asks ABOUT, too: #810's first draft asked whether any word after a bracketed credential lacked the suffix TAG, and kept `John Smith (MA) VI`, `(MA) Ph. D.` and `(MA) Dr.` nicknames while `(MA) III` and `(MA) PhD` escaped; asking the role the parse read for the following word answers for every spelling.

### A separator's spacing

The same holds for a separator's SPACING: a comma (or any punctuation) can stand alone, glue to the word before it or glue to the word after, and each is a different token stream. #653's first fix swept `(née, Jones)` and missed `(née , Jones)`, where the kept comma became a word after the marker and M3 read the clause as maiden ', Jones'; its review found it. Put all three spacings in any grid around a separator.

And a separator glued to a word hides the word from every vocabulary test, not only the one being changed: the semicolon delimiter's first draft read a glued word's stem in C1's run test alone and put 365 of ClinicalTrials.gov's reversed names right, missing the ones C13, C4 and C6 read off a word's TAGS (`MBBS;`, `MA;`); tagging the stem put 412 right, and reading it again in the comma decision's shape tests, which read a word's text rather than its tags (`MBBS;`), 431 (decisions/C10, 2026-10-24). A rule over a glued spelling reads the stem everywhere the word is read, its tags and every test of its text, and is swept against the space twin -- with a declared word delimiter too, which a substring test finds inside other words ('Stand' under ' and ', the review of the same change).

### A full stop inside a word

A full stop INSIDE a word has four spellings of its own: initials run together (`J.R.R.`), joined words each closed by a stop (`Lt.Gov.`, `Msc.Ed.`), a joined word or name closed by none (`St.John`, `J.Smith`), and an abbreviation's own ending, closed or not (Italian `Sig.ra`, Latvian `Dr.philol.`). Shape tells the last from none of the others, so a rule over the shape decides which it costs; #838 found the ending only through the snapshot's CLDR row `Dut.ra Prof.ra`, and its first narrowing traded `St.John` for `Sig.ra` while the snapshot listed the `Dr.philol.` move among moves read as intended, until the design-docs review named it.

Initials run together are also how some SURNAMES are written (Nepali `B.K.`, `K.C.`), and a caseless script writes its abbreviations, degrees included, as dotted letters (Thai `พ.บ.`): #864 found S3's position reading taking the first from 2.4.0 on, visible only once #866's Nepal candidates gave the corpora a population that writes them, and its first fix moved CLDR's Thai degrees into the name. A rule over dotted letters reads both before it ships.

### Capitals between two name words

Capitals between two name words have the same second reading: some writers put their own initials there (`Maria Ana MA Silva`), so a rule that reads a word's capitals as a credential reads the initials too; #785 met it only in ctgov's field moves, no grid having held the shape, and Derek chose the initials (rules/S8: a name word behind capitals keeps them a name word where no family comma stands).

### Adjacent pairs of words

A predicate over ADJACENT PAIRS of words meets two shapes no grid of one word holds: an overlapping pair and a joining word beside an initial. #752's split-credential test (phase 2e) read `Dr. Ph.` in `Jane Doe Dr. Ph. D.` as the listed `drph`, leaving `D.` a word of its own (found by the maiden take's candidate grid), and a particle beside a surname written short as the listed `ded` (`DE D JUNIOR`, found only in tse-donors' readings), so put a title, a particle and a connective beside each pair spelling, and a pair overlapping another, in the grid.
