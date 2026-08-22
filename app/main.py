from contextlib import asynccontextmanager
import logging
import sys
import time
from uuid import uuid4

from fastapi import FastAPI, Request

from app.agents.mcp_registry import mcp_registry
from app.api.analysis import initialize_task_store
from app.api.analysis import router as analysis_router
from app.core.checkpoint import close_checkpointer, initialize_checkpointer
from app.core.config import settings
from app.core.health import dependency_status


# Uvicorn normally configures logging, but explicitly attach a console handler to
# the application logger so diagnostics are visible when the app is started in
# other ways (python, IDE, tests, etc.).
logger = logging.getLogger("app")
logger.setLevel(logging.INFO)
logger.propagate = True
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s"))
    logger.addHandler(handler)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info(
        "application.startup environment=%s llm_provider=%s llm_model=%s llm_base_url=%s llm_api_key_configured=%s",
        settings.environment,
        settings.llm_provider,
        settings.llm_model,
        settings.llm_base_url or "default",
        bool(settings.llm_api_key),
    )
    initialize_task_store()
    logger.info("application.task_store.initialized")
    if settings.environment != "test":
        await initialize_checkpointer()
        logger.info("application.checkpointer.initialized")
        await mcp_registry.initialize()
        logger.info(
            "application.mcp.initialized errors=%d discovered=crm:%d,database:%d,knowledge:%d,report:%d",
            len(mcp_registry.errors),
            len(mcp_registry.tools("crm")),
            len(mcp_registry.tools("database")),
            len(mcp_registry.tools("knowledge")),
            len(mcp_registry.tools("report")),
        )
    try:
        yield
    finally:
        if settings.environment != "test":
            await mcp_registry.close()
            await close_checkpointer()
        logger.info("application.shutdown")


app = FastAPI(title="OfficeAgent", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    started = time.perf_counter()
    logger.info(
        "http.request.start request_id=%s method=%s path=%s",
        request_id,
        request.method,
        request.url.path,
    )
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "http.request.failed request_id=%s method=%s path=%s elapsed_ms=%.1f",
            request_id,
            request.method,
            request.url.path,
            (time.perf_counter() - started) * 1000,
        )
        raise
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "http.request.completed request_id=%s method=%s path=%s status=%d elapsed_ms=%.1f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        (time.perf_counter() - started) * 1000,
    )
    return response


app.include_router(analysis_router)


@app.get("/health")
def health() -> dict:
    dependencies = dependency_status()
    return {
        "status": "ok" if all(item.ok for item in dependencies) else "degraded",
        "service": settings.app_name,
        "dependencies": {
            item.name: {"ok": item.ok, "detail": item.detail} for item in dependencies
        },
        "mcp": {"discovered": {name: len(mcp_registry.tools(name)) for name in ("crm", "database", "knowledge", "report")}, "errors": mcp_registry.errors},
    }
