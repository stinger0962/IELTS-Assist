import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.database import get_db
from app.models.models import Base, User
import bcrypt

TEST_DATABASE_URL = "sqlite:///test.db"

@pytest.fixture(scope="function")
def test_db():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(test_db):
    def override_get_db():
        try:
            yield test_db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def test_user(test_db):
    hashed_password = bcrypt.hashpw("test123456".encode(), bcrypt.gensalt()).decode()
    user = User(
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        hashed_password=hashed_password
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user

@pytest.fixture
def auth_token(client, test_user):
    response = client.post(
        "/api/auth/login",
        data={"username": "test@example.com", "password": "test123456"}
    )
    return response.json()["access_token"]