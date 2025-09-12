from db.mdb import MongoDBConnector

import logging
from datetime import datetime, timedelta, timezone

import json
from bson import ObjectId
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Request, Query, WebSocket, WebSocketDisconnect, BackgroundTasks, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from config.config_loader import ConfigLoader
from utils import convert_objectids, format_document

from db.mdb import MongoDBConnector

from agent_workflow_graph import create_workflow_graph
from agent_state import AgentState
from agent_checkpointer import AgentCheckpointer

# Import Phase 2 services
from services.excursion_detector import ExcursionDetector
from services.correlation_engine import CorrelationEngine
from services.rca_generator import RCAGenerator
from services.alert_manager import AlertManager, AlertSeverity, AlertStatus, AlertType

import os
from dotenv import load_dotenv
import asyncio

load_dotenv()

# Load configuration
config = ConfigLoader()
# Get configuration values
# MongoDB URI
MDB_URI = os.getenv("MONGODB_URI")
# Database
MDB_DATABASE_NAME = config.get("MDB_DATABASE_NAME")
# Collections
MDB_HISTORICAL_RECOMMENDATIONS_COLLECTION = config.get("MDB_HISTORICAL_RECOMMENDATIONS_COLLECTION")
MDB_AGENT_SESSIONS_COLLECTION = config.get("MDB_AGENT_SESSIONS_COLLECTION")
MDB_EMBEDDINGS_COLLECTION = config.get("MDB_EMBEDDINGS_COLLECTION")
MDB_EMBEDDINGS_COLLECTION_VS_FIELD = config.get("MDB_EMBEDDINGS_COLLECTION_VS_FIELD")
MDB_TIMESERIES_COLLECTION = config.get("MDB_TIMESERIES_COLLECTION")
MDB_LOGS_COLLECTION = config.get("MDB_LOGS_COLLECTION")
MDB_AGENT_PROFILES_COLLECTION = config.get("MDB_AGENT_PROFILES_COLLECTION")
AGENT_PROFILE_CHOSEN_ID = config.get("AGENT_PROFILE_CHOSEN_ID")
# Checkpointer
MDB_CHECKPOINTER_COLLECTION = config.get("MDB_CHECKPOINTER_COLLECTION")
MDB_CHECKPOINTER_WRITES = MDB_CHECKPOINTER_COLLECTION + "_writes"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter()

# Initialize Phase 2 services
excursion_detector = None
correlation_engine = None
rca_generator = None
alert_manager = None
monitoring_active = False
monitoring_task = None

# WebSocket connections for real-time updates
active_connections: List[WebSocket] = []

@app.get("/")
async def read_root(request: Request):
    return {"message": "Server is running"}


@app.get("/run-agent")
async def run_agent(query_reported: str = Query("Default query reported by the user", description="Query reported text")):
    """Run the agent with the given query.

    Args:
        query_reported (str, optional): _description_. Defaults to Query("Default query reported by the user", description="Query reported text").

    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_
    """
    initial_state: AgentState = {
        "query_reported": query_reported,
        "chain_of_thought": "",
        "timeseries_data": [],
        "embedding_vector": [],
        "historical_recommendations_list": [],
        "recommendation_text": "",
        "next_step": "reasoning_node",
        "updates": [],
        "thread_id": ""
    }
    thread_id = f"thread_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    initial_state["thread_id"] = thread_id
    config = {"configurable": {"thread_id": thread_id}}
    try:
        logger.info(f"Running agent for thread ID: {thread_id}")
        mongodb_saver = AgentCheckpointer(database_name=MDB_DATABASE_NAME, collection_name=MDB_CHECKPOINTER_COLLECTION).create_mongodb_saver()
        if mongodb_saver:
            with mongodb_saver as checkpointer:
                workflow = create_workflow_graph(checkpointer=checkpointer)
                final_state = workflow.invoke(initial_state, config=config)
                final_state = convert_objectids(final_state)
        else:
            workflow = create_workflow_graph()
            final_state = workflow.invoke(initial_state, config=config)
            final_state = convert_objectids(final_state)
        final_state["thread_id"] = thread_id
        
        try:
            with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector: 
                session_metadata = {
                    "thread_id": thread_id,
                    "query_reported": query_reported,
                    "created_at": datetime.now(timezone.utc),
                    "status": "completed",
                    "recommendation": final_state["recommendation_text"]
                }
                session_metadata = convert_objectids(session_metadata)
                mdb_connector.insert_one(collection_name=MDB_AGENT_SESSIONS_COLLECTION, document=session_metadata)
                return final_state
        except Exception as e:
            logger.info(f"[MongoDB] Error storing session metadata: {e}")
            return final_state
    except Exception as e:
        logger.info(f"[Error] An error occurred during execution: {e}")
        logger.info(f"You can resume this session later using thread ID: {thread_id}")
        try:
            with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector: 
                session_metadata = {
                    "thread_id": thread_id,
                    "query_reported": query_reported,
                    "created_at": datetime.now(timezone.utc),
                    "status": "error",
                    "error_message": str(e)
                }
                session_metadata = convert_objectids(session_metadata)
                mdb_connector.insert_one(collection_name=MDB_AGENT_SESSIONS_COLLECTION, document=session_metadata)
                logger.info("[MongoDB] Error state recorded in session metadata")
        except Exception as db_error:
                logger.info(f"[MongoDB] Error storing session error state: {db_error}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/resume-agent")
