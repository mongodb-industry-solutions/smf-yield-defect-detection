"""
AI Agents Router
Handles AI multi-agent system control endpoints
"""
import logging
import os
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Body
from motor.motor_asyncio import AsyncIOMotorClient
from multi_agent.workers import analyze_scenario_tool
from multi_agent.tools.investigation_tools import query_process_context, query_wafer_defects, query_historical_rca_reports, query_troubleshooting_guides
from multi_agent.prompts.investigation_prompts import build_investigation_synthesis_prompt
from multi_agent.prompts.rca_prompts import build_rca_synthesis_prompt
from multi_agent.prompts.supervisor_prompts import build_supervisor_synthesis_prompt
from multi_agent.simple_bedrock import call_claude
import json
import time

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ai-agents",
    tags=["AI Agents"],
    responses={404: {"description": "Not found"}},
)

# Dependencies (injected from main.py on startup)
auto_excursions_enabled: bool = False  # Default: manual excursions only


def set_dependencies(enable_auto_excursions: bool):
    """
    Inject dependencies from main.py

    Args:
        enable_auto_excursions: Flag to enable/disable automatic excursions in demo mode
    """
    global auto_excursions_enabled
    auto_excursions_enabled = enable_auto_excursions
    logger.info("✅ Auto-excursion dependencies injected into router")


def get_auto_excursions_flag() -> bool:
    """Get current auto-excursions flag value"""
    return auto_excursions_enabled


def set_auto_excursions_flag(enabled: bool) -> bool:
    """Set auto-excursions flag value and return previous state"""
    global auto_excursions_enabled
    previous_state = auto_excursions_enabled
    auto_excursions_enabled = enabled
    return previous_state


logger.info("📦 AI Agents router initialized")


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.get("/status")
async def get_auto_excursions_status():
    """
    Get current auto-excursions status

    When enabled: Demo mode generates automatic excursions
    When disabled: Only manual pattern injection creates excursions
    """
    logger.info(f"📥 GET /ai-agents/status - Fetching auto-excursions status")

    try:
        status = {
            "enabled": auto_excursions_enabled,
            "description": "Automatic excursion generation in demo mode",
            "behavior": {
                "when_enabled": "Demo mode generates random excursions based on probability",
                "when_disabled": "Demo mode runs without automatic excursions (manual injection only)"
            }
        }

        logger.info(f"✅ GET /ai-agents/status - Auto-excursions: {'ENABLED' if auto_excursions_enabled else 'DISABLED'}")
        return status

    except Exception as e:
        logger.error(f"❌ GET /ai-agents/status - Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/toggle")
async def toggle_auto_excursions(enabled: bool):
    """
    Enable or disable automatic excursions in demo mode

    Args:
        enabled: True to enable automatic excursions, False to disable

    Returns:
        Status confirmation
    """
    logger.info(f"📥 POST /ai-agents/toggle - Request to {'ENABLE' if enabled else 'DISABLE'} auto-excursions")

    try:
        # Get previous state and update flag
        previous_state = set_auto_excursions_flag(enabled)

        logger.info(f"⚙️ Auto-excursions toggled from {previous_state} to {enabled}")
        logger.info(f"🎲 Automatic Excursions: {'ENABLED' if enabled else 'DISABLED'} (toggled via API)")

        response = {
            "status": "success",
            "enabled": auto_excursions_enabled,
            "previous_state": previous_state,
            "message": f"Automatic excursions {'enabled' if auto_excursions_enabled else 'disabled'}",
            "behavior": "Demo mode will " + ("generate random excursions" if auto_excursions_enabled else "run without automatic excursions (manual only)")
        }

        logger.info(f"✅ POST /ai-agents/toggle - Auto-excursions now: {'ENABLED' if auto_excursions_enabled else 'DISABLED'}")
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


@router.post("/analyze-alert/{alert_id}")
async def analyze_existing_alert(alert_id: str):
    """
    Analyze existing alert (e.g., from lot processing) instead of creating new one

    This endpoint enables reusing lot processing alerts in agentic AI mode:
    - Fetches existing alert by ID
    - Extracts scenario_id from source_data (must be in format: "gradual_drift", etc.)
    - Runs MongoDB time series analysis
    - Runs Claude AI analysis
    - Updates existing alert with monitoring_agent_analysis
    - Returns alert_id to continue pipeline with agents 2-4

    Workflow after this endpoint:
    1. POST /ai-agents/analyze-alert/{alert_id} (this endpoint)
    2. POST /ai-agents/investigate (with alert_id)
    3. POST /ai-agents/rca/{alert_id}
    4. POST /ai-agents/supervisor/{alert_id}

    Args:
        alert_id: Existing alert ID from lot processing or previous analysis

    Returns:
        Analysis results with alert_id (not creating new alert)
    """
    logger.info("=" * 80)
    logger.info(f"📥 POST /ai-agents/analyze-alert/{alert_id}")
    logger.info("=" * 80)

    try:
        # Import the new worker function
        from multi_agent.workers import analyze_existing_alert_tool

        # Connect to MongoDB
        mongodb_uri = os.getenv("MONGODB_URI")
        database_name = os.getenv("MDB_DATABASE_NAME", "smf-yield-defect")

        if not mongodb_uri:
            raise HTTPException(status_code=500, detail="MONGODB_URI not configured")

        logger.info(f"🔗 Connecting to MongoDB...")
        client = AsyncIOMotorClient(mongodb_uri)
        db = client[database_name]

        # Run analysis on existing alert
        logger.info(f"🚀 Starting analysis for existing alert: {alert_id}")
        result = await analyze_existing_alert_tool(alert_id, db)

        # Close connection
        client.close()
        logger.info(f"🔌 MongoDB connection closed")

        # Check for errors
        if "error" in result:
            logger.error(f"❌ Alert analysis failed: {result['error']}")
            raise HTTPException(status_code=404, detail=result['error'])

        logger.info("=" * 80)
        logger.info(f"✅ POST /ai-agents/analyze-alert/{alert_id} - Success")
        logger.info(f"   🔄 Alert updated (not created new)")
        logger.info(f"   📊 Ready for agents 2-4")
        logger.info("=" * 80)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ POST /ai-agents/analyze-alert/{alert_id} - Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/investigate")
