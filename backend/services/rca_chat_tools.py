"""
LangChain Tools for Root Cause Analysis Chat Agent

This module provides tools that wrap existing services for the LangGraph agent.
Tools are async to work with MongoDB motor driver.
"""

import os
import base64
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

from langchain_core.tools import tool
from motor.motor_asyncio import AsyncIOMotorClient
import boto3
from botocore.exceptions import ClientError

from services.embedding_service import EmbeddingService

# Environment variables
MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("MDB_DATABASE_NAME", "smf-yield-defect")

# Module-level MongoDB client (singleton pattern)
_mongo_client: Optional[AsyncIOMotorClient] = None

# Configure logging
logger = logging.getLogger(__name__)


def _get_db():
    """Get async MongoDB database instance."""
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = AsyncIOMotorClient(MONGODB_URI)
    return _mongo_client[DATABASE_NAME]


# ===== Helper functions for query_wafer_info tool =====

def _create_text_content(wafer: Dict[str, Any]) -> str:
    """
    Build search text from OBSERVABLE characteristics only.

    IMPORTANT: Do NOT include suspected root causes from description.
    Only use measurable facts: pattern, equipment, yield, severity.
    """
    defect_summary = wafer.get('defect_summary', {})
    process_ctx = wafer.get('process_context', {})

    equipment = 'unknown'
    if process_ctx.get('equipment_used'):
        equipment = process_ctx['equipment_used'][0] if isinstance(process_ctx['equipment_used'], list) else process_ctx['equipment_used']

    text_parts = [
        f"Wafer ID: {wafer.get('wafer_id', 'unknown')}",
        f"Lot ID: {wafer.get('lot_id', 'unknown')}",
        f"Defect pattern: {defect_summary.get('defect_pattern', 'unknown')}",
        f"Severity: {defect_summary.get('severity', 'unknown')}",
        f"Equipment: {equipment}",
        f"Process step: {process_ctx.get('last_process_step', 'unknown')}",
        f"Failed dies: {defect_summary.get('failed_dies', 0)} out of {defect_summary.get('total_dies', 0)}",
        f"Yield: {defect_summary.get('yield_percentage', 0)}%"
    ]

    return " ".join(text_parts)


