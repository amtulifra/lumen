from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings

engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        auth_ctx = getattr(request.state, "auth", None)
        if auth_ctx is not None:
            await set_db_request_context(
                session,
                workspace_id=auth_ctx.workspace_id,
                user_id=auth_ctx.user_id,
                role=auth_ctx.role,
            )
        yield session


async def set_db_request_context(
    db: AsyncSession,
    workspace_id: str,
    user_id: str,
    role: str,
) -> None:
    await db.execute(
        text(
            "SELECT "
            "set_config('app.current_workspace_id', :workspace_id, false), "
            "set_config('app.current_user_id', :user_id, false), "
            "set_config('app.current_role', :role, false)"
        ),
        {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "role": role,
        },
    )
