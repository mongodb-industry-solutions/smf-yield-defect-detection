"""
Dashboard Preload Router - Optimized single-call endpoint for dashboard data

This router provides a single endpoint to fetch ALL dashboard data in one optimized call.
Used by frontend to preload and cache all necessary data after seed initialization,
eliminating multiple API calls and providing instant dashboard rendering.
"""

import logging
import time
import asyncio
from typing import Dict, Any
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
    responses={404: {"description": "Not found"}},
)

# Dependencies (injected from main.py)
mongodb_client: AsyncIOMotorClient | None = None
mdb_database_name: str | None = None


def set_dependencies(async_client: AsyncIOMotorClient, db_name: str):
    """
    Inject dependencies from main.py
    
    Args:
        async_client: MongoDB async client instance
        db_name: Database name
    """
    global mongodb_client, mdb_database_name
    mongodb_client = async_client
    mdb_database_name = db_name
    logger.info("✅ Dashboard preload dependencies injected")


@router.get("/preload")
async def preload_dashboard_data():
    """
    Pre-load ALL dashboard data in a single optimized call
    
    This endpoint fetches all data needed for dashboard initial render:
    - KPI statistics (yield, alerts, equipment health)
    - Equipment health status (6 standardized equipment)
    - Recent alerts (last 50 open/acknowledged)
    - Chart data (sensor readings for last 24h, sampled)
    - Recent wafers (last 20)
    
    All queries run in parallel via asyncio.gather() for optimal performance.
    
    Returns:
        Dict with all dashboard data pre-aggregated and ready to cache:
        - success: bool
        - timestamp: str (ISO format)
        - data: Dict containing kpis, equipment, alerts, chart_data, wafers
        - fetch_time_ms: float (time taken for parallel queries)
    """
    start_time = time.time()
    logger.info("📥 GET /dashboard/preload - Starting dashboard preload")
    
    try:
        if mongodb_client is None or mdb_database_name is None:
            raise HTTPException(status_code=500, detail="Database not initialized")
        
        db = mongodb_client[mdb_database_name]
        
        # Equipment IDs for queries
        equipment_ids = ["CMP_TOOL_01", "CMP_TOOL_02", "ETCH_01", "ETCH_02", "LITHO_01", "LITHO_02"]
        
        # Define all aggregation functions
        # These run in PARALLEL via asyncio.gather
        
        async def fetch_kpis():
            """Fetch KPI statistics: yield, alerts, equipment health"""
            logger.debug("  ⚙️ Fetching KPI statistics...")
            
            # Yield calculation from recent wafers
            wafer_pipeline = [
                {"$sort": {"inspection_timestamp": -1}},
                {"$limit": 10},
                {"$group": {
                    "_id": None,
                    "avg_yield": {"$avg": "$defect_summary.yield_percentage"},
                    "latest_yield": {"$first": "$defect_summary.yield_percentage"},
                }}
            ]
            wafer_cursor = db.wafer_defects.aggregate(wafer_pipeline)
            wafer_results = await wafer_cursor.to_list(length=1)
            
            # Active alerts count by severity
            alert_pipeline = [
                {"$match": {"status": {"$in": ["open", "acknowledged"]}}},
                {"$group": {
                    "_id": "$severity",
                    "count": {"$sum": 1}
                }}
            ]
            alert_cursor = db.alerts.aggregate(alert_pipeline)
            alert_results = await alert_cursor.to_list(length=10)
            
            # Equipment health count
            equipment_healthy = await db.equipment.count_documents({"status": "healthy"})
            equipment_total = await db.equipment.count_documents({})
            
            # Parse results
            yield_data = wafer_results[0] if wafer_results else {"avg_yield": 0, "latest_yield": 0}
            
            alert_counts = {"total": 0, "critical": 0, "warning": 0}
            for alert in alert_results:
                alert_counts["total"] += alert["count"]
                if alert["_id"] == "CRITICAL":
                    alert_counts["critical"] = alert["count"]
                elif alert["_id"] == "WARNING":
                    alert_counts["warning"] = alert["count"]
            
            return {
                "yield": {
                    "current": round(yield_data.get("latest_yield", 0), 1),
                    "average": round(yield_data.get("avg_yield", 0), 1),
                    "trend": "up" if yield_data.get("latest_yield", 0) > yield_data.get("avg_yield", 0) else "down"
                },
                "active_alerts": alert_counts,
                "equipment_health": {
                    "healthy": equipment_healthy,
                    "total": equipment_total,
                    "degraded": equipment_total - equipment_healthy
                },
                "uptime": 98.5  # Placeholder - can be calculated from equipment data if needed
            }
        
        async def fetch_equipment():
            """Fetch equipment status with latest sensor readings and alert counts"""
            logger.debug("  ⚙️ Fetching equipment status...")
            
            equipment_data = []
            
            for eq_id in equipment_ids:
                # Latest sensor reading
                latest_sensor = await db.process_sensor_ts.find_one(
                    {"equipment_id": eq_id},
                    sort=[("timestamp", -1)]
                )
                
                # Active alerts for this equipment
                active_alerts = await db.alerts.count_documents({
                    "equipment_id": eq_id,
                    "status": {"$in": ["open", "acknowledged"]}
                })
                
                # Determine status based on alerts
                if not latest_sensor:
                    status = "unknown"
                    health_score = 0
                elif active_alerts > 0:
                    status = "critical" if active_alerts >= 2 else "degraded"
                    health_score = max(0, 100 - (active_alerts * 20))
                else:
                    status = "healthy"
                    health_score = 100
                
                equipment_data.append({
                    "equipment_id": eq_id,
                    "status": status,
                    "health_score": health_score,
                    "active_alerts": active_alerts,
                    "last_reading": {
                        "timestamp": latest_sensor["timestamp"].isoformat() if latest_sensor else None,
                        "particle_count": latest_sensor["metrics"]["particle_count"] if latest_sensor else 0,
                        "temperature": latest_sensor["metrics"]["temperature"] if latest_sensor else 0,
                        "rf_power": latest_sensor["metrics"].get("rf_power", 0) if latest_sensor else 0
                    } if latest_sensor else None
                })
            
            return equipment_data
        
        async def fetch_alerts():
            """Fetch recent open/acknowledged alerts"""
            logger.debug("  ⚙️ Fetching recent alerts...")
            
            cursor = db.alerts.find(
                {"status": {"$in": ["open", "acknowledged"]}},
                {
                    "alert_id": 1,
                    "equipment_id": 1,
                    "severity": 1,
                    "alert_type": 1,
                    "timestamp": 1,
                    "status": 1,
                    "metrics": 1
                }
            ).sort("timestamp", -1).limit(50)
            
            alerts = await cursor.to_list(length=50)
            
            # Convert ObjectId to string and datetime to ISO
            for alert in alerts:
                if "_id" in alert:
                    alert["_id"] = str(alert["_id"])
                if "timestamp" in alert and isinstance(alert["timestamp"], datetime):
                    alert["timestamp"] = alert["timestamp"].isoformat()
            
            return alerts
        
        async def fetch_chart_data():
            """Fetch sensor readings for charts (last 24 hours, sampled)"""
            logger.debug("  ⚙️ Fetching chart data...")
            
            # Get last 24 hours of sensor data
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
            
            chart_data = {
                "particle_counts": {},
                "temperatures": {},
                "rf_power": {}
            }
            
            for eq_id in equipment_ids:
                # Sample up to 100 points for performance
                cursor = db.process_sensor_ts.find(
                    {
                        "equipment_id": eq_id,
                        "timestamp": {"$gte": cutoff_time}
                    },
                    {
                        "timestamp": 1,
                        "metrics.particle_count": 1,
                        "metrics.temperature": 1,
                        "metrics.rf_power": 1
                    }
                ).sort("timestamp", 1).limit(100)
                
                readings = await cursor.to_list(length=100)
                
                chart_data["particle_counts"][eq_id] = [
                    {
                        "timestamp": r["timestamp"].isoformat(),
                        "value": r["metrics"]["particle_count"]
                    }
                    for r in readings
                ]
                
                chart_data["temperatures"][eq_id] = [
                    {
                        "timestamp": r["timestamp"].isoformat(),
                        "value": r["metrics"]["temperature"]
                    }
                    for r in readings
                ]
                
                chart_data["rf_power"][eq_id] = [
                    {
                        "timestamp": r["timestamp"].isoformat(),
                        "value": r["metrics"].get("rf_power", 0)
                    }
                    for r in readings
                ]
            
            return chart_data
        
        async def fetch_wafers():
            """Fetch recent wafers with yield and defect information"""
            logger.debug("  ⚙️ Fetching recent wafers...")
            
            cursor = db.wafer_defects.find(
                {},
                {
                    "wafer_id": 1,
                    "equipment_id": 1,
                    "defect_summary.yield_percentage": 1,
                    "defect_summary.total_defects": 1,
                    "defect_summary.severity": 1,
                    "inspection_timestamp": 1
                }
            ).sort("inspection_timestamp", -1).limit(20)
            
            wafers = await cursor.to_list(length=20)
            
            # Flatten structure and convert types
            for wafer in wafers:
                if "_id" in wafer:
                    wafer["_id"] = str(wafer["_id"])
                if "inspection_timestamp" in wafer and isinstance(wafer["inspection_timestamp"], datetime):
                    wafer["inspection_timestamp"] = wafer["inspection_timestamp"].isoformat()
                if "defect_summary" in wafer:
                    summary = wafer.pop("defect_summary")
                    wafer["yield_percentage"] = summary.get("yield_percentage", 0)
                    wafer["total_defects"] = summary.get("total_defects", 0)
                    wafer["severity"] = summary.get("severity", "unknown")
            
            return wafers
        
        # Execute all fetches in parallel
        logger.debug("⚡ Running all fetches in parallel...")
        kpis, equipment, alerts, chart_data, wafers = await asyncio.gather(
            fetch_kpis(),
            fetch_equipment(),
            fetch_alerts(),
            fetch_chart_data(),
            fetch_wafers()
        )
        
        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"✅ Dashboard preload complete in {elapsed_ms:.0f}ms")
        
        return {
            "success": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "kpis": kpis,
                "equipment": equipment,
                "alerts": alerts,
                "chart_data": chart_data,
                "wafers": wafers
            },
            "fetch_time_ms": round(elapsed_ms, 0)
        }
        
    except Exception as e:
        logger.error(f"❌ Dashboard preload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Dashboard preload failed: {str(e)}"
        )


logger.info("📦 Dashboard preload router initialized")

