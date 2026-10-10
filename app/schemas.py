import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.models import Certificate, CertificateJob, CertificateStatus, JobStatus

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class CertificateSpec(BaseModel):
    title: ShortText
    issuer: ShortText
    issue_date: date
    heading: ShortText = "Certificate of Completion"
    intro: ShortText = "This certifies that"
    statement: ShortText = "has successfully completed"


class RecipientIn(BaseModel):
    name: str = Field(default="", max_length=1000)
    email: str = Field(default="", max_length=1000)


class JobCreate(BaseModel):
    certificate: CertificateSpec
    recipients: list[RecipientIn] = Field(min_length=1)


class PreviewRequest(BaseModel):
    certificate: CertificateSpec
    recipient_name: PersonName


class JobCreated(BaseModel):
    id: uuid.UUID
    status: JobStatus
    total: int


class Counts(BaseModel):
    pending: int = 0
    succeeded: int = 0
    failed: int = 0

    @property
    def total(self) -> int:
        return self.pending + self.succeeded + self.failed


class JobOut(BaseModel):
    id: uuid.UUID
    title: str
    issuer: str
    issue_date: date
    heading: str
    intro: str
    statement: str
    status: JobStatus
    total: int
    counts: Counts
    progress_percent: float
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    @classmethod
    def build(cls, job: CertificateJob, counts: Counts) -> "JobOut":
        finished = counts.succeeded + counts.failed
        return cls(
            id=job.id,
            title=job.title,
            issuer=job.issuer,
            issue_date=job.issue_date,
            heading=job.heading,
            intro=job.intro,
            statement=job.statement,
            status=job.status,
            total=counts.total,
            counts=counts,
            progress_percent=round(100 * finished / counts.total, 1),
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )


class JobPage(BaseModel):
    items: list[JobOut]
    page: int
    page_size: int
    total: int


class ErrorInfo(BaseModel):
    code: str
    message: str


class CertificateOut(BaseModel):
    id: uuid.UUID
    row_index: int
    recipient_name: str
    recipient_email: str
    status: CertificateStatus
    error: ErrorInfo | None
    download_url: str | None

    @classmethod
    def build(cls, cert: Certificate, download_url: str | None) -> "CertificateOut":
        error = ErrorInfo(code=cert.error_code, message=cert.error_message) if cert.error_code else None
        return cls(
            id=cert.id,
            row_index=cert.row_index,
            recipient_name=cert.recipient_name,
            recipient_email=cert.recipient_email,
            status=cert.status,
            error=error,
            download_url=download_url,
        )


class CertificatePage(BaseModel):
    items: list[CertificateOut]
    page: int
    page_size: int
    total: int
