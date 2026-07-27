# Secrets Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make GitHub Secrets the source of truth for runtime credentials, and close the live `SECRET_KEY` vulnerability, without risking a boot failure that takes the site down.

**Architecture:** The deploy workflow writes `/root/IELTS-Assist/backend/.env` (mode 600) from GitHub Secrets before restarting the backend. `config.py` already reads that file (`env_file = ".env"`, and systemd's `WorkingDirectory` is that directory), so **no application code change is required for secrets to load**. The systemd unit is left untouched in Phase 1 — a deliberate safety choice explained below.

**Tech Stack:** GitHub Actions, `appleboy/ssh-action@v1`, systemd, pydantic-settings.

---

## Why this is safe: the precedence trick

pydantic-settings resolves configuration in this order (highest priority first):

```
environment variables  >  .env file  >  defaults in config.py
```

The systemd unit currently sets `DATABASE_URL`, `OPENAI_API_KEY`, `AZURE_SPEECH_*`,
`GOOGLE_APPLICATION_CREDENTIALS`, `YOUDAO_*` as real environment variables. It does **not** set
`SECRET_KEY`.

So when we write `.env` while leaving the unit alone:

| Setting | Comes from | Changes? |
|---|---|---|
| `SECRET_KEY` | **`.env`** (nothing else defines it) | ✅ **Vulnerability closed** |
| `DATABASE_URL`, `OPENAI_API_KEY`, `AZURE_SPEECH_*`, `GOOGLE_*`, `YOUDAO_*` | systemd unit (env vars win) | ❌ No change — still the proven values |

**This is the key property: Phase 1 fixes the vulnerability while being unable to break any
currently-working credential.** If the `.env` write goes wrong, the app keeps booting on exactly the
values it uses today. There is no path from this change to an outage.

Phase 2 (removing the inline `Environment=` lines) is what makes `.env` authoritative — and that one
*can* break things, so it is deliberately deferred and gated.

## Phase ordering and the Youdao dependency

`YOUDAO_APP_KEY` / `YOUDAO_APP_SECRET` were intentionally **not** created as GitHub Secrets, because
Youdao is being retired.

⚠️ **This makes Phase 2 blocked until Youdao is actually gone.** The moment the inline `Environment=`
lines are removed, those two variables vanish. `config.py` defaults them to `""`, and
`translate_definition` catches the resulting failure and returns `{"content_zh": ""}` — so nothing
crashes, but **Chinese definition translation silently stops working** for `zh` users.

Phase 1 is unaffected (the unit still supplies them). Sequence:

```
Phase 1 (this plan, now)  →  Youdao retirement  →  Phase 2 (unit cutover)
```

---

## Task 1: Write runtime secrets from the deploy workflow

**Files:**
- Modify: `.github/workflows/deploy.yml:38-68`

- [ ] **Step 1: Add the secret environment block to the deploy step**

In `.github/workflows/deploy.yml`, the existing step begins:

```yaml
      - name: Deploy to VPS
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.VPS_HOST }}
```

Insert an `env:` block between `uses:` and `with:`, so the step reads:

```yaml
      - name: Deploy to VPS
        uses: appleboy/ssh-action@v1
        env:
          SECRET_KEY: ${{ secrets.SECRET_KEY }}
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          AZURE_SPEECH_KEY: ${{ secrets.AZURE_SPEECH_KEY }}
          AZURE_SPEECH_REGION: ${{ secrets.AZURE_SPEECH_REGION }}
        with:
          host: ${{ secrets.VPS_HOST }}
```

- [ ] **Step 2: Forward those variables into the remote shell**

In the same `with:` block, alongside `host`/`username`/`key`, add:

```yaml
          envs: SECRET_KEY,DATABASE_URL,OPENAI_API_KEY,AZURE_SPEECH_KEY,AZURE_SPEECH_REGION
```

`appleboy/ssh-action` only exports variables named here — omitting this silently sends empty values.

- [ ] **Step 3: Write the .env file before the backend restarts**

In the `script:` block, insert the following **immediately after** `git reset --hard origin/main` and
**before** the `# Backend` section. Order matters: the file must exist before the service restarts.

```bash
            # --- Runtime secrets (source of truth: GitHub Secrets) ---
            ENV_PATH=/root/IELTS-Assist/backend/.env
            umask 077
            printf '%s\n' \
              "SECRET_KEY=${SECRET_KEY}" \
              "DATABASE_URL=${DATABASE_URL}" \
              "OPENAI_API_KEY=${OPENAI_API_KEY}" \
              "AZURE_SPEECH_KEY=${AZURE_SPEECH_KEY}" \
              "AZURE_SPEECH_REGION=${AZURE_SPEECH_REGION}" \
              > "$ENV_PATH.tmp"

            # Refuse to install a file with an empty SECRET_KEY — that would silently
            # leave the app on the insecure default.
            if ! grep -qE '^SECRET_KEY=.+$' "$ENV_PATH.tmp"; then
              echo "FATAL: SECRET_KEY missing or empty — is the GitHub Secret set?" >&2
              rm -f "$ENV_PATH.tmp"
              exit 1
            fi

            chmod 600 "$ENV_PATH.tmp"
            mv "$ENV_PATH.tmp" "$ENV_PATH"
            echo "Wrote $ENV_PATH ($(wc -l < "$ENV_PATH") entries)"
```

Note: it prints the *line count*, never the contents. Nothing in this script echoes a secret value.

- [ ] **Step 4: Add a post-restart health check**

At the very end of the `script:` block, after the frontend section, append:

```bash
            # --- Health check: fail the deploy if the backend did not come back ---
            sleep 3
            for i in 1 2 3 4 5; do
              CODE=$(curl -s -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1:8000/ || echo 000)
              if [ "$CODE" = "200" ]; then
                echo "Backend healthy (HTTP $CODE)"
                break
              fi
              if [ "$i" = "5" ]; then
                echo "FATAL: backend unhealthy after restart (last code $CODE)" >&2
                journalctl -u ielts-backend -n 30 --no-pager >&2
                exit 1
              fi
              sleep 3
            done
```

Without this, a backend that fails to boot shows up as a green deploy and a dead site.

- [ ] **Step 5: Validate the workflow file parses**

Run: `cd /d/IELTS-Assist && python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/deploy.yml')); print('YAML OK')"`
Expected: `YAML OK`

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "feat(deploy): write runtime secrets from GitHub Secrets and health-check after restart"
```

---

## Task 2: Ship and verify Phase 1

- [ ] **Step 1: Push and let the pipeline run**

```bash
git push origin main
```

- [ ] **Step 2: Confirm CI then Deploy both go green**

```bash
gh run list --workflow=ci.yml -L 2 && gh run list --workflow=deploy.yml -L 2
```

Expected: both `success`. If Deploy fails at the secrets step with `FATAL: SECRET_KEY missing`, the
GitHub Secret was not created or is empty — fix it and re-run; the site is unaffected because the
failure happens before the restart.

- [ ] **Step 3: Verify the file landed with correct permissions (no values printed)**

On the VPS:

```bash
ssh -i ~/.ssh/ielts_assist_deploy root@152.42.251.169 "ls -l /root/IELTS-Assist/backend/.env && cut -d= -f1 /root/IELTS-Assist/backend/.env"
```

Expected: mode `-rw-------`, owner `root`, and exactly these five names — `SECRET_KEY`,
`DATABASE_URL`, `OPENAI_API_KEY`, `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`.

- [ ] **Step 4: Prove the new signing key is actually in effect**

The definitive test: a token issued before the change must now be rejected. Log in on
`https://annababy.cc`, then confirm any previously-open session is logged out.

Expected: **all existing users are logged out exactly once.** That is the visible signature of the key
having rotated. If nobody is logged out, `.env` is not being read — stop and investigate before
assuming the vulnerability is closed.

- [ ] **Step 5: Confirm the AI features still work**

Grade one writing task and generate one exercise through the UI. These still draw credentials from the
systemd unit, so they must behave exactly as before.

---

## Task 3: Fail loudly on an insecure key (hardening)

Ship this **only after Task 2 passes**. It converts "silently insecure" into "refuses to start".

**Files:**
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_config_guard.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_config_guard.py`:

```python
import pytest

from app.config import INSECURE_SECRET_KEY, assert_secret_key_is_safe


def test_rejects_the_placeholder_key():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        assert_secret_key_is_safe(INSECURE_SECRET_KEY)


def test_rejects_an_empty_key():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        assert_secret_key_is_safe("")


def test_accepts_a_real_key():
    assert_secret_key_is_safe("Zq3n_KpX8sVb2LmT9wYc1RfJ4hGd7aNe0oUiPtSxQvB") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_config_guard.py -v`
Expected: FAIL — `ImportError: cannot import name 'INSECURE_SECRET_KEY'`

- [ ] **Step 3: Implement the guard**

In `backend/app/config.py`, change line 13 to reference a named constant and add the check function.
Above `class Settings`, add:

```python
INSECURE_SECRET_KEY = "your-secret-key-change-in-production"


def assert_secret_key_is_safe(key: str) -> None:
    """Refuse to run with a guessable JWT signing key.

    Every token is signed and verified with this value, so the placeholder default
    would let anyone mint a token for any account.
    """
    if not key or key == INSECURE_SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY is unset or still the placeholder. Set it via "
            "/root/IELTS-Assist/backend/.env (written by the deploy workflow from GitHub Secrets)."
        )
