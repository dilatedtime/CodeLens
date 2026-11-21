import os
import tempfile
from pathlib import Path
import pytest

_test_dir = tempfile.TemporaryDirectory(prefix='codelens-tests-')
os.environ['DATABASE_URL'] = 'sqlite:///' + (Path(_test_dir.name) / 'test.db').as_posix()
os.environ['QUEUE_MODE'] = 'local'

from app.db import Base, engine


@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    engine.dispose()


@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient
    import app.main as main
    monkeypatch.setattr(main, 'enqueue', lambda _: None)
    with TestClient(main.app) as client:
        yield client
