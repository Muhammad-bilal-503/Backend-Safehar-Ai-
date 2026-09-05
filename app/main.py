import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import init_db, close_db
from app.api import auth, users, contacts, journeys, emergencies, services, ws, assistant, reports, incidents, tracking

os.makedirs(settings.MEDIA_ROOT, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect to MongoDB and register all Document models with Beanie
    # before the app starts accepting requests.
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="SafeHer AI API",
    description="Backend for the SafeHer AI personal safety platform.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/media", StaticFiles(directory=settings.MEDIA_ROOT), name="media")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(contacts.router)
app.include_router(journeys.router)
app.include_router(emergencies.router)
app.include_router(reports.router)
app.include_router(services.router)
app.include_router(assistant.router)
app.include_router(incidents.router)
app.include_router(tracking.router)
app.include_router(ws.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "SafeHer AI API", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "healthy"}
