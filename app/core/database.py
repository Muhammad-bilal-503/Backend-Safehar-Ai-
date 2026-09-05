"""MongoDB connection + Beanie ODM initialization.

Beanie (https://beanie-odm.dev/) sits on top of Motor (the official async
MongoDB driver) and models documents as Pydantic classes, which is why the
conversion from SQLAlchemy models is mostly mechanical: each `Base` model
became a `Document` model in app/models/, keeping the same field names.
"""
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.core.config import settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGODB_URL)
    return _client


async def init_db() -> None:
    """Connect to MongoDB and register all Document models with Beanie.

    Called once from the FastAPI lifespan handler in app/main.py.
    """
    # Imported here (rather than at module load time) to avoid circular
    # imports between app.core.database and app.models.*.
    from app.models.user import User
    from app.models.otp import OTPCode
    from app.models.trusted_contact import TrustedContact
    from app.models.journey import Journey
    from app.models.emergency_event import EmergencyEvent
    from app.models.incident import Incident

    client = get_client()
    database = client[settings.MONGODB_DB_NAME]

    await init_beanie(
        database=database,
        document_models=[
            User,
            OTPCode,
            TrustedContact,
            Journey,
            EmergencyEvent,
            Incident,
        ],
    )


async def close_db() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
