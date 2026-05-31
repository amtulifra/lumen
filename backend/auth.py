import time
from dataclasses import dataclass
from typing import Literal

import httpx
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db, set_db_request_context
import logging

Role = Literal["viewer", "editor", "admin", "owner"]

ROLE_RANK: dict[Role, int] = {
    "viewer": 1,
    "editor": 2,
    "admin": 3,
    "owner": 4,
}

DEV_WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"
DEV_USER_ID = "00000000-0000-0000-0000-000000000002"

_JWKS_CACHE: dict[str, object] = {"expires_at": 0.0, "jwks": {}}
logger = logging.getLogger("lumen.auth")


@dataclass
class RequestContext:
    user_id: str
    workspace_id: str
    role: Role
    external_subject: str | None = None
    email: str | None = None


def _normalize_role(value: str | None) -> Role:
    role = (value or "viewer").lower()
    if role not in ROLE_RANK:
        return "viewer"
    return role  # type: ignore[return-value]


async def _get_jwks() -> dict:
    now = time.time()
    if _JWKS_CACHE["jwks"] and now < float(_JWKS_CACHE["expires_at"]):
        return _JWKS_CACHE["jwks"]  # type: ignore[return-value]

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(settings.clerk_jwks_url)
        response.raise_for_status()
        jwks = response.json()

    _JWKS_CACHE["jwks"] = jwks
    _JWKS_CACHE["expires_at"] = now + 600.0
    return jwks


async def _decode_clerk_jwt(token: str) -> dict:
    import jwt

    unverified = jwt.get_unverified_header(token)
    kid = unverified.get("kid")
    if not kid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token kid")

    jwks = await _get_jwks()
    key = next((j for j in jwks.get("keys", []) if j.get("kid") == kid), None)
    if key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown signing key")

    audience = settings.clerk_audience or None
    try:
        return jwt.decode(
            token,
            jwt.algorithms.RSAAlgorithm.from_jwk(key),
            algorithms=["RS256"],
            audience=audience,
            issuer=settings.clerk_issuer,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}") from exc


async def get_request_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_workspace_id: str | None = Header(default=None),
) -> RequestContext:
    if not settings.auth_required:
        ctx = RequestContext(
            user_id=request.headers.get("x-user-id", DEV_USER_ID),
            workspace_id=x_workspace_id or request.headers.get("x-workspace-id", DEV_WORKSPACE_ID),
            role=_normalize_role(request.headers.get("x-role", "owner")),
            external_subject=request.headers.get("x-subject"),
            email=request.headers.get("x-email"),
        )
        await set_db_request_context(db, ctx.workspace_id, ctx.user_id, ctx.role)
        logger.info(
            "auth_decision allow user=%s workspace=%s role=%s source=dev",
            ctx.user_id,
            ctx.workspace_id,
            ctx.role,
        )
        request.state.auth = ctx
        return ctx

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    if not x_workspace_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-Workspace-Id")

    token = authorization.split(" ", 1)[1]
    claims = await _decode_clerk_jwt(token)
    subject = claims.get("sub")
    email = claims.get("email")
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing subject claim")

    user_result = await db.execute(
        text(
            "INSERT INTO users (id, external_subject, email) "
            "VALUES (gen_random_uuid(), :sub, :email) "
            "ON CONFLICT (external_subject) DO UPDATE SET email = EXCLUDED.email "
            "RETURNING id"
        ),
        {"sub": subject, "email": email or ""},
    )
    user_id = str(user_result.scalar_one())

    member_result = await db.execute(
        text(
            "SELECT role FROM workspace_memberships "
            "WHERE workspace_id = CAST(:workspace_id AS uuid) "
            "AND user_id = CAST(:user_id AS uuid)"
        ),
        {"workspace_id": x_workspace_id, "user_id": user_id},
    )
    role = member_result.scalar_one_or_none()
    if role is None:
        # Avoid resource enumeration across tenants.
        logger.warning(
            "auth_decision deny user=%s workspace=%s reason=no_membership",
            user_id,
            x_workspace_id,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    ctx = RequestContext(
        user_id=user_id,
        workspace_id=x_workspace_id,
        role=role,
        external_subject=subject,
        email=email,
    )
    await set_db_request_context(db, ctx.workspace_id, ctx.user_id, ctx.role)
    logger.info(
        "auth_decision allow user=%s workspace=%s role=%s source=clerk",
        ctx.user_id,
        ctx.workspace_id,
        ctx.role,
    )
    request.state.auth = ctx
    return ctx


def require_role(min_role: Role):
    async def _dependency(ctx: RequestContext = Depends(get_request_context)) -> RequestContext:
        if ROLE_RANK[ctx.role] < ROLE_RANK[min_role]:
            logger.warning(
                "auth_decision deny user=%s workspace=%s role=%s required=%s",
                ctx.user_id,
                ctx.workspace_id,
                ctx.role,
                min_role,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {min_role} role",
            )
        return ctx

    return _dependency


require_viewer = require_role("viewer")
require_editor = require_role("editor")
require_admin = require_role("admin")
require_owner = require_role("owner")
