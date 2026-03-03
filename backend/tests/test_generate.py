import pytest
from fastapi import status

def test_get_daily_reading(client, test_user, auth_token):
    """Test getting daily reading practice"""
    response = client.get(
        "/api/generate/daily-reading",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    # May return existing or generate new
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "practices" in data

def test_generate_reading_requires_auth(client):
    """Test generate reading requires authentication"""
    response = client.post("/api/generate/generate-reading?count=1")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_generate_more_requires_auth(client):
    """Test generate more requires authentication"""
    response = client.post("/api/generate/generate-more?count=1")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED