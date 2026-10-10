import pytest

from tests.factories import JOBS_URL, job_payload, read_job, submit

VALID = {"name": "Asha Verma", "email": "asha@example.com"}
CERTIFICATE = {"title": "Python Bootcamp", "issuer": "Acme Academy", "issue_date": "2026-10-01"}


@pytest.mark.parametrize(
    ("recipient", "code"),
    [
        ({"name": "", "email": "a@example.com"}, "INVALID_NAME"),
        ({"name": "   ", "email": "a@example.com"}, "INVALID_NAME"),
        ({"name": "x" * 101, "email": "a@example.com"}, "INVALID_NAME"),
        ({"email": "a@example.com"}, "INVALID_NAME"),
        ({"name": "Asha", "email": "not-an-email"}, "INVALID_EMAIL"),
        ({"name": "Asha"}, "INVALID_EMAIL"),
    ],
)
def test_invalid_recipient_is_recorded_as_failed(client, recipient, code):
    job_id = submit(client, job_payload(recipients=[recipient]))
    item = client.get(f"{JOBS_URL}/{job_id}/certificates").json()["items"][0]
    assert item["status"] == "FAILED"
    assert item["error"]["code"] == code
    assert item["download_url"] is None
    assert read_job(client, job_id)["status"] == "FAILED"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"recipients": [VALID]},
        {"certificate": CERTIFICATE},
        {"certificate": CERTIFICATE, "recipients": []},
        {"certificate": CERTIFICATE, "recipients": "nobody"},
        {"certificate": CERTIFICATE, "recipients": [{"name": 7, "email": "a@example.com"}]},
        {"certificate": {**CERTIFICATE, "title": ""}, "recipients": [VALID]},
        {"certificate": {**CERTIFICATE, "issue_date": "yesterday"}, "recipients": [VALID]},
    ],
)
def test_malformed_request_is_rejected(client, payload):
    response = client.post(JOBS_URL, json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_too_many_recipients_is_rejected(client):
    limit = client.app.state.settings.max_recipients
    names = [f"Person {index}" for index in range(limit + 1)]
    response = client.post(JOBS_URL, json=job_payload(*names))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_limit_is_inclusive(client):
    limit = client.app.state.settings.max_recipients
    names = [f"Person {index}" for index in range(limit)]
    assert client.post(JOBS_URL, json=job_payload(*names)).status_code == 202
