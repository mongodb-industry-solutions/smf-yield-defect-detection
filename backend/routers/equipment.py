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

            # OPTIMIZED: Project specific fields before grouping (avoids $$ROOT)
            {"$project": {
                "equipment_id": 1,
                "process_step": 1,
                "timestamp": 1,
                "metrics": 1
            }},

            # Group by equipment to get latest reading
            {"$group": {
                "_id": "$equipment_id",
                "process_step": {"$first": "$process_step"},
                "last_update": {"$first": "$timestamp"},
                "current_metrics": {"$first": "$metrics"}
            }},

            # Project with proper field names
            {"$project": {
                "equipment_id": "$_id",
                "process_step": 1,
                "last_update": 1,
                "current_metrics": 1
            }}
        ]

        # Execute aggregation asynchronously
        query_start = time.time()
        logger.info("   📊 Executing equipment aggregation pipeline...")
        cursor = sensor_collection.aggregate(pipeline)
        equipment_list = await cursor.to_list(length=None)
        query_time = (time.time() - query_start) * 1000
        logger.info(f"   📊 Equipment query completed in {query_time:.0f}ms, found {len(equipment_list)} equipment")

        # Get all open alerts for equipment (only from last 15 minutes)
        alerts_start = time.time()
        fifteen_minutes_ago = datetime.utcnow() - timedelta(minutes=15)
        logger.info("   🚨 Fetching open alerts for equipment...")
        open_alerts = await alerts_collection.find({
            "status": {"$in": ["open", "acknowledged"]},
            "equipment_id": {"$exists": True},
            "timestamp": {"$gte": fifteen_minutes_ago}
        }).to_list(length=None)
        alerts_time = (time.time() - alerts_start) * 1000
        logger.info(f"   🚨 Alerts query completed in {alerts_time:.0f}ms, found {len(open_alerts)} open alerts")

        # Create a map of equipment_id to highest severity alert (with frozen metrics)
        processing_start = time.time()
        logger.debug("⚙️ Processing alert severity mapping...")
        equipment_alerts = {}
        for alert in open_alerts:
            eq_id = alert.get("equipment_id")
            severity = alert.get("severity", "medium")
            # Get the frozen metrics from when alert was created
            alert_metrics = alert.get("source_data", {}).get("metrics")
            alert_timestamp = alert.get("timestamp")

            # Keep highest severity alert for each equipment (with its frozen metrics)
            if eq_id:
                if eq_id not in equipment_alerts:
                    equipment_alerts[eq_id] = {
                        "severity": severity,
                        "metrics": alert_metrics,
                        "timestamp": alert_timestamp
                    }
                else:
                    # Priority: critical > high > medium > low
                    severity_priority = {"critical": 4, "high": 3, "medium": 2, "low": 1}
                    current_priority = severity_priority.get(equipment_alerts[eq_id]["severity"], 0)
                    new_priority = severity_priority.get(severity, 0)
                    if new_priority > current_priority:
                        equipment_alerts[eq_id] = {
                            "severity": severity,
                            "metrics": alert_metrics,
                            "timestamp": alert_timestamp
                        }

        # Add status based on alerts and freeze metrics if alert is open
        logger.debug("⚙️ Calculating equipment status based on alerts...")
        for eq in equipment_list:
            eq_id = eq.get("equipment_id")
            if eq_id in equipment_alerts:
                alert_data = equipment_alerts[eq_id]
                alert_severity = alert_data["severity"]

                # Map alert severity to equipment status
                if alert_severity == "critical":
                    eq["status"] = "critical"
                elif alert_severity == "high":
                    eq["status"] = "warning"
                else:
                    eq["status"] = "warning"  # medium/low alerts show as warning

                # FREEZE METRICS: Use alert's metrics instead of live metrics
                if alert_data.get("metrics"):
                    eq["current_metrics"] = alert_data["metrics"]
                    eq["last_update"] = alert_data.get("timestamp", eq.get("last_update"))
                    logger.debug(f"🔒 Frozen metrics for {eq_id} (alert active)")
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