async def _fetch_wafer_image(wafer: Dict[str, Any]) -> Optional[str]:
    """
    Fetch wafer ink_map image from S3 or use thumbnail fallback.

    Returns base64 encoded image string or None if not available.
    """
    ink_map = wafer.get("ink_map", {})

    # Try S3 full image first (better quality)
    s3_url = ink_map.get("full_image_url")
    if s3_url and s3_url.startswith("s3://"):
        try:
            # Parse S3 URL: s3://bucket/path/to/image.png
            path = s3_url[5:]  # Remove "s3://"
            parts = path.split("/", 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else ""

            # Initialize S3 client
            s3_client = boto3.client('s3')

            # Fetch image
            logger.info(f"Fetching image from S3: {s3_url}")
            response = s3_client.get_object(Bucket=bucket, Key=key)
            image_bytes = response['Body'].read()

            # Convert to base64
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            logger.info(f"Successfully fetched S3 image ({len(image_bytes)} bytes)")

            return image_base64

        except ClientError as e:
            logger.warning(f"Failed to fetch S3 image: {e}")
        except Exception as e:
            logger.error(f"Error fetching S3 image: {e}")

    # Fallback to thumbnail_base64
    thumbnail = ink_map.get("thumbnail_base64")
    if thumbnail:
        logger.info(f"Using thumbnail fallback for {wafer.get('wafer_id')}")
        return thumbnail

    # No image available
    logger.warning(f"No image available for {wafer.get('wafer_id')}")
    return None


async def _search_similar_wafers(
    db,
    query_embedding: List[float],
    limit: int = 3
) -> List[Dict[str, Any]]:
    """
    Perform vector search using pre-computed embedding.

    Searches only OLD wafers (those with embeddings) to find
    historical patterns with known root causes.
    """
    # Build MongoDB Atlas Vector Search pipeline
    # Note: knnBeta should be at top level, not nested in compound
    pipeline = [
        {
            "$search": {
                "index": "wafer_defects_vector_index",
                "knnBeta": {
                    "vector": query_embedding,
                    "path": "embedding",
                    "k": limit * 2  # Get extra candidates for better results
                }
            }
        },
        {
            "$addFields": {
                "score": {"$meta": "searchScore"}
            }
        },
        {
            "$limit": limit
        },
        {
            "$project": {
                "wafer_id": 1,
                "lot_id": 1,
                "description": 1,
                "defect_summary": 1,
                "process_context": 1,
                "ink_map.thumbnail_base64": 1,
                "ink_map.thumbnail_size": 1,
                "score": 1
            }
        }
    ]

    logger.info(f"Searching for {limit} similar historical wafers...")
    cursor = db.wafer_defects.aggregate(pipeline)
    results = await cursor.to_list(length=limit)
    logger.info(f"Found {len(results)} similar wafers")

    return results


@tool
async def query_alerts(
    equipment_id: Optional[str] = None,
    wafer_id: Optional[str] = None,
    hours_back: int = 24
) -> List[Dict[str, Any]]:
    """
    Query open alerts from MongoDB alerts collection.

    Use this tool to find recent open alerts (particle excursions), filter by equipment or wafer.
    Only returns alerts with status='open'.

    Args:
        equipment_id: Filter by specific equipment (e.g., 'CMP_TOOL_01'). Optional.
        wafer_id: Filter by specific wafer (e.g., 'W_001_A'). Optional.
        hours_back: Look back this many hours from now. Default 24 hours.

    Returns:
        List of open alert documents with excursion details and metrics.
    """
    db = _get_db()

    # Build the match filter - ONLY open status alerts
    match_filter = {
        "status": "open",
        "timestamp": {"$gte": datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours_back)}
    }

    if equipment_id:
        match_filter["equipment_id"] = equipment_id

    if wafer_id:
        match_filter["wafer_id"] = wafer_id

    # Aggregation pipeline
    pipeline = [
        {"$match": match_filter},
        {"$sort": {"timestamp": -1}},
        {"$limit": 10},
        {
            "$project": {
                "_id": 0,
                "alert_id": 1,
                "alert_type": 1,
                "severity": 1,
                "status": 1,
                "equipment_id": 1,
                "wafer_id": 1,
                "lot_id": 1,
                "timestamp": 1,
                "title": 1,
                "description": 1,
                "excursion_type": "$source_data.excursion_type",
                "metrics": "$source_data.metrics"
            }
        }
    ]

    try:
        alerts = await db.alerts.aggregate(pipeline).to_list(10)
        return alerts
    except Exception as e:
        return [{"error": f"Failed to query alerts: {str(e)}"}]


