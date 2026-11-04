from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from acnopviz.api import create_app
from acnopviz.config import Settings
from acnopviz.synthetic import generate_dataset


@pytest.fixture()
def dataset():
    return generate_dataset(seed=20261104, as_of="2026-10-31")


@pytest.fixture()
def settings(tmp_path):
    return Settings(
        db_path=tmp_path / "test.db", seed=20261104, as_of="2026-10-31", bootstrap_paths=300
    )


@pytest.fixture()
def client(settings):
    app = create_app(settings)
    with TestClient(app) as c:
        yield c
