import pytest


@pytest.mark.parametrize(
    ("path", "content_type"),
    [
        ("/", "text/html"),
        ("/styles.css", "text/css"),
        ("/js/main.js", "text/javascript"),
        ("/js/views/job.js", "text/javascript"),
        ("/js/views/new-job.js", "text/javascript"),
        ("/js/views/jobs.js", "text/javascript"),
        ("/js/presets.js", "text/javascript"),
    ],
)
def test_frontend_assets_are_served(client, path, content_type):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type)


def test_index_loads_the_app_module(client):
    assert '/js/main.js' in client.get("/").text


def test_api_still_wins_over_static_files(client):
    response = client.get("/api/v1/certificate-jobs/not-a-uuid")
    assert response.status_code == 422

