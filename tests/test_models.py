import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Certificate, CertificateJob, JobStatus
from tests.factories import job_payload, seed_job


def test_job_round_trip(client):
    job_id = seed_job(client, job_payload())
    with client.app.state.session_factory() as db:
        job = db.get(CertificateJob, job_id)
        assert job.status == JobStatus.PENDING
        assert job.created_at.tzinfo is not None
        assert job.title == "Python Bootcamp"


def test_row_index_is_unique_per_job(client):
    job_id = seed_job(client, job_payload())
    with client.app.state.session_factory() as db:
        db.add(
            Certificate(job_id=job_id, row_index=0, recipient_name="Dup", recipient_email="d@example.com")
        )
        with pytest.raises(IntegrityError):
            db.commit()
