"""
Sensors Router
Handles all sensor data endpoints for real-time monitoring
"""
import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Query, Body

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/sensors",
    tags=["Sensors"],
    responses={404: {"description": "Not found"}},
)

# Dependencies (injected from main.py on startup)
mongodb_connector_class = None
sensor_data_writer_class = None
convert_objectids_func = None
mdb_uri: str | None = None
mdb_database_name: str | None = None
mdb_timeseries_collection: str | None = None


def set_dependencies(
    connector_class,
    sensor_writer_class,
    convert_func,
    uri: str,
    db_name: str,
    timeseries_collection: str
):
    """
    Inject dependencies from main.py
    
    Args:
        connector_class: MongoDBConnector class for sync operations
        sensor_writer_class: SensorDataWriter class for dual writes
        convert_func: Function to convert ObjectIds to strings
        uri: MongoDB URI
        db_name: MongoDB database name
        timeseries_collection: Timeseries collection name
    """
    global mongodb_connector_class, sensor_data_writer_class, convert_objectids_func
    global mdb_uri, mdb_database_name, mdb_timeseries_collection
    
    mongodb_connector_class = connector_class
    sensor_data_writer_class = sensor_writer_class
    convert_objectids_func = convert_func
    mdb_uri = uri
    mdb_database_name = db_name
    mdb_timeseries_collection = timeseries_collection
    
    logger.info("✅ Sensors dependencies injected into router")


def get_mongodb_connector():
    """Get MongoDB connector with error handling"""
    if mongodb_connector_class is None or mdb_uri is None or mdb_database_name is None:
        logger.error("❌ MongoDB connector not initialized")
        raise HTTPException(status_code=500, detail="Database connection not initialized")
    return mongodb_connector_class(uri=mdb_uri, database_name=mdb_database_name)


def get_sensor_writer():
    """
    Get SensorDataWriter with error handling
    
    Note: We're using MongoDBConnector directly instead of SensorDataWriter
    to avoid async client initialization issues in sync endpoints.
    """
    if mongodb_connector_class is None or mdb_uri is None or mdb_database_name is None:
        logger.error("❌ MongoDB connector not initialized")
        raise HTTPException(status_code=500, detail="MongoDB connector not initialized")
    return mongodb_connector_class(uri=mdb_uri, database_name=mdb_database_name)


def convert_objectids(data: Any) -> Any:
    """Convert ObjectIds in data using injected function"""
    if convert_objectids_func is None:
        logger.error("❌ convert_objectids function not initialized")
        raise HTTPException(status_code=500, detail="Conversion function not available")
    return convert_objectids_func(data)


