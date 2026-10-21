from fastapi import APIRouter

from auth_service.api.dependencies import CurrentUser, Service
from auth_service.schemas import ProfileUpdate, UserResponse

router = APIRouter(tags=["profile"])


@router.get("/me", response_model=UserResponse)
async def read_profile(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    body: ProfileUpdate, user: CurrentUser, service: Service
) -> UserResponse:
    updated = await service.update_profile(user, body.full_name)
    return UserResponse.model_validate(updated)