async def investigate_scenario(payload: dict):
    """
    Investigation Agent Endpoint - Query MongoDB collections for evidence

    Takes monitoring agent output and queries relevant MongoDB collections
    to gather manufacturing context evidence. Does NOT perform root cause
    analysis - only gathers structured data.

    Expected payload (from monitoring agent output):
    {
        "scenario_id": "gradual_drift",
        "equipment_id": "CMP_TOOL_01",
        "slurry_batch": "SB_2025_021",  # Optional
        "recipe_id": "ETCH_RECIPE_05",   # Optional
        "alert_id": "alert_12345"        # Optional
    }

    Returns:
        Evidence gathered from MongoDB:
        - process_context: Slurry batches, recipes, reticles
        - (Future) sensor_data: Time series analysis
        - (Future) wafer_defects: Defect pattern analysis
        - (Future) historical_knowledge: RAG knowledge base
    """
    logger.info("=" * 80)
    logger.info("📥 POST /ai-agents/investigate")
    logger.info("=" * 80)
    logger.info(f"📦 Payload: {payload}")

    try:
        # Extract parameters from payload
        scenario_id = payload.get("scenario_id")
        equipment_id = payload.get("equipment_id")
        slurry_batch = payload.get("slurry_batch")
        recipe_id = payload.get("recipe_id")
        alert_id = payload.get("alert_id")

        # Validate required fields
        if not equipment_id:
            raise HTTPException(
                status_code=400,
                detail="equipment_id is required in payload"
            )

        logger.info(f"🔍 Investigation Parameters:")
        logger.info(f"   scenario_id: {scenario_id}")
        logger.info(f"   equipment_id: {equipment_id}")
        logger.info(f"   slurry_batch: {slurry_batch}")
        logger.info(f"   recipe_id: {recipe_id}")
        logger.info(f"   alert_id: {alert_id}")

        # Connect to MongoDB
        mongodb_uri = os.getenv("MONGODB_URI")
        database_name = os.getenv("MDB_DATABASE_NAME", "smf-yield-defect")

        if not mongodb_uri:
            raise HTTPException(status_code=500, detail="MONGODB_URI not configured")

        logger.info(f"🔗 Connecting to MongoDB...")
        client = AsyncIOMotorClient(mongodb_uri)
        db = client[database_name]

        # ========== STEP 1: Query All MongoDB Tools Sequentially ==========
        logger.info("🔧 STEP 1: Calling all investigation tools sequentially...")

        # Tool 1: Query Process Context
        logger.info("   📦 Tool 1: query_process_context()")
        tool1_start = time.time()
        process_context_evidence = await query_process_context(
            db=db,
            equipment_id=equipment_id,
            slurry_batch=slurry_batch,
            recipe_id=recipe_id,
            context_types=["slurry_batch", "etch_recipe", "recipe", "reticle"]
        )
        tool1_elapsed = (time.time() - tool1_start) * 1000
        logger.info(f"   ⏱️  Tool 1 completed in {tool1_elapsed:.0f}ms")

        # Tool 2: Query Wafer Defects (Vector Search)
        logger.info("   📦 Tool 2: query_wafer_defects() - VECTOR SEARCH")
        tool2_start = time.time()

        # Extract excursion_type from payload for defect pattern mapping
        excursion_type = payload.get("excursion_type")

        wafer_defects_evidence = await query_wafer_defects(
            db=db,
            equipment_id=equipment_id,
            excursion_type=excursion_type,
            limit=10
        )
        tool2_elapsed = (time.time() - tool2_start) * 1000
        logger.info(f"   ⏱️  Tool 2 completed in {tool2_elapsed:.0f}ms")

        # TODO: Add more tools in future
        # Tool 3: query_sensor_history()
        # Tool 4: query_historical_knowledge() - moved to RCA agent

        # Close connection
        client.close()
        logger.info(f"🔌 MongoDB connection closed")

        # ========== STEP 2: LLM Evidence Synthesis ==========
        logger.info("🧠 STEP 2: Invoking Claude for evidence synthesis...")
        logger.info(f"   Model: anthropic.claude-3-haiku-20240307-v1:0")

        synthesis_start = time.time()

        # Extract monitoring analysis from payload (or build minimal version)
        monitoring_analysis = {
            "risk_level": payload.get("risk_level", "UNKNOWN"),
            "pattern_detected": payload.get("pattern_detected", "unknown"),
            "equipment_id": equipment_id,
            "key_insights": payload.get("key_insights", [])
        }

        # Build synthesis prompt
        prompt = build_investigation_synthesis_prompt(
            monitoring_analysis=monitoring_analysis,
            process_context_evidence=process_context_evidence,
            wafer_defects_evidence=wafer_defects_evidence
        )

        logger.info(f"   📝 Prompt length: {len(prompt)} characters")

        # Call Claude
        try:
            claude_response = call_claude(prompt, temperature=0.2, max_tokens=2000)
            synthesis = json.loads(claude_response)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Claude returned malformed JSON: {e}")
            logger.error(f"   Response preview: {claude_response[:500]}")
            # Fallback to minimal synthesis
            synthesis = {
                "key_findings": ["Investigation completed but LLM synthesis failed"],
                "problematic_materials": [],
                "evidence_quality": "unknown",
                "correlation_with_monitoring": "Unable to synthesize due to LLM error",
                "recommended_next_steps": ["Review raw evidence data"]
            }

        synthesis_elapsed = (time.time() - synthesis_start) * 1000
        logger.info(f"⚡ [CLAUDE] Synthesis completed in {synthesis_elapsed:.0f}ms")
        logger.info(f"   📊 Key findings: {len(synthesis.get('key_findings', []))}")
        logger.info(f"   🚨 Problematic materials: {len(synthesis.get('problematic_materials', []))}")
        logger.info(f"   🎯 Evidence quality: {synthesis.get('evidence_quality', 'unknown')}")

        # ========== STEP 3: Save to Alert (if alert_id provided) ==========
        if alert_id:
            logger.info(f"\n💾 SAVING TO ALERT DOCUMENT")
            logger.info(f"   Alert ID: {alert_id}")

            investigation_analysis = {
                "tool_outputs": {
                    "process_context": {
                        "execution_time_ms": round(tool1_elapsed, 2),
                        "slurry_batches_found": len(process_context_evidence.get('slurry_batches', [])),
                        "recipes_found": len(process_context_evidence.get('recipes', [])),
                        "reticles_found": len(process_context_evidence.get('reticles', [])),
                        "problematic_items": process_context_evidence.get('problematic_items', 0),
                        "raw_data": {
                            "slurry_batches": process_context_evidence.get('slurry_batches', []),
                            "recipes": process_context_evidence.get('recipes', []),
                            "reticles": process_context_evidence.get('reticles', [])
                        }
                    },
                    "wafer_defects": {
                        "execution_time_ms": round(tool2_elapsed, 2),
                        "wafers_found": wafer_defects_evidence.get('summary', {}).get('total_wafers_found', 0),
                        "avg_yield": wafer_defects_evidence.get('summary', {}).get('avg_yield', 0),
                        "yield_loss": wafer_defects_evidence.get('summary', {}).get('yield_impact', {}).get('yield_loss', 0),
                        "search_type": "vector_similarity",
                        "raw_data": {
                            "wafers": wafer_defects_evidence.get('wafer_defects', [])
                        }
                    }
                },
                "llm_synthesis": synthesis,
                "execution_time_ms": round(tool1_elapsed + tool2_elapsed + synthesis_elapsed, 2)
            }

            # Reconnect to DB (connection was closed earlier)
            client = AsyncIOMotorClient(mongodb_uri)
            db = client[database_name]

            # Update alert document
            update_result = await db.alerts.update_one(
                {"alert_id": alert_id},
                {"$set": {"investigation_agent_analysis": investigation_analysis}}
            )

            # Close connection
            client.close()

            if update_result.modified_count > 0:
                logger.info(f"   ✅ Saved investigation_agent_analysis to alert: {alert_id}")
            elif update_result.matched_count > 0:
                logger.info(f"   ℹ️  Alert {alert_id} already has investigation_agent_analysis")
            else:
                logger.warning(f"   ⚠️  Alert {alert_id} not found in database")

        # ========== STEP 4: Build Complete Response ==========
        response = {
            "investigation_id": f"inv_{scenario_id}_{alert_id}" if scenario_id and alert_id else None,
            "scenario_id": scenario_id,
            "equipment_id": equipment_id,
            "alert_id": alert_id,

            # RAW DATA from tools
            "raw_evidence": {
                "process_context": process_context_evidence,
                "wafer_defects": wafer_defects_evidence,
                # Future tools:
                # "sensor_history": {...}
            },

            # LLM SYNTHESIS
            "investigation_analysis": {
                "key_findings": synthesis.get("key_findings", []),
                "problematic_materials": synthesis.get("problematic_materials", []),
                "evidence_quality": synthesis.get("evidence_quality", "unknown"),
                "correlation_with_monitoring": synthesis.get("correlation_with_monitoring", ""),
                "recommended_next_steps": synthesis.get("recommended_next_steps", [])
            },

            # Quick summary stats
            "summary": {
                "total_slurry_batches": len(process_context_evidence.get("slurry_batches", [])),
                "total_recipes": len(process_context_evidence.get("recipes", [])),
                "total_reticles": len(process_context_evidence.get("reticles", [])),
                "problematic_items_found": process_context_evidence.get("problematic_items", 0),
                "total_wafers_found": wafer_defects_evidence.get("summary", {}).get("total_wafers_found", 0),
                "wafer_avg_yield": wafer_defects_evidence.get("summary", {}).get("avg_yield", 0),
                "wafer_yield_loss": wafer_defects_evidence.get("summary", {}).get("yield_impact", {}).get("yield_loss", 0),
                "execution_time_ms": round(tool1_elapsed + tool2_elapsed + synthesis_elapsed, 2)
            }
        }

        logger.info("=" * 80)
        logger.info("✅ POST /ai-agents/investigate - Success")
        logger.info(f"📊 Investigation Summary:")
        logger.info(f"   Evidence collected:")
        logger.info(f"     - Slurry batches: {response['summary']['total_slurry_batches']}")
        logger.info(f"     - Recipes: {response['summary']['total_recipes']}")
        logger.info(f"     - Reticles: {response['summary']['total_reticles']}")
        logger.info(f"   Problematic items: {response['summary']['problematic_items_found']}")
        logger.info(f"   Key findings: {len(synthesis.get('key_findings', []))}")
        logger.info(f"   Total execution time: {response['summary']['execution_time_ms']:.0f}ms")
        logger.info("=" * 80)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ POST /ai-agents/investigate - Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rca/{alert_id}")
