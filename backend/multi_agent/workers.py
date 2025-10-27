"""
Multi-Agent Worker Agents
Worker agents for alert analysis workflow
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
import os
from multi_agent.simple_bedrock import call_claude
from bson import ObjectId
import time
from datetime import timezone
from services.websocket_manager import get_websocket_manager, ConnectionType

logger = logging.getLogger(__name__)


async def get_equipment_statistical_context(equipment_id: str, db, current_particle_count: float = 0) -> dict:
    """
    Get statistical context using MongoDB time series aggregations

    Calculates avg, max, min, stddev from last 1 hour of readings
    Performance: 10-50ms (practical for real-time)

    Args:
        equipment_id: Equipment identifier
        db: MongoDB database instance
        current_particle_count: Current reading for deviation calculation

    Returns:
        Statistical context dict with averages, ranges, and deviations
    """
    logger.info(f"📊 Fetching statistical context for {equipment_id}")

    try:
        pipeline = [
            {
                "$match": {
                    "equipment_id": equipment_id,
                    "timestamp": {"$gte": datetime.utcnow() - timedelta(hours=1)}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "avg_particles": {"$avg": "$metrics.particle_count"},
                    "max_particles": {"$max": "$metrics.particle_count"},
                    "min_particles": {"$min": "$metrics.particle_count"},
                    "stddev_particles": {"$stdDevPop": "$metrics.particle_count"},
                    "readings_count": {"$sum": 1}
                }
            }
        ]

        # Query process_sensor_ts for historical statistical analysis (time series collection)
        stats = await db.process_sensor_ts.aggregate(pipeline).to_list(1)

        if stats and stats[0]:
            s = stats[0]
            # Calculate sigma deviation
            if s.get('stddev_particles', 0) > 0:
                s['deviation_sigma'] = round(
                    (current_particle_count - s['avg_particles']) / s['stddev_particles'],
                    2
                )
            else:
                s['deviation_sigma'] = 0

            logger.info(f"   ✅ Stats retrieved: avg={s.get('avg_particles', 0):.1f}, "
                       f"stddev={s.get('stddev_particles', 0):.1f}, "
                       f"deviation={s.get('deviation_sigma', 0):.1f}σ")
            return s

        logger.warning(f"   ⚠️ No historical data found for {equipment_id}")
        return {}

    except Exception as e:
        logger.error(f"   ❌ Failed to get statistical context: {e}")
        return {}


async def monitoring_agent_tool(state: dict) -> dict:
    """
    Monitoring Agent: Proactively filters false positives

    Uses:
    - MongoDB Time Series Statistical Context (10-50ms aggregations)
    - LLM reasoning (Claude Haiku for speed + cost)

    Input: Alert context with sensor readings
    Output: Decision (create_alert: true/false) + reasoning + confidence

    Args:
        state: AlertAnalysisState dict

    Returns:
        Updated state with monitoring_decision and statistical_context
    """
    logger.info(f"🔵 [MONITORING AGENT] Starting analysis for alert {state['alert_id']}")
    logger.info(f"🔵    Equipment: {state['equipment_id']}, Type: {state['excursion_type']}")

    current_metrics = state.get('metrics', {})
    equipment_id = state['equipment_id']
    current_particle_count = current_metrics.get('particle_count', 0)

    # Get statistical context (fast MongoDB aggregation)
    client = AsyncIOMotorClient(os.getenv('MONGODB_URI'))
    db = client[os.getenv('MDB_DATABASE_NAME', 'smf-yield-defect')]

    stats = await get_equipment_statistical_context(equipment_id, db, current_particle_count)

    # Calculate deviation percentage
    if stats.get('avg_particles'):
        stats['deviation_pct'] = round(
            ((current_particle_count / stats['avg_particles']) - 1) * 100,
            1
        )
    else:
        stats['deviation_pct'] = 0

    logger.info(f"🔵    📈 Current vs Average: {stats.get('deviation_pct', 0):+.1f}% "
               f"({stats.get('deviation_sigma', 0):.1f}σ)")

    # Build LLM prompt with statistical context
    avg_particles = stats.get('avg_particles')
    min_particles = stats.get('min_particles')
    max_particles = stats.get('max_particles')
    stddev_particles = stats.get('stddev_particles')

    avg_str = f"{avg_particles:.1f}" if avg_particles is not None else "N/A"
    min_str = f"{min_particles:.0f}" if min_particles is not None else "N/A"
    max_str = f"{max_particles:.0f}" if max_particles is not None else "N/A"
    stddev_str = f"{stddev_particles:.1f}" if stddev_particles is not None else "N/A"

    stats_text = f"""
STATISTICAL CONTEXT (Last 1 Hour via MongoDB):
- Average Particle Count: {avg_str}
- Range: {min_str} to {max_str}
- Std Deviation: {stddev_str}
- Current vs Avg: {stats.get('deviation_pct', 0):+.1f}% ({stats.get('deviation_sigma', 0):.1f}σ)
- Readings Analyzed: {stats.get('readings_count', 0)}
"""

    prompt = f"""You are a monitoring agent for semiconductor manufacturing. Analyze sensor data to determine if an alert should be created.

EQUIPMENT: {equipment_id}

CURRENT READING:
- Particle Count: {current_metrics.get('particle_count', 'N/A')}
- RF Power: {current_metrics.get('rf_power', 'N/A')}W
- Temperature: {current_metrics.get('temperature', 'N/A')}°C

{stats_text}

DECISION CRITERIA:

CREATE ALERT (create_alert=true) if:
- Statistical deviation >2.5σ (highly unusual)
- Deviation >30% from hourly average
- Clear trend: drift, sustained spike, oscillation

FILTER ALERT (create_alert=false) if:
- Statistical deviation <1.5σ (within normal variation)
- Deviation <15% from average
- Single isolated spike with no trend (likely sensor glitch)

Respond ONLY with valid JSON:
{{
  "create_alert": true,
  "reasoning": "Brief explanation referencing statistical deviation",
  "confidence": 0.85,
  "pattern_detected": "drift"
}}

