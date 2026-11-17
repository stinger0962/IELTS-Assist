# Local synthetic preview demo

This is an opt-in laboratory, not a production route or staged service. It imports
the isolated question-only React component, and calls the **real pure Python
preview and raw scoring helpers**, using the existing original synthetic renderer
fixtures. Nothing starts the application, database, providers, Stripe, accounts,
or environment/config loaders. No accepted answers are bundled into the browser.
No history, grade bands, persistence, authentication, or deployment is provided.
The small server is for a trusted local development machine only, never exposure.

## Run

From repository root, with frontend dependencies already installed and Python 3.10+:

```sh
(cd frontend && npx tsc -p demo-preview/tsconfig.json && npx vite build --config demo-preview/vite.config.ts)
python tools/mock-preview/serve.py
```

Open **http://127.0.0.1:8765** (not localhost). Ctrl-C stops the process.
The server always binds 127.0.0.1, checks Host/Origin, sends no CORS headers,
and serves only its separate built artifact directory and two fixed synthetic
preview/scoring endpoints. It does not serve repository source/answer fixtures.
It accepts at most 16 KiB of JSON per scoring request. Do not put secrets or
personal content into this laboratory. The server does not persist submissions.

Choose Reading or Listening. Enter `box` in the first input, leave others empty,
review, then submit. The real scorer returns **1 / 40**. Blank submissions return
0 / 40. Section navigation retains draft answers; New attempt resets them.
Late prior-attempt responses cannot install a result into the new attempt.

Listening deliberately contains a synthetic URL without an audio asset: native
controls are present, but playback is not implemented or verified. No audio is
generated or downloaded. The browser may report a missing asset if play is clicked.

The main app's scripts, routes, Vite config and imports are unchanged.
Demo assets live under ignored `frontend/demo-preview/dist/`; normal builds
continue using frontend/index.html. Never deploy this directory.

## Tests and optional 430px acceptance

```sh
python -m unittest discover -s tools/mock-preview -v
(cd frontend && npx tsc -p demo-preview/tsconfig.json)
```

Three standard-library tests exercise both real preview -> HTTP score paths,
1/40 and blank scores, and rejection of unknown legacy keys, source traversal,
unexpected Host/Origin and wrong content type. No pytest/third-party Python
packages required.

With the server running and an **existing** Playwright/Chromium installation:

```sh
PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs \
CHROMIUM_PATH=/absolute/path/to/chromium \
node tools/mock-preview/browser-smoke.mjs
```

Omit those variables if Playwright resolves locally and its browser is installed.
The runner blocks requests outside the exact loopback origin, uses a 430x932
viewport, exercises both skills through the real scorer, cancellation, section
navigation and resets; it asserts no horizontal document overflow in every
section and saves full-page screenshots under /tmp/mock-preview-evidence.
Do not treat screenshots as reviewed until a person/agent inspects their pixels.

### Verification in this task environment

- Separate demo build, type check and HTTP tests passed.
- Chromium and Playwright were found; Chromium launch failed with
  `process_singleton_posix.cc: socket() failed: Operation not permitted`,
  including a permission-approved retry. Thus **browser interaction, 430px
  visual/overflow checks and audio playback were not executed**. No screenshots
  or rendered-layout pass is claimed. The executable runner is supplied for a
  browser-capable environment.
- Fixed the component's undefined `--color-text` reference to the existing
  `--color-text-primary` token with fallback. This is isolated preview styling,
  not a change to legacy pages.
