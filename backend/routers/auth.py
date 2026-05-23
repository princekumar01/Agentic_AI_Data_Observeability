"""
backend/routers/auth.py
─────────────────────────────────────────────────────
POST /auth/login
POST /auth/signup
POST /auth/logout
POST /auth/forgot-password
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from backend.models.schemas import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    SignupRequest,
    SignupResponse,
    UserOut,
)
from backend.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
    user = auth_service.authenticate_user(body.username, body.password)
    if not user:
        return LoginResponse(
            success=False,
            error="Invalid credentials",
        )
    token = auth_service.create_access_token({"sub": user["username"]})
    return LoginResponse(
        success=True,
        token=token,
        user=UserOut(
            id=user["id"],
            username=user["username"],
            fullName=user["fullName"],
            email=user["email"],
            role=user["role"],
            avatar_initials=user.get("avatar_initials", "??"),
        ),
    )


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest):
    try:
        user = auth_service.create_user(
            full_name=body.fullName,
            username=body.username,
            email=body.email,
            password=body.password,
            role=body.role,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"success": False, "error": "Username already exists"},
        )
    token = auth_service.create_access_token({"sub": user["username"]})
    return SignupResponse(
        success=True,
        token=token,
        user=UserOut(
            id=user["id"],
            username=user["username"],
            fullName=user["fullName"],
            email=user["email"],
            role=user["role"],
            avatar_initials=user.get("avatar_initials", "??"),
        ),
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(request: Request):
    # JWT is stateless; client clears token.
    return LogoutResponse(success=True, message="Logged out successfully")


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(body: ForgotPasswordRequest):
    # Always return 200 to prevent email enumeration.
    # No actual email sent in POC.
    return ForgotPasswordResponse(
        success=True,
        message="Reset instructions sent if email exists",
    )