async def run_rca_agent(alert_id: str):
    """
    Run Root Cause Analysis (RCA) Agent

    The RCA agent:
    1. Fetches alert with monitoring and investigation data
    2. Tool 1: Queries historical knowledge (RAG search for similar RCA reports)
    3. Tool 2: Runs correlation engine analysis (temporal, batch, recipe, spatial, equipment)
    4. LLM synthesis: Validates root causes using Claude
    5. Saves rca_agent_analysis to alert document

    Args:
        alert_id: Alert ID to analyze

    Returns:
        RCA analysis with validated root causes, confidence scores, and recommendations

    Example:
        POST /ai-agents/rca/ALT-SCENARIO-20251019203732-68f4feb4bcc9556c01b096b6

        Response:
        {
            "alert_id": "ALT-SCENARIO-...",
            "equipment_id": "CMP_TOOL_01",
            "tool_outputs": {
                "historical_knowledge": {...},
                "correlation_analysis": {...}
            },
            "llm_synthesis": {
                "validated_root_causes": [...],
                "overall_confidence": 0.85,
                "reasoning": "...",
                "recommendations": [...]
            },
            "summary": {
                "execution_time_ms": 15000,
                "root_causes_identified": 2,
                "overall_confidence": 0.85
            }
        }
    """
    logger.info("=" * 80)
    logger.info(f"📥 POST /ai-agents/rca/{alert_id} - Running RCA Agent")
    logger.info("=" * 80)

    # if not use_ai_agents_flag:
    #     logger.warning("⚠️  AI agents are disabled - returning mock response")
    #     raise HTTPException(status_code=503, detail="AI agents are disabled")

    try:
        # ========== STEP 1: Fetch Alert and Validate ==========
        logger.info(f"\n📋 STEP 1: FETCH ALERT AND VALIDATE")
        logger.info(f"   Alert ID: {alert_id}")

        mongodb_uri = os.getenv("MONGODB_URI")
        database_name = os.getenv("MDB_DATABASE_NAME", "smf-yield-defect")

        client = AsyncIOMotorClient(mongodb_uri)
        db = client[database_name]

        # Fetch alert
        alert = await db.alerts.find_one({"alert_id": alert_id})

        if not alert:
            client.close()
            logger.error(f"   ❌ Alert not found: {alert_id}")
            raise HTTPException(status_code=404, detail=f"Alert not found: {alert_id}")

        logger.info(f"   ✅ Alert found")
        logger.info(f"   Equipment: {alert.get('equipment_id', 'UNKNOWN')}")
        logger.info(f"   Severity: {alert.get('severity', 'UNKNOWN')}")

        # Validate that monitoring and investigation have run
        monitoring_analysis = alert.get('monitoring_agent_analysis')
        investigation_analysis = alert.get('investigation_agent_analysis')

        if not monitoring_analysis:
            client.close()
            logger.error(f"   ❌ Monitoring agent has not run yet for this alert")
            raise HTTPException(
                status_code=400,
                detail="Monitoring agent must run first. Call POST /ai-agents/analyze-scenario/{scenario_id}"
            )

        if not investigation_analysis:
            client.close()
            logger.error(f"   ❌ Investigation agent has not run yet for this alert")
            raise HTTPException(
                status_code=400,
                detail="Investigation agent must run first. Call POST /ai-agents/investigate"
            )

        logger.info(f"   ✅ Monitoring and investigation agents have completed")

        # Extract context for RCA
        alert_context = {
            "alert_id": alert_id,
            "equipment_id": alert.get('equipment_id'),
            "severity": alert.get('severity'),
            "timestamp": alert.get('timestamp')
        }

        # ========== STEP 2: Tool 1 - Query Historical Knowledge ==========
        logger.info(f"\n🔍 STEP 2: TOOL 1 - QUERY HISTORICAL KNOWLEDGE (RAG)")

        tool1_start = time.time()

        # Extract parameters for historical knowledge search
        # monitoring_analysis structure: {llm_interpretation: {pattern_detected, risk_level, ...}}
        llm_interpretation = monitoring_analysis.get('llm_interpretation', {})
        pattern_type = llm_interpretation.get('pattern_detected', 'unknown')
        equipment_id = alert.get('equipment_id')

        # Get defect pattern from investigation if available
        defect_pattern = None
        investigation_synthesis = investigation_analysis.get('llm_synthesis', {})
        problematic_materials = investigation_synthesis.get('problematic_materials', [])
        if problematic_materials:
            # Use the first problematic material as context
            defect_pattern = problematic_materials[0].get('type', None)

        logger.info(f"   Searching historical knowledge:")
        logger.info(f"   - Excursion Type: {pattern_type}")
        logger.info(f"   - Equipment ID: {equipment_id}")
        logger.info(f"   - Defect Pattern: {defect_pattern or 'Any'}")

        # Use simple direct vector search function
        historical_knowledge = await query_historical_rca_reports(
            db=db,
            excursion_type=pattern_type,
            defect_pattern=defect_pattern,
            equipment_id=equipment_id,
            limit=5
        )

        tool1_end = time.time()
        tool1_elapsed = (tool1_end - tool1_start) * 1000  # Convert to milliseconds

        knowledge_docs_found = len(historical_knowledge.get('knowledge_documents', []))
        logger.info(f"   ✅ Historical knowledge search complete")
        logger.info(f"   Documents found: {knowledge_docs_found}")
        logger.info(f"   Execution time: {tool1_elapsed:.0f}ms")

        # ========== STEP 3: Tool 2 - Correlation Engine Analysis ==========
        # TEMPORARILY DISABLED - Testing historical knowledge tool first
        logger.info(f"\n🔗 STEP 3: TOOL 2 - CORRELATION ENGINE ANALYSIS (SKIPPED)")

        tool2_start = time.time()

        # Mock correlation analysis for now
        correlation_analysis = {
            "summary": {"overall_confidence": 0, "key_insights": []},
            "temporal_correlation": {},
            "batch_correlation": {},
            "recipe_correlation": {},
            "spatial_correlation": {},
            "equipment_correlation": {}
        }

        tool2_end = time.time()
        tool2_elapsed = (tool2_end - tool2_start) * 1000

        correlation_confidence = 0
        logger.info(f"   ⚠️  Correlation analysis skipped (testing historical knowledge only)")
        logger.info(f"   Execution time: {tool2_elapsed:.0f}ms")

        # Close DB connection before LLM call
        client.close()

        # ========== STEP 4: LLM Synthesis - Validate Root Causes ==========
        logger.info(f"\n🤖 STEP 4: LLM SYNTHESIS - VALIDATE ROOT CAUSES")

        synthesis_start = time.time()

        # Build RCA prompt
        prompt = build_rca_synthesis_prompt(
            alert_context=alert_context,
            monitoring_analysis=monitoring_analysis,
            investigation_synthesis=investigation_synthesis,
            historical_knowledge=historical_knowledge,
            correlation_analysis=correlation_analysis
        )

        logger.info(f"   Calling Claude for root cause validation...")

        # Call Claude
        llm_response = call_claude(
            prompt=prompt,
            model_id="anthropic.claude-3-haiku-20240307-v1:0",
            temperature=0.2,
            max_tokens=2000  # Increased for comprehensive RCA response
        )

        # Parse JSON response
        try:
            synthesis = json.loads(llm_response)
            logger.info(f"   ✅ LLM synthesis complete")
            logger.info(f"   Root causes identified: {len(synthesis.get('validated_root_causes', []))}")
            logger.info(f"   Overall confidence: {synthesis.get('overall_confidence', 0):.2f}")
        except json.JSONDecodeError as e:
            logger.error(f"   ❌ Failed to parse LLM response as JSON: {e}")
            logger.error(f"   Raw response: {llm_response}")
            raise HTTPException(status_code=500, detail="LLM response is not valid JSON")

        synthesis_end = time.time()
        synthesis_elapsed = (synthesis_end - synthesis_start) * 1000

        logger.info(f"   Execution time: {synthesis_elapsed:.0f}ms")

        # ========== STEP 5: Save to Alert Document ==========
        logger.info(f"\n💾 STEP 5: SAVE TO ALERT DOCUMENT")
        logger.info(f"   Alert ID: {alert_id}")

        # Build rca_agent_analysis object
        rca_analysis = {
            "tool_outputs": {
                "historical_knowledge": {
                    "execution_time_ms": round(tool1_elapsed, 2),
                    "documents_found": knowledge_docs_found,
                    "search_parameters": {
                        "excursion_type": pattern_type,
                        "defect_pattern": defect_pattern,
                        "equipment_id": equipment_id,
                        "limit": 5
                    },
                    "raw_data": historical_knowledge
                },
                "correlation_analysis": {
                    "execution_time_ms": round(tool2_elapsed, 2),
                    "confidence_score": correlation_confidence,
                    "raw_data": correlation_analysis
                }
            },
            "llm_synthesis": synthesis,
            "execution_time_ms": round(tool1_elapsed + tool2_elapsed + synthesis_elapsed, 2)
        }

        # Reconnect to DB to save
        client = AsyncIOMotorClient(mongodb_uri)
        db = client[database_name]

        # Update alert document
        update_result = await db.alerts.update_one(
            {"alert_id": alert_id},
            {"$set": {"rca_agent_analysis": rca_analysis}}
        )

        # Close connection
        client.close()

        if update_result.modified_count > 0:
            logger.info(f"   ✅ Saved rca_agent_analysis to alert: {alert_id}")
        else:
            logger.warning(f"   ⚠️  Alert not updated (may already have RCA analysis)")

        # ========== STEP 6: Build Response ==========
        response = {
            "alert_id": alert_id,
            "equipment_id": alert_context.get('equipment_id'),
            "tool_outputs": rca_analysis["tool_outputs"],
            "llm_synthesis": synthesis,
            "summary": {
                "execution_time_ms": round(tool1_elapsed + tool2_elapsed + synthesis_elapsed, 2),
                "root_causes_identified": len(synthesis.get('validated_root_causes', [])),
                "overall_confidence": synthesis.get('overall_confidence', 0),
                "recommendations_count": len(synthesis.get('recommendations', []))
            }
        }

        # Log summary
        logger.info("=" * 80)
        logger.info(f"✅ RCA AGENT COMPLETE")
        logger.info(f"   Alert ID: {alert_id}")
        logger.info(f"   Root causes identified: {response['summary']['root_causes_identified']}")
        logger.info(f"   Overall confidence: {response['summary']['overall_confidence']:.2f}")
        logger.info(f"   Total execution time: {response['summary']['execution_time_ms']:.0f}ms")
        logger.info("=" * 80)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ POST /ai-agents/rca/{alert_id} - Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/supervisor/{alert_id}")
