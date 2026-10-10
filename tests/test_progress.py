
from app.models import CertificateJob
from app.services.processor import process_batch
from tests.factories import job_payload, pending_ids, read_job, seed_job


def test_progress_advances_one_item_at_a_time(client):
    pipeline = client.app.state.pipeline
    job_id = seed_job(client, job_payload("A", "B", "C", "D"))
    assert read_job(client, job_id)["progress_percent"] == 0.0
    for done, certificate_id in enumerate(pending_ids(client, job_id), start=1):
        with pipeline.session_factory() as db:
            process_batch(db, db.get(CertificateJob, job_id), [certificate_id], pipeline)
        job = read_job(client, job_id)
        assert job["counts"] == {"pending": 4 - done, "succeeded": done, "failed": 0}
        assert job["progress_percent"] == done * 25.0
        assert job["total"] == 4


def test_invalid_rows_count_towards_progress(client):
    recipients = [
        {"name": "Asha", "email": "asha@example.com"},
        {"name": "", "email": "nobody@example.com"},
    ]
    job = read_job(client, seed_job(client, job_payload(recipients=recipients)))
    assert job["counts"] == {"pending": 1, "succeeded": 0, "failed": 1}
    assert job["progress_percent"] == 50.0


def test_status_response_shape(client):
    job = read_job(client, seed_job(client, job_payload()))
    assert set(job) == {
        "id",
        "title",
        "issuer",
        "issue_date",
        "heading",
        "intro",
        "statement",
        "status",
        "total",
        "counts",
        "progress_percent",
        "created_at",
        "started_at",
        "completed_at",
    }
