from uuid import UUID

from sqlalchemy import select

from app.models import Certificate, CertificateStatus
from app.schemas import JobCreate
from app.services.jobs import create_job

JOBS_URL = "/api/v1/certificate-jobs"
CERTIFICATES_URL = "/api/v1/certificates"
DEFAULT_NAMES = ("Asha Verma", "Rohan Mehta")


def job_payload(*names, recipients=None):
    if recipients is None:
        recipients = [
            {"name": name, "email": f"user{index}@example.com"}
            for index, name in enumerate(names or DEFAULT_NAMES)
        ]
    return {
        "certificate": {"title": "Python Bootcamp", "issuer": "Acme Academy", "issue_date": "2026-10-01"},
        "recipients": recipients,
    }


def seed_job(client, payload) -> UUID:
    with client.app.state.session_factory() as db:
        return create_job(db, JobCreate.model_validate(payload)).id


def pending_ids(client, job_id) -> list[UUID]:
    with client.app.state.session_factory() as db:
        return list(
            db.scalars(
                select(Certificate.id)
                .where(Certificate.job_id == job_id, Certificate.status == CertificateStatus.PENDING)
                .order_by(Certificate.row_index)
            )
        )


def submit(client, payload) -> UUID:
    response = client.post(JOBS_URL, json=payload)
    assert response.status_code == 202
    return UUID(response.json()["id"])


def read_job(client, job_id) -> dict:
    return client.get(f"{JOBS_URL}/{job_id}").json()
