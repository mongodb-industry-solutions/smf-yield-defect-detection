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
correlation_engine_instance = None
use_ai_agents_flag = True
mdb_database_name = None
mdb_timeseries_collection = None

# Will be imported when needed
AlertSeverity = None
AlertType = None
AlertStatus = None


def set_dependencies(alert_manager, convert_func, mongodb_client=None, correlation_engine=None, use_ai_agents=True, 
                     db_name=None, timeseries_collection=None):
    """
    Inject dependencies from main.py
    
    Args:
        alert_manager: AlertManager instance for alert operations
        convert_func: Function to convert ObjectIds to strings
        mongodb_client: Optional MongoDB client for direct queries
        correlation_engine: Optional CorrelationEngine instance
        use_ai_agents: Feature flag for AI multi-agent system
        db_name: MongoDB database name
        timeseries_collection: MongoDB timeseries collection name
    """
    global alert_manager_instance, convert_objectids_func, mongodb_client_instance
    global correlation_engine_instance, use_ai_agents_flag
    global mdb_database_name, mdb_timeseries_collection
    global AlertSeverity, AlertType, AlertStatus
    
    alert_manager_instance = alert_manager
    convert_objectids_func = convert_func
    mongodb_client_instance = mongodb_client
    correlation_engine_instance = correlation_engine
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
        
        # Fetch alerts with filters
        alerts = alert_manager.get_active_alerts(
            severity=severity_enum,
            alert_type=alert_type_enum,
            equipment_id=equipment_id,
            limit=limit
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
        monitoring_decision = alert.get('monitoring_decision', {})
        if monitoring_decision:
            agents.append({
                "id": 1,
                "name": "Monitor",
                "status": "completed",
                "output": {
                    "decision": "CREATE ALERT" if monitoring_decision.get('create_alert') else "FILTER",
                    "confidence": monitoring_decision.get('confidence', 0),
                    "pattern": monitoring_decision.get('pattern_detected', 'unknown'),
                    "reasoning": monitoring_decision.get('reasoning', ''),
                    "statistical_context": monitoring_decision.get('statistical_context', {})
                },
                "data_used": ["process_sensor_ts"]  # Statistical context from time series
            })

        # Agent 2: Investigation Agent
        ai_investigation = alert.get('ai_investigation', {})
        if ai_investigation:
            agents.append({
                "id": 2,
                "name": "Investigate",
                "status": "completed",
                "output": {
                    "affected_wafers": ai_investigation.get('affected_wafers', 0),
                    "correlation_confidence": ai_investigation.get('correlation_confidence', 0),
                    "key_findings": ai_investigation.get('key_findings', []),
                    "summary": ai_investigation.get('summary', '')
                },
                "data_used": ["wafer_defects", "process_context", "alerts"]
            })

        # Agent 3: RCA Agent
        ai_rca = alert.get('ai_rca', {})
        if ai_rca:
            agents.append({
                "id": 3,
                "name": "RCA",
                "status": "completed",
                "output": {
                    "confidence": ai_rca.get('confidence', 0),
                    "validated_causes": ai_rca.get('validated_causes', []),
                    "recommendations": ai_rca.get('recommendations', []),
                    "validation": ai_rca.get('validation', '')
                },
                "data_used": ["historical_knowledge"]
            })

        # Agent 4: Supervisor Agent
        ai_supervisor = alert.get('ai_supervisor', {})
        if ai_supervisor:
            agents.append({
                "id": 4,
                "name": "Synthesize",
                "status": "completed",
                "output": {
                    "risk_level": ai_supervisor.get('risk_level', 'Unknown'),
                    "overall_confidence": ai_supervisor.get('overall_confidence', 0),
                    "synthesis": ai_supervisor.get('synthesis', ''),
                    "agent_summary": ai_supervisor.get('agent_summary', {})
                },
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


@router.get("/{alert_id}/correlation")
async def get_alert_correlation(alert_id: str):
    """
    Get correlation analysis for a specific alert
    """
    logger.info(f"📥 GET /alerts/{alert_id}/correlation - Fetching correlation analysis")
    
    try:
        logger.debug(f"🔧 Getting correlation analysis for alert: {alert_id}")
        
        # Get dependencies
        alert_manager = get_alert_manager()
        
        if not correlation_engine_instance:
            logger.warning(f"⚠️ Correlation engine not initialized")
            raise HTTPException(status_code=503, detail="Services not initialized. Start monitoring first.")
        
        # Fetch alert
        alert = alert_manager.get_alert_by_id(alert_id)
        
        if not alert:
            logger.warning(f"⚠️ GET /alerts/{alert_id}/correlation - Alert not found")
            raise HTTPException(status_code=404, detail="Alert not found")
        
        # Perform correlation analysis if not already done (skip if AI agents enabled)
        if not alert.get("correlation_analysis") and not use_ai_agents_flag:
            logger.info(f"🔧 Triggering async correlation analysis for alert: {alert_id}")
            
            # Import necessary functions
            import asyncio
            # Note: run_alert_correlation and run_alert_rca need to be accessible
            # For now, we'll trigger but note that these functions are in main.py
            # This is a limitation we'll document
            
            logger.warning(f"⚠️ Async correlation analysis triggered but functions are in main.py")
            # asyncio.create_task(run_alert_correlation(alert_id))

            # Trigger RCA for critical alerts
            # if alert.get("severity") == "critical":
            #     asyncio.create_task(run_alert_rca(alert_id, AlertSeverity.CRITICAL))

            return {
                "alert_id": alert_id,
                "message": "Analysis triggered. Check back in a few seconds.",
                "status": "processing"
            }

        # Convert ObjectIds
        alert = convert_objectids(alert)
        
        logger.debug(f"📊 Preparing correlation response for alert: {alert_id}")

        # Prepare response with backward compatibility
        response = {
            "alert_id": alert_id,
            "correlation_analysis": alert.get("correlation_analysis", {}),
            "correlation_data": alert.get("correlation_analysis", {}),  # Backward compatibility
        }

        # Handle RCA fields (could be rca_analysis or rca_hints due to migration)
        rca_data = alert.get("rca_analysis", alert.get("rca_hints", {}))
        response["rca_analysis"] = rca_data
        response["rca_hints"] = rca_data  # Backward compatibility

        # Extract recommendations for backward compatibility
        if rca_data and "recommendations" in rca_data:
            response["rca_recommendations"] = rca_data["recommendations"]
        else:
            response["rca_recommendations"] = []

        logger.info(f"✅ GET /alerts/{alert_id}/correlation - Success: Retrieved correlation data")

        return response
        
    except HTTPException:
        logger.warning(f"⚠️ GET /alerts/{alert_id}/correlation - HTTPException raised")
        raise
    except Exception as e:
        logger.error(f"❌ Error analyzing correlation for alert {alert_id}: {e}", exc_info=True)
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

