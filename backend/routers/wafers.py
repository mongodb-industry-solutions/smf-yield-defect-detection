"""
Wafers Router
Handles all wafer-related endpoints for the yield defect detection system
"""
import logging
import time
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Query, Body

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/wafers",
    tags=["Wafers"],
    responses={404: {"description": "Not found"}},
)

# Dependencies (injected from main.py on startup)
mongodb_connector_class = None
convert_objectids_func = None
mongodb_client_instance = None
wafer_generator_instance = None
excursion_detector_instance = None
demo_service_instance = None
mdb_uri = None
mdb_database_name = None
use_ai_agents_flag = True


def set_dependencies(
    connector_class,
    convert_func,
    mongodb_client=None,
    wafer_generator=None,
    excursion_detector=None,
    demo_service=None,
    uri=None,
    db_name=None,
    use_ai_agents=True
):
    """
    Inject dependencies from main.py
    
    Args:
        connector_class: MongoDBConnector class for sync operations
        convert_func: Function to convert ObjectIds to strings
        mongodb_client: AsyncIOMotorClient for async operations
        wafer_generator: WaferGenerator instance for wafer creation
        excursion_detector: ExcursionDetector instance for injecting wafers
        demo_service: DemoModeService instance for demo integration
        uri: MongoDB URI
        db_name: MongoDB database name
        use_ai_agents: Feature flag for AI multi-agent system
    """
    global mongodb_connector_class, convert_objectids_func, mongodb_client_instance
    global wafer_generator_instance, excursion_detector_instance, demo_service_instance
    global mdb_uri, mdb_database_name, use_ai_agents_flag
    
    mongodb_connector_class = connector_class
    convert_objectids_func = convert_func
    mongodb_client_instance = mongodb_client
    wafer_generator_instance = wafer_generator
    excursion_detector_instance = excursion_detector
    demo_service_instance = demo_service
    mdb_uri = uri
    mdb_database_name = db_name
    use_ai_agents_flag = use_ai_agents
    
    logger.info("✅ Wafers dependencies injected into router")


def get_mongodb_connector():
    """Get MongoDB connector with error handling"""
    if mongodb_connector_class is None or mdb_uri is None or mdb_database_name is None:
        logger.error("❌ MongoDB connector not initialized")
        raise HTTPException(status_code=500, detail="Database connection not initialized")
    return mongodb_connector_class(uri=mdb_uri, database_name=mdb_database_name)


def convert_objectids(data):
    """Convert ObjectIds in data using injected function"""
    if convert_objectids_func is None:
        logger.error("❌ convert_objectids function not initialized")
        raise HTTPException(status_code=500, detail="Conversion function not available")
    return convert_objectids_func(data)


