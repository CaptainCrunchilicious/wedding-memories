import logging
from contextlib import asynccontextmanager
from collections.abc import Callable
from typing import AsyncIterator, Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.albums import router as albums_router
from app.api.v1.public import router as public_router
from app.api.v1.admin_photos import router as admin_photos_router
from app.core.config import Settings, get_settings
from app.database.collections import initialize_collections
from app.database.connection import MongoConnection
from app.database.indexes import initialize_indexes
from app.services.upload_guard import UploadGuard
from app.storage.local import LocalPhotoStorage
from app.storage.google_drive import GoogleDriveStorage
from app.middleware.upload_size import UploadBodyLimitMiddleware
from app.middleware.oauth_log_redaction import OAuthCallbackAccessLogFilter

logger = logging.getLogger(__name__)
DatabaseStatus = Literal["connected", "not_configured", "disconnected"]


def create_app(settings_provider: Callable[[], Settings] = get_settings) -> FastAPI:
    settings: Settings = settings_provider()
    access_logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, OAuthCallbackAccessLogFilter) for item in access_logger.filters):
        access_logger.addFilter(OAuthCallbackAccessLogFilter())

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        connection = MongoConnection(settings)
        application.state.settings = settings
        application.state.mongo_connection = connection
        application.state.database_status = "not_configured"
        application.state.database_name = settings.mongodb_database
        application.state.upload_guard = UploadGuard()
        application.state.local_photo_storage = LocalPhotoStorage(settings.photo_storage_local_path)
        # Compatibility alias retained for existing local-storage integrations and tests.
        application.state.photo_storage = application.state.local_photo_storage
        application.state.google_drive_storage = GoogleDriveStorage(settings, connection)
        application.state.photo_storage_provider = settings.photo_storage_provider
        connection_closed = False

        if not settings.mongodb_uri.strip():
            logger.warning("MongoDB is not configured; API will run in degraded mode.")
        else:
            try:
                await connection.connect()
                database = connection.database
                if database is None:
                    raise RuntimeError("MongoDB connection did not select a database")
                await initialize_collections(database)
                await initialize_indexes(database)
                try:
                    selected_provider = await database["photo_settings"].find_one({"key": "storage_provider"})
                    if selected_provider and selected_provider.get("value") in {"local", "google_drive"}:
                        application.state.photo_storage_provider = selected_provider["value"]
                except Exception as exc:
                    logger.warning("Saved storage provider could not be loaded (%s).", type(exc).__name__)
                application.state.database_status = "connected"
                logger.info("MongoDB initialized for database '%s'.", settings.mongodb_database)
            except Exception as exc:
                application.state.database_status = "disconnected"
                logger.error(
                    "MongoDB initialization failed (%s). Check the URI, network access, and Atlas IP allowlist.",
                    type(exc).__name__,
                )
                await connection.close()
                connection_closed = True

        try:
            yield
        finally:
            if not connection_closed:
                await connection.close()
            logger.info("MongoDB client resources released.")

    application = FastAPI(
        title="Wedding Memories",
        description="API foundation for Wedding Memories.",
        version="0.2.0",
        lifespan=lifespan,
    )
    application.include_router(auth_router, prefix=f"{settings.api_v1_prefix.rstrip('/')}/auth")
    application.include_router(albums_router, prefix=settings.api_v1_prefix.rstrip("/"))
    application.include_router(public_router, prefix=settings.api_v1_prefix.rstrip("/"))
    application.include_router(admin_photos_router, prefix=settings.api_v1_prefix.rstrip("/"))
    from app.api.v1.integrations import router as integrations_router
    from app.api.v1.admin_storage import router as admin_storage_router
    application.include_router(integrations_router, prefix=settings.api_v1_prefix.rstrip("/"))
    application.include_router(admin_storage_router, prefix=settings.api_v1_prefix.rstrip("/"))
    application.add_middleware(UploadBodyLimitMiddleware, max_bytes=settings.upload_max_request_bytes)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.frontend_origins.split(",")],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @application.get("/health", tags=["health"])
    async def health(request: Request) -> JSONResponse:
        connection: MongoConnection = request.app.state.mongo_connection
        if connection.client is not None:
            request.app.state.database_status = (
                "connected" if await connection.check_connection() else "disconnected"
            )
        database_status: DatabaseStatus = request.app.state.database_status
        database_name: str = request.app.state.database_name
        healthy = database_status == "connected"
        return JSONResponse(
            status_code=200 if healthy else 503,
            content={
                "status": "healthy" if healthy else "degraded",
                "application": request.app.state.settings.app_name,
                "database": {"status": database_status, "name": database_name},
            },
        )

    return application


app = create_app()
