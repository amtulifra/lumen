import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from knowledge.memory import record_event
from notifications_email import send_email_notification


async def create_notification(
    type: str, message: str, payload: dict, db: AsyncSession
) -> str:
    notification_id = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO notifications (id, type, message, payload) "
            "VALUES (:id, :type, :message, :payload)"
        ),
        {
            "id": notification_id,
            "type": type,
            "message": message,
            "payload": payload,
        },
    )

    if type == "hypothesis_evidence":
        await _send_email_notification_to_workspace(notification_id, message, payload, db)
    return notification_id


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
    if result.rowcount > 0:
        await record_event(
            event_type="notification_opened",
            subject_id=notification_id,
            subject_type="notification",
            content=f"Notification opened: {notification_id}",
            db=db,
        )
    return result.rowcount > 0


async def mark_all_read(db: AsyncSession) -> None:
    await db.execute(text("UPDATE notifications SET read = TRUE WHERE workspace_id = current_workspace_id() AND read = FALSE"))
    await db.commit()


async def _send_email_notification_to_workspace(
    notification_id: str,
    message: str,
    payload: dict,
    db: AsyncSession,
) -> None:
    rows = await db.execute(
        text(
            "SELECT DISTINCT u.email "
            "FROM workspace_memberships wm "
            "JOIN users u ON u.id = wm.user_id "
            "WHERE wm.workspace_id = current_workspace_id() "
            "AND u.email IS NOT NULL "
            "AND u.email <> ''"
        )
    )
    recipients = [r["email"] for r in rows.mappings().all()]
    if not recipients:
        return

    paper_id = str(payload.get("paper_id", ""))
    hypothesis_id = str(payload.get("hypothesis_id", ""))
    verdict = str(payload.get("verdict", ""))
    link = f"{settings.app_base_url}/hypotheses"
    body = (
        f"{message}\n\n"
        f"Verdict: {verdict or 'unknown'}\n"
        f"Hypothesis ID: {hypothesis_id or 'n/a'}\n"
        f"Paper ID: {paper_id or 'n/a'}\n\n"
        f"Open in Lumen: {link}\n"
    )

    sent_count = 0
    for email in recipients:
        try:
            sent = await send_email_notification(
                to_email=email,
                subject="Lumen hypothesis update",
                body_text=body,
            )
            if sent:
                sent_count += 1
        except Exception:
            # Non-fatal for product loop; notification is still persisted in-app.
            continue

    if sent_count > 0:
        await record_event(
            event_type="notification_sent",
            subject_id=notification_id,
            subject_type="notification",
            content=f"Notification email sent to {sent_count} recipient(s)",
            db=db,
        )
