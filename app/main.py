from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from app.agents.mcp_registry import mcp_registry
from app.api.analysis import initialize_task_store
from app.api.analysis import router as analysis_router
from app.core.checkpoint import close_checkpointer, initialize_checkpointer
from app.core.config import settings
from app.core.health import dependency_status

logging.getLogger("app").setLevel(logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("application.startup environment=%s", settings.environment)
    initialize_task_store()
    logger.info("application.task_store.initialized")
    if settings.environment != "test":
        await initialize_checkpointer()
        logger.info("application.checkpointer.initialized")
        await mcp_registry.initialize()
        logger.info("application.mcp.initialized errors=%d", len(mcp_registry.errors))
    try:
        yield
    finally:
        if settings.environment != "test":
            await mcp_registry.close()
            await close_checkpointer()
        logger.info("application.shutdown")


app = FastAPI(title="OfficeAgent", version="0.1.0", lifespan=lifespan)
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
