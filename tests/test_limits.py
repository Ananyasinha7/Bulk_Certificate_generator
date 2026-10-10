def test_limits_report_the_configured_maximum(client, settings):
    response = client.get("/api/v1/limits")
    assert response.status_code == 200
    assert response.json() == {"max_recipients": settings.max_recipients}


def test_default_limit_is_ten_thousand():
    from app.config import Settings

    assert Settings().max_recipients == 10000
