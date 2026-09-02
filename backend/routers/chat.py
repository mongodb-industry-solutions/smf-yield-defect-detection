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

from langchain_aws import ChatBedrockConverse
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.mongodb import MongoDBSaver

from services.rca_chat_tools import TOOLS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Environment variables
MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("MDB_DATABASE_NAME", "smf-yield-defect")
AWS_REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
APP_NAME = os.getenv("APP_NAME", "devrel-fastapi-smf-yield-defect-detection")
COMPLETION_MODEL_ID = os.getenv("COMPLETION_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")

# Global agent instance (initialized on first request)
_agent = None
_checkpointer = None


def _get_agent():
    """Get or create the LangGraph agent instance with MongoDB checkpointing."""
    global _agent, _checkpointer

    if _agent is not None:
        return _agent

    logger.info("Initializing LangGraph ReAct agent...")

    # Initialize LLM (AWS Bedrock via Application Inference Profile)
    llm = ChatBedrockConverse(
        model=COMPLETION_MODEL_ID,
        region_name=AWS_REGION,
        temperature=0.3,
        max_tokens=2048
    )
    logger.info(f"✅ Bedrock LLM initialized (region: {AWS_REGION})")

    # Initialize MongoDB checkpointer for conversation memory
    # Using MongoDBSaver (AsyncMongoDBSaver is deprecated)
    try:
        # Create checkpointer instance - use pymongo.MongoClient, not motor
        from pymongo import MongoClient
        
        mongo_client = MongoClient(MONGODB_URI, appname=APP_NAME)
        _checkpointer = MongoDBSaver(
            mongo_client,  # pymongo client (not motor)
            DATABASE_NAME,  # db_name (positional)
        )
        logger.info(f"✅ MongoDB checkpointer initialized (database: {DATABASE_NAME})")
    except Exception as e:
        logger.warning(f"⚠️ Failed to initialize checkpointer: {e}")
        logger.warning(f"⚠️ Error details: {type(e).__name__}")
        logger.warning("⚠️ Continuing without conversation memory (agent will work but won't remember context)")
        _checkpointer = None

    # Create ReAct agent WITH checkpointing (if available)
    _agent = create_react_agent(
        llm,
        TOOLS,
        checkpointer=_checkpointer  # Will be None if checkpointing failed
    )
    
    if _checkpointer:
        logger.info(f"✅ ReAct agent created with {len(TOOLS)} tools and MongoDB checkpointing")
    else:
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
    Generate SSE stream for chat responses with conversation memory.

    Yields Server-Sent Events in the format:
    data: {"type": "token", "content": "...", "timestamp": "..."}\\n\\n
    """
    try:
        agent = _get_agent()

        # Configure thread for checkpointing (enables conversation memory)
        config = {
            "configurable": {
                "thread_id": session_id,  # Use session_id as thread_id
                "checkpoint_ns": "rca_chat"  # Namespace for organization
            }
        }

        # Load previous conversation history from checkpoint (NEW - ENABLES MULTI-TURN MEMORY)
        previous_messages = []
        if _checkpointer is not None:
            try:
                checkpoint = await _checkpointer.aget_tuple(config)
                if checkpoint and checkpoint.checkpoint:
                    channel_values = checkpoint.checkpoint.get("channel_values", {})
                    previous_messages = channel_values.get("messages", [])
                    logger.info(f"[{session_id}] Loaded {len(previous_messages)} previous messages from checkpoint")
            except Exception as e:
                logger.warning(f"[{session_id}] Failed to load checkpoint history: {e}")
                # Continue without history - don't fail the request

        # Stream agent execution WITH config for memory
        async for event in agent.astream(
            {"messages": [("user", message)]},
            config=config,  # Pass config for checkpointing
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
                    # ChatBedrockConverse returns content as a list of blocks
                    # (e.g. [{"type": "text", "text": "..."}, {"type": "tool_use", ...}])
                    # rather than a plain string, so extract just the text parts.
                    raw_content = getattr(last_message, "content", "")
                    if isinstance(raw_content, list):
                        content = "".join(
                            block.get("text", "")
                            for block in raw_content
                            if isinstance(block, dict) and block.get("type") == "text"
                        )
                    else:
                        content = raw_content
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

                    # For vector_search_knowledge_base tool, send full result data
                    if tool_name == "vector_search_knowledge_base" and tool_result:
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
        "checkpointing_enabled": _checkpointer is not None,
        "tools_count": len(TOOLS)
    }


# ============================================================================
# Phase 2: Conversation History Endpoints
# ============================================================================

@router.get("/history/{session_id}")
async def get_conversation_history(session_id: str, limit: int = 50):
    """
    Get conversation history for a session from checkpointer.

    Args:
        session_id: Session/thread identifier
        limit: Maximum number of messages to return (default 50)

    Returns:
        Conversation history with messages and metadata

    Example:
        GET /chat/history/test-123
    """
    try:
        global _checkpointer

        # Ensure checkpointer is initialized
        if _checkpointer is None:
            _get_agent()  # This initializes checkpointer

        # If still None, checkpointing is not available
        if _checkpointer is None:
            return {
                "session_id": session_id,
                "messages": [],
                "checkpointing_enabled": False,
                "message": "Conversation memory not available (checkpointing disabled)"
            }

        # Get checkpoint data using async methods
        config = {"configurable": {"thread_id": session_id}}
        checkpoint = await _checkpointer.aget_tuple(config)

        if not checkpoint or checkpoint.checkpoint is None:
            return {
                "session_id": session_id,
                "messages": [],
                "checkpointing_enabled": True,
                "message": "No conversation history found for this session"
            }

        # Extract messages from checkpoint
        messages = []
        channel_values = checkpoint.checkpoint.get("channel_values", {})
        if "messages" in channel_values:
            for msg in channel_values["messages"]:
                message_data = {
                    "type": msg.__class__.__name__,
                    "content": getattr(msg, "content", None)
                }

                # Include tool calls if present
                if hasattr(msg, "tool_calls"):
                    message_data["tool_calls"] = msg.tool_calls

                messages.append(message_data)


        return {
            "session_id": session_id,
            "messages": messages[-limit:],  # Return last N messages
            "total_messages": len(messages),
            "checkpointing_enabled": True,
            "checkpoint_id": str(checkpoint.config.get("configurable", {}).get("checkpoint_id", ""))
        }

    except Exception as e:
        logger.error(f"Error fetching conversation history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear/{session_id}")
async def clear_conversation(session_id: str):
    """
    Clear conversation history for a session.

    Args:
        session_id: Session/thread identifier to clear

    Returns:
        Deletion result with count of removed checkpoints

    Example:
        DELETE /chat/clear/test-123
    """
    try:
        # Use pymongo for synchronous deletion (MongoDBSaver uses pymongo, not motor)
        from pymongo import MongoClient

        # Connect to MongoDB directly to clear checkpoint data
        client = MongoClient(MONGODB_URI, appname=APP_NAME)
        db = client[DATABASE_NAME]
        collection = db["checkpoints"]  # Default collection name for MongoDBSaver

        # Delete checkpoints for this thread_id
        # LangGraph stores checkpoints with thread_id in the config
        result = collection.delete_many({"thread_id": session_id})

        client.close()

        return {
            "session_id": session_id,
            "deleted_count": result.deleted_count,
            "status": "cleared",
            "message": f"Conversation history cleared ({result.deleted_count} checkpoints removed)"
        }

    except Exception as e:
        logger.error(f"Error clearing session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
