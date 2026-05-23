"""
backend/services/auth_service.py
─────────────────────────────────────────────────────
In-memory user store with JWT creation and validation.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.context import CryptContext

load_dotenv()

JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-to-a-random-32-char-string")
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRE_HOURS: int = 24

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _initials(full_name: str) -> str:
    parts = full_name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return parts[0][:2].upper() if parts else "??"


# ─── In-memory user store ────────────────────────────────────────────────────
# keyed by username
_users: Dict[str, Dict] = {
    "admin": {
        "id": "USR_001",
        "username": "admin",
        "fullName": "Dr. Sarah Johnson",
        "email": "sarah.johnson@clinicaltrials.ai",
        "role": "Clinical Data Manager",
        "hashed_password": _pwd_ctx.hash("admin123"),
        "created_at": "2024-01-01T00:00:00Z",
        "avatar_initials": "SJ",
    }
}


# ─── Public API ──────────────────────────────────────────────────────────────

def create_user(
    full_name: str,
    username: str,
    email: str,
    password: str,
    role: str,
) -> Dict:
    """Hash password and store user.  Raises ValueError if username taken."""
    if username in _users:
        raise ValueError(f"Username '{username}' already exists.")
    user = {
        "id": f"USR_{len(_users) + 1:03d}",
        "username": username,
        "fullName": full_name,
        "email": email,
        "role": role,
        "hashed_password": _pwd_ctx.hash(password),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "avatar_initials": _initials(full_name),
    }
    _users[username] = user
    return _safe_user(user)


def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """Verify credentials; return safe user dict or None."""
    user = _users.get(username)
    if not user:
        return None
    if not _pwd_ctx.verify(password, user["hashed_password"]):
        return None
    return _safe_user(user)


def create_access_token(
    data: Dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT with 24-hour expiry."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=JWT_EXPIRE_HOURS)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(token: str) -> Dict:
    """Decode JWT and return user dict.  Raises ValueError if invalid."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub", "")
        if not username:
            raise ValueError("Invalid token payload")
    except JWTError as exc:
        raise ValueError(f"Token validation failed: {exc}") from exc

    user = _users.get(username)
    if not user:
        raise ValueError("User not found")
    return _safe_user(user)


# ─── Private helpers ─────────────────────────────────────────────────────────

def _safe_user(user: Dict) -> Dict:
    """Return user dict without the hashed_password."""
    return {k: v for k, v in user.items() if k != "hashed_password"}