logger.info("📦 Wafers router initialized")


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.get("/latest")
async def get_latest_wafers(
    limit: int = Query(10, description="Number of wafers to return"),
    pattern: Optional[str] = Query(None, description="Filter by defect pattern"),
    min_yield: Optional[float] = Query(None, description="Minimum yield percentage"),
    include_visualization: bool = Query(False, description="Include die_map and defects for visualization")
):
    """
    Get latest wafer inspection results with optional visualization data
    """
    start_time = time.time()
    logger.info(f"📥 GET /wafers/latest - limit={limit}, pattern={pattern}, min_yield={min_yield}, include_viz={include_visualization}")
    
    try:
        logger.debug(f"🔍 Opening MongoDB connection to fetch wafers")
        
        with get_mongodb_connector() as mdb_connector:
            wafer_collection = mdb_connector.get_collection("wafer_defects")

            # Build query
            query = {}
            if pattern:
                query["defect_summary.defect_pattern"] = pattern
                logger.debug(f"🔍 Filtering by pattern: {pattern}")
            if min_yield:
                query["defect_summary.yield_percentage"] = {"$gte": min_yield}
                logger.debug(f"🔍 Filtering by min_yield >= {min_yield}")

            # Build projection based on include_visualization flag
            projection = None
            if not include_visualization:
                # Exclude die_map and limit defects when not needed for visualization
                projection = {"die_map": 0}  # Exclude die_map to reduce payload
                logger.debug(f"📊 Using projection to exclude die_map")

            # Get latest wafers
            query_start = time.time()
            if projection:
                wafers = list(wafer_collection.find(query, projection).sort("inspection_timestamp", -1).limit(limit))
            else:
                wafers = list(wafer_collection.find(query).sort("inspection_timestamp", -1).limit(limit))
            query_time = (time.time() - query_start) * 1000
            logger.info(f"   📊 MongoDB query completed in {query_time:.0f}ms, found {len(wafers)} wafers")

            # Process wafers based on visualization flag
            process_start = time.time()
            for wafer in wafers:
                if not include_visualization:
                    # Remove large image data for API response
                    if "ink_map" in wafer and "thumbnail_base64" in wafer["ink_map"]:
                        # Keep only first 100 chars of thumbnail for preview
                        wafer["ink_map"]["has_thumbnail"] = True
                        wafer["ink_map"]["thumbnail_preview"] = wafer["ink_map"]["thumbnail_base64"][:100] + "..."
                        del wafer["ink_map"]["thumbnail_base64"]

                    # Limit defects array to reduce payload
                    if "defects" in wafer and len(wafer.get("defects", [])) > 5:
                        wafer["defects"] = wafer["defects"][:5]
                        wafer["defects_truncated"] = True
                else:
                    # When including visualization, keep full_image_base64 for display
                    if "ink_map" in wafer:
                        # Keep full_image_base64 for visualization
                        # Only remove thumbnail to save bandwidth (thumbnail not used when full image available)
                        if "thumbnail_base64" in wafer["ink_map"]:
                            del wafer["ink_map"]["thumbnail_base64"]  # Remove to reduce size

            process_time = (time.time() - process_start) * 1000
            logger.info(f"   🔧 Wafer processing completed in {process_time:.0f}ms")

            convert_start = time.time()
            wafers = convert_objectids(wafers)
            convert_time = (time.time() - convert_start) * 1000
            logger.info(f"   🔄 ObjectId conversion completed in {convert_time:.0f}ms")

            total_time = (time.time() - start_time) * 1000

            # Calculate total payload size
            import json
            payload_size = len(json.dumps(wafers)) / 1024  # KB
            logger.info(f"   📦 Response payload size: {payload_size:.1f}KB")
            logger.info(f"✅ GET /wafers/latest completed in {total_time:.0f}ms - {len(wafers)} wafers returned")

            return {
                "count": len(wafers),
                "wafers": wafers,
                "visualization_included": include_visualization
            }

    except HTTPException:
        total_time = (time.time() - start_time) * 1000
        logger.warning(f"⚠️ GET /wafers/latest - HTTPException after {total_time:.0f}ms")
        raise
    except Exception as e:
        total_time = (time.time() - start_time) * 1000
        logger.error(f"❌ GET /wafers/latest - Error after {total_time:.0f}ms: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batches")
async def get_wafer_batches(
    limit: int = Query(5, description="Number of batches to return"),
    include_stats: bool = Query(True, description="Include batch statistics")
):
    """
    Get wafer batch history with statistics
    """
    start_time = time.time()
    logger.info(f"📥 GET /wafers/batches - limit={limit}, include_stats={include_stats}")
    
    try:
        logger.debug(f"🔍 Opening MongoDB connection for batch aggregation")
        
        with get_mongodb_connector() as mdb_connector:
            wafer_collection = mdb_connector.get_collection("wafer_defects")
            
            logger.debug(f"⚙️ Building aggregation pipeline for batch grouping")
            
            # Aggregate by lot_id to get batches
            pipeline = [
                {"$sort": {"inspection_timestamp": -1}},
                {"$group": {
                    "_id": "$lot_id",
                    "batch_timestamp": {"$first": "$inspection_timestamp"},
                    "wafer_count": {"$sum": 1},
                    "avg_yield": {"$avg": "$defect_summary.yield_percentage"},
                    "min_yield": {"$min": "$defect_summary.yield_percentage"},
                    "max_yield": {"$max": "$defect_summary.yield_percentage"},
                    "patterns": {"$addToSet": "$defect_summary.defect_pattern"},
                    "wafers": {"$push": {
                        "wafer_id": "$wafer_id",
                        "yield": "$defect_summary.yield_percentage",
                        "pattern": "$defect_summary.defect_pattern"
                    }}
                }},
                {"$sort": {"batch_timestamp": -1}},
                {"$limit": limit}
            ]
            
            query_start = time.time()
            batches = list(wafer_collection.aggregate(pipeline))
            query_time = (time.time() - query_start) * 1000
            logger.info(f"   📊 MongoDB aggregation completed in {query_time:.0f}ms, found {len(batches)} batches")
            
            # Format response
            process_start = time.time()
            formatted_batches = []
            for batch in batches:
                batch_data = {
                    "lot_id": batch["_id"],
                    "timestamp": batch["batch_timestamp"],
                    "wafer_count": batch["wafer_count"]
                }
                
                if include_stats:
                    batch_data.update({
                        "avg_yield": round(batch["avg_yield"], 2),
                        "min_yield": round(batch["min_yield"], 2),
                        "max_yield": round(batch["max_yield"], 2),
                        "defect_patterns": batch["patterns"],
                        "wafer_details": batch["wafers"][:5]  # Limit details
                    })
                
                formatted_batches.append(batch_data)
            
            process_time = (time.time() - process_start) * 1000
            logger.info(f"   🔧 Batch formatting completed in {process_time:.0f}ms")
            
            total_time = (time.time() - start_time) * 1000
            logger.info(f"✅ GET /wafers/batches completed in {total_time:.0f}ms - {len(formatted_batches)} batches returned")
            
            return {
                "count": len(formatted_batches),
                "batches": formatted_batches
            }
    
    except HTTPException:
        total_time = (time.time() - start_time) * 1000
        logger.warning(f"⚠️ GET /wafers/batches - HTTPException after {total_time:.0f}ms")
        raise
    except Exception as e:
        total_time = (time.time() - start_time) * 1000
        logger.error(f"❌ GET /wafers/batches - Error after {total_time:.0f}ms: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/yield-timeline")
