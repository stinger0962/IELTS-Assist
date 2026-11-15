# Academic Task 2 writing calibration smoke test

Paid Study Pass writing reviews return AI estimates, not official IELTS
results. Ordinary CI validates code and credit accounting, not scoring
accuracy. Use the existing opt-in calibration harness separately before
launch and after changes to the model or rubric.

## Examiner anchors

Use the official [IELTS Academic Writing sample PDF][samples]. The page
numbers below are 1-based. Record the examiner band; do not include examiner
comments in the grading input or put sample scripts in this repository.

| Fixture ID | Prompt page | Script and examiner pages | Expected overall band |
| --- | ---: | ---: | ---: |
| task2a-a | 6 | 18 | 4.0 |
| task2a-b | 6 | 19–20 | 6.5 |
| task2a-c | 6 | 21–22 | 8.5 |
| task2b-a | 7 | 23–24 | 5.5 |
| task2b-b | 7 | 25–26 | 7.5 |

These five samples span two prompts and are a small diagnostic, not
proof of calibration across the full IELTS distribution. Future expansion
should cover independent prompt types, score boundaries, and formats.

## Run only after authorization

1. Use only inputs you are permitted to copy and submit to the chosen AI
   service. Do not use customer data. Keep any transcribed sample fixture
   local in the gitignored `backend/tests/fixtures/calibration_essays.json`
   (structure: `calibration_essays.example.json`). Avoid publishing the
   scripts, prompts, or model output quoting those scripts.
2. Use an approved test project, runtime-injected credential and budget.
   Do not add an API key to the fixture or use production credentials.
   For five essays and three runs each, expect 15 scoring attempts and
   up to 15 annotation attempts before retries. Verify the current
   model/usage budget first. The default test suite does not run them.
3. From `backend`: `python -m pytest tests/test_calibration.py -m calibration -s`.
   Require five fixture cases, not a skip due to missing input.
4. Record the exact model, commit, expected and observed bands, mean drift,
   within-essay spread, whether annotations were available, latency and
   app-specific billed usage if measured. The harness currently asserts at
   most half a band of mean drift and within-essay spread and does not
   itself collect latency or billing. Report unmeasured fields as such.
5. Examine individual misses and fix reproducible issues before calling
   the grader ready for a paid trial. A passing small smoke test does not
   justify a claim that scores match an examiner.

No real calibration run or provider cost is implied by this document.

[samples]: https://ielts.org/cdn/Sample-tests/ielts-academic-writing-sample-tasks-2023.pdf
