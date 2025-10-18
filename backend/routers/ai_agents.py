"""
AI Agents Router
Handles AI multi-agent system control endpoints
"""
import logging
from typing import Any
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ai-agents",
    tags=["AI Agents"],
    responses={404: {"description": "Not found"}},
)

# Dependencies (injected from main.py on startup)
use_ai_agents_flag: bool = True


def set_dependencies(use_ai_agents: bool):
    """
    Inject dependencies from main.py
    
    Args:
        use_ai_agents: Feature flag for AI multi-agent system
    """
    global use_ai_agents_flag
    use_ai_agents_flag = use_ai_agents
    logger.info("✅ AI Agents dependencies injected into router")


def get_ai_agents_flag() -> bool:
    """Get current AI agents flag value"""
    return use_ai_agents_flag


def set_ai_agents_flag(enabled: bool) -> bool:
    """Set AI agents flag value and return previous state"""
    global use_ai_agents_flag
    previous_state = use_ai_agents_flag
    use_ai_agents_flag = enabled
    return previous_state


logger.info("📦 AI Agents router initialized")


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.get("/status")
async def get_ai_agents_status():
    """
    Get current AI agent system status
    """
    logger.info(f"📥 GET /ai-agents/status - Fetching AI agent system status")
    
    try:
        status = {
            "enabled": use_ai_agents_flag,
            "agents": ["Monitoring", "Investigation", "RCA", "Supervisor"],
            "model": "anthropic.claude-3-haiku-20240307-v1:0",
            "description": "Multi-agent system for yield defect detection and quality control"
        }
        
        logger.info(f"✅ GET /ai-agents/status - Success: AI agents {'ENABLED' if use_ai_agents_flag else 'DISABLED'}")
        return status
        
    except Exception as e:
        logger.error(f"❌ GET /ai-agents/status - Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/toggle")
async def toggle_ai_agents(enabled: bool):
    """
    Enable or disable AI agent system

    Args:
        enabled: True to enable AI agents, False to disable

    Returns:
        Status confirmation
    """
    logger.info(f"📥 POST /ai-agents/toggle - Request to {'ENABLE' if enabled else 'DISABLE'} AI agents")
    
    try:
        # Get previous state and update flag
        previous_state = set_ai_agents_flag(enabled)
        
        logger.info(f"⚙️ AI agents toggled from {previous_state} to {enabled}")
        logger.info(f"🤖 AI Multi-Agent System: {'ENABLED' if enabled else 'DISABLED'} (toggled via API)")
        
        response = {
            "status": "success",
            "enabled": use_ai_agents_flag,
            "previous_state": previous_state,
            "message": f"AI agents {'enabled' if use_ai_agents_flag else 'disabled'}",
            "agents_affected": ["Monitoring", "Investigation", "RCA", "Supervisor"]
        }
        
        logger.info(f"✅ POST /ai-agents/toggle - Success: AI agents now {'ENABLED' if use_ai_agents_flag else 'DISABLED'}")
        return response
        
    except Exception as e:
        logger.error(f"❌ POST /ai-agents/toggle - Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

