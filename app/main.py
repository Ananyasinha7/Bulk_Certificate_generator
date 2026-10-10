from concurrent.futures import Executor
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import sessionmaker

from app.api import certificates, jobs, limits, previews
from app.config import Settings
from app.db import create_db_engine
from app.errors import register_error_handlers
from app.services.processor import Pipeline, create_executor, process_job, resume_unfinished
from app.services.renderer import Renderer, render
from app.services.storage import Storage

API_PREFIX = "/api/v1"
STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(
    settings: Settings | None = None,
    renderer: Renderer = render,
    executor: Executor | None = None,
) -> FastAPI:
    settings = settings or Settings()
    engine = create_db_engine(settings.database_url)
    session_factory = sessionmaker(engine, expire_on_commit=False)
    storage = Storage(settings.storage_dir)
    executor = executor or create_executor(settings.render_workers)
    pipeline = Pipeline(session_factory, storage, renderer, executor, settings.batch_size)
    processor = partial(process_job, pipeline=pipeline)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        resume_unfinished(session_factory, processor)
        yield
        executor.shutdown(wait=False, cancel_futures=True)
        engine.dispose()

    app = FastAPI(title="Bulk Certificate Generator", lifespan=lifespan)
    app.state.settings = settings
    app.state.session_factory = session_factory
    app.state.storage = storage
    app.state.renderer = renderer
    app.state.pipeline = pipeline
    app.state.processor = processor
    register_error_handlers(app)
    app.include_router(jobs.router, prefix=API_PREFIX)
    app.include_router(certificates.router, prefix=API_PREFIX)
    app.include_router(previews.router, prefix=API_PREFIX)
    app.include_router(limits.router, prefix=API_PREFIX)
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
    return app
