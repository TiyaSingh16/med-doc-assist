

def get_auth_token(client):
    client.post("/auth/register", json={
        "email": "doctest@example.com",
        "password": "password123"
    })
    response = client.post("/auth/login", json={
        "email": "doctest@example.com",
        "password": "password123"
    })
    return response.json()["access_token"]


def test_upload_non_pdf_rejected(client):
    token = get_auth_token(client)
    response = client.post(
        "/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("test.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 400


def test_upload_without_auth_rejected(client):
    response = client.post(
        "/documents/upload",
        files={"file": ("test.pdf", b"fake pdf content", "application/pdf")},
    )
    assert response.status_code == 401


def test_get_documents_requires_auth(client):
    response = client.get("/documents/")
    assert response.status_code == 401