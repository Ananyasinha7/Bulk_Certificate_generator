from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Query, Request, Response
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.deps import Db, ProcessorDep, SettingsDep, StorageDep
from app.errors import ApiError
from app.models import ACTIVE_JOB_STATUSES, Certificate, CertificateStatus
from app.schemas import CertificateOut, CertificatePage, JobCreate, JobCreated, JobOut, JobPage
from app.services import jobs

router = APIRouter(prefix="/certificate-jobs", tags=["certificate-jobs"])


def certificate_out(certificate: Certificate, request: Request) -> CertificateOut:
    url = None
    if certificate.status == CertificateStatus.SUCCEEDED:
        url = str(request.url_for("download_certificate", certificate_id=certificate.id))
    return CertificateOut.build(certificate, url)


@router.post("", status_code=202, response_model=JobCreated)
def create_job(
    payload: JobCreate,
    request: Request,
    response: Response,
    background: BackgroundTasks,
    db: Db,
    settings: SettingsDep,
    processor: ProcessorDep,
) -> JobCreated:
    if len(payload.recipients) > settings.max_recipients:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            f"A request may contain at most {settings.max_recipients} recipients",
        )
    job = jobs.create_job(db, payload)
    background.add_task(processor, job.id)
    response.headers["Location"] = str(request.url_for("read_job", job_id=job.id))
    return JobCreated(id=job.id, status=job.status, total=len(payload.recipients))


@router.get("", response_model=JobPage)
def list_jobs(
    db: Db,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> JobPage:
    items, total = jobs.list_jobs(db, page, page_size)
    counts = jobs.counts_for(db, [job.id for job in items])
    return JobPage(
        items=[JobOut.build(job, counts[job.id]) for job in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{job_id}", response_model=JobOut)
def read_job(job_id: UUID, db: Db) -> JobOut:
    job = jobs.get_job(db, job_id)
    return JobOut.build(job, jobs.job_counts(db, job_id))


@router.get("/{job_id}/certificates", response_model=CertificatePage)
def list_job_certificates(
    job_id: UUID,
    request: Request,
    db: Db,
    status: CertificateStatus | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CertificatePage:
    jobs.get_job(db, job_id)
    items, total = jobs.list_certificates(db, job_id, status, page, page_size)
    return CertificatePage(
        items=[certificate_out(item, request) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{job_id}/download")
def download_job(job_id: UUID, db: Db, storage: StorageDep) -> FileResponse:
    job = jobs.get_job(db, job_id)
    if job.status in ACTIVE_JOB_STATUSES:
        raise ApiError(409, "JOB_NOT_FINISHED", "Certificate job is still processing")
    archive = storage.archive(jobs.succeeded_files(db, job_id))
    return FileResponse(
        archive,
        media_type="application/zip",
        filename=f"certificates-{job_id}.zip",
        background=BackgroundTask(archive.unlink),
    )
