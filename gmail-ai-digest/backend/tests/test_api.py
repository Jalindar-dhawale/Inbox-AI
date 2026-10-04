from fastapi.testclient import TestClient
from app.main import app

def test_health():
    with TestClient(app) as client: assert client.get("/api/health").json()["status"]=="ok"

def test_dashboard_requires_auth():
    with TestClient(app) as client: assert client.get("/api/emails").status_code==401

def test_demo_login_and_emails():
    with TestClient(app) as client:
        assert client.post("/api/auth/demo").status_code==200
        response=client.get("/api/emails"); assert response.status_code==200; assert response.json()["stats"]["total"]>0
        assert response.json()["ai"]["provider"]=="rules"
        account=client.get("/api/account")
        assert account.status_code==200
        assert account.json()["user"]["provider"]=="demo"

def test_unknown_provider():
    with TestClient(app) as client: assert client.get("/api/auth/unknown",follow_redirects=False).status_code==404