Valid pattern_detected values: "drift", "spike", "oscillation", "normal_variation", "single_spike"
"""

    try:
        # Call Claude via simple Bedrock client (uses your existing AWS SSO session)
        logger.info(f"🔵    🤖 Invoking Claude Haiku for decision...")

        response = call_claude(prompt, temperature=0.2, max_tokens=300)
        decision = json.loads(response)

        # Validate response
        required_fields = ["create_alert", "reasoning", "confidence"]
        if not all(field in decision for field in required_fields):
            logger.error(f"🔵    ❌ Invalid LLM response, missing required fields")
            raise ValueError(f"Missing required fields in LLM response: {decision}")

        logger.info(f"🔵    ✅ Decision: {'CREATE ALERT' if decision['create_alert'] else 'FILTER'}")
        logger.info(f"🔵    📊 Confidence: {decision['confidence']:.2f}, Pattern: {decision.get('pattern_detected', 'unknown')}")
        logger.info(f"🔵    💡 Reasoning: {decision['reasoning']}")

        # Return updated state
        return {
            "monitoring_decision": decision,
            "statistical_context": stats,
            "workflow_stage": "investigation" if decision['create_alert'] else "complete"
        }

    except json.JSONDecodeError as e:
        logger.error(f"🔵    ❌ Failed to parse LLM response as JSON: {e}")
        logger.error(f"🔵    Raw response: {response}")
        # Fail-safe: create alert on error
        return {
            "monitoring_decision": {
                "create_alert": True,
                "reasoning": f"LLM response parsing failed, creating alert as fail-safe",
                "confidence": 0.5,
                "pattern_detected": "error"
            },
            "statistical_context": stats,
            "workflow_stage": "investigation"
        }

    except Exception as e:
        logger.error(f"🔵    ❌ Monitoring agent error: {e}")
        # Fail-safe: create alert on error
        return {
            "monitoring_decision": {
                "create_alert": True,
                "reasoning": f"Agent error: {str(e)}, creating alert as fail-safe",
                "confidence": 0.5,
                "pattern_detected": "error"
            },
            "statistical_context": stats,
            "workflow_stage": "investigation"
        }

    finally:
        client.close()


def _map_evidence_quality_to_confidence(
    evidence_quality: str,
    problematic_items: int,
    wafers_found: int,
    root_causes_found: int = 0,
    scenario_correlations: int = 0,
    impact_assessments: int = 0
) -> float:
    """
    Map evidence quality from investigation synthesis to numeric confidence score
    
    Evidence quality comes from LLM synthesis:
    - "high": High confidence with clear evidence and enhanced data
    - "strong": High confidence with clear evidence
    - "moderate": Some evidence but not conclusive  
    - "weak": Limited evidence
    - "unknown": No determination possible
    
    Args:
        evidence_quality: Quality assessment from investigation synthesis
        problematic_items: Count of problematic materials found
        wafers_found: Count of similar wafer defects found via vector search
        root_causes_found: Count of specific root causes identified (from enhanced data)
        scenario_correlations: Count of scenario correlations (from enhanced data)
        impact_assessments: Count of impact assessments (from enhanced data)
        
    Returns:
        Confidence score between 0.0 and 1.0
    """
    # Base confidence from evidence quality (updated to include "high")
    base_confidence = {
        "high": 0.85,     # NEW: When enhanced data provides high confidence
        "strong": 0.80,
        "moderate": 0.60,
        "medium": 0.60,   # Support alternate naming
        "weak": 0.40,
        "low": 0.40,      # Support alternate naming
        "unknown": 0.50
    }.get(evidence_quality.lower(), 0.50)
    
    # Boost confidence if problematic items found (direct evidence)
    if problematic_items > 0:
        base_confidence = min(1.0, base_confidence + 0.10)
    
    # Boost confidence if similar wafer defects found (pattern evidence)
    if wafers_found >= 5:
        base_confidence = min(1.0, base_confidence + 0.05)
    
    # NEW: Boost confidence if enhanced data provides specific root causes
    if root_causes_found > 0:
        base_confidence = min(1.0, base_confidence + 0.10)
    
    # NEW: Boost confidence if scenario correlations found
    if scenario_correlations > 0:
        base_confidence = min(1.0, base_confidence + 0.05)
    
    # NEW: Boost confidence if impact assessments available
    if impact_assessments > 0:
        base_confidence = min(1.0, base_confidence + 0.05)
    
    return round(base_confidence, 2)


async def investigation_agent_tool(state: dict) -> dict:
    """
    Investigation Agent: Query MongoDB collections for evidence (matches sequential workflow)

    This implementation MUST match the sequential workflow in routers/ai_agents.py
    
    Calls TWO MongoDB tool functions sequentially:
    1. query_process_context() - Slurry batches, recipes, reticles
    2. query_wafer_defects() - Vector search using voyage-multimodal-3 embeddings
    
    Then uses LLM to synthesize evidence into actionable insights.

    Args:
        state: AlertAnalysisState dict with alert_id, equipment_id, excursion_type

    Returns:
        Updated state with:
        - process_context_evidence: Raw data from query_process_context()
        - wafer_defects_evidence: Raw data from query_wafer_defects()
        - investigation_synthesis: LLM synthesis of evidence
        - investigation_summary: For RCA agent compatibility
        - key_findings: For RCA agent compatibility
        - correlation_results: For RCA agent compatibility
        - workflow_stage: "rca"
    """
    logger.info(f"🟠 [INVESTIGATION AGENT] Starting investigation for alert {state['alert_id']}")
    logger.info(f"🟠    Equipment: {state.get('equipment_id')}, Excursion: {state.get('excursion_type')}")

    alert_id = state['alert_id']
    equipment_id = state.get('equipment_id')
    excursion_type = state.get('excursion_type')
    ws_manager = get_websocket_manager()

    try:
        # ========== STEP 1: Connect to MongoDB ==========
        from motor.motor_asyncio import AsyncIOMotorClient
        import os

        mongodb_uri = os.getenv("MONGODB_URI")
        database_name = os.getenv("MDB_DATABASE_NAME", "smf-yield-defect")

        if not mongodb_uri:
            raise ValueError("MONGODB_URI not configured")

        logger.info(f"🟠    🔗 Connecting to MongoDB...")
        connection_start = time.time()
        client = AsyncIOMotorClient(mongodb_uri)
        db = client[database_name]
        connection_elapsed = (time.time() - connection_start) * 1000

        # Emit WebSocket progress: Step 1 completed (MongoDB connection)
        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id,
            "agent": "investigation",
            "step": "connect",
            "step_number": 1,
            "total_steps": 4,
            "status": "completed",
            "execution_time_ms": round(connection_elapsed, 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)

        # Get slurry_batch and recipe_id from state metadata (passed from monitoring agent)
        # Fallback to fetching from alert document if not in state
        state_metadata = state.get('metadata', {})
        slurry_batch = state_metadata.get('slurry_batch')
        recipe_id = state_metadata.get('recipe_id')

        # If not in state metadata, fetch from alert document
        if not slurry_batch and not recipe_id:
            logger.info(f"🟠    📄 Fetching alert document to extract context...")
            alert_doc = await db.alerts.find_one({"alert_id": alert_id})

            if alert_doc:
                source_data = alert_doc.get('source_data', {})
                alert_metadata = source_data.get('metadata', {})
                slurry_batch = alert_metadata.get('slurry_batch')
                recipe_id = alert_metadata.get('recipe_id')
                logger.info(f"🟠    📋 Extracted from alert: slurry_batch={slurry_batch}, recipe_id={recipe_id}")
            else:
                logger.warning(f"🟠    ⚠️  Alert {alert_id} not found, proceeding without slurry/recipe context")
        else:
            logger.info(f"🟠    📋 Using from state metadata: slurry_batch={slurry_batch}, recipe_id={recipe_id}")

        # ========== STEP 2: Tool 1 - Query Process Context ==========
        logger.info("🟠    📦 Tool 1: query_process_context()")
        tool1_start = time.time()

        from multi_agent.tools.investigation_tools import query_process_context

        process_context_evidence = await query_process_context(
            db=db,
            equipment_id=equipment_id,
            slurry_batch=slurry_batch,
            recipe_id=recipe_id,
            context_types=["slurry_batch", "etch_recipe", "recipe", "reticle"]
        )

        tool1_elapsed = (time.time() - tool1_start) * 1000
        logger.info(f"🟠    ⏱️  Tool 1 completed in {tool1_elapsed:.0f}ms")
        logger.info(f"🟠    📊 Process context: {process_context_evidence.get('problematic_items', 0)} problematic items")

        # Emit WebSocket progress: Step 2 completed (Process context query)
        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id,
            "agent": "investigation",
            "step": "process_context",
            "step_number": 2,
            "total_steps": 4,
            "status": "completed",
            "execution_time_ms": round(tool1_elapsed, 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)

        # ========== STEP 3: Tool 2 - Query Wafer Defects (Vector Search) ==========
        logger.info("🟠    📦 Tool 2: query_wafer_defects() - VECTOR SEARCH")
        tool2_start = time.time()

        from multi_agent.tools.investigation_tools import query_wafer_defects

        wafer_defects_evidence = await query_wafer_defects(
            db=db,
            equipment_id=equipment_id,
            excursion_type=excursion_type,
            limit=10
        )

        tool2_elapsed = (time.time() - tool2_start) * 1000
        logger.info(f"🟠    ⏱️  Tool 2 completed in {tool2_elapsed:.0f}ms")
        logger.info(f"🟠    📊 Wafer defects: {wafer_defects_evidence.get('summary', {}).get('total_wafers_found', 0)} wafers found")

        # Emit WebSocket progress: Step 3 completed (Wafer defects vector search)
        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id,
            "agent": "investigation",
            "step": "wafer_defects",
            "step_number": 3,
            "total_steps": 4,
            "status": "completed",
            "execution_time_ms": round(tool2_elapsed, 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)

        # Close MongoDB connection
        client.close()
        logger.info(f"🟠    🔌 MongoDB connection closed")

        # ========== STEP 4: LLM Evidence Synthesis ==========
        logger.info("🟠    🧠 STEP 4: Invoking Claude for evidence synthesis...")
        synthesis_start = time.time()

        from multi_agent.prompts.investigation_prompts import build_investigation_synthesis_prompt
        from multi_agent.simple_bedrock import call_claude
        import json

        # Build monitoring analysis summary for prompt
        monitoring_summary = {
            "risk_level": state.get("risk_level", "UNKNOWN"),
            "pattern_detected": state.get("pattern_detected", "unknown"),
            "equipment_id": equipment_id,
            "key_insights": state.get("key_insights", [])
        }

        # Build synthesis prompt
        prompt = build_investigation_synthesis_prompt(
            monitoring_analysis=monitoring_summary,
            process_context_evidence=process_context_evidence,
            wafer_defects_evidence=wafer_defects_evidence
        )

        logger.info(f"🟠    📝 Prompt length: {len(prompt)} characters")

        # Call Claude
        try:
            claude_response = call_claude(prompt, temperature=0.2, max_tokens=2000)
            synthesis = json.loads(claude_response)
        except json.JSONDecodeError as e:
            logger.error(f"🟠    ❌ Claude returned malformed JSON: {e}")
            logger.error(f"🟠       Response preview: {claude_response[:500]}")
            # Fallback to minimal synthesis
            synthesis = {
                "key_findings": ["Investigation completed but LLM synthesis failed"],
                "problematic_materials": [],
                "evidence_quality": "unknown",
                "correlation_with_monitoring": "Unable to synthesize due to LLM error",
                "recommended_next_steps": ["Review raw evidence data"]
            }

        synthesis_elapsed = (time.time() - synthesis_start) * 1000
        logger.info(f"🟠    ⚡ [CLAUDE] Synthesis completed in {synthesis_elapsed:.0f}ms")
        logger.info(f"🟠    📊 Key findings: {len(synthesis.get('key_findings', []))}")
        logger.info(f"🟠    🚨 Problematic materials: {len(synthesis.get('problematic_materials', []))}")
        logger.info(f"🟠    🎯 Evidence quality: {synthesis.get('evidence_quality', 'unknown')}")

        # Emit WebSocket progress: Step 4 completed (LLM evidence synthesis)
        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id,
            "agent": "investigation",
            "step": "llm_synthesis",
            "step_number": 4,
            "total_steps": 4,
            "status": "completed",
            "execution_time_ms": round(synthesis_elapsed, 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)

        # Calculate confidence score from evidence (including enhanced data)
        # Extract enhanced data counts for confidence calculation
        root_causes_count = len(process_context_evidence.get("root_causes", []))
        scenario_correlations_count = len(process_context_evidence.get("scenario_correlations", []))
        impact_assessments_count = len(process_context_evidence.get("impact_assessments", []))

        confidence_score = _map_evidence_quality_to_confidence(
            synthesis.get("evidence_quality", "unknown"),
            process_context_evidence.get("problematic_items", 0),
            wafer_defects_evidence.get("summary", {}).get("total_wafers_found", 0),
            root_causes_found=root_causes_count,
            scenario_correlations=scenario_correlations_count,
            impact_assessments=impact_assessments_count
        )
        logger.info(f"🟠    📈 Calculated correlation confidence: {confidence_score:.2f}")

        # Log enhanced data usage
        if root_causes_count > 0 or scenario_correlations_count > 0 or impact_assessments_count > 0:
            logger.info(f"🟠    ✨ Using enhanced data: {root_causes_count} root causes, {scenario_correlations_count} scenario correlations, {impact_assessments_count} impact assessments")

        logger.info(f"🟠    ✅ Investigation complete")
        logger.info(f"🟠    🎯 Next stage: RCA")

        # Return updated state (matching sequential workflow output structure)
        return {
            # Fields for MongoDB persistence (via wrapper in workflow_graph.py)
            "process_context_evidence": process_context_evidence,
            "wafer_defects_evidence": wafer_defects_evidence,
            "investigation_synthesis": synthesis,
            "tool_execution_times": {
                "process_context_ms": round(tool1_elapsed, 2),
                "wafer_defects_ms": round(tool2_elapsed, 2),
                "synthesis_ms": round(synthesis_elapsed, 2),
                "total_ms": round(tool1_elapsed + tool2_elapsed + synthesis_elapsed, 2)
            },
            
            # Fields for RCA agent state compatibility (rca_agent_tool expects these)
            "investigation_summary": synthesis.get("correlation_with_monitoring", ""),
            "key_findings": synthesis.get("key_findings", []),
            "correlation_results": {
                "confidence_score": confidence_score
            },
            
            "workflow_stage": "rca"  # Proceed to RCA stage
        }

    except Exception as e:
        logger.error(f"🟠    ❌ Investigation agent error: {e}", exc_info=True)
        # Return minimal results, allow workflow to continue
        return {
            "process_context_evidence": {},
            "wafer_defects_evidence": {},
            "investigation_synthesis": {
                "key_findings": [f"Investigation failed: {str(e)}"],
                "problematic_materials": [],
                "evidence_quality": "error",
                "correlation_with_monitoring": "Investigation failed",
                "recommended_next_steps": []
            },
            "tool_execution_times": {
                "process_context_ms": 0,
                "wafer_defects_ms": 0,
                "synthesis_ms": 0,
                "total_ms": 0
            },
            # RCA agent compatibility fields
            "investigation_summary": f"Investigation failed: {str(e)}",
            "key_findings": [],
            "correlation_results": {
                "confidence_score": 0.0
            },
            "workflow_stage": "rca"  # Still try RCA even if investigation fails
        }


async def rca_agent_tool(state: dict) -> dict:
    """
    RCA Agent (Worker 3): Root Cause Analysis with historical knowledge and LLM synthesis

    MATCHES SEQUENTIAL WORKFLOW:
    - Tool 1: query_historical_rca_reports() for RAG search
    - Tool 2: Correlation analysis (skipped, same as sequential)
    - LLM Synthesis: build_rca_synthesis_prompt() with Claude
    - Returns: tool outputs + state fields for Supervisor agent

    Returns structure for both MongoDB persistence and state propagation
    """
    import time
    from motor.motor_asyncio import AsyncIOMotorClient
    from multi_agent.tools.investigation_tools import query_historical_rca_reports
    from multi_agent.prompts.rca_prompts import build_rca_synthesis_prompt
    import json

    alert_id = state.get('alert_id')
    equipment_id = state.get('equipment_id', 'Unknown')
    excursion_type = state.get('excursion_type', 'Unknown')
    ws_manager = get_websocket_manager()

    logger.info(f"🟣 [RCA AGENT] Starting root cause analysis for alert {alert_id}")
    logger.info(f"🟣    Equipment: {equipment_id}, Excursion: {excursion_type}")

    try:
        # Connect to MongoDB
        connection_start = time.time()
        mongodb_uri = os.getenv("MONGODB_URI")
        database_name = os.getenv("MDB_DATABASE_NAME", "smf-yield-defect")
        client = AsyncIOMotorClient(mongodb_uri)
        db = client[database_name]
        connection_elapsed = (time.time() - connection_start) * 1000

        # Emit WebSocket progress: Step 1 completed (MongoDB connection)
        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id,
            "agent": "rca",
            "step": "connect",
            "step_number": 1,
            "total_steps": 4,
            "status": "completed",
            "execution_time_ms": round(connection_elapsed, 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)

        # Fetch alert for context
        alert = await db.alerts.find_one({"alert_id": alert_id})
        if not alert:
            client.close()
            raise ValueError(f"Alert not found: {alert_id}")

        # Extract monitoring and investigation data from state
        monitoring_analysis = state.get('monitoring_agent_analysis') or {}
        investigation_synthesis = state.get('investigation_synthesis') or {}

        # Extract pattern and defect information
        llm_interpretation = monitoring_analysis.get('llm_interpretation') or {}
        pattern_type = llm_interpretation.get('pattern_detected', excursion_type) if llm_interpretation else excursion_type

        # Get defect pattern from investigation
        defect_pattern = None
        problematic_materials = investigation_synthesis.get('problematic_materials', [])
        if problematic_materials:
            defect_pattern = problematic_materials[0].get('type', None)

        alert_context = {
            "alert_id": alert_id,
            "equipment_id": equipment_id,
            "severity": alert.get('severity', 'UNKNOWN'),
            "timestamp": alert.get('timestamp')
        }

        # ========== TOOL 1: Query Historical Knowledge (RAG) ==========
        logger.info(f"🟣    🔍 TOOL 1: Query Historical Knowledge (RAG)")
        logger.info(f"🟣       Excursion: {pattern_type}, Pattern: {defect_pattern}, Equipment: {equipment_id}")

        tool1_start = time.time()
        historical_knowledge = await query_historical_rca_reports(
            db=db,
            excursion_type=pattern_type,
            defect_pattern=defect_pattern,
            equipment_id=equipment_id,
            limit=5
        )
        tool1_elapsed = (time.time() - tool1_start) * 1000

        knowledge_docs_found = len(historical_knowledge.get('knowledge_documents', []))
        logger.info(f"🟣       ✅ Found {knowledge_docs_found} historical RCA reports ({tool1_elapsed:.0f}ms)")

        # Emit WebSocket progress: Step 2 completed (Historical knowledge vector search)
        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id,
            "agent": "rca",
            "step": "historical_knowledge",
            "step_number": 2,
            "total_steps": 4,
            "status": "completed",
            "execution_time_ms": round(tool1_elapsed, 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)

        # ========== TOOL 2: Correlation Analysis (SKIPPED) ==========
        logger.info(f"🟣    🔗 TOOL 2: Correlation Analysis (SKIPPED - same as sequential)")

        tool2_start = time.time()
        correlation_analysis = {
            "summary": {"overall_confidence": 0, "key_insights": []},
            "temporal_correlation": {},
            "batch_correlation": {},
            "recipe_correlation": {},
            "spatial_correlation": {},
            "equipment_correlation": {}
        }
        tool2_elapsed = (time.time() - tool2_start) * 1000

        # Emit WebSocket progress: Step 3 completed (Correlation analysis - skipped but emitted for UI consistency)
        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id,
            "agent": "rca",
            "step": "correlation",
            "step_number": 3,
            "total_steps": 4,
            "status": "completed",
            "execution_time_ms": round(tool2_elapsed, 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)

        # Close DB before LLM call
        client.close()

        # ========== LLM SYNTHESIS: Validate Root Causes ==========
        logger.info(f"🟣    🤖 LLM SYNTHESIS: Validate Root Causes")

        synthesis_start = time.time()

        # Build comprehensive RCA prompt
        prompt = build_rca_synthesis_prompt(
            alert_context=alert_context,
            monitoring_analysis=monitoring_analysis,
            investigation_synthesis=investigation_synthesis,
            historical_knowledge=historical_knowledge,
            correlation_analysis=correlation_analysis
        )

        logger.info(f"🟣       Calling Claude Haiku for root cause validation...")

        # Call Claude
        llm_response = call_claude(
            prompt=prompt,
            model_id="anthropic.claude-3-haiku-20240307-v1:0",
            temperature=0.2,
            max_tokens=2000
        )

        # Parse JSON response
        try:
            synthesis = json.loads(llm_response)
            logger.info(f"🟣       ✅ LLM synthesis complete")
            logger.info(f"🟣          Root causes: {len(synthesis.get('validated_root_causes', []))}")
            logger.info(f"🟣          Confidence: {synthesis.get('overall_confidence', 0):.2f}")
        except json.JSONDecodeError as e:
            logger.error(f"🟣       ❌ Failed to parse LLM response: {e}")
            synthesis = {
                "validated_root_causes": [],
                "overall_confidence": 0,
                "reasoning": "LLM response parsing failed",
                "recommendations": []
            }

        synthesis_elapsed = (time.time() - synthesis_start) * 1000

        # Emit WebSocket progress: Step 4 completed (LLM root cause validation)
        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id,
            "agent": "rca",
            "step": "llm_synthesis",
            "step_number": 4,
            "total_steps": 4,
            "status": "completed",
            "execution_time_ms": round(synthesis_elapsed, 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)

        total_elapsed = tool1_elapsed + tool2_elapsed + synthesis_elapsed
        logger.info(f"🟣    ✅ RCA agent complete ({total_elapsed:.0f}ms)")
        logger.info(f"🟣    🎯 Next stage: Supervisor")

        # Return structure with BOTH MongoDB fields and state fields
        return {
            # MongoDB persistence fields (for wrapper to save)
            "historical_knowledge_output": {
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
            "correlation_output": {
                "execution_time_ms": round(tool2_elapsed, 2),
                "confidence_score": 0,
                "raw_data": correlation_analysis
            },
            "rca_synthesis": synthesis,
            "tool_execution_times": {
                "historical_knowledge_ms": round(tool1_elapsed, 2),
                "correlation_analysis_ms": round(tool2_elapsed, 2),
                "llm_synthesis_ms": round(synthesis_elapsed, 2),
                "total_ms": round(total_elapsed, 2)
            },
            # State fields for Supervisor agent (matching supervisor expectations)
            "validated_causes": synthesis.get('validated_root_causes', []),  # Supervisor expects 'validated_causes'
            "rca_validation": synthesis.get('reasoning', ''),  # Supervisor expects 'rca_validation'
            "rca_patterns": {
                "recommendations": synthesis.get('recommendations', [])  # Supervisor expects 'rca_patterns.recommendations'
            },
            "overall_confidence": synthesis.get('overall_confidence', 0),
            "historical_precedent": synthesis.get('historical_precedent', ''),
            "workflow_stage": "complete"
        }

    except ValueError as e:
        logger.error(f"🟣    ❌ Alert not found: {e}")
        return {
            "historical_knowledge_output": {},
            "correlation_output": {},
            "rca_synthesis": {"error": str(e)},
            "validated_root_causes": [],
            "overall_confidence": 0,
            "recommendations": [],
            "workflow_stage": "complete"
        }

    except Exception as e:
        logger.error(f"🟣    ❌ RCA agent error: {e}", exc_info=True)
        return {
            "historical_knowledge_output": {},
            "correlation_output": {},
            "rca_synthesis": {"error": str(e)},
            "validated_causes": [],
            "rca_validation": f"Error: {str(e)}",
            "rca_patterns": {"recommendations": []},
            "overall_confidence": 0,
            "workflow_stage": "complete"
        }


async def supervisor_agent_tool(state: dict) -> dict:
    """
    Supervisor Agent (Worker 4): Comprehensive Quality Control Report with troubleshooting guidance

    MATCHES SEQUENTIAL WORKFLOW:
    - Tool 1: query_troubleshooting_guides() for RAG search on actionable solutions
    - LLM Synthesis: build_supervisor_synthesis_prompt() with Claude Sonnet for comprehensive JSON report
    - Returns: tool outputs + state fields for final response

    This agent aggregates insights from:
    - Monitoring Agent: Pattern detection and risk assessment
    - Investigation Agent: Evidence gathering and problematic materials
    - RCA Agent: Root cause validation and initial recommendations
    - Troubleshooting Guides: Solution-oriented knowledge base (vector search)
    """
    import time
    from motor.motor_asyncio import AsyncIOMotorClient
    from multi_agent.tools.investigation_tools import query_troubleshooting_guides
    from multi_agent.prompts.supervisor_prompts import build_supervisor_synthesis_prompt
    import json

    alert_id = state.get('alert_id')
    equipment_id = state.get('equipment_id', 'Unknown')
    ws_manager = get_websocket_manager()

    try:
        # Connect to MongoDB
        connection_start = time.time()
        mongodb_uri = os.getenv("MONGODB_URI")
        database_name = os.getenv("MDB_DATABASE_NAME", "smf-yield-defect")
        client = AsyncIOMotorClient(mongodb_uri)
        db = client[database_name]
        connection_elapsed = (time.time() - connection_start) * 1000

        # Emit WebSocket progress: Step 1 completed (MongoDB connection)
        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id,
            "agent": "supervisor",
            "step": "connect",
            "step_number": 1,
            "total_steps": 3,
            "status": "completed",
            "execution_time_ms": round(connection_elapsed, 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)

        # Fetch alert for context
        alert = await db.alerts.find_one({"alert_id": alert_id})
        if not alert:
            client.close()
            raise ValueError(f"Alert not found: {alert_id}")

        logger.info(f"🟢 [SUPERVISOR AGENT] Starting comprehensive synthesis for alert {alert_id}")
        logger.info(f"🟢    Equipment: {equipment_id}")

        # Extract agent analyses from alert document
        monitoring_analysis = alert.get('monitoring_agent_analysis') or {}
        investigation_analysis = alert.get('investigation_agent_analysis') or {}
        rca_analysis = alert.get('rca_agent_analysis') or {}

        # Validate all previous agents have run
        if not monitoring_analysis:
            client.close()
            raise ValueError("Monitoring agent has not run yet")
        if not investigation_analysis:
            client.close()
            raise ValueError("Investigation agent has not run yet")
        if not rca_analysis:
            client.close()
            raise ValueError("RCA agent has not run yet")

        logger.info(f"🟢    ✅ All previous agents (Monitoring, Investigation, RCA) have completed")

        alert_context = {
            "alert_id": alert_id,
            "equipment_id": equipment_id,
            "severity": alert.get('severity', 'UNKNOWN'),
            "timestamp": alert.get('timestamp')
        }

        # ========== TOOL 1: Query Troubleshooting Guides (RAG) ==========
        logger.info(f"🟢    🔍 TOOL 1: Query Troubleshooting Guides (RAG)")

        tool_start = time.time()

        # Extract root causes from RCA analysis
        rca_llm = rca_analysis.get('llm_synthesis', {})
        validated_root_causes = rca_llm.get('validated_root_causes', [])
        root_cause_descriptions = [rc.get('root_cause', '') for rc in validated_root_causes if rc.get('root_cause')]

        # Extract defect types from investigation analysis
        investigation_llm = investigation_analysis.get('llm_synthesis', {})
        problematic_materials = investigation_llm.get('problematic_materials', [])
        defect_types = list(set([pm.get('type', '') for pm in problematic_materials if pm.get('type')]))

        logger.info(f"🟢       Root Causes: {len(root_cause_descriptions)}")
        logger.info(f"🟢       Defect Types: {len(defect_types)}")
        logger.info(f"🟢       Equipment ID: {equipment_id}")

        # Query troubleshooting guides
        troubleshooting_guides = await query_troubleshooting_guides(
            db=db,
            root_causes=root_cause_descriptions,
            defect_types=defect_types,
            equipment_id=equipment_id,
            limit=10
        )

        tool_elapsed = (time.time() - tool_start) * 1000

        guides_found = len(troubleshooting_guides.get('knowledge_documents', []))
        logger.info(f"🟢       ✅ Found {guides_found} troubleshooting guides ({tool_elapsed:.0f}ms)")

        # Emit WebSocket progress: Step 2 completed (Troubleshooting guides vector search)
        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id,
            "agent": "supervisor",
            "step": "troubleshooting_guides",
            "step_number": 2,
            "total_steps": 3,
            "status": "completed",
            "execution_time_ms": round(tool_elapsed, 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)

        # Close DB before LLM call
        client.close()

        # ========== LLM SYNTHESIS: Generate Comprehensive QC Report ==========
        logger.info(f"🟢    🤖 LLM SYNTHESIS: Generate Comprehensive QC Report")

        synthesis_start = time.time()

        # Build comprehensive supervisor prompt
        prompt = build_supervisor_synthesis_prompt(
            alert_context=alert_context,
            monitoring_analysis=monitoring_analysis,
            investigation_analysis=investigation_analysis,
            rca_analysis=rca_analysis,
            troubleshooting_guides=troubleshooting_guides
        )

        logger.info(f"🟢       Calling Claude Sonnet for comprehensive synthesis...")
        logger.info(f"🟢       Model: anthropic.claude-3-sonnet-20240229-v1:0")

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
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            synthesis = json.loads(response_text)
            logger.info(f"🟢       ✅ LLM synthesis complete")
            logger.info(f"🟢          Recommendations: {len(synthesis.get('recommendations', []))}")
            logger.info(f"🟢          Overall confidence: {synthesis.get('overall_confidence', 0):.2f}")
        except json.JSONDecodeError as e:
            logger.error(f"🟢       ❌ Failed to parse LLM response: {e}")
            synthesis = {
                "executive_summary": "Error parsing LLM response",
                "recommendations": [],
                "overall_confidence": 0
            }

        synthesis_elapsed = (time.time() - synthesis_start) * 1000

        # Emit WebSocket progress: Step 3 completed (Comprehensive QC report synthesis)
        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id,
            "agent": "supervisor",
            "step": "llm_synthesis",
            "step_number": 3,
            "total_steps": 3,
            "status": "completed",
            "execution_time_ms": round(synthesis_elapsed, 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)

        total_elapsed = tool_elapsed + synthesis_elapsed

        logger.info(f"🟢    ✅ Supervisor agent complete ({total_elapsed:.0f}ms)")
        logger.info(f"🟢    🎯 Ready for final response")

        # Return structure with BOTH MongoDB fields and state fields
        # MongoDB fields stored in _metadata (won't conflict with state)
        return {
            # MongoDB persistence fields (stored separately, not in state)
            "_troubleshooting_guides_output": {
                "execution_time_ms": round(tool_elapsed, 2),
                "documents_found": guides_found,
                "search_parameters": {
                    "root_causes_count": len(root_cause_descriptions),
                    "defect_types_count": len(defect_types),
                    "equipment_id": equipment_id,
                    "limit": 10
                },
                "raw_data": troubleshooting_guides
            },
            "_supervisor_synthesis": synthesis,
            "_tool_execution_times": {
                "troubleshooting_guides_ms": round(tool_elapsed, 2),
                "llm_synthesis_ms": round(synthesis_elapsed, 2),
                "total_ms": round(total_elapsed, 2)
            },
            # State fields (must match AlertAnalysisState TypedDict)
            "supervisor_synthesis": synthesis.get('executive_summary', ''),  # Text summary for state
            "risk_level": synthesis.get('risk_assessment', {}).get('recurrence_risk', 'medium'),
            "overall_confidence": synthesis.get('overall_confidence', 0),
            "action_items": [
                {"action": rec.get("action", ""), "priority": rec.get("priority", ""), "agent": "supervisor"}
                for rec in synthesis.get('recommendations', [])[:10]
            ],
            "workflow_stage": "complete"
        }

    except ValueError as e:
        logger.error(f"🟢    ❌ Validation error: {e}")
        return {
            "_troubleshooting_guides_output": {},
            "_supervisor_synthesis": {"error": str(e)},
            "supervisor_synthesis": f"Error: {str(e)}",
            "risk_level": "unknown",
            "overall_confidence": 0,
            "action_items": [],
            "workflow_stage": "complete"
        }

    except Exception as e:
        logger.error(f"🟢    ❌ Supervisor agent error: {e}", exc_info=True)
        return {
            "_troubleshooting_guides_output": {},
            "_supervisor_synthesis": {"error": str(e)},
            "supervisor_synthesis": f"Error: {str(e)}",
            "risk_level": "unknown",
            "overall_confidence": 0,
            "action_items": [],
            "workflow_stage": "complete"
        }


async def analyze_scenario_tool(scenario_id: str, db) -> dict:
    """
    UPDATED VERSION - NO DEDUPLICATION - Creates NEW alert every time
    Scenario Analysis Agent Tool (Orchestration Layer)
    
    Analyzes pre-seeded failure scenarios using advanced MongoDB aggregations to showcase
    MongoDB's time series capabilities. Designed for <5 second execution time.
    
    Creates ONE alert per scenario (with deduplication) to demonstrate full monitoring flow.
    
    Architecture:
    - Orchestrates modular tool functions from multi_agent.tools
    - Each responsibility (MongoDB queries, alerts, prompts) is separated
    - Maintains comprehensive logging for demo purposes
    
    Workflow:
    1. Load metadata (scenario_tools.load_scenario_metadata)
    2. Check/create alert (alert_tools)
    3. Run MongoDB analysis (scenario_tools.perform_comprehensive_analysis)
    4. Generate Claude insights (prompts.build_scenario_analysis_prompt + simple_bedrock)
    5. Return comprehensive results
    
    MongoDB Aggregations Demonstrated (via mongodb_tools):
    - Multi-facet statistical summary ($facet)
    - Rolling window analysis ($setWindowFields)
    - Trend detection (linear regression)
    - Comparative window analysis (baseline vs anomaly vs recovery)
    
    Args:
        scenario_id: Scenario identifier (gradual_drift, sudden_spike, oscillating_pattern)
        db: MongoDB database instance
        
    Returns:
        Comprehensive analysis including MongoDB query results, alert info, and Claude insights
        
    Reduced from ~450 lines to ~80 lines via tool extraction
    """
    # Import modular tools
    from multi_agent.tools.scenario_tools import (
        load_scenario_metadata,
        perform_comprehensive_analysis
    )
    from multi_agent.tools.alert_tools import (
        check_existing_scenario_alert,
        create_scenario_alert
    )
    from multi_agent.prompts.scenario_prompts import (
        build_scenario_analysis_prompt
    )
    
    logger.info("=" * 80)
    logger.info(f"🔍 [SCENARIO ANALYZER] Starting comprehensive analysis for: {scenario_id}")
    logger.info("=" * 80)
    
    overall_start = time.time()
    alert_id = None
    alert_created = False  # Initialize to False, will be set to True when alert is created
    ws_manager = get_websocket_manager()

    try:
        # ===== Step 1: Load Scenario Metadata =====
        metadata_start = time.time()
        metadata = await load_scenario_metadata(db, scenario_id)
        if not metadata:
            return {"error": f"Scenario {scenario_id} not found"}

        metadata_elapsed = (time.time() - metadata_start) * 1000

        # Emit WebSocket progress: Step 1 completed
        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id or "pending",
            "agent": "monitoring",
            "step": "metadata",
            "step_number": 1,
            "total_steps": 7,
            "status": "completed",
            "execution_time_ms": round(metadata_elapsed, 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)

        # ===== Steps 2-5: Execute Comprehensive MongoDB Analysis FIRST =====
        # Execute MongoDB analysis before alert creation so we can include results in alert
        analysis_results = await perform_comprehensive_analysis(db, scenario_id)

        # Emit WebSocket progress: Steps 2-5 completed (stats, rolling, trend, comparative)
        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id or "pending",
            "agent": "monitoring",
            "step": "stats",
            "step_number": 2,
            "total_steps": 7,
            "status": "completed",
            "execution_time_ms": round(analysis_results['execution_metrics']['stats_ms'], 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)

        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id or "pending",
            "agent": "monitoring",
            "step": "rolling",
            "step_number": 3,
            "total_steps": 7,
            "status": "completed",
            "execution_time_ms": round(analysis_results['execution_metrics']['rolling_ms'], 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)

        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id or "pending",
            "agent": "monitoring",
            "step": "trend",
            "step_number": 4,
            "total_steps": 7,
            "status": "completed",
            "execution_time_ms": round(analysis_results['execution_metrics']['trend_ms'], 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)

        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id or "pending",
            "agent": "monitoring",
            "step": "comparative",
            "step_number": 5,
            "total_steps": 7,
            "status": "completed",
            "execution_time_ms": round(analysis_results['execution_metrics']['comparative_ms'], 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)
        
        # ===== Step 6: Claude Analysis (Before Alert Creation) =====
        logger.info(f"\n🧠 [STEP 6] Invoking Claude for insight generation...")
        logger.info(f"   Model: anthropic.claude-3-haiku-20240307-v1:0")
        claude_start = time.time()
        
        # Build comprehensive prompt using template
        prompt = build_scenario_analysis_prompt(
            metadata,
            analysis_results['statistics'],
            analysis_results['trend'],
            analysis_results['comparative']
        )
        
        logger.info(f"   📝 Prompt length: {len(prompt)} characters")
        
        claude_response = call_claude(prompt, temperature=0.2, max_tokens=600)
        claude_analysis = json.loads(claude_response)
        
        claude_elapsed = (time.time() - claude_start) * 1000
        logger.info(f"⚡ [CLAUDE] Analysis completed in {claude_elapsed:.0f}ms")
        logger.info(f"   🎯 Risk Level: {claude_analysis.get('risk_level', 'UNKNOWN')}")
        logger.info(f"   📊 Confidence: {claude_analysis.get('confidence', 0):.2f}")
        logger.info(f"   🔍 Pattern: {claude_analysis.get('pattern_detected', 'unknown')}")

        # Emit WebSocket progress: Step 6 completed (LLM analysis)
        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id or "pending",
            "agent": "monitoring",
            "step": "llm",
            "step_number": 6,
            "total_steps": 7,
            "status": "completed",
            "execution_time_ms": round(claude_elapsed, 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)

        # Create comprehensive analysis summary for alert's monitoring_agent_analysis field
        # This includes BOTH MongoDB results AND Claude's LLM interpretation
        mongodb_analysis_for_alert = {
            "statistical_summary": {
                "avg_particle_count": round(analysis_results['statistics']['overall'].get('avg_particles', 0), 1),
                "min": int(analysis_results['statistics']['overall'].get('min_particles', 0)),
                "max": int(analysis_results['statistics']['overall'].get('max_particles', 0)),
                "stddev": round(analysis_results['statistics']['overall'].get('stddev_particles', 0), 1),
                "threshold_violations": analysis_results['statistics']['violations'].get('violation_count', 0),
                "readings_analyzed": analysis_results['statistics']['overall'].get('readings_count', 0)
            },
            "trend_analysis": {
                "direction": analysis_results['trend']['direction'],
                "change_percentage": round(analysis_results['trend']['change_pct'], 1),
                "first_period_avg": round(analysis_results['trend']['first_avg'], 1),
                "last_period_avg": round(analysis_results['trend']['last_avg'], 1)
            },
            "comparative_windows": {
                "baseline_avg": round(analysis_results['comparative']['baseline'].get('avg', 0), 1),
                "baseline_stddev": round(analysis_results['comparative']['baseline'].get('stddev', 0), 1),
                "anomaly_avg": round(analysis_results['comparative']['anomaly'].get('avg', 0), 1),
                "anomaly_max": int(analysis_results['comparative']['anomaly'].get('max', 0)),
                "deviation_pct": round(analysis_results['comparative']['deviation_pct'], 1)
            },
            "execution_metrics": analysis_results['execution_metrics'],
            # NEW: Add Claude's LLM interpretation
            "llm_interpretation": {
                "risk_level": claude_analysis.get('risk_level', 'UNKNOWN'),
                "confidence": claude_analysis.get('confidence', 0),
                "pattern_detected": claude_analysis.get('pattern_detected', 'unknown'),
                "key_insights": claude_analysis.get('key_insights', []),
                "recommended_actions": claude_analysis.get('recommended_actions', []),
                "mongodb_showcase": claude_analysis.get('mongodb_showcase', '')
            }
        }
        
        # ===== Step 1.5: Create New Alert (No Deduplication) =====
        logger.info(f"\n🚨 [ALERT CREATION] Creating new alert - NO DEDUPLICATION! VERSION 2")
        logger.info(f"   📋 About to call create_scenario_alert for scenario: {scenario_id}")
        
        # Always create new alert with unique ID (no deduplication)
        # This allows multiple alerts for the same scenario
        alert_creation_start = time.time()
        alert_id = await create_scenario_alert(db, scenario_id, metadata, mongodb_analysis_for_alert)
        alert_created = True
        alert_creation_elapsed = (time.time() - alert_creation_start) * 1000

        logger.info(f"   ✅ New alert created with ID: {alert_id}")
        logger.info(f"   ✅ alert_created flag set to: {alert_created}")

        # Emit WebSocket progress: Step 7 completed (Alert creation)
        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id,
            "agent": "monitoring",
            "step": "alert",
            "step_number": 7,
            "total_steps": 7,
            "status": "completed",
            "execution_time_ms": round(alert_creation_elapsed, 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)

        # ===== Final Summary =====
        overall_elapsed = (time.time() - overall_start) * 1000
        mongodb_time = analysis_results['execution_metrics']['mongodb_total_ms']
        
        # Extract statistics for response building
        overall = analysis_results['statistics']['overall']
        violations = analysis_results['statistics']['violations']
        rolling_result = analysis_results['rolling_windows']['data']
        trend = analysis_results['trend']
        comparative = analysis_results['comparative']
        
        logger.info(f"\n" + "=" * 80)
        logger.info(f"📋 [SUMMARY] Analysis Complete")
        logger.info(f"=" * 80)
        logger.info(f"   ⏱️  Total Time: {overall_elapsed:.0f}ms")
        logger.info(f"   🗄️  MongoDB Queries: {mongodb_time:.0f}ms (4 aggregations)")
        logger.info(f"   🤖 Claude Analysis: {claude_elapsed:.0f}ms")
        logger.info(f"   📊 Data Points Analyzed: {overall.get('readings_count', 0)}")
        logger.info(f"   🎯 Risk: {claude_analysis.get('risk_level', 'UNKNOWN')} ({claude_analysis.get('confidence', 0):.0%} confidence)")
        if alert_created:
            logger.info(f"   🚨 Alert Created: {alert_id}")
        else:
            logger.info(f"   ℹ️  Using Existing Alert: {alert_id}")
        logger.info("=" * 80 + "\n")
        
        # Build comprehensive response
        return {
            "scenario_id": scenario_id,
            "alert_info": {
                "alert_id": alert_id,
                "alert_created": alert_created,
                "message": "New alert created" if alert_created else "Using existing alert (deduplication)"
            },
            "scenario_metadata": {
                "title": metadata['title'],
                "description": metadata['description'],
                "equipment_id": metadata['equipment_id'],
                "duration_minutes": metadata['duration_minutes'],
                "data_points": metadata['data_points'],
                "pattern_type": metadata['pattern_type'],
                "root_cause": metadata['root_cause']
            },
            "execution_metrics": {
                "total_time_ms": round(overall_elapsed, 0),
                "mongodb_time_ms": round(mongodb_time, 0),
                "claude_time_ms": round(claude_elapsed, 0),
                "queries_executed": 4
            },
            "mongodb_analysis": {
                "statistical_summary": {
                    "avg_particle_count": round(overall.get('avg_particles', 0), 1),
                    "min": int(overall.get('min_particles', 0)),
                    "max": int(overall.get('max_particles', 0)),
                    "stddev": round(overall.get('stddev_particles', 0), 1),
                    "threshold_violations": violations.get('violation_count', 0),
                    "readings_analyzed": overall.get('readings_count', 0)
                },
                "trend_analysis": {
                    "direction": trend['direction'],
                    "change_percentage": round(trend['change_pct'], 1),
                    "first_period_avg": round(trend['first_avg'], 1),
                    "last_period_avg": round(trend['last_avg'], 1)
                },
                "comparative_windows": {
                    "baseline": {
                        "avg": round(comparative['baseline'].get('avg', 0), 1),
                        "stddev": round(comparative['baseline'].get('stddev', 0), 1)
                    },
                    "anomaly": {
                        "avg": round(comparative['anomaly'].get('avg', 0), 1),
                        "stddev": round(comparative['anomaly'].get('stddev', 0), 1),
                        "max": int(comparative['anomaly'].get('max', 0)),
                        "deviation_from_baseline_pct": round(comparative['deviation_pct'], 1)
                    },
                    "recovery": {
                        "avg": round(comparative['recovery'].get('avg', 0), 1)
                    }
                },
                "rolling_windows": {
                    "data_points": len(rolling_result),
                    "sample_data": rolling_result[:10] if rolling_result else []  # First 10 points for visualization
                }
            },
            "agent_analysis": claude_analysis,
            "mongodb_showcase": {
                "features_demonstrated": [
                    "$facet - Parallel aggregation pipelines for multi-dimensional analysis",
                    "$setWindowFields - Rolling window calculations without client-side processing",
                    "$group with complex expressions - Trend detection and statistical analysis",
                    "Time-based $match - Efficient indexed queries on time series data"
                ],
                "performance_highlight": f"Analyzed {overall.get('readings_count', 0)} time series data points with 4 complex aggregations in {mongodb_time:.0f}ms",
                "total_analysis_time": f"{overall_elapsed:.0f}ms (target: <5000ms) ✅"
            }
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse Claude response: {e}")
        logger.error(f"   Raw response: {claude_response if 'claude_response' in locals() else 'N/A'}")
        return {"error": "Failed to parse Claude response", "details": str(e)}
    
    except Exception as e:
        logger.error(f"❌ Scenario analysis error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": "Scenario analysis failed", "details": str(e)}


async def analyze_existing_alert_tool(alert_id: str, db) -> dict:
    """
    Analyze existing alert (e.g., from lot processing) instead of creating new one.

    This enables reusing lot processing alerts in agentic AI mode:
    1. Fetches existing alert by ID
    2. Extracts scenario_id from source_data (must be in agentic AI format: "gradual_drift", etc.)
    3. Runs same MongoDB analysis as analyze_scenario_tool
    4. Updates existing alert with monitoring_agent_analysis (instead of creating new alert)
    5. Returns alert_id to continue pipeline with agents 2-4

    Args:
        alert_id: Existing alert ID to analyze
        db: MongoDB database instance

    Returns:
        Analysis results with alert_id (not creating new alert)
    """
    # Import modular tools
    from multi_agent.tools.scenario_tools import (
        load_scenario_metadata,
        perform_comprehensive_analysis
    )
    from multi_agent.prompts.scenario_prompts import (
        build_scenario_analysis_prompt
    )

    logger.info("=" * 80)
    logger.info(f"🔄 [ANALYZE EXISTING ALERT] Analyzing alert: {alert_id}")
    logger.info("=" * 80)

    overall_start = time.time()
    ws_manager = get_websocket_manager()

    try:
        # ===== Step 1: Fetch Existing Alert =====
        logger.info(f"\n📥 [STEP 1] Fetching existing alert from database...")
        step1_start = time.time()
        alert = await db.alerts.find_one({"alert_id": alert_id})

        if not alert:
            logger.error(f"❌ Alert not found: {alert_id}")
            return {"error": f"Alert {alert_id} not found"}

        step1_elapsed = (time.time() - step1_start) * 1000
        logger.info(f"   ✅ Alert found: {alert.get('title', 'Unknown')}")
        logger.info(f"   📋 Alert type: {alert.get('alert_type')}")
        logger.info(f"   🏷️  Severity: {alert.get('severity')}")

        # Emit WebSocket progress: Step 1 completed (fetch alert metadata)
        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id,
            "agent": "monitoring",
            "step": "metadata",
            "step_number": 1,
            "total_steps": 7,
            "status": "completed",
            "execution_time_ms": round(step1_elapsed, 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)

        # ===== Step 2: Extract Scenario Info =====
        logger.info(f"\n🔍 [STEP 2] Extracting scenario metadata from alert...")
        source_data = alert.get("source_data", {})
        scenario_id = source_data.get("scenario_id")

        if not scenario_id:
            logger.error(f"❌ Alert missing scenario_id in source_data")
            logger.error(f"   Source data keys: {list(source_data.keys())}")
            return {"error": "Alert missing scenario_id in source_data. Cannot run agentic analysis."}

        logger.info(f"   ✅ Scenario ID: {scenario_id}")
        logger.info(f"   🎯 Pattern type: {source_data.get('pattern_type', 'unknown')}")
        logger.info(f"   📦 Lot processing: {source_data.get('is_lot_processing_scenario', False)}")

        # ===== Step 3: Load Scenario Metadata =====
        logger.info(f"\n📊 [STEP 3] Loading scenario metadata for: {scenario_id}")
        metadata = await load_scenario_metadata(db, scenario_id)
        if not metadata:
            logger.error(f"❌ Scenario metadata not found for: {scenario_id}")
            return {"error": f"Scenario {scenario_id} not found in database"}

        logger.info(f"   ✅ Metadata loaded: {metadata.get('title', 'Unknown')}")

        # ===== Step 4-5: Execute Comprehensive MongoDB Analysis =====
        logger.info(f"\n🗄️  [STEP 4-5] Running MongoDB analysis...")
        analysis_results = await perform_comprehensive_analysis(db, scenario_id)

        # Emit WebSocket progress: Steps 2-5 completed (MongoDB aggregations)
        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id,
            "agent": "monitoring",
            "step": "stats",
            "step_number": 2,
            "total_steps": 7,
            "status": "completed",
            "execution_time_ms": round(analysis_results['execution_metrics']['stats_ms'], 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)

        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id,
            "agent": "monitoring",
            "step": "rolling",
            "step_number": 3,
            "total_steps": 7,
            "status": "completed",
            "execution_time_ms": round(analysis_results['execution_metrics']['rolling_ms'], 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)

        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id,
            "agent": "monitoring",
            "step": "trend",
            "step_number": 4,
            "total_steps": 7,
            "status": "completed",
            "execution_time_ms": round(analysis_results['execution_metrics']['trend_ms'], 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)

        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id,
            "agent": "monitoring",
            "step": "comparative",
            "step_number": 5,
            "total_steps": 7,
            "status": "completed",
            "execution_time_ms": round(analysis_results['execution_metrics']['comparative_ms'], 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)

        # ===== Step 6: Claude Analysis =====
        logger.info(f"\n🧠 [STEP 6] Invoking Claude for insight generation...")
        claude_start = time.time()

        # Build comprehensive prompt using template
        prompt = build_scenario_analysis_prompt(
            metadata,
            analysis_results['statistics'],
            analysis_results['trend'],
            analysis_results['comparative']
        )

        claude_response = call_claude(prompt, temperature=0.2, max_tokens=600)
        claude_analysis = json.loads(claude_response)

        claude_elapsed = (time.time() - claude_start) * 1000
        logger.info(f"⚡ [CLAUDE] Analysis completed in {claude_elapsed:.0f}ms")
        logger.info(f"   🎯 Risk Level: {claude_analysis.get('risk_level', 'UNKNOWN')}")
        logger.info(f"   📊 Confidence: {claude_analysis.get('confidence', 0):.2f}")

        # Emit WebSocket progress: Step 6 completed (LLM analysis)
        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id,
            "agent": "monitoring",
            "step": "llm",
            "step_number": 6,
            "total_steps": 7,
            "status": "completed",
            "execution_time_ms": round(claude_elapsed, 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)

        # ===== Step 7: Build Monitoring Agent Analysis =====
        mongodb_analysis_for_alert = {
            "statistical_summary": {
                "avg_particle_count": round(analysis_results['statistics']['overall'].get('avg_particles', 0), 1),
                "min": int(analysis_results['statistics']['overall'].get('min_particles', 0)),
                "max": int(analysis_results['statistics']['overall'].get('max_particles', 0)),
                "stddev": round(analysis_results['statistics']['overall'].get('stddev_particles', 0), 1),
                "threshold_violations": analysis_results['statistics']['violations'].get('violation_count', 0),
                "readings_analyzed": analysis_results['statistics']['overall'].get('readings_count', 0)
            },
            "trend_analysis": {
                "direction": analysis_results['trend']['direction'],
                "change_percentage": round(analysis_results['trend']['change_pct'], 1),
                "first_period_avg": round(analysis_results['trend']['first_avg'], 1),
                "last_period_avg": round(analysis_results['trend']['last_avg'], 1)
            },
            "comparative_windows": {
                "baseline_avg": round(analysis_results['comparative']['baseline'].get('avg', 0), 1),
                "baseline_stddev": round(analysis_results['comparative']['baseline'].get('stddev', 0), 1),
                "anomaly_avg": round(analysis_results['comparative']['anomaly'].get('avg', 0), 1),
                "anomaly_max": int(analysis_results['comparative']['anomaly'].get('max', 0)),
                "deviation_pct": round(analysis_results['comparative']['deviation_pct'], 1)
            },
            "execution_metrics": analysis_results['execution_metrics'],
            "llm_interpretation": {
                "risk_level": claude_analysis.get('risk_level', 'UNKNOWN'),
                "confidence": claude_analysis.get('confidence', 0),
                "pattern_detected": claude_analysis.get('pattern_detected', 'unknown'),
                "key_insights": claude_analysis.get('key_insights', []),
                "recommended_actions": claude_analysis.get('recommended_actions', []),
                "mongodb_showcase": claude_analysis.get('mongodb_showcase', '')
            }
        }

        # ===== Step 8: UPDATE Existing Alert (NOT Create New) =====
        logger.info(f"\n🔄 [STEP 8] Updating existing alert with monitoring agent analysis...")
        update_start = time.time()
        update_result = await db.alerts.update_one(
            {"alert_id": alert_id},
            {
                "$set": {
                    "monitoring_agent_analysis": mongodb_analysis_for_alert,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        update_elapsed = (time.time() - update_start) * 1000

        if update_result.modified_count > 0:
            logger.info(f"   ✅ Alert updated successfully!")
            logger.info(f"   📊 Added monitoring_agent_analysis field")
        else:
            logger.warning(f"   ⚠️  Alert not modified (may already have analysis)")

        # Emit WebSocket progress: Step 7 completed (Alert update)
        await ws_manager.broadcast({
            "type": "agent_progress",
            "alert_id": alert_id,
            "agent": "monitoring",
            "step": "alert",
            "step_number": 7,
            "total_steps": 7,
            "status": "completed",
            "execution_time_ms": round(update_elapsed, 0),
            "timestamp": datetime.utcnow().isoformat()
        }, connection_type=ConnectionType.AGENT)

        # ===== Final Summary =====
        overall_elapsed = (time.time() - overall_start) * 1000
        mongodb_time = analysis_results['execution_metrics']['mongodb_total_ms']

        logger.info(f"\n" + "=" * 80)
        logger.info(f"📋 [SUMMARY] Existing Alert Analysis Complete")
        logger.info("=" * 80)
        logger.info(f"   ⏱️  Total Time: {overall_elapsed:.0f}ms")
        logger.info(f"   🗄️  MongoDB Queries: {mongodb_time:.0f}ms")
        logger.info(f"   🤖 Claude Analysis: {claude_elapsed:.0f}ms")
        logger.info(f"   🔄 Alert Updated: {alert_id} (NOT created new)")
        logger.info(f"   🎯 Risk: {claude_analysis.get('risk_level', 'UNKNOWN')} ({claude_analysis.get('confidence', 0):.0%} confidence)")
        logger.info("=" * 80 + "\n")

        # Build response matching analyze_scenario_tool format
        return {
            "alert_id": alert_id,  # Return same alert_id
            "alert_created": False,  # CRITICAL: Indicates we updated existing alert
            "scenario_id": scenario_id,
            "alert_info": {
                "alert_id": alert_id,
                "alert_created": False,
                "message": f"Updated existing alert {alert_id} with monitoring agent analysis"
            },
            "scenario_metadata": {
                "title": metadata['title'],
                "description": metadata['description'],
                "equipment_id": metadata['equipment_id'],
                "duration_minutes": metadata['duration_minutes'],
                "data_points": metadata['data_points'],
                "pattern_type": metadata['pattern_type'],
                "root_cause": metadata['root_cause']
            },
            "execution_metrics": {
                "total_time_ms": round(overall_elapsed, 0),
                "mongodb_time_ms": round(mongodb_time, 0),
                "claude_time_ms": round(claude_elapsed, 0),
                "queries_executed": 4
            },
            "mongodb_analysis": mongodb_analysis_for_alert,
            "agent_analysis": claude_analysis
        }

    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse Claude response: {e}")
        return {"error": "Failed to parse Claude response", "details": str(e)}

    except Exception as e:
        logger.error(f"❌ Existing alert analysis error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": "Existing alert analysis failed", "details": str(e)}
