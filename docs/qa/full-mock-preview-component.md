# Isolated experimental question-only component

`components/experimental/FullMockPreviewPractice.tsx` renders the explicit
`full_mock_active_preview_v2` DTO. It is **not imported by a production page,
route or legacy full-test component**. It has no API/store/provider imports.

Props are the typed preview, a nonempty attempt ID, optional English/Chinese
locale, and an attempt-scoped `onSubmit` callback. Submission produces only
`{schema_version: "full_mock_raw_v2", answers: {...}}` with unchanged audit IDs
and input strings. A parent must bind the callback to the correct authenticated
attempt before any eventual route integration. The component does not invent
practice ownership, authentication, inventory admission or storage behavior.

Section navigation preserves draft answers. A different attempt or changed
preview content remounts the local session and clears the old draft; equivalent
DTO values and language changes preserve it. The parent must not switch attempt
IDs unintentionally. Late completion of an old callback cannot clear or lock the
new session. A confirmation step permits partial/blank submission; it never
fills missing answers. Duplicate callbacks are locked while submitting, errors
retain inputs and allow retry, and success stays locked until a new attempt.

The component renders passage/prompt/option strings as React text, not HTML.
Listening uses controlled same-origin audio paths, `preload="none"` and no
autoplay. Missing/unapproved audio references show an unavailable notice instead
of fetching another destination. Audio is recreated between sections. Source
transcripts, explanations and accepted answers are absent from the server DTO.

Tests use actual DOM controls, synthetic DTOs and callback promises. They cover
partial/blank answers, key preservation, section transitions, stale-attempt
resets, language changes, duplicate/retry handling, late completion, malicious
markup and rejected audio destinations. Python snapshot tests connect the React
fixtures to the actual server whitelist helper. This is not real playback,
responsive screenshot QA, server submission or end-to-end deployment testing.
