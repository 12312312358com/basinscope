from app import app


def test_health_endpoint():
    client = app.test_client()
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "scope": "yellow-river"}


def test_index_redirects_to_dashboard():
    client = app.test_client()
    response = client.get("/")
    assert response.status_code in (301, 302, 308)
    assert "/page/dashboard" in response.headers["Location"]
