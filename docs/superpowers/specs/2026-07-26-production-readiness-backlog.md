# Production Readiness Backlog

**Status:** Backlog — not yet planned. Revisit before public launch.
**Created:** 2026-07-26, during the post-outage investigation.
**Related:** [OpenAI model migration plan](../plans/2026-07-26-openai-model-migration.md)

This captures issues found while diagnosing the July 2026 outage. None of them belong in the
model-migration plan. Each needs its own spec before implementation.

---

## P0 — Fix before public traffic

### 1. `SECRET_KEY` is unset in production — JWTs are forgeable

**Confirmed 2026-07-26.** The systemd unit `/etc/systemd/system/ielts-backend.service` defines
`DATABASE_URL`, `OPENAI_API_KEY`, `AZURE_SPEECH_*`, `YOUDAO_*`, `GOOGLE_APPLICATION_CREDENTIALS`
and `OPENROUTER_API_KEY` — but **not `SECRET_KEY`**. There is no `.env` file on the server either.

Therefore `settings.SECRET_KEY` falls back to the default in `backend/app/config.py:13`:

```python
SECRET_KEY: str = "your-secret-key-change-in-production"
```

`backend/app/services/auth.py:28,41` signs *and* verifies every JWT with that value. Anyone who
knows the string — it is committed to the repo and is a widely-used placeholder — can mint a valid
token for any `user_id` and access any account.

**Fix:** generate a strong random key, deliver it as a runtime secret, restart the service.
**Side effect:** rotating the key invalidates all existing sessions; every user must log in again.
**Hardening:** make the app refuse to boot in production if `SECRET_KEY` is still the default.

### 2. No rate limiting or per-user quotas on AI endpoints

Any authenticated user can trigger unbounded generation and grading calls. At launch this is the
largest financial exposure: cost scales linearly with abuse and nothing caps it. Needs per-user
daily caps and a global circuit breaker.

### 3. `OPENROUTER_API_KEY` is set on the server but referenced nowhere in the codebase

Confirmed by grep across `backend/` and `frontend/`: no code reads it. An unused live credential is
pure blast radius. Remove it from the unit and revoke it at the provider.

---

## P1 — Reliability

### 4. `dictionaryapi.dev` is a hard dependency on a free, unauthenticated third party

Called directly from the browser in three places (`AIGrammarView.tsx:80`, `useVocabSelection.ts:30`,
`Topics.tsx:83`). Worse, the `audio_url` it returns is **stored in the database** on saved vocabulary,
so previously-saved words depend on that service permanently. If it rate-limits or disappears,
vocabulary lookup breaks for all users and saved audio breaks retroactively.

**Fix:** consolidate into a backend endpoint (LLM for definition/IPA/translation + existing Google TTS
for self-hosted pronunciation audio), cached in Postgres. Retires Youdao at the same time.

### 5. Backend runs uvicorn with `--reload` in production

Confirmed in the unit's `ExecStart`. A development flag: it runs a file-watcher and an extra process
on a 2 GB box, and restarts the app on any file change.

### 6. No swap on a 2 GB droplet

~436 MB available at inspection, `Swap: 0B`. Nothing has OOM-killed yet, but there is no headroom.
Add a swapfile.

---

## P2 — Hygiene

### 7. `BACKEND_CORS_ORIGINS` lists only localhost

`config.py:18` still has the dev defaults. Harmless today because nginx makes the app same-origin,
but misleading and will bite if an API subdomain is introduced.

### 8. Deploy has no health check or rollback

`deploy.yml` restarts the service and exits. A failed boot is only visible by the site being down.
Add a post-restart health probe against `/api/` and fail the workflow if it does not return 200.
