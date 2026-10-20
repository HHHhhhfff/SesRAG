from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_session
from backend.api.schemas.v2.models import ModelListResponse
from backend.application.model_profiles import list_model_profiles
from backend.infrastructure.session.model_profiles import SQLModelProfileRepository

router = APIRouter(prefix="/api/v2/models", tags=["v2 models"])


@router.get("", response_model=ModelListResponse)
async def get_models(session: AsyncSession = Depends(get_session)):
    return await list_model_profiles(SQLModelProfileRepository(session))
