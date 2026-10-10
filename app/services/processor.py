import logging
import uuid
from collections.abc import Callable
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from multiprocessing import get_context
from threading import Thread

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.db import utcnow
from app.models import Certificate, CertificateJob, CertificateStatus, JobStatus
from app.services.jobs import final_status, job_counts
from app.services.renderer import CertificateData, Renderer, RenderOutcome, attempt
from app.services.storage import Storage

logger = logging.getLogger(__name__)

Processor = Callable[[uuid.UUID], None]
CHUNKS_PER_BATCH = 8


@dataclass(frozen=True)
class Pipeline:
    session_factory: sessionmaker[Session]
    storage: Storage
    renderer: Renderer
    executor: Executor
    batch_size: int = 50


def create_executor(workers: int) -> Executor:
    if workers > 1:
        return ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn"))
    return ThreadPoolExecutor(max_workers=1)


def claim(db: Session, certificate_ids: list[uuid.UUID]) -> list[uuid.UUID]:
    claimed = db.scalars(
        update(Certificate)
        .where(Certificate.id.in_(certificate_ids), Certificate.status == CertificateStatus.PENDING)
        .values(status=CertificateStatus.PROCESSING)
        .returning(Certificate.id)
        .execution_options(synchronize_session=False)
    ).all()
    db.commit()
    return list(claimed)


def record(certificate: Certificate, job_id: uuid.UUID, outcome: RenderOutcome, storage: Storage) -> None:
    if outcome.pdf is not None:
        try:
            certificate.file_path = storage.save(job_id, certificate.id, outcome.pdf)
            certificate.status = CertificateStatus.SUCCEEDED
            certificate.generated_at = utcnow()
            return
        except OSError:
            logger.exception("Certificate could not be stored")
            outcome = RenderOutcome(code="STORAGE_ERROR", message="Certificate could not be saved")
    certificate.status = CertificateStatus.FAILED
    certificate.error_code = outcome.code
    certificate.error_message = outcome.message


def process_batch(
    db: Session,
    job: CertificateJob,
    certificate_ids: list[uuid.UUID],
    pipeline: Pipeline,
) -> None:
    claimed = claim(db, certificate_ids)
    if not claimed:
        return
    certificates = list(
        db.scalars(select(Certificate).where(Certificate.id.in_(claimed)).order_by(Certificate.row_index))
    )
    requests = [
        CertificateData(
            certificate_id=certificate.id,
            recipient_name=certificate.recipient_name,
            title=job.title,
            issuer=job.issuer,
            issue_date=job.issue_date,
            heading=job.heading,
            intro=job.intro,
            statement=job.statement,
        )
        for certificate in certificates
    ]
    outcomes = pipeline.executor.map(
        partial(attempt, pipeline.renderer),
        requests,
        chunksize=max(1, len(requests) // CHUNKS_PER_BATCH),
    )
    for certificate, outcome in zip(certificates, outcomes):
        record(certificate, job.id, outcome, pipeline.storage)
    db.commit()


def finish_job(db: Session, job: CertificateJob) -> None:
    counts = job_counts(db, job.id)
    if counts.pending:
        return
    job.status = final_status(counts)
    job.completed_at = utcnow()
    db.commit()


def process_job(job_id: uuid.UUID, pipeline: Pipeline) -> None:
    with pipeline.session_factory() as db:
        job = db.get(CertificateJob, job_id)
        if job is None:
            return
        job.status = JobStatus.PROCESSING
        job.started_at = job.started_at or utcnow()
        db.commit()
        pending = list(
            db.scalars(
                select(Certificate.id)
                .where(Certificate.job_id == job_id, Certificate.status == CertificateStatus.PENDING)
                .order_by(Certificate.row_index)
            )
        )
        for start in range(0, len(pending), pipeline.batch_size):
            process_batch(db, job, pending[start : start + pipeline.batch_size], pipeline)
        finish_job(db, job)


def recover(session_factory: sessionmaker[Session]) -> list[uuid.UUID]:
    with session_factory() as db:
        db.execute(
            update(Certificate)
            .where(Certificate.status == CertificateStatus.PROCESSING)
            .values(status=CertificateStatus.PENDING)
        )
        job_ids = list(
            db.scalars(
                select(CertificateJob.id)
                .where(CertificateJob.status.in_([JobStatus.PENDING, JobStatus.PROCESSING]))
                .order_by(CertificateJob.created_at)
            )
        )
        db.commit()
    return job_ids


def resume_unfinished(session_factory: sessionmaker[Session], processor: Processor) -> None:
    job_ids = recover(session_factory)
    if not job_ids:
        return

    def run() -> None:
        for job_id in job_ids:
            processor(job_id)

    Thread(target=run, daemon=True).start()
