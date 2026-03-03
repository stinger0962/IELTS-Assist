import pytest
from fastapi import status

def test_root(client):
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert "message" in response.json()

def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "healthy"

def test_register(client):
    """Test user registration"""
    response = client.post(
        "/api/auth/register",
        json={
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "password123",
            "full_name": "New User"
        }
    )
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
    assert response.json()["email"] == "newuser@example.com"

def test_register_duplicate_email(client, test_user):
    """Test duplicate email registration fails"""
    response = client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "username": "anotheruser",
            "password": "password123"
        }
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

def test_login_success(client, test_user):
    """Test successful login"""
    response = client.post(
        "/api/auth/login",
        data={"username": "test@example.com", "password": "test123456"}
    )
    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

def test_login_wrong_password(client, test_user):
    """Test login with wrong password fails"""
    response = client.post(
        "/api/auth/login",
        data={"username": "test@example.com", "password": "wrongpassword"}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_login_nonexistent_user(client):
    """Test login with nonexistent user fails"""
    response = client.post(
        "/api/auth/login",
        data={"username": "nonexistent@example.com", "password": "password"}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_get_current_user(client, test_user, auth_token):
    """Test get current user"""
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["email"] == "test@example.com"

def test_get_current_user_no_token(client):
    """Test get current user without token fails"""
    response = client.get("/api/auth/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED