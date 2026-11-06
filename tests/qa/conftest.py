import os, sys
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
for _p in (_ROOT, os.path.join(_ROOT, "sdk")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("DRIFTLINE_DB", str(tmp_path / "qa.db"))
    monkeypatch.setenv("DRIFTLINE_ADMIN_KEY", "dl_qa_admin")
    from server import db
    from server import app as appmod

    importlib.reload(db)
    importlib.reload(appmod)
    db.init()
    db.create_project("qa", "dl_qa_test")
    with TestClient(appmod.app) as test_client:
        test_client.headers.update({"X-Driftline-Key": "dl_qa_test"})
        yield test_client

