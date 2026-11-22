# Probe evaluation (TO-164)

Labels for the two failure-mode probe rounds in `probes/round1/results.jsonl` (questions q01 to q21) and
`probes/round2/results.jsonl` (q22 to q37). Every number below is computed from files in this repository
(`probes/round*/results.jsonl`, `eval/expected.jsonl`, `eval/checks.jsonl`, `eval/labels.jsonl`) and can be
reproduced with `uv run python eval/checks.py` and `uv run python eval/summarize.py`.

Round 1 was evaluated on 2026-11-21. Round 2 was evaluated on 2026-11-22 with the same method. The round 1 expected
answers and labels are carried over unchanged from the first evaluation; they were not read again. The mechanical
checks were re-run on both rounds.

## Summary

- No run gave a confident wrong answer in either round: 0 of 111 runs, 0 of 37 questions. None of the traps the
  questions were written to spring showed up as a wrong figure. Round 2 added cash flow periods, computed figures,
  changes, false premises, ambiguous figures and facts outside the tables.
- The system fails at retrieval, in both rounds. Of the 31 questions whose answer is in the corpus, the top 8
  chunks lacked the expected line in 11 and held one figure of three in 1. Of those 12, 10 ended without a full
  answer (7 false refusals, 3 hedges). In the other 2, both in round 2, the model reached the right answer from
  other retrieved figures (q27, q29).
- When the expected figure, or every input of a computed one, was retrieved (19 questions), the answer was correct
  in every run.
- All 6 questions with no answer in the corpus were refused correctly in every run, with no figure offered as the
  answer.
- No false premise was accepted. Two were rejected with the right figure in every run (q32, q33). One was not
  accepted but could not be corrected, because the total revenue line was not retrieved (q31).
- The model did arithmetic it was not handed, and got it right in every run where the inputs were retrieved: a
  share (q26), a difference (q28), a change (q30), a ratio (q27), a total rebuilt from two segments (q29).
- One new kind of slip in round 2: a correct refusal with a mislabelled supporting figure, because a footnote was
  retrieved without the table row it belongs to (q36, 2 of 3 runs).
- The three runs of a question never differed in outcome. Retrieval is deterministic, so for retrieval failures
  "3/3" is one observation repeated, not three.
- Do not read an accuracy figure out of this. See Limitations.

## What ran

| | Round 1 | Round 2 |
|---|---|---|
| Build | `naive-v1`, as named in `probes/round1/README.md` | Same build and same database (`probes/round2/README.md`) |
| Answering model | `claude-opus-5-5` requested and returned for all 63 runs (the `model` field of each API response). Every run ended with `end_turn`. | `claude-opus-5-5` requested and returned for all 48 runs. Every run ended with `end_turn`. |
| Questions | 21 (q01 to q21), in 8 categories. 17 have an answer in the corpus (q01 under one of its two readings), 4 do not. | 16 (q22 to q37), in 6 categories. 14 have an answer in the corpus (5 of them computed from figures in it), 2 do not. |
| Runs | 3 per question, 63 in total, asked exactly as written | 3 per question, 48 in total, asked exactly as written |
| Run date | 2026-11-21 (timestamps 20:07:57 to 20:09:30 UTC) | 2026-11-22 (timestamps 03:18:30 to 03:20:03 UTC) |
| Evaluation date | 2026-11-21 | 2026-11-22 |

Both rounds:

| | |
|---|---|
| Build tag | No `naive-v1` git tag exists on the remote as of 2026-11-22, although both probe prompts ask for it. `src/` was last changed in commit `0f21a35`. |
| Retrieval | SQLite FTS5 BM25, `k=8`, company name weighted 5x, question words OR-ed with adjacent word pairs |
| Corpus | Five 10-Qs for the period ended 2026-09-30: Microsoft (59 chunks), Amazon (61), JPMorgan (185), Carriage Services (40), NRC Health (22). 367 chunks. |
| Totals | 37 questions, 111 runs |

## Method

The labeller is a Claude model, from the same family as the model that answered. It wrote the expected answers,
the acceptance rules, the mechanical checks and the labels. Nothing here was checked by a person. The two rounds
were labelled in two separate sessions.

