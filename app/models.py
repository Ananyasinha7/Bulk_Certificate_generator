import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UTCDateTime, utcnow


class JobStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"


ACTIVE_JOB_STATUSES = frozenset({JobStatus.PENDING, JobStatus.PROCESSING})


class CertificateStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class CertificateJob(Base):
    __tablename__ = "certificate_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str]
    issuer: Mapped[str]
    issue_date: Mapped[date]
    heading: Mapped[str]
    intro: Mapped[str]
    statement: Mapped[str]
    status: Mapped[JobStatus] = mapped_column(default=JobStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Certificate(Base):
    __tablename__ = "certificates"
    __table_args__ = (
        UniqueConstraint("job_id", "row_index"),
        Index("ix_certificates_job_status", "job_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("certificate_jobs.id"))
    row_index: Mapped[int]
    recipient_name: Mapped[str]
    recipient_email: Mapped[str]
    status: Mapped[CertificateStatus] = mapped_column(default=CertificateStatus.PENDING)
    error_code: Mapped[str | None]
    error_message: Mapped[str | None]
    file_path: Mapped[str | None]
    generated_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
