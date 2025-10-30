"""
Alerts Router
Handles all alert-related endpoints for the yield defect detection system
"""
import logging
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Body

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/alerts",
    tags=["Alerts"],
    responses={404: {"description": "Not found"}},
)

# Dependencies (injected from main.py on startup)
alert_manager_instance = None
convert_objectids_func = None
mongodb_client_instance = None
use_ai_agents_flag = True
mdb_database_name = None
mdb_timeseries_collection = None

# Will be imported when needed
AlertSeverity = None
AlertType = None
AlertStatus = None


def set_dependencies(alert_manager, convert_func, mongodb_client=None, use_ai_agents=True,
                     db_name=None, timeseries_collection=None):
    """
    Inject dependencies from main.py

    Args:
        alert_manager: AlertManager instance for alert operations
        convert_func: Function to convert ObjectIds to strings
        mongodb_client: Optional MongoDB client for direct queries
        use_ai_agents: Feature flag for AI multi-agent system
        db_name: MongoDB database name
        timeseries_collection: MongoDB timeseries collection name
    """
    global alert_manager_instance, convert_objectids_func, mongodb_client_instance
    global use_ai_agents_flag
    global mdb_database_name, mdb_timeseries_collection
    global AlertSeverity, AlertType, AlertStatus

    alert_manager_instance = alert_manager
    convert_objectids_func = convert_func
    mongodb_client_instance = mongodb_client
    use_ai_agents_flag = use_ai_agents
    mdb_database_name = db_name
    mdb_timeseries_collection = timeseries_collection
    
    # Import enums from alert_manager's module
    if alert_manager:
        from services.alert_manager import AlertSeverity as AS, AlertType as AT, AlertStatus as ASt
        AlertSeverity = AS
        AlertType = AT
        AlertStatus = ASt
    
    logger.info("✅ Alerts dependencies injected into router")


def get_alert_manager():
    """Get alert manager with error handling"""
    if alert_manager_instance is None:
        logger.error("❌ Alert manager not initialized")
        raise HTTPException(
            status_code=503, 
            detail="Alert manager not initialized. Start monitoring first."
        )
    return alert_manager_instance


def convert_objectids(data):
    """Convert ObjectIds in data using injected function"""
    if convert_objectids_func is None:
        logger.error("❌ convert_objectids function not initialized")
        raise HTTPException(status_code=500, detail="Conversion function not available")
    return convert_objectids_func(data)


logger.info("📦 Alerts router initialized")


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.get("/statistics/summary")
async def get_alert_statistics(
    time_window_hours: int = Query(24, description="Time window in hours for statistics")
):
    """
    Get alert statistics for dashboard
    """
    logger.info(f"📥 GET /alerts/statistics/summary - Time window: {time_window_hours}h")
    
    try:
        logger.debug(f"🔧 Fetching alert statistics for {time_window_hours} hour window")
        
        # Get alert manager instance
        alert_manager = get_alert_manager()
        
        # Fetch statistics
        stats = alert_manager.get_alert_statistics(time_window_hours)
        
        logger.info(f"✅ GET /alerts/statistics/summary - Success: Retrieved statistics for {time_window_hours}h window")
        logger.debug(f"📊 Statistics summary: {len(stats)} metrics returned")
        
        return stats
        
    except HTTPException:
        logger.warning(f"⚠️ GET /alerts/statistics/summary - HTTPException raised")
        raise
    except Exception as e:
        logger.error(f"❌ GET /alerts/statistics/summary - Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def get_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity: critical, high, medium, low"),
    alert_type: Optional[str] = Query(None, description="Filter by alert type"),
    equipment_id: Optional[str] = Query(None, description="Filter by equipment ID"),
    limit: int = Query(100, description="Maximum number of alerts to return")
):
    """
    Get active alerts with optional filtering
    """
    logger.info(f"📥 GET /alerts - Filters: severity={severity}, type={alert_type}, equipment={equipment_id}, limit={limit}")
    
    try:
        logger.debug(f"🔧 Getting active alerts with filters")
        
        # Get alert manager instance
        alert_manager = get_alert_manager()
        
        # Convert string parameters to enums if provided
        severity_enum = AlertSeverity(severity) if severity else None
        alert_type_enum = AlertType(alert_type) if alert_type else None
        
        if severity_enum:
            logger.debug(f"🔍 Severity filter: {severity} -> {severity_enum}")
        if alert_type_enum:
            logger.debug(f"🔍 Alert type filter: {alert_type} -> {alert_type_enum}")
        
        # Fetch alerts with filters (no time filter)
        alerts = alert_manager.get_active_alerts(
            severity=severity_enum,
            alert_type=alert_type_enum,
            equipment_id=equipment_id,
            limit=limit,
            minutes_ago=None  # Always fetch all alerts regardless of age
        )

        # Convert ObjectIds for JSON serialization
        alerts = convert_objectids(alerts)
        
        logger.debug(f"📊 Retrieved {len(alerts)} alerts before compatibility mapping")

        # Add backward compatibility mapping for frontend
        for alert in alerts:
            # Map new field names to old ones for frontend compatibility
            if 'correlation_analysis' in alert:
                alert['correlation_data'] = alert['correlation_analysis']  # Frontend expects this

            # Handle RCA fields - could be either rca_analysis (new) or rca_hints (old)
            rca_data = None
            if 'rca_analysis' in alert:
                rca_data = alert['rca_analysis']
                alert['rca_hints'] = rca_data  # Add old name for compatibility
            elif 'rca_hints' in alert:
                rca_data = alert['rca_hints']
                alert['rca_analysis'] = rca_data  # Add new name for consistency

            # Extract recommendations for backward compatibility
            if rca_data and 'recommendations' in rca_data:
                alert['rca_recommendations'] = rca_data['recommendations']

        logger.info(f"✅ GET /alerts - Success: Retrieved {len(alerts)} alerts")
        
        return {
            "count": len(alerts),
            "alerts": alerts
        }
        
    except ValueError as ve:
        logger.warning(f"⚠️ GET /alerts - Invalid parameter: {ve}")
        raise HTTPException(status_code=400, detail=f"Invalid parameter value: {ve}")
    except HTTPException:
        logger.warning(f"⚠️ GET /alerts - HTTPException raised")
        raise
    except Exception as e:
        logger.error(f"❌ GET /alerts - Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analyzed")
async def get_analyzed_alerts(
    limit: int = Query(50, description="Maximum number of analyzed alerts to return")
):
    """
    Get alerts that have been analyzed by AI agents
    Returns alerts with monitoring_agent_analysis, investigation_agent_analysis, rca_agent_analysis, and supervisor_agent_analysis
    """
    logger.info(f"📥 GET /alerts/analyzed - Fetching alerts with AI agent analysis (limit={limit})")

    try:
        # Access MongoDB directly to query for alerts with agent analysis
        if mongodb_client_instance is None or mdb_database_name is None:
            logger.error("❌ MongoDB client not initialized")
            raise HTTPException(status_code=503, detail="Database not available")

        db = mongodb_client_instance[mdb_database_name]
        alerts_collection = db['alerts']

        # Query for unresolved scenario_analysis alerts that have at least one agent analysis field
        query = {
            "alert_type": "scenario_analysis",
            "status": {"$ne": "resolved"},
            "$or": [
                {"monitoring_agent_analysis": {"$exists": True, "$ne": None}},
                {"investigation_agent_analysis": {"$exists": True, "$ne": None}},
                {"rca_agent_analysis": {"$exists": True, "$ne": None}},
                {"supervisor_agent_analysis": {"$exists": True, "$ne": None}}
            ]
        }

        # Fetch alerts sorted by timestamp (most recent first)
        analyzed_alerts = await alerts_collection.find(query).sort("timestamp", -1).limit(limit).to_list(length=limit)

        logger.debug(f"📊 Found {len(analyzed_alerts)} analyzed alerts")

        # Convert ObjectIds for JSON serialization
        analyzed_alerts = convert_objectids(analyzed_alerts)

        # Transform alerts to include summary info for frontend display
        alert_summaries = []
        for alert in analyzed_alerts:
            summary = {
                "alert_id": alert.get("alert_id"),
                "scenario_id": alert.get("scenario_id"),
                "timestamp": alert.get("timestamp"),
                "equipment_id": alert.get("equipment_id"),
                "severity": alert.get("severity"),
                "alert_type": alert.get("alert_type"),
                "status": alert.get("status"),
                "has_monitoring": bool(alert.get("monitoring_agent_analysis")),
                "has_investigation": bool(alert.get("investigation_agent_analysis")),
                "has_rca": bool(alert.get("rca_agent_analysis")),
                "has_supervisor": bool(alert.get("supervisor_agent_analysis")),
                # Include brief preview for dropdown display
                "preview": {
                    "risk_level": None,
                    "pattern": None,
                    "key_finding": None
                }
            }

            # Extract preview data from monitoring agent if available
            if alert.get("monitoring_agent_analysis"):
                mon_analysis = alert["monitoring_agent_analysis"]
                if "output" in mon_analysis and "llm_interpretation" in mon_analysis["output"]:
                    llm = mon_analysis["output"]["llm_interpretation"]
                    summary["preview"]["risk_level"] = llm.get("risk_level")
                    summary["preview"]["pattern"] = llm.get("pattern_detected")
                    if llm.get("key_insights") and len(llm["key_insights"]) > 0:
                        summary["preview"]["key_finding"] = llm["key_insights"][0]

            alert_summaries.append(summary)

        logger.info(f"✅ GET /alerts/analyzed - Success: Retrieved {len(alert_summaries)} analyzed alerts")

        return {
            "count": len(alert_summaries),
            "alerts": alert_summaries
        }

    except HTTPException:
        logger.warning(f"⚠️ GET /alerts/analyzed - HTTPException raised")
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching analyzed alerts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{alert_id}")
async def get_alert_details(alert_id: str):
    """
    Get detailed information about a specific alert
    """
    logger.info(f"📥 GET /alerts/{alert_id} - Fetching alert details")
    
    try:
        logger.debug(f"🔧 Getting alert details for: {alert_id}")
        
        # Get alert manager instance
        alert_manager = get_alert_manager()
        
        # Fetch alert
        alert = alert_manager.get_alert_by_id(alert_id)
        
        if not alert:
            logger.warning(f"⚠️ GET /alerts/{alert_id} - Alert not found")
            raise HTTPException(status_code=404, detail="Alert not found")
        
        logger.debug(f"🔧 Fetching alert history for: {alert_id}")
        
        # Get alert history
        history = alert_manager.get_alert_history(alert_id)

        # Convert ObjectIds
        alert = convert_objectids(alert)
        history = convert_objectids(history)
        
        logger.debug(f"📊 Alert retrieved with {len(history)} history entries")

        # Add backward compatibility mapping for frontend
        if alert:
            # Map new field names to old ones for frontend compatibility
            if 'correlation_analysis' in alert:
                alert['correlation_data'] = alert['correlation_analysis']

            # Handle RCA fields - could be either rca_analysis (new) or rca_hints (old)
            rca_data = None
            if 'rca_analysis' in alert:
                rca_data = alert['rca_analysis']
                alert['rca_hints'] = rca_data  # Add old name for compatibility
            elif 'rca_hints' in alert:
                rca_data = alert['rca_hints']
                alert['rca_analysis'] = rca_data  # Add new name for consistency

            # Extract recommendations for backward compatibility
            if rca_data and 'recommendations' in rca_data:
                alert['rca_recommendations'] = rca_data['recommendations']

        logger.info(f"✅ GET /alerts/{alert_id} - Success: Retrieved alert with {len(history)} history entries")
        
        return {
            "alert": alert,
            "history": history
        }
        
    except HTTPException:
        logger.warning(f"⚠️ GET /alerts/{alert_id} - HTTPException raised")
        raise
    except Exception as e:
        logger.error(f"❌ GET /alerts/{alert_id} - Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{alert_id}/agent-details")
