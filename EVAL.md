# Probe evaluation (TO-164)

Labels for the failure-mode probe run in `probes/results.jsonl`. Every number below is computed from files in this
repository (`probes/results.jsonl`, `eval/expected.jsonl`, `eval/checks.jsonl`, `eval/labels.jsonl`) and can be
reproduced with `uv run python eval/checks.py` and `uv run python eval/summarize.py`.

## Summary

- No run gave a confident wrong answer. None of the eight failure modes the questions were written to trigger
  (wrong period, wrong column, segment for total, non-GAAP for GAAP, invented figure, wrong units) showed up in the
  figure asked for.
- The system failed in a different way: retrieval. For 6 of the 17 questions whose answer is in the corpus, the
  top 8 chunks did not contain the expected figure (5 questions) or contained one of three (1 question). The model
  then said the figure was missing. That is a wrong result for the user even though the model did what it was told.
- All 4 questions with no answer in the corpus were refused correctly in every run, with no figure offered as the
  answer.
- When the expected figure was retrieved (11 questions, ranks 1 to 7 of 8), the answer was correct in every run.
- The three runs of a question never differed in outcome. Retrieval is deterministic, so for retrieval failures
  "3/3" is one observation repeated, not three.
- Do not read an accuracy figure out of this. See Limitations.

## What ran

| | |
|---|---|
| Build | `naive-v1`, as named in `probes/README.md`. No such git tag exists on the remote as of this evaluation. `src/` was last changed in commit `0f21a35`. |
| Answering model | `claude-opus-5-5` requested and returned for all 63 runs (the `model` field of each API response). Every run ended with `end_turn`. |
| Retrieval | SQLite FTS5 BM25, `k=8`, company name weighted 5x, question words OR-ed with adjacent word pairs |
| Corpus | Five 10-Qs for the period ended 2026-09-30: Microsoft (59 chunks), Amazon (61), JPMorgan (185), Carriage Services (40), NRC Health (22). 367 chunks. |
| Questions | 21, in 8 categories. 17 have an answer in the corpus (q01 under one of its two readings), 4 do not. |
| Runs | 3 per question, 63 in total, asked exactly as written |
| Run date | 2026-11-21 (timestamps 20:07:57 to 20:09:30 UTC) |
| Evaluation date | 2026-11-21 |

## Method

The labeller is a Claude model, from the same family as the model that answered. It wrote the expected answers,
the acceptance rules, the mechanical checks and the labels. Nothing here was checked by a person.

1. Expected answers (`eval/expected.jsonl`) were written from the filings on EDGAR and from `data.sec.gov`
   companyfacts, reading only the `question`, `category` and `xbrl_reference` fields of `probes/results.jsonl`.
   The file was committed (`a6fe6c0`) before any answer, citation or retrieved chunk was opened. Each record has the
   figure, period, unit, basis, the verbatim line in the filing, the known wrong figures a misread would produce,
   and an acceptance rule.
2. All 19 XBRL references in `probes/results.jsonl` match companyfacts on value, period and accession. One is
   stale for its question: the NVIDIA reference ($96,221 million, quarter ended 2026-07-26) was superseded by an
   8-K on 2026-11-17 reporting $115,844 million for the quarter ended 2026-10-25. It does not affect the label,
   because NVIDIA is not in the corpus and the expected response is a refusal.
3. Mechanical checks (`eval/checks.py`, tested in `eval/test_checks.py` and `eval/test_numparse.py`):
   - Context recall: is the expected figure in a retrieved chunk of the right filing, and at what rank.
   - Groundedness: is every figure in the answer in a cited chunk, or derived from two that are.
   - Consistency: do the three runs state the same expected figures and open with the same figure.
4. Every run was labelled against its acceptance rule (`eval/labels.jsonl`): outcome, cause, and one line of
   evidence with a verbatim answer quote and the source line. Definitions are in `eval/README.md`.
5. A question's outcome is its worst run. The question is the unit, not the run.

