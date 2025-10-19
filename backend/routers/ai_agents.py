"""
AI Agents Router
Handles AI multi-agent system control endpoints
"""
import logging
import os
from typing import Any
from fastapi import APIRouter, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from multi_agent.workers import analyze_scenario_tool

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


@router.get("/scenarios")
async def list_scenarios():
    """
    List all available pre-seeded failure scenarios for analysis
    
    Returns:
        List of scenario metadata with descriptions and statistics
    """
    logger.info("📥 GET /ai-agents/scenarios - Fetching available scenarios")
    
    try:
        # Connect to MongoDB
        mongodb_uri = os.getenv("MONGODB_URI")
        database_name = os.getenv("MDB_DATABASE_NAME", "smf-yield-defect")
        
        if not mongodb_uri:
            raise HTTPException(status_code=500, detail="MONGODB_URI not configured")
        
        client = AsyncIOMotorClient(mongodb_uri)
        db = client[database_name]
        
        # Fetch all scenarios
        scenarios = await db.scenario_metadata.find({}).to_list(100)
        
        # Close connection
        client.close()
        
        if not scenarios:
            logger.warning("⚠️ No scenarios found in database. Run: uv run python scripts/seed_scenarios.py")
            return {
                "count": 0,
                "scenarios": [],
                "message": "No scenarios found. Run seed script to load scenario data."
            }
        
        # Convert ObjectId to string for JSON serialization
        for scenario in scenarios:
            if '_id' in scenario:
                scenario['_id'] = str(scenario['_id'])
        
        logger.info(f"✅ GET /ai-agents/scenarios - Found {len(scenarios)} scenarios")
        
        return {
            "count": len(scenarios),
            "scenarios": scenarios,
            "available_ids": [s['scenario_id'] for s in scenarios]
        }
        
    except Exception as e:
        logger.error(f"❌ GET /ai-agents/scenarios - Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-scenario/{scenario_id}")
async def analyze_scenario(scenario_id: str):
    """
    Trigger comprehensive time series analysis for a pre-seeded failure scenario
    
    This endpoint showcases MongoDB's advanced time series capabilities through:
    - Multi-facet statistical aggregations ($facet)
    - Rolling window analysis ($setWindowFields)
    - Trend detection (linear regression using MongoDB expressions)
    - Comparative window analysis (baseline vs anomaly vs recovery)
    - AI-powered insights (Claude Haiku interpretation)
    
    Target execution time: <5 seconds
    
    Args:
        scenario_id: Scenario identifier (gradual_drift, sudden_spike, oscillating_pattern)
        
    Returns:
        Comprehensive analysis including:
        - MongoDB query execution metrics
        - Statistical summary (avg, min, max, stddev)
        - Rolling window analysis results
        - Trend detection (direction, change percentage)
        - Comparative windows (baseline vs anomaly)
        - Claude AI insights and recommendations
        - MongoDB feature showcase
    """
    logger.info("=" * 80)
    logger.info(f"📥 POST /ai-agents/analyze-scenario/{scenario_id}")
    logger.info("=" * 80)
    
    try:
        # Validate scenario_id
        valid_scenarios = ["gradual_drift", "sudden_spike", "oscillating_pattern"]
        if scenario_id not in valid_scenarios:
            logger.warning(f"⚠️ Invalid scenario_id: {scenario_id}")
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid scenario_id. Must be one of: {', '.join(valid_scenarios)}"
            )
        
        # Connect to MongoDB
        mongodb_uri = os.getenv("MONGODB_URI")
        database_name = os.getenv("MDB_DATABASE_NAME", "smf-yield-defect")
        
        if not mongodb_uri:
            raise HTTPException(status_code=500, detail="MONGODB_URI not configured")
        
        logger.info(f"🔗 Connecting to MongoDB...")
        client = AsyncIOMotorClient(mongodb_uri)
        db = client[database_name]
        
        # Run comprehensive scenario analysis
        logger.info(f"🚀 Starting scenario analysis for: {scenario_id}")
        result = await analyze_scenario_tool(scenario_id, db)
        
        # Close connection
        client.close()
        logger.info(f"🔌 MongoDB connection closed")
        
        # Check for errors
        if "error" in result:
            logger.error(f"❌ Scenario analysis failed: {result['error']}")
            raise HTTPException(status_code=404, detail=result['error'])
        
        logger.info("=" * 80)
        logger.info(f"✅ POST /ai-agents/analyze-scenario/{scenario_id} - Success")
        logger.info("=" * 80)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ POST /ai-agents/analyze-scenario/{scenario_id} - Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


