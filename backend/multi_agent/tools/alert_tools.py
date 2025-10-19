"""
Alert Management Tools

Functions for alert creation, deduplication, and management.
Handles business logic for scenario analysis alerts.
"""

import logging
from typing import Optional, Dict
from datetime import datetime, timezone
from bson import ObjectId

logger = logging.getLogger(__name__)


async def check_existing_scenario_alert(db, scenario_id: str) -> Optional[Dict]:
    """
    Check if alert already exists for scenario (deduplication).
    
    Queries the alerts collection to find any existing scenario_analysis alert
    for the given scenario_id.
    
    Args:
        db: MongoDB database instance
        scenario_id: Scenario identifier to check
        
    Returns:
        Alert document if exists, None otherwise
    """
    existing_alert = await db.alerts.find_one({
        "source_data.scenario_id": scenario_id,
        "alert_type": "scenario_analysis"
    })
    
    return existing_alert


async def create_scenario_alert(
    db, 
    scenario_id: str, 
    scenario_metadata: Dict,
    mongodb_analysis: Optional[Dict] = None
) -> str:
    """
    Create new scenario analysis alert matching AlertManager structure.
    
    Creates an alert document in the alerts collection with:
    - Unique alert_id in format: ALT-SCENARIO-YYYYMMDDHHMMSS-ObjectId
    - Severity based on pattern type
    - All required fields matching AlertManager structure
    - monitoring_agent_analysis field with MongoDB aggregation results
    
    Args:
        db: MongoDB database instance
        scenario_id: Scenario identifier
        scenario_metadata: Metadata dict with title, equipment_id, pattern_type, etc.
        mongodb_analysis: MongoDB aggregation results (for monitoring_agent_analysis field)
        
    Returns:
        alert_id string of created alert
    """
    # Determine severity based on pattern
    severity_map = {
        "drift": "critical",
        "spike": "high",
        "oscillation": "high"
    }
    severity = severity_map.get(scenario_metadata.get('pattern_type'), "high")
    
    # Generate alert_id (keep ALT-SCENARIO prefix for identification)
    alert_id_str = f"ALT-SCENARIO-{datetime.now().strftime('%Y%m%d%H%M%S')}-{ObjectId()}"
    
    # Calculate estimated impact (simplified version matching AlertManager)
    estimated_impact = _calculate_impact(severity, scenario_metadata.get('pattern_type'))
    
    # Get actual timestamp from scenario time series data at anomaly window start
    # This makes the alert timestamp match when the excursion actually occurred in the scenario
    anomaly_window = scenario_metadata.get('anomaly_window', {})
    anomaly_start_minute = anomaly_window.get('start_minute', 0)
    
    # Use aggregation to skip to the anomaly start reading and get its timestamp
    pipeline = [
        {"$match": {"metadata.scenario_id": scenario_id}},
        {"$sort": {"timestamp": 1}},
        {"$skip": anomaly_start_minute},
        {"$limit": 1},
        {"$project": {"timestamp": 1, "_id": 0}}
    ]
    
    cursor = db.scenario_time_series.aggregate(pipeline)
    anomaly_readings = await cursor.to_list(length=1)
    
    # Use anomaly timestamp if found, otherwise fall back to current time
    if anomaly_readings and 'timestamp' in anomaly_readings[0]:
        alert_timestamp = anomaly_readings[0]['timestamp']
        logger.info(f"   🕐 Using scenario timestamp: {alert_timestamp} (minute {anomaly_start_minute})")
    else:
        alert_timestamp = datetime.now(timezone.utc)
        logger.warning(f"   ⚠️  Could not find scenario timestamp, using current time")
    
    # Build alert document matching AlertManager structure exactly
    # Extract lot_id and wafer_id from scenario metadata (matches AlertManager pattern)
    lot_id = scenario_metadata.get('lot_id')  # Now populated from scenario metadata
    wafer_id = scenario_metadata.get('wafer_id')  # Now populated from scenario metadata
    
    alert_doc = {
        "alert_id": alert_id_str,
        "alert_type": "scenario_analysis",
        "severity": severity,
        "status": "open",
        "title": f"Scenario Analysis: {scenario_metadata.get('title', 'Unknown')}",
        "description": f"Time series analysis detected {scenario_metadata.get('pattern_type', 'unknown')} pattern on {scenario_metadata.get('equipment_id', 'unknown')}",
        "timestamp": alert_timestamp,  # Use actual scenario timestamp, not current time
        "acknowledged_at": None,
        "resolved_at": None,  # Match AlertManager structure
        "closed_at": None,  # Match AlertManager structure
        "equipment_id": scenario_metadata.get('equipment_id'),
        "lot_id": lot_id,  # From scenario metadata (for downstream agent analysis)
        "wafer_id": wafer_id,  # From scenario metadata (for downstream agent analysis)
        "source_data": {
            "scenario_id": scenario_id,
            "pattern_type": scenario_metadata.get('pattern_type'),
            "root_cause": scenario_metadata.get('root_cause'),
            "anomaly_window": scenario_metadata.get('anomaly_window')
        },
        "assigned_to": None,
        "resolution_notes": None,  # Match AlertManager structure
        "estimated_impact": estimated_impact,  # Match AlertManager structure
        "auto_generated": True,  # Match AlertManager structure
        "notifications_sent": [],  # Match AlertManager structure
        "escalation_level": 0,  # Match AlertManager structure
        # NEW: Add MongoDB analysis results from monitoring agent
        "monitoring_agent_analysis": mongodb_analysis if mongodb_analysis else {}
    }
    
    # Log alert structure before attempting to insert
    logger.info(f"   📋 Attempting to insert alert...")
    logger.info(f"   📋 Alert ID: {alert_id_str}")
    logger.info(f"   📋 Alert has monitoring_agent_analysis: {bool(mongodb_analysis)}")
    if mongodb_analysis and 'llm_interpretation' in mongodb_analysis:
        logger.info(f"   📋 LLM interpretation included: YES")
    
    try:
        result = await db.alerts.insert_one(alert_doc)
        logger.info(f"   ✅ Alert inserted successfully!")
        logger.info(f"   ✅ MongoDB inserted_id: {result.inserted_id}")
        logger.info(f"   🚨 Alert created: {alert_id_str}")
        logger.info(f"   📊 Severity: {severity.upper()}")
        logger.info(f"   🔍 Pattern: {scenario_metadata.get('pattern_type')}")
        if mongodb_analysis:
            logger.info(f"   📊 MongoDB Analysis: Included in alert")
    except Exception as e:
        logger.error(f"   ❌ Failed to insert alert: {e}")
        logger.error(f"   ❌ Error type: {type(e).__name__}")
        raise
    
    return alert_id_str


def _calculate_impact(severity: str, pattern_type: str) -> Dict:
    """
    Calculate estimated impact based on severity and pattern.
    Simplified version matching AlertManager logic.
    
    Args:
        severity: Alert severity level (critical, high, medium, low)
        pattern_type: Pattern type (drift, spike, oscillation)
        
    Returns:
        Dict with estimated yield loss, cost, and affected equipment
    """
    impact_scores = {
        "critical": {"yield_impact": 15.0, "cost_impact": 50000},
        "high": {"yield_impact": 8.0, "cost_impact": 25000},
        "medium": {"yield_impact": 3.0, "cost_impact": 10000},
        "low": {"yield_impact": 1.0, "cost_impact": 2000}
    }
    
    base_impact = impact_scores.get(severity, impact_scores["medium"])
    
    return {
        "estimated_yield_loss_percent": base_impact["yield_impact"],
        "estimated_cost_usd": base_impact["cost_impact"],
        "affected_equipment": 1,
        "calculation_method": "scenario_severity_based"
    }

