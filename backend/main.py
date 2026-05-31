import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from config import settings
from ingestion.rss import watch_feeds
from logging_config import setup_logging

setup_logging()
logger = logging.getLogger("lumen")


def _run_migrations_sync() -> None:
    from alembic import command
    from alembic.config import Config

    base_dir = Path(__file__).resolve().parent
    cfg_candidates = [base_dir / "alembic.ini", base_dir.parent / "alembic.ini"]
    cfg_path = next((path for path in cfg_candidates if path.exists()), None)
    if cfg_path is None:
        raise FileNotFoundError("Could not find alembic.ini in backend or repository root")

    cfg = Config(str(cfg_path))
    script_location = cfg.get_main_option("script_location")
    if script_location:
        resolved_script_location = str((cfg_path.parent / script_location).resolve())
        cfg.set_main_option("script_location", resolved_script_location)
    command.upgrade(cfg, "head")
    logger.info("Database migrations applied")


async def run_migrations() -> None:
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=1) as executor:
        await loop.run_in_executor(executor, _run_migrations_sync)


async def refresh_all_researchers() -> None:
    from database import SessionLocal
    from database import set_db_request_context
    from researchers.profiles import refresh_profile
    from sqlalchemy import text

    logger.info("Starting weekly researcher refresh")
    async with SessionLocal() as db:
        workspaces = await db.execute(text("SELECT id FROM workspaces"))
        workspace_ids = [str(row.id) for row in workspaces.all()]

    total = 0
    for workspace_id in workspace_ids:
        async with SessionLocal() as workspace_db:
            await set_db_request_context(
                workspace_db,
                workspace_id=workspace_id,
                user_id="00000000-0000-0000-0000-000000000002",
                role="owner",
            )
            result = await workspace_db.execute(text("SELECT id FROM researchers"))
            ids = [row.id for row in result.all()]
            total += len(ids)
            for researcher_id in ids:
                try:
                    await refresh_profile(researcher_id, workspace_db)
                except Exception:
                    logger.exception(
                        "Failed to refresh researcher %s in workspace %s",
                        researcher_id,
                        workspace_id,
                    )

    logger.info("Weekly researcher refresh complete — %d profiles", total)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_migrations()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(watch_feeds, "cron", hour=6, minute=0)
    scheduler.add_job(refresh_all_researchers, "cron", day_of_week="sun", hour=3, minute=0)
    scheduler.start()
    logger.info("Lumen started")

    yield

    scheduler.shutdown()
    logger.info("Lumen stopped")


app = FastAPI(
    title="Lumen",
    description="Research intelligence layer for ML practitioners",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