logger.info("📦 Sensors router initialized")


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/write")
async def write_sensor_data(data: Dict[str, Any] = Body(...)):
    """
    Write sensor data to trigger monitoring and wafer generation

    Note: Uses synchronous MongoDB operations for consistency with other endpoints.
    FastAPI handles thread pool execution automatically.

    Example body:
    {
        "equipment_id": "CMP_TOOL_01",
        "process_step": "CMP",
        "timestamp": "2025-01-16T12:00:00Z",
        "metrics": {
            "particle_count": 1500,
            "rf_power": 1200,
            "chamber_pressure": 45,
            "temperature": 65,
            "flow_rate": 200
        },
        "metadata": {
            "lot_id": "LOT_TEST_001",
            "wafer_id": "W_TEST_001"
        }
    }
    """
    start_time = time.time()
    equipment_id = data.get("equipment_id", "UNKNOWN")
    logger.info(f"📥 POST /sensors/write - Request for equipment_id={equipment_id}")
    
    try:
        # Ensure timestamp is datetime object
        if "timestamp" not in data:
            data["timestamp"] = datetime.now(timezone.utc)
            logger.debug(f"⚙️ No timestamp provided, using current UTC: {data['timestamp']}")
        elif isinstance(data["timestamp"], str):
            original_timestamp = data["timestamp"]
            data["timestamp"] = datetime.fromisoformat(data["timestamp"].replace('Z', '+00:00'))
            logger.debug(f"⚙️ Converted timestamp from '{original_timestamp}' to datetime: {data['timestamp']}")

        # Validate required fields
        logger.debug(f"⚙️ Validating required fields for equipment_id={equipment_id}")
        if "equipment_id" not in data:
            logger.error(f"❌ POST /sensors/write - Validation failed: equipment_id is required")
            raise HTTPException(status_code=400, detail="equipment_id is required")
        if "metrics" not in data:
            logger.error(f"❌ POST /sensors/write - Validation failed: metrics are required for equipment_id={equipment_id}")
            raise HTTPException(status_code=400, detail="metrics are required")
        
        logger.debug(f"✅ Validation passed for equipment_id={equipment_id}")

        # Add process step if not provided
        if "process_step" not in data:
            data["process_step"] = data["equipment_id"].split("_")[0]
            logger.debug(f"⚙️ Auto-generated process_step from equipment_id: {data['process_step']}")
        else:
            logger.debug(f"⚙️ Using provided process_step: {data['process_step']}")

        # Use MongoDBConnector for dual writes to both collections
        # (avoiding SensorDataWriter to prevent async client initialization issues)
        logger.debug(f"⚙️ Initializing MongoDB connector for equipment_id={equipment_id}")
        connector = get_mongodb_connector()
        
        result = {
            "sensor_events": None,
            "process_sensor_ts": None,
            "success": False,
            "errors": []
        }
        
        try:
            # Write to sensor_events (for real-time monitoring)
            logger.info(f"   📊 Writing to sensor_events for {equipment_id} with metrics: {list(data['metrics'].keys())}")
            sensor_events_coll = connector.get_collection("sensor_events")
            try:
                result_events = sensor_events_coll.insert_one(data.copy())
                result["sensor_events"] = str(result_events.inserted_id)
                logger.debug(f"   ✅ Inserted into sensor_events: {result_events.inserted_id}")
            except Exception as e:
                logger.error(f"   ❌ Failed to insert into sensor_events: {e}")
                result["errors"].append(f"sensor_events: {str(e)}")

            # Write to process_sensor_ts (for historical analysis)
            logger.debug(f"   ⚙️ Writing to process_sensor_ts for {equipment_id}")
            process_sensor_ts_coll = connector.get_collection(mdb_timeseries_collection)
            try:
                result_ts = process_sensor_ts_coll.insert_one(data.copy())
                result["process_sensor_ts"] = str(result_ts.inserted_id)
                logger.debug(f"   ✅ Inserted into process_sensor_ts: {result_ts.inserted_id}")
            except Exception as e:
                logger.error(f"   ❌ Failed to insert into process_sensor_ts: {e}")
                result["errors"].append(f"process_sensor_ts: {str(e)}")

            # Mark success if at least one write succeeded
            result["success"] = bool(result["sensor_events"] or result["process_sensor_ts"])
            
        finally:
            connector.close_connection()
            logger.debug(f"⚙️ MongoDB connector closed for equipment_id={equipment_id}")

        # Log the results
        if result["success"]:
            particle_count = data['metrics'].get('particle_count', 0)
            sensor_events_id = result.get('sensor_events')
            process_sensor_ts_id = result.get('process_sensor_ts')
            
            logger.info(f"   ✅ Dual write successful for {equipment_id}: "
                       f"particle_count={particle_count}, "
                       f"sensor_events_id={sensor_events_id}, "
                       f"process_sensor_ts_id={process_sensor_ts_id}")
        else:
            logger.warning(f"   ⚠️ Partial write for {equipment_id}: {result.get('errors', [])}")

        # Return success if at least one write succeeded
        if result["success"]:
            elapsed_time = (time.time() - start_time) * 1000  # Convert to ms
            logger.info(f"✅ POST /sensors/write - Success for {equipment_id} in {elapsed_time:.2f}ms")
            
            return {
                "status": "success",
                "message": f"Sensor data written for {data['equipment_id']}",
                "details": {
                    "sensor_events_id": result.get("sensor_events"),
                    "process_sensor_ts_id": result.get("process_sensor_ts"),
                    "dual_write": True
                },
                "document_id": result.get("sensor_events") or result.get("process_sensor_ts"),
                "metrics": data["metrics"],
                "note": "If particle_count > 1000, alert will be created and wafer generated in 10 seconds"
            }
        else:
            # If both writes failed, raise an error
            error_detail = f"Failed to write sensor data: {result.get('errors', [])}"
            logger.error(f"❌ POST /sensors/write - Both writes failed for {equipment_id}: {error_detail}")
            raise HTTPException(
                status_code=500,
                detail=error_detail
            )

    except HTTPException:
        raise
    except Exception as e:
        elapsed_time = (time.time() - start_time) * 1000  # Convert to ms
        logger.error(f"❌ POST /sensors/write - Error for {equipment_id} after {elapsed_time:.2f}ms: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/realtime")