async def resume_agent(thread_id: str = Query(..., description="Thread ID to resume session")):
    """Resume the agent with the given thread ID. 
    
    Args:
        thread_id (str, optional): Thread ID to resume session. Defaults to Query(..., description="Thread ID to resume session").

    Raises:
        HTTPException: _description_
    
    Returns:
        session: The session to resume.
    """
    try:
        with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector: 
            mdb_sessions_collection = mdb_connector.get_collection(MDB_AGENT_SESSIONS_COLLECTION)
            logger.info(f"Resuming agent for thread ID: {thread_id}")
            session = mdb_sessions_collection.find_one({"thread_id": thread_id})
        if session:
            session = convert_objectids(session)
            return session
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.get("/get-sessions")
async def get_sessions():
    """Get the last 10 sessions. 
    
    Returns:
        sessions: The last 10 sessions.

    Raises:
        HTTPException
    """
    try:
        with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector:
            mdb_sessions_collection = mdb_connector.get_collection(MDB_AGENT_SESSIONS_COLLECTION)
            sessions = list(mdb_sessions_collection.find().sort("created_at", -1).limit(10))
        sessions = convert_objectids(sessions)
        return sessions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.get("/get-run-documents")
async def get_run_documents(thread_id: str = Query(..., description="Thread ID of the agent run")):
    """Get all documents for a given run. 
    
    Args:
        thread_id (str, optional): Thread ID of the agent run. Defaults to Query(..., description="Thread ID of the agent run").

    Returns:
        docs: The documents for the given run.
    """
    try:
        docs = {}

        # For collections where thread_id is stored with extra characters, use regex to find the right data
        query = {"thread_id": {"$regex": f"^{thread_id}"}}

        # Retrieve documents
        logger.info(f"Retrieving documents for thread ID: {thread_id}")
        with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector:
            mdb_historical_recommendations_collection = mdb_connector.get_collection(MDB_HISTORICAL_RECOMMENDATIONS_COLLECTION)
            mdb_agent_sessions_collection = mdb_connector.get_collection(MDB_AGENT_SESSIONS_COLLECTION)
            mdb_timeseries_collection = mdb_connector.get_collection(MDB_TIMESERIES_COLLECTION)
            mdb_logs_collection = mdb_connector.get_collection(MDB_LOGS_COLLECTION)
            mdb_agent_profiles_collection = mdb_connector.get_collection(MDB_AGENT_PROFILES_COLLECTION)
            mdb_embeddings_collection = mdb_connector.get_collection(MDB_EMBEDDINGS_COLLECTION)
            mdb_checkpoint_collection = mdb_connector.get_collection(MDB_CHECKPOINTER_COLLECTION)
        
            # Retrieve agent_sessions document
            session = mdb_agent_sessions_collection.find_one(query)

            # Retrieve historical_recommendations for the run
            historical = mdb_historical_recommendations_collection.find_one(query)

            # Retrieve 3 timeseries data points
            timeseries = list(mdb_timeseries_collection.find().limit(3))

            # Retrieve logs for the run
            log = mdb_logs_collection.find_one(query)

            # Retrieve the agent profile
            chosen_agent_id = AGENT_PROFILE_CHOSEN_ID or "DEFAULT"
            profile = mdb_agent_profiles_collection.find_one({"agent_id": chosen_agent_id})

            # Retrieve 3 queries from the embeddings collection
            queries = list(mdb_embeddings_collection.find().limit(3))

            # Retrieve the last checkpoint
            last_checkpoint = mdb_checkpoint_collection.find_one(query)
        
        logger.info(f"Formatting documents for thread ID: {thread_id}")
        # Format the documents
        docs["agent_sessions"] = format_document(session) if session else {}
        docs["historical_recommendations"] = format_document(historical) if historical else {}
        docs["agent_profile"] = format_document(profile) if profile else {}
        docs[MDB_TIMESERIES_COLLECTION] = [format_document(record) for record in timeseries] if timeseries else {}
        docs["queries"] = [format_document(record) for record in queries] if queries else {}
        docs["logs"] = format_document(log) if log else {}
        docs["last_checkpoint"] = format_document(last_checkpoint) if last_checkpoint else {}
        logger.info(f"Documents formatted for thread ID: {thread_id}")

        return docs
    except Exception as e:
        logger.error(f"Error while retrieving documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================== Phase 2: Real-time Monitoring Endpoints ======================

@app.post("/monitoring/start")
async def start_monitoring(background_tasks: BackgroundTasks):
    """
    Start real-time monitoring services
    """
    global excursion_detector, correlation_engine, rca_generator, alert_manager, monitoring_active, monitoring_task
    
    try:
        if monitoring_active:
            return {"status": "already_running", "message": "Monitoring is already active"}
        
        # Initialize services
        excursion_detector = ExcursionDetector(
            mongodb_uri=MDB_URI,
            database=MDB_DATABASE_NAME
        )
        
        correlation_engine = CorrelationEngine(
            mongodb_uri=MDB_URI,
            database=MDB_DATABASE_NAME
        )
        
        rca_generator = RCAGenerator(
            mongodb_uri=MDB_URI,
            database=MDB_DATABASE_NAME
        )
        
        alert_manager = AlertManager(
            mongodb_uri=MDB_URI,
            database_name=MDB_DATABASE_NAME
        )
        
        # Initialize alert manager (async setup)
        await alert_manager.initialize()
        
        # Start monitoring in background
        monitoring_active = True
        background_tasks.add_task(run_monitoring_loop)
        
        logger.info("Phase 2 monitoring services started")
        return {
            "status": "started",
            "message": "Real-time monitoring services initialized",
            "services": {
                "excursion_detector": "active",
                "correlation_engine": "active",
                "rca_generator": "active",
                "alert_manager": "active"
            }
        }
        
    except Exception as e:
        logger.error(f"Error starting monitoring services: {e}")
        monitoring_active = False
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/monitoring/stop")
async def stop_monitoring():
    """
    Stop real-time monitoring services
    """
    global monitoring_active, excursion_detector, correlation_engine, rca_generator, alert_manager
    
    try:
        if not monitoring_active:
            return {"status": "not_running", "message": "Monitoring is not active"}
        
        monitoring_active = False
        
        # Cleanup services
        if excursion_detector:
            excursion_detector.cleanup()
        if correlation_engine:
            correlation_engine.cleanup()
        if rca_generator:
            rca_generator.cleanup()
        if alert_manager:
            alert_manager.cleanup()
        
        logger.info("Phase 2 monitoring services stopped")
        return {
            "status": "stopped",
            "message": "Real-time monitoring services stopped"
        }
        
    except Exception as e:
        logger.error(f"Error stopping monitoring services: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/monitoring/status")
async def get_monitoring_status():
    """
    Get current monitoring status
    """
    return {
        "monitoring_active": monitoring_active,
        "services": {
            "excursion_detector": "active" if excursion_detector else "inactive",
            "correlation_engine": "active" if correlation_engine else "inactive",
            "rca_generator": "active" if rca_generator else "inactive",
            "alert_manager": "active" if alert_manager else "inactive"
        }
    }


@app.get("/alerts")
async def get_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity: critical, high, medium, low"),
    alert_type: Optional[str] = Query(None, description="Filter by alert type"),
    equipment_id: Optional[str] = Query(None, description="Filter by equipment ID"),
    limit: int = Query(100, description="Maximum number of alerts to return")
):
    """
    Get active alerts with optional filtering
    """
    try:
        if not alert_manager:
            raise HTTPException(status_code=503, detail="Alert manager not initialized. Start monitoring first.")
        
        # Convert string parameters to enums if provided
        severity_enum = AlertSeverity(severity) if severity else None
        alert_type_enum = AlertType(alert_type) if alert_type else None
        
        alerts = await alert_manager.get_active_alerts(
            severity=severity_enum,
            alert_type=alert_type_enum,
            equipment_id=equipment_id,
            limit=limit
        )
        
        # Convert ObjectIds for JSON serialization
        alerts = convert_objectids(alerts)
        
        return {
            "count": len(alerts),
            "alerts": alerts
        }
        
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=f"Invalid parameter value: {ve}")
    except Exception as e:
        logger.error(f"Error retrieving alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/alerts/{alert_id}")
async def get_alert_details(alert_id: str):
    """
    Get detailed information about a specific alert
    """
    try:
        if not alert_manager:
            raise HTTPException(status_code=503, detail="Alert manager not initialized. Start monitoring first.")
        
        alert = await alert_manager.get_alert_by_id(alert_id)
        
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        # Get alert history
        history = await alert_manager.get_alert_history(alert_id)
        
        # Convert ObjectIds
        alert = convert_objectids(alert)
        history = convert_objectids(history)
        
        return {
            "alert": alert,
            "history": history
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/alerts/{alert_id}/correlation")
async def get_alert_correlation(alert_id: str):
    """
    Get correlation analysis for a specific alert
    """
    try:
        if not alert_manager or not correlation_engine:
            raise HTTPException(status_code=503, detail="Services not initialized. Start monitoring first.")
        
        alert = await alert_manager.get_alert_by_id(alert_id)
        
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        # Perform correlation analysis if not already done
        if not alert.get("correlation_data"):
            source_data = alert.get("source_data", {})
            
            # Run correlation analysis (simplified for now as analyze_alert is async)
            # In production, this would be run asynchronously
            correlations = {
                "temporal_correlation": {
                    "wafer_defects_found": 2,
                    "yield_impact": 0.92
                },
                "batch_correlation": {
                    "batch_id": "BATCH-001",
                    "is_problematic": False
                },
                "spatial_correlation": {
                    "pattern_detected": "clustered",
                    "confidence": 0.85
                },
                "alert_analyzed": True,
                "analysis_timestamp": datetime.now().isoformat()
            }
            
            # Update alert with correlation data
            await alert_manager.add_correlation_data(alert_id, correlations)
            
            # Generate RCA recommendations
            rca_recommendations = rca_generator.generate_rca_hints(
                alert_id=alert_id,
                correlation_results=correlations,
                alert_data=source_data
            )
            
            await alert_manager.add_rca_recommendations(alert_id, rca_recommendations)
            
            # Retrieve updated alert
            alert = await alert_manager.get_alert_by_id(alert_id)
        
        # Convert ObjectIds
        alert = convert_objectids(alert)
        
        return {
            "alert_id": alert_id,
            "correlation_data": alert.get("correlation_data", {}),
            "rca_recommendations": alert.get("rca_recommendations", [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing correlation for alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    acknowledged_by: str = Query(..., description="User acknowledging the alert"),
    notes: Optional[str] = Query(None, description="Acknowledgment notes")
):
    """
    Acknowledge an alert
    """
    try:
        if not alert_manager:
            raise HTTPException(status_code=503, detail="Alert manager not initialized. Start monitoring first.")
        
        success = await alert_manager.acknowledge_alert(alert_id, acknowledged_by, notes)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to acknowledge alert. It may already be acknowledged.")
        
        return {
            "status": "success",
            "message": f"Alert {alert_id} acknowledged by {acknowledged_by}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error acknowledging alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    resolved_by: str = Query(..., description="User resolving the alert"),
    resolution_notes: str = Query(..., description="Resolution notes")
):
    """
    Resolve an alert
    """
    try:
        if not alert_manager:
            raise HTTPException(status_code=503, detail="Alert manager not initialized. Start monitoring first.")
        
        success = await alert_manager.update_alert_status(
            alert_id=alert_id,
            status=AlertStatus.RESOLVED,
            updated_by=resolved_by,
            notes=resolution_notes
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to resolve alert")
        
        return {
            "status": "success",
            "message": f"Alert {alert_id} resolved by {resolved_by}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/alerts/statistics/summary")
async def get_alert_statistics(
    time_window_hours: int = Query(24, description="Time window in hours for statistics")
):
    """
    Get alert statistics for dashboard
    """
    try:
        if not alert_manager:
            raise HTTPException(status_code=503, detail="Alert manager not initialized. Start monitoring first.")
        
        stats = await alert_manager.get_alert_statistics(time_window_hours)
        
        return stats
        
    except Exception as e:
        logger.error(f"Error retrieving alert statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================== Real-time Monitoring Dashboard APIs ======================

@app.get("/sensors/realtime")
async def get_realtime_sensors(
    equipment_id: Optional[str] = Query(None, description="Filter by equipment ID"),
    metric: Optional[str] = Query(None, description="Specific metric to retrieve"),
    limit: int = Query(50, description="Number of records to return")
):
    """
    Get real-time sensor data for monitoring dashboard
    """
    try:
        with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector:
            sensor_collection = mdb_connector.get_collection(MDB_TIMESERIES_COLLECTION)
            
            # Build query
            query = {}
            if equipment_id:
                query["equipment_id"] = equipment_id
            
            # Get latest sensor readings
            pipeline = [
                {"$match": query},
                {"$sort": {"timestamp": -1}},
                {"$limit": limit}
            ]
            
            if equipment_id:
                # Get single equipment data
                sensors = list(sensor_collection.aggregate(pipeline))
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
                sensors = list(sensor_collection.aggregate(pipeline))
            
            # Convert ObjectIds
            sensors = convert_objectids(sensors)
            
            return {
                "count": len(sensors),
                "data": sensors
            }
            
    except Exception as e:
        logger.error(f"Error fetching realtime sensors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sensors/stream/{equipment_id}")
async def get_sensor_stream(
    equipment_id: str,
    window_minutes: int = Query(60, description="Time window in minutes"),
    interval: int = Query(1, description="Data point interval in minutes")
):
    """
    Get sensor data stream for specific equipment
    """
    try:
        with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector:
            sensor_collection = mdb_connector.get_collection(MDB_TIMESERIES_COLLECTION)
            
            # Calculate time window
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=window_minutes)
            
            # Aggregate data with time buckets
            pipeline = [
                {"$match": {
                    "equipment_id": equipment_id,
                    "timestamp": {"$gte": start_time, "$lte": end_time}
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
            
            data_points = list(sensor_collection.aggregate(pipeline))
            
            # Format response
            formatted_data = []
            for point in data_points:
                formatted_data.append({
                    "timestamp": point["_id"],
                    "metrics": point["metrics"],
                    "sample_count": point["count"]
                })
            
            return {
                "equipment_id": equipment_id,
                "window_minutes": window_minutes,
                "interval_minutes": interval,
                "data_points": formatted_data,
                "count": len(formatted_data)
            }
            
    except Exception as e:
        logger.error(f"Error fetching sensor stream for {equipment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/wafers/latest")
async def get_latest_wafers(
    limit: int = Query(10, description="Number of wafers to return"),
    pattern: Optional[str] = Query(None, description="Filter by defect pattern"),
    min_yield: Optional[float] = Query(None, description="Minimum yield percentage")
):
    """
    Get latest wafer inspection results
    """
    try:
        with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector:
            wafer_collection = mdb_connector.get_collection("wafer_defects")
            
            # Build query
            query = {}
            if pattern:
                query["defect_summary.defect_pattern"] = pattern
            if min_yield:
                query["defect_summary.yield_percentage"] = {"$gte": min_yield}
            
            # Get latest wafers
            wafers = list(wafer_collection.find(query).sort("inspection_timestamp", -1).limit(limit))
            
            # Remove large image data for API response
            for wafer in wafers:
                if "ink_map" in wafer and "thumbnail_base64" in wafer["ink_map"]:
                    # Keep only first 100 chars of thumbnail for preview
                    wafer["ink_map"]["has_thumbnail"] = True
                    wafer["ink_map"]["thumbnail_preview"] = wafer["ink_map"]["thumbnail_base64"][:100] + "..."
                    del wafer["ink_map"]["thumbnail_base64"]
            
            wafers = convert_objectids(wafers)
            
            return {
                "count": len(wafers),
                "wafers": wafers
            }
            
    except Exception as e:
        logger.error(f"Error fetching latest wafers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/wafers/batches")
async def get_wafer_batches(
    limit: int = Query(5, description="Number of batches to return"),
    include_stats: bool = Query(True, description="Include batch statistics")
):
    """
    Get wafer batch history with statistics
    """
    try:
        with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector:
            wafer_collection = mdb_connector.get_collection("wafer_defects")
            
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
            
            batches = list(wafer_collection.aggregate(pipeline))
            
            # Format response
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
            
            return {
                "count": len(formatted_batches),
                "batches": formatted_batches
            }
            
    except Exception as e:
        logger.error(f"Error fetching wafer batches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/equipment/status")
async def get_equipment_status():
    """
    Get equipment fleet status matrix
    """
    try:
        with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector:
            sensor_collection = mdb_connector.get_collection(MDB_TIMESERIES_COLLECTION)
            
            # Get latest status for each equipment
            pipeline = [
                {"$sort": {"timestamp": -1}},
                {"$group": {
                    "_id": "$equipment_id",
                    "latest_reading": {"$first": "$$ROOT"},
                    "avg_metrics": {"$avg": "$metrics"}
                }},
                {"$project": {
                    "equipment_id": "$_id",
                    "process_step": "$latest_reading.process_step",
                    "last_update": "$latest_reading.timestamp",
                    "current_metrics": "$latest_reading.metrics",
                    "status": {
                        "$cond": {
                            "if": {"$gt": ["$latest_reading.metrics.particle_count", 1000]},
                            "then": "critical",
                            "else": {
                                "$cond": {
                                    "if": {"$gt": ["$latest_reading.metrics.particle_count", 800]},
                                    "then": "warning",
                                    "else": "good"
                                }
                            }
                        }
                    }
                }}
            ]
            
            equipment_list = list(sensor_collection.aggregate(pipeline))
            
            # Group by process type
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
            
            return {
                "matrix": equipment_matrix,
                "total_equipment": len(equipment_list),
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error fetching equipment status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/equipment/{equipment_id}/metrics")
async def get_equipment_metrics(
    equipment_id: str,
    hours: int = Query(24, description="Time window in hours")
):
    """
    Get detailed metrics for specific equipment
    """
    try:
        with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector:
            sensor_collection = mdb_connector.get_collection(MDB_TIMESERIES_COLLECTION)
            
            # Calculate time window
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            
            # Get metrics statistics
            pipeline = [
                {"$match": {
                    "equipment_id": equipment_id,
                    "timestamp": {"$gte": start_time, "$lte": end_time}
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
            
            stats = list(sensor_collection.aggregate(pipeline))
            
            if not stats:
                return {
                    "equipment_id": equipment_id,
                    "message": "No data available for specified time window"
                }
            
            metrics = stats[0]
            del metrics["_id"]
            
            # Calculate utilization (simplified)
            utilization = min(100, (metrics["total_readings"] / (hours * 60)) * 100)
            
            return {
                "equipment_id": equipment_id,
                "time_window_hours": hours,
                "metrics": metrics,
                "utilization_percentage": round(utilization, 2),
                "health_score": 100 - (metrics.get("excursions", 0) * 10)  # Simple health score
            }
            
    except Exception as e:
        logger.error(f"Error fetching equipment metrics for {equipment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """
    WebSocket endpoint for real-time alert updates
    """
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        while True:
            # Keep connection alive and wait for messages
            data = await websocket.receive_text()
            
            # Echo back for now (could implement filtering based on client preferences)
            await websocket.send_text(f"Monitoring active: {monitoring_active}")
            
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)


@app.websocket("/ws/sensors")
async def websocket_sensors(websocket: WebSocket):
    """
    WebSocket endpoint for real-time sensor data streaming
    """
    await websocket.accept()
    
    try:
        # Send initial data
        with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector:
            sensor_collection = mdb_connector.get_collection(MDB_TIMESERIES_COLLECTION)
            
            while True:
                # Get latest sensor data
                pipeline = [
                    {"$sort": {"timestamp": -1}},
                    {"$group": {
                        "_id": "$equipment_id",
                        "latest": {"$first": "$$ROOT"}
                    }},
                    {"$replaceRoot": {"newRoot": "$latest"}},
                    {"$limit": 10}
                ]
                
                sensors = list(sensor_collection.aggregate(pipeline))
                sensors = convert_objectids(sensors)
                
                # Send to client
                await websocket.send_json({
                    "type": "sensor_update",
                    "timestamp": datetime.now().isoformat(),
                    "data": sensors
                })
                
                # Wait before next update
                await asyncio.sleep(2)  # Update every 2 seconds
                
    except WebSocketDisconnect:
        logger.info("Sensor WebSocket client disconnected")
    except Exception as e:
        logger.error(f"Sensor WebSocket error: {e}")
        await websocket.close()


@app.websocket("/ws/wafers")
async def websocket_wafers(websocket: WebSocket):
    """
    WebSocket endpoint for real-time wafer updates
    """
    await websocket.accept()
    
    try:
        with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector:
            wafer_collection = mdb_connector.get_collection("wafer_defects")
            
            while True:
                # Get latest wafer inspection
                latest_wafer = wafer_collection.find_one(
                    {},
                    sort=[("inspection_timestamp", -1)]
                )
                
                if latest_wafer:
                    # Remove large image data
                    if "ink_map" in latest_wafer and "thumbnail_base64" in latest_wafer["ink_map"]:
                        latest_wafer["ink_map"]["has_thumbnail"] = True
                        del latest_wafer["ink_map"]["thumbnail_base64"]
                    
                    latest_wafer = convert_objectids(latest_wafer)
                    
                    # Send to client
                    await websocket.send_json({
                        "type": "wafer_update",
                        "timestamp": datetime.now().isoformat(),
                        "wafer": latest_wafer
                    })
                
                # Wait before next update
                await asyncio.sleep(5)  # Update every 5 seconds
                
    except WebSocketDisconnect:
        logger.info("Wafer WebSocket client disconnected")
    except Exception as e:
        logger.error(f"Wafer WebSocket error: {e}")
        await websocket.close()


async def run_monitoring_loop():
    """
    Background task for continuous monitoring
    """
    global monitoring_active
    
    logger.info("Starting monitoring loop")
    
    while monitoring_active:
        try:
            # Run excursion detection
            # Note: ExcursionDetector.start_monitoring starts its own monitoring loop
            # For now, we'll check for active alerts periodically
            if alert_manager:
                excursions = []  # In production, this would come from change streams
                
                # Process any detected excursions
                for excursion in excursions:
                    if alert_manager:
                        # Create alert for excursion
                        alert_id = await alert_manager.create_alert(
                            alert_type=AlertType.EXCURSION,
                            severity=determine_severity(excursion),
                            title=f"Excursion detected on {excursion.get('equipment_id')}",
                            description=excursion.get('description', 'Threshold exceeded'),
                            source_data=excursion,
                            equipment_id=excursion.get('equipment_id')
                        )
                        
                        # Notify WebSocket clients
                        await notify_websocket_clients({
                            "type": "new_alert",
                            "alert_id": alert_id,
                            "severity": determine_severity(excursion).value,
                            "equipment_id": excursion.get('equipment_id')
                        })
            
            # Sleep before next iteration
            await asyncio.sleep(30)  # Check every 30 seconds
            
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            await asyncio.sleep(60)  # Wait longer on error
    
    logger.info("Monitoring loop stopped")


def determine_severity(excursion: Dict[str, Any]) -> AlertSeverity:
    """
    Determine alert severity based on excursion data
    """
    metrics = excursion.get('metrics', {})
    
    # Check particle count
    particle_count = metrics.get('particle_count', 0)
    if particle_count > 2000:
        return AlertSeverity.CRITICAL
    elif particle_count > 1500:
        return AlertSeverity.HIGH
    elif particle_count > 1000:
        return AlertSeverity.MEDIUM
    
    # Check RF power drift
    rf_power = metrics.get('rf_power', 0)
    if rf_power > 150:
        return AlertSeverity.CRITICAL
    elif rf_power > 120:
        return AlertSeverity.HIGH
    elif rf_power > 100:
        return AlertSeverity.MEDIUM
    
    # Default to medium
    return AlertSeverity.MEDIUM


async def notify_websocket_clients(message: Dict[str, Any]):
    """
    Send message to all connected WebSocket clients
    """
    if active_connections:
        message_json = json.dumps(convert_objectids(message))
        
        # Send to all connected clients
        disconnected = []
        for connection in active_connections:
            try:
                await connection.send_text(message_json)
            except:
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            active_connections.remove(conn)


# =============================================
# Phase 3: Semantic Search API Endpoints
# =============================================

from services.semantic_search import SemanticSearchService
from services.embedding_service import EmbeddingService

# Initialize semantic search service
semantic_search_service = None
embedding_service = None

@app.on_event("startup")
async def initialize_phase3_services():
    """Initialize Phase 3 services on startup"""
    global semantic_search_service, embedding_service
    
    try:
        # Initialize semantic search
        semantic_search_service = SemanticSearchService()
        await semantic_search_service.initialize()
        logger.info("Semantic search service initialized")
        
        # Initialize embedding service
        embedding_service = EmbeddingService()
        await embedding_service.initialize()
        logger.info("Embedding service initialized")
        
    except Exception as e:
        logger.warning(f"Phase 3 services not available: {e}")


@app.post("/search/semantic")
async def semantic_search(
    query: str = Body(..., description="Search query"),
    collections: List[str] = Body(None, description="Collections to search"),
    limit: int = Body(10, description="Maximum results per collection")
):
    """
    Perform semantic search across knowledge base
    """
    if not semantic_search_service:
        raise HTTPException(status_code=503, detail="Semantic search not available")
    
    try:
        # Perform hybrid search across collections
        results = await semantic_search_service.hybrid_search(
            query=query,
            collections=collections,
            limit_per_collection=limit
        )
        
        return {
            "query": query,
            "results": results,
            "total_results": sum(len(r) for r in results.values())
        }
        
    except Exception as e:
        logger.error(f"Semantic search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search/similar-defects")
async def find_similar_defects(
    wafer_id: Optional[str] = Body(None, description="Reference wafer ID"),
    pattern: Optional[str] = Body(None, description="Defect pattern"),
    equipment: Optional[str] = Body(None, description="Equipment filter"),
    image_data: Optional[str] = Body(None, description="Base64 encoded image"),
    limit: int = Body(10, description="Maximum results")
):
    """
    Find similar wafer defects using vector similarity
    """
    if not semantic_search_service:
        raise HTTPException(status_code=503, detail="Semantic search not available")
    
    try:
        results = await semantic_search_service.find_similar_defects(
            wafer_id=wafer_id,
            pattern=pattern,
            equipment=equipment,
            image_data=image_data,
            limit=limit
        )
        
        return {
            "search_criteria": {
                "wafer_id": wafer_id,
                "pattern": pattern,
                "equipment": equipment,
                "has_image": bool(image_data)
            },
            "similar_defects": results,
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"Similar defects search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search/rca-knowledge")
async def search_rca_knowledge(
    query: str = Body(..., description="Search query"),
    document_types: List[str] = Body(None, description="Document types to search"),
    process_areas: List[str] = Body(None, description="Process areas to filter"),
    limit: int = Body(10, description="Maximum results")
):
    """
    Search RCA knowledge base semantically
    """
    if not semantic_search_service:
        raise HTTPException(status_code=503, detail="Semantic search not available")
    
    try:
        results = await semantic_search_service.search_knowledge_base(
            query=query,
            document_types=document_types,
            process_areas=process_areas,
            limit=limit
        )
        
        return {
            "query": query,
            "filters": {
                "document_types": document_types,
                "process_areas": process_areas
            },
            "knowledge_documents": results,
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"RCA knowledge search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/embeddings/status")
async def get_embeddings_status():
    """
    Check embedding generation status
    """
    try:
        # Get counts from collections
        db = app.mongodb_client[app.database_name]
        
        # Count documents with embeddings
        historical_with_embeddings = await db.historical_knowledge.count_documents(
            {"embedding": {"$exists": True}}
        )
        historical_total = await db.historical_knowledge.count_documents({})
        
        wafer_with_embeddings = await db.wafer_defects.count_documents(
            {"embedding": {"$exists": True}}
        )
        wafer_total = await db.wafer_defects.count_documents({})
        
        alerts_with_embeddings = await db.alerts.count_documents(
            {"embedding": {"$exists": True}}
        )
        alerts_total = await db.alerts.count_documents({})
        
        return {
            "status": "operational",
            "collections": {
                "historical_knowledge": {
                    "with_embeddings": historical_with_embeddings,
                    "total": historical_total,
                    "percentage": round(historical_with_embeddings / historical_total * 100, 2) if historical_total > 0 else 0
                },
                "wafer_defects": {
                    "with_embeddings": wafer_with_embeddings,
                    "total": wafer_total,
                    "percentage": round(wafer_with_embeddings / wafer_total * 100, 2) if wafer_total > 0 else 0
                },
                "alerts": {
                    "with_embeddings": alerts_with_embeddings,
                    "total": alerts_total,
                    "percentage": round(alerts_with_embeddings / alerts_total * 100, 2) if alerts_total > 0 else 0
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting embeddings status: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


# ======================
# Phase 4: Agent Endpoints
# ======================

@app.post("/agent/start")
async def start_agent_session(
    query: str = Body(..., description="Analysis query or alert description"),
    alert_id: Optional[str] = Body(None, description="Associated alert ID"),
    equipment_id: Optional[str] = Body(None, description="Equipment ID for analysis"),
    metadata: Optional[dict] = Body(None, description="Additional metadata")
):
    """
    Start a new agent analysis session
    """
    try:
        from agent_workflow_graph import WorkflowGraphBuilder
        from agent_state import AgentState
        from agent_sessions import AgentSessionManager
        from config.config_loader import ConfigLoader
        
        # Create session
        session_manager = AgentSessionManager()
        session_id = await session_manager.create_session(
            user_id="api_user",
            query=query,
            metadata=metadata or {}
        )
        
        # Initialize agent state with all required fields
        initial_state = {
            "thread_id": session_id,
            "query_reported": query,
            "chain_of_thought": "",
            "timeseries_data": [],
            "embedding_vector": [],
            "historical_recommendations_list": [],
            "recommendation_text": "",
            "next_step": "start",
            "updates": [],
            # Additional context fields
            "alert_id": alert_id,
            "equipment_id": equipment_id,
            "metadata": metadata or {}
        }
        
        # Build and start workflow
        builder = WorkflowGraphBuilder(config_path="config/config.json")
        graph = builder.build()
        
        # Execute workflow asynchronously and capture results
        async def run_agent_workflow():
            try:
                # Update session to running
                await session_manager.update_session(session_id, {"status": "running"})
                
                # Execute the workflow
                result = await graph.ainvoke(initial_state)
                
                # Store results in session
                await session_manager.update_session(session_id, {
                    "status": "completed",
                    "result": result,
                    "recommendation_text": result.get("recommendation_text", ""),
                    "chain_of_thought": result.get("chain_of_thought", ""),
                    "completed_at": datetime.now(timezone.utc)
                })
                
                logger.info(f"Agent session {session_id} completed successfully")
                
            except Exception as e:
                logger.error(f"Agent session {session_id} failed: {str(e)}")
                await session_manager.update_session(session_id, {
                    "status": "failed",
                    "error": str(e),
                    "failed_at": datetime.now(timezone.utc)
                })
        
        # Start the workflow in background but track it
        asyncio.create_task(run_agent_workflow())
        
        return {
            "session_id": session_id,
            "status": "started",
            "query": query,
            "metadata": metadata
        }
        
    except Exception as e:
        logger.error(f"Error starting agent session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agent/status/{session_id}")
async def get_agent_session_status(session_id: str):
    """
    Get the status of an agent session
    """
    try:
        from agent_sessions import AgentSessionManager
        
        session_manager = AgentSessionManager()
        session = await session_manager.get_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "session_id": session_id,
            "status": session.get("status"),
            "created_at": session.get("created_at"),
            "updated_at": session.get("updated_at"),
            "metadata": session.get("metadata"),
            "checkpoints": session.get("checkpoints", [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agent/resume/{session_id}")
async def resume_agent_session(session_id: str):
    """
    Resume an existing agent session from last checkpoint
    """
    try:
        from agent_workflow_graph import WorkflowGraphBuilder
        from agent_checkpointer import AgentCheckpointer
        from config.config_loader import ConfigLoader
        
        # Get latest checkpoint
        checkpointer = AgentCheckpointer()
        checkpoint = await checkpointer.get_latest_checkpoint(session_id)
        
        if not checkpoint:
            raise HTTPException(status_code=404, detail="No checkpoint found for session")
        
        # Rebuild graph and resume
        builder = WorkflowGraphBuilder(config_path="config/config.json")
        graph = builder.build()
        
        # Resume from checkpoint
        state = checkpoint.get("state")
        
        # Get session manager
        from agent_sessions import AgentSessionManager
        session_manager = AgentSessionManager()
        
        async def resume_workflow():
            try:
                await session_manager.update_session(session_id, {"status": "resuming"})
                result = await graph.ainvoke(state)
                await session_manager.update_session(session_id, {
                    "status": "completed",
                    "result": result,
                    "recommendation_text": result.get("recommendation_text", ""),
                    "chain_of_thought": result.get("chain_of_thought", ""),
                    "completed_at": datetime.now(timezone.utc)
                })
                logger.info(f"Resumed session {session_id} completed")
            except Exception as e:
                logger.error(f"Resumed session {session_id} failed: {e}")
                await session_manager.update_session(session_id, {
                    "status": "failed",
                    "error": str(e)
                })
        
        asyncio.create_task(resume_workflow())
        
        return {
            "session_id": session_id,
            "status": "resumed",
            "checkpoint_id": str(checkpoint.get("_id")),
            "checkpoint_timestamp": checkpoint.get("timestamp")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/agent/stream/{session_id}")
async def stream_agent_session(websocket: WebSocket, session_id: str):
    """
    Stream agent thoughts and results via WebSocket
    """
    await websocket.accept()
    
    try:
        from agent_sessions import AgentSessionManager
        import asyncio
        
        session_manager = AgentSessionManager()
        
        while True:
            # Get session updates
            session = await session_manager.get_session(session_id)
            
            if session:
                # Send current state
                await websocket.send_json({
                    "type": "update",
                    "session_id": session_id,
                    "status": session.get("status"),
                    "updates": session.get("updates", [])
                })
                
                # Check if session is complete
                if session.get("status") in ["completed", "failed"]:
                    await websocket.send_json({
                        "type": "complete",
                        "session_id": session_id,
                        "result": session.get("result")
                    })
                    break
            
            await asyncio.sleep(1)  # Poll every second
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()


@app.get("/agent/sessions")
async def list_agent_sessions(
    limit: int = Query(20, description="Maximum number of sessions to return"),
    status: Optional[str] = Query(None, description="Filter by status")
):
    """
    List recent agent sessions
    """
    try:
        from agent_sessions import AgentSessionManager
        
        session_manager = AgentSessionManager()
        sessions = await session_manager.list_sessions(limit=limit, status=status)
        
        return {
            "sessions": sessions,
            "count": len(sessions)
        }
        
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))