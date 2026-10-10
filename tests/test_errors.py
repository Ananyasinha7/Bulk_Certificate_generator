import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import create_app
from tests.factories import CERTIFICATES_URL, JOBS_URL, job_payload, seed_job

UNKNOWN = "00000000-0000-0000-0000-000000000000"


@pytest.mark.parametrize(
    ("method", "path", "status", "code"),
    [
        ("get", f"{JOBS_URL}/not-a-uuid", 422, "VALIDATION_ERROR"),
        ("get", f"{CERTIFICATES_URL}/not-a-uuid/download", 422, "VALIDATION_ERROR"),
        ("get", f"{JOBS_URL}/{UNKNOWN}", 404, "NOT_FOUND"),
        ("get", f"{CERTIFICATES_URL}/{UNKNOWN}/download", 404, "NOT_FOUND"),
        ("get", "/api/v1/nowhere", 404, "NOT_FOUND"),
        ("delete", JOBS_URL, 405, "METHOD_NOT_ALLOWED"),
        ("post", JOBS_URL, 422, "VALIDATION_ERROR"),
    ],
)
def test_error_paths_use_the_uniform_envelope(client, method, path, status, code):
    response = getattr(client, method)(path)
    assert response.status_code == status
    error = response.json()["error"]
    assert error["code"] == code
    assert isinstance(error["message"], str)
    assert isinstance(error["details"], dict)


def test_conflict_uses_the_uniform_envelope(client):
    job_id = seed_job(client, job_payload())
    response = client.get(f"{JOBS_URL}/{job_id}/download")
    assert response.status_code == 409
    assert set(response.json()["error"]) == {"code", "message", "details"}


def test_unexpected_error_does_not_leak_details(settings):
    app = create_app(settings)
    app.router.routes.insert(0, APIRoute("/boom", lambda: 1 / 0))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")
    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "INTERNAL_ERROR", "message": "Internal server error", "details": {}}
    }