async def get_yield_timeline(
    limit: int = Query(50, description="Number of wafers to include in timeline"),
    include_alerts: bool = Query(True, description="Include alert markers")
):
    """
    Get yield trend timeline data for charting
    Returns wafer yield data with optional alert markers for correlation visualization
    """
    start_time = time.time()
    logger.info(f"📥 GET /wafers/yield-timeline - limit={limit}, include_alerts={include_alerts}")
    
    try:
        logger.debug(f"🔍 Opening MongoDB connection for timeline query")
        
        with get_mongodb_connector() as mdb_connector:
            wafer_collection = mdb_connector.get_collection("wafer_defects")
            alert_collection = mdb_connector.get_collection("alerts")

            # Get latest wafers sorted by inspection time
            query_start = time.time()
            wafers = list(wafer_collection.find()
                        .sort("inspection_timestamp", -1)
                        .limit(limit))
            query_time = (time.time() - query_start) * 1000
            logger.info(f"   📊 Wafer query completed in {query_time:.0f}ms, found {len(wafers)} wafers")

            # Reverse to get chronological order for chart
            wafers.reverse()
            logger.debug(f"⚙️ Reversed wafers to chronological order for timeline chart")

            # Extract timeline data
            process_start = time.time()
            timeline_data = []
            for wafer in wafers:
                timeline_data.append({
                    "wafer_id": wafer.get("wafer_id"),
                    "timestamp": wafer.get("inspection_timestamp"),
                    "yield_percentage": wafer.get("defect_summary", {}).get("yield_percentage", 0),
                    "pattern": wafer.get("defect_summary", {}).get("defect_pattern"),
                    "severity": wafer.get("defect_summary", {}).get("severity"),
                    "equipment_id": wafer.get("equipment_id"),
                    "lot_id": wafer.get("lot_id")
                })
            process_time = (time.time() - process_start) * 1000
            logger.info(f"   🔧 Timeline data extraction completed in {process_time:.0f}ms")

            # Get alerts in same timeframe if requested
            alert_markers = []
            if include_alerts and timeline_data:
                logger.debug(f"🔍 Fetching alert markers for timeline timeframe")
                start_ts = timeline_data[0]["timestamp"]
                end_ts = timeline_data[-1]["timestamp"]

                alert_query_start = time.time()
                alerts = list(alert_collection.find({
                    "timestamp": {"$gte": start_ts, "$lte": end_ts}
                }).sort("timestamp", 1))
                alert_query_time = (time.time() - alert_query_start) * 1000
                logger.info(f"   📊 Alert query completed in {alert_query_time:.0f}ms, found {len(alerts)} alerts")

                for alert in alerts:
                    alert_markers.append({
                        "alert_id": alert.get("alert_id"),
                        "timestamp": alert.get("timestamp"),
                        "severity": alert.get("severity"),
                        "equipment_id": alert.get("equipment_id"),
                        "excursion_type": alert.get("source_data", {}).get("excursion_type")
                    })

            # Convert MongoDB dates to ISO strings
            convert_start = time.time()
            timeline_data = convert_objectids(timeline_data)
            alert_markers = convert_objectids(alert_markers)
            convert_time = (time.time() - convert_start) * 1000
            logger.info(f"   🔄 ObjectId conversion completed in {convert_time:.0f}ms")

            # Calculate stats
            stats = {
                "avg_yield": sum(d["yield_percentage"] for d in timeline_data) / len(timeline_data) if timeline_data else 0,
                "min_yield": min(d["yield_percentage"] for d in timeline_data) if timeline_data else 0,
                "max_yield": max(d["yield_percentage"] for d in timeline_data) if timeline_data else 0
            }

            total_time = (time.time() - start_time) * 1000
            logger.info(f"✅ GET /wafers/yield-timeline completed in {total_time:.0f}ms - {len(timeline_data)} datapoints, {len(alert_markers)} alerts")

            return {
                "timeline": timeline_data,
                "alert_markers": alert_markers,
                "count": len(timeline_data),
                "timeframe": {
                    "start": timeline_data[0]["timestamp"] if timeline_data else None,
                    "end": timeline_data[-1]["timestamp"] if timeline_data else None
                },
                "stats": stats
            }

    except HTTPException:
        total_time = (time.time() - start_time) * 1000
        logger.warning(f"⚠️ GET /wafers/yield-timeline - HTTPException after {total_time:.0f}ms")
        raise
    except Exception as e:
        total_time = (time.time() - start_time) * 1000
        logger.error(f"❌ GET /wafers/yield-timeline - Error after {total_time:.0f}ms: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/inject")