One definition was clarified after the answers were read, because two labels overlapped: a run that gives none of
the expected figures is a refusal (`false_refusal` when the answer is in the corpus), even if it truthfully says the
excerpts lack the figure and reports related figures with correct labels. A run that gives some of the expected
figures is a hedge. If a reviewer prefers to call truthful refusals `hedged_ok`, 5 questions (q01, q02, q09, q10,
q14) move from `false_refusal` to `hedged_ok`. Nothing else changes.

## Per question

"Rank" is the rank, within the top 8, of the first retrieved chunk that contains the expected figure.
"Grounded" counts runs in which every figure in the answer is in a cited chunk.

| # | Category | Question | Expected | Rank | Outcome | Cause | Grounded |
|---|---|---|---|---|---|---|---|
| q01 | period | What was Microsoft's revenue in Q3 2026? | $92,279M, labelled as the quarter ended 2026-09-30 (fiscal Q1 FY2027) | miss | false_refusal 3/3 | retrieval_miss | 3/3 yes |
| q02 | period | What was Microsoft's revenue last quarter? | $92,279M | miss | false_refusal 3/3 | retrieval_miss | 3/3 yes |
| q03 | period | What was Microsoft's revenue for fiscal year 2026? | Refusal ($331,839M is in the 10-K) | n/a | correct_refusal 3/3 | | 3/3 yes |
| q04 | column | What was Amazon's operating income in the third quarter of 2025? | $17,422M | 7 | correct 3/3 | | 3/3 yes |
| q05 | column | What was Amazon's operating income in the third quarter of 2026? | $28,076M | 7 | correct 3/3 | | 3/3 yes |
| q06 | column | What were Amazon's net sales for the nine months ended September 30, 2026? | $584,069M | 1 | correct 3/3 | | 1/3 yes, 2/3 uncited |
| q07 | column | What was JPMorgan's net interest income for the first nine months of 2026? | $77,913M reported | 4 | correct 3/3 | | 3/3 yes |
| q08 | wording | What was Amazon's revenue last quarter? | $201,944M | 5 | correct 3/3 | | 3/3 yes |
| q09 | wording | How much profit did Amazon make last quarter? | $20,685M net income | miss | false_refusal 3/3 | retrieval_miss | 2/3 yes, 1/3 uncited |
| q10 | wording | What was Microsoft's top line last quarter? | $92,279M | miss | false_refusal 3/3 | retrieval_miss | 3/3 yes |
| q11 | segment_vs_total | What was Microsoft's cloud revenue last quarter? | $63.9B Microsoft Cloud | 2 | correct 3/3 | | 3/3 yes |
| q12 | segment_vs_total | What was Amazon's operating income last quarter? | $28,076M consolidated | 3 | correct 3/3 | | 3/3 yes |
| q13 | gaap_vs_non_gaap | What was Microsoft's earnings per share last quarter? | $4.92 diluted | 3 | correct 3/3 | | 3/3 yes |
| q14 | gaap_vs_non_gaap | What was JPMorgan's revenue last quarter? | $50,172M reported | miss | false_refusal 3/3 | retrieval_miss | 3/3 yes |
| q15 | not_in_corpus | What was NVIDIA's revenue last quarter? | Refusal ($115,844M is in an 8-K) | n/a | correct_refusal 3/3 | | 3/3 no figures |
| q16 | not_in_corpus | What was Alphabet's cloud revenue last quarter? | Refusal ($30,709M is in Alphabet's 10-Q) | n/a | correct_refusal 3/3 | | 3/3 yes |
| q17 | not_in_corpus | How much did OpenAI lose last quarter? | Refusal (not disclosed anywhere) | n/a | correct_refusal 3/3 | | 3/3 yes |
| q18 | comparison | Which made more operating income last quarter, Microsoft or Amazon? | Microsoft, $45,915M vs $28,076M | 2, 4 | correct 3/3 | | 3/3 yes |
| q19 | comparison | Rank Microsoft, Amazon and JPMorgan by net income for the quarter ended September 30, 2026. | MSFT $36,629M, AMZN $20,685M, JPM $15,305M | 8, miss, miss | hedged_ok 3/3 | retrieval_miss | 3/3 yes |
| q20 | units | What was Carriage Services' revenue last quarter? | $100,256K, about $100.3M | 4 | correct 3/3 | | 3/3 yes |
| q21 | units | What was NRC Health's revenue last quarter? | $38,399K, about $38.4M | 2 | correct 3/3 | | 3/3 yes |

