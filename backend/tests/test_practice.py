import pytest
from fastapi import status

def test_get_reading_practice(client):
    """Test getting reading practice"""
    response = client.get("/api/practice/reading")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    # Response is a list of practice items
    assert isinstance(data, list)

def test_get_listening_practice(client):
    """Test getting listening practice"""
    response = client.get("/api/practice/listening")
    assert response.status_code == status.HTTP_200_OK

def test_get_writing_practice(client):
    """Test getting writing practice"""
    response = client.get("/api/practice/writing")
    assert response.status_code == status.HTTP_200_OK

def test_get_speaking_practice(client):
    """Test getting speaking practice"""
    response = client.get("/api/practice/speaking")
    assert response.status_code == status.HTTP_200_OK

def test_submit_practice(client, test_user, auth_token):
    """Test submitting practice results"""
    response = client.post(
        "/api/practice/submit",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "skill": "reading",
            "exercise_id": "test-001",
            "score": 7.5,
            "total_questions": 10,
            "correct_answers": 8,
            "time_taken_seconds": 1800
        }
    )
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]

def test_get_practice_history(client, test_user, auth_token):
    """Test getting practice history"""
    response = client.get(
        "/api/practice/history?skill=reading",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)