import os
import tempfile
os.environ['PDF_STORAGE']=tempfile.mkdtemp(prefix='folio-tests-')
os.environ['PDF_TIMEOUT_SECONDS']='60'
import pytest
from fastapi.testclient import TestClient
from app.main import app
@pytest.fixture(scope='session')
def client():
    with TestClient(app) as test_client: yield test_client
