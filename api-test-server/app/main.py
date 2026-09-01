from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, ValidationError
from sqlalchemy import Engine

from app.core.config import Settings
from app.database.session import (
    DatabaseUnavailableError,
    create_database_engine,
    initialize_database,
    verify_database_connection,
)


class HealthResponse(BaseModel):
    status: Literal["ok"]


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine: Engine | None = None
        database_error: str | None = None

        try:
            database_settings = settings or Settings()
            engine = create_database_engine(database_settings)
            initialize_database(engine)
        except ValidationError:
            database_error = "Database configuration is invalid"
        except DatabaseUnavailableError:
            database_error = "Database unavailable"
            if engine is not None:
                engine.dispose()
            engine = None

        application.state.db_engine = engine
        application.state.database_error = database_error

        try:
            yield
        finally:
            if engine is not None:
                engine.dispose()

    application = FastAPI(
        title="API Test Server",
        description="Controllable backend for the API automation framework.",
        version="0.2.0",
        lifespan=lifespan,
    )

    @application.get("/health", response_model=HealthResponse)
    async def get_health() -> HealthResponse:
        return HealthResponse(status="ok")

    @application.get("/health/db", response_model=HealthResponse)
    def get_database_health(request: Request) -> HealthResponse:
        engine: Engine | None = request.app.state.db_engine
        if engine is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=request.app.state.database_error,
            )

        try:
            verify_database_connection(engine)
        except DatabaseUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database unavailable",
            ) from exc

        return HealthResponse(status="ok")

    return application


app = create_app()
