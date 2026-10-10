from uuid import UUID

from fastapi import APIRouter, Response

from app.deps import RendererDep
from app.errors import ApiError
from app.schemas import PreviewRequest
from app.services.renderer import CertificateData, attempt

router = APIRouter(prefix="/certificate-previews", tags=["certificate-previews"])

SAMPLE_ID = UUID(int=0)


@router.post("", response_class=Response, responses={200: {"content": {"application/pdf": {}}}})
def preview_certificate(payload: PreviewRequest, renderer: RendererDep) -> Response:
    spec = payload.certificate
    data = CertificateData(
        certificate_id=SAMPLE_ID,
        recipient_name=payload.recipient_name,
        title=spec.title,
        issuer=spec.issuer,
        issue_date=spec.issue_date,
        heading=spec.heading,
        intro=spec.intro,
        statement=spec.statement,
    )
    outcome = attempt(renderer, data)
    if outcome.pdf is None:
        raise ApiError(422 if outcome.code == "UNSUPPORTED_TEXT" else 500, outcome.code, outcome.message)
    return Response(
        outcome.pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="preview.pdf"'},
    )
