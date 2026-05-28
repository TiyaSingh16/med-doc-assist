from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_register_new_user():
    response = client.post("/auth/register", json={
        "email": "newuser@example.com",
        "password": "password123"
    })
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["email"] == "newuser@example.com"


def test_register_duplicate_email():
    client.post("/auth/register", json={
        "email": "duplicate@example.com",
        "password": "password123"
    })
    response = client.post("/auth/register", json={
        "email": "duplicate@example.com",
        "password": "password123"
    })
    assert response.status_code == 400


def test_login_valid_credentials():
    client.post("/auth/register", json={
        "email": "logintest@example.com",
        "password": "password123"
    })
    response = client.post("/auth/login", json={
        "email": "logintest@example.com",
        "password": "password123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password():
    response = client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "wrongpassword"
    })
    assert response.status_code == 401