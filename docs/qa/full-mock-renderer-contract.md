# Offline existing-renderer submission contract

The `fullMockRenderer.test.tsx` Vitest tests mount the actual unchanged
`AIReadingFullTestView` and `AIListeningFullTestView` components. They enter
answers through DOM controls, advance all sections, confirm submission, and
inspect the outgoing mocked API call. No copies of component key-generation
algorithms run in the tests.

The shared original synthetic JSON fixtures contain complete 40-leaf examples:
Reading 13/13/14 with completion, MCQ and nested headings; Listening 10/10/10/10
with completion, matching and MCQ; and Listening with empty completion groups,
two separate matching blocks and MCQ. Expected section-scoped input identities
are checked against the pure pinned bridge in
`test_full_mock_renderer_fixture_contract.py`. The DOM tests then establish
that those same identities are actually emitted by the existing components.
Repeated keys across sections remain independent; matching stems and headings
produce individual controls. Mixed-language topic labels do not supply IDs.

API requests, audio playback, vocabulary lookup and celebrations are mocked.
This verifies DOM interactions/submission shape, not real audio playback,
responsive layout, real server scoring, authorization, network behavior,
provider output or pedagogic quality. It does not establish safe delivery of
the answer-bearing legacy payload. The experimental preview DTO is not wired
into these components. Summary completion and matching-information limitations
remain as documented in the full-mock content/scoring checklist.

No production component or route was changed for these contract tests.
