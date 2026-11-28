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
   collect billing. Opt-in metadata collection below can measure latency and
   reported token usage, not billed cost. Report unmeasured fields as such.
5. Examine individual misses and fix reproducible issues before calling
   the grader ready for a paid trial. A passing small smoke test does not
   justify a claim that scores match an examiner.

No real calibration run or provider cost is implied by this document.

[samples]: https://ielts.org/cdn/Sample-tests/ielts-academic-writing-sample-tasks-2023.pdf

## Optional non-content observations

After the same provider/input/budget authorization above, enable
`CALIBRATION_OBSERVE=1` on the calibration command. Without that exact value,
the existing grader call and harness behavior are unchanged. This flag does
not authorize a provider call or make calibration safe to run by default.
No real calibration was performed to test this observer.

The test-only `tests/calibration_observer.py` context temporarily wraps the
actual grader's scoring/annotation methods and SDK `create()` boundary. It emits
one JSON object per local run containing stage and attempt events, including
when scoring raises or annotation falls back. Production code, logs, routes,
request parameters, retry logic and returned grading results are unchanged.
This uses process-global patches: use only in sequential isolated calibration,
never around application traffic, threads, or overlapping contexts.

Metadata whitelist:
- Stage: scoring or annotation; success/error; elapsed monotonic milliseconds.
  Annotation's complete/partial/unavailable status is retained separately from
  exceptions, so a successful call with unusable annotations isn't called good.
- Attempt: stage-local attempt number, response/empty_response/provider_error,
  elapsed milliseconds; prompt/completion/total tokens and optional cached
  prompt/reasoning token counts.
- Missing, malformed or unavailable usage is JSON null (**unknown**, not zero).
  A known numeric zero remains zero. No estimated or actual money is calculated.
  Cached/reasoning counts are subdivisions, not extra totals to add to usage.

Confirmed against the locally installed pinned OpenAI Python **2.24.0** source:
`openai.types.chat.ChatCompletion.usage` is optional
`openai.types.completion_usage.CompletionUsage`; usage has prompt_tokens,
completion_tokens, total_tokens plus optional prompt_tokens_details.cached_tokens
and completion_tokens_details.reasoning_tokens. The production wrapper currently
uses `chat.completions.create(...).choices[0]` and otherwise discards usage.
Synthetic tests construct real SDK ChatCompletion objects and exercise that
unchanged wrapper and actual WritingGrader, including the empty-response retry.

Each measured attempt means one SDK create invocation. SDK-internal HTTP
retries are opaque and may consume time or tokens not represented by the final
response. Provider exceptions may have incurred usage: null must not be counted
as free. Stage latency includes local parsing; attempt latency includes SDK
handling/retries. No prompt, essay, answer, response content, exception message,
provider ID, credential or sample name is copied into these events. Existing
calibration band summaries still print as before. Keep any combined console
capture local; this helper does not write telemetry files or upload anything.

Offline verification, no provider calls:
`python -m pytest tests/test_calibration_observer.py -q`.
