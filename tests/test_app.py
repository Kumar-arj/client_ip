from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    """Test / endpoint returns IP"""
    response = client.get("/")
    assert response.status_code == 200
    assert "ip" in response.json()
    assert response.json()["ip"] != ""


def test_health_endpoint():
    """Test /health endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_endpoint():
    """Test /ready endpoint"""
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_ip_with_x_forwarded_for():
    """Test X-Forwarded-For header handling"""
    response = client.get("/", headers={"x-forwarded-for": "192.168.1.100"})
    assert response.status_code == 200
    assert response.json()["ip"] == "192.168.1.100"


def test_ip_with_multiple_x_forwarded_for():
    """Test X-Forwarded-For with multiple IPs (takes first)"""
    response = client.get("/", headers={"x-forwarded-for": "192.168.1.100, 10.0.0.1"})
    assert response.status_code == 200
    assert response.json()["ip"] == "192.168.1.100"