@tool
async def query_wafer_info(
    wafer_id: str,
    include_similar_patterns: bool = True,
    similarity_limit: int = 3
) -> Dict[str, Any]:
    """
    Get detailed wafer information and find similar historical defect patterns
    using multimodal similarity search (text + image).

    For NEW wafers (auto-generated from excursions), generates multimodal
    embedding from observable defect characteristics + ink_map visualization,
    then searches against historical wafers whose descriptions contain proven
    root causes.

    Use this tool to get wafer defect details, yield info, and find similar
    historical patterns to understand potential root causes.

    Args:
        wafer_id: Wafer ID (e.g., "W_004_16" for new, "W_CMP_001" for historical)
        include_similar_patterns: Whether to search historical knowledge base (default True)
        similarity_limit: Maximum number of similar labeled examples to return (default 3)

    Returns:
        Dictionary with wafer data, type, alert link, and similar historical patterns
    """
    db = _get_db()

    # Step 1: Fetch wafer
    wafer = await db.wafer_defects.find_one({"wafer_id": wafer_id})
    if not wafer:
        return {"error": f"Wafer {wafer_id} not found in wafer_defects collection"}

    # Step 2: Determine wafer type
    process_context = wafer.get("process_context", {})
    if "excursion_alert_id" in process_context:
        wafer_type = "new"
        alert_id = process_context["excursion_alert_id"]
        logger.info(f"NEW wafer detected: {wafer_id}, linked to alert: {alert_id}")
    else:
        wafer_type = "historical"
        alert_id = None
        logger.info(f"HISTORICAL wafer detected: {wafer_id}")

    # Step 3-7: Multimodal search for NEW wafers
    similar_patterns = None
    search_metadata = {}

    if wafer_type == "new" and include_similar_patterns:
        try:
            # Initialize embedding service
            embedding_service = EmbeddingService()
            await embedding_service.initialize()

            # Build text content from observable facts
            text_content = _create_text_content(wafer)
            logger.info(f"Text content: {text_content[:100]}...")

            # Fetch wafer image
            image_data = await _fetch_wafer_image(wafer)

            # Generate embedding
            if image_data:
                # Multimodal embedding (text + image)
                logger.info(f"Generating multimodal embedding for {wafer_id}...")
                query_embedding = await embedding_service.generate_image_embedding(
                    image_data=image_data,
                    text_context=text_content
                )
                search_metadata["embedding_type"] = "multimodal"
                logger.info(f"Multimodal embedding generated ({len(query_embedding)} dims)")
            else:
                # Fallback to text-only
                logger.warning(f"No image available, using text-only embedding")
                query_embedding = await embedding_service.generate_text_embedding(
                    text_content
                )
                search_metadata["embedding_type"] = "text"

            # Perform vector search
            results = await _search_similar_wafers(db, query_embedding, similarity_limit)

            # Format results
            similar_patterns = []
            for result in results:
                similar_patterns.append({
                    "wafer_id": result.get("wafer_id"),
                    "lot_id": result.get("lot_id"),
                    "description": result.get("description"),  # Contains root cause!
                    "defect_summary": result.get("defect_summary", {}),
                    "process_context": {
                        "equipment_used": result.get("process_context", {}).get("equipment_used", []),
                        "last_process_step": result.get("process_context", {}).get("last_process_step"),
                        "slurry_batch": result.get("process_context", {}).get("slurry_batch"),
                        "recipe_id": result.get("process_context", {}).get("recipe_id")
                    },
                    "ink_map": result.get("ink_map", {}),  # Include ink_map for visualization
                    "similarity_score": round(result.get("score", 0), 4)
                })

            search_metadata["similarity_metric"] = "cosine"
            search_metadata["model"] = "voyage-multimodal-3"
            search_metadata["num_results"] = len(similar_patterns)

        except Exception as e:
            logger.error(f"Error during similarity search: {e}", exc_info=True)
            search_metadata["error"] = str(e)

    # Step 8: Return response
    return {
        "wafer": {
            "wafer_id": wafer.get("wafer_id"),
            "lot_id": wafer.get("lot_id"),
            "inspection_timestamp": wafer.get("inspection_timestamp"),
            "defect_summary": wafer.get("defect_summary", {}),
            "description": wafer.get("description"),
            "process_context": wafer.get("process_context", {}),
            "defects": wafer.get("defects", [])[:10],  # Limit defects array
            "ink_map": wafer.get("ink_map", {})  # Include ink_map with thumbnail_base64
        },
        "wafer_type": wafer_type,
        "linked_alert_id": alert_id,
        "similar_historical_patterns": similar_patterns,
        "search_metadata": search_metadata if wafer_type == "new" else None
    }


# ===== Helper functions for query_time_series_data tool =====

def _parse_timestamp(ts_str: str) -> datetime:
    """
    Parse ISO 8601 timestamp string to datetime object.

    Handles formats:
    - "2025-08-11T21:05:12.031Z"
    - "2025-08-11T21:05:12.031026+00:00"

    Args:
        ts_str: ISO 8601 timestamp string

    Returns:
        datetime object

    Raises:
        ValueError: If timestamp format is invalid
    """
    try:
        # Replace 'Z' with '+00:00' for ISO format parsing
        if ts_str.endswith('Z'):
            ts_str = ts_str[:-1] + '+00:00'
        return datetime.fromisoformat(ts_str)
    except Exception as e:
        logger.error(f"Failed to parse timestamp {ts_str}: {e}")
        raise ValueError(f"Invalid timestamp format: {ts_str}")


