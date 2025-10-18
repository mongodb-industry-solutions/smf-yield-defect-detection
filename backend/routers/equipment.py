"""
Equipment Router
Handles all equipment-related endpoints for status monitoring and metrics
"""
import logging
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/equipment",
    tags=["Equipment"],
    responses={404: {"description": "Not found"}},
)

# Dependencies (injected from main.py on startup)
mongodb_client: AsyncIOMotorClient | None = None
mongodb_connector_class = None
mdb_uri: str | None = None
mdb_database_name: str | None = None
mdb_timeseries_collection: str | None = None


def set_dependencies(
    async_client,
    connector_class,
    uri: str,
    db_name: str,
    timeseries_collection: str
):
    """
    Inject dependencies from main.py
    
    Args:
        async_client: AsyncIOMotorClient for async operations
        connector_class: MongoDBConnector class for sync operations
        uri: MongoDB URI
        db_name: MongoDB database name
        timeseries_collection: Timeseries collection name
    """
    global mongodb_client, mongodb_connector_class
    global mdb_uri, mdb_database_name, mdb_timeseries_collection
    
    mongodb_client = async_client
    mongodb_connector_class = connector_class
    mdb_uri = uri
    mdb_database_name = db_name
    mdb_timeseries_collection = timeseries_collection
    
    logger.info("✅ Equipment dependencies injected into router")


def get_mongodb_connector():
    """Get MongoDB connector with error handling"""
    if mongodb_connector_class is None or mdb_uri is None or mdb_database_name is None:
        logger.error("❌ MongoDB connector not initialized")
        raise HTTPException(status_code=500, detail="Database connection not initialized")
    return mongodb_connector_class(uri=mdb_uri, database_name=mdb_database_name)