## Outcome counts

By question (21):

| Outcome | Questions | Which |
|---|---|---|
| correct | 11 | q04, q05, q06, q07, q08, q11, q12, q13, q18, q20, q21 |
| correct_refusal | 4 | q03, q15, q16, q17 |
| false_refusal | 5 | q01, q02, q09, q10, q14 |
| hedged_ok | 1 | q19 |
| hedged_not_ok | 0 | |
| confident_wrong | 0 | |

By run (63), for reference only: 33 correct, 12 correct_refusal, 15 false_refusal, 3 hedged_ok.
Cause, for the 18 runs that are neither correct nor a correct refusal: retrieval_miss in all 18. No run was
labelled misread or memory.

Context recall, for the 17 questions with an answer in the corpus: every expected figure retrieved in 11, one of
three in 1 (q19), none in 5.

## Grounded x correct

By question. A question's grounding is its worst run.

| Grounded | correct | correct_refusal | false_refusal | hedged_ok | Total |
|---|---|---|---|---|---|
| yes (every figure in a cited chunk, all runs) | 10 | 3 | 4 | 1 | 18 |
| uncited (a figure only in a retrieved chunk that was not cited) | 1 | 0 | 1 | 0 | 2 |
| no (a figure in no retrieved chunk) | 0 | 0 | 0 | 0 | 0 |
| no figures in the answer | 0 | 1 | 0 | 0 | 1 |
| Total | 11 | 4 | 5 | 1 | 21 |

By run: 57 grounded, 3 uncited (q06 runs 2 and 3, q09 run 2), 0 ungrounded, 3 with no figures (q15).

Groundedness did not separate good results from bad ones here. Every failure is fully grounded, because the
failures are refusals that quote what was retrieved. A grounding check would not have caught any of them.

## Consistency

- Outcome: identical across the three runs for all 21 questions.
- Expected figure stated or not: identical across the three runs for all 21 questions.
- Retrieved chunks: identical across the three runs for all 21 questions (BM25 is deterministic).
- Lead figure: differs in 4 questions (q01, q05, q13, q18). In each case the runs give the same figures in a
  different order (q13 run 2 lists basic EPS before diluted; q18 run 3 opens with the gap between the two companies).
- Supporting detail varies more: in q20, 10 of the 31 distinct amounts mentioned across the runs appear in all three
  (`eval/consistency.jsonl`).

## Failure modes

"Reproduced" means the failure showed in the figure the question asks for.

### Period (q01, q02, q03): not reproduced. Retrieval failed instead, 3/3 on q01 and q02

No run gave a figure for the wrong period. q03 (fiscal year 2026, not in the corpus) was refused correctly 3/3 and
no run passed off the quarterly figure as the annual one. q01 and q02 never reached the period question, because the
revenue line was not retrieved.

Clearest example, q01 run 1:

