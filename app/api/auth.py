import random
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
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
async def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(400, "An account with this email already exists.")
    user = User(
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        phone=payload.phone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    await _issue_otp(db, user.email, "verify_email")
    return _tokens_for(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(401, "Incorrect email or password.")
    if not user.is_active:
        raise HTTPException(403, "This account has been disabled.")
    return _tokens_for(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    data = decode_token(payload.refresh_token)
    if not data or data.get("type") != "refresh":
        raise HTTPException(401, "Invalid refresh token.")
    user = db.get(User, data.get("sub"))
    if not user:
        raise HTTPException(401, "Invalid refresh token.")
    return _tokens_for(user)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


async def _issue_otp(db: Session, email: str, purpose: str) -> str:
    code = f"{random.randint(0, 999999):06d}"
    otp = OTPCode(
        email=email, code=code, purpose=purpose,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db.add(otp)
    db.commit()
    subject = "Verify your SafeHer AI account" if purpose == "verify_email" else "Reset your SafeHer AI password"
    await send_email(email, subject, f"<p>Your verification code is:</p><h2>{code}</h2><p>Expires in 10 minutes.</p>")
    return code


@router.post("/otp/request")
async def request_otp(payload: OTPRequest, db: Session = Depends(get_db)):
    await _issue_otp(db, payload.email, payload.purpose)
    return {"message": "Verification code sent."}


@router.post("/otp/verify")
def verify_otp(payload: OTPVerify, db: Session = Depends(get_db)):
    otp = (
        db.query(OTPCode)
        .filter(OTPCode.email == payload.email, OTPCode.purpose == payload.purpose, OTPCode.used == False)  # noqa: E712
        .order_by(OTPCode.created_at.desc())
        .first()
    )
    if not otp or otp.code != payload.code or otp.expires_at < datetime.now(timezone.utc):
        raise HTTPException(400, "Invalid or expired code.")
    otp.used = True
    if payload.purpose == "verify_email":
        user = db.query(User).filter(User.email == payload.email).first()
        if user:
            user.is_verified = True
    db.commit()
    return {"message": "Verified."}


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if user:  # don't leak whether the email exists
        await _issue_otp(db, payload.email, "reset_password")
    return {"message": "If that account exists, a reset code has been sent."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    otp = (
        db.query(OTPCode)
        .filter(OTPCode.email == payload.email, OTPCode.purpose == "reset_password", OTPCode.used == False)  # noqa: E712
        .order_by(OTPCode.created_at.desc())
        .first()
    )
    if not otp or otp.code != payload.code or otp.expires_at < datetime.now(timezone.utc):
        raise HTTPException(400, "Invalid or expired code.")
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(404, "Account not found.")
    user.hashed_password = hash_password(payload.new_password)
    otp.used = True
    db.commit()
    return {"message": "Password updated."}