async def inject_test_wafer():
    """
    Inject a test wafer defect without excursion link for testing wafer monitoring
    This simulates wafers from manual inspection or batch imports
    """
    start_time = time.time()
    logger.info(f"📥 POST /wafers/inject - Creating test wafer")
    
    try:
        logger.debug(f"🔍 Opening MongoDB connection for wafer injection")
        
        # Connect to MongoDB
        with get_mongodb_connector() as mdb_connector:
            wafer_collection = mdb_connector.get_collection("wafer_defects")

            # Generate a unique wafer ID
            count_start = time.time()
            wafer_count = wafer_collection.count_documents({})
            count_time = (time.time() - count_start) * 1000
            wafer_id = f"W_TEST_{wafer_count + 1:04d}"
            logger.debug(f"📊 Wafer count query completed in {count_time:.0f}ms, new ID: {wafer_id}")

            # Create test wafer with high severity but no excursion link
            logger.debug(f"⚙️ Generating test wafer data with high severity pattern")
            test_wafer = {
                "wafer_id": wafer_id,
                "lot_id": f"LOT_TEST_{datetime.now().strftime('%Y%m%d')}",
                "inspection_timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                "ink_map": {
                    "thumbnail_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
                    "thumbnail_size": [150, 150],
                    "format": "PNG"
                },
                "defect_summary": {
                    "total_dies": 625,
                    "failed_dies": 200,  # High failure count
                    "yield_percentage": 68.0,  # Low yield
                    "defect_pattern": "clustered",  # Pattern that should trigger alert
                    "severity": "high"  # High severity
                },
                "die_map": [[1 if (x*25 + y) < 425 else 0 for y in range(25)] for x in range(25)],
                "defects": [
                    {
                        "type": "particle",
                        "location": {"x": 10.5, "y": 8.3},
                        "size_um": 1.5,
                        "confidence": 0.95
                    },
                    {
                        "type": "particle",
                        "location": {"x": 11.2, "y": 8.8},
                        "size_um": 1.2,
                        "confidence": 0.93
                    }
                ],
                "description": "Test wafer with high-severity clustered defects (manual inspection)",
                "process_context": {
                    "last_process_step": "MANUAL_INSPECTION",
                    "equipment_used": ["INSPECTION_TOOL_01"],
                    "slurry_batch": "SB_TEST_001",
                    "clean_cycle": 150
                    # Note: No excursion_alert_id field
                }
            }

            # Insert the test wafer
            insert_start = time.time()
            result = wafer_collection.insert_one(test_wafer)
            insert_time = (time.time() - insert_start) * 1000
            logger.info(f"   💉 Wafer inserted in {insert_time:.0f}ms, ID: {result.inserted_id}")

            logger.info(f"   📊 Test wafer: {wafer_id}, yield: {test_wafer['defect_summary']['yield_percentage']:.1f}%, pattern: {test_wafer['defect_summary']['defect_pattern']}")

            total_time = (time.time() - start_time) * 1000
            logger.info(f"✅ POST /wafers/inject completed in {total_time:.0f}ms - Wafer {wafer_id} injected")

            return {
                "status": "success",
                "message": f"Test wafer {wafer_id} injected successfully",
                "wafer_id": wafer_id,
                "severity": test_wafer["defect_summary"]["severity"],
                "yield_percentage": test_wafer["defect_summary"]["yield_percentage"],
                "defect_pattern": test_wafer["defect_summary"]["defect_pattern"],
                "has_excursion_link": False,
                "expected_alert": "Should trigger wafer defect alert due to high severity",
                "document_id": str(result.inserted_id)
            }

    except HTTPException:
        total_time = (time.time() - start_time) * 1000
        logger.warning(f"⚠️ POST /wafers/inject - HTTPException after {total_time:.0f}ms")
        raise
    except Exception as e:
        total_time = (time.time() - start_time) * 1000
        logger.error(f"❌ POST /wafers/inject - Error after {total_time:.0f}ms: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{wafer_id}/visualization")
