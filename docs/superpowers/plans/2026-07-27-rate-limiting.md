# AI Usage Quotas & Circuit Breaker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cap what any single user — and the application as a whole — can spend on paid AI calls in a day, so cost cannot scale without bound when the app goes public.

**Architecture:** A `UsageCounter` table holds one row per (user, UTC day, category). A FastAPI dependency increments and checks it before the expensive work runs. Categories carry a rough USD weight, so the same table also powers a global daily spend cap that trips a circuit breaker for everyone.

**Tech Stack:** FastAPI dependencies, SQLAlchemy, Postgres. No new libraries.

---

## 1. Why

Every paid endpoint is currently unbounded. An authenticated user — or a bug, or a loop in the frontend — can call grading and generation as fast as the server answers. There is no cap, no alert, and no way to stop it short of taking the app down.

This is the single largest financial risk at launch, and unlike the other backlog items it fails *silently and expensively* rather than loudly.

### Costs are wildly asymmetric, so a flat request limit is wrong

| Category | Endpoints | What it costs | Rough USD/call |
|---|---|---|---|
| `grade` | writing + speaking grading | luna grading, plus Whisper + Azure PA for speaking | **~$0.02–0.05** |
| `generate` | reading/listening/grammar generation | luna authoring + Google TTS for listening audio | **~$0.01–0.10** |
| `lookup` | `define-word`, `translate`, `explain-mistakes`, `extract-vocabulary` | one small `utility` call | **~$0.0007** |

A single "200 requests/day" rule would either strangle vocabulary lookups or leave grading wide open. Limits are therefore per-category.

### Cache hits must not count

`define-word` serves most lookups from `vocab_cache` at zero cost. Charging quota for a free response would punish exactly the behaviour we want. The dependency records usage *before* the handler runs, so cached responses need an explicit refund — see Task 3.

## 2. Design decisions

1. **Database-backed, not in-memory.** A single uvicorn worker means an in-process counter would work, but deploys happen several times a day and would reset every quota. Counters must survive restarts.
2. **No new dependency.** `slowapi` is built around IP + sliding windows, and Redis is a non-starter on a 2 GB box already under memory pressure. Per-user daily counters against Postgres are a dozen lines.
3. **Limits are configuration, not code.** They live in `config.py`, so they reach the server through the `.env` pipeline built in secrets Phase 2 and can be changed without a code review.
4. **UTC days.** Simple, predictable, and matches the existing `daily_generate` cron.
5. **The cron is exempt.** `daily_generate` runs in-process with no user, so it never passes through the dependency. Its cost is bounded by its schedule.
6. **Fail open on counter errors.** If the quota table itself errors, log and allow the request. A bug in metering must not take down the product; the global cap remains as the backstop.

## 3. File structure

| File | Responsibility |
|---|---|
| `backend/app/models/models.py` | **Modify.** Add `UsageCounter`. |
| `backend/app/config.py` | **Modify.** Per-category limits + global daily spend cap. |
| `backend/app/services/quota.py` | **Create.** Counter increment, quota check, circuit breaker. |
| `backend/app/routers/*.py` | **Modify.** Attach the dependency to paid routes. |
| `backend/tests/test_quota.py` | **Create.** Limits, refunds, breaker, fail-open. |

---

## Task 1: UsageCounter model

**Files:** Modify `backend/app/models/models.py`

- [ ] **Step 1: Add the model** after `VocabCache`:

```python
class UsageCounter(Base):
    """Paid-AI usage per user, per UTC day, per category.

    Database-backed rather than in-process: deploys restart the app several
    times a day and would otherwise reset everyone's quota.
    """

    __tablename__ = "usage_counters"
    __table_args__ = (UniqueConstraint("user_id", "day", "category", name="uq_usage_user_day_category"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    day = Column(Date, nullable=False, index=True)        # UTC
    category = Column(String(20), nullable=False)         # grade | generate | lookup
    count = Column(Integer, nullable=False, default=0)
```

- [ ] **Step 2: Add the imports** `Date` and `UniqueConstraint` to the existing `sqlalchemy` import line.

- [ ] **Step 3: Verify**

Run: `cd backend && python -c "from app.models.models import UsageCounter; print(UsageCounter.__tablename__)"`
Expected: `usage_counters`

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/models.py
git commit -m "feat(quota): add UsageCounter model"
```

---

## Task 2: Configuration

**Files:** Modify `backend/app/config.py`

- [ ] **Step 1: Add settings** after the model tiers:

```python
    # --- AI usage quotas (per user, per UTC day) ---
    # Sized so normal study is never interrupted while a runaway loop is capped.
    QUOTA_GRADE_PER_DAY: int = 30        # ~$1.50/day worst case per user
    QUOTA_GENERATE_PER_DAY: int = 60
    QUOTA_LOOKUP_PER_DAY: int = 300      # cache hits are refunded, so this is generous
    # Global circuit breaker: estimated spend across ALL users in a UTC day.
    # Trips to 503 on paid endpoints until midnight UTC.
    DAILY_SPEND_CAP_USD: float = 20.0
    QUOTAS_ENABLED: bool = True          # kill switch, no redeploy needed