logger.info("📦 Equipment router initialized")


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/status")
async def get_equipment_status():
    """
    Get equipment fleet status matrix - OPTIMIZED
    Uses alerts collection as single source of truth for excursions
    """
    start_time = time.time()
    logger.info("📥 GET /equipment/status - Starting request")

    try:
        # Validate dependencies
        if mongodb_client is None or mdb_database_name is None or mdb_timeseries_collection is None:
            logger.error("❌ GET /equipment/status - MongoDB client not initialized")
            raise HTTPException(status_code=500, detail="Database connection not initialized")
        
        # Use async MongoDB client
        db = mongodb_client[mdb_database_name]
        sensor_collection = db[mdb_timeseries_collection]
        alerts_collection = db["alerts"]
        logger.debug("⚙️ MongoDB collections initialized")

        # Get latest reading per equipment (without status calculation)
        # OPTIMIZATION: Limit to recent data only to avoid scanning entire collection
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        logger.debug(f"⚙️ Time filter: {one_hour_ago} (1 hour ago)")

        pipeline = [
            # Add time filter to limit data scan
            {"$match": {"timestamp": {"$gte": one_hour_ago}}},

            # Sort by timestamp descending (uses index now)
            {"$sort": {"timestamp": -1}},

            # Group by equipment to get latest reading (stops at first match per equipment)
            {"$group": {
                "_id": "$equipment_id",
                "latest_reading": {"$first": "$$ROOT"}
            }},

            # Project the needed fields
            {"$project": {
                "equipment_id": "$_id",
                "process_step": "$latest_reading.process_step",
                "last_update": "$latest_reading.timestamp",
                "current_metrics": "$latest_reading.metrics"
            }}
        ]

        # Execute aggregation asynchronously
        query_start = time.time()
        logger.info("   📊 Executing equipment aggregation pipeline...")
        cursor = sensor_collection.aggregate(pipeline)
        equipment_list = await cursor.to_list(length=None)
        query_time = (time.time() - query_start) * 1000
        logger.info(f"   📊 Equipment query completed in {query_time:.0f}ms, found {len(equipment_list)} equipment")

        # Get all open alerts for equipment
        alerts_start = time.time()
        logger.info("   🚨 Fetching open alerts for equipment...")
        open_alerts = await alerts_collection.find({
            "status": {"$in": ["open", "acknowledged"]},
            "equipment_id": {"$exists": True}
        }).to_list(length=None)
        alerts_time = (time.time() - alerts_start) * 1000
        logger.info(f"   🚨 Alerts query completed in {alerts_time:.0f}ms, found {len(open_alerts)} open alerts")

        # Create a map of equipment_id to highest severity alert
        processing_start = time.time()
        logger.debug("⚙️ Processing alert severity mapping...")
        equipment_alerts = {}
        for alert in open_alerts:
            eq_id = alert.get("equipment_id")
            severity = alert.get("severity", "medium")

            # Keep highest severity alert for each equipment
            if eq_id:
                if eq_id not in equipment_alerts:
                    equipment_alerts[eq_id] = severity
                else:
                    # Priority: critical > high > medium > low
                    severity_priority = {"critical": 4, "high": 3, "medium": 2, "low": 1}
                    current_priority = severity_priority.get(equipment_alerts[eq_id], 0)
                    new_priority = severity_priority.get(severity, 0)
                    if new_priority > current_priority:
                        equipment_alerts[eq_id] = severity

        # Add status based on alerts
        logger.debug("⚙️ Calculating equipment status based on alerts...")
        for eq in equipment_list:
            eq_id = eq.get("equipment_id")
            if eq_id in equipment_alerts:
                # Map alert severity to equipment status
                alert_severity = equipment_alerts[eq_id]
                if alert_severity == "critical":
                    eq["status"] = "critical"
                elif alert_severity == "high":
                    eq["status"] = "warning"
                else:
                    eq["status"] = "warning"  # medium/low alerts show as warning
            else:
                eq["status"] = "good"  # No open alerts

        processing_time = (time.time() - processing_start) * 1000
        logger.info(f"   🔧 Status processing completed in {processing_time:.0f}ms")

        # Group by process type
        grouping_start = time.time()
        logger.debug("⚙️ Grouping equipment by process step...")
        equipment_matrix = {}
        for eq in equipment_list:
            process = eq.get("process_step", "UNKNOWN")
            if process not in equipment_matrix:
                equipment_matrix[process] = []

            equipment_matrix[process].append({
                "equipment_id": eq["equipment_id"],
                "status": eq["status"],
                "metrics": eq["current_metrics"],
                "last_update": eq["last_update"]
            })

        # Sort equipment within each process group
        for process in equipment_matrix:
            equipment_matrix[process].sort(key=lambda x: x["equipment_id"])

        grouping_time = (time.time() - grouping_start) * 1000
        logger.info(f"   📊 Matrix grouping completed in {grouping_time:.0f}ms")

        total_time = (time.time() - start_time) * 1000
        logger.info(f"✅ GET /equipment/status - Success: {len(equipment_list)} equipment in {total_time:.0f}ms")

        return {
            "matrix": equipment_matrix,
            "total_equipment": len(equipment_list),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        total_time = (time.time() - start_time) * 1000
        logger.error(f"❌ GET /equipment/status - Error after {total_time:.0f}ms: {e}", exc_info=True)
        # Return cached/default data on error for better UX
        return {
            "matrix": {},
            "total_equipment": 0,
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@router.get("/{equipment_id}/metrics")
async def get_equipment_metrics(
    equipment_id: str,
    hours: int = Query(24, description="Time window in hours")
):
    """
    Get detailed metrics for specific equipment
    """
    start_time = time.time()
    logger.info(f"📥 GET /equipment/{equipment_id}/metrics - Request with hours={hours}")
    
    try:
        with get_mongodb_connector() as mdb_connector:
            logger.debug(f"⚙️ MongoDB connector established for equipment/{equipment_id}/metrics")
            sensor_collection = mdb_connector.get_collection(mdb_timeseries_collection)
            
            # Calculate time window
            end_time = datetime.now()
            start_time_query = end_time - timedelta(hours=hours)
            logger.debug(f"⚙️ Time window: {start_time_query} to {end_time} ({hours} hours)")
            
            # Get metrics statistics
            pipeline = [
                {"$match": {
                    "equipment_id": equipment_id,
                    "timestamp": {"$gte": start_time_query, "$lte": end_time}
                }},
                {"$group": {
                    "_id": None,
                    "total_readings": {"$sum": 1},
                    "avg_particle_count": {"$avg": "$metrics.particle_count"},
                    "max_particle_count": {"$max": "$metrics.particle_count"},
                    "min_particle_count": {"$min": "$metrics.particle_count"},
                    "avg_rf_power": {"$avg": "$metrics.rf_power"},
                    "avg_temperature": {"$avg": "$metrics.temperature"},
                    "avg_pressure": {"$avg": "$metrics.chamber_pressure"},
                    "excursions": {
                        "$sum": {
                            "$cond": [{"$gt": ["$metrics.particle_count", 1000]}, 1, 0]
                        }
                    }
                }}
            ]
            
            logger.info(f"   📊 Executing metrics aggregation for {equipment_id}...")
            stats = list(sensor_collection.aggregate(pipeline))
            logger.debug(f"   ✅ Retrieved {len(stats)} stat records for {equipment_id}")
            
            if not stats:
                elapsed_time = (time.time() - start_time) * 1000
                logger.info(f"✅ GET /equipment/{equipment_id}/metrics - No data available in {elapsed_time:.2f}ms")
                return {
                    "equipment_id": equipment_id,
                    "message": "No data available for specified time window"
                }
            
            metrics = stats[0]
            del metrics["_id"]
            logger.debug(f"⚙️ Processing metrics: {metrics['total_readings']} readings, {metrics.get('excursions', 0)} excursions")
            
            # Calculate utilization (simplified)
            utilization = min(100, (metrics["total_readings"] / (hours * 60)) * 100)
            health_score = 100 - (metrics.get("excursions", 0) * 10)
            logger.debug(f"⚙️ Calculated utilization: {utilization:.2f}%, health score: {health_score}")
            
            elapsed_time = (time.time() - start_time) * 1000
            logger.info(f"✅ GET /equipment/{equipment_id}/metrics - Success: {metrics['total_readings']} readings in {elapsed_time:.2f}ms")
            
            return {
                "equipment_id": equipment_id,
                "time_window_hours": hours,
                "metrics": metrics,
                "utilization_percentage": round(utilization, 2),
                "health_score": health_score  # Simple health score
            }
            
    except HTTPException:
        raise
    except Exception as e:
        elapsed_time = (time.time() - start_time) * 1000
        logger.error(f"❌ GET /equipment/{equipment_id}/metrics - Error after {elapsed_time:.2f}ms: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

