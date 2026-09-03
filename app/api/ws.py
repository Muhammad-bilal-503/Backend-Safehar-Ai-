from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.ws_manager import manager

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/monitor")
async def monitor_socket(websocket: WebSocket):
    """Live alert feed for the Monitor dashboard — pushes an event whenever any
    EmergencyEvent is created or updated (see app/api/emergencies.py)."""
    await manager.connect(websocket)
    try:
        while True:
            # Dashboard doesn't need to send anything; keep the connection open.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
