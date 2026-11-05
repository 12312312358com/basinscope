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
    assert b"SOPRAS - Multi-source Public-Opinion Analytics" in response.data


def test_question_answering_endpoint_is_disabled():
    client = app.test_client()
    assert client.get("/page/chat").status_code == 404
    assert client.post("/page/chat", json={"message": "test"}).status_code == 404


def test_english_ui_asset_is_available():
    client = app.test_client()
    response = client.get("/static/js/signaltrace-ui-en.js")
    assert response.status_code == 200
    assert b"17 views" in response.data
