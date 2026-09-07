import random
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import (
    hash_password, verify_password, create_access_token, create_refresh_token, decode_token,
)
from app.models.user import User
from app.models.otp import OTPCode
from app.schemas.auth import (
    RegisterRequest, LoginRequest, TokenResponse, RefreshRequest,
    OTPRequest, OTPVerify, ForgotPasswordRequest, ResetPasswordRequest,
)
from app.schemas.user import UserOut
from app.services.email_service import send_email
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _tokens_for(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest):
    if await User.find_one(User.email == payload.email):
        raise HTTPException(400, "An account with this email already exists.")
    user = User(
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        phone=payload.phone,
    )
    await user.insert()
    await _issue_otp(user.email, "verify_email")
    return _tokens_for(user)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    user = await User.find_one(User.email == payload.email)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(401, "Incorrect email or password.")
    if not user.is_active:
        raise HTTPException(403, "This account has been disabled.")
    return _tokens_for(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest):
    data = decode_token(payload.refresh_token)
    if not data or data.get("type") != "refresh":
        raise HTTPException(401, "Invalid refresh token.")
    user = await User.get(data.get("sub"))
    if not user:
        raise HTTPException(401, "Invalid refresh token.")
    return _tokens_for(user)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


async def _issue_otp(email: str, purpose: str) -> str:
    code = f"{random.randint(0, 999999):06d}"
    otp = OTPCode(
        email=email, code=code, purpose=purpose,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    await otp.insert()
    subject = "Verify your SafeHer AI account" if purpose == "verify_email" else "Reset your SafeHer AI password"
    await send_email(email, subject, f"<p>Your verification code is:</p><h2>{code}</h2><p>Expires in 10 minutes.</p>")
    return code


@router.post("/otp/request")
async def request_otp(payload: OTPRequest):
    await _issue_otp(payload.email, payload.purpose)
    return {"message": "Verification code sent."}


@router.post("/otp/verify")
async def verify_otp(payload: OTPVerify):
    otp = (
        await OTPCode.find(
            OTPCode.email == payload.email,
            OTPCode.purpose == payload.purpose,
            OTPCode.used == False,  # noqa: E712
        )
        .sort(-OTPCode.created_at)
        .first_or_none()
    )
    if not otp or otp.code != payload.code or otp.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(400, "Invalid or expired code.")
    otp.used = True
    await otp.save()
    if payload.purpose == "verify_email":
        user = await User.find_one(User.email == payload.email)
        if user:
            user.is_verified = True
            await user.save()
    return {"message": "Verified."}


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest):
    user = await User.find_one(User.email == payload.email)
    if user:  # don't leak whether the email exists
        await _issue_otp(payload.email, "reset_password")
    return {"message": "If that account exists, a reset code has been sent."}


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest):
    otp = (
        await OTPCode.find(
            OTPCode.email == payload.email,
            OTPCode.purpose == "reset_password",
            OTPCode.used == False,  # noqa: E712
        )
        .sort(-OTPCode.created_at)
        .first_or_none()
    )
    if not otp or otp.code != payload.code or otp.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(400, "Invalid or expired code.")
    user = await User.find_one(User.email == payload.email)
    if not user:
        raise HTTPException(404, "Account not found.")
    user.hashed_password = hash_password(payload.new_password)
    await user.save()
    otp.used = True
    await otp.save()
    return {"message": "Password updated."}