1. Expected answers (`eval/expected.jsonl`) were written from the filings on EDGAR and from `data.sec.gov`
   companyfacts, reading only the `question`, `category` and `xbrl_reference` fields of each `results.jsonl`.
   Each round's records were committed before any answer, citation or retrieved chunk of that round was opened
   (round 1 in `a6fe6c0`, round 2 in `a6e291d`). Each record has the figure, period, unit, basis, the verbatim line
   in the filing, the known wrong figures a misread would produce, and an acceptance rule. For a computed answer
   the record gives the arithmetic and the source lines of its inputs.
2. XBRL references. All 19 in round 1 and all 26 in round 2 match companyfacts on value, period and accession.
   Two do not fit their question:
   - q15 (round 1): the NVIDIA reference ($96,221 million, quarter ended 2026-07-26) was superseded by an 8-K on
     2026-11-17 reporting $115,844 million for the quarter ended 2026-10-25. It does not affect the label, because
     NVIDIA is not in the corpus and the expected response is a refusal.
   - q24 (round 2): the reference is NRC Health's nine-month operating cash flow, with a note that no three-month
     value is tagged. That is true of companyfacts, but the filing states the quarter ($8,020 thousand) in its free
     cash flow reconciliation, and that is the expected answer.
3. Mechanical checks (`eval/checks.py`, tested in `eval/test_checks.py` and `eval/test_numparse.py`):
   - Context recall: is the expected figure in a retrieved chunk of the right filing, and at what rank. For a
     computed answer, recall is judged on its inputs.
   - Groundedness: is every figure in the answer in a cited chunk, or derived from figures that are.
   - Consistency: do the three runs state the same expected figures and open with the same figure.
4. Every run was labelled against its acceptance rule (`eval/labels.jsonl`): outcome, cause, and one line of
   evidence with a verbatim answer quote and the source line. Definitions are in `eval/README.md`.
5. A question's outcome is its worst run. The question is the unit, not the run.

Definitions clarified after answers were read:

- Round 1: a run that gives none of the expected figures is a refusal (`false_refusal` when the answer is in the
  corpus), even if it truthfully says the excerpts lack the figure and reports related figures with correct
  labels. A run that gives some of the expected figures is a hedge. If a reviewer prefers to call truthful
  refusals `hedged_ok`, 7 questions (q01, q02, q09, q10, q14, q25, q34) move from `false_refusal` to `hedged_ok`.
  Nothing else changes.
- Round 2: where a question's own acceptance rule, written before the answers were read, says what a partial
  response is, the rule wins over that convention. This applies to q22 (the trailing-twelve-month figure given
  with its label) and q31 (the premise not accepted, but not corrected). Both are `hedged_ok`. If a reviewer
  applies the round 1 convention instead, q31 becomes `false_refusal`.

Changes to the checks since the round 1 evaluation: percentages, share counts and names can be expected values; a
percentage in an answer can match a bare table cell; a figure can be derived from three others; a scale word after
accounting parentheses is read ("$(42.4) billion"). Re-running on round 1 changed one row: in q06 run 2, two
percentages that were listed as uncited now count as grounded. No round 1 label or count changed.

## Per question

"Rank" is the rank, within the top 8, of the first retrieved chunk that contains the expected figure.
"Grounded" counts runs in which every figure in the answer is in a cited chunk.

### Round 1

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

### Round 2

For computed answers the rank is that of the inputs.