@router.get("/{equipment_id}/details")
async def get_equipment_details(
    equipment_id: str,
    hours: int = Query(24, description="Time window in hours for historical data")
):
    """
    Get comprehensive equipment details including:
    - Current status and metrics
    - Related lots and wafers
    - Process materials (slurry batches, recipes, reticles)
    - Recent alerts
    - Performance statistics
    """
    start_time = time.time()
    logger.info(f"📥 GET /equipment/{equipment_id}/details - Request with hours={hours}")

    try:
        # Validate dependencies
        if mongodb_client is None or mdb_database_name is None or mdb_timeseries_collection is None:
            logger.error("❌ MongoDB client not initialized")
            raise HTTPException(status_code=500, detail="Database connection not initialized")

        # Use async MongoDB client for parallel queries
        db = mongodb_client[mdb_database_name]
        sensor_collection = db[mdb_timeseries_collection]
        wafer_collection = db["wafer_defects"]
        alerts_collection = db["alerts"]
        process_context_collection = db["process_context"]

        # Calculate time window
        end_time = datetime.utcnow()
        start_time_query = end_time - timedelta(hours=hours)
        logger.debug(f"⚙️ Time window: {start_time_query} to {end_time} ({hours} hours)")

        # === QUERY 1: Latest equipment metrics and status ===
        query1_start = time.time()
        latest_sensor_pipeline = [
            {"$match": {
                "equipment_id": equipment_id,
                "timestamp": {"$gte": start_time_query}
            }},
            {"$sort": {"timestamp": -1}},
            {"$limit": 1}
        ]

        cursor = sensor_collection.aggregate(latest_sensor_pipeline)
        latest_sensors = await cursor.to_list(length=1)
        latest_reading = latest_sensors[0] if latest_sensors else None
        query1_time = (time.time() - query1_start) * 1000
        logger.info(f"   📊 Query 1 (Latest metrics) completed in {query1_time:.0f}ms")

        # === QUERY 2: Related wafers processed by this equipment ===
        query2_start = time.time()
        wafer_pipeline = [
            {"$match": {
                "process_context.equipment_used": equipment_id,
                "inspection_timestamp": {
                    "$gte": start_time_query.isoformat() + "Z",
                    "$lte": end_time.isoformat() + "Z"
                }
            }},
            {"$sort": {"inspection_timestamp": -1}},
            {"$limit": 20}
        ]

        cursor = wafer_collection.aggregate(wafer_pipeline)
        wafers = await cursor.to_list(length=20)
        query2_time = (time.time() - query2_start) * 1000
        logger.info(f"   📊 Query 2 (Related wafers) completed in {query2_time:.0f}ms, found {len(wafers)} wafers")

        # === QUERY 3: Aggregate lots from wafers ===
        query3_start = time.time()
        lot_aggregation = {}
        for wafer in wafers:
            lot_id = wafer.get("lot_id")
            if lot_id:
                if lot_id not in lot_aggregation:
                    lot_aggregation[lot_id] = {
                        "lot_id": lot_id,
                        "wafer_count": 0,
                        "yields": [],
                        "first_inspection": wafer.get("inspection_timestamp"),
                        "last_inspection": wafer.get("inspection_timestamp")
                    }

                lot_data = lot_aggregation[lot_id]
                lot_data["wafer_count"] += 1
                lot_data["yields"].append(wafer.get("defect_summary", {}).get("yield_percentage", 0))

                # Update inspection period
                inspection_time = wafer.get("inspection_timestamp")
                if inspection_time < lot_data["first_inspection"]:
                    lot_data["first_inspection"] = inspection_time
                if inspection_time > lot_data["last_inspection"]:
                    lot_data["last_inspection"] = inspection_time

        # Calculate lot statistics
        related_lots = []
        for lot_id, lot_data in lot_aggregation.items():
            avg_yield = sum(lot_data["yields"]) / len(lot_data["yields"]) if lot_data["yields"] else 0
            related_lots.append({
                "lot_id": lot_id,
                "wafer_count": lot_data["wafer_count"],
                "avg_yield": round(avg_yield, 2),
                "inspection_period": f"{lot_data['first_inspection'][:10]} to {lot_data['last_inspection'][:10]}"
            })

        query3_time = (time.time() - query3_start) * 1000
        logger.info(f"   📊 Query 3 (Lot aggregation) completed in {query3_time:.0f}ms, found {len(related_lots)} lots")

        # === QUERY 4: Process materials used with this equipment ===
        query4_start = time.time()

        # Get unique slurry batches from wafers
        slurry_batches = []
        recipes = []
        reticles = []

        slurry_batch_ids = set()
        recipe_ids = set()
        reticle_ids = set()

        for wafer in wafers:
            process_ctx = wafer.get("process_context", {})

            if "slurry_batch" in process_ctx:
                slurry_batch_ids.add(process_ctx["slurry_batch"])

            if "etch_recipe" in process_ctx:
                recipe_ids.add(process_ctx["etch_recipe"])

            if "reticle_id" in process_ctx:
                reticle_ids.add(process_ctx["reticle_id"])

        # Query process_context collection for material details
        # NOTE: process_context uses "context_type" and "context_id" fields
        if slurry_batch_ids:
            cursor = process_context_collection.find({
                "context_type": "slurry_batch",
                "context_id": {"$in": list(slurry_batch_ids)}
            })
            slurry_docs = await cursor.to_list(length=None)

            for doc in slurry_docs:
                context_id = doc.get("context_id")
                slurry_batches.append({
                    "batch_id": context_id,
                    "usage_count": sum(1 for w in wafers if w.get("process_context", {}).get("slurry_batch") == context_id),
                    "is_problematic": doc.get("is_problematic", False),
                    "known_issues": doc.get("known_issues", []),
                    "manufacturer": doc.get("slurry_details", {}).get("manufacturer"),
                    "composition": doc.get("slurry_details", {}).get("composition"),
                    "qc_status": doc.get("slurry_details", {}).get("qc_status")
                })

        if recipe_ids:
            cursor = process_context_collection.find({
                "context_type": "etch_recipe",
                "context_id": {"$in": list(recipe_ids)}
            })
            recipe_docs = await cursor.to_list(length=None)

            for doc in recipe_docs:
                context_id = doc.get("context_id")
                recipes.append({
                    "recipe_id": context_id,
                    "usage_count": sum(1 for w in wafers if w.get("process_context", {}).get("etch_recipe") == context_id)
                })

        if reticle_ids:
            cursor = process_context_collection.find({
                "context_type": "reticle",
                "context_id": {"$in": list(reticle_ids)}
            })
            reticle_docs = await cursor.to_list(length=None)

            for doc in reticle_docs:
                context_id = doc.get("context_id")
                reticles.append({
                    "reticle_id": context_id,
                    "usage_count": sum(1 for w in wafers if w.get("process_context", {}).get("reticle_id") == context_id)
                })

        query4_time = (time.time() - query4_start) * 1000
        logger.info(f"   📊 Query 4 (Process materials) completed in {query4_time:.0f}ms")

        # === QUERY 5: Recent alerts ===
        query5_start = time.time()
        cursor = alerts_collection.find({
            "equipment_id": equipment_id,
            "timestamp": {"$gte": start_time_query}
        }).sort("timestamp", -1).limit(10)

        alert_docs = await cursor.to_list(length=10)

        recent_alerts = []
        for alert in alert_docs:
            recent_alerts.append({
                "alert_id": str(alert.get("_id")),
                "severity": alert.get("severity"),
                "alert_type": alert.get("alert_type"),
                "timestamp": alert.get("timestamp").isoformat() if alert.get("timestamp") else None,
                "status": alert.get("status")
            })

        query5_time = (time.time() - query5_start) * 1000
        logger.info(f"   📊 Query 5 (Recent alerts) completed in {query5_time:.0f}ms, found {len(recent_alerts)} alerts")

        # === QUERY 6: Performance statistics ===
        query6_start = time.time()
        stats_pipeline = [
            {"$match": {
                "equipment_id": equipment_id,
                "timestamp": {"$gte": start_time_query, "$lte": end_time}
            }},
            {"$group": {
                "_id": None,
                "total_readings": {"$sum": 1},
                "excursion_count": {
                    "$sum": {
                        "$cond": [{"$gt": ["$metrics.particle_count", 1000]}, 1, 0]
                    }
                }
            }}
        ]

        cursor = sensor_collection.aggregate(stats_pipeline)
        stats_result = await cursor.to_list(length=1)
        stats = stats_result[0] if stats_result else {"total_readings": 0, "excursion_count": 0}

        # Calculate statistics
        total_wafers = len(wafers)
        avg_yield_24h = sum(w.get("defect_summary", {}).get("yield_percentage", 0) for w in wafers) / total_wafers if total_wafers > 0 else 0
        utilization = min(100, (stats.get("total_readings", 0) / (hours * 60)) * 100)

        query6_time = (time.time() - query6_start) * 1000
        logger.info(f"   📊 Query 6 (Statistics) completed in {query6_time:.0f}ms")

        # === Determine equipment status from alerts ===
        status = "good"
        if recent_alerts:
            open_alerts = [a for a in recent_alerts if a["status"] in ["open", "acknowledged"]]
            if open_alerts:
                severities = [a["severity"] for a in open_alerts]
                if "critical" in severities:
                    status = "critical"
                elif "high" in severities:
                    status = "warning"
                else:
                    status = "warning"

        # === Format related wafers for response ===
        related_wafers = []
        for wafer in wafers[:10]:  # Limit to 10 for response size
            related_wafers.append({
                "wafer_id": wafer.get("wafer_id"),
                "lot_id": wafer.get("lot_id"),
                "yield_percentage": wafer.get("defect_summary", {}).get("yield_percentage"),
                "defect_pattern": wafer.get("defect_summary", {}).get("defect_pattern"),
                "inspection_timestamp": wafer.get("inspection_timestamp")
            })

        # === Build response ===
        response = {
            "equipment_id": equipment_id,
            "process_step": latest_reading.get("process_step") if latest_reading else equipment_id.split("_")[0],
            "status": status,
            "current_metrics": latest_reading.get("metrics") if latest_reading else None,
            "last_update": latest_reading.get("timestamp").isoformat() if latest_reading and latest_reading.get("timestamp") else None,
            "related_lots": related_lots,
            "related_wafers": related_wafers,
            "process_materials": {
                "slurry_batches": slurry_batches,
                "recipes": recipes,
                "reticles": reticles
            },
            "recent_alerts": recent_alerts,
            "statistics": {
                "total_wafers_processed": total_wafers,
                "avg_yield_24h": round(avg_yield_24h, 2),
                "excursion_count_24h": stats.get("excursion_count", 0),
                "utilization_percentage": round(utilization, 2)
            },
            "time_window_hours": hours
        }

        total_time = (time.time() - start_time) * 1000
        logger.info(f"✅ GET /equipment/{equipment_id}/details - Success in {total_time:.0f}ms")

        return response

    except HTTPException:
        raise
    except Exception as e:
        elapsed_time = (time.time() - start_time) * 1000
        logger.error(f"❌ GET /equipment/{equipment_id}/details - Error after {elapsed_time:.0f}ms: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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

