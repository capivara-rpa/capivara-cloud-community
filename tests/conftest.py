from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path

import pytest

PASTA_TESTE = Path(tempfile.mkdtemp(prefix="capivara-cloud-test-"))
os.environ["CAPIVARA_CLOUD_DATA"] = str(PASTA_TESTE)
os.environ["CAPIVARA_CLOUD_BANCO"] = str(PASTA_TESTE / "cloud.db")
os.environ["CAPIVARA_CLOUD_CHAVE"] = str(PASTA_TESTE / "cloud.key")
os.environ["CAPIVARA_CLOUD_KEY"] = base64.urlsafe_b64encode(os.urandom(32)).decode()
os.environ["CAPIVARA_CLOUD_PERMITIR_REDE_LOCAL"] = "false"
os.environ["CAPIVARA_CLOUD_AGENDADOR"] = "false"


@pytest.fixture(autouse=True)
def banco_iniciado():
    from app import db

    db.iniciar_banco()
    yield


@pytest.fixture
def cliente():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
