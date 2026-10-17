

def test_health_check_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_health_check_returns_correct_fields(client):
    response = client.get("/health")
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert data["status"] == "ok"


def test_health_check_returns_ok_status(client):
    response = client.get("/health")
    assert response.json()["status"] == "ok"