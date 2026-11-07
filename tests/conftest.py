import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DATABASE_URL','sqlite:///./test_autofix.db')
import pytest
from fastapi.testclient import TestClient
from app.database import Base,engine,SessionLocal
from app.main import app
@pytest.fixture(scope='session',autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine); Base.metadata.create_all(bind=engine)
    from app.seed import seed_fixtures
    with SessionLocal() as db: seed_fixtures(db)
    yield
    Base.metadata.drop_all(bind=engine)
@pytest.fixture
def client():
    with TestClient(app) as c: yield c
