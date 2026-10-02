from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import get_settings
from app.db import make_engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize resources here
    app.state.engine = make_engine(get_settings().database_url)

    yield  # This is where the application runs

    # Clean up resources here
    await app.state.engine.dispose()

app = FastAPI(title="Lumen API", version="0.1.0")