from tests.factories import JOBS_URL, job_payload, read_job, submit


def test_create_returns_accepted_with_location(client):
    response = client.post(JOBS_URL, json=job_payload())
    body = response.json()
    assert response.status_code == 202
    assert body["total"] == 2
    assert body["status"] == "PENDING"
    assert response.headers["location"].endswith(f"{JOBS_URL}/{body['id']}")


def test_job_runs_to_completion(client):
    job = read_job(client, submit(client, job_payload()))
    assert job["status"] == "COMPLETED"
    assert job["counts"] == {"pending": 0, "succeeded": 2, "failed": 0}
    assert job["progress_percent"] == 100.0
    assert job["started_at"] is not None
    assert job["completed_at"] is not None


def test_batch_with_one_bad_row_writes_only_valid_pdfs(client, settings):
    good = {"name": "Asha Verma", "email": "asha@example.com"}
    bad = {"name": "", "email": "nobody@example.com"}
    job = read_job(client, submit(client, job_payload(recipients=[good, bad, good])))
    assert job["status"] == "COMPLETED_WITH_ERRORS"
    assert job["counts"] == {"pending": 0, "succeeded": 2, "failed": 1}
    assert len(list(settings.storage_dir.rglob("*.pdf"))) == 2


def test_duplicate_recipients_are_not_deduplicated(client):
    same = {"name": "Asha Verma", "email": "asha@example.com"}
    job = read_job(client, submit(client, job_payload(recipients=[same, same])))
    assert job["counts"]["succeeded"] == 2


def test_unknown_job_is_not_found(client):
    response = client.get(f"{JOBS_URL}/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
