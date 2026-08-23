from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from roostos_web.services.events import event_publisher

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.get("/stream")
async def event_stream() -> StreamingResponse:
    """Server-Sent Events (SSE) stream broadcasting real-time system, device, and schedule events."""
    return StreamingResponse(
        event_publisher.subscribe(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