async def run_supervisor_agent(alert_id: str):
    """
    Run Supervisor Agent - Generate comprehensive quality control report

    The supervisor agent:
    1. Fetches alert with ALL agent analyses (monitoring, investigation, RCA)
    2. Tool: Queries troubleshooting guides (vector search for actionable guidance)
    3. LLM synthesis: Aggregates insights + generates comprehensive QC report
    4. Saves supervisor_agent_analysis to alert document

    The supervisor synthesizes:
    - Monitoring agent: Pattern detection and risk assessment
    - Investigation agent: Evidence gathering and problematic materials
    - RCA agent: Root cause validation and initial recommendations
    - Troubleshooting guides: Solution-oriented knowledge base

    Args:
        alert_id: Alert ID to analyze

    Returns:
        Comprehensive quality control report with:
        - Executive summary (for management)
        - Cross-agent synthesis
        - Quality control metrics
        - Prioritized recommendations with timelines and ownership
        - Risk assessment
        - Lessons learned

    Example:
        POST /ai-agents/supervisor/ALT-SCENARIO-20251019203732-68f4feb4bcc9556c01b096b6

        Response:
        {
            "alert_id": "ALT-SCENARIO-...",
            "equipment_id": "CMP_TOOL_01",
            "tool_outputs": {
                "troubleshooting_guides": {...}
            },
            "llm_synthesis": {
                "executive_summary": "...",
                "cross_agent_synthesis": {...},
                "quality_control_report": {...},
                "recommendations": [...],
                "risk_assessment": {...},
                "lessons_learned": [...],
                "overall_confidence": 0.92
            },
            "summary": {
                "execution_time_ms": 18000,
                "recommendations_count": 8,
                "overall_confidence": 0.92
            }
        }
    """
    logger.info("=" * 80)
    logger.info(f"📥 POST /ai-agents/supervisor/{alert_id} - Running Supervisor Agent")
    logger.info("=" * 80)

    try:
        # ========== STEP 1: Fetch Alert and Validate ALL Agents ==========
        logger.info(f"\n📋 STEP 1: FETCH ALERT AND VALIDATE ALL AGENTS")
        logger.info(f"   Alert ID: {alert_id}")

        mongodb_uri = os.getenv("MONGODB_URI")
        database_name = os.getenv("MDB_DATABASE_NAME", "smf-yield-defect")

        client = AsyncIOMotorClient(mongodb_uri)
        db = client[database_name]

        # Fetch alert
        alert = await db.alerts.find_one({"alert_id": alert_id})

        if not alert:
            client.close()
            logger.error(f"   ❌ Alert not found: {alert_id}")
            raise HTTPException(status_code=404, detail=f"Alert not found: {alert_id}")

        logger.info(f"   ✅ Alert found")
        logger.info(f"   Equipment: {alert.get('equipment_id', 'UNKNOWN')}")
        logger.info(f"   Severity: {alert.get('severity', 'UNKNOWN')}")

        # Validate that ALL previous agents have completed
        monitoring_analysis = alert.get('monitoring_agent_analysis')
        investigation_analysis = alert.get('investigation_agent_analysis')
        rca_analysis = alert.get('rca_agent_analysis')

        if not monitoring_analysis:
            client.close()
            logger.error(f"   ❌ Monitoring agent has not run yet")
            raise HTTPException(
                status_code=400,
                detail="Monitoring agent must run first. Call POST /ai-agents/analyze-scenario/{scenario_id}"
            )

        if not investigation_analysis:
            client.close()
            logger.error(f"   ❌ Investigation agent has not run yet")
            raise HTTPException(
                status_code=400,
                detail="Investigation agent must run first. Call POST /ai-agents/investigate"
            )

        if not rca_analysis:
            client.close()
            logger.error(f"   ❌ RCA agent has not run yet")
            raise HTTPException(
                status_code=400,
                detail="RCA agent must run first. Call POST /ai-agents/rca/{alert_id}"
            )

        logger.info(f"   ✅ All previous agents (Monitoring, Investigation, RCA) have completed")

        # Extract context for Supervisor
        alert_context = {
            "alert_id": alert_id,
            "equipment_id": alert.get('equipment_id'),
            "severity": alert.get('severity'),
            "timestamp": alert.get('timestamp')
        }

        # ========== STEP 2: Tool - Query Troubleshooting Guides ==========
        logger.info(f"\n🔍 STEP 2: TOOL - QUERY TROUBLESHOOTING GUIDES")

        tool_start = time.time()

        # Extract root causes from RCA analysis
        rca_llm = rca_analysis.get('llm_synthesis', {})
        validated_root_causes = rca_llm.get('validated_root_causes', [])
        root_cause_descriptions = [rc.get('root_cause', '') for rc in validated_root_causes if rc.get('root_cause')]

        # Extract defect types from investigation analysis
        investigation_llm = investigation_analysis.get('llm_synthesis', {})
        problematic_materials = investigation_llm.get('problematic_materials', [])
        defect_types = list(set([pm.get('type', '') for pm in problematic_materials if pm.get('type')]))

        equipment_id = alert.get('equipment_id')

        logger.info(f"   Searching troubleshooting guides:")
        logger.info(f"   - Root Causes: {len(root_cause_descriptions)}")
        logger.info(f"   - Defect Types: {len(defect_types)}")
        logger.info(f"   - Equipment ID: {equipment_id}")

        # Query troubleshooting guides
        troubleshooting_guides = await query_troubleshooting_guides(
            db=db,
            root_causes=root_cause_descriptions,
            defect_types=defect_types,
            equipment_id=equipment_id,
            limit=10
        )

        tool_end = time.time()
        tool_elapsed = (tool_end - tool_start) * 1000

        guides_found = len(troubleshooting_guides.get('knowledge_documents', []))
        logger.info(f"   ✅ Troubleshooting guide search complete")
        logger.info(f"   Guides found: {guides_found}")
        logger.info(f"   Execution time: {tool_elapsed:.0f}ms")

        # Keep DB connection open - we'll need it to save results later

        # ========== STEP 3: LLM Synthesis - Generate Comprehensive Report ==========
        logger.info(f"\n🤖 STEP 3: LLM SYNTHESIS - GENERATE COMPREHENSIVE QC REPORT")

        synthesis_start = time.time()

        # Build supervisor prompt
        prompt = build_supervisor_synthesis_prompt(
            alert_context=alert_context,
            monitoring_analysis=monitoring_analysis,
            investigation_analysis=investigation_analysis,
            rca_analysis=rca_analysis,
            troubleshooting_guides=troubleshooting_guides
        )

        logger.info(f"   Calling Claude Sonnet for comprehensive synthesis...")
        logger.info(f"   Model: anthropic.claude-3-sonnet-20240229-v1:0")

        # Call Claude Sonnet (more capable for comprehensive synthesis)
        llm_response = call_claude(
            prompt=prompt,
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            temperature=0.2,
            max_tokens=4000  # Comprehensive report needs more tokens
        )

        # Parse JSON response (strip markdown code blocks if present)
        try:
            # Remove markdown code blocks if present
            response_text = llm_response.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]  # Remove ```json
            if response_text.startswith("```"):
                response_text = response_text[3:]  # Remove ```
            if response_text.endswith("```"):
                response_text = response_text[:-3]  # Remove trailing ```
            response_text = response_text.strip()

            synthesis = json.loads(response_text)
            logger.info(f"   ✅ LLM synthesis complete")
            logger.info(f"   Recommendations generated: {len(synthesis.get('recommendations', []))}")
            logger.info(f"   Overall confidence: {synthesis.get('overall_confidence', 0):.2f}")
        except json.JSONDecodeError as e:
            logger.error(f"   ❌ Failed to parse LLM response as JSON: {e}")
            logger.error(f"   Raw response preview: {llm_response[:500]}")
            raise HTTPException(status_code=500, detail="LLM response is not valid JSON")

        synthesis_end = time.time()
        synthesis_elapsed = (synthesis_end - synthesis_start) * 1000

        logger.info(f"   Execution time: {synthesis_elapsed:.0f}ms")

        # ========== STEP 4: Save to Alert Document ==========
        logger.info(f"\n💾 STEP 4: SAVE TO ALERT DOCUMENT")
        logger.info(f"   Alert ID: {alert_id}")

        # Build supervisor_agent_analysis object
        supervisor_analysis = {
            "tool_outputs": {
                "troubleshooting_guides": {
                    "execution_time_ms": round(tool_elapsed, 2),
                    "documents_found": guides_found,
                    "search_parameters": {
                        "root_causes_count": len(root_cause_descriptions),
                        "defect_types_count": len(defect_types),
                        "equipment_id": equipment_id,
                        "limit": 10
                    },
                    "raw_data": troubleshooting_guides
                }
            },
            "llm_synthesis": synthesis,
            "execution_time_ms": round(tool_elapsed + synthesis_elapsed, 2)
        }

        # ========== STEP 4: Save to Alert Document ==========
        logger.info(f"\n💾 STEP 4: SAVE TO ALERT DOCUMENT")
        logger.info(f"   Alert ID: {alert_id}")

        # Update alert document (reuse existing db connection)
        update_result = await db.alerts.update_one(
            {"alert_id": alert_id},
            {"$set": {"supervisor_agent_analysis": supervisor_analysis}}
        )

        # Close connection
        client.close()

        if update_result.modified_count > 0:
            logger.info(f"   ✅ Saved supervisor_agent_analysis to alert: {alert_id}")
        else:
            logger.warning(f"   ⚠️  Alert not updated (may already have supervisor analysis)")

        # ========== STEP 5: Build Response ==========
        response = {
            "alert_id": alert_id,
            "equipment_id": alert_context.get('equipment_id'),
            "tool_outputs": supervisor_analysis["tool_outputs"],
            "llm_synthesis": synthesis,
            "summary": {
                "execution_time_ms": round(tool_elapsed + synthesis_elapsed, 2),
                "recommendations_count": len(synthesis.get('recommendations', [])),
                "overall_confidence": synthesis.get('overall_confidence', 0)
            }
        }

        # Log summary
        logger.info("=" * 80)
        logger.info(f"✅ SUPERVISOR AGENT COMPLETE")
        logger.info(f"   Alert ID: {alert_id}")
        logger.info(f"   Recommendations generated: {response['summary']['recommendations_count']}")
        logger.info(f"   Overall confidence: {response['summary']['overall_confidence']:.2f}")
        logger.info(f"   Total execution time: {response['summary']['execution_time_ms']:.0f}ms")
        logger.info("=" * 80)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ POST /ai-agents/supervisor/{alert_id} - Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# LANGGRAPH WORKFLOW ENDPOINTS
