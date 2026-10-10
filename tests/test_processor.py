from dataclasses import replace
from uuid import uuid4

from sqlalchemy import select, update

from app.models import Certificate, CertificateJob, CertificateStatus, JobStatus
from app.services.processor import process_job, recover
from app.services.renderer import render
from tests.factories import JOBS_URL, job_payload, read_job, seed_job, submit


def run(client, job_id, renderer=render):
    pipeline = replace(client.app.state.pipeline, renderer=renderer)
    process_job(job_id, pipeline)


def failing_for(*names):
    def renderer(data):
        if data.recipient_name in names:
            raise RuntimeError("internal detail")
        return render(data)

    return renderer


def counting(counter):
    def renderer(data):
        counter.append(data.recipient_name)
        return render(data)

    return renderer


def failed_items(client, job_id):
    return client.get(f"{JOBS_URL}/{job_id}/certificates", params={"status": "FAILED"}).json()["items"]


def test_one_failure_does_not_block_the_others(make_client):
    client = make_client(failing_for("Bad Name"))
    job_id = submit(client, job_payload("Good One", "Bad Name", "Good Two"))
    job = read_job(client, job_id)
    assert job["status"] == "COMPLETED_WITH_ERRORS"
    assert job["counts"] == {"pending": 0, "succeeded": 2, "failed": 1}
    [item] = failed_items(client, job_id)
    assert item["recipient_name"] == "Bad Name"
    assert item["error"]["code"] == "RENDER_ERROR"
    assert "internal detail" not in item["error"]["message"]


def test_all_items_failing_marks_job_failed(make_client):
    client = make_client(failing_for("A", "B"))
    job_id = submit(client, job_payload("A", "B"))
    assert read_job(client, job_id)["status"] == "FAILED"


def test_unsupported_text_reports_a_clear_error(client):
    job_id = submit(client, job_payload("आशा", "Asha"))
    [item] = failed_items(client, job_id)
    assert item["error"]["code"] == "UNSUPPORTED_TEXT"
    assert "U+" in item["error"]["message"]
    assert read_job(client, job_id)["status"] == "COMPLETED_WITH_ERRORS"


def test_files_are_stored_under_job_directory(client, settings):
    job_id = submit(client, job_payload("Asha"))
    items = client.get(f"{JOBS_URL}/{job_id}/certificates").json()["items"]
    assert (settings.storage_dir / str(job_id) / f"{items[0]['id']}.pdf").is_file()


def test_processing_is_idempotent(client):
    calls = []
    job_id = seed_job(client, job_payload("A", "B", "C"))
    run(client, job_id, counting(calls))
    run(client, job_id, counting(calls))
    assert sorted(calls) == ["A", "B", "C"]
    assert read_job(client, job_id)["status"] == "COMPLETED"


def test_claimed_item_is_skipped_and_job_stays_open(client):
    calls = []
    job_id = seed_job(client, job_payload("A", "B", "C"))
    with client.app.state.session_factory() as db:
        db.execute(
            update(Certificate)
            .where(Certificate.job_id == job_id, Certificate.row_index == 1)
            .values(status=CertificateStatus.PROCESSING)
        )
        db.commit()
    run(client, job_id, counting(calls))
    assert sorted(calls) == ["A", "C"]
    job = read_job(client, job_id)
    assert job["status"] == "PROCESSING"
    assert job["completed_at"] is None


def test_batches_span_the_whole_job(client):
    names = [f"Person {index}" for index in range(5)]
    job_id = seed_job(client, job_payload(*names))
    run(client, job_id)
    job = read_job(client, job_id)
    assert job["counts"] == {"pending": 0, "succeeded": 5, "failed": 0}
    assert job["status"] == "COMPLETED"


def test_storage_failure_fails_only_that_item(client):
    class BrokenStorage:
        def save(self, job_id, certificate_id, data):
            raise OSError("disk full")

    job_id = seed_job(client, job_payload("A"))
    pipeline = replace(client.app.state.pipeline, storage=BrokenStorage())
    process_job(job_id, pipeline)
    [item] = failed_items(client, job_id)
    assert item["error"]["code"] == "STORAGE_ERROR"
    assert read_job(client, job_id)["status"] == "FAILED"


def test_recovery_resets_stuck_items_and_finishes_the_job(client, settings):
    job_id = seed_job(client, job_payload("A", "B"))
    with client.app.state.session_factory() as db:
        db.execute(
            update(Certificate)
            .where(Certificate.job_id == job_id, Certificate.row_index == 0)
            .values(status=CertificateStatus.PROCESSING)
        )
        db.execute(update(CertificateJob).values(status=JobStatus.PROCESSING))
        db.commit()
    assert recover(client.app.state.session_factory) == [job_id]
    with client.app.state.session_factory() as db:
        statuses = set(db.scalars(select(Certificate.status).where(Certificate.job_id == job_id)))
    assert statuses == {CertificateStatus.PENDING}
    run(client, job_id)
    assert read_job(client, job_id)["status"] == "COMPLETED"
    assert len(list(settings.storage_dir.rglob("*.pdf"))) == 2


def test_recovery_ignores_finished_jobs(client):
    submit(client, job_payload())
    assert recover(client.app.state.session_factory) == []


def test_unknown_job_is_ignored(client):
    run(client, uuid4())