| # | Category | Question | Expected | Rank | Outcome | Cause | Grounded |
|---|---|---|---|---|---|---|---|
| q22 | period | What was Amazon's free cash flow last quarter? | About -$33,456M, computed from the three-month cash flow lines. The filing states only the trailing-twelve-month figure, $(42,357)M. | miss | hedged_ok 3/3 | retrieval_miss | 3/3 yes |
| q23 | period | What was JPMorgan's cash flow from operating activities in the third quarter of 2026? | Refusal (the 10-Q has nine-month cash flows only: $(203,883)M) | n/a | correct_refusal 3/3 | | 2/3 yes, 1/3 uncited |
| q24 | period | What was NRC Health's operating cash flow last quarter? | $8,020K, about $8.0M | 2 | correct 3/3 | | 3/3 yes |
| q25 | computed | What was Amazon's operating margin last quarter? | 13.9%, computed (28,076 / 201,944) | miss | false_refusal 3/3 | retrieval_miss | 3/3 yes |
| q26 | computed | What share of Microsoft's revenue came from Microsoft Cloud last quarter? | About 69%, computed ($63.9B / $92,279M) | 2, 3 | correct 3/3 | | 3/3 yes |
| q27 | computed | What was JPMorgan's efficiency ratio last quarter? | 54% (the overhead ratio) | miss (both inputs at 5) | correct 3/3 | | 3/3 yes |
| q28 | computed | By how many dollars did Amazon's net sales grow year over year last quarter? | $21,775M, computed (201,944 - 180,169) | 2 | correct 3/3 | | 3/3 yes |
| q29 | change | By what percentage did Carriage Services' revenue change compared with the same quarter last year? | A 2.4% decrease | miss (segment totals at 3 and 7) | correct 3/3 | | 3/3 yes |
| q30 | change | Did NRC Health's net income rise or fall last quarter compared with a year earlier, and by how much? | Rose by $582K, about 14% | 3 | correct 3/3 | | 3/3 yes |
| q31 | false_premise | Why did Microsoft's revenue fall last quarter? | Premise false: revenue rose 19%, to $92,279M | miss | hedged_ok 3/3 | retrieval_miss | 3/3 yes |
| q32 | false_premise | Why did JPMorgan report a net loss last quarter? | Premise false: net income was $15,305M | 2 | correct 3/3 | | 2/3 yes, 1/3 uncited |
| q33 | false_premise | How much did Amazon's AWS segment lose last quarter? | Premise false: AWS operating income was $17,773M | 2 | correct 3/3 | | 3/3 yes |
| q34 | which_figure | What was Carriage Services' total debt at the end of last quarter? | $516,204K long-term debt, named as such | miss | false_refusal 3/3 | retrieval_miss | 3/3 yes |
| q35 | which_figure | How many NRC Health shares were outstanding? | 21,221,538 | 3 | correct 3/3 | | 3/3 yes |
| q36 | facts_outside_the_tables | What did JPMorgan agree to pay for the Apple Card portfolio? | Refusal (the 10-Q states no price) | n/a | correct_refusal 3/3 | | 3/3 yes |
| q37 | facts_outside_the_tables | Who signed Carriage Services' 10-Q as principal executive officer? | No one. John Enwright signed, as Principal Financial Officer. | 5 | correct 3/3 | | 3/3 yes |

For q31, `eval/checks.jsonl` reports two of the three expected figures as retrieved (ranks 7 and 8). Both are
coincidences: "$14.6 billion" matches product revenue of 14,631 and "19%" matches an unrelated cell. Neither
source line is in a retrieved chunk, so the table says miss.

## Outcome counts

By question:

| Outcome | Round 1 | Round 2 | Both | Which |
|---|---|---|---|---|
| correct | 11 | 10 | 21 | q04, q05, q06, q07, q08, q11, q12, q13, q18, q20, q21, q24, q26, q27, q28, q29, q30, q32, q33, q35, q37 |
| correct_refusal | 4 | 2 | 6 | q03, q15, q16, q17, q23, q36 |
| false_refusal | 5 | 2 | 7 | q01, q02, q09, q10, q14, q25, q34 |
| hedged_ok | 1 | 2 | 3 | q19, q22, q31 |
| hedged_not_ok | 0 | 0 | 0 | |
| confident_wrong | 0 | 0 | 0 | |
| Total | 21 | 16 | 37 | |

By run, for reference only:

| Outcome | Round 1 | Round 2 | Both |
|---|---|---|---|
| correct | 33 | 30 | 63 |
| correct_refusal | 12 | 6 | 18 |
| false_refusal | 15 | 6 | 21 |
| hedged_ok | 3 | 6 | 9 |
| Total | 63 | 48 | 111 |

Cause, for the 30 runs that are neither correct nor a correct refusal: retrieval_miss in all 30 (18 in round 1,
12 in round 2). No run was labelled misread or memory.

Context recall, for the questions with an answer in the corpus:

| | Round 1 | Round 2 | Both |
|---|---|---|---|
| Every expected figure, or every input, retrieved | 11 | 8 | 19 |
| One of three retrieved (q19) | 1 | 0 | 1 |
| Expected line not retrieved, answer not reached | 5 | 4 (q22, q25, q31, q34) | 9 |
| Expected line not retrieved, answered correctly from other retrieved figures | 0 | 2 (q27, q29) | 2 |
| Total | 17 | 14 | 31 |