```

Change the field default to use the constant:

```python
    SECRET_KEY: str = INSECURE_SECRET_KEY
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_config_guard.py -v`
Expected: PASS — 3 passed.

- [ ] **Step 5: Enforce it at application startup**

In `backend/app/main.py`, after the `settings` import, add:

```python
from app.config import assert_secret_key_is_safe

assert_secret_key_is_safe(settings.SECRET_KEY)
```

⚠️ This makes a missing `SECRET_KEY` a hard boot failure. That is the intent — combined with the
Task 1 health check, a broken secret now fails the deploy loudly instead of silently reverting to a
forgeable key. Only ship this once Task 2 Step 4 has proven `.env` loads.

- [ ] **Step 6: Confirm the whole suite still passes**

Run: `cd backend && python -m pytest tests/ -v`
Expected: PASS.

The test suite must supply a `SECRET_KEY`; if `tests/conftest.py` does not already set one, add
`os.environ.setdefault("SECRET_KEY", "test-key-not-used-in-production")` at the top of that file.

- [ ] **Step 7: Commit and deploy**

```bash
git add backend/app/config.py backend/app/main.py backend/tests/test_config_guard.py backend/tests/conftest.py
git commit -m "feat(security): refuse to boot with a placeholder SECRET_KEY"
git push origin main
```

Then confirm `gh run list --workflow=deploy.yml -L 2` is `success` and the site still loads.

---

---

# Phase 2 Spec — every runtime variable from GitHub Secrets, via CI

**Status:** ready. Youdao retired in `293c84c`, which was the only blocker.

**Goal:** `.env` — written by the deploy workflow from GitHub Secrets — becomes the **sole** source of
every runtime variable the backend reads. Nothing configured by hand on the server.

## Why this is required, not cosmetic

Environment variables set by systemd **take precedence over `.env`**. The unit currently defines
`DATABASE_URL`, `OPENAI_API_KEY`, `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`,
`GOOGLE_APPLICATION_CREDENTIALS` and `PYTHONUNBUFFERED`, so those inline values win and the ones the
deploy writes are **silently ignored**.

Concretely: **rotating `OPENAI_API_KEY` in GitHub Secrets today does nothing.** The deploy writes the
new value into `.env`, the unit keeps supplying the old one, and there is no error. GitHub Secrets are
currently authoritative for exactly one variable — `SECRET_KEY` — because it is the only one the unit
does not already define.

## Approach: a drop-in, not a unit rewrite

Earlier drafts of this plan called for editing the unit by hand. That was wrong on two counts: it is
not a read-only/diagnostic action (the project's SSH rule permits only those), and a hand-edited unit
is neither reviewable nor repeatable. The deploy workflow already SSHes in as root, so it manages
this itself, idempotently, on every deploy.

`/etc/systemd/system/ielts-backend.service.d/override.conf`:

```ini
[Service]
# Empty assignment resets the list systemd inherited from the base unit, so the
# inline secrets there stop applying without the unit file being touched.
Environment=
EnvironmentFile=/root/IELTS-Assist/backend/.env
```

Properties this buys:
- The **base unit is never modified** — nothing to corrupt, nothing to restore.
- **Rollback is deleting one file** plus `daemon-reload`.
- It is ordinary repo code (`deploy.yml`), reviewed in a commit and applied by CI.

⚠️ **Assumption to verify on first run:** systemd documents that an empty `Environment=` resets the
inherited list. Task 6 verifies the inline values genuinely stopped applying rather than assuming it.

## Variable inventory after Phase 2

| Variable | Source | Notes |
|---|---|---|
| `SECRET_KEY` | GitHub Secret → `.env` | already working |
| `DATABASE_URL` | GitHub Secret → `.env` | pre-flight: hash matches unit, connects OK |
| `OPENAI_API_KEY` | GitHub Secret → `.env` | pre-flight: hash matches unit, 125 models visible |
| `AZURE_SPEECH_KEY` | GitHub Secret → `.env` | pre-flight: hash matches unit |
| `AZURE_SPEECH_REGION` | GitHub Secret → `.env` | pre-flight: hash matches unit |
| `PYTHONUNBUFFERED` | `.env` (literal `1`) | not a secret; moved for single-source-of-truth |
| `GOOGLE_APPLICATION_CREDENTIALS` | `.env` (literal path) | points at the file below |
| *(the GCP key file)* | GitHub Secret `GCP_SA_KEY_JSON` → `/root/ielts-tts-key.json` | shipped by scp, see Task 2 |
| `YOUDAO_APP_KEY` / `_SECRET` | **removed** | vendor retired in `293c84c` |
| `OPENROUTER_API_KEY` | **removed** | already deleted from the unit; still needs revoking at the provider |

## Task 1: Write the full variable set into .env

**Files:** Modify `.github/workflows/deploy.yml`

- [ ] **Step 1: Extend the printf block** in the "Runtime secrets" section with the two
      non-secret variables, so `.env` is complete rather than partial:

```bash
                "PYTHONUNBUFFERED=1" \
                "GOOGLE_APPLICATION_CREDENTIALS=/root/ielts-tts-key.json" \
