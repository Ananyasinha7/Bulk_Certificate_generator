from fastapi import APIRouter
from pydantic import BaseModel

from app.deps import SettingsDep

router = APIRouter(prefix="/limits", tags=["limits"])


class Limits(BaseModel):
    max_recipients: int


@router.get("", response_model=Limits)
def read_limits(settings: SettingsDep) -> Limits:
    return Limits(max_recipients=settings.max_recipients)