## Grounded x correct

By question. A question's grounding is its worst run.

Round 1:

| Grounded | correct | correct_refusal | false_refusal | hedged_ok | Total |
|---|---|---|---|---|---|
| yes (every figure in a cited chunk, all runs) | 10 | 3 | 4 | 1 | 18 |
| uncited (a figure only in a retrieved chunk that was not cited) | 1 | 0 | 1 | 0 | 2 |
| no (a figure in no retrieved chunk) | 0 | 0 | 0 | 0 | 0 |
| no figures in the answer | 0 | 1 | 0 | 0 | 1 |
| Total | 11 | 4 | 5 | 1 | 21 |

Round 2:

| Grounded | correct | correct_refusal | false_refusal | hedged_ok | Total |
|---|---|---|---|---|---|
| yes | 9 | 1 | 2 | 2 | 14 |
| uncited | 1 | 1 | 0 | 0 | 2 |
| no | 0 | 0 | 0 | 0 | 0 |
| no figures in the answer | 0 | 0 | 0 | 0 | 0 |
| Total | 10 | 2 | 2 | 2 | 16 |

Both rounds:

| Grounded | correct | correct_refusal | false_refusal | hedged_ok | Total |
|---|---|---|---|---|---|
| yes | 19 | 4 | 6 | 3 | 32 |
| uncited | 2 | 1 | 1 | 0 | 4 |
| no | 0 | 0 | 0 | 0 | 0 |
| no figures in the answer | 0 | 1 | 0 | 0 | 1 |
| Total | 21 | 6 | 7 | 3 | 37 |

By run: round 1 has 57 grounded, 3 uncited (q06 runs 2 and 3, q09 run 2), 0 ungrounded, 3 with no figures (q15).
Round 2 has 46 grounded, 2 uncited (q23 run 1, q32 run 2), 0 ungrounded. Both rounds: 103, 5, 0 and 3 of 111.

Groundedness did not separate good results from bad ones in either round. Every failure is fully grounded,
because the failures are refusals and hedges that quote what was retrieved. A grounding check would not have
caught any of them. It also passed the one mislabelled figure found in round 2 (q36): the number is in the cited
chunk, and what is wrong is what the answer says the number is.

## Consistency

- Outcome: identical across the three runs for all 37 questions.
- Expected figure stated or not: identical across the three runs for all 37 questions.
- Retrieved chunks: identical across the three runs for all 37 questions (BM25 is deterministic).
- Lead figure: differs in 4 questions of round 1 (q01, q05, q13, q18) and 4 of round 2 (q22, q27, q31, q33). In
  each case the runs give the same figures in a different order (q13 run 2 lists basic EPS before diluted; q18
  run 3 opens with the gap between the two companies; q33 runs 1 and 3 open by quoting the segment table, run 2
  with prose).
- Supporting detail varies more: in q20, 10 of the 31 distinct amounts mentioned across the runs appear in all three
  (`eval/consistency.jsonl`). The supporting-context slip in q36 appears in runs 1 and 3 and not in run 2.

## Failure modes, round 1

"Reproduced" means the failure showed in the figure the question asks for.

### Period, fiscal and calendar (q01, q02, q03): not reproduced. Retrieval failed instead, 3/3 on q01 and q02

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
another company. Across all 63 answers, `eval/checks.jsonl` has no figure that is absent from the retrieved chunks,
apart from differences and percentages computed from figures that are in them. The same holds for the 48 round 2
answers.

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

## Failure modes, round 2

### Period, cash flow (q22, q23, q24): not reproduced. q22 stopped at retrieval, 3/3

The trap: a 10-Q cash flow statement is year to date, and Amazon states free cash flow only for the trailing
twelve months. No run passed a longer period off as the quarter. q24: all three runs took the three-month figure
from the free cash flow reconciliation ($8,020 thousand) and gave the nine-month figure separately, labelled.
q23: refused correctly 3/3, but the cash flow statement was not retrieved, so the nine-month figure was never in
front of the model and the trap was not exercised. q22: the three-month cash flow lines were not retrieved.

Clearest example, q22 run 2:

- Question: What was Amazon's free cash flow last quarter?
- Answer excerpt: "The filing doesn't report a single-quarter free cash flow figure for Amazon." and "Free cash flow was $(42,357) million, compared with $14,788 million for the twelve months ended September 30, 2025."
- Cited excerpt (chunk 222, Amazon 10-Q, rank 1): "Free cash flow | $14,788 | $(42,357)" under the header "Twelve Months Ended September 30," and "2025 | 2026"
- Correct figure: about -$33,456 million for the quarter ended 2026-09-30, computed on Amazon's definition from
  the three-month columns: 42,422 - 77,259 + 1,381. Source: Amazon 10-Q (accession 0001018724-26-000040),
  Consolidated Statements of Cash Flows, "Net cash provided by (used in) operating activities | 35,525 | 42,422 | ...",
  "Purchases of property and equipment | ( 35,095 ) | ( 77,259 ) | ...", "Proceeds from property and equipment
  sales and incentives | 867 | 1,381 | ...".
- Why retrieval failed: 2 of the 8 chunks were Amazon's. Three came from NRC Health and three from Carriage
  Services. "Free cash flow" occurs 17 times in NRC Health's filing and 10 times in Amazon's, and the cash flow
  statement itself does not contain the phrase.
- Labelled `hedged_ok`: the figure given is right, labelled trailing twelve months, and the answer says the
  quarter cannot be computed from the excerpts, which is true of them.

### Computed (q25 to q28): not reproduced where the inputs were retrieved. Retrieval miss on q25, 3/3

q26 and q28: right inputs, right arithmetic, 3/3, and each run says the result is its own calculation. q27: the
stated ratio (54%) was not retrieved; all three runs mapped "efficiency ratio" to JPMorgan's "overhead ratio",
computed 54.4% from noninterest expense and total net revenue, and labelled it an estimate. q25 never got
Amazon's income statement.

Clearest example, q25 run 1:

- Question: What was Amazon's operating margin last quarter?
- Answer excerpt: "The search results don't contain any filings from Amazon, so I can't tell you its operating margin for last quarter."
- Cited excerpt (chunk 357, NRC Health 10-Q, rank 3): "Operating margin | 23% | 22% | 1"
- Correct figure: 13.9% for the quarter ended 2026-09-30, computed: operating income 28,076 / net sales 201,944.
  Source: Amazon 10-Q, Consolidated Statements of Operations, "Operating income | 17,422 | 28,076 | 54,998 | 79,389"
  and "Total net sales | 180,169 | 201,944 | 503,538 | 584,069" (three months 2025 | 2026 first).
- Why retrieval failed: none of the 8 chunks was Amazon's (2 NRC Health, 1 Carriage Services, 5 Microsoft).
  "Operating margin" occurs 3 times in NRC Health's filing, 4 times in Microsoft's and 0 times in Amazon's. The
  5x weight on the company name did not outweigh the phrase match.
- The answer reports NRC Health's 23% and labels it as NRC Health's.

### Change (q29, q30): not reproduced

Direction and size were right in all 6 runs. q30: all three said net income rose by about $582 thousand (14%), and
kept that apart from two true statements that point the other way: adjusted net income fell for the quarter and
net income fell for the nine months.

Example, q29 run 1, correct despite a retrieval miss:

- Question: By what percentage did Carriage Services' revenue change compared with the same quarter last year?
- Answer excerpt: "Carriage Services' revenue for the quarter ended September 30, 2026 fell about 2.4% from the same quarter in 2025" and "The filing excerpts don't state a single consolidated revenue figure. I added the two segment totals myself"
- Cited excerpts (chunks 335 and 337, Carriage Services 10-Q, ranks 7 and 3): "Total | $65,348 | $62,778 | $2,570 | 4.1%" and "Total | $34,908 | $39,964 | $(5,056) | (12.7)%"
- Correct figure: a decrease of 2.4%. Source: Carriage Services 10-Q (accession 0001016281-26-000070), MD&A,
  Financial Highlights, "Total revenue | $100,256 | $102,742 | $(2,486) | (2.4)%" (three months 2026 | 2025, in
  thousands). The two segment totals sum exactly to these figures.
- All 8 chunks were Carriage's, but none held the consolidated revenue line.

### False premise (q31, q32, q33): not reproduced. No run accepted a false premise