async def get_wafer_visualization(wafer_id: str):
    """
    Get wafer data formatted for visualization in frontend.
    Returns die_map and defect data for rendering wafer maps.

    MongoDB Features: Document queries for complex nested data
    """
    start_time = time.time()
    logger.info(f"📥 GET /wafers/{wafer_id}/visualization - Fetching visualization data")
    
    try:
        logger.debug(f"🔍 Opening MongoDB connection to fetch wafer {wafer_id}")
        
        with get_mongodb_connector() as mdb_connector:
            wafer_collection = mdb_connector.get_collection("wafer_defects")

            # Query wafer from MongoDB
            query_start = time.time()
            wafer = wafer_collection.find_one({"wafer_id": wafer_id})
            query_time = (time.time() - query_start) * 1000
            logger.debug(f"📊 MongoDB query completed in {query_time:.0f}ms")

            if not wafer:
                logger.warning(f"⚠️ Wafer {wafer_id} not found in database")
                raise HTTPException(status_code=404, detail=f"Wafer {wafer_id} not found")

            logger.debug(f"⚙️ Formatting visualization data for wafer {wafer_id}")
            
            # Convert ObjectId to string if present
            if "_id" in wafer:
                wafer["_id"] = str(wafer["_id"])

            # Check die_map and defects for logging
            die_map_size = len(wafer.get("die_map", []))
            defect_count = len(wafer.get("defects", []))
            logger.info(f"   📊 Wafer data: die_map={die_map_size}x{die_map_size}, defects={defect_count}")

            total_time = (time.time() - start_time) * 1000
            logger.info(f"✅ GET /wafers/{wafer_id}/visualization completed in {total_time:.0f}ms")

            # Return visualization-ready data
            return {
                "wafer_id": wafer_id,
                "die_map": wafer.get("die_map", []),  # 25x25 array of 0s and 1s
                "defects": wafer.get("defects", []),  # Array of defect locations with x,y coords
                "defect_summary": wafer.get("defect_summary", {}),
                "visualization_config": {
                    "grid_size": 25,
                    "die_size_pixels": 20,  # Suggested pixel size per die
                    "wafer_diameter_pixels": 500,
                    "colors": {
                        "pass": "#90EE90",  # Light green for good dies
                        "fail": "#FF6B6B",  # Light red for failed dies
                        "border": "#333333",
                        "background": "#F5F5F5",
                        "wafer_edge": "#CCCCCC"
                    },
                    "pattern_colors": {
                        "clustered": "#FF4444",  # Red for clustered defects
                        "edge": "#FFA500",  # Orange for edge defects
                        "systematic": "#9B59B6",  # Purple for systematic
                        "random": "#3498DB"  # Blue for random
                    }
                },
                "metadata": {
                    "lot_id": wafer.get("lot_id"),
                    "inspection_timestamp": wafer.get("inspection_timestamp"),
                    "equipment": wafer.get("process_context", {}).get("equipment_used", []),
                    "pattern_type": wafer.get("defect_summary", {}).get("defect_pattern"),
                    "severity": wafer.get("defect_summary", {}).get("severity"),
                    "yield_percentage": wafer.get("defect_summary", {}).get("yield_percentage")
                },
                "ink_map": {
                    "has_thumbnail": bool(wafer.get("ink_map", {}).get("thumbnail_base64")),
                    "has_full_image": bool(wafer.get("ink_map", {}).get("full_image_url") or
                                          wafer.get("ink_map", {}).get("full_image_base64"))
                }
            }

    except HTTPException:
        total_time = (time.time() - start_time) * 1000
        logger.warning(f"⚠️ GET /wafers/{wafer_id}/visualization - HTTPException after {total_time:.0f}ms")
        raise
    except Exception as e:
        total_time = (time.time() - start_time) * 1000
        logger.error(f"❌ GET /wafers/{wafer_id}/visualization - Error after {total_time:.0f}ms: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/visualization/batch")
