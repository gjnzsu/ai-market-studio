import logging
from fastapi import APIRouter, HTTPException, Request

from backend.models import ChatRequest, ChatResponse
from backend.agent.agent import run_agent
from backend.connectors.base import ConnectorError

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    """Accept a user message and return an AI-generated reply with FX data."""
    connector = request.app.state.connector
    history = [m.model_dump() for m in body.history]

    try:
        result = await run_agent(
            message=body.message,
            history=history,
            connector=connector,
        )
    except ConnectorError as e:
        logger.error("Connector error in /chat: %s", e)
        raise HTTPException(status_code=503, detail="Market data service unavailable.")
    except Exception as e:
        logger.exception("Unexpected error in /chat: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error.")

    return ChatResponse(
        reply=result["reply"],
        data=result["data"],
        tool_used=result["tool_used"],
    )