```

⚠️ systemd's `EnvironmentFile` parser is stricter than python-dotenv: it does not expand variables and
treats a leading `#` as a comment. All current values are plain tokens and paths, so this is safe —
but a future secret containing `#` or a newline would need quoting.

## Task 2: Ship the GCP service-account key from its secret

The JSON is multi-line, so it cannot travel through the ssh-action's `envs`. Write it to a file in
the runner and scp it — the value never appears in a command line or log.

- [ ] **Step 1: Materialise the secret in the runner**, before the scp step:

```yaml
      - name: Materialise GCP service-account key
        env:
          GCP_SA_KEY_JSON: ${{ secrets.GCP_SA_KEY_JSON }}
        run: |
          printf '%s' "$GCP_SA_KEY_JSON" > gcp-key.json
          python -c "import json;json.load(open('gcp-key.json'));print('valid JSON')"
```

Failing here is the desired behaviour: a malformed secret must stop the deploy, not reach the server.

- [ ] **Step 2: Ship it to a staging path** (never straight over the live key):

```yaml
      - name: Ship GCP key to VPS
        uses: appleboy/scp-action@v1
        with:
          host: ${{ secrets.VPS_HOST }}
          username: root
          key: ${{ secrets.VPS_SSH_KEY }}
          source: "gcp-key.json"
          target: "/root/staging"
          overwrite: true
```

