# Mechanisms

How this codebase solves recurring problem shapes. Before proposing a design, check whether an entry already fits — the catalog is keyed by problem shape, because that is what you have in hand when searching.

Entry format: an `## UPPER-KEBAB-SLUG — one-line slogan` heading, then **Problem shape** (the situation that should trigger recall), **Contract statement** (one or two sentences stating what the mechanism promises — the citable line), **How it works**, **Lives in**, and **Reach for it when** (the tell-tale sign you should be using this instead of inventing something). Each label opens its own paragraph, and that is load-bearing: tests/v2/test_doc_citations.py reads a Contract statement to the end of its paragraph, so whatever shares the paragraph becomes quotable. An entry carries its contract and pointers; how an instance was found belongs in the decisions entry that decided it, or in the Field notes below when it is a trap rather than a decision.

The Contract statement is citable under the same discipline as rules: a committed comment making a mechanism claim — including any claim about which stage or layer does something — cites the slug and quotes a verbatim excerpt (`# mechanisms.md#SPANS: ...`), checked by the citation-integrity test. Free-prose restatements of mechanism claims are how one wrong sentence has shipped six times.

This catalog converts discovery into a one-time cost — it does not remove discovery. What nobody knows yet still has to be found the hard way, once; the promise is that found things stay found.

## SPANS — position is identity, text is not

**Problem shape.** A later stage needs to refer to "that word."

**Contract statement.** Every token carries its (start, end) character span in the original string, and stages refer to tokens by index, never by searching for matching text.

