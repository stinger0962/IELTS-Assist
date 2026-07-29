# Password Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user who has forgotten their password recover their account by email, without an administrator editing Postgres by hand.

**Architecture:** A single-use, time-limited token is emailed as a link. Only its SHA-256 hash is stored, so a database leak cannot be used to seize accounts. Completing a reset also invalidates every existing session for that user. Mail goes out through Resend, which the owner already uses.

**Tech Stack:** FastAPI, SQLAlchemy, `httpx` (already a dependency), Resend REST API, React.

---

## 1. Why now

`auth.py` exposes exactly four endpoints: register, login, me, settings. **There is no password reset and no email capability anywhere in the codebase.** Every user who forgets their password is permanently locked out, and the only remedy is hand-editing `users.hashed_password` in Postgres. With one user that is an annoyance; at launch it is the thing that quietly kills retention.

### The related security gap

`create_access_token` puts only `sub` and `exp` in the JWT — no `iat`, no `jti`. Tokens therefore cannot be revoked, and `ACCESS_TOKEN_EXPIRE_MINUTES` is **7 days**.

So a reset that only changes `hashed_password` leaves any stolen token working for up to a week. Since "someone else has my account" is the main reason people reset passwords, that would make the feature largely cosmetic. Session invalidation is in scope for this plan, not a follow-up.

## 2. Decisions

1. **Store only the token hash.** The emailed value is never persisted. A database leak then yields nothing usable.
2. **One hour expiry, single use.** A completed reset also invalidates that user's other outstanding tokens.
3. **Never reveal whether an email is registered.** `forgot-password` always returns the same 200. Account enumeration on a study app is a real privacy leak (it says who is preparing for IELTS).
4. **Invalidate sessions via `password_changed_at`.** Cheaper than a token blocklist: stamp the user, put `iat` in the JWT, reject tokens issued earlier. No new storage, no lookup per request.
5. **Degrade, never crash, when unconfigured.** With no `RESEND_API_KEY` the link is logged instead of sent, so the feature can ship before the secret exists — the same pattern used for the GCP key.
6. **Throttle by user, not IP.** Cloudflare hides client IPs unless we parse `CF-Connecting-IP`; counting recent tokens per user is simpler and directly limits mail volume per mailbox.

## 3. What the owner must provide

| Item | Notes |
|---|---|
| `RESEND_API_KEY` GitHub Secret | From the existing Resend account |
| **Domain verification for `annababy.cc` in Resend** | ⚠️ Without it Resend only delivers to the account owner's own address. Needs SPF/DKIM records in Cloudflare — the same records Cloudflare already warns are missing |
| `EMAIL_FROM` | e.g. `IELTS Assist <noreply@annababy.cc>`; must be on the verified domain |

## 4. File structure

| File | Responsibility |
|---|---|
| `backend/app/models/models.py` | **Modify.** `PasswordResetToken`; `User.password_changed_at`. |
| `backend/app/config.py` | **Modify.** Resend key, from-address, frontend base URL, TTL, throttle. |
| `backend/app/services/email.py` | **Create.** Resend transport; no-op with a logged link when unconfigured. |
| `backend/app/services/password_reset.py` | **Create.** Token issue/verify/consume. |
| `backend/app/services/auth.py` | **Modify.** `iat` in tokens; reject pre-reset tokens. |
| `backend/app/routers/auth.py` | **Modify.** `forgot-password`, `reset-password`. |
| `backend/tests/test_password_reset.py` | **Create.** |
| `frontend/src/pages/ForgotPassword.tsx`, `ResetPassword.tsx` | **Create.** |
| `frontend/src/api/index.ts`, `App.tsx`, `Auth.tsx` | **Modify.** Client calls, routes, link. |

---

## Task 1: Model

- [ ] **Step 1** Add to `models.py`:

```python
class PasswordResetToken(Base):
    """Single-use password reset token.

    Only the SHA-256 hash is stored: the value that can actually reset an
    account exists solely in the email we sent, so a database leak yields
    nothing usable.
    """

    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
```

- [ ] **Step 2** Add to `User`:

```python
    # Set on every password change. Tokens issued before this are rejected, so a
    # reset ends sessions an attacker may already hold.
    password_changed_at = Column(DateTime, nullable=True)
```

## Task 2: Config

- [ ] **Step 1** Add to `Settings`:

```python
    # --- Transactional email (Resend) ---
    RESEND_API_KEY: str = ""            # unset => links are logged, not sent
    EMAIL_FROM: str = "IELTS Assist <noreply@annababy.cc>"
    FRONTEND_BASE_URL: str = "https://annababy.cc"
    PASSWORD_RESET_TTL_MINUTES: int = 60
    PASSWORD_RESET_MAX_PER_HOUR: int = 3
```

## Task 3: Email transport

- [ ] **Step 1** Create `backend/app/services/email.py` with `send_email(to, subject, html) -> bool`, posting to `https://api.resend.com/emails` with `Authorization: Bearer`. When `RESEND_API_KEY` is empty, log and return `False` rather than raising. Never log the token itself in production paths.

## Task 4: Token service

- [ ] **Step 1** Create `backend/app/services/password_reset.py`:
  - `hash_token(raw) -> str` — SHA-256 hex.
  - `issue(db, user) -> str | None` — returns the raw token, or `None` when the user is over `PASSWORD_RESET_MAX_PER_HOUR`.
  - `consume(db, raw, new_password) -> bool` — validates hash, expiry and single use; sets the password; stamps `password_changed_at`; marks this token and every other outstanding one for that user as used.

## Task 5: Session invalidation

- [ ] **Step 1** In `create_access_token`, add `"iat": datetime.utcnow()`.
- [ ] **Step 2** In `get_current_user`, after loading the user, reject when `user.password_changed_at` is set and `iat` predates it (allow one second of clock slack).

## Task 6: Endpoints

- [ ] **Step 1** `POST /api/auth/forgot-password` — always returns the same 200 body regardless of whether the address exists or is throttled.
- [ ] **Step 2** `POST /api/auth/reset-password` — `{token, new_password}`; 400 on invalid, expired or already-used; enforce a minimum password length consistent with register.

## Task 7: Frontend

- [ ] Add `ForgotPassword` and `ResetPassword` pages, an API client pair, routes, and a "Forgot password?" link on the login form. The reset page reads the token from the query string.

## Task 8: Tests

Cover: hash is stored not the raw token; expired token rejected; used token rejected; successful reset changes the password and invalidates old sessions; `forgot-password` returns an identical response for known and unknown addresses; throttle engages; the flow works with email unconfigured.

## Task 9: Deploy

- [ ] Add `RESEND_API_KEY` to the workflow's secret list and `.env`, ship, and verify a real reset end to end.

## 5. Out of scope

- **Email verification at registration.** Worth doing, but it gates signup and should not ride along with account recovery.
- **Login rate limiting.** Distinct concern (credential stuffing), distinct fix.
