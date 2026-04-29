from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from ingestion.rss import watch_feeds
from knowledge.graph import knowledge_graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    await knowledge_graph.build_from_db()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(watch_feeds, "cron", hour=6, minute=0)
    scheduler.start()

    yield

    scheduler.shutdown()


app = FastAPI(
    title="Lumen",
    description="Research intelligence layer for ML practitioners",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