**How it works.** v1 re-found pieces by value, so a name with a repeated word could rewrite the wrong occurrence (#100 and relatives); a position cannot be confused with a look-alike. Every parsed part is an exact slice of the input (rule T1's Background).

**Lives in.** nameparser/_types.py (Span), threaded through every _pipeline/ stage.

**Reach for it when.** New code is about to do `if token.text == ...` to LOCATE rather than to classify.

## FOLDED_TAG — reorder at render time, not parse time

**Problem shape.** A rule wants words to RENDER in a different order than they sit in the string.

**Contract statement.** Tokens never move: a rule that needs different rendering order tags the token, and the rendering views consult the tag — EVERY view that renders the affected role, ordering folded tokens first, not the field views alone.

**How it works.** Reordering the token tuple would break span math and reintroduce the #100 family. Parse state stays in string order; only the view reorders (rule R1, rule R3's order clause, rule O3's render clause). The consumer list is where this mechanism fails, in two opposite directions — and only ONE of them has ever shipped, which is worth keeping straight because a roster is walked differently when it is guarding against a defect than when it is guarding against a possibility. SHIPPED: a consumer that never read the tag (`initials()` walked written order through 2.0, 2.1 and 2.2 — #408, filed as an instance of RENDER-HONORS-THE-PARSE and fixed 2026-08-30). HAZARD, never released: a consumer that reads the tag where it should not (the revise strip below), which arrived with `Parser.revise` in the same commit as the test that pins it, so no version has gone out without it and no issue, decision entry or test names a defect of that shape. Adding a producer is cheap; adding a view is where the roster has to be walked.

**Lives in.** nameparser/_types.py (FOLDED_TAG, `_text_for` — every role it renders, not FAMILY alone), nameparser/_render.py (`initials`, the same partition per role), nameparser/_facade.py (`_list_tokens_for`, which prepends the carriers the same way — it is the ONE walk behind both the v1 `*_list` views and the facade's initials since #528, and `_list_for` is the string view built on it and holds no ordering of its own, so a reader who follows this roster to the string builder lands one level below the partition), nameparser/_pipeline/_post_rules.py and _assign.py (its producers: O3's fold and P6's no-comma attachment in post_rules, P6's attachment after a family comma in assign since #613 -- every one of which re-roles to FAMILY — so FAMILY is the only role a parse can put the tag on today, and the views partitioning every role is uniformity with this contract rather than reachable behavior), and nameparser/_parser.py (`Parser.revise`, the one deliberate CONSUMER-side strip: it removes the tag from the tokens it harvests, a revised value not being allowed to inherit fold ordering) — losing that strip is this mechanism's measured hazard, a family rendering "García Gabriel Márquez". A module path and not a method name, because this roster is what a reader walks when adding a view, and a bare `Parser.revise` sends them looking in the wrong file.

**Reach for it when.** A new rule needs "X renders before Y" and you are tempted to swap tokens. Don't swap. Tag.

## VOCAB-TAGS — the vocabulary layer speaks once

**Problem shape.** A later stage needs to know what the vocabulary knew about a word.

**Contract statement.** classify tags every token with what the vocabulary knows about it, and later stages test tags — they never re-look a word up.

**How it works.** One lookup site means one answer: a stage that re-derived vocabulary facts could disagree with the stage before it. Stable tags ("particle", "conjunction", "initial") are API;
"vocab:"-namespaced ones are not.

**Lives in.** nameparser/_pipeline/_classify.py (producer); consumers throughout _group/_assign/_post_rules, and nameparser/_render.py, which is not a stage but reads the same tags to decide what a view shows (#458 moved case repair's conjunction test onto the tag; initials() had read them since 2.0), and nameparser/_facade.py, whose `_token_is_conjunction` joined them in #528 — the v1 layer is a tag consumer too now, so a sweep that stops at `_render.py` is one module short.

**Reach for it when.** A stage is about to import Lexicon to ask about a word classify already saw — or a view is, which is the harder one to notice, since a view legitimately holds a Lexicon for the questions classify never answered; the view side is RENDER-HONORS-THE-PARSE, which owns it and covers the decisions this entry does not produce.

## PIECES — joining structure survives assignment

**Problem shape.** A rule needs to know how words were JOINED (chained titles, particle groups), not just what roles they got.

**Contract statement.** group records the joining structure as pieces — runs of token indices per segment — and that structure remains readable after roles are assigned.

**How it works.** Roles alone lose the grouping ("who chained with whom"); #359's fix made the particle fold read the opening PIECE rather than the assigned role, which is what makes rule P1 hold under every name_order.

**Lives in.** nameparser/_pipeline/_group.py (producer), _pipeline/_state.py (ParseState.pieces), _post_rules.py (reader).

**Reach for it when.** A rule keyed on assigned roles behaves differently under different name_order values — the stable thing to read is usually the structure. Known limit, found by #395: the structure survives ASSIGNMENT, not group's own later merges. The prefix chain absorbs a joined piece into a longer one, so a rule reading pieces after that point can no longer see the join — see UNIT-PARTITION.

## UNIT-PARTITION — count the units the joining rules built

**Problem shape.** A rule counts "one name word", but the input holds words that another rule has already joined into one name — and the joining structure it would read has been merged away.

**Contract statement.** Three rules build multi-word units: a particle chain (P2), a conjunction join (P3), and a bound given-name pair (P5). A rule that counts name words counts those units, and takes each whole or not at all — with one stated exception, rules/C3's count of the words before a comma, which counts particle surnames alone (decisions/C3, #575).

**How it works.** group builds each join as a piece, but its own prefix chain then merges the joined piece into a longer one, so PIECES no longer carries the boundary — the units are rebuilt from the tags the vocabulary layer left (`particle`, `conjunction`, `vocab:bound-given`). The rebuild is RECURSIVE: what a conjunction or a bound word joins is the next UNIT, not the next word, and absorbing a single token instead strands a particle severed from the words it chains. Note the two joins arrive here for opposite reasons — the conjunction join was built and then swallowed, while the bound-given join was never built at all (P5 joins only at the first non-title piece), so restoring piece boundaries in group would fix the first and silently split the second.

**Lives in.** nameparser/_pipeline/_vocab.py (`unit_ends`, the walk, shared since #575) and its two readers: _post_rules.py (`_units`, over classify's tags, for P1's fold) and rules/C3's counts before a comma: `_comma._whole_name`, over classify's tags (`surname_unit_facts`) since #613 moved the decision after classify, and `_vocab.name_word_count`, which builds its facts from the vocabulary (`surname_unit_tags`, held to classify's tags by an agreement test) -- a view script_segment needed while it asked a hand copy of C1 before classify ran, until #613's /simplify had it ask `_comma.decide` itself on a classified copy. A fourth walk is S2's read (#614): `_pieces._chain_units` marks each piece by the unit P2's chain WILL put it in -- opening a unit, or a name word the chain joins -- asking the chain's own `chain_run_end`, which `_group`'s chain calls too; a word the reading weighs (`_weighed`) keeps a unit of its own, as a position always counted it. The particles straight behind each other are merged ahead of the read, into the piece the chain would open its run with (`_pieces.merge_particle_runs`, #625), so a particle run is one piece the read takes whole or not at all, and no mark stands for a particle inside it. The trailing peel's words to spare and #602's run start count in those marks, the peel stops at a word the chain joins, and everything else -- the numeral fork's look at the word in front, the H5 chain, the run's title test -- reads the pieces as written. It runs before the chain joins name words to a particle run, which is why it cannot read the merged tags `unit_ends` walks; #614 had rebuilt the chain as a merged COPY instead, whose three defects in one review -- words the reading weighs hidden inside a unit, indices drifting from the pieces' -- were each patched in that copy, and #620 replaced it with the marks (decisions/S2). C3 counts particle chains only, reaching one word as the fold does: a bound pair builds a given name, and whether P3 joins a connective depends on the whole name the count is helping to decide, so neither is one surname before a comma (`_vocab.SURNAME_UNIT_TAGS`, decisions/C3). rules/P1 and rules/C3 are the counting rules, P2/P3/P5 the joining ones.

**Reach for it when.** A rule says "one name word" and the input can contain a join — enumerate the joining rules out of the rules rather than the ones you remember.

## MARK-DONT-STRIP — record the decision, keep the fact

**Problem shape.** A stage concludes that a vocabulary fact is not operative for one occurrence — a particle that joins nothing, a middle that will render as family.

**Contract statement.** It MARKS the token with a namespaced marker rather than removing the vocabulary tag: the tag says what the word IS, the marker says what was decided about it, and consumers ask for the pair. The cost, which has to be paid in the docs rather than avoided: where a stable tag was documented with a RECIPE — `particle` combined with Role.FAMILY "for actual family particles" — the marker makes the recipe diverge from the view it reproduced, so the recipe's documentation has to say so.

**How it works.** Stripping is tempting because every downstream consumer becomes correct for free, with no predicate to change; it pays for that by destroying the record, and asymmetrically. `particle` is the only tag all but two of the never-given particles carry, so stripping it leaves nothing on the token, while every ambiguous one still carries `vocab:particle-ambiguous` (the two exceptions, `mc` and `vd`, carry `vocab:suffix` — the same dual membership P6's S2 precedence turns on) — the half where a later fork is most interesting is the half that loses its evidence, and ParsedName has no lexicon to re-derive from. Marking also leaves a POSITIVE predicate: "this token used to have a tag" is not testable, `UNJOINED_TAG in tags` is, which is what an ambiguity emitter needs (#405). And `particle` is documented stable API meaning "a word from the particle vocabulary wherever it lands", so removing it would be a breaking change as well as a lossy one.

**Lives in.** nameparser/_types.py — FOLDED_TAG (O3's fold, P6's attachment), UNJOINED_TAG (R2's standalone particle) and UNJOINED_CONJUNCTION_TAG (R3's connective with nothing in its part to join, #461), all namespaced and internal, qualifying stable tags that stay put.

**Reach for it when.** A rule decides a word is not doing the job its vocabulary implies.

## STRUCTURE-GATES — comma shape as an explicit state

**Problem shape.** A rule should fire only under one comma convention.

**Contract statement.** The comma structure (NO_COMMA, FAMILY_COMMA, SUFFIX_COMMA) is decided once and every later stage gates on that single decision rather than re-inspecting commas. segment parts the string and hands every comma form over as FAMILY_COMMA; group decides it at its head, once classify has tagged the words (#613), and script_segment, which runs between and reads the handover, asks its own narrower question where it needs more (`_postnominal_behind_a_whole_name`); classify, the other stage between, reads no structure since #613.

**Lives in.** nameparser/_pipeline/_state.py (Structure), _pipeline/_segment.py (the parts), _pipeline/_comma.py (the one decider, called by group).

**Reach for it when.** New code is about to count commas.

## TWO-LAYER-ASSIGN — vocabulary claims, position takes the rest

**Problem shape.** Where should a new "recognize X" behavior live?

**Contract statement.** A vocabulary layer first claims words for what they ARE, wherever they sit; a positional layer then reads every unclaimed word by where it STANDS. Every rule belongs to exactly one layer — with one named exception: the leading-abbreviation shape (rule H2) fires before the suffix vocabulary is consulted, so
"Esq. Smith" reads title, not suffix.

**How it works.** The two layers compose without ordering bugs because the positional layer never overrides a vocabulary claim (rule O4 is the positional layer's contract). The exception is still ONE, re-checked 2026-09-08 against the trailing title run (rule H5), which reads title vocabulary in the trailing slot and is NOT a second one: it runs after the suffix peel rather than before it, so a post-nominal keeps its claim — `John Smith Esq.` reads suffix and `John Smith Prof. Jr.` reads suffix `Jr.`, both measured. That rule is also the worked answer to the Reach-for-it line below: it wanted a word's identity and its position at once and was split by SLOT, the front asking about shape (H2) and the back about vocabulary (H5), two questions with two criteria rather than one rule fighting both layers.

**Lives in.** _classify/_group (vocabulary side), _assign (positional side).

**Reach for it when.** A proposed rule wants a word's identity AND its position at once — split it, or it will fight both layers.

## READ-WITHOUT-THEN-BIND — read the name without the construct, then fix that reading

**Problem shape.** An optional construct sits inside a name — a maiden clause, a trailing title — and the requirement is that writing it changes nothing else about the name. Checked after the fact, that invariant has to be defended at every place the construct can end, and each defense has to model what later stages would do to the words it gives up.

**Contract statement.** Read the name as if the construct were not written, using the rule that reads that position, not the whole parse. The construct takes only what that reading leaves. Where later stages could still move what the reading decided, give those words their roles at the take so no later join can reach them. The invariant then holds by construction and is not a property each stop must defend.

**How it works.** M2 before #601 scanned forward, stopped at suffix-looking words, and kept a release check asking at each stop whether the name left standing would read what was given up as post-nominals. That check modelled the P2 chain, the P5 bound join and P6's attachment, and #548 was it failing at the one stop that never asked. #601 replaced the stops and the check with the clause-free reading plus the bind: a net 689 lines out of `_group.py` (+210/−899 in the #601 commit), and #535's grids went from 15,586 and 8,713 invariant violations to 0 (prototype measurement, 2026-10-03, #601's comments). The first half already appears twice. H5's trailing title is TRANSPARENT: "what stands once the chain is taken reads exactly as it would read written without the title, plus the title". P3 and P8 ask the word count and the one-case question of the name's OWN words, so a clause beside the name changes neither. M2 is the first to bind as well, because its construct sits in front of the run it reads and the joins come later. C1 is the second (#613, rules/C7): the part after the comma is read once, after classify and before any join, by the reading a part holding no name word gets, and a postnominal part's roles are set there. segment had decided the structure before the tags existed, so it modelled group's particle chain (#562's pair) and assign's reading of a run the capitals settle, and assign re-decided #296's positional read with a second count; all three went. S2 is the third (#614): the trailing run of a main segment is read once, between P3's connective joins and the particle chain, and split off, so the joins that had re-asked the peel before and after themselves -- the chain's stop and its rollback, the bound-given reserve's two views -- answer from that one reading, and assign places the run off it. Where the read sits is the lesson. Joins the run does not depend on but whose units it counts come FIRST: read before P3's connectives, the H5 chain took the second title of a bare `Mr. and Mrs.` and left 'and' as the family name, and a joined pair counted as two words (#614's review). Joins the run does depend on come after, and the read counts what they will build instead -- the particle chain's run and the words it joins as one unit, marked on the pieces rather than built, with every word the reading weighs still a word of its own: #614 counted through a merged copy, whose review found it hiding a shape-only roman numeral and a title inside a credential run, each patched there, until #620 counted the chain's units over the pieces as written (decisions/S2). Two limits, both measured on #601. Read with the TRAILING rule, not the full parse: a head the full parse reads differently (H1's lone title, a P5 join) would otherwise move where the construct ends. And binding means the run can read differently from the same words with no construct (`JANE Q. DOE GEB. LE DO DO` gives suffix `DO DO`, while the full parse of `JANE Q. DOE DO DO` chains them into the family), which rules/M2 accepts in so many words.

**Lives in.** nameparser/_pipeline/_group.py (`_maiden_take`: the view, `tail_reading` over it, and the role-tagged pieces `group()` applies); nameparser/_pipeline/_pieces.py (`tail_reading`, H5's chain); the P3 own-word test in `_group.py`; nameparser/_pipeline/_comma.py (C1's read-and-bind); `_pieces.read_trailing_run` and `_chain_units`, and the read after P3's joins in `_group._group_segment` (S2's).

**Reach for it when.** A rule is growing stops, exceptions or a release check whose job is to keep one construct from disturbing the rest of the name, and above all when that check has started to model another stage. Ask what the name reads as without the construct, and make that the rule.

## MERGE-THEN-SETTLE — merge what a count decides, and split back what it declines

**Problem shape.** Two words may be one unit, and whether they are is a question only a later reading answers: a count of the words around them, made by a rule that reads pieces. Merged too early, a pair the reading declines is read as one piece where it should be two, and the merge hides a word that would have answered something by itself; left unmerged, the reading never sees the unit at all.

**Contract statement.** Merge the candidate into one piece, tagged as a candidate, and let the rule that decides read it. Where the rule takes it, keep the piece; where it declines, split it back into the words it is written as before anything else reads them, so a declined candidate reads exactly as the words read with no merge. Where the deciding reading is one pass over a whole part, read the part again unmerged rather than unpicking the merged reading.

**How it works.** rules/S12's split credential (#752, phase 2e): classify tags each pair `_vocab.split_pair` admits, group merges it as a member of the ambiguous class, S2's trailing read decides it by S4's count, and `_group._settle_splits` splits back every merged pair the read left in front of the run before the particle chain or the bound join can see it. In the given part after a family comma, where the deciding reading is assign's walk, the pair is merged ahead of group's joins and the joins treat it as the credential it may be: the particle chain stops in front of it and P5's bound join declines it. Moving the merge after the joins instead, so that none could take it, let the chain take its first word (`Smith, John van Pharm D` read middle 'van Pharm D'): a candidate merged later than the readers it should stop is no candidate to them. After a comma `_comma.decide` reads the part with the pairs merged and, where that reading does not take one as a credential, reads the part again with none merged: the first version kept the merged reading there, and the pair hid an `MB` that had opened the part as a credential (C13), reversing 15 ClinicalTrials.gov names (`Aa Aa, MB ChB BAO` read given 'MB'). The settled outcome is either the merge's reading or the as-written one, never a third, which is what lets a measurement read every move as a pair the count took.

**Lives in.** nameparser/_pipeline/_classify.py (the pair tag); nameparser/_pipeline/_group.py (the merge, `_settle_splits`, and P5's decline of a split piece); nameparser/_pipeline/_comma.py (`decide`'s retry, `_pieces(splits=...)`).

**Reach for it when.** A unit of several words is decided by a count or a position the merge itself changes, and the safe reading of a declined unit is the reading its words already had.

## LICENSED-BY-NEIGHBOR — a structural word is structural only beside the right neighbor

**Problem shape.** A word in a structural vocabulary — a marker announcing a maiden name, a connective joining surnames — turns up where what it would announce makes no sense: behind a title alone, behind a credential, at the end of a name. Designing a reading for each such shape is endless, and the shapes are mostly junk.

**Contract statement.** Make the vocabulary claim conditional on the neighbor: the word is structural only where the word beside it has the role the structure needs. Anywhere else it is an ordinary word and goes to the positional layer (TWO-LAYER-ASSIGN), with no reading designed for the junk.

**How it works.** M2 (#601): a marker counts only behind a name word of the part holding the family name, not behind the leading title run, an unambiguous suffix word or a connective. So `Dr. nee Smith` gives first `nee`, last `Smith`, and `Jane Doe PhD nee Smith` gives suffix `PhD nee Smith`, neither designed. P3 is the same shape for the connectives that are also generational vocabulary: `i` joins only where "a name word stands on each side of it". The condition must be checked against real names, not just against the vocabulary. #601's first cut also refused a marker behind a particle and broke `Mai Le née Nguyen` and `Anh Do née Tran` — Le, Do and Van are particle vocabulary and among the commonest Vietnamese surnames.

**Lives in.** nameparser/_pipeline/_group.py (`_maiden_take`'s head rule; `_between_name_words` for P3).

**Reach for it when.** A structural word is producing bad readings in positions its structure does not fit. Make its claim depend on the neighbor before adding a reading or a stop for each position.

## STATE-OFFSET-CHANNELS — early facts ride the state

**Problem shape.** A fact known during tokenization matters to a much later stage.

**Contract statement.** A pre-token fact is recorded as offsets on the ParseState (comma_offsets, interpunct_offsets) and consulted later by position — or by presence alone where the fact is name-level, as both interpunct consumers do, or as a single boolean for the whole name, as `ParseState.one_case` is (#289/#516: the written-case fact three later sites read — the trailing suffix slot, the post-comma given slot, and the tail-segment reading — none of which may disagree about it) — rather than re-derived from text.

**How it works.** The offsets survive every intermediate stage untouched; #298's transcription marker rides this channel from tokenize to order resolution (rules T3/W4). `one_case` differs from the offset channels in WHO writes it: it is computed once by whichever of segment and classify needs it first (classify always, segment only where a comma form could turn it on), recorded as `None` for "not asked yet", and never recomputed once set (decisions/S6).

**Lives in.** nameparser/_pipeline/_state.py, produced in _tokenize (the offsets) or in segment/classify (`one_case`).

**Reach for it when.** You are about to re-scan the original string in a late stage to rediscover something tokenize already knew.

## PIPELINE-STAGE-CONTRACTS — the ownership map

**Problem shape.** "Which stage does X?" — asked before attributing behavior in prose, comments, or fixes.

**Contract statement.** Each stage's docstring header declares what it consumes, produces and reads, and ParseState's docstring holds the cross-stage map, pinned by tests/v2/pipeline/test_state.py.

**How it works.** A claim about which stage or layer does something is CHECKABLE — `parse(s).tokens` prints every token's role and tags — so check it before writing it; one plausible attribution sentence once shipped six times wrong (AGENTS.md's stage-attribution note).

**Lives in.** nameparser/_pipeline/_state.py and every stage header.

**Reach for it when.** Writing any sentence of the form "X happens before Y sees it."

## ONE-PREDICATE-PER-QUESTION — one predicate answers it, and every other site calls that

**Problem shape.** Two stages need the same answer about the same input, and the one that does not own the decision is about to test for it.

**Contract statement.** Where two sites ask the same question, exactly one predicate answers it and every other site calls that one — never a condition written to match it. The predicate belongs to the QUESTION, not to whichever stage decides: it may sit in a leaf both stages import, and for the leading-title test it must, since the deciding stage is assign and group cannot import assign. Stage order is this mechanism's limit: where the reader comes AFTER the decider, record the answer on the state instead — `ParseState.order` is that shape, "Recorded rather than recomputed downstream, because the two can differ" — which is unavailable whenever the EARLIER stage is the one asking.

**How it works.** A hand-written mirror agrees with its original only until one of them moves, and the drift is invisible in both directions: each site keeps passing its own tests while they disagree about an input neither covers. Every instance below was found as a defect before it was found as a pattern. The destination follows the LAYER, not the topic: a predicate over token text goes to `_vocab`, one over pieces and tags to `_pieces`, both leaves the stages sit on. The piece layer got its own module only in #439; until then those predicates collected in `_group`, the one place both stages could reach, so the sharing between group and assign predates the module (decisions/parse-cost measured #439 as a pure relocation). The cost is a second evaluation of the same predicate, measured for #429 at 1.2–2.2% of a family-comma parse and 0% of every other — the right price there over plumbing a state field the two sites would not otherwise share. Folding two copies into one, take from each caller only what genuinely differs between them, and ask whether a parameter one caller had been filling with a guard is a question the other caller must answer too (#617, decisions/P3). The census of which stage calls which predicate, and how each instance was found, was kept here until #759 and is in git history (`git show fe85bb3d:docs/design/mechanisms.md`); the decisions entries carry each instance's argument.

**Lives in.** nameparser/_pipeline/_vocab.py over token text: `is_wholly_suffix` (#319, decisions/W2), `reads_as_generation` (#401/#421 as `is_trailing_numeral_suffix`, decisions/P5; since #752 the predicate every rule weighing a numeral as the generation asks, the vocabulary's own numerals read inside it; C4's run refuses a one-letter numeral by its shape alone, `is_single_letter_numeral`, a question about the shape of an initial and not a generation, decisions/vocabulary-model), `split_pair` (#752, the split credential: `Ph.` `D.` once, which group's merge, `_comma._pieces` and `is_wholly_suffix` each tested with their own copy; since phase 2e every pair rules/S12 reads, asked by classify alone behind a C-level shape, length and fold test and written as a tag that group and `_comma._pieces` read, `is_wholly_suffix` asking `SPLIT_PAIR_OPENS` for the Ph./D. answer alone; decisions/phd-merge, decisions/S12), `is_cased_paired_initials` (#752, rules/S3's paired initials in a script with capitals, which classify asked inline; C5 asks the bare `is_paired_initials`, decisions/S3), `maiden_marker_run` (#434, decisions/M2), `delimiter_cores` (#436/#437, decisions/R1), `in_initialless_script` (#322/#323, decisions/cjk-full-stops), `caps_shape_candidate` (#516, decisions/S9). nameparser/_pipeline/_pieces.py over pieces and tags: `is_suffix_piece`, `leading_titles` and `is_leading_title` (#424), `is_title_piece`, `peel_walk`, `trailing_start`, `tail_reading` (the peel-and-chain fixed point that answers where the name pieces end, decisions/H5), `segment_suffix_reading` (#430, decisions/R1), `particle_tail` and `trailing_candidates` (#610, decisions/M2), `join_connectives` (#617, decisions/P3). nameparser/_pipeline/_post_rules.py: `suffix_entries` (#511, decisions/R1), the one instance in a stage rather than a leaf, being a pass over a whole ParseState. tests/v2/test_layering.py holds each module's contract, and a piece predicate growing a dependency on a STAGE shows up there as a widened entry.

**Reach for it when.** You are about to write a condition that mirrors, matches or "does what X does" — or you find a comment saying one does. Grep for the other site's predicate and call it instead.

## RENDER-HONORS-THE-PARSE — the parse decides it, the views honor it

**Problem shape.** A render view needs a fact the parse already settled — whether a word is the conjunction or an initial, whether a particle is acting as one, which word renders first.

**Contract statement.** The parse decides it; the render views honor those decisions and never re-evaluate them. Two directions break that: a view RE-DERIVES the answer from the text, keeping its own copy of a pipeline predicate, or a view honors the record and then OVERRIDES it, readmitting what the decision excluded. Known limit: a token the parse never saw carries no decision to honor, so a view falls back to the vocabulary — the tell is `UNCLASSIFIED_TAG`, which `ParsedName.replace()` stamps when it splices raw text into a field and the facade's v1 pickle load stamps when it rebuilds a name from `*_list` strings.

**How it works.** This is the CONSUMER-side rule over the producer-side entries — VOCAB-TAGS records what the vocabulary knew, MARK-DONT-STRIP what a stage decided about it, FOLDED_TAG what order to render in — and a view reads what they recorded. It sits where ONE-PREDICATE-PER-QUESTION's stated limit leaves off: a render view always comes AFTER the decider, so the answer is recorded on the TOKEN, no view being able to see a ParseState. The fallback's tell is the mark and nothing else: not untaggedness, since an ordinary parsed name word carries no tags, and not `span is None`, since `Parser.revise()` builds span-less tokens whose tags it keeps on purpose. A view can fall back only if it is HANDED a vocabulary — `capitalized(lexicon=...)`, and since #528 the facade's `HumanName.initials()` — and the core `ParsedName.initials()`, handed none, never guesses one (decisions/R4). Within a view that can fall back, the fallback is drawn per QUESTION (rules/R4's Accepted clause). Both directions have shipped as defects and both are closed: re-deriving in case repair (#458, decisions/R4) and in `initials()`'s written-order walk (#408, decisions/R3), overriding in `initials()`'s readmission of an all-particle part's connective, closed by settling what rules/R3 says rather than by making the view louder (#461, decisions/R2 and decisions/R3). Two divergences stand by decision: the facade's fallback can initial a spliced field differently from a parse of the same text (decisions/R3, 2026-09-13 #528), and case repair's PARTICLE conjunct keys on the lexicon it is handed rather than the `particle` tag (decisions/R4's NOT DONE bullet). The case history this entry carried until #759 is in git history (`git show fe85bb3d:docs/design/mechanisms.md`).

**Lives in.** nameparser/_render.py (`capitalized`/`_cap_word`, `_reads_as_conjunction`, and `initials`, the CORE view, which honors tags and never falls back), nameparser/_types.py (`_text_for` and `UNCLASSIFIED_TAG`, with the `ParsedName.replace()` producer beside it), and nameparser/_facade.py, on this list twice and for opposite reasons: the v1 pickle load is the SECOND producer of the mark — a change that follows the list into `_types.py` alone leaves it behind, which is the site test_a_restored_pickle_keeps_v1_conjunction_repair protects — and since #528 `_token_is_conjunction`/`_process_initial` are a CONSUMER, reading the tag and calling `_render._reads_as_conjunction` for the mark's own tokens.

**Reach for it when.** A view is about to consult a Lexicon, a regex or an exception list about a word the parse already saw — or a view and a field disagree about the same parse, which is the shape #408 was (`parse("der, y van")` gave family `van der` and initials `y. d. v.`; decisions/R3).

## CLAUSE-CONTENT-OVERRULES-DELIMITER — content wins

**Problem shape.** A bracketed clause should be treated as something other than what its delimiter pair says.

**Contract statement.** extract may inspect a clause's content against the lexicon and, when it matches, mask only the two delimiter spans so the inner content rejoins the main token stream for ordinary downstream parsing.

**How it works.** "Andrew Perkins (MBA)" is not a nickname (rule S1): the parens are masked away and MBA is classified by the normal machinery — reusing the downstream path, so the delimited and bare forms cannot drift.

**Lives in.** nameparser/_pipeline/_extract.py (_suffix_shaped and the inner-span branch).

**Reach for it when.** About to add a second code path that duplicates what the bare form already does — #335's fix is this shape (a _maiden_marked sibling predicate).

## CURATED-VOCABULARY-ALTERNATION — the config already splits them

**Problem shape.** Two string shapes collide — the same written form means two different things — and no predicate separates them.

**Contract statement.** A curated vocabulary that OMITS the ambiguous entries is itself the separator: membership is the license, and the per-entry vetting reasons live beside the set.

**How it works.** GLUED_HONORIFICS is the exemplar (rule W2): 씨 peels because it can never end a name; 양 stays out because 김지양 is a given name. The set, not a regex, draws the line.

**Lives in.** nameparser/vocab/*.toml, where each word the peel may take carries `attached`. A word refused only the glued position carries `excluded = { attached = … }` on the reading it keeps (`uv run python tools/vocab/query.py --excluded attached`), and a word refused the honorific reading in both positions, such as 君 or bare 선생, carries a word-level `excluded` (`--excluded honorific`), each with its reason.

**Reach for it when.** Arguing that "no regex can separate X from Y" — check whether a config set already splits them by listing one side. The second half of the pattern: to USE the set in a regex, hand-copy the alternation and pin the copy against the set (tests/v2/test_regex_sync.py holds the pipeline's copies).

## RECORDED-ROSTERS — record the answer, don't re-derive it

**Problem shape.** A guard needs to know what the answer WAS, so it can detect the answer changing.

**Contract statement.** Store the measured answer as literal data (a roster) and compare against it; never re-derive the expectation from the same inputs the check reads, because a derivation from the same data always agrees with itself. Known limit, and it is what the contract statement does NOT cover: a roster row can hold a recorded INPUT as well as a recorded expectation, and only the expectation half is asserted. The test to apply to a recorded input is not "is it checked" but "would the consumer answer DIFFERENTLY if it were wrong". The differential ledgers' rosters were this entry's worked cases (`_CROSS_RULE_WINNERS` carried wrong recorded shapes that agreed with themselves until #497 moved them where a run measured them), and were retired with the ledgers in #664; their measurements are in git, at the commit decisions/differential-ledger names.

**How it works.** The purest case is a recorded expectation whose only consumer is the check that compares it, re-derived by nothing: tools/differential/snapshot.jsonl records every corpus name's reading, and tests/v2/test_snapshot.py compares the tree against it.

**Lives in.** tools/differential/snapshot.jsonl, tests/v2/test_facade_cases.py (_CORE_ONLY_IDS), tests/v2/test_benchmark.py (_CALL_BASELINE), tests/v2/rules_budget.json (each rule's recorded size).

**Reach for it when.** Writing a check whose expected value is computed by the code under test, or a comment that enumerates ids/counts — make it data the suite asserts. And when a roster row carries anything the check CONSUMES rather than compares, ask what measures that half.

## COMPILED-DATA-COMMITTED — compile the data at build time, hold the artifact to a fresh compile

**Problem shape.** Data written for people (rich, commented, one fact per word) is the wrong thing for a runtime to parse on every import, and a generated runtime form can drift from its source.

**Contract statement.** Compile the source into a committed, generated module that the runtime imports, and test that the committed module is byte-identical to a fresh compile, failing with the command that refreshes it; run the compiler's checks over the shipped source in the same test, with warnings as errors, and give each check a mutation it must refuse.

**How it works.** The parser imports nameparser/config/_compiled.py, frozenset literals one entry per line so a one-word change is a one-line diff; tools/vocab/build.py writes it from nameparser/vocab/*.toml; tests/v2/test_vocab.py compiles in memory and compares. The source can grow descriptive data (notes, counts, expansions) that compiles to nothing and costs the runtime nothing. Cost: a data change touches two files and needs the tool run, which the staleness test turns from a silent drift into a CI failure carrying the fix.

**Lives in.** tools/vocab/build.py, tests/v2/test_vocab.py (decisions/vocabulary-model).

**Reach for it when.** A data file the runtime would otherwise parse, or a hand-kept Python copy of data that has a better home — and not for a measured expectation, which is RECORDED-ROSTERS.

## CANONICAL-VOCABULARY-AT-THE-BOUNDARY — one vocabulary at the comparison

**Problem shape.** Two surfaces name the same concept differently (first/last vs given/family), and a matcher needs to compare across them.

**Contract statement.** Canonicalize at the point of comparison: every compared surface's output is converted to one vocabulary before matching, and the canonical choice is the one the codebase already derives everywhere else.

**How it works.** Teaching the matcher both vocabularies doubles every comparison silently; canonicalizing means a second surface joins without new keys. The snapshot records the facade's v1 fields under Role's names, and compare.py's 1.4.0 rows do the same, so a 1.4 reading and a 2.x one compare field by field.

**Lives in.** tools/differential/snapshot.py (row, V1_FOR).

**Reach for it when.** A second surface joins an existing matcher — without this, every existing comparison silently stops matching the new surface, which looks like added coverage.

## VOCABULARY-OVERLAP-AS-PRECONDITION — assert the intersection you stand on

**Problem shape.** A test's input depends on two config sets intersecting (a word that is both a title and a particle), and a vocabulary edit could quietly unground it.

**Contract statement.** Assert the intersection as a precondition and distinguish the two failure modes: word moved (pick another member; the message prints what is left) versus intersection empty (the code under test is unreachable — delete it rather than repointing the test).

**Lives in.** tests/v2/test_parser.py (test_the_chained_emitter_is_still_reachable).

**Reach for it when.** Any config-coupled fixture — a test input chosen because of what a vocabulary happens to contain.

## VOCABULARY-FEEDS-STRUCTURE — a wordlist edit can move the comma decision

**Problem shape.** Editing suffix vocabulary looks field-local, but the comma-structure decision (rule C1) reads that vocabulary, so a removal can flip which segment is the family name.

**Contract statement.** Suffix-set membership is an input to the structure decision: removing a word from the suffix vocabulary can change a suffix-comma name into a listing-form name, relocating the family.

**How it works.** Measured in the comma-suffix arc: dropping "dr" from the suffix vocabulary flips "John Smith, Dr." from family="Smith" suffix="Dr." to family="John Smith" — three individually correct documented facts composing into a family-name loss.

**Lives in.** nameparser/_pipeline/_comma.py (the C1 decision, since #613) reading the suffix sets through _vocab.is_wholly_suffix.

**Reach for it when.** Editing suffix membership for any word that occurs after a comma in real data — check the structure flip, not just the field.

## WARN-AT-THE-CALLER — walk out of the library, don't count frames

**Problem shape.** A warning should point at the caller's code, but the entry depth varies (constructor, add(), unpickle, dataclasses.replace, the shim snapshot), so any fixed stacklevel lands on library internals for most paths.

**Contract statement.** The warner walks the stack outward until the first frame outside the library's own modules and warns there, instead of counting frames.

**Lives in.** nameparser/_lexicon.py (_warn_dead_entry), and the related but distinct per-read-location choice is in the #293/#354 bridge (decisions/3-0-reevaluations). First measured instance of the hazard: the delegated bytes-deprecation warnings shipped with fixed stacklevel=2 and needed the follow-up fix (0044073).

**Reach for it when.** Adding any warning reachable through more than one public entry point.

## LEGACY-STATE-SIGNATURE — subtract legacy defaults only as a complete set

**Problem shape.** A retired default rides in on old pickles, but a user may have deliberately re-added one of the same entries.

**Contract statement.** Known-dead legacy defaults are subtracted from restored state only when the state carries ALL of them — the complete pre-retirement signature — so real legacy blobs clean up silently while a deliberate single re-add survives round-trips.

**Lives in.** nameparser/_lexicon.py / _config_shim.py (_LEGACY_DEAD_ENTRIES).

**Reach for it when.** Retiring any default vocabulary entry that existing pickles may carry.

## AMBIGUITY-AT-THE-DECISION-SITE — emit where the branch is taken

**Problem shape.** An ambiguity report should fire exactly when the parse chose between live readings — no more, no less — and the choosing happens in code, not in vocabulary.

**Contract statement.** Emit at the site that takes the branch, not where an ambiguous tag sits; when a fork's two branches are decided in different stages, EVERY deciding stage carries an emitter; and a branch that runs but changes nothing is not a decision and must not report. The decision is the site's, but a FIELD the report names is not: a later rule can still move the word, so the emitter leaves the field to assemble (`PendingAmbiguity.field_tail`), which words it from the final role (#626). Segment's report on a part past the second comma names no field at all, since that part's words can land in two (#629).

**How it works.** PARTICLE_OR_GIVEN fires from assignment for a lone leading particle and from grouping when a title shifts it off the front — for two years only the first site emitted. And keying on
"the code got here" instead of "the outcome differed" once reported
a fork for all ambiguous particles on "Dr. Van Jr.".

**Lives in.** The AmbiguityKind emitters across _pipeline/ (rule A1 is the observable contract).

**Reach for it when.** Adding any ambiguous vocabulary or any new fork — count the deciding sites, then count the emitters.

## MAKE-WRONG-STATES-UNREPRESENTABLE — the house meta-pattern

**Problem shape.** A convention keeps being violated no matter how clearly it is written down.

**Contract statement.** Convert the consistency problem into a referential-integrity problem: make the wrong state impossible to express, or mechanically checked, rather than merely documented.

**How it works.** Three instances built this documentation system: _CORE_ONLY_IDS replaced an enumerating comment; verbatim-excerpt citations replaced paraphrase; no-boundary: markers replaced silent omission. The executable examples in the rules are the same move at document scale.

**Lives in.** tests/v2/test_doc_citations.py, tests/v2/test_rules_doc.py, and every recorded roster.

**Reach for it when.** Tempted to write "remember to keep X in sync with Y."

## LOCALE-PACKS-PURE-DATA — packs configure, they never compute

**Problem shape.** Language-specific behavior needs a home that cannot drift from the core.

**Contract statement.** A locale pack is pure data — a Policy patch and Lexicon ADDITIONS, add-only: a pack unions vocabulary in and can never remove a base entry — applied by parser_for; packs contain no code paths of their own, and each pack's docstring declares its deviations from the defaults.

**How it works.** What is policy for every language (an order constant) is policy, not pack data; packs are lowercase modules exposing uppercase constants; a pack error is wrapped with the pack's code (rule D2). Pure data means a pack can be audited by reading it — and add-only means a bad DEFAULT can never be routed around by a pack, which is why #342-class fixes must change shipped vocabulary.

**Lives in.** nameparser/locales/ (packs), nameparser/_parser.py (parser_for, the one applier).

**Reach for it when.** A language fix wants an if-statement — make it vocabulary or policy in a pack instead.

## FACADE-CONTRACT — HumanName wraps the core; 1.4-warning-free code keeps working

**Problem shape.** Where does v1-compatibility behavior live, and what may it do?

**Contract statement.** HumanName is a mutable facade over the immutable core: code that runs warning-free on 1.4 keeps working through 2.x with identical results EXCEPT release-log-classified fixes, verified for 2.0 by the differential ledger and since #664 visible against 1.4.0 through `tools/differential/compare.py --baseline 1.4.0` (the RFC's compatibility promise carries the same carve-out) — via validating setters, dirty-tracked re-parses, and pickle round-trips — and the facade never calls the v1 parsing hooks it still carries. "Warning-free" describes the code's 1.4 behavior, not a promise it STAYS warning-free: 2.x adds deliberate warnings (the multi-word-vocabulary and field-assignment ones), each release-log-classified, always with identical results.

**Lives in.** nameparser/_facade.py; v1 import paths preserved by nameparser/parser.py and nameparser/config/.

**Reach for it when.** A core change needs a v1-visible behavior — the facade, not the core, is where parity lives (and cite decisions/3-0-reevaluations when parity is the only reason).

## CONFIG-SHIM-SNAPSHOT — v1 config mutations reach the core by snapshot

**Problem shape.** v1 code mutates CONSTANTS at runtime; the core is immutable.

**Contract statement.** nameparser.config re-exports mutable managers whose contents are converted to immutable core objects through a dirty-tracked snapshot: mutations mark the snapshot stale, and the next parse rebuilds it, so v1 mutation semantics survive over an immutable core.

**Lives in.** nameparser/_config_shim.py, nameparser/config/.

**Reach for it when.** Wiring any new v1 config surface — it must go through the snapshot, never sideways into a Lexicon.

## Verification shapes

How to measure in this codebase without fooling yourself. The inert-measurement class — checks that run, print plausible results, and measure nothing — has recurred double-digit times; these shapes are its known antidotes. Convention (AGENTS.md): guard tests SHOULD carry a RECORDED negative control, the `_UNGUARDED_EFFECT` shape (tests/v2/pipeline/test_state.py) — the answer with the guard off, stored as data. Honest limit, precisely drawn: these reduce the inert-measurement class. Mutation testing reaches part of the wrong-predicate class too — mutating the thing a guard watches exposes a guard that never depended on it (the #329 survivors: deleting the tag check left the suite green while every multi-word maiden clause lost its first word, after adversarial review had passed that code twice) — but a predicate wrong in a way the fixture happens to satisfy still needs adversarial review.

### VERSION-TELL — know who answered

**Contract statement.** A subprocess that speaks for a pinned version writes its __version__ and __file__ as its first output line, and the caller aborts before comparing anything if either half disagrees with what was requested. Both halves are load-bearing: an editable install reports the tree's version (agreement proves nothing when tree and baseline share a number); a genuine wheel at the wrong version passes any path check. Lives in tools/differential/compare.py (_check_tell).

### GENERATED-SCRIPT-OUTSIDE-THE-WORKTREE — escape the shadow

**Contract statement.** A worker that must run under a pinned dependency is rendered to a temp directory outside the worktree and spawned by absolute path, so sys.path[0] contains no copy of the package and the inline pin is genuine. Sentinel substitution (@@VERSION@@), not str.format — the worker body is mostly literal braces. Lives in tools/differential/compare.py (_worker_source, _run_worker).

### SENTINEL-SET-OVER-MATCH-CHECK — catching match-everything

**Contract statement.** A user-supplied pattern is rejected as over-matching by probing it against a small set of inputs sharing no script, vocabulary or punctuation; matching all of them means it targets no behavior family. Measured: `.`, `.+`, `\b` and `[\s\S]` all decline the empty string — the naive probe — and still match every corpus name. Lived in tools/differential/compare.py (_SENTINELS) until the ledgers it checked were retired (#664); the shape stands for any user-supplied pattern.

### VOCABULARY-EXERCISES-FORKS — pin the branch, not the wordlist

**Contract statement.** A vocabulary set a caller configures is data; the code that reads it is what has behavior, so a case row earns its place by exercising a FORK — a branch the parser takes for one INPUT and not another — never by covering one more member. The unit is the input, not the member, because most forks are keyed on the shape of the surrounding name rather than on which word appeared. Find them by reading the sites that consult the set and enumerating the branches they take, and expect that enumeration to come back empty: `maiden_markers` is read at exactly two sites (`_classify.py`'s tagging and `_extract.py`'s `_maiden_marked`), both plain whole-token membership after `_normalize`, and every shipped member parses to one structural class in bare, bracketed and lone-bracketed shapes with the marker text normalised out — zero member forks. What earns the maiden rows is clause SHAPE: marker first against marker later, a word after the marker against none, a marker a separator divides from the name against one glued to it. Two adjacent things are NOT forks of this set and do not want rows: the substring-versus-token split is a question tools/differential/README.md's coverage recipe asks wider than the parser does, and edge-period normalization lives in `_lexicon._normalize`, applying to every token of every vocabulary, so it discriminates spellings rather than members. Only "a member borne as an ordinary name" is member-keyed (decisions/vocabulary-collisions), and it has its own rows. The reduction does NOT carry across to delimiter pairs, and the difference is the line to hold: a pair the library SHIPS is caller-visible behavior, and vocabulary a caller configures is data — deleting `("«", "»")` from the defaults reddens three tests, so cases.py's one-row-per-shipped-pair convention is load-bearing and this criterion is not permission to delete those rows. Within the pairs the code does fork, on whether open and close are the same character (N2) and again inside that class, where `WORD_INTERNAL_DELIMITERS` carves the apostrophe out: `Jane Smith"` reports UNBALANCED_DELIMITER and `Jane Smith'` reports nothing. ASCII against fullwidth is not one of them — swapping `( )` for `（ ）` across every corpus name holding a paren changes no field and no ambiguity kind. A row may also earn its place a second way, with no fork behind it: pinning a name a release note advertises BY NAME, which is a promise to a reader rather than a branch in the parser. It follows that "N of M entries have no test" is not a finding; it reads as one because it carries a number, and it inflates with every entry added, which is the tell that it measures the data. The finding is "this fork has no test". State the argument without present-tense counts over a drifting wordlist — see docs/design/AGENTS.md — and where a count is genuinely wanted, ship the one-liner instead:

```
uv run python -c "
from nameparser import parse
from nameparser.config.maiden_markers import MAIDEN_MARKERS
shapes = ['Jane Smith {m} Jones', 'Jane Smith ({m} Jones)', 'Jane Smith ({m})']
cls = {}
for m in sorted(MAIDEN_MARKERS):
    sig = tuple(tuple((f, (getattr(parse(s.format(m=m)), f) or '').replace(m, '<M>'))
                      for f in ('given', 'middle', 'family', 'suffix', 'nickname', 'maiden'))
                for s in shapes)
    cls.setdefault(sig, []).append(m)
print(len(MAIDEN_MARKERS), 'members ->', len(cls), 'structural classes')"
```

### FORCE-A-DECISION-TABLE — no silent defaults on growth

**Contract statement.** Where adding an enum member or a file must not silently inherit a default, a local table's key set is asserted equal to the population, so growth fails the suite until someone decides — against a local table, not the constant under test. Exemplar: tests/v2/pipeline/test_vocab.py's per-script initials check; reused for the pack registry (test_registry_is_the_pack_contract: every registered pack must ship DEVIATES and its rotator list or the suite fails structurally — decisions/deviates-registry). Known gap it exposes: DEFAULT_SCRIPT_ORDERS has no such guard.

### SELF-EXPIRING-GUARD — a decline keyed to a measured defect

**Contract statement.** A workaround keyed to a third-party library's measured defect carries a canary test that pins the defect itself, so the workaround cannot outlive its reason: when the library fixes it, the canary fails and the decline gets revisited rather than fossilizing. Exemplar: tests/v2/test_locales.py's namedivider shime canary pins 0.4.x cutting 〆木太郎 at offset 1 with confidence 1.0, guarding the adapter's 〆 decline (#303 arc); its comment says to revisit the decline, not delete the test.

### SIMULATE-EVERY-OPTION — price the option space, not the chosen option

**Contract statement.** Where a fix has more than one plausible shape, every candidate is measured before one is chosen — simulated in-process against the real pipeline rather than implemented — and the choice cites the resulting table.

**How it works.** The seams already exist, so simulating is cheap: `Parser(lexicon=dataclasses.replace(Lexicon.default(), ...))` for a vocabulary question, a pytest plugin recompiling one stage for a code question, a monkeypatched predicate for a guard. What the table buys is the discovery that the candidates differ in ways argument does not reveal — #400's obvious fix, adding `abd` to the wordlist, provably changed nothing on the common three-word shape, and the two vocabulary alternatives each silently lost a credential spelling; the winner was a fifth option the wordlist framing had hidden. The counterexample is the same PR's ledger `fields`, widened to include `suffix` on one reviewer's finding without pricing what else the widening claimed: it took `{family, suffix}` from a neighbouring rule and two further shapes from UNEXPLAINED, diffs in which the rule's own subject does not move, and was reverted. One table would have shown that before the commit rather than after.

**Reach for it when.** A review names a defect and the fix looks obvious — that is when the option space is least examined, and the obvious fix is the candidate whose cost nobody has priced. Not a mechanism with a home module; the technique IS the seams above, which is why it sits here rather than in the catalog.

### TWO-ELEMENT-GROUPS — a partition's mutation check needs something to permute

**Problem shape.** A test pins an ordering, a sort, a dedup or a partition, and its fixture gives one of the affected groups a single element.

**Contract statement.** Every group a test claims to cover carries at least TWO elements, because on a one-element group a partition is the identity — the assertion holds whether the code runs or not, and the mutation that should expose it passes.

**How it works.** This is the inert-measurement class arriving through the FIXTURE rather than through the predicate, and it hides behind a mutation check that looks conclusive: #408's `initials()` partitions three roles, and its first test carried two GIVEN tokens and one MIDDLE, and its second carried two of each and no FAMILY token at all — a group of ZERO is the identity as surely as a group of one, and looks even less like a hole. Scoping the partition to FAMILY failed that test, which read as the arms being pinned — but skipping the partition for MIDDLE alone passed the entire suite (measured 2026-08-30, in review, at 6128 passed), because `initials("{middle}")` over one token is the same string either way. The tell is that the mutation which fails is not the mutation the test's docstring promises: a per-role claim wants a per-role mutation, one arm at a time, and only then does the fixture's arity show.

**Reach for it when.** A test asserts on the ORDER or MEMBERSHIP of a rendered group and the fixture was written to be small.

### SHADOWED-NEGATIVE-ROWS — a new check can answer for an old row

**Problem shape.** A change adds a check to a validator, a constructor or a loader that already has negative rows — rows that build a bad value and assert it is refused — and the new check refuses those rows too, whether it runs before their own checks or after them.

**Contract statement.** After adding such a check, every existing negative row is re-run with its OWN check removed; a row that still passes is being refused by the new check instead, and its fixture is rebuilt to satisfy the new check, so that each row is refused by the one check it names.

**How it works.** This is the inert-measurement class arriving through a SECOND REFUSAL: with a row's own check gone, the row still raises, the suite stays green, and the assertion reads as correct, because a refusal is all it asks for. #798 gave the NPPES credential tally (tools/name_usage.py) a consistency check, that every stored spelling choice names a token. Four rows testing the token values replaced the tokens with a single key and kept the stored choices, which still named the token they had dropped, so the new check refused all four as well, though it runs after the value checks there. The mutation run found it: deleting each of the three value checks those rows guard left the suite green (3 of that run's 38 mutants missed). The fix replaced the stored choices along with the tokens in each row, with a comment above the parametrize saying why. Distinct from TWO-ELEMENT-GROUPS, where the fixture is too small to exercise the code, and from the root AGENTS.md's widened check that quietly narrows: here the old check still works and its test has stopped reaching it.

**Reach for it when.** The check you are adding relates two fields — a cross-field consistency check is the usual cause, since a row editing one field breaks it without meaning to.

### NAME-DATA-JOBS — the job decides where a source's names live

**Problem shape.** A new source of names turns up (a registry, a dataset, a dump) and the question is what to build for it: a committed corpus, a column in a tool, a script that writes vocabulary.

**Contract statement.** A name source does one or more of five jobs — WATCH, SCORE, COUNT, DERIVE and SURVEY — and the job decides where its data lives. Only WATCH and SCORE in CI need the names in the repository, so a source whose names cannot be committed still does COUNT and SURVEY, WATCH and SCORE outside CI, and DERIVE where its terms let a derived list ship.

**How it works.** WATCH asks whether a change moved a name: a committed corpus, `snapshot.jsonl` and a test that fails, or a local corpus read with `snapshot.py --local`, which no CI run sees. SCORE asks whether the parser agrees with someone who knows the fields: a committed fields file and agreement record, read by `cldr_agreement.py` from the repository alone, or a local corpus whose records carry the fields their filers typed, with its record kept in the cache beside it (`local_agreement.py`). The local score tells a change's author what moved among real filed names, by field, and gives agreement by group and how often each disagreement shape occurs. It cannot guard anything: no CI run and no reviewer sees it, and no test fails when it moves (the tool itself exits 1). Its truth is the filer's, so a box filled wrongly (a job typed as a title) reads as a miss unless the scorer sets it aside, and the scorer has to say what it sets aside. COUNT asks how one word is used: a cached source behind a row of `tools/name_usage.py`, with only the counts cited. DERIVE asks what a shipped list should hold: a cached source and a script writing the vocabulary (`tools/zh_surnames.py`). SURVEY asks how people write whole names, and how OFTEN they write each shape: a cached local corpus (`tools/differential/local_corpora.py`).

A second axis cuts across the jobs: whether the names are real or invented, labelled with fields or bare text, chosen or unselected. Every committed corpus is CHOSEN: invented to fill fields (CLDR, the conventions table, the rules examples), cataloged (GND), filtered to names whose every word aligns with a stated part (both Wikidata corpora, a filter that drops credentials and typos), or picked by someone testing or reporting a case (v1's test names in `corpus.jsonl`, the case-table rows in `corpus_cjk.jsonl` and `corpus_shapes.jsonl`, and the strings reporters typed into `corpus_issues.jsonl`). The last group does hold hand-typed shapes — a job title in the name (`Bob Jones, author`), a credential before the comma (`Washington Jr. MD, Franklin`) — but one instance of each, as chosen. What SURVEY adds is the unselected population and its frequencies: ClinicalTrials.gov's study officials (local corpus `ctgov-officials`, measured 2026-10-21) are typed into a free-text field by sponsors' staff, so they show how often each shape occurs, and hold some no committed corpus does, such as `MBBS,FCPS` with no space. The FEC's individual contributors (local corpus `fec-individuals`, measured 2026-10-22) are unselected too, but mostly a filer's software writing a form's fields in a fixed order, so nearly all of its 1.89 million names share one shape (capitals, family, comma, given) and the hand-typed part is what goes inside the fields (a credential run or a suffix after a second comma): the population for that shape's variants, and blind to case. The UK Electoral Commission's individual donors (local corpus `ukec-individuals`, measured 2026-10-22) are the opposite shape: names as a donee's return gave them, mixed case and in spoken order, `parse()` reading a title in 8,219 of 15,214 (`Mr`, `Lord`, `Sir`) and only 2 holding a comma. Brazil's individual donors to candidates (local corpus `tse-donors`, measured 2026-10-22) are the FEC's comma-less counterpart: 848,351 filed names, nearly all in capitals and in spoken order, full of particles and agnomens (`DE`, `DA`, `DOS`; `FILHO`, `NETO`, `JUNIOR`), each beside the tax registry's name for the same donor, so a typed form can be read against its reference form (205,925 of 854,531 pairs differ). A source that pairs two spellings of one person scores without fields: the parse of each spelling should find the same surname, so where the spellings differ only in what cannot move a surname (accents, case), a disagreement is the parser reading one name two ways, found with no one labelling either (`local_corpora.py pairs --agreement`; on `tse-donors` on 2026-10-22, 1,304 of 43,552 accents-only pairs, 1,121 of them from `JÚNIOR`/`JUNIOR` and `SÁ`/`SA`). Read it per shape: a pair that leaves a word out can change the surname for real. JRC-Names (local corpus `jrc-names`, measured 2026-10-24) widens the pair to a group: one person's spellings harvested from news text across scripts, 218,822 persons with two or more. Words in two scripts cannot be compared, so `local_corpora.py groups` compares the readings' structure instead (title, suffix, given, family, the family's length and where it stands), counting persons. Read it per pair of scripts, since a structure can differ by convention: a script read family first stands its family elsewhere, and a writing variant moves the reading for real (the Arabic comma, katakana with and without `・`). Companies House's people with significant control (local corpus `psc-individuals`, measured 2026-10-22) are unselected and labelled at once: each filer types the name into four boxes (title, forename, middle name, surname) and states a nationality, so the corpus is the one real population a local SCORE reads by nationality. It is filed through a form's boxes, so it holds almost no comma (838 of 1,040,708 sampled records) or credential. One source may do several jobs, each through its own code: Wikidata does COUNT live and WATCH and SCORE through its builders. A live source has no fixed file to pin, so its cached copy is the pin, carrying the source's own data date and a sha256 checked on every load (a truncated file otherwise reads as a run of false zeros, #775).

**Reach for it when.** A source is proposed, before choosing between a builder and a tool column; and when a corpus would hold real people's names nobody vetted for publication, which is the case for a local corpus rather than a committed one.

### PAIRED-SPELLINGS-PER-CHANGE — count both directions, and compare whole fields

**Problem shape.** A change is measured over a source that holds two or more spellings of one person (tse-donors' filed and registry names, nepal-candidates' romanization and Devanagari, a JRC-Names group), and the question is whether it makes the parser read one person one way.

**Contract statement.** Per change, count the persons whose spellings go from reading differently to reading alike AND the persons who go the other way, never a net figure; compare the readings on what the two spellings can share (whole given and family fields with accents folded and an initial matching the word it begins, or, across scripts, the structure alone); and read the "now apart" moves by shape before calling any a regression.

**How it works.** Agreement is not correctness, so this is a second measure beside a SCORE (mechanisms.md#NAME-DATA-JOBS), never in place of one. Its trap is a comparison that agreed for the wrong reason. #752's first version compared the family's LAST WORD as written, and gating the Brazilian agnomens counted 1,043 tse pairs "now apart" (2026-10-24): on master both spellings had agreed on `FILHO` as the family, and once the agnomen read as a suffix the comparison reached the real surname, which the two spellings write differently. Comparing whole fields after folding cut the agnomen gate's apart count to 304, and reading those by shape showed what was left: a word differing between the spellings, an initial, a length difference, and 47 differing only by accent or case, which point at the one real defect: the spike asked a case cue the design does not. Across scripts the same measure found what no single-script corpus could: taking `Guru` out of the titles pushed 44 Nepali pairs apart because its Devanagari twin stayed a title.

**Reach for it when.** A change moves a word between fields in a population that holds the same names spelled twice; and when a vocabulary word has a twin in another script, which a pair source shows and a single-script snapshot cannot.

### Field notes — the traps themselves

- Test a function INSIDE a stage on the inputs its caller hands it, not on the stage's finished output. #610's first sweep test built pieces by running `group` whole and handed them to the maiden take's candidate function, but the take runs before any join, so the test read `de VI Prof.` as one piece where production hands it three: a guard checking a structure production never passes in, green for the wrong reason. Review moved the oracle to the take itself by wrapping it (tests/v2/pipeline/test_pieces.py), and recorded the old loop's misses there as the negative control (432), which is what shows the moved harness can still see a difference.
- Enumerate the rules that BUILD a structure; do not recall them. #395's unit walk was written three times in one PR — P2's chain missing, then the conjunction and bound-given branches absorbing one token where the particle branch absorbed a unit, then the suffix stop — and each miss came from listing the joining rules from memory instead of reading them out of the rules. Both later misses reproduced the very defect the first fix had just removed, mirrored.
- Widening a predicate widens nothing its callers filter out first. A predicate on a hot path often sits behind a C-level pre-check at each call site, a necessary half of it inlined so a word that cannot pass pays no frame (`isalpha()` and `isupper()` ahead of `caps_shape_candidate`), and a widened predicate behind an unwidened pre-check is unreachable: #752's joined capitals (`PU-PH`) failed `isalpha()` at all three call sites, and the 2026-10-23 measurement of the change first moved nothing. Before measuring a widened predicate, grep its call sites for the pre-check and widen each with it, and hold one input the change must move.
- Prefer monkeypatching a module-level helper to re-exec'ing a module: a caller looks a module global up at CALL time, so replacing `_units` or `_name_positions` reaches it and none of the traps below apply. Re-exec is only needed for logic INLINE in a function, and "the thing I want to mutate is not a module-level helper" is a hint that it could be one.
- Re-exec'ing a module redefines the classes that module DEFINES, not the ones it imports — the exec re-runs its own import statements, which resolve through sys.modules. So `is` comparisons break selectively: re-exec'ing `_group.py` yields a second `BoundJoin` (defined there) while `Structure` (imported) stays identical, and `bound_join is not BoundJoin.DISABLED` is then always true, joining a family comma's own segment and reporting 3,150 phantom movers. Rebind what the module defines (`mod.__dict__["BoundJoin"] = real.BoundJoin`) and assert the identity rather than assuming it either way.
- `_pipeline.STAGES` holds function OBJECTS captured at import, so re-exec'ing a stage module leaves the pipeline running the old function and every result is a false negative. Rewire `STAGES` and assert the new function is in it.
- Either route: hold one input the mutation MUST move and one it must NOT, and check both before believing a count. Every trap here produces confident numbers rather than an error.
- Assert which tree you imported, on BOTH sides of a comparison. `python -c` puts CWD on sys.path; a script's own directory holds no nameparser in tools/differential/, so a stray PYTHONPATH outranks the editable install — measured: 89 diffs became 0, exit 0, both tell halves passing, because both sides had become the shadow.
- Release notes describe intent; TAGS are ground truth. Before trusting a changelog cross-reference about what shipped where, run `git diff <tagA> <tagB> -- <file>` — the "1.2.1 pickle shim" claim recurred twice from a changelog line describing a thing that never shipped.
- Never pipe a check's output when its exit code matters. Under zsh, `snapshot.py | tail` makes `$?` tail's status. Redirect to a file and read the file.
- Mutation-test a new guard before believing it, and mutate the thing the guard watches — a survivor usually means the fixture satisfies the invariant for free. A guard over a HAND COPY of a pipeline set has two such holes, and #744's review found both in one test of tools/vocab/build.py's check 2, which copies the tokenizer's sets because the tool cannot import the package it writes. Pinning a copy to its source sees only the classes someone copied: the first test pinned `DIVIDERS` alone, and emoji, which the tokenizer strips under `Policy.strip_emoji`, had no copy and no check, so `dr★` compiled and the test passed. Its replacement swept every codepoint `_tokenize._ignorable` drops but accepted any refusal short of a TOML error, so the space in `dr x` passed because the phrase-title check refused it, and a class check 2 never learned would pass too wherever a later check happened to refuse its test text. Drive the sweep from the pipeline's own predicate, match the refusal by the checked rule's own messages, and record the control (hiding the emoji check behind its pinned constant fails the sweep: `test_every_character_the_tokenizer_ignores_is_refused` in tests/v2/test_vocab.py, which now leaves the space out, a phrase's word separator). The predicate reaches only what it decides, though: the interpunct between East Asian characters (rules/T3) is divided by context in `_tokenize_region`, never by `_ignorable`, so hiding that check passes the sweep (measured in #746's review, 2026-10-19). What holds it is its `MUTATIONS` row (`text-with-an-east-asian-interpunct`, input `先·生`); the `EAST_ASIAN_RANGES` and `INTERPUNCT` pins hold only the copies, and stay green with the check gone. Name such a class where the guard stands, and the test that holds it, rather than let the sweep imply it.
- A claim about what a vocabulary entry DOES is a claim about the parse WITHOUT it, so take that parse (`Parser(lexicon=Lexicon.default().remove(titles={...}))`) and compare: the parse with the entry present shows only that the output is consistent with it. #773's first note on `wm` said that removing it would move `Wm. Smith`, read off the parse with the word listed; with the word removed, `Wm. Smith` read exactly as before, rules/H2's leading-abbreviation title then claiming `Wm.` either way. The corrected note then said only the bare `Wm Smith` moves, and that was wrong too (#789, 2026-10-24): it took the off-switch parse at the head of the name only, and a trailing `Wm.` (rules/H5) and a `Wm.` before a family comma (rules/H6), which read vocabulary rather than shape, moved as well. A shape rule shadows an entry only in the spelling and the slot it reads, so take the off-switch parse for each spelling, bare and period-marked, in each position a rule reads the word in.
- Verify the restore, not just the mutation: diff against the pre-mutation copy; do not trust the harness's own restore report.
- Run all the gates, not the ones you remember: ruff runs before mypy and pytest in CI, and each has caught what the others passed.
- Purge __pycache__ between same-length source mutations; stale bytecode makes a changed file measure as unchanged.
- After NARROWING a rule, check the receiver: the names a narrowed rule sheds land on a neighbour, and nothing guarantees the neighbour's prose describes what it inherited — #375 fixed an over-claiming rule and relocated the bug onto its neighbour. Ask also what the old behavior was CONCEALING: #379's attachment removed the input a test used to build an all-particle middle name (#402), and #400's reserve fix exposed the dual-membership count shape #397 names -- twice in one session a fix's real yield was a defect it stopped hiding.
- A check that is quiet about a name is not evidence that the baseline read it the same. #603's first draft wrote that 1.4.0 read a title past the second comma as a title because no 1.4.0 name moved unexplained, when the 1.4.0 ledger's broad `fix(comma-family)` rule was claiming each one; the released wheel read suffix 'Jr., Attorney General'. Ask the wheel (`PYTHONSAFEPATH=1 uv run --isolated --no-project --with nameparser==X`, from outside the worktree, or `tools/differential/compare.py --baseline X`) before writing what a release did.
- A skip is indistinguishable from "correctly declined": pytest turns an empty parametrize into a skip, and a filter that widens its own skip set cannot fail. After changing any selection shape, verify the guard still REACHES the code it watches — assert the selected set is non-empty, or force-a-decision on its size.
- A differential corpus cannot evidence behavior keyed to OUT-of-vocabulary shapes: it holds only names someone wrote down, and an unrecognized word is by definition outside the vocabulary — a green run over the corpus proves nothing about such a rule.
- The corpus can be near-blind to a WRITING CONVENTION even where the vocabulary is well covered, and a small honest count then reads as a small blast radius. Measured for rules/P6: of 782 corpus names, 245 carry a comma, TWO of those end in a particle, and ONE of the two clears the words-to-spare guard and actually moves — so the Dutch trailing-tussenvoegsel listing the rule exists for is essentially unsampled. Before reporting "N names move", report the size of the population that COULD move; when that is ~1, the number is evidence about the corpus. This note's first wording said "exactly ONE ends in a particle", conflating the population with the movers — the very error it exists to prevent, committed inside the correction. Caught by re-running the count against AGENTS.md's axis 1 rather than by re-reading it.
- An invariant judged on the part a JOIN PRODUCED is satisfied by whatever the join absorbed. #397's both-sides condition was stated as "a name word stands on each side of the link", and the invariant written from that sentence walks the joined part and asks whether a non-connective word stands on each side of the letter — which a swallowed credential answers yes to, being that word. `Josep Lluis Carod i III` read family 'Carod i III' and PASSED it. The merge has already destroyed the evidence, so the question cannot be re-asked downstream at all. Judge on the PRE-join classes, or against a second parse with the rule turned off — the off-switch parse puts the credential in `suffix`, and "no word the off-switch reading calls a suffix lands inside a joined name part" caught it on 639 parses of the shipped grid where the first invariant caught none (960 over the full cross product, a dated snapshot before the grid was trimmed by shape). The same pairing is worth reaching for whenever a rule MERGES tokens.
- A detector that re-implements a rule's grouping will get the grouping wrong. Derive the boundary from the same vocabulary the rule reads, not from the half you happen to be thinking about: walking a particle run over the NEVER-GIVEN set alone (the rule chains through ANY particle) split "de la Vega" after "de la" and reported 50 false movers for #364, where the true count is one. Both wrong answers were plausible and printed cleanly.
- Guard the whole family, parametrize over it: a defect on one of N parallel entry points hides behind a per-example test — three times in one session (a guard on one class of two, a decode hint on 3 of 5 entry points, a sync roster missing 4 copies) — and a {class}×{field}×{bad-value} parametrization is what caught each.
- A growth guard needs calibration, not just existence: benchmark guards that compare n vs 4n catch the quadratic the absolute-time tests are blind to, but calibrate against the WEAKEST signal you must detect and confirm a planted regression fails across repeated runs, not once — a stochastic check "verified" on one sample verifies nothing.
- A frame BUDGET pinned on one reference name cannot see algorithmic blowup; a frame RATIO over two input sizes can. #531's first implementation had a trailing walk re-enter the predicate that owns it, so a run of k ambiguous credentials cost 2**k — `'Doe, John ' + 'MA '*24` took about 6s, wall clock, where the parent commit took 0.24ms (two runs of that one measurement, 5.8s and 5.9s, which is the spread the guard below quotes them at) — while every absolute figure beside the change stayed correct and unmoved: `tools/perf/call_count.py`'s 412/449 on its reference name, and +0 frames on a comma name carrying no class member. The budget is a claim about ONE input and the defect is a claim about a family of them, so no budget is the instrument. The guard that catches it counts frames at 8 members against 16 and bounds THAT ratio (`tests/v2/test_benchmark.py::test_a_trailing_credential_run_does_not_cost_exponentially`): 2,347 → 394,671 frames unfixed, 168x, against 865 → 1,497 and 1.73x fixed, with the bound at 6x. ONE pair does not see every curve, though, and the fix round measured how badly: at 2× the input the per-member linear work swamps a quadratic, so the per-member memo the first fix shipped — a genuine quadratic — reads 2.08x at that pair, inside any bound this one can carry. Separating those needs 4× the input, where the same memo reads 7.42x against the linear 3.53x, so the guard carries a second pair (16 against 64) and asserts the cheap one FIRST: an exponential does not return from a run of 64. Frames rather than a clock for two reasons — the recursion IS frame entries, so the count is the defect rather than a proxy, and the input length that separates an exponential from a linear on a timing test does not finish. It needs the reachability assertion a `_POLICY_SHAPES` row carries, for the same reason: the walk under measurement runs only while every unit still reads as a credential, and a precedence change that routes them elsewhere leaves a green test measuring a walk that no longer happens.
- Mind the optional-extra environment split: a local venv's incidental namedivider makes `if available` branches run PRESENT locally and ABSENT in CI, so a locally-green suite proves nothing about the no-extra path (this broke #337's first landing). Run the decisive check in both states or gate the example.