# ============================================================================


@router.post("/analyze-workflow/{scenario_id}")
async def analyze_with_langgraph_workflow(
    scenario_id: str,
    request: Optional[Dict] = Body(default=None)
):
    """
    Run full 4-agent pipeline via LangGraph StateGraph (NEW!)

    This endpoint uses LangGraph to orchestrate the entire multi-agent workflow:
    1. Monitoring Agent - Pattern detection and false positive filtering
    2. Investigation Agent - Evidence gathering (conditional, skipped if filtered)
    3. RCA Agent - Root cause analysis with vector search
    4. Supervisor Agent - Comprehensive QC report synthesis

    Can work with:
    - NEW alerts: Creates alert from scenario (default behavior)
    - EXISTING alerts: Uses pre-created alert from lot processing (pass alert_id in body)

    Benefits over manual sequential approach:
    - Automatic state management (no manual state passing)
    - Conditional routing (skips investigation if monitoring filters alert)
    - Built-in observability and debugging
    - Workflow visualization support
    - Pause/resume capabilities (with checkpointing)

    Args:
        scenario_id: Scenario identifier (gradual_drift, sudden_spike, oscillating_pattern)
        request: Optional JSON body with {"alert_id": "existing_alert_id"}

    Returns:
        Complete workflow result with all agent outputs in state
    """
    # Extract optional alert_id from request body
    alert_id_from_request = request.get("alert_id") if request else None

    logger.info("=" * 80)
    logger.info(f"📥 POST /ai-agents/analyze-workflow/{scenario_id} (LangGraph)")
    if alert_id_from_request:
        logger.info(f"   🔄 Using existing alert: {alert_id_from_request}")
    else:
        logger.info(f"   🆕 Will create new alert from scenario")
    logger.info("=" * 80)

    try:
        from multi_agent.workflow_graph import create_alert_workflow
        from multi_agent.alert_analysis_state import create_initial_state

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

        # Load scenario metadata
        logger.info(f"📊 Loading scenario metadata for: {scenario_id}")
        scenario = await db.scenario_metadata.find_one({"scenario_id": scenario_id})

        if not scenario:
            client.close()
            raise HTTPException(
                status_code=404,
                detail=f"Scenario {scenario_id} not found in database"
            )

        # Step 1: Monitoring Agent - either use existing alert or create new one
        if alert_id_from_request:
            # OPTION A: Use existing alert from lot processing
            logger.info(f"🔄 Step 1: Using existing alert: {alert_id_from_request}")

            # Verify alert exists
            existing_alert = await db.alerts.find_one({"alert_id": alert_id_from_request})
            if not existing_alert:
                client.close()
                raise HTTPException(
                    status_code=404,
                    detail=f"Alert {alert_id_from_request} not found in database"
                )

            # Run monitoring analysis on existing alert (updates monitoring_agent_analysis)
            from multi_agent.workers import analyze_existing_alert_tool

            monitoring_start = time.time()
            monitoring_result = await analyze_existing_alert_tool(alert_id_from_request, db)
            monitoring_elapsed = (time.time() - monitoring_start) * 1000

            if "error" in monitoring_result:
                client.close()
                raise HTTPException(status_code=500, detail=monitoring_result["error"])

            alert_id = alert_id_from_request
            logger.info(f"✅ Step 1 complete: Updated existing alert with monitoring analysis")

        else:
            # OPTION B: Create new alert from scenario (current behavior)
            logger.info(f"🆕 Step 1: Creating new alert from scenario...")
            from multi_agent.workers import analyze_scenario_tool

            monitoring_start = time.time()
            monitoring_result = await analyze_scenario_tool(scenario_id, db)
            monitoring_elapsed = (time.time() - monitoring_start) * 1000

            if "error" in monitoring_result:
                client.close()
                raise HTTPException(status_code=500, detail=monitoring_result["error"])

            # Extract alert_id created by monitoring agent
            alert_id = monitoring_result["alert_info"]["alert_id"]
            logger.info(f"✅ Step 1 complete: Alert created in DB: {alert_id}")

        logger.info(f"   Monitoring time: {monitoring_elapsed:.0f}ms")
        logger.info(f"   Alert ID: {alert_id}")

        # Build initial state with alert_id (works for both existing and new alerts)
        logger.info(f"🔧 Building initial state for LangGraph workflow...")
        initial_state = create_initial_state(
            alert_id=alert_id,
            equipment_id=scenario.get('equipment_id', 'CMP_TOOL_01'),
            excursion_type="particle",
            severity="high",
            metrics={"particle_count": 1500},
            metadata={
                "scenario_id": scenario_id,
                "pattern_type": scenario.get('pattern_type', 'unknown'),
                "source": "langgraph_workflow",
                "used_existing_alert": bool(alert_id_from_request),
                # Add slurry_batch and recipe_id for investigation agent
                "slurry_batch": scenario.get('slurry_batch'),
                "recipe_id": scenario.get('recipe_id')
            }
        )

        # Pre-populate monitoring decision from analyze_scenario_tool result
        initial_state["monitoring_decision"] = {
            "create_alert": True,  # Always true since alert was created
            "confidence": monitoring_result["agent_analysis"]["confidence"],
            "pattern_detected": monitoring_result["agent_analysis"]["pattern_detected"],
            "reasoning": str(monitoring_result["agent_analysis"].get("key_insights", []))
        }
        initial_state["workflow_stage"] = "investigation"  # Skip monitoring node

        # Step 2-4: Run LangGraph workflow (Investigation → RCA → Supervisor)
        logger.info(f"🚀 Step 2-4: Creating LangGraph workflow...")
        workflow = create_alert_workflow(start_from="investigation")  # Start from investigation

        logger.info(f"▶️  Executing workflow (3 remaining agents: investigation → rca → supervisor)...")
        workflow_start = time.time()

        # Run the workflow - starts at investigation node
        result = await workflow.ainvoke(initial_state)

        workflow_elapsed = (time.time() - workflow_start) * 1000
        total_elapsed = monitoring_elapsed + workflow_elapsed

        # Close MongoDB connection
        client.close()
        logger.info(f"🔌 MongoDB connection closed")

        # Extract key results from final state
        monitoring_decision = result.get("monitoring_decision", {})
        supervisor_synthesis = result.get("supervisor_synthesis", "")
        overall_confidence = result.get("overall_confidence", 0)
        risk_level = result.get("risk_level", "Unknown")

        # Extract monitoring analysis from monitoring_result (which came from analyze_scenario_tool)
        monitoring_analysis = monitoring_result.get("agent_analysis", {})

        # Debug: Log final state keys
        logger.info(f"🔍 Final state keys: {list(result.keys())}")
        logger.info(f"🔍 risk_level in state: {result.get('risk_level')}")
        logger.info(f"🔍 overall_confidence in state: {result.get('overall_confidence')}")

        logger.info("=" * 80)
        logger.info(f"✅ LANGGRAPH WORKFLOW COMPLETE")
        logger.info(f"   Scenario: {scenario_id}")
        logger.info(f"   Alert ID: {result['alert_id']}")
        logger.info(f"   Workflow Stage: {result.get('workflow_stage', 'unknown')}")
        logger.info(f"   Risk Level: {risk_level}")
        logger.info(f"   Overall Confidence: {overall_confidence:.2f}")
        logger.info(f"   Total Execution Time: {total_elapsed:.0f}ms")
        logger.info(f"      - Monitoring: {monitoring_elapsed:.0f}ms")
        logger.info(f"      - LangGraph (Inv+RCA+Sup): {workflow_elapsed:.0f}ms")
        logger.info("=" * 80)

        # Build comprehensive response
        response = {
            "workflow_type": "langgraph",
            "scenario_id": scenario_id,
            "alert_id": result["alert_id"],
            "used_existing_alert": bool(alert_id_from_request),
            "execution_metrics": {
                "total_time_ms": round(total_elapsed, 0),
                "monitoring_time_ms": round(monitoring_elapsed, 0),
                "workflow_time_ms": round(workflow_elapsed, 0),
                "workflow_engine": "LangGraph StateGraph"
            },
            "monitoring": {
                "pattern_detected": monitoring_analysis.get("pattern_detected", monitoring_decision.get("pattern_detected", "unknown")),
                "confidence": monitoring_analysis.get("confidence", monitoring_decision.get("confidence", 0)),
                "risk_level": monitoring_analysis.get("risk_level", "unknown"),
                "key_insights": monitoring_analysis.get("key_insights", [])[:3]  # Top 3 insights
            },
            "investigation": {
                "key_findings": result.get("key_findings", [])[:3],  # Top 3 findings
                "correlation_confidence": (result.get("correlation_results") or {}).get("confidence_score", 0)
            },
            "rca": {
                "validated_causes": result.get("validated_causes", [])[:3],  # Top 3 causes
                "recommendations_count": len((result.get("rca_patterns") or {}).get("recommendations", []))
            },
            "supervisor": {
                "risk_level": risk_level,
                "overall_confidence": overall_confidence,
                "synthesis": supervisor_synthesis[:500] if supervisor_synthesis else ""  # First 500 chars
            },
            "workflow_stage": result.get("workflow_stage", "unknown"),
            "success": True
        }

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ POST /ai-agents/analyze-workflow/{scenario_id} - Error: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflow/graph")
async def get_workflow_graph():
    """
    Visualize the LangGraph workflow as a graph

    Returns workflow visualization in multiple formats:
    - Mermaid diagram (for rendering in frontend)
    - ASCII diagram (for terminal/logs)

    This helps developers understand the agent flow and conditional routing logic.

    Returns:
        dict: Contains 'mermaid', 'ascii', and 'description' fields
    """
    logger.info("📥 GET /ai-agents/workflow/graph - Fetching workflow visualization")

    try:
        from multi_agent.workflow_graph import get_workflow_visualization

        viz = get_workflow_visualization()

        logger.info("✅ GET /ai-agents/workflow/graph - Visualization generated")
        logger.info(f"   Nodes: 4 agents (monitoring, investigation, rca, supervisor)")
        logger.info(f"   Conditional routing: monitoring → investigation (if create_alert=true)")

        return {
            "workflow_type": "langgraph",
            "visualization": viz,
            "nodes": [
                "monitoring - Pattern detection and false positive filtering",
                "investigation - Evidence gathering and correlation analysis",
                "rca - Root cause analysis with vector search",
                "supervisor - Comprehensive QC report synthesis"
            ],
            "conditional_edges": [
                "monitoring → investigation (if create_alert=true)",
                "monitoring → END (if create_alert=false, filtered)"
            ]
        }

    except Exception as e:
        logger.error(f"❌ GET /ai-agents/workflow/graph - Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
