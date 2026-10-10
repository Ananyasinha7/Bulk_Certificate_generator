from tests.factories import JOBS_URL, job_payload, read_job, submit

DEFAULTS = {
    "heading": "Certificate of Completion",
    "intro": "This certifies that",
    "statement": "has successfully completed",
}


def test_wording_defaults_are_applied(client):
    job = read_job(client, submit(client, job_payload()))
    assert {key: job[key] for key in DEFAULTS} == DEFAULTS


def test_custom_wording_is_stored_and_reported(client):
    payload = job_payload()
    payload["certificate"].update(
        heading="Certificate of Participation", intro="Presented to", statement="for attending"
    )
    job = read_job(client, submit(client, payload))
    assert job["heading"] == "Certificate of Participation"
    assert job["intro"] == "Presented to"
    assert job["statement"] == "for attending"
    assert job["status"] == "COMPLETED"


def test_blank_wording_is_rejected(client):
    payload = job_payload()
    payload["certificate"]["statement"] = "   "
    response = client.post(JOBS_URL, json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
