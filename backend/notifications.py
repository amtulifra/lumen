import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def create_notification(
    type: str, message: str, payload: dict, db: AsyncSession
) -> None:
    await db.execute(
        text(
            "INSERT INTO notifications (id, type, message, payload) "
            "VALUES (:id, :type, :message, :payload)"
        ),
        {
            "id": str(uuid.uuid4()),
            "type": type,
            "message": message,
            "payload": payload,
        },
    )


async def list_notifications(db: AsyncSession, unread_only: bool = False) -> list[dict]:
    query = (
        "SELECT id, type, message, payload, read, created_at FROM notifications "
        + ("WHERE workspace_id = current_workspace_id() AND read = FALSE " if unread_only else "WHERE workspace_id = current_workspace_id() ")
        + "ORDER BY created_at DESC LIMIT 50"
    )
    result = await db.execute(text(query))
    return [dict(row) for row in result.mappings().all()]


async def mark_read(notification_id: str, db: AsyncSession) -> bool:
    result = await db.execute(
        text("UPDATE notifications SET read = TRUE WHERE workspace_id = current_workspace_id() AND id = :id AND read = FALSE"),
        {"id": notification_id},
    )
    await db.commit()
    return result.rowcount > 0


async def mark_all_read(db: AsyncSession) -> None:
    await db.execute(text("UPDATE notifications SET read = TRUE WHERE workspace_id = current_workspace_id() AND read = FALSE"))
    await db.commit()