```

- [ ] **Step 2: Verify**

Run: `cd backend && python -c "from app.config import settings; print(settings.QUOTA_GRADE_PER_DAY, settings.DAILY_SPEND_CAP_USD)"`
Expected: `30 20.0`

---

## Task 3: Quota service

**Files:** Create `backend/app/services/quota.py`, Test `backend/tests/test_quota.py`

- [ ] **Step 1: Write the failing test**

```python
import datetime as dt

import pytest
from fastapi import HTTPException

from app.models.models import UsageCounter, User
from app.services import quota


def _user(db):
    u = User(email="q@example.com", username="q", full_name="Q", hashed_password="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_first_call_is_allowed_and_counted(test_db):
    u = _user(test_db)
    quota.consume(test_db, u.id, "lookup", limit=3)
    row = test_db.query(UsageCounter).filter_by(user_id=u.id, category="lookup").one()
    assert row.count == 1


def test_exceeding_the_limit_raises_429(test_db):
    u = _user(test_db)
    for _ in range(3):
        quota.consume(test_db, u.id, "lookup", limit=3)
    with pytest.raises(HTTPException) as exc:
        quota.consume(test_db, u.id, "lookup", limit=3)
    assert exc.value.status_code == 429


def test_refund_gives_the_call_back(test_db):
    """Cache hits cost nothing, so they must not consume quota."""
    u = _user(test_db)
    quota.consume(test_db, u.id, "lookup", limit=1)
    quota.refund(test_db, u.id, "lookup")
    quota.consume(test_db, u.id, "lookup", limit=1)  # must not raise


def test_categories_are_counted_separately(test_db):
    u = _user(test_db)
    quota.consume(test_db, u.id, "lookup", limit=1)
    quota.consume(test_db, u.id, "grade", limit=1)  # must not raise


def test_estimated_spend_sums_weighted_usage(test_db):
    u = _user(test_db)
    quota.consume(test_db, u.id, "grade", limit=10)
    spend = quota.estimated_spend_today(test_db)
    assert spend == pytest.approx(quota.COST_WEIGHTS["grade"])


def test_breaker_trips_above_the_cap(test_db):
    u = _user(test_db)
    quota.consume(test_db, u.id, "grade", limit=100)
    with pytest.raises(HTTPException) as exc:
        quota.check_breaker(test_db, cap_usd=0.001)
    assert exc.value.status_code == 503
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_quota.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.quota'`

- [ ] **Step 3: Implement**

```python
"""Per-user daily quotas and a global spend circuit breaker for paid AI calls.

Counters live in Postgres rather than memory: deploys restart the app several
times a day and would otherwise hand everyone a fresh quota.
"""

import datetime as dt
import logging

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.models import UsageCounter, User
from app.services.auth import get_current_user

logger = logging.getLogger(__name__)

# Rough USD per call, used only for the global breaker. Order-of-magnitude is
# enough — this decides when to stop spending, not what to bill.
COST_WEIGHTS = {"grade": 0.04, "generate": 0.05, "lookup": 0.001}

LIMITS = {
    "grade": lambda: settings.QUOTA_GRADE_PER_DAY,
    "generate": lambda: settings.QUOTA_GENERATE_PER_DAY,
    "lookup": lambda: settings.QUOTA_LOOKUP_PER_DAY,
}


def _today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def _row(db: Session, user_id: int, category: str) -> UsageCounter:
    row = (
        db.query(UsageCounter)
        .filter_by(user_id=user_id, day=_today(), category=category)
        .first()
    )
    if row is None:
        row = UsageCounter(user_id=user_id, day=_today(), category=category, count=0)
        db.add(row)
        db.flush()
    return row


def consume(db: Session, user_id: int, category: str, limit: int) -> None:
    """Count one paid call. Raises 429 once the user is over their daily limit."""
    row = _row(db, user_id, category)
    if row.count >= limit:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Daily {category} limit reached ({limit}). "
                "It resets at midnight UTC."
            ),
        )
    row.count += 1
    db.commit()


def refund(db: Session, user_id: int, category: str) -> None:
    """Give a call back when it turned out to cost nothing (e.g. a cache hit)."""
    row = _row(db, user_id, category)
    if row.count > 0:
        row.count -= 1
        db.commit()


def estimated_spend_today(db: Session) -> float:
    """Weighted sum of today's usage across all users, in USD."""
    rows = db.query(UsageCounter).filter(UsageCounter.day == _today()).all()
    return sum(COST_WEIGHTS.get(r.category, 0.0) * r.count for r in rows)


def check_breaker(db: Session, cap_usd: float) -> None:
    """Stop all paid work once the estimated daily spend exceeds the cap."""
    if estimated_spend_today(db) >= cap_usd:
        raise HTTPException(
            status_code=503,
            detail="Daily AI budget reached. Service resumes at midnight UTC.",
        )


def quota(category: str):
    """FastAPI dependency factory: attach to any route that spends money.

    Fails open on unexpected errors — a bug in metering must not take down the
    product. The global breaker remains as the backstop.
    """

    def dependency(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> None:
        if not settings.QUOTAS_ENABLED:
            return
        try:
            check_breaker(db, settings.DAILY_SPEND_CAP_USD)
            consume(db, current_user.id, category, LIMITS[category]())
        except HTTPException:
            raise
        except Exception as e:
            logger.error("quota check failed open for user %s: %s", current_user.id, e)

    return dependency
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest tests/test_quota.py -q`
Expected: PASS — 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/quota.py backend/tests/test_quota.py
git commit -m "feat(quota): per-user daily quotas and global spend breaker"
```

---

## Task 4: Attach to paid routes

**Files:** Modify the six routers that spend money.

- [ ] **Step 1: Apply the dependency.** For each route below add `dependencies=[Depends(quota("<category>"))]` to its decorator and import `from app.services.quota import quota`.

| Router | Routes | Category |
|---|---|---|
| `writing.py` | the grading submission route | `grade` |
| `speaking.py` | both transcription/grading routes | `grade` |
| `reading.py` | on-demand generation | `generate` |
| `listening.py` | on-demand generation | `generate` |
| `grammar.py` | on-demand generation | `generate` |
| `generate.py` | `explain-mistakes`, `extract-vocabulary`, `translate`, `define-word` | `lookup` |

Read each router before editing and attach only to routes that actually reach a paid call — routes that merely serve pre-generated content from the pool must stay unmetered, or normal study would burn quota for free work.

- [ ] **Step 2: Refund cached lookups** in `define_word`, immediately before the cached return:

```python
    if cached:
        # Served from cache — cost nothing, so give the quota back.
        quota_service.refund(db, current_user.id, "lookup")
        return {...}
```

Import as `from app.services import quota as quota_service` to avoid clashing with the dependency factory.

- [ ] **Step 3: Verify with a test** appended to `tests/test_quota.py`:

```python
def test_cached_lookup_does_not_consume_quota(client, test_user, auth_token, monkeypatch, test_db):
    from app.services import vocab

    monkeypatch.setattr(vocab, "generate_entry", lambda w, c=None: {
        "definition_en": "x", "definition_zh": None, "example": None, "phonetic": None})
    monkeypatch.setattr(vocab, "synthesize_pronunciation", lambda w: None)

    h = {"Authorization": f"Bearer {auth_token}"}
    client.post("/api/generate/define-word", json={"word": "reef"}, headers=h)
    client.post("/api/generate/define-word", json={"word": "reef"}, headers=h)  # cached

    row = test_db.query(UsageCounter).filter_by(user_id=test_user.id, category="lookup").one()
    assert row.count == 1, "the cached second lookup must not consume quota"
```

- [ ] **Step 4: Run the suite**

Run: `cd backend && python -m pytest tests/ -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app
git commit -m "feat(quota): meter paid routes, refund cached lookups"
```

---

## Task 5: Deploy and verify

- [ ] **Step 1:** Push; confirm CI and Deploy are `success`.
- [ ] **Step 2: Verify the happy path** — normal study is unaffected. Grade an essay, generate an exercise, look up several words.
- [ ] **Step 3: Verify the limit trips.** Temporarily set `QUOTA_LOOKUP_PER_DAY=2` in the environment, restart, and confirm the third lookup returns **429** with the reset message.
- [ ] **Step 4: Verify the refund** — look the same word up repeatedly and confirm `usage_counters.count` stops rising once it is cached.
- [ ] **Step 5: Verify the breaker** — set `DAILY_SPEND_CAP_USD=0.001`, confirm paid endpoints return **503** while unpaid pages still load, then restore.
- [ ] **Step 6: Restore real limits** and confirm normal operation.

## 4. Rollout note

Ship with `QUOTAS_ENABLED=true` and the defaults above. They are deliberately generous — the goal is to bound catastrophe, not to ration study. Watch `usage_counters` for a week before tightening: real usage data beats a guess, and the table is the observability this app currently lacks.

`QUOTAS_ENABLED=false` is a kill switch that needs only an env change, no redeploy, if quotas ever misfire against a real user.

## 5. Deliberately excluded

- **Per-IP limiting for unauthenticated routes.** Login and register are cheap; abuse there is a different problem (credential stuffing) needing a different tool.
- **Billing or paid tiers.** This caps spend; it does not charge for it.
- **Alerting.** Worth adding once there is somewhere to send an alert. The counters make it easy later.