q32 and q33: all 6 runs opened by rejecting the premise and gave the right figure (net income of $15.3 billion;
AWS operating income of $17,773 million). q31: no run accepted that revenue fell, but none could say it rose.

Clearest example, q31 run 2, the nearest any run came to going along with a premise:

- Question: Why did Microsoft's revenue fall last quarter?
- Answer excerpt: "The excerpts don't show that Microsoft's total revenue fell" and, in closing, "In short, the decline was concentrated in product revenue, Windows OEM and devices, and Xbox, while cloud and commercial businesses grew strongly. If you have the full income statement with total revenue, I can check whether total revenue actually decreased."
- Cited excerpt (chunk 247, Microsoft 10-Q, rank 8): "Product | $14,631 | $15,922"
- Correct answer: revenue did not fall. It rose 19%, by $14.6 billion, to $92,279 million from $77,673 million.
  Source: Microsoft 10-Q (accession 0001193125-26-436133), MD&A, "Revenue increased $14.6 billion or 19% driven by
  growth in Agents and Infra.", and Income Statements, "Total revenue | 92,279 | 77,673".
- Why retrieval failed: the same chunk boundary as q02 in round 1. Chunk 247 ends at the product revenue line,
  two lines before total revenue, and the next chunk was not in the top 8. The MD&A sentence was not retrieved.
- What the answer does state is accurate and labelled: product revenue fell, Windows OEM and devices fell 22%,
  Xbox content and services fell 2%, Microsoft Cloud grew 30%.

Example of a rejected premise, q33 run 2:

- Question: How much did Amazon's AWS segment lose last quarter?
- Answer excerpt: "Amazon's AWS segment didn't lose money last quarter. It was profitable."
- Cited excerpt (chunk 208, Amazon 10-Q, rank 2): "Operating income | $11,434 | $17,773 | $33,141 | $48,555"
- Correct figure: AWS operating income of $17,773 million for the quarter ended 2026-09-30. Source: Amazon 10-Q,
  Note 8 Segment Information (three months 2025 | 2026, nine months 2025 | 2026).

### Which figure (q34, q35): not reproduced. q34 stopped at retrieval, 3/3

q35: all three runs gave 21,221,538 shares outstanding and kept shares issued, treasury shares and the weighted
averages apart, each labelled. q34: the balance sheet and the debt note were not retrieved.

Clearest example, q34 run 3:

- Question: What was Carriage Services' total debt at the end of last quarter?
- Answer excerpt: "The excerpts don't state a total debt figure for Carriage Services" and "Adding these three gives about $492.7 million. That is not reported total debt, for two reasons:"
- Cited excerpt (chunk 318, Carriage Services 10-Q, rank 2): "At September 30, 2026, the carrying value and fair value of our Credit Facility were $114.8 million."
- Correct figure: long-term debt of $516,204 thousand at 2026-09-30. Source: Carriage Services 10-Q, Note 10,
  "Total Long-term debt | $516,204 | $528,335", and the balance sheet, "Long-term debt | 516,204 | 528,335"
  (September 30, 2026 | December 31, 2025, in thousands).
- Why retrieval failed: all 8 chunks were Carriage's, but none was the balance sheet or the debt note. The two
  cited chunks are the fair value note and the cash flow discussion. "Total debt" occurs 0 times in the filing.