async def get_realtime_sensors(
    equipment_id: Optional[str] = Query(None, description="Filter by equipment ID"),
    metric: Optional[str] = Query(None, description="Specific metric to retrieve"),
    limit: int = Query(50, description="Number of records to return")
):
    """
    Get real-time sensor data for monitoring dashboard
    """
    start_time = time.time()
    logger.info(f"📥 GET /sensors/realtime - Request with equipment_id={equipment_id}, metric={metric}, limit={limit}")
    
    try:
        with get_mongodb_connector() as mdb_connector:
            logger.debug(f"⚙️ MongoDB connector established for /sensors/realtime")
            sensor_collection = mdb_connector.get_collection(mdb_timeseries_collection)
            
            # Build query
            query = {}
            if equipment_id:
                query["equipment_id"] = equipment_id
                logger.debug(f"⚙️ Query filter: equipment_id={equipment_id}")
            else:
                logger.debug(f"⚙️ No equipment filter - fetching latest from all equipment")
            
            # Get latest sensor readings
            if equipment_id:
                # Get single equipment data
                pipeline = [
                    {"$match": query},
                    {"$sort": {"timestamp": -1}},
                    {"$limit": limit}
                ]
                logger.info(f"   📊 Executing aggregation for single equipment: {equipment_id}")
                sensors = list(sensor_collection.aggregate(pipeline))
                logger.debug(f"   ✅ Retrieved {len(sensors)} records for {equipment_id}")
            else:
                # Get latest from each equipment
                pipeline = [
                    {"$sort": {"timestamp": -1}},
                    {"$group": {
                        "_id": "$equipment_id",
                        "latest": {"$first": "$$ROOT"}
                    }},
                    {"$replaceRoot": {"newRoot": "$latest"}},
                    {"$limit": limit}
                ]
                logger.info(f"   📊 Executing aggregation for latest from all equipment")
                sensors = list(sensor_collection.aggregate(pipeline))
                logger.debug(f"   ✅ Retrieved latest from {len(sensors)} equipment")
            
            # Convert ObjectIds
            logger.debug(f"⚙️ Converting ObjectIds")
            sensors = convert_objectids(sensors)
            
            elapsed_time = (time.time() - start_time) * 1000  # Convert to ms
            logger.info(f"✅ GET /sensors/realtime - Success: {len(sensors)} records in {elapsed_time:.2f}ms")
            
            return {
                "count": len(sensors),
                "data": sensors
            }
            
    except HTTPException:
        raise
    except Exception as e:
        elapsed_time = (time.time() - start_time) * 1000  # Convert to ms
        logger.error(f"❌ GET /sensors/realtime - Error after {elapsed_time:.2f}ms: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stream/{equipment_id}")
async def get_sensor_stream(
    equipment_id: str,
    window_minutes: int = Query(60, description="Time window in minutes"),
    interval: int = Query(1, description="Data point interval in minutes")
):
    """
    Get sensor data stream for specific equipment
    """
    start_time = time.time()
    logger.info(f"📥 GET /sensors/stream/{equipment_id} - Request with window_minutes={window_minutes}, interval={interval}")
    
    try:
        with get_mongodb_connector() as mdb_connector:
            logger.debug(f"⚙️ MongoDB connector established for /sensors/stream/{equipment_id}")
            sensor_collection = mdb_connector.get_collection(mdb_timeseries_collection)
            
            # Calculate time window
            end_time = datetime.now()
            start_time_query = end_time - timedelta(minutes=window_minutes)
            logger.debug(f"⚙️ Time window: {start_time_query} to {end_time} ({window_minutes} minutes)")
            
            # Aggregate data with time buckets
            pipeline = [
                {"$match": {
                    "equipment_id": equipment_id,
                    "timestamp": {"$gte": start_time_query, "$lte": end_time}
                }},
                {"$sort": {"timestamp": 1}},
                {"$group": {
                    "_id": {
                        "$dateTrunc": {
                            "date": "$timestamp",
                            "unit": "minute",
                            "binSize": interval
                        }
                    },
                    "metrics": {"$avg": "$metrics"},
                    "count": {"$sum": 1}
                }},
                {"$sort": {"_id": 1}}
            ]
            
            logger.info(f"   📊 Executing time-bucketed aggregation for {equipment_id} (interval={interval}min)")
            data_points = list(sensor_collection.aggregate(pipeline))
            logger.debug(f"   ✅ Retrieved {len(data_points)} data points for {equipment_id}")
            
            # Format response
            logger.debug(f"⚙️ Formatting {len(data_points)} data points")
            formatted_data = []
            for point in data_points:
                formatted_data.append({
                    "timestamp": point["_id"],
                    "metrics": point["metrics"],
                    "sample_count": point["count"]
                })
            
            elapsed_time = (time.time() - start_time) * 1000  # Convert to ms
            logger.info(f"✅ GET /sensors/stream/{equipment_id} - Success: {len(formatted_data)} data points in {elapsed_time:.2f}ms")
            
            return {
                "equipment_id": equipment_id,
                "window_minutes": window_minutes,
                "interval_minutes": interval,
                "data_points": formatted_data,
                "count": len(formatted_data)
            }
            
    except HTTPException:
        raise
    except Exception as e:
        elapsed_time = (time.time() - start_time) * 1000  # Convert to ms
        logger.error(f"❌ GET /sensors/stream/{equipment_id} - Error after {elapsed_time:.2f}ms: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

