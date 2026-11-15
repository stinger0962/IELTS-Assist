"""Opt-in real PostgreSQL acceptance tests; never import app/database/main.

Run from repo root with the CI-only local Postgres 16 service. An isolated schema
is created and removed; no provider calls, production credentials or grant API.
"""
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

URL = os.getenv('IELTS_TEST_POSTGRES_URL')
pytestmark = pytest.mark.skipif(not URL, reason='disposable PostgreSQL URL not provided')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))


@pytest.fixture
def pg(monkeypatch):
    # Fail, never skip/fallback, if a configured target is unsafe or unavailable.
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import sessionmaker
    from app.config import settings
    from app.models.models import Base
    from app.services import study_pass

    if os.getenv('IELTS_TEST_POSTGRES_ALLOW_DISPOSABLE') != '1':
        pytest.fail('explicit disposable-database opt-in required')
    url = make_url(URL)
    if (url.get_backend_name() != 'postgresql' or url.host not in ('127.0.0.1', 'localhost')
            or url.database != 'test_db' or url.username != 'test_user'
            or url.port not in (None, 5432, 5433) or url.query):
        pytest.fail('refusing target: expected loopback CI test_user/test_db with no URL options')
    schema = 'ielts_qa_' + uuid4().hex
    # Explicit driver: do not consult the app's database fallback/initialization.
    bootstrap = create_engine(url.set(drivername='postgresql+psycopg2'), connect_args={'connect_timeout': 3})
    with bootstrap.begin() as conn:
        identity = conn.execute(text('SELECT current_user, current_database()')).one()
        assert tuple(identity) == ('test_user', 'test_db')
        assert conn.dialect.name == 'postgresql'
        conn.execute(text(f'CREATE SCHEMA {schema}'))
    engine = create_engine(url.set(drivername='postgresql+psycopg2'), connect_args={
        'connect_timeout': 3,
        'options': f'-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000',
    }, pool_size=5, max_overflow=0)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(settings, 'STUDY_PASS_ENABLED', True)
    try:
        Base.metadata.create_all(engine)
        yield factory, study_pass, settings
    finally:
        engine.dispose()
        try:
            with bootstrap.begin() as conn:
                conn.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        finally:
            bootstrap.dispose()


def seed(factory, role='free', cards=2):
    from app.models.models import User, GeneratedPractice, UserPractice
    with factory() as db:
        suffix = uuid4().hex
        user = User(email=f'{suffix}@invalid.test', username=suffix, hashed_password='fixture', role=role)
        db.add(user)
        db.flush()
        ids = []
        for _ in range(cards):
            practice = GeneratedPractice(skill='writing', content='{}')
            db.add(practice)
            db.flush()
            db.add(UserPractice(user_id=user.id, practice_id=practice.id))
            ids.append(practice.id)
        db.commit()
        return user.id, ids


def user_for(db, user_id):
    from app.models.models import User
    return db.get(User, user_id)


def reserve_parallel(factory, service, user_id, practice_ids):
    from fastapi import HTTPException
    start = threading.Barrier(len(practice_ids))
    def reserve(practice_id):
        with factory() as db:
            user = user_for(db, user_id)
            start.wait(timeout=5)
            try:
                return 'reserved', service.reserve_writing_review(db, user, practice_id)
            except HTTPException as exc:
                return exc.status_code, exc.detail
    with ThreadPoolExecutor(max_workers=len(practice_ids)) as pool:
        futures = [pool.submit(reserve, p) for p in practice_ids]
        return [future.result(timeout=20) for future in futures]


def test_feature_off_preserves_legacy_and_does_not_create_grants(pg):
    from app.models.models import StudyPassGrant, WritingReviewReservation
    factory, service, settings = pg
    free, cards = seed(factory)
    vip, _ = seed(factory, role='vip')
    settings.STUDY_PASS_ENABLED = False
    with factory() as db:
        assert service.study_pass_status(db, user_for(db, free)) == dict(
            enabled=False, status='none', expires_at=None,
            writing_reviews_remaining=None, full_mock_access=False)
        assert service.study_pass_status(db, user_for(db, vip))['full_mock_access'] is True
        assert service.reserve_writing_review(db, user_for(db, free), cards[0]) is None
        assert db.query(StudyPassGrant).count() == db.query(WritingReviewReservation).count() == 0


def test_lifetime_free_and_expired_pass_fallback(pg):
    from fastapi import HTTPException
    factory, service, _ = pg
    user_id, cards = seed(factory)
    now = datetime.utcnow()
    with factory() as db:
        service.grant_study_pass(db, user_id, 'old-pass', 4, now=now - timedelta(days=31))
        db.commit()
        user = user_for(db, user_id)
        status = service.study_pass_status(db, user, now=now)
        assert status['status'] == 'expired'
        assert status['writing_reviews_remaining'] == 1
        assert status['full_mock_access'] is False
        reservation = service.reserve_writing_review(db, user, cards[0])
        service.finalize_writing_review(db, reservation)
        db.commit()
        assert service.study_pass_status(db, user)['writing_reviews_remaining'] == 0
        with pytest.raises(HTTPException) as error:
            service.reserve_writing_review(db, user, cards[1])
        assert error.value.status_code == 402
        assert error.value.detail['code'] == 'study_pass_required'


