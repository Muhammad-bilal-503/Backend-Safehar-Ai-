from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.models.user import User
from app.api.deps import get_current_user
from app.services.assistant_service import chat as assistant_chat

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


@router.post("/chat")
async def chat(payload: ChatRequest, current_user: User = Depends(get_current_user)):
    history = [{"role": m.role, "content": m.content} for m in payload.history]
    reply = await assistant_chat(payload.message, history)
    return {"reply": reply}
