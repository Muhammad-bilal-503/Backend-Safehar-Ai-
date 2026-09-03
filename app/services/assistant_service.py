"""Optional AI Safety Assistant — proxies to Anthropic if ANTHROPIC_API_KEY is set,
otherwise returns a canned safety-guidance response so the feature still works offline."""
import httpx

from app.core.config import settings

SYSTEM_PROMPT = (
    "You are SafeHer AI's safety assistant. Give brief, practical personal-safety guidance: "
    "safer routes, de-escalation tips, when to contact emergency services, and how to use the "
    "app's SOS/journey-sharing features. Keep replies under 120 words unless asked for detail."
)


async def chat(message: str, history: list[dict]) -> str:
    if not settings.ANTHROPIC_API_KEY:
        return (
            "I'm here to help with your safety. For real emergencies, use the SOS button or "
            "call your local emergency number directly. (Connect an ANTHROPIC_API_KEY on the "
            "backend to enable full AI responses.)"
        )

    messages = history + [{"role": "user", "content": message}]
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 400,
                "system": SYSTEM_PROMPT,
                "messages": messages,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
