"""
Shared pytest configuration for the PlantGuard backend test suite.

Per the Software Test Plan (Section 2.2, Out of Scope): AI model prediction
accuracy is owned by the AI/Model Optimization leads and is explicitly out of
scope for this backend test effort. torch/torchvision/timm/huggingface_hub are
therefore stubbed out here rather than installed, so tests exercise the real
business logic (auth, validation, severity, treatment lookup, admin hierarchy)
without requiring a multi-gigabyte ML dependency stack or network access to
Hugging Face Hub.

The `supabase` client is likewise stubbed since profile-photo storage is not
part of this test scope, and the real client would otherwise try to validate
a Supabase project URL at import time (app/services/storage.py instantiates
the client at module load, not lazily -- see defect log).
"""
import sys
import types
from unittest.mock import MagicMock

# ---- Stub torch ----
torch_stub = types.ModuleType("torch")
torch_stub.cuda = types.SimpleNamespace(is_available=lambda: False)
torch_stub.no_grad = MagicMock()
torch_stub.softmax = MagicMock()
torch_stub.load = MagicMock()
sys.modules["torch"] = torch_stub

torchvision_stub = types.ModuleType("torchvision")
transforms_stub = types.ModuleType("torchvision.transforms")
transforms_stub.Compose = MagicMock()
transforms_stub.Resize = MagicMock()
transforms_stub.CenterCrop = MagicMock()
transforms_stub.ToTensor = MagicMock()
transforms_stub.Normalize = MagicMock()
torchvision_stub.transforms = transforms_stub
sys.modules["torchvision"] = torchvision_stub
sys.modules["torchvision.transforms"] = transforms_stub

timm_stub = types.ModuleType("timm")
timm_stub.create_model = MagicMock()
sys.modules["timm"] = timm_stub

hf_stub = types.ModuleType("huggingface_hub")
hf_stub.hf_hub_download = MagicMock(return_value="./fake_model.pth")
sys.modules["huggingface_hub"] = hf_stub

supabase_stub = types.ModuleType("supabase")
supabase_stub.create_client = MagicMock(return_value=MagicMock())
supabase_stub.Client = MagicMock
sys.modules["supabase"] = supabase_stub

import pytest
import pytest_asyncio
import asyncio
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.db.models import Base
from app.core.config import get_settings

settings = get_settings()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Creates all tables fresh before each test function, drops them after."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    session_factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_engine):
    """An httpx AsyncClient wired to the real FastAPI app, with the DB
    dependency overridden to use our test engine/schema."""
    from app.main import app
    from app.db.base import get_db
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


def unique_email():
    return f"test_{uuid.uuid4().hex[:10]}@test.com"