- The answer adds a market value (the Senior Notes' fair value, $371.9 million) to two book values, then says in
  the next sentence that the sum is not total debt. Runs 1 and 2 decline to make that sum. Labelled
  `false_refusal` because no acceptable total is given.

### Facts outside the tables (q36, q37): not reproduced in the answer. Wrong supporting context on q36, 2/3

q37: the signature block was retrieved at rank 5. All three runs said no one signed as principal executive
officer, named John Enwright as the only signer (Principal Financial Officer), and placed the Chief Executive
Officer in the exhibit index as the certifying officer. q36: all three runs said the 10-Q gives no price and that
none of the Apple Card figures in it is a price.

Clearest example of a slip, q36 run 3:

- Question: What did JPMorgan agree to pay for the Apple Card portfolio?
- Answer excerpt: "The firmwide allowance for credit losses at September 30, 2026 included $2.2 billion associated with the Apple Card transaction."
- Cited excerpt (chunk 4, JPMorgan 10-Q, rank 2): "(f)Included $2.2 billion associated with the Apple Card transaction."
- Correct reading: footnote (f) marks the provision for credit losses for the fourth quarter of 2025. Source:
  JPMorgan 10-Q (accession 0001628280-26-069523), Consolidated financial highlights,
  "Provision for credit losses | 2,743 | 2,515 | 2,507 | 4,655 | (f) | 3,403 | 7,765 | 9,557" (3Q26, 2Q26, 1Q26,
  4Q25, 3Q25). At September 30, 2026 the allowance tied to Apple Card was $2.3 billion.
- Why: the footnote and its table row are in different chunks, and only the footnote chunk was retrieved. The
  model supplied a label for a number whose label was not in front of it. Run 1 did the same with different
  words; run 2 quoted the footnote without saying what it measures.
- The refusal itself is right, so the runs are labelled `correct_refusal` and listed for human review.

## Retrieval miss: the only cause found, 3/3 on 11 questions and partial on 1

Not on either probe list. In 2 of the 11 the model still answered correctly (q27, q29).

| Pattern | Questions | Evidence |
|---|---|---|
| A phrase in the question matches another company's filing | q01, q22, q25 | "Q3 2026" is Amazon's wording, and all 8 chunks for a Microsoft question are Amazon's. "Operating margin" is in NRC Health's and Microsoft's filings and not in Amazon's: 0 of 8 chunks are Amazon's. "Free cash flow" occurs more often in NRC Health's filing than in Amazon's: 2 of 8 chunks are Amazon's. |
| "Last quarter" matches boilerplate, which takes slots in the top 8 | q02, q09, q10, q14 and others | Carriage Services chunk 325 (credit facility covenants: "as of the last day of each fiscal quarter") is retrieved for 12 of the 14 round 1 questions that say "last quarter", at rank 1 for 7 of them, and for 0 of the other 7. In round 2 it is retrieved for 6 of the 11 that say "last quarter" (rank 1 for q27, q32 and q34) and for 1 of the other 5 (q29, a Carriage question). |
| The question's word is not the filing's word | q09, q10, q14, q27, q34 | "profit" vs "Net income"; "top line" vs "Total revenue"; "revenue" vs "Total net revenue" in a 185-chunk filing; "efficiency ratio" (in none of the five filings) vs "Overhead ratio"; "total debt" (not in Carriage's filing) vs "Long-term debt" |
| Chunk boundary | q02, q31, and the q36 slip | The income statement is split two lines before "Total revenue" (chunk 247, both rounds). A footnote is split from its table row (JPMorgan chunk 4). |
| Right filing, wrong section | q29, q34 | All 8 chunks are Carriage's. None has the consolidated revenue line or the debt table. |
| One top-8 list for several companies | q19 | 1 of 3 figures retrieved, at rank 8 |

Two more round 1 questions were close to failing the same way: in q04 and q05 the chunk with the answer was at
rank 7 of 8, behind five chunks from JPMorgan and NRC Health.

## Limitations

- The questions were chosen to break the system. They are not a sample of what users ask, so this report gives no
  accuracy figure and the counts above should not be turned into one.
- Small n: 37 questions, 5 filings, one corpus build, two days. Each failure mode has 2 to 4 questions.
- The three runs share one retrieval result per question. They measure variation in generation only. A retrieval
  failure that shows 3/3 was observed once.
- The labeller is a Claude model from the same family as the answering model, and it also wrote the expected
  answers and the rules. Shared blind spots would not show up. No label was checked by a person.
- The round 1 labels were not read again when round 2 was added. They were re-checked only mechanically.
- A failure that did not reproduce may only mean these phrasings did not trigger it. In particular, 10 questions
  did not reach the generation step they were meant to test because retrieval failed first. In round 1: the
  period, wording and GAAP traps in q01, q02, q09, q10 and q14, and q19 for two companies of three. In round 2:
  q22 and q25 (no quarterly inputs to compute from), q31 (no total revenue to correct the premise with), q34 (no
  debt table to choose from). These are untested, not passed. In q23 the nine-month figure was not retrieved, so
  the refusal does not show the model would resist passing it off as the quarter.
- The units check rests on q20 in round 1, plus the thousands filers in round 2 (q24, q29, q30), where every run
  converted thousands correctly. q21 did not exercise it.
- For computed questions the expected value is the labeller's own arithmetic. It was recomputed by script.
- The mechanical checks compare figures only. They do not check period or basis labels, they ignore sign, and
  they count a figure as grounded if any cited chunk contains that number. A percentage matches any bare table
  cell with the same number, which produced two false matches in q31. Both labelling slips found (q12 run 1,
  q36 runs 1 and 3) were found by reading, not by a check.
- The `naive-v1` tag named in both probe READMEs is not on the remote, so the build cannot be pinned to a tag here.

## Needs human review

No run is labelled `confident_wrong`, so that list is empty. Runs where the label and the mechanical checks
disagree, where supporting context is wrong, or where the labeller made a judgment call (`eval/review.jsonl`, 22 rows):

| Run | Round | Label | Why it is listed |
|---|---|---|---|
| q06 run 2 | 1 | correct | 7 figures are supported only by retrieved chunks the answer did not cite: $582,013 million, $203,156 million, $134,850 million, $56,689 million, $41,163 million, $17,289 million, $5,119 million. The round 1 labeller checked them against the filing and they match. The asked figure ($584,069 million) is cited. |
| q06 run 3 | 1 | correct | $582,013 million (net sales at prior-year exchange rates) is in a retrieved chunk that was not cited. It matches the filing. |
| q12 run 1 | 1 | correct | Supporting context has reversed column labels (see Column, round 1). |
| q22 runs 1 to 3 | 2 | hedged_ok | Judgment call. The answer gives the trailing-twelve-month figure, labelled, and no figure for the quarter asked about. The acceptance rule names this a hedge. |
| q26 run 3 | 2 | correct | Check false positive: the answer says "the filing doesn't state it directly" about the share it then computes, which the check reads as refusal language. |
| q27 runs 1 to 3 | 2 | correct | The expected 54% is neither stated nor retrieved. The answer computes 54.4% from retrieved inputs and labels it an estimate, which the acceptance rule accepts. A reviewer may prefer `hedged_ok`, since each run adds that the reported figure may differ. |
| q29 runs 1 to 3 | 2 | correct | The consolidated revenue line is in no retrieved chunk. The answer says so and rebuilds the total from two segment totals. The result equals the filed figure. |
| q31 runs 1 to 3 | 2 | hedged_ok | Judgment call. The premise is not accepted but not corrected. Under the round 1 convention this would be `false_refusal`. Run 2's closing line reads as if there were an overall decline. |
| q32 run 2 | 2 | correct | $52,954 million and $44,023 million (nine-month net income) are in a retrieved chunk that was not cited. They match the filing. |
| q34 runs 1 to 3 | 2 | false_refusal | Judgment call. Two of the three components of the total are given and labelled, so a reviewer may prefer `hedged_ok`. Run 3 adds a market value to book values and then disowns the sum. |
| q36 runs 1 and 3 | 2 | correct_refusal | Wrong supporting context: $2.2 billion is called the firmwide allowance (run 3: at September 30, 2026). It is the 4Q25 provision (see Facts outside the tables). |

Judgment calls a reviewer may want to overrule:

1. `false_refusal` for truthful refusals after a retrieval miss (q01, q02, q09, q10, q14, q25, q34, 21 runs). See Method.
2. q01: the answer flags the fiscal-calendar ambiguity but gives no figure. Under the acceptance rule that is not
   enough for `correct`.
3. q01: the model used a fact that is not in the retrieved chunks (Microsoft's fiscal year end). The system prompt
   says to use only the search results. The fact is right and no figure is involved, so it was not labelled
   `memory`. q23 is similar: the runs say a 10-Q cash flow statement is usually year to date, which is not in the
   retrieved chunks and is true of this filing.
4. q21: labelled correct although the units conversion was not exercised.
5. q15: the XBRL reference in `probes/round1/results.jsonl` is stale (see Method). Worth correcting in a later probe run.
6. q22 and q31 as `hedged_ok`, q34 as `false_refusal`, q27 as `correct`: see the table above. The three hedge or
   refusal calls rest on which convention applies, not on what the answers say.
7. q37: its category is "facts outside the tables", but the question turned out to carry a false premise (no one
   signed as principal executive officer). It was labelled against that reading.
