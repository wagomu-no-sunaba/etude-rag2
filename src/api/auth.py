"""Google OAuth authentication module.

This module provides Google OAuth 2.0 authentication with whitelist-based access control.
Only users whose email addresses are in the allowed_emails list can access the application.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from src.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@lru_cache
def get_oauth() -> OAuth:
    """Get cached OAuth instance configured for Google."""
    settings = get_settings()
    oauth = OAuth()
    oauth.register(
        name="google",
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    return oauth


@dataclass
class AuthenticatedUser:
    """Authenticated user data from session."""

    email: str
    name: str
    picture: str | None = None


def get_current_user(request: Request) -> AuthenticatedUser | None:
    """Get current user from session.

    Args:
        request: The incoming request.

    Returns:
        AuthenticatedUser if authenticated, None otherwise.
    """
    user_data = request.session.get("user")
    if not user_data:
        return None
    return AuthenticatedUser(
        email=user_data.get("email", ""),
        name=user_data.get("name", ""),
        picture=user_data.get("picture"),
    )


def require_auth(request: Request) -> AuthenticatedUser:
    """Require authenticated user (raises HTTPException if not authenticated).

    Args:
        request: The incoming request.

    Returns:
        AuthenticatedUser if authenticated.

    Raises:
        HTTPException: 401 if not authenticated.
    """
    user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


def check_whitelist(email: str) -> bool:
    """Check if email is in the whitelist.

    Args:
        email: Email address to check.

    Returns:
        True if email is allowed, False otherwise.
    """
    settings = get_settings()
    allowed_emails = settings.allowed_emails_list

    if not allowed_emails:
        logger.warning("No whitelist configured, denying all access")
        return False

    email_lower = email.lower()
    return email_lower in allowed_emails


@router.get("/login")
async def login(request: Request):
    """Redirect to Google OAuth authorization."""
    oauth = get_oauth()
    redirect_uri = request.url_for("auth_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def auth_callback(request: Request):
    """Handle OAuth callback from Google.

    Exchanges the authorization code for tokens, validates the user's email
    against the whitelist, and creates a session.
    """
    oauth = get_oauth()

    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as e:
        logger.error(f"OAuth error: {e}")
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {e.description}",
        ) from e

    user_info = token.get("userinfo")
    if not user_info:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Failed to get user info",
        )

    email = user_info.get("email")
    if not email:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Email not provided",
        )

    # Check whitelist
    if not check_whitelist(email):
        logger.warning(f"Access denied for email: {email}")
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="アクセスが拒否されました。許可されたメールアドレスではありません。",
        )

    # Store user info in session
    request.session["user"] = {
        "email": email,
        "name": user_info.get("name", ""),
        "picture": user_info.get("picture"),
    }

    logger.info(f"User logged in: {email}")
    return RedirectResponse(url="/", status_code=302)


@router.get("/logout")
async def logout(request: Request):
    """Clear session and redirect to login page."""
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=302)


@router.get("/me")
async def get_me(request: Request):
    """Get current user info."""
    user = require_auth(request)
    return {
        "email": user.email,
        "name": user.name,
        "picture": user.picture,
    }