async def get_alert_agent_details(alert_id: str):
    """
    Get AI agent execution details for a specific alert
    Returns structured data about what each agent did and which collections were accessed
    """
    logger.info(f"📥 GET /alerts/{alert_id}/agent-details - Fetching AI agent details")
    
    try:
        logger.debug(f"🔧 Getting agent details for alert: {alert_id}")
        
        # Get alert manager instance
        alert_manager = get_alert_manager()

        logger.info(f"✅ [ALERT LIFECYCLE] Retrieving agent details for alert {alert_id}")

        # Try to find alert by alert_id first, then by _id (MongoDB ObjectId)
        alert = alert_manager.get_alert_by_id(alert_id)

        if not alert:
            # Try finding by MongoDB _id
            from bson import ObjectId
            logger.debug(f"🔍 Trying to find alert by MongoDB _id: {alert_id}")
            try:
                alert = alert_manager.alerts_collection.find_one({"_id": ObjectId(alert_id)})
            except:
                pass

        if not alert:
            logger.warning(f"⚠️ GET /alerts/{alert_id}/agent-details - Alert not found")
            raise HTTPException(status_code=404, detail="Alert not found")

        # Extract agent data from the alert document
        agents = []

        # Agent 1: Monitoring Agent
        monitoring_agent_analysis = alert.get('monitoring_agent_analysis', {})
        if monitoring_agent_analysis:
            agents.append({
                "id": 1,
                "name": "Monitor",
                "status": "completed",
                "output": monitoring_agent_analysis,  # Return complete structure
                "data_used": ["scenario_time_series", "process_sensor_ts"]
            })

        # Agent 2: Investigation Agent
        investigation_agent_analysis = alert.get('investigation_agent_analysis', {})
        if investigation_agent_analysis:
            agents.append({
                "id": 2,
                "name": "Investigate",
                "status": "completed",
                "output": investigation_agent_analysis,  # Return complete structure
                "data_used": ["wafer_defects", "process_context", "alerts"]
            })

        # Agent 3: RCA Agent
        rca_agent_analysis = alert.get('rca_agent_analysis', {})
        ai_rca = alert.get('ai_rca', rca_agent_analysis)  # Check both old and new field names
        if ai_rca:
            agents.append({
                "id": 3,
                "name": "RCA",
                "status": "completed",
                "output": ai_rca,  # Return complete structure
                "data_used": ["historical_knowledge"]
            })

        # Agent 4: Supervisor Agent
        supervisor_agent_analysis = alert.get('supervisor_agent_analysis', {})
        ai_supervisor = alert.get('ai_supervisor', supervisor_agent_analysis)  # Check both old and new field names
        if ai_supervisor:
            agents.append({
                "id": 4,
                "name": "Synthesize",
                "status": "completed",
                "output": ai_supervisor,  # Return complete structure
                "data_used": ["wafer_defects", "historical_knowledge", "process_context"]  # Aggregated from all agents
            })

        logger.info(f"✅ [ALERT LIFECYCLE] Returned details for {len(agents)} agents")
        logger.info(f"✅ GET /alerts/{alert_id}/agent-details - Success: Retrieved {len(agents)} agent details")

        return {
            "alert_id": str(alert.get('_id', alert_id)),
            "equipment_id": alert.get('equipment_id', 'Unknown'),
            "agents": agents,
            "workflow_complete": len(agents) >= 4
        }

    except HTTPException:
        logger.warning(f"⚠️ GET /alerts/{alert_id}/agent-details - HTTPException raised")
        raise
    except Exception as e:
        logger.error(f"❌ Error retrieving agent details for alert {alert_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    acknowledged_by: str = Query(..., description="User acknowledging the alert"),
    notes: Optional[str] = Query(None, description="Acknowledgment notes")
):
    """
    Acknowledge an alert
    """
    logger.info(f"📥 POST /alerts/{alert_id}/acknowledge - User: {acknowledged_by}, Notes: {notes[:50] if notes else 'None'}")
    
    try:
        logger.debug(f"🔧 Acknowledging alert: {alert_id} by {acknowledged_by}")
        
        # Get alert manager
        alert_manager = get_alert_manager()
        
        # Acknowledge the alert
        success = alert_manager.acknowledge_alert(alert_id, acknowledged_by, notes)
        
        if not success:
            logger.warning(f"⚠️ POST /alerts/{alert_id}/acknowledge - Failed to acknowledge")
            raise HTTPException(status_code=400, detail="Failed to acknowledge alert. It may already be acknowledged.")
        
        logger.info(f"✅ POST /alerts/{alert_id}/acknowledge - Success: Acknowledged by {acknowledged_by}")
        
        return {
            "status": "success",
            "message": f"Alert {alert_id} acknowledged by {acknowledged_by}"
        }
        
    except HTTPException:
        logger.warning(f"⚠️ POST /alerts/{alert_id}/acknowledge - HTTPException raised")
        raise
    except Exception as e:
        logger.error(f"❌ Error acknowledging alert {alert_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    resolved_by: str = Query(..., description="User resolving the alert"),
    resolution_notes: str = Query(..., description="Resolution notes")
):
    """
    Resolve an alert
    """
    logger.info(f"📥 POST /alerts/{alert_id}/resolve - User: {resolved_by}, Notes: {resolution_notes[:50]}")
    
    try:
        logger.debug(f"🔧 Resolving alert: {alert_id} by {resolved_by}")
        
        # Get alert manager
        alert_manager = get_alert_manager()
        
        # Resolve the alert
        success = alert_manager.update_alert_status(
            alert_id=alert_id,
            status=AlertStatus.RESOLVED,
            updated_by=resolved_by,
            notes=resolution_notes
        )
        
        if not success:
            logger.warning(f"⚠️ POST /alerts/{alert_id}/resolve - Failed to resolve")
            raise HTTPException(status_code=400, detail="Failed to resolve alert")
        
        logger.info(f"✅ POST /alerts/{alert_id}/resolve - Success: Resolved by {resolved_by}")
        
        return {
            "status": "success",
            "message": f"Alert {alert_id} resolved by {resolved_by}"
        }
        
    except HTTPException:
        logger.warning(f"⚠️ POST /alerts/{alert_id}/resolve - HTTPException raised")
        raise
    except Exception as e:
        logger.error(f"❌ Error resolving alert {alert_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{alert_id}/fix")
