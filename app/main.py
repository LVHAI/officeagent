from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.analysis import initialize_task_store
from app.api.analysis import router as analysis_router
from app.core.config import settings
from app.core.health import dependency_status


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Persistent task storage must be initialized before the first request.
    initialize_task_store()
    yield


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
    }