- [ ] **Step 3: Validate then install it**, inside the deploy script before the backend restart:

```bash
            # GCP key — validate the shipped copy before it replaces the working one
            if python3 -c "import json,sys;json.load(open('/root/staging/gcp-key.json'))" 2>/dev/null; then
              install -m 600 /root/staging/gcp-key.json /root/ielts-tts-key.json
              echo "Installed GCP service-account key"
            else
              echo "FATAL: shipped GCP key is not valid JSON" >&2
              exit 1
            fi
```

## Task 3: Install the systemd drop-in

- [ ] **Step 1: Write it idempotently** in the deploy script, before the backend restart:

```bash
            # Make .env authoritative: reset the inline Environment list from the base unit.
            DROPIN=/etc/systemd/system/ielts-backend.service.d
            mkdir -p "$DROPIN"
            cat > "$DROPIN/override.conf" <<'CONF'
[Service]
Environment=
EnvironmentFile=/root/IELTS-Assist/backend/.env
CONF
            systemctl daemon-reload
```

`daemon-reload` must precede the `systemctl restart` already in the script.

## Task 4: Roll back automatically if the backend does not come up

- [ ] **Step 1: Wrap the existing health check** so a failed boot removes the drop-in and restarts on
      the old configuration, rather than leaving the API down:

```bash
            if [ "${OK:-0}" != "1" ]; then
              echo "Backend unhealthy after cutover — removing drop-in and reverting" >&2
              rm -f /etc/systemd/system/ielts-backend.service.d/override.conf
              systemctl daemon-reload
              systemctl restart ielts-backend
              sleep 5
              curl -s -o /dev/null -w "after revert: HTTP %{http_code}\n" -m 5 http://127.0.0.1:8000/
              exit 1
            fi
```

## Task 5: Deploy

- [ ] Push to `main`; confirm CI then Deploy are both `success`.
- [ ] Confirm the deploy log shows `Installed GCP service-account key` and `Backend healthy`.

## Task 6: Verify the cutover actually took effect

Do not infer success from a green deploy — the drop-in reset is the assumption under test.

- [ ] **Step 1: Confirm the base unit is untouched** — it should still contain its inline
      `Environment=` lines, proving nothing was rewritten.
- [ ] **Step 2: Confirm the retired variables are gone from the service environment.**
      `systemctl show ielts-backend -p Environment` must show **no** `YOUDAO_*`. If they are still
      present, the empty-`Environment=` reset did not work and the approach needs revisiting.
- [ ] **Step 3: Prove the app still reads every secret** — a Speaking transcription exercises
      `OPENAI_API_KEY`, listening audio exercises the GCP key, any page load exercises `DATABASE_URL`,
      and being logged in exercises `SECRET_KEY`.
- [ ] **Step 4: Prove rotation now works** — the point of the whole exercise. Change a
      non-critical secret (`AZURE_SPEECH_REGION`) in GitHub, redeploy, and confirm the new value
      reaches the app. Before Phase 2 this silently would not have.

## Follow-ups deliberately excluded

- Removing `--reload` from `ExecStart` (backlog item 5) requires touching the base unit and is a
  production-readiness concern, not a secrets one. Keep this change focused.
- Revoking `OPENROUTER_API_KEY` at the provider — only the account owner can do it.
