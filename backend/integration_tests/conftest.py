"""Explicit local PostgreSQL tests; never reset or delete the public schema."""

import os
from uuid import uuid4

import pytest
from sqlalchemy.schema import CreateSchema, DropSchema

from app.cache import make_redis
from app.config import get_settings
from app.db import make_engine
from app.models import Base
from app.repository import SearchRepository


@pytest.fixture
async def storage():
    engine = make_engine(
        os.environ.get("LUMEN_TEST_DATABASE_URL") or get_settings().database_url
    )
    schema = "lumen_test_" + uuid4().hex
    assert schema.startswith("lumen_test_") and schema[11:].isalnum()
    async with engine.begin() as connection:
        await connection.execute(CreateSchema(schema))
    isolated = engine.execution_options(schema_translate_map={None: schema})
    try:
        async with isolated.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield SearchRepository(isolated), isolated
    finally:
        # Only the unique schema created by this fixture is disposable.
        assert schema.startswith("lumen_test_") and len(schema) == 43
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True))
        await engine.dispose()


@pytest.fixture
async def redis_scope():
    client = make_redis(get_settings().redis_url)
    prefix = "lumen:test:" + uuid4().hex
    try:
        assert await client.ping()
        yield client, prefix
    finally:
        assert prefix.startswith("lumen:test:") and len(prefix) == 43
        keys = [key async for key in client.scan_iter(match=prefix + ":*")]
        if keys:
            assert all(key.startswith(prefix + ":") for key in keys)
            await client.delete(*keys)
        await client.aclose()