async def _query_sensor_stats_for_period(
    db,
    equipment_id: str,
    start_time: datetime,
    end_time: datetime,
    metrics: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Query sensor data for a time period and return statistics using MongoDB aggregation.

    This is TOKEN-EFFICIENT: Instead of returning raw time series data,
    we compute statistics (min, max, avg, stddev) on the MongoDB server.

    Args:
        db: MongoDB database instance
        equipment_id: Equipment ID to query (e.g., "CMP_TOOL_01")
        start_time: Period start time (datetime object)
        end_time: Period end time (datetime object)
        metrics: List of metrics to analyze (e.g., ["temperature", "particle_count"])
                 If None, analyzes all available metrics.

    Returns:
        Dictionary with:
        - data_points: Number of sensor readings in period
        - statistics: {metric_name: {min, max, avg, stddev}}
    """
    # Default metrics if not specified
    if metrics is None:
        metrics = ["particle_count", "temperature", "rf_power", "chamber_pressure", "flow_rate"]

    # Build aggregation pipeline
    # Stage 1: Match equipment and time range
    match_stage = {
        "$match": {
            "equipment_id": equipment_id,
            "timestamp": {
                "$gte": start_time,
                "$lte": end_time
            }
        }
    }

    # Stage 2: Group and compute statistics
    group_stage = {
        "$group": {
            "_id": None,
            "data_points": {"$sum": 1}
        }
    }

    # Add statistics for each metric
    for metric in metrics:
        metric_path = f"metrics.{metric}"
        group_stage["$group"][f"{metric}_min"] = {"$min": f"${metric_path}"}
        group_stage["$group"][f"{metric}_max"] = {"$max": f"${metric_path}"}
        group_stage["$group"][f"{metric}_avg"] = {"$avg": f"${metric_path}"}
        group_stage["$group"][f"{metric}_stddev"] = {"$stdDevPop": f"${metric_path}"}

    # Execute aggregation
    pipeline = [match_stage, group_stage]
    cursor = db.process_sensor_ts.aggregate(pipeline)
    results = await cursor.to_list(length=1)

    if not results:
        # No data found
        return {
            "data_points": 0,
            "statistics": {}
        }

    result = results[0]
    data_points = result.get("data_points", 0)

    # Format statistics by metric
    statistics = {}
    for metric in metrics:
        statistics[metric] = {
            "min": result.get(f"{metric}_min"),
            "max": result.get(f"{metric}_max"),
            "avg": result.get(f"{metric}_avg"),
            "stddev": result.get(f"{metric}_stddev")
        }

    return {
        "data_points": data_points,
        "statistics": statistics
    }


@tool
async def query_time_series_data(
    equipment_id: str,
    center_timestamp: Optional[str] = None,
    window_minutes: int = 10,
    hours_back: int = 1,
    metrics: Optional[List[str]] = None,
    include_baseline_comparison: bool = True
) -> Dict[str, Any]:
    """
    Query time-series sensor data and provide statistical analysis for LLM reasoning.

    This tool is designed as a PURE DATA PROVIDER - it returns statistical data only
    and does NOT perform correlation analysis. The LLM performs all root cause reasoning
    based on the statistical data provided.

    This tool is designed for the demo architecture where temperature/RF anomalies
    and particle excursions happen SIMULTANEOUSLY in sensor readings. It compares
    the excursion period against a baseline period for LLM root cause analysis.

    Use this tool to:
    - Analyze sensor behavior around a specific alert timestamp
    - Compare excursion metrics vs normal baseline operation
    - Provide statistical data for LLM correlation analysis and reasoning
    - Get statistical summaries (NOT raw time-series arrays for token efficiency)

    Two query modes:
    1. CENTERED (when center_timestamp provided): Analyze ±window_minutes around alert
    2. RECENT (when center_timestamp is None): Analyze last N hours

    Args:
        equipment_id: Equipment ID (e.g., "CMP_TOOL_01", "LITHO_01")
        center_timestamp: ISO 8601 timestamp of alert (e.g., "2025-08-11T21:15:00Z")
                         If provided, queries ±window_minutes around this time.
                         If None, queries last N hours.
        window_minutes: Minutes before/after center_timestamp (default 10)
                       Only used in CENTERED mode.
        hours_back: Hours to look back from now (default 1)
                   Only used in RECENT mode (when center_timestamp is None).
        metrics: List of metrics to analyze (e.g., ["temperature", "particle_count"])
                If None, analyzes all: particle_count, temperature, rf_power,
                chamber_pressure, flow_rate
        include_baseline_comparison: Whether to compare against baseline period (default True)
                                     Only applies in CENTERED mode.

    Returns:
        Dictionary with:
        - query_mode: "centered" or "recent"
        - equipment_id: Equipment ID
        - excursion_period: {start, end, duration_minutes, data_points, statistics}
        - baseline_period: {start, end, duration_minutes, data_points, statistics}
                          (Only if CENTERED mode and include_baseline_comparison=True)
        - metadata: Query metadata (timestamps, metrics analyzed)

        Note: LLM analyzes the statistics to determine correlations and root causes.
    """
    db = _get_db()

    # Step 1: Determine query mode and time windows
    if center_timestamp:
        # CENTERED mode: ±window_minutes around alert
        query_mode = "centered"
        center_dt = _parse_timestamp(center_timestamp)

        # Excursion window: [center - window, center + window]
        excursion_start = center_dt - timedelta(minutes=window_minutes)
        excursion_end = center_dt + timedelta(minutes=window_minutes)

        # Baseline window: 30 minutes BEFORE excursion (no overlap)
        baseline_end = excursion_start
        baseline_start = baseline_end - timedelta(minutes=30)

        logger.info(f"CENTERED query for {equipment_id} around {center_timestamp}")
        logger.info(f"  Excursion: {excursion_start} to {excursion_end}")
        logger.info(f"  Baseline: {baseline_start} to {baseline_end}")
    else:
        # RECENT mode: Last N hours
        query_mode = "recent"
        excursion_end = datetime.now(timezone.utc).replace(tzinfo=None)
        excursion_start = excursion_end - timedelta(hours=hours_back)

        baseline_start = None
        baseline_end = None

        logger.info(f"RECENT query for {equipment_id} (last {hours_back} hours)")
        logger.info(f"  Period: {excursion_start} to {excursion_end}")

    # Step 2: Query excursion period statistics
    try:
        excursion_stats = await _query_sensor_stats_for_period(
            db=db,
            equipment_id=equipment_id,
            start_time=excursion_start,
            end_time=excursion_end,
            metrics=metrics
        )
    except Exception as e:
        logger.error(f"Failed to query excursion period: {e}", exc_info=True)
        return {"error": f"Failed to query sensor data: {str(e)}"}

    # Step 3: Build base response
    response = {
        "query_mode": query_mode,
        "equipment_id": equipment_id,
        "excursion_period": {
            "start": excursion_start.isoformat(),
            "end": excursion_end.isoformat(),
            "duration_minutes": (excursion_end - excursion_start).total_seconds() / 60,
            "data_points": excursion_stats["data_points"],
            "statistics": excursion_stats["statistics"]
        },
        "metadata": {
            "center_timestamp": center_timestamp,
            "window_minutes": window_minutes if query_mode == "centered" else None,
            "hours_back": hours_back if query_mode == "recent" else None,
            "metrics_analyzed": metrics or ["particle_count", "temperature", "rf_power", "chamber_pressure", "flow_rate"]
        }
    }

    # Step 4: Query baseline and detect correlations (CENTERED mode only)
    if query_mode == "centered" and include_baseline_comparison:
        try:
            baseline_stats = await _query_sensor_stats_for_period(
                db=db,
                equipment_id=equipment_id,
                start_time=baseline_start,
                end_time=baseline_end,
                metrics=metrics
            )

            response["baseline_period"] = {
                "start": baseline_start.isoformat(),
                "end": baseline_end.isoformat(),
                "duration_minutes": 30,
                "data_points": baseline_stats["data_points"],
                "statistics": baseline_stats["statistics"]
            }

        except Exception as e:
            logger.error(f"Failed to query baseline: {e}", exc_info=True)
            response["baseline_error"] = str(e)

    return response


# Tool registry for LangGraph
TOOLS = [query_alerts, query_wafer_info, query_time_series_data]


# Independent test suite
if __name__ == "__main__":
    import asyncio

    async def test_query_alerts():
        """Test the query_alerts tool independently."""
        print("=== Testing query_alerts tool ===\n")

        # Test 1: Query all recent open alerts (last 24 hours)
        print("Test 1: Query all recent open alerts (last 24 hours)")
        result = await query_alerts.ainvoke({})
        print(f"Found {len(result)} open alerts")
        if result and not result[0].get("error"):
            print(f"Sample alert: {result[0]}")
            if "excursion_type" in result[0]:
                print(f"  Excursion type: {result[0]['excursion_type']}")
            if "metrics" in result[0]:
                print(f"  Metrics: {result[0]['metrics']}")
        print()

        # Test 2: Query alerts for specific equipment
        print("Test 2: Query open alerts for CMP_TOOL_01")
        result = await query_alerts.ainvoke({"equipment_id": "CMP_TOOL_01"})
        print(f"Found {len(result)} open alerts for CMP_TOOL_01")
        print()

        # Test 3: Query alerts for specific wafer
        print("Test 3: Query open alerts for wafer W_001_A")
        result = await query_alerts.ainvoke({"wafer_id": "W_001_A"})
        print(f"Found {len(result)} open alerts for W_001_A")
        print()

        # Test 4: Query last 48 hours
        print("Test 4: Query open alerts from last 48 hours")
        result = await query_alerts.ainvoke({"hours_back": 48})
        print(f"Found {len(result)} open alerts in last 48 hours")
        print()

        print("=== All tests completed ===")

        # Clean up
        global _mongo_client
        if _mongo_client:
            _mongo_client.close()

    # Run tests
    asyncio.run(test_query_alerts())
