# Proposed full-mock content and scoring acceptance

Documentation-only design, not implemented behavior, a launch decision or a
promise of official IELTS equivalence. Existing delivery tests prove plumbing,
not content quality. Payment/webhook behavior is unaffected.

## Verified reference and current gap

Official IELTS guidance specifies Academic Reading as three sections, 40
questions and 60 minutes, with 2,150–2,750 words across the texts. Listening has
four parts with ten questions each. Each correct answer earns one mark; published
raw-to-band examples are averages that can vary by test version. Overall IELTS
band combines four skills, not one mock's sections.

- [IELTS Academic Reading format](https://ielts.org/take-a-test/test-types/ielts-academic-test/ielts-academic-format-reading)
- [IELTS Listening format](https://ielts.org/take-a-test/test-types/ielts-academic-test/ielts-academic-format-listening)
- [IELTS scoring guidance](https://ielts.org/take-a-test/your-results/ielts-scoring-in-detail)

Checked against source at local revision `1db1898`: Reading presets target ten
questions per section, but that target is not passed to the generator. Both exam
validators accept declared section counts of at least five. Counting differs
between generator, scorer and renderer. Existing band functions ignore the
provided total, floor zero correct at 4.0 and cap full marks at 8.5. The UI calls
single-skill results “Overall Band”. These are inherited limitations, not
validated conversion rules to reuse.

## Proposed new-content contract

- Explicit version identifies new Academic mock content and scoring. Reading:
  three sections and exactly 40 scoreable items; Listening: four sections with
  exactly ten each. Reading fixture allocation 13/13/14 is a local convention,
  not an official requirement.
- Normalize supported question formats to consistent scoreable leaf items. Each
  has one unique answer key, a recognized type, a nonempty answer definition and
  a corresponding rendered input. Count these items, not metadata, container
  objects or the number of answer alternatives. Generator validation, renderer
  and scorer must agree, including nested matching/headings formats.
- Validate section identity/order, actual counts and declared totals. Reject
  duplicate keys, missing answers, unsupported shapes and inconsistent counts
  before admitting inventory or scoring new-format submissions.
- Award one mark per item; unanswered is incorrect. Return raw correct/total
  and section/type breakdowns with `0 <= correct <= total`. New results should
  say “Practice result: X/40”, without an estimated band until a separately
  reviewed calibration policy exists. Do not interpolate unverified band maps.
- A missing band must stay absent/null through API, rendering, history and
  analytics. Do not coerce it to zero, animate a band, save a fabricated
  `band_score` or describe this result as an official or overall IELTS score.

## Inventory, quality and compatibility protections

Keep old exercises and stored results unchanged: no retrospective rescoring,
rewriting or deletion. Preserve historical raw marks and stored bands; a legacy
band may be labeled “Legacy practice estimate”. Content without a new version
must not silently become compliant new-format inventory. Existing assigned
legacy exercises need a compatible completion/history path, not a destructive
migration or surprise rejection.

An entitlement does not create inventory. Admission of a new full mock requires
structural validation and separate quality review: original/licensed content,
topic freshness and diversity, appropriate text length, progressive difficulty,
answer support and unambiguous marking. Listening additionally needs intelligible,
relevant audio aligned to its transcript/questions, suitable speakers and pacing,
and verified browser playback/static mapping. Tiny texts and tones cannot pass
that quality review just because their structures are valid.

An optional future rollout flag could isolate new-format generation/delivery;
if adopted, default off and test the disabled path. This is a design option only.
Do not change existing production settings, study-pass/checkout defaults,
scheduler behavior, credentials, provider jobs or webhook handling for this spec.
Do not seed production or enable generation to hide an empty pool.

## Proposed original-fixture acceptance cases

Use only original synthetic fixtures, isolated disposable databases and mocked
providers/replenishment. No official exam text, live AI/audio/payment services or
remote writes are necessary.

- Reading 13/13/14 and Listening 10/10/10/10; mixed supported question formats,
  including nested shapes, all map to 40 unique rendered/scored leaf keys.
- Reject 39/41 items, Listening 9/11 per part, false `total_questions`, duplicate
  sections/keys, empty answers and unsupported structures. Check that alternative
  acceptable answers do not inflate the question count.
- Raw scores 0, 1, 39 and 40; unanswered/wrong answers; section sums equal total.
  New results have no estimated band and persist/reopen without inventing one.
- Authentic synthetic pass holder receives an eligible mock once, opens its
  complete payload, submits and reopens results. Preserve free/expired gates,
  owner isolation, duplicate-submit protection and empty-inventory reporting.
- Existing legacy content/history still opens with unchanged persisted results;
  new eligibility checks do not reinterpret it. Optional flag-off path retains
  prior behavior.
- Local audio fixtures prove URL/media contracts only. Keep browser playback,
  seeking, deployed mapping and pedagogic quality as separate acceptance checks.

See [delivery checklist](full-mock-delivery.md) for existing test scope and limits.

## Offline structural auditor

`app.services.full_mock_audit.audit_full_mock(payload, skill="reading")`
(or `skill="listening"`) now provides an explicitly invoked, pure structural
check. It returns 40 immutable answerable-leaf records or raises
`MockStructureError`. It checks declared totals, ordered section identities,
unique leaf identities, supported question shapes, nonempty prompts/answers,
Reading heading-to-paragraph alignment, Listening matching stem-to-answer
alignment, and Listening's ten items per part. Acceptable-answer alternatives
remain one leaf. The implementation supports current Reading grouped and
Listening flat/nested shapes, not arbitrary future types.

The returned `sN:...` identities are **audit-only**, not submission keys.
The legacy Listening full-test renderer expands matching stems, whereas its
scorer currently treats matching blocks as ordinary items. Consequently an
audit pass is not evidence of legacy renderer/scorer agreement; that mismatch
still needs a separately versioned delivery/scoring change and integration QA.

Nothing calls this helper from production routes, generators, scoring or
inventory admission. It does not change content versions, legacy results, bands
or entitlement behavior. Passage/transcript/audio fields are checked only for
presence, not authenticity, length, playable media or pedagogic quality.
Synthetic tests cover 13/13/14 Reading and 10/10/10/10 Listening; no real provider
calls, official exam text or production content are used.