async def get_batch_wafer_visualization(
    request: Dict[str, List[str]]  # Expects {"wafer_ids": ["W_001", "W_002", ...]}
):
    """
    Get visualization data for multiple wafers.
    Useful for comparative analysis and batch visualization.

    MongoDB Features: Bulk queries with $in operator
    """
    start_time = time.time()
    wafer_ids = request.get("wafer_ids", [])
    logger.info(f"📥 POST /wafers/visualization/batch - Requesting {len(wafer_ids)} wafers")
    
    try:
        if not wafer_ids:
            logger.warning(f"⚠️ POST /wafers/visualization/batch - No wafer IDs provided")
            raise HTTPException(status_code=400, detail="No wafer IDs provided")

        if len(wafer_ids) > 50:  # Limit batch size
            logger.warning(f"⚠️ POST /wafers/visualization/batch - Too many wafers requested: {len(wafer_ids)}")
            raise HTTPException(status_code=400, detail="Maximum 50 wafers per batch request")

        logger.debug(f"🔍 Opening MongoDB connection for batch query of {len(wafer_ids)} wafers")
        logger.debug(f"   Wafer IDs: {wafer_ids[:5]}{'...' if len(wafer_ids) > 5 else ''}")

        with get_mongodb_connector() as mdb_connector:
            wafer_collection = mdb_connector.get_collection("wafer_defects")

            # Query multiple wafers at once
            query_start = time.time()
            wafers = wafer_collection.find(
                {"wafer_id": {"$in": wafer_ids}},
                {
                    "wafer_id": 1,
                    "die_map": 1,
                    "defects": 1,
                    "defect_summary": 1,
                    "lot_id": 1,
                    "inspection_timestamp": 1,
                    "process_context.equipment_used": 1
                }
            )
            
            # Process results
            process_start = time.time()
            results = []
            found_ids = []

            for wafer in wafers:
                found_ids.append(wafer["wafer_id"])
                results.append({
                    "wafer_id": wafer["wafer_id"],
                    "die_map": wafer.get("die_map", []),
                    "defects": wafer.get("defects", [])[:10],  # Limit defects for batch response
                    "yield_percentage": wafer.get("defect_summary", {}).get("yield_percentage", 0),
                    "pattern": wafer.get("defect_summary", {}).get("defect_pattern", "unknown"),
                    "severity": wafer.get("defect_summary", {}).get("severity", "unknown"),
                    "total_dies": wafer.get("defect_summary", {}).get("total_dies", 625),
                    "failed_dies": wafer.get("defect_summary", {}).get("failed_dies", 0),
                    "lot_id": wafer.get("lot_id"),
                    "timestamp": wafer.get("inspection_timestamp")
                })
            
            query_time = (time.time() - query_start) * 1000
            logger.info(f"   📊 MongoDB batch query completed in {query_time:.0f}ms, found {len(results)}/{len(wafer_ids)} wafers")

            # Check for missing wafers
            missing_ids = list(set(wafer_ids) - set(found_ids))
            if missing_ids:
                logger.warning(f"   ⚠️ Missing wafers: {missing_ids}")

            total_time = (time.time() - start_time) * 1000
            logger.info(f"✅ POST /wafers/visualization/batch completed in {total_time:.0f}ms - {len(results)} wafers returned")

            return {
                "wafers": results,
                "count": len(results),
                "requested": len(wafer_ids),
                "missing_wafers": missing_ids if missing_ids else None
            }

    except HTTPException:
        total_time = (time.time() - start_time) * 1000
        logger.warning(f"⚠️ POST /wafers/visualization/batch - HTTPException after {total_time:.0f}ms")
        raise
    except Exception as e:
        total_time = (time.time() - start_time) * 1000
        logger.error(f"❌ POST /wafers/visualization/batch - Error after {total_time:.0f}ms: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

