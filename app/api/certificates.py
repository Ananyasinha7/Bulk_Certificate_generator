from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.deps import Db, StorageDep
from app.errors import ApiError
from app.models import CertificateStatus
from app.services import jobs

router = APIRouter(prefix="/certificates", tags=["certificates"])


@router.get("/{certificate_id}/download", name="download_certificate")
def download_certificate(certificate_id: UUID, db: Db, storage: StorageDep) -> FileResponse:
    certificate = jobs.get_certificate(db, certificate_id)
    if certificate.status != CertificateStatus.SUCCEEDED:
        raise ApiError(409, "NOT_GENERATED", "Certificate has not been generated")
    return FileResponse(
        storage.path(certificate.file_path),
        media_type="application/pdf",
        filename=f"{certificate.id}.pdf",
    )
