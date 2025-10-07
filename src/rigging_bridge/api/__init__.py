from fastapi import FastAPI

from rigging_bridge.api.v1 import router as v1_router
from rigging_bridge.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title=settings.app_name)
    app.include_router(v1_router, prefix="/v1")
    return app


app = create_app()
