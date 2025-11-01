"""
RCA Chat Router with LangGraph Agent and SSE Streaming

This router provides a streaming chat endpoint for root cause analysis using:
- LangGraph ReAct agent for tool calling
- AWS Bedrock Claude 3.5 Sonnet for LLM
- MongoDB checkpointing for conversation memory
- Server-Sent Events (SSE) for real-time streaming
"""

import os
import json
import logging
from typing import AsyncIterator
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from langchain_aws import ChatBedrock
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.mongodb.aio import AsyncMongoDBSaver

from services.rca_chat_tools import TOOLS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Environment variables
MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("MDB_DATABASE_NAME", "smf-yield-defect")
AWS_REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))

# Global agent instance (initialized on first request)
_agent = None
_checkpointer = None


def _get_agent():
    """Get or create the LangGraph agent instance."""
    global _agent, _checkpointer

    if _agent is not None:
        return _agent

    logger.info("Initializing LangGraph ReAct agent...")

    # Initialize LLM (AWS Bedrock Claude 3.5 Sonnet)
    llm = ChatBedrock(
        model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        region_name=AWS_REGION,
        model_kwargs={
            "temperature": 0.3,
            "max_tokens": 2048
        }
    )
    logger.info(f"✅ Bedrock LLM initialized (region: {AWS_REGION})")

    # Create ReAct agent WITHOUT checkpointing for now (will add later)
    _agent = create_react_agent(
        llm,
        TOOLS
    )
    logger.info(f"✅ ReAct agent created with {len(TOOLS)} tools (no checkpointing)")

    return _agent


# Request/Response models
class ChatRequest(BaseModel):
    message: str
    session_id: str


class ChatStreamEvent(BaseModel):
    type: str  # "token", "tool_call", "tool_result", "error", "done"
    content: str
    timestamp: str


async def chat_stream_generator(message: str, session_id: str) -> AsyncIterator[str]:
    """
    Generate SSE stream for chat responses.

    Yields Server-Sent Events in the format:
    data: {"type": "token", "content": "...", "timestamp": "..."}\\n\\n
    """
    try:
        agent = _get_agent()

        # Stream agent execution (no checkpointing for now)
        async for event in agent.astream(
            {"messages": [("user", message)]},
            stream_mode="values"
        ):
            # Extract messages from the event
            messages = event.get("messages", [])
            if not messages:
                continue

            # Get the last message
            last_message = messages[-1]

            # Handle different message types
            if hasattr(last_message, "type"):
                msg_type = last_message.type

                if msg_type == "ai":
                    # AI response token
                    content = getattr(last_message, "content", "")
                    if content:
                        stream_event = ChatStreamEvent(
                            type="token",
                            content=content,
                            timestamp=datetime.utcnow().isoformat()
                        )
                        yield f"data: {stream_event.model_dump_json()}\n\n"

                elif msg_type == "tool":
                    # Tool execution result
                    tool_name = getattr(last_message, "name", "unknown")
                    tool_result = getattr(last_message, "content", "")

                    stream_event = ChatStreamEvent(
                        type="tool_result",
                        content=f"Tool '{tool_name}' executed",
                        timestamp=datetime.utcnow().isoformat()
                    )
                    yield f"data: {stream_event.model_dump_json()}\n\n"

                    # For query_wafer_info tool, send full result data with images
                    if tool_name == "query_wafer_info" and tool_result:
                        try:
                            # Parse tool result JSON
                            result_data = json.loads(tool_result) if isinstance(tool_result, str) else tool_result

                            # Send full data event for frontend visualization
                            data_event = {
                                "type": "tool_result_data",
                                "tool_name": tool_name,
                                "data": result_data,
                                "timestamp": datetime.utcnow().isoformat()
                            }
                            yield f"data: {json.dumps(data_event)}\n\n"
                            logger.info(f"Sent tool_result_data for {tool_name}")
                        except (json.JSONDecodeError, Exception) as e:
                            logger.warning(f"Failed to parse tool result for {tool_name}: {e}")

        # Send completion event
        done_event = ChatStreamEvent(
            type="done",
            content="",
            timestamp=datetime.utcnow().isoformat()
        )
        yield f"data: {done_event.model_dump_json()}\n\n"

    except Exception as e:
        logger.error(f"Error in chat stream: {e}", exc_info=True)

        error_event = ChatStreamEvent(
            type="error",
            content=str(e),
            timestamp=datetime.utcnow().isoformat()
        )
        yield f"data: {error_event.model_dump_json()}\n\n"


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """
    Stream chat responses using Server-Sent Events (SSE).

    Args:
        request: ChatRequest with message and session_id

    Returns:
        StreamingResponse with SSE events

    Example:
        curl -N -X POST http://localhost:8000/chat/stream \\
          -H "Content-Type: application/json" \\
          -d '{"message": "Show me recent open alerts", "session_id": "test-123"}'
    """
    logger.info(f"[{request.session_id}] Chat request: {request.message[:50]}...")

    return StreamingResponse(
        chat_stream_generator(request.message, request.session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent_initialized": _agent is not None,
        "tools_count": len(TOOLS)
    }
