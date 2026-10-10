from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import Settings
from app.services.processor import Processor
from app.services.renderer import Renderer
from app.services.storage import Storage


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as db:
        yield db


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_storage(request: Request) -> Storage:
    return request.app.state.storage


def get_renderer(request: Request) -> Renderer:
    return request.app.state.renderer


def get_processor(request: Request) -> Processor:
    return request.app.state.processor


Db = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
StorageDep = Annotated[Storage, Depends(get_storage)]
RendererDep = Annotated[Renderer, Depends(get_renderer)]
ProcessorDep = Annotated[Processor, Depends(get_processor)]
