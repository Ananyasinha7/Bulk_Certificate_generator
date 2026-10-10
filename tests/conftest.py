from contextlib import ExitStack

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.renderer import render


@pytest.fixture
def settings(tmp_path):
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        storage_dir=tmp_path / "storage",
        max_recipients=5,
        render_workers=1,
        batch_size=2,
    )


@pytest.fixture
def make_client(settings):
    with ExitStack() as stack:

        def factory(renderer=render, executor=None):
            return stack.enter_context(TestClient(create_app(settings, renderer, executor)))

        yield factory


@pytest.fixture
def client(make_client):
    return make_client()