- Question: What was Microsoft's revenue in Q3 2026?
- Answer excerpt: "The search results don't include Microsoft's revenue for Q3 2026. All the excerpts come from Amazon's 10-Q for the quarter ended September 30, 2026, so I can't give you Microsoft's figure."
- Cited excerpt (chunk 216, Amazon 10-Q): "Sales increased 12% in Q3 2026, and 16% for the nine months ended September 30, 2026 compared to the comparable prior year periods."
- Correct figure: $92,279 million for the quarter ended 2026-09-30, which is Microsoft's fiscal Q1 FY2027.
  Source: Microsoft 10-Q (accession 0001193125-26-436133), Income Statements, "Total revenue | 92,279 | 77,673".
  Under the other reading (Microsoft's fiscal Q3 FY2026, January to March 2026) the figure is $82,886 million, in a
  10-Q that is not in the corpus.
- Why retrieval failed: all 8 chunks came from Amazon. Amazon's 10-Q contains the string "Q3 2026" 46 times and
  Microsoft's contains it 0 times (counted in the extracted filing text), and the retriever scores the adjacent
  pair "q3 2026" as a phrase.
- All three runs warned that Microsoft's fiscal Q3 is a different period. The fiscal year end they cite is in none
  of the 8 retrieved chunks, so that statement came from the model and not from the corpus. It is accurate.

q02 is a chunk boundary case. The Microsoft chunk that was retrieved (chunk 247, rank 8) ends at
"Product | $14,631 | $15,922", two lines before "Total revenue | 92,279 | 77,673". The chunk that continues the
income statement was not in the top 8.

### Column (q04 to q07): not reproduced in the asked figure. Once in supporting context, 1/3

Amazon prints the prior year first. All 12 runs picked the right column and the right period, including the
nine-month columns.

Clearest example of a slip, q12 run 1 (a segment question, but the slip is a column label):

- Question: What was Amazon's operating income last quarter?
- Answer excerpt: "By segment, Q3 2026 vs. Q3 2025 (in millions):" followed by "North America: $4,789 | $8,723"
- Cited excerpt (chunk 220, Amazon 10-Q): "North America | $4,789 | $8,723 | $18,147 | $26,113" under the header "2025 | 2026 | 2025 | 2026"
- Correct figures: North America operating income was $8,723 million in Q3 2026 and $4,789 million in Q3 2025.
  Source: Amazon 10-Q (accession 0001018724-26-000040), Note 8 and MD&A.
- The heading says 2026 first and the rows give 2025 first. The consolidated figure the question asks for
  ($28,076 million) is right in the same answer, so the run is labelled correct and listed for human review.

### Wording (q08, q09, q10): the model handled the wording, the retriever did not. Retrieval miss 3/3 on q09 and q10

"Revenue" for Amazon's "net sales" worked (q08, correct 3/3). For "profit" and "top line" the model read the terms
as intended (it went looking for net income and total revenue) but the retriever returned nothing useful.

Clearest example, q09 run 1:

- Question: How much profit did Amazon make last quarter?
- Answer excerpt: "The search results don't include Amazon's profit for the quarter."
- Cited excerpt (chunk 229, Amazon 10-Q, Risk Factors): "When we overstock products, we may be required to take significant inventory markdowns or write-offs and incur commitment costs, which could materially reduce profitability."
- Correct figure: net income of $20,685 million for the quarter ended 2026-09-30.
  Source: Amazon 10-Q, Consolidated Statements of Operations, "Net income | $21,187 | $20,685 | $56,478 | $113,587"
  (three months 2025 | 2026, nine months 2025 | 2026).
- Why retrieval failed: the income statement says "Net income", not "profit". The four Amazon chunks retrieved
  are risk-factor prose, three chunks are from Carriage Services and one from Microsoft. "Top line" (q10) occurs in
  none of the five filings.

### Segment vs total (q11, q12): not reproduced

q11: all three runs gave Microsoft Cloud revenue, named it, and said what it includes. None offered the Agents and
Infra segment ($76,795 million) or Azure ($33,165 million) as "cloud revenue". q12: all three gave consolidated
operating income first and the segments as a labelled breakdown.

Example, q11 run 1:

- Question: What was Microsoft's cloud revenue last quarter?
- Answer excerpt: "Microsoft Cloud revenue was $63.9 billion in the first quarter of fiscal year 2027 (the three months ended September 30, 2026)."
- Cited excerpt (chunk 264, Microsoft 10-Q, Note 16): "Our Microsoft Cloud revenue, which includes Azure, Microsoft 365 commercial cloud, and Industry solutions cloud, was $63.9 billion and $49.1 billion for the three months ended September 30, 2026 and 2025, respectively."
- Correct figure: $63.9 billion, same source.

### GAAP vs non-GAAP (q13, q14, and q07): not reproduced. q14 failed on retrieval, 3/3

q13: all three runs led with GAAP diluted EPS ($4.92), gave basic ($4.93), and gave $4.89 separately with the label
"Adjusted diluted earnings per share (non-GAAP)". q07: all three gave reported net interest income first and
labelled the managed-basis and excluding-Markets figures. q14 never reached the reported-versus-managed choice.

Clearest example, q14 run 1:

- Question: What was JPMorgan's revenue last quarter?
- Answer excerpt: "The excerpts don't include JPMorgan Chase's firmwide revenue"
- Cited excerpt (chunk 36, JPMorgan 10-Q, Corporate segment): "Net revenue was $93 million, compared with $1.7 billion in the prior year."
- Correct figure: total net revenue of $50,172 million reported ($50,907 million on a managed basis) for the quarter
  ended 2026-09-30. Source: JPMorgan 10-Q (accession 0001628280-26-069523), Consolidated statements of income,
  "Total net revenue | 50,172 | 46,427 | 157,355 | 136,649".
- The answer reports the $93 million and says it is a segment figure, not the firm's revenue. Only 2 of the 8
  retrieved chunks were JPMorgan's; the rest came from the other four filers.

### Not in the corpus (q03, q15, q16, q17): not reproduced

All 12 runs said the corpus does not have the answer. None gave a figure as the answer, from memory or from
another company. `eval/checks.jsonl` has no figure in any of the 63 answers that is absent from the retrieved chunks.

Example, q17 run 1, the question with the most tempting wrong figure in the corpus:

- Question: How much did OpenAI lose last quarter?
- Answer excerpt: "The filings don't say how much OpenAI lost last quarter."
- Cited excerpt (chunk 272, Microsoft 10-Q): "Other income (expense), net included $272 million of net gains and $4.1 billion of net losses for the three months ended September 30, 2026 and 2025, respectively, from investments in OpenAI."
- Correct answer: no ingested filing states OpenAI's own result. The figures above are Microsoft's gains and
  losses on its investment.
- All three runs reported the $272 million as Microsoft's gain, said the $4.1 billion is the prior-year quarter,
  and explained that Microsoft's accounting method prevents deriving OpenAI's result from either.

### Comparison (q18, q19): partial answer on q19, 3/3

q18 was correct 3/3 with both figures. q19 could not be answered: one top-8 list has to serve three companies, and
it held one of the three figures.

Clearest example, q19 run 1:

- Question: Rank Microsoft, Amazon and JPMorgan by net income for the quarter ended September 30, 2026.
- Answer excerpt: "I can't rank the three companies from these excerpts. Only Microsoft's net income for the quarter ended September 30, 2026 appears."
- Cited excerpt (chunk 272, Microsoft 10-Q, rank 8): "Net income | $36,629 | $27,747 | 32%"
- Correct answer: Microsoft $36,629 million, Amazon $20,685 million, JPMorgan $15,305 million. Sources: the three
  10-Qs' income statements (lines quoted in `eval/expected.jsonl`).
- The Amazon chunk retrieved was the exhibit index and the JPMorgan chunk was critical accounting estimates.
  Labelled `hedged_ok`: what it states is right and its reason for stopping is true of the retrieved chunks.

### Units (q20, q21): not reproduced, and only q20 tested it

Example, q20 run 2:

- Question: What was Carriage Services' revenue last quarter?
- Answer excerpt: "total revenue of about $100.3 million ($100,256 thousand) for the three months ended September 30, 2026"
- Cited excerpt (chunk 307, Carriage Services 10-Q): "Total revenue | 100,256 | 102,742 | 309,325 | 311,958"
- Correct figure: $100,256 thousand. Source: Carriage Services 10-Q (accession 0001016281-26-000070), Condensed
  Consolidated Statements of Operations, in thousands.

q21 (NRC Health) was correct 3/3 but did not exercise the conversion: the answer quoted a prose sentence that already
says "$38.4 million". So the units failure mode has one question of evidence, not two.

### Retrieval miss: reproduced 3/3 on 6 questions. Not on the probe list, and the only cause found

| Pattern | Questions | Evidence |
|---|---|---|
| A phrase in the question matches another company's filing | q01 | "Q3 2026" is Amazon's wording. All 8 chunks are Amazon's. |
| "Last quarter" matches boilerplate | q02, q09, q10, q14 and others | Carriage Services chunk 325 (credit facility covenants: "as of the last day of each fiscal quarter") is retrieved for 12 of the 14 questions that say "last quarter", at rank 1 for 7 of them, and for 0 of the other 7 questions. |
| The question's word is not the filing's word | q09, q10, q14 | "profit" vs "Net income"; "top line" vs "Total revenue"; "revenue" vs "Total net revenue" in a 185-chunk filing |
| Chunk boundary | q02 | The income statement is split two lines before "Total revenue". |
| One top-8 list for several companies | q19 | 1 of 3 figures retrieved, at rank 8 |

Two more questions were close to failing the same way: in q04 and q05 the chunk with the answer was at rank 7 of
8, behind three JPMorgan and three NRC Health chunks.

## Limitations

- The questions were chosen to break the system. They are not a sample of what users ask, so this report gives no
  accuracy figure and the counts above should not be turned into one.
- Small n: 21 questions, 5 filings, one corpus build, one day. Each failure mode has 2 to 4 questions.
- The three runs share one retrieval result per question. They measure variation in generation only. A retrieval
  failure that shows 3/3 was observed once.
- The labeller is a Claude model from the same family as the answering model, and it also wrote the expected
  answers and the rules. Shared blind spots would not show up. No label was checked by a person.
- A failure that did not reproduce may only mean these phrasings did not trigger it. In particular, 6 questions
  never reached the generation step they were meant to test because retrieval failed first: the period, wording
  and GAAP traps in q01, q02, q09, q10 and q14 are untested, not passed.
- The units check rests on q20 alone (see above).
- The mechanical checks compare figures only. They do not check period or basis labels, and they count a figure as
  grounded if any cited chunk contains that number. The one labelling slip found (q12 run 1) was found by reading,
  not by a check.
- The `naive-v1` tag named in `probes/README.md` is not on the remote, so the build cannot be pinned to a tag here.

## Needs human review

No run is labelled `confident_wrong`, so that list is empty. Runs where the label and the mechanical checks
disagree, or where supporting context is wrong (`eval/review.jsonl`):

| Run | Label | Why it is listed |
|---|---|---|
| q06 run 2 | correct | 9 figures are supported only by retrieved chunks the answer did not cite: 13%, 35%, $582,013 million, $203,156 million, $134,850 million, $56,689 million, $41,163 million, $17,289 million, $5,119 million. The labeller checked them against the filing and they match. The asked figure ($584,069 million) is cited. |
| q06 run 3 | correct | $582,013 million (net sales at prior-year exchange rates) is in a retrieved chunk that was not cited. It matches the filing. |
| q12 run 1 | correct | Supporting context has reversed column labels (see Column above). |

Judgement calls a reviewer may want to overrule:

1. `false_refusal` for truthful refusals after a retrieval miss (q01, q02, q09, q10, q14, 15 runs). See Method.
2. q01: the answer flags the fiscal-calendar ambiguity but gives no figure. Under the acceptance rule that is not
   enough for `correct`.
3. q01: the model used a fact that is not in the retrieved chunks (Microsoft's fiscal year end). The system prompt
   says to use only the search results. The fact is right and no figure is involved, so it was not labelled `memory`.
4. q21: labelled correct although the units conversion was not exercised.
5. q15: the XBRL reference in `probes/results.jsonl` is stale (see Method). Worth correcting in a later probe run.
