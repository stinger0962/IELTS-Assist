# Production Readiness Backlog

**Status:** 8 of 8 original items closed as of 2026-07-27. Remaining work is listed at the bottom.
**Created:** 2026-07-26, during the post-outage investigation.
**Related:** [OpenAI model migration plan](../plans/2026-07-26-openai-model-migration.md)

This captures issues found while diagnosing the July 2026 outage. None of them belong in the
model-migration plan. Each needs its own spec before implementation.

---

## P0 — Fix before public traffic

### 1. ~~`SECRET_KEY` is unset in production — JWTs are forgeable~~ — **DONE 2026-07-26**

Fixed in `21e88bf` (delivered via `.env` from GitHub Secrets, 86 chars, verified not the placeholder)
and hardened in `0a13c54`, which makes the app refuse to boot on the default key.

Original note:

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

### 2. ~~No rate limiting or per-user quotas on AI endpoints~~ — **DONE 2026-07-27**

Shipped in `50a2fb7`. Per-user daily quotas by cost category (30 grade / 60 generate / 300 lookup)
plus a global $20/day estimated-spend circuit breaker, counted in `usage_counters` and verified
against Postgres. See [the plan](../plans/2026-07-27-rate-limiting.md).

Two follow-ups this opens up:
- **`usage_counters` is the first real usage visibility this app has.** Watch it for a week before
  tightening the defaults — real data beats the guesses baked in now.
- **No alerting yet.** The breaker returns 503 silently; nobody is told the budget was hit. Worth
  wiring up once there is somewhere to send an alert.

### 3. ~~`OPENROUTER_API_KEY` is set on the server but referenced nowhere~~ — **DONE 2026-07-27**

Removed from the systemd unit and confirmed absent from the running process. **Not revoked** — the
owner uses that key for other projects, so it stays valid; removing it here only shrinks this box's
blast radius.

Original note:

Confirmed by grep across `backend/` and `frontend/`: no code reads it. An unused live credential is
pure blast radius. Remove it from the unit and revoke it at the provider.

---

## P1 — Reliability

### 4. ~~`dictionaryapi.dev` is a hard dependency on a free third party~~ — **DONE 2026-07-27**

Retired in `4231ce8`. `POST /generate/define-word` returns definition + Chinese + IPA in one model
call, Google TTS makes a self-hosted pronunciation MP3, and results cache globally in `vocab_cache`.
See [the plan](../plans/2026-07-27-vocab-consolidation.md).

Original note:

Called directly from the browser in three places (`AIGrammarView.tsx:80`, `useVocabSelection.ts:30`,
`Topics.tsx:83`). Worse, the `audio_url` it returns is **stored in the database** on saved vocabulary,
so previously-saved words depend on that service permanently. If it rate-limits or disappears,
vocabulary lookup breaks for all users and saved audio breaks retroactively.

**Fix:** consolidate into a backend endpoint (LLM for definition/IPA/translation + existing Google TTS
for self-hosted pronunciation audio), cached in Postgres. Retires Youdao at the same time.

### 5. ~~Backend runs uvicorn with `--reload` in production~~ — **DONE 2026-07-27**

Dropped via the systemd drop-in's `ExecStart=` reset (`c352b64`), so it shipped through CI rather than a
hand-edited unit. Measured effect: the backend went from **three processes to one** — the reload
watcher was spawning a `resource_tracker` and a forked child.

Original note:

Confirmed in the unit's `ExecStart`. A development flag: it runs a file-watcher and an extra process
on a 2 GB box, and restarts the app on any file change.

### 6. ~~No swap on a 2 GB droplet~~ — **DONE 2026-07-27** (caused a real outage on 2026-07-26)

2 GB swapfile added, `swappiness` 60→20, persistence tested via `swapoff` + `swapon -a`.
The unrelated workloads noted below still share the box — that part stands.

Original note:

`Swap: 0B`. Available memory has been observed swinging between 826 MB and **52 MB**. When two
deploys ran concurrently and each started a vite build, the box went into I/O thrash — load average
peaked above **54** — and nginx stopped serving even static files until the orphaned `tsc` processes
were killed. With swap this would have been a slowdown, not an outage.

Fixed since: the frontend is no longer built on the VPS (scp'd from CI instead), and deploys are
serialised by a concurrency group. But the underlying fragility remains — **add a swapfile.**

The droplet also carries several unrelated workloads competing for the same 2 GB:

| Process | RSS |
|---|---|
| `openclaw` agent (gateway + node run) | ~200 MB |
| `/app` stack (`run.py` ×2, `vite --host`, `npm run dev`) | ~220 MB |
| Outline VPN server + prometheus | ~75 MB |
| dockerd + containerd | ~70 MB |

Note the `npm run dev` / `vite --host` pair has been running for **132 days** — a dev server left
running in production, costing ~120 MB. Not IELTS-owned, but worth reclaiming.

---

## P2 — Hygiene

### 7. ~~`BACKEND_CORS_ORIGINS` lists only localhost~~ — **DONE 2026-07-27**

Production origins added in `c352b64`.

Original note:

`config.py:18` still has the dev defaults. Harmless today because nginx makes the app same-origin,
but misleading and will bite if an API subdomain is introduced.

### 8. ~~Deploy has no health check or rollback~~ — **DONE 2026-07-27**

Backend health check added in `21e88bf`; frontend swap verification and restore in `c352b64`/`3252e5b`.
The `rm -rf` + copy window previously had no way back if the copy failed midway.

Original note:

`deploy.yml` restarts the service and exits. A failed boot is only visible by the site being down.
Add a post-restart health probe against `/api/` and fail the workflow if it does not return 200.


---

## Still open

| Item | Why it matters |
|---|---|
| **Grading calibration** | The harness ships (`c352b64`) but needs 4–6 essays with examiner-assigned bands. Until then nobody has verified luna's bands are *correct*, only that they are produced. This is the last thing gating a confident launch. |
| **Alerting** | The spend breaker returns 503 silently. Nobody is told the budget was hit. |
| **Tune quotas from real data** | `usage_counters` is the first usage visibility this app has had. Watch a week before trusting the current guesses. |
| **`whisper-1` → `gpt-4o-mini-transcribe`** | Newer and ~half the price, but the transcript drives Speaking band scores for non-native speakers. Needs a listening test on real accented audio before switching. |
| **Reclaim the 132-day `vite --host` dev server** | ~120 MB on a 2 GB box, not IELTS-owned. |