async def fix_equipment_issue(alert_id: str):
    """
    Fix equipment issue by injecting healthy sensor data and resolving the alert
    This simulates a maintenance action that fixes the equipment
    """
    logger.info(f"📥 POST /alerts/{alert_id}/fix - Fixing equipment issue")
    
    try:
        logger.debug(f"🔧 Starting equipment fix for alert: {alert_id}")
        
        # Get alert manager
        alert_manager = get_alert_manager()
        
        # Get the alert details
        alert = alert_manager.get_alert_by_id(alert_id)
        if not alert:
            logger.warning(f"⚠️ POST /alerts/{alert_id}/fix - Alert not found")
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
        
        equipment_id = alert.get("equipment_id")
        if not equipment_id:
            logger.warning(f"⚠️ POST /alerts/{alert_id}/fix - No equipment associated")
            raise HTTPException(status_code=400, detail="Alert has no associated equipment")
        
        logger.info(f"🔧 Fixing equipment: {equipment_id} for alert: {alert_id}")
        
        # Use async MongoDB client
        db = mongodb_client_instance[mdb_database_name]
        sensor_collection = db[mdb_timeseries_collection]
        
        logger.debug(f"🔍 Fetching last sensor reading for equipment: {equipment_id}")
        
        # Get the process step for this equipment
        last_reading = await sensor_collection.find_one(
            {"equipment_id": equipment_id},
            sort=[("timestamp", -1)]
        )
        
        process_step = last_reading.get("process_step", "UNKNOWN") if last_reading else "UNKNOWN"
        logger.debug(f"📊 Process step for {equipment_id}: {process_step}")
        
        # Create healthy sensor reading
        healthy_reading = {
            "timestamp": datetime.utcnow(),
            "equipment_id": equipment_id,
            "process_step": process_step,
            "metrics": {
                "particle_count": 450,  # Healthy level (< 800)
                "rf_power": 1200.0,     # Normal RF power
                "chamber_pressure": 45.5,  # Normal pressure
                "temperature": 65.0,    # Normal temperature
                "flow_rate": 200.0      # Normal flow rate
            },
            "metadata": {
                "source": "maintenance_fix",
                "alert_id": alert_id,
                "action": "equipment_fixed"
            }
        }
        
        logger.debug(f"💉 Injecting healthy sensor data for {equipment_id}")
        
        # Insert healthy reading into time series
        result = await sensor_collection.insert_one(healthy_reading)
        
        if not result.inserted_id:
            logger.error(f"❌ Failed to insert healthy sensor data for {equipment_id}")
            raise HTTPException(status_code=500, detail="Failed to insert healthy sensor data")
        
        logger.info(f"✅ Healthy sensor data injected: {result.inserted_id}")
        
        # Now resolve the alert
        resolution_notes = f"Equipment fixed - Healthy sensor data injected. Particle count reduced to {healthy_reading['metrics']['particle_count']}"
        success = alert_manager.update_alert_status(
            alert_id=alert_id,
            status=AlertStatus.RESOLVED,
            updated_by="system",
            notes=resolution_notes
        )
        
        if not success:
            logger.warning(f"⚠️ Alert {alert_id} could not be resolved after fix")
        
        # Log the fix action
        logger.info(f"✅ POST /alerts/{alert_id}/fix - Success: Equipment {equipment_id} fixed, alert resolved: {success}")
        
        return {
            "status": "success",
            "message": f"Equipment {equipment_id} fixed successfully",
            "alert_id": alert_id,
            "new_metrics": healthy_reading["metrics"],
            "alert_resolved": success
        }
        
    except HTTPException:
        logger.warning(f"⚠️ POST /alerts/{alert_id}/fix - HTTPException raised")
        raise
    except Exception as e:
        logger.error(f"❌ Error fixing equipment for alert {alert_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

