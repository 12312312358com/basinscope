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


def test_english_language_assets_are_available():
    client = app.test_client()
    response = client.get("/static/js/basinscope-i18n.js")
    assert response.status_code == 200
    assert b"langSwitch" in response.data
    assert b"SignalTrace - Multi-source Public-Opinion Analytics" in response.data
