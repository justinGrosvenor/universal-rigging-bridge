from fastapi import APIRouter, HTTPException, status
from fastapi.concurrency import run_in_threadpool

from rigging_bridge.api.v1.models import (
    ConversionRequest,
    ConversionResponse,
)
from rigging_bridge.services.conversion import BlenderConversionError, ConversionService

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
async def health() -> dict[str, str]:
    """Simple liveness probe."""
    return {"status": "ok"}


@router.post("/convert", response_model=ConversionResponse, status_code=status.HTTP_202_ACCEPTED)
async def convert(request: ConversionRequest) -> ConversionResponse:
    """Run the Blender-based rig conversion pipeline."""
    service = ConversionService()
    try:
        return await run_in_threadpool(service.convert, request)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except BlenderConversionError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
