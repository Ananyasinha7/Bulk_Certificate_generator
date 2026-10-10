import uuid

from pydantic import BaseModel, EmailStr, ValidationError
from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Certificate, CertificateJob, CertificateStatus, JobStatus
from app.schemas import Counts, JobCreate, PersonName, RecipientIn

COUNT_FIELD = {
    CertificateStatus.PENDING: "pending",
    CertificateStatus.PROCESSING: "pending",
    CertificateStatus.SUCCEEDED: "succeeded",
    CertificateStatus.FAILED: "failed",
}


class RecipientCheck(BaseModel):
    name: PersonName
    email: EmailStr


def build_row(job_id: uuid.UUID, row_index: int, recipient: RecipientIn) -> dict:
    row = {
        "id": uuid.uuid4(),
        "job_id": job_id,
        "row_index": row_index,
        "recipient_name": recipient.name,
        "recipient_email": recipient.email,
        "status": CertificateStatus.PENDING,
        "error_code": None,
        "error_message": None,
    }
    try:
        valid = RecipientCheck(name=recipient.name, email=recipient.email)
    except ValidationError as exc:
        issue = exc.errors()[0]
        field = issue["loc"][0]
        row["status"] = CertificateStatus.FAILED
        row["error_code"] = f"INVALID_{str(field).upper()}"
        row["error_message"] = f"{field}: {issue['msg']}"
        return row
    row["recipient_name"] = valid.name
    row["recipient_email"] = valid.email
    return row


def create_job(db: Session, payload: JobCreate) -> CertificateJob:
    job = CertificateJob(id=uuid.uuid4(), **payload.certificate.model_dump())
    db.add(job)
    db.flush()
    rows = [build_row(job.id, index, recipient) for index, recipient in enumerate(payload.recipients)]
    db.execute(insert(Certificate), rows)
    db.commit()
    return job


def get_job(db: Session, job_id: uuid.UUID) -> CertificateJob:
    job = db.get(CertificateJob, job_id)
    if job is None:
        raise ApiError(404, "NOT_FOUND", "Certificate job not found")
    return job


def get_certificate(db: Session, certificate_id: uuid.UUID) -> Certificate:
    certificate = db.get(Certificate, certificate_id)
    if certificate is None:
        raise ApiError(404, "NOT_FOUND", "Certificate not found")
    return certificate


def counts_for(db: Session, job_ids: list[uuid.UUID]) -> dict[uuid.UUID, Counts]:
    rows = db.execute(
        select(Certificate.job_id, Certificate.status, func.count())
        .where(Certificate.job_id.in_(job_ids))
        .group_by(Certificate.job_id, Certificate.status)
    )
    counts = {job_id: Counts() for job_id in job_ids}
    for job_id, status, number in rows:
        field = COUNT_FIELD[status]
        setattr(counts[job_id], field, getattr(counts[job_id], field) + number)
    return counts


def job_counts(db: Session, job_id: uuid.UUID) -> Counts:
    return counts_for(db, [job_id])[job_id]


def final_status(counts: Counts) -> JobStatus:
    if counts.succeeded == counts.total:
        return JobStatus.COMPLETED
    if counts.failed == counts.total:
        return JobStatus.FAILED
    return JobStatus.COMPLETED_WITH_ERRORS


def list_jobs(db: Session, page: int, page_size: int) -> tuple[list[CertificateJob], int]:
    total = db.scalar(select(func.count()).select_from(CertificateJob))
    query = (
        select(CertificateJob)
        .order_by(CertificateJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(query)), total


def list_certificates(
    db: Session,
    job_id: uuid.UUID,
    status: CertificateStatus | None,
    page: int,
    page_size: int,
) -> tuple[list[Certificate], int]:
    query = select(Certificate).where(Certificate.job_id == job_id)
    if status is not None:
        query = query.where(Certificate.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    page_query = query.order_by(Certificate.row_index).offset((page - 1) * page_size).limit(page_size)
    return list(db.scalars(page_query)), total


def succeeded_files(db: Session, job_id: uuid.UUID) -> list[tuple[str, str]]:
    rows = db.execute(
        select(Certificate.row_index, Certificate.id, Certificate.file_path)
        .where(Certificate.job_id == job_id, Certificate.status == CertificateStatus.SUCCEEDED)
        .order_by(Certificate.row_index)
    )
    return [(f"{row_index}_{cert_id}.pdf", path) for row_index, cert_id, path in rows]
