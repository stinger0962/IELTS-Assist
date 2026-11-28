"""Run the staging binding check against the existing disposable CI database."""

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from test_study_pass_postgres import URL, pg

pytestmark = pytest.mark.skipif(not URL, reason="disposable PostgreSQL URL not provided")


def test_staging_guard_accepts_real_disposable_postgresql_binding(pg):
    from app.staging import validate_binding

    checked_sessions, _, _ = pg
    url = checked_sessions.kw["bind"].url.update_query_dict({"connect_timeout": "5"})
    engine = create_engine(url)
    try:
        validate_binding(
            SimpleNamespace(engine=engine, SessionLocal=sessionmaker(bind=engine)),
            (url.host, url.port or 5432, "test_db", "test_user"),
            text,
        )
    finally:
        engine.dispose()
