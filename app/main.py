from fastapi import FastAPI

from app.api.analysis import router as analysis_router
from app.core.config import settings
from app.core.health import dependency_status

app = FastAPI(title="OfficeAgent", version="0.1.0")
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
