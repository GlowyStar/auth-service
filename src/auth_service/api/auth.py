from fastapi import APIRouter, status

from auth_service.api.dependencies import Service
from auth_service.schemas import ConfirmEmailRequest, EmailRequest, SignUpRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def sign_up(body: SignUpRequest, service: Service) -> UserResponse:
    user = await service.sign_up(body.email, body.password)
    return UserResponse.model_validate(user)


@router.post("/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_email(body: ConfirmEmailRequest, service: Service) -> None:
    await service.confirm_email(body.email, body.code)


@router.post("/confirm/resend", status_code=status.HTTP_202_ACCEPTED)
async def resend_confirmation(body: EmailRequest, service: Service) -> None:
    await service.resend_confirmation(body.email)
