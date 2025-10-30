"""
KPI Router
Handles all KPI statistics endpoints for dashboard metrics
"""
import logging
import time
import asyncio
from typing import Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/kpi",
    tags=["KPI"],
    responses={404: {"description": "Not found"}},
)

# Dependencies (injected from main.py on startup)
mongodb_client: AsyncIOMotorClient | None = None
mdb_database_name: str | None = None


def set_dependencies(
    async_client,
    db_name: str
):
    """
    Inject dependencies from main.py
    
    Args:
        async_client: AsyncIOMotorClient for async operations
        db_name: MongoDB database name
    """
    global mongodb_client, mdb_database_name
    
    mongodb_client = async_client
    mdb_database_name = db_name
    
    logger.info("✅ KPI dependencies injected into router")


logger.info("📦 KPI router initialized")


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/statistics")
async def get_kpi_statistics():
    """
    Get comprehensive KPI statistics for dashboard
    Optimized to run all aggregations in parallel
    """
    start_time = time.time()
    logger.info("📥 GET /kpi/statistics - Starting KPI calculations")
    
    try:
        # Validate dependencies
        if mongodb_client is None or mdb_database_name is None:
            logger.error("❌ GET /kpi/statistics - MongoDB client not initialized")
            raise HTTPException(status_code=500, detail="Database connection not initialized")
        
        # Use async MongoDB client from app startup
        db = mongodb_client[mdb_database_name]
        logger.debug("⚙️ MongoDB database initialized")
        
        # Define all aggregation pipelines (OPTIMIZED - project only needed fields)
        logger.debug("⚙️ Defining optimized aggregation pipelines...")
        wafer_pipeline = [
            {"$sort": {"inspection_timestamp": -1}},
            {"$limit": 10},
            {"$project": {
                "yield": "$defect_summary.yield_percentage"
            }},
            {"$group": {
                "_id": None,
                "avg_yield": {"$avg": "$yield"},
                "latest_yield": {"$first": "$yield"},
                "total_wafers": {"$sum": 1}
            }}
        ]

        alert_pipeline = [
            {"$match": {
                "status": {"$in": ["open", "acknowledged"]}
            }},
            {"$project": {
                "severity": 1
            }},
            {"$group": {
                "_id": "$severity",
                "count": {"$sum": 1}
            }}
        ]

        # Calculate cutoff time for last 1 hour (using naive UTC to match sensor data timestamps)
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)

        equipment_pipeline = [
            {"$match": {
                "timestamp": {"$gte": one_hour_ago}
            }},
            {"$sort": {"timestamp": -1}},
            {"$project": {
                "equipment_id": 1,
                "rf_power": "$metrics.rf_power",
                "particle_count": "$metrics.particle_count"
            }},
            {"$group": {
                "_id": "$equipment_id",
                "rf_power": {"$first": "$rf_power"},
                "particle_count": {"$first": "$particle_count"}
            }}
        ]
        
        # Execute all aggregations in parallel using asyncio.gather
        parallel_start = time.time()
        logger.info("   📊 Executing 3 parallel aggregations...")

        # Create async tasks for each aggregation
        wafer_task = db.wafer_defects.aggregate(wafer_pipeline).to_list(length=None)
        alert_task = db.alerts.aggregate(alert_pipeline).to_list(length=None)
        equipment_task = db.process_sensor_ts.aggregate(equipment_pipeline).to_list(length=None)

        # Run all tasks in parallel
        wafer_stats, alert_results, equipment_results = await asyncio.gather(
            wafer_task,
            alert_task,
            equipment_task
        )

        parallel_time = (time.time() - parallel_start) * 1000
        logger.info(f"   📊 Parallel aggregations completed in {parallel_time:.0f}ms")
        logger.debug(f"   ✅ Results: {len(wafer_stats)} wafer stats, {len(alert_results)} alert types, "
                    f"{len(equipment_results)} equipment")
        
        # Process results (same logic as before, but now with parallel data)
        calc_start = time.time()
        logger.debug("⚙️ Processing KPI calculations...")

        
        current_yield = wafer_stats[0]["latest_yield"] if wafer_stats else 94.2
        avg_yield = wafer_stats[0]["avg_yield"] if wafer_stats else 94.2
        
        # Process alert counts
        alert_counts = {item["_id"]: item["count"] for item in alert_results}
        total_alerts = sum(alert_counts.values())
        critical_alerts = alert_counts.get("critical", 0) + alert_counts.get("high", 0)
        logger.debug(f"⚙️ Alerts: {total_alerts} total ({critical_alerts} critical/high)")

        # MTTR and Cost Savings are hard-coded (overridden in frontend based on dashboard mode)
        avg_resolution_minutes = 360  # Static placeholder (6 hrs)
        cost_savings = 3000000  # Static placeholder ($3M)
        logger.debug(f"⚙️ MTTR: {avg_resolution_minutes} minutes (static placeholder)")
        logger.debug(f"⚙️ Cost savings: ${cost_savings/1000000:.1f}M (static placeholder)")

        # Calculate equipment utilization
        total_utilization = 0
        equipment_count = 0
        for eq in equipment_results:
            if eq.get("rf_power"):
                utilization = min(100, (eq["rf_power"] / 1500) * 100)
                total_utilization += utilization
                equipment_count += 1
        
        avg_utilization = total_utilization / equipment_count if equipment_count > 0 else 75
        logger.debug(f"⚙️ Equipment utilization: {avg_utilization:.1f}%")
        
        # Calculate trend value
        trend_value = round(current_yield - avg_yield, 1) if avg_yield else 0
        
        calc_time = (time.time() - calc_start) * 1000
        logger.info(f"   📊 KPI calculations completed in {calc_time:.0f}ms")
        
        total_time = (time.time() - start_time) * 1000
        logger.info(f"✅ GET /kpi/statistics - Success: 5 KPIs calculated in {total_time:.0f}ms")
        
        return {
            "kpi": {
                "yield": {
                    "label": "Current Yield",
                    "value": round(current_yield, 1),
                    "unit": "%",
                    "trend": "up" if trend_value > 0 else "down",
                    "trendValue": abs(trend_value),
                    "target": 95,
                    "thresholds": {"critical": 85, "warning": 92, "good": 95}
                },
                "alerts": {
                    "label": "Active Alerts",
                    "value": total_alerts,
                    "unit": "",
                    "trend": "down" if total_alerts < 5 else "up",
                    "trendValue": abs(total_alerts - 5),
                    "severity": "critical" if critical_alerts > 2 else "warning" if total_alerts > 3 else "good",
                    "thresholds": {"critical": 10, "warning": 5, "good": 2}
                },
                "mttr": {
                    "label": "Avg Resolution Time",
                    "value": round(avg_resolution_minutes),
                    "unit": "min",
                    "trend": "down",
                    "trendValue": 0,
                    "count": 0,
                    "thresholds": {"critical": 60, "warning": 30, "good": 15}
                },
                "savings": {
                    "label": "Cost Savings",
                    "value": round(cost_savings / 1000000, 1),
                    "unit": "M",
                    "prefix": "$",
                    "trend": "up",
                    "trendValue": 0,
                    "period": "Last 30 min",
                    "count": 0,
                    "thresholds": {"critical": 0, "warning": 0.5, "good": 1}
                },
                "utilization": {
                    "label": "Equipment Utilization",
                    "value": round(avg_utilization),
                    "unit": "%",
                    "trend": "up" if avg_utilization > 70 else "down",
                    "trendValue": abs(avg_utilization - 70),
                    "thresholds": {"critical": 50, "warning": 70, "good": 85}
                }
            },
            "summary": {
                "total_wafers_processed": wafer_stats[0]["total_wafers"] if wafer_stats else 100,
                "total_equipment": equipment_count,
                "alerts_by_severity": alert_counts,
                "avg_yield_10_wafers": round(avg_yield, 1) if avg_yield else 94.2
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        total_time = (time.time() - start_time) * 1000
        logger.error(f"❌ GET /kpi/statistics - Error after {total_time:.0f}ms: {e}", exc_info=True)
        # Return default values on error
        return {
            "kpi": {
                "yield": {
                    "label": "Current Yield",
                    "value": 94.2,
                    "unit": "%",
                    "trend": "up",
                    "trendValue": 2.3,
                    "target": 95,
                    "thresholds": {"critical": 85, "warning": 92, "good": 95}
                },
                "alerts": {
                    "label": "Active Alerts",
                    "value": 3,
                    "unit": "",
                    "trend": "down",
                    "trendValue": 2,
                    "severity": "warning",
                    "thresholds": {"critical": 10, "warning": 5, "good": 2}
                },
                "mttr": {
                    "label": "Avg Resolution Time",
                    "value": 12,
                    "unit": "min",
                    "trend": "down",
                    "trendValue": 85,
                    "trendLabel": "% improvement",
                    "thresholds": {"critical": 60, "warning": 30, "good": 15}
                },
                "savings": {
                    "label": "Cost Savings",
                    "value": 2.4,
                    "unit": "M",
                    "prefix": "$",
                    "trend": "up",
                    "trendValue": 18,
                    "period": "This Month",
                    "thresholds": {"critical": 0, "warning": 1, "good": 2}
                },
                "utilization": {
                    "label": "Equipment Utilization",
                    "value": 75,
                    "unit": "%",
                    "trend": "up",
                    "trendValue": 5,
                    "thresholds": {"critical": 50, "warning": 70, "good": 85}
                }
            },
            "summary": {
                "total_wafers_processed": 100,
                "total_equipment": 4,
                "alerts_by_severity": {"warning": 2, "critical": 1},
                "avg_yield_10_wafers": 94.2
            },
            "timestamp": datetime.utcnow().isoformat()
        }
