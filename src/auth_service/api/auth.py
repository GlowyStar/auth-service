from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from auth_service.api.dependencies import ClientIp, Service
from auth_service.schemas import (
    ConfirmEmailRequest,
    EmailRequest,
    LoginRequest,
    RefreshRequest,
    SignUpRequest,
    TokenResponse,
    UserResponse,
)

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


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, client_ip: ClientIp, service: Service) -> TokenResponse:
    tokens = await service.login(body.email, body.password, client_ip)
    return TokenResponse.model_validate(tokens)


@router.post("/token", response_model=TokenResponse)
async def login_with_form(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    client_ip: ClientIp,
    service: Service,
) -> TokenResponse:
    tokens = await service.login(form.username.lower(), form.password, client_ip)
    return TokenResponse.model_validate(tokens)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(body: RefreshRequest, service: Service) -> TokenResponse:
    tokens = await service.refresh(body.refresh_token)
    return TokenResponse.model_validate(tokens)
