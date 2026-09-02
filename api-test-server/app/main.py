from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, ValidationError
from sqlalchemy import Engine

from app.api.auth import router as auth_router
from app.api.orders import router as orders_router
from app.api.products import router as products_router
from app.api.users import router as users_router
from app.core.config import AuthSettings, Settings
from app.database.session import (
    DatabaseUnavailableError,
    create_database_engine,
    initialize_database,
    verify_database_connection,
)


class HealthResponse(BaseModel):
    status: Literal["ok"]


def create_app(
    settings: Settings | None = None,
    auth_settings: AuthSettings | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine: Engine | None = None
        database_error: str | None = None
        resolved_auth_settings: AuthSettings | None = None
        auth_error: str | None = None

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

        try:
            resolved_auth_settings = auth_settings or AuthSettings()
        except ValidationError:
            auth_error = "Authentication configuration is invalid"

        application.state.db_engine = engine
        application.state.database_error = database_error
        application.state.auth_settings = resolved_auth_settings
        application.state.auth_error = auth_error

        try:
            yield
        finally:
            if engine is not None:
                engine.dispose()

    application = FastAPI(
        title="API Test Server",
        description="Controllable backend for the API automation framework.",
        version="0.5.0",
        lifespan=lifespan,
    )
    application.include_router(auth_router)
    application.include_router(users_router)
    application.include_router(products_router)
    application.include_router(orders_router)

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