def test_active_paid_allowance_zero_does_not_remove_mock_access(pg):
    from fastapi import HTTPException
    factory, service, _ = pg
    user_id, cards = seed(factory)
    with factory() as db:
        service.grant_study_pass(db, user_id, 'paid-pass', 1)
        db.commit()
        user = user_for(db, user_id)
        reservation = service.reserve_writing_review(db, user, cards[0])
        service.finalize_writing_review(db, reservation)
        db.commit()
        status = service.study_pass_status(db, user)
        assert status['status'] == 'active'
        assert status['writing_reviews_remaining'] == 0
        assert status['full_mock_access'] is True
        with pytest.raises(HTTPException) as error:
            service.reserve_writing_review(db, user, cards[1])
        assert error.value.status_code == 402  # no silent trial fallback while active


def test_expiry_boundary_is_exclusive(pg):
    factory, service, _ = pg
    user_id, _ = seed(factory)
    start = datetime(2026, 11, 1)
    with factory() as db:
        grant = service.grant_study_pass(db, user_id, 'boundary', 2, now=start)
        db.commit()
        user = user_for(db, user_id)
        assert service.study_pass_status(db, user, now=grant.expires_at - timedelta(microseconds=1))['status'] == 'active'
        assert service.study_pass_status(db, user, now=grant.expires_at)['status'] == 'expired'


def test_concurrent_first_free_requests_cannot_double_grant(pg):
    from app.models.models import StudyPassGrant, WritingReviewReservation
    factory, service, _ = pg
    user_id, cards = seed(factory)
    results = reserve_parallel(factory, service, user_id, cards)
    assert sorted(str(r[0]) for r in results) == ['402', 'reserved']
    with factory() as db:
        assert db.query(StudyPassGrant).filter_by(user_id=user_id, kind='trial').count() == 1
        assert db.query(StudyPassGrant).filter_by(user_id=user_id).one().reviews_remaining == 0
        assert db.query(WritingReviewReservation).filter_by(user_id=user_id, state='pending').count() == 1


def test_concurrent_last_paid_review_is_atomic(pg, monkeypatch):
    from app.models.models import StudyPassGrant, WritingReviewReservation
    factory, service, _ = pg
    user_id, cards = seed(factory)
    with factory() as db:
        service.grant_study_pass(db, user_id, 'one-left', 1)
        db.commit()
    # Force both sessions to observe the same pre-debit grant before continuing.
    selected = threading.Barrier(2)
    original = service._active_pass
    def both_read(*args, **kwargs):
        value = original(*args, **kwargs)
        selected.wait(timeout=5)
        return value
    monkeypatch.setattr(service, '_active_pass', both_read)
    results = reserve_parallel(factory, service, user_id, cards)
    assert sorted(str(r[0]) for r in results) == ['402', 'reserved']
    with factory() as db:
        assert db.query(StudyPassGrant).filter_by(user_id=user_id).one().reviews_remaining == 0
        assert db.query(WritingReviewReservation).filter_by(user_id=user_id, state='pending').count() == 1


@pytest.mark.parametrize('role', ['free', 'vip'])
def test_same_card_concurrent_submission_is_duplicate_protected(pg, role):
    from app.models.models import WritingReviewReservation
    factory, service, _ = pg
    user_id, cards = seed(factory, role=role)
    results = reserve_parallel(factory, service, user_id, [cards[0], cards[0]])
    assert sorted(str(r[0]) for r in results) == ['409', 'reserved']
    with factory() as db:
        assert db.query(WritingReviewReservation).filter_by(user_id=user_id).count() == 1


def test_failure_release_is_idempotent_and_stale_token_cannot_refund_retry(pg):
    from app.models.models import StudyPassGrant
    factory, service, _ = pg
    user_id, cards = seed(factory)
    with factory() as db:
        user = user_for(db, user_id)
        failed = service.reserve_writing_review(db, user, cards[0])
        service.release_writing_review(db, failed)
        service.release_writing_review(db, failed)
        db.expire_all()
        assert db.query(StudyPassGrant).filter_by(user_id=user_id).one().reviews_remaining == 1
        retry = service.reserve_writing_review(db, user, cards[0])
        assert retry.token != failed.token
        service.release_writing_review(db, failed)
        db.expire_all()
        assert db.query(StudyPassGrant).filter_by(user_id=user_id).one().reviews_remaining == 0
        service.finalize_writing_review(db, retry)
        db.commit()
        service.release_writing_review(db, retry)
        db.expire_all()
        assert db.query(StudyPassGrant).filter_by(user_id=user_id).one().reviews_remaining == 0


def test_finalization_rollback_preserves_pending_until_release(pg):
    from app.models.models import WritingReviewReservation, StudyPassGrant
    factory, service, _ = pg
    user_id, cards = seed(factory)
    with factory() as db:
        reservation = service.reserve_writing_review(db, user_for(db, user_id), cards[0])
        service.finalize_writing_review(db, reservation)
        db.rollback()  # simulate result transaction failing before commit
        assert db.query(WritingReviewReservation).get(reservation.id).state == 'pending'
        service.release_writing_review(db, reservation)
        assert db.query(StudyPassGrant).filter_by(user_id=user_id).one().reviews_remaining == 1


def test_cross_user_card_cannot_reserve(pg):
    from fastapi import HTTPException
    from app.models.models import WritingReviewReservation, StudyPassGrant
    factory, service, _ = pg
    owner, cards = seed(factory)
    other, _ = seed(factory)
    with factory() as db:
        with pytest.raises(HTTPException) as error:
            service.reserve_writing_review(db, user_for(db, other), cards[0])
        assert error.value.status_code == 404
        assert db.query(StudyPassGrant).count() == 0
        assert db.query(WritingReviewReservation).count() == 0
