from db.mdb import MongoDBConnector

import logging
from datetime import datetime, timedelta, timezone

import json
from bson import ObjectId
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient

from fastapi import FastAPI, HTTPException, Request, Query, WebSocket, WebSocketDisconnect, BackgroundTasks, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from config.config_loader import ConfigLoader
from utils import convert_objectids, format_document

from agent_workflow_graph import create_workflow_graph
from agent_state import AgentState
from agent_checkpointer import AgentCheckpointer

# Import Phase 2 services
from services.excursion_detector import ExcursionDetector
from services.correlation_engine import CorrelationEngine
from services.rca_generator import RCAGenerator
from services.alert_manager import AlertManager, AlertSeverity, AlertStatus, AlertType
from services.websocket_manager import get_websocket_manager, ConnectionType
from services.wafer_generator import WaferGenerator
from services.sensor_data_writer import SensorDataWriter

# Import Multi-Agent System (Phase 3)
from multi_agent import create_initial_state
from multi_agent.workers import monitoring_agent_tool, investigation_agent_tool, rca_agent_tool
from multi_agent.supervisor import supervisor_synthesis_agent

import os
from dotenv import load_dotenv
import asyncio
import random

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

# Demo Mode Configuration
DEMO_MODE_ENABLED = os.getenv("DEMO_MODE_ENABLED", "false").lower() == "true"
DEMO_INTERVAL_SECONDS = int(os.getenv("DEMO_INTERVAL_SECONDS", "60"))  # 60 seconds (1 minute) for continuous Atlas Charts visualization
DEMO_EXCURSION_PROBABILITY = float(os.getenv("DEMO_EXCURSION_PROBABILITY", "0.05"))  # 5% excursion rate for realistic monitoring

# Demo Mode Global State
demo_mode_active = False
demo_task = None

# Pattern-based demo state for realistic anomaly scenarios
equipment_pattern_state = {}  # {equipment_id: {"pattern": "drift", "stage": 3, ...}}

# Process context IDs cache (loaded from MongoDB)
process_context_cache = {
    "problematic_batches": [],
    "normal_batches": [],
    "recipes": [],
    "loaded": False
}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Feature flag for AI multi-agent system
USE_AI_AGENTS = os.getenv("USE_AI_AGENTS", "true").lower() == "true"
logger.info(f"🤖 AI Multi-Agent System: {'ENABLED' if USE_AI_AGENTS else 'DISABLED'}")

# ============================================================================
# Demo Mode Functions
# ============================================================================

async def load_process_context_ids():
    """Load real process context IDs from MongoDB for demo metadata"""
    global process_context_cache

    if process_context_cache["loaded"]:
        return process_context_cache

    try:
        async_client = AsyncIOMotorClient(MDB_URI)
        async_db = async_client[MDB_DATABASE_NAME]

        # Fetch problematic slurry batches
        problematic_cursor = async_db.process_context.find({
            "is_problematic": True,
            "context_type": "slurry_batch"
        })
        process_context_cache["problematic_batches"] = [
            doc["context_id"] async for doc in problematic_cursor
        ]

        # Fetch normal slurry batches
        normal_cursor = async_db.process_context.find({
            "is_problematic": False,
            "context_type": "slurry_batch"
        })
        process_context_cache["normal_batches"] = [
            doc["context_id"] async for doc in normal_cursor
        ]

        # Fetch recipe IDs
        recipe_cursor = async_db.process_context.find({
            "context_type": "recipe"
        })
        process_context_cache["recipes"] = [
            doc["context_id"] async for doc in recipe_cursor
        ]

        process_context_cache["loaded"] = True
        async_client.close()

        logger.info(f"✅ Loaded process context: {len(process_context_cache['problematic_batches'])} problematic batches, "
                   f"{len(process_context_cache['normal_batches'])} normal batches, "
                   f"{len(process_context_cache['recipes'])} recipes")
        logger.info(f"📋 Problematic batches: {process_context_cache['problematic_batches']}")
        logger.info(f"📋 Normal batches (first 5): {process_context_cache['normal_batches'][:5]}")
        logger.info(f"📋 Recipes: {process_context_cache['recipes']}")

        return process_context_cache

    except Exception as e:
        logger.error(f"Failed to load process context IDs: {e}")
        # Fallback to hardcoded values if MongoDB fails
        process_context_cache["problematic_batches"] = ["SB_2025_021", "SB_2025_043", "SB_2025_045", "SB_2025_047", "SB_2025_048"]
        process_context_cache["normal_batches"] = ["SB_2025_003", "SB_2025_005", "SB_2025_010", "SB_2025_011", "SB_2025_012"]
        process_context_cache["recipes"] = ["RECIPE_01", "RECIPE_02", "RECIPE_03", "RECIPE_04", "RECIPE_05"]
        process_context_cache["loaded"] = True
        return process_context_cache

def initialize_pattern_state():
    """Initialize pattern state for realistic demo scenarios with industry-aligned patterns"""
    global equipment_pattern_state
    equipment_ids = ["CMP_TOOL_01", "CMP_TOOL_02", "ETCH_01", "ETCH_02", "LITHO_01", "LITHO_02"]

    for eq_id in equipment_ids:
        equipment_pattern_state[eq_id] = {
            "pattern": "normal",
            "stage": 0,
            "baseline_value": None,
            "target_value": None,
            "started_at": None,
            "total_stages": 0
        }

    logger.info("Initialized pattern-based demo state for realistic anomaly scenarios")

def should_create_pattern(equipment_id: str) -> bool:
    """Decide if equipment should start a new pattern (5% chance per cycle)"""
    state = equipment_pattern_state.get(equipment_id, {})

    # Already in a pattern? Continue it
    if state.get("pattern") != "normal":
        return False

    # 5% chance to start new pattern
    return random.random() < 0.05

def get_pattern_metrics(equipment_id: str, base_metrics: dict) -> tuple:
    """
    Generate metrics following realistic industry patterns for monitoring agent validation

    Patterns based on industry research (NVIDIA NV-Tesseract, semiconductor fab operations):
    - drift: Gradual increase (filter degradation, contamination buildup)
    - spike: Sudden persistent issue (equipment malfunction)
    - false_positive: Single spike returning to normal (sensor glitch, transient)
    - oscillation: Recurring pattern (cyclic process issue)

    Returns:
        (metrics_dict, is_real_excursion_bool)
    """
    state = equipment_pattern_state.get(equipment_id, {})

    # Initialize new pattern if needed
    if state.get("pattern") == "normal" and should_create_pattern(equipment_id):
        # Choose pattern type (aligned with monitoring agent detection capabilities)
        pattern_type = random.choices(
            ["drift", "spike", "false_positive", "oscillation"],
            weights=[30, 25, 35, 10],  # False positive most common (35%) to showcase filtering
            k=1
        )[0]

        state["pattern"] = pattern_type
        state["stage"] = 0
        state["baseline_value"] = base_metrics["particle_count"]
        state["started_at"] = datetime.now(timezone.utc)

        if pattern_type == "drift":
            state["target_value"] = random.randint(1200, 2000)
            state["total_stages"] = random.randint(5, 8)  # 5-8 readings to reach target
            logger.info(f"📈 {equipment_id}: Starting DRIFT pattern ({state['baseline_value']} → {state['target_value']} over {state['total_stages']} readings)")
        elif pattern_type == "spike":
            state["target_value"] = random.randint(1500, 3000)
            state["total_stages"] = random.randint(3, 5)  # Persist 3-5 readings
            logger.info(f"⚡ {equipment_id}: Starting SPIKE pattern (value: {state['target_value']}, persists: {state['total_stages']} readings)")
        elif pattern_type == "false_positive":
            state["target_value"] = random.randint(1050, 1200)  # Just over threshold
            state["total_stages"] = 1  # Single spike only
            logger.info(f"🔔 {equipment_id}: Starting FALSE_POSITIVE pattern (spike to {state['target_value']}, immediate return)")
        elif pattern_type == "oscillation":
            state["target_value"] = random.randint(1100, 1500)
            state["total_stages"] = random.randint(6, 10)
            logger.info(f"🌊 {equipment_id}: Starting OSCILLATION pattern (amplitude: {state['target_value']}, cycles: {state['total_stages']})")

    # Apply current pattern
    pattern = state.get("pattern", "normal")
    metrics = base_metrics.copy()
    is_real_excursion = False

    if pattern == "drift":
        # Gradual linear increase (realistic filter degradation or contamination buildup)
        stage = state["stage"]
        total = state["total_stages"]
        baseline = state["baseline_value"]
        target = state["target_value"]

        current_value = baseline + (target - baseline) * (stage / total)
        metrics["particle_count"] = int(current_value)

        # Only trigger alert on FIRST reading that exceeds threshold (one pattern = one alert)
        is_real_excursion = (current_value > 1000 and stage == 0)

        state["stage"] += 1

        if state["stage"] >= total:
            state["pattern"] = "normal"
            state["stage"] = 0
            logger.info(f"✅ {equipment_id}: DRIFT pattern completed ({baseline} → {target})")

    elif pattern == "spike":
        # Sudden spike that persists (equipment malfunction)
        if state["stage"] == 0:
            metrics["particle_count"] = state["target_value"]
        else:
            metrics["particle_count"] = state["target_value"] + random.randint(-50, 50)

        # Only trigger alert on FIRST reading of spike (one pattern = one alert)
        is_real_excursion = (state["stage"] == 0)

        state["stage"] += 1

        if state["stage"] >= state["total_stages"]:
            state["pattern"] = "normal"
            state["stage"] = 0
            logger.info(f"✅ {equipment_id}: SPIKE pattern completed")

    elif pattern == "false_positive":
        # Single spike then immediate return (sensor glitch - LLM should filter this!)
        if state["stage"] == 0:
            metrics["particle_count"] = state["target_value"]
            logger.info(f"🔔 {equipment_id}: FALSE_POSITIVE spike at {state['target_value']} (monitoring agent should filter)")
            state["stage"] += 1
        else:
            # Return to normal immediately
            metrics["particle_count"] = state["baseline_value"] + random.randint(-20, 20)
            state["pattern"] = "normal"
            state["stage"] = 0
            is_real_excursion = False
            logger.info(f"✅ {equipment_id}: FALSE_POSITIVE resolved (returned to normal)")

    elif pattern == "oscillation":
        # Cyclic up/down pattern (recurring process issue)
        import math
        stage = state["stage"]
        baseline = state["baseline_value"]
        amplitude = state["target_value"] - baseline

        current_value = baseline + (amplitude * abs(math.sin(stage * math.pi / 2)))
        metrics["particle_count"] = int(current_value)

        # Only trigger alert on FIRST reading that exceeds threshold (one pattern = one alert)
        is_real_excursion = (current_value > 1000 and stage == 0)

        state["stage"] += 1

        if state["stage"] >= state["total_stages"]:
            state["pattern"] = "normal"
            state["stage"] = 0
            logger.info(f"✅ {equipment_id}: OSCILLATION pattern completed")

    return metrics, is_real_excursion

def generate_demo_metrics(equipment_id: str, is_excursion: bool = False) -> dict:
    """Generate realistic sensor metrics with pattern-based anomalies for monitoring agent validation"""
    base_metrics = {
        "CMP_TOOL": {
            "particle_count": 450 + random.randint(-50, 50),  # [400-500] - realistic clean room range
            "rf_power": 1450 + random.uniform(-20, 20),
            "chamber_pressure": 45 + random.uniform(-2, 2),
            "temperature": 65 + random.uniform(-1, 1),
            "flow_rate": 200 + random.uniform(-10, 10)
        },
        "ETCH": {
            "particle_count": 400 + random.randint(-40, 40),  # [360-440] - realistic clean room range
            "rf_power": 1200 + random.uniform(-15, 15),
            "chamber_pressure": 35 + random.uniform(-1.5, 1.5),
            "temperature": 70 + random.uniform(-1.5, 1.5),
            "flow_rate": 150 + random.uniform(-8, 8)
        },
        "LITHO": {
            "particle_count": 350 + random.randint(-30, 30),  # [320-380] - realistic clean room range
            "rf_power": 800 + random.uniform(-10, 10),
            "chamber_pressure": 25 + random.uniform(-1, 1),
            "temperature": 22 + random.uniform(-0.5, 0.5),
            "flow_rate": 100 + random.uniform(-5, 5)
        }
    }

    # Determine equipment type (CMP_TOOL_01 -> CMP)
    equipment_type = equipment_id.split("_")[0]
    # Map CMP to CMP_TOOL in base_metrics
    if equipment_type == "CMP":
        equipment_type = "CMP_TOOL"
    metrics = base_metrics.get(equipment_type, base_metrics["CMP_TOOL"]).copy()

    # Use pattern-based generation if pattern state exists
    if equipment_id in equipment_pattern_state:
        metrics, _ = get_pattern_metrics(equipment_id, metrics)
    elif is_excursion:
        # Fallback to old behavior if pattern state not initialized
        excursion_type = random.choice(["particle_excursion", "rf_power_drift", "temperature_drift"])

        if excursion_type == "particle_excursion":
            metrics["particle_count"] = random.randint(1100, 4000)
        elif excursion_type == "rf_power_drift":
            metrics["rf_power"] = metrics["rf_power"] + random.uniform(200, 400)
        elif excursion_type == "temperature_drift":
            metrics["temperature"] = metrics["temperature"] + random.uniform(5, 10)

    # Round values to reasonable precision
    metrics["particle_count"] = int(metrics["particle_count"])
    metrics["rf_power"] = round(metrics["rf_power"], 1)
    metrics["chamber_pressure"] = round(metrics["chamber_pressure"], 1)
    metrics["temperature"] = round(metrics["temperature"], 1)
    metrics["flow_rate"] = round(metrics["flow_rate"], 1)

    # Add temp_drift for monitoring (temperature change from normal baseline)
    normal_temps = {"CMP_TOOL": 65, "ETCH": 70, "LITHO": 22}
    normal_temp = normal_temps.get(equipment_type, 65)
    metrics["temp_drift"] = round(metrics["temperature"] - normal_temp, 1)

    return metrics

def generate_demo_metadata(is_excursion: bool = False) -> dict:
    """Generate realistic metadata using REAL process context IDs from MongoDB"""
    global process_context_cache

    lot_number = random.randint(1, 50)
    wafer_number = random.randint(1, 25)

    # Use REAL slurry batch IDs from process_context collection
    if is_excursion and random.random() < 0.7:  # 70% chance to use problematic batch during excursion
        # Use real problematic batches from MongoDB
        if process_context_cache["problematic_batches"]:
            slurry_batch = random.choice(process_context_cache["problematic_batches"])
        else:
            # Fallback if not loaded yet
            slurry_batch = "SB_2025_021"
    else:
        # Use real normal batches from MongoDB
        if process_context_cache["normal_batches"]:
            slurry_batch = random.choice(process_context_cache["normal_batches"])
        else:
            # Fallback if not loaded yet
            slurry_batch = "SB_2025_003"

    # Use real recipe IDs from MongoDB
    if process_context_cache["recipes"]:
        recipe_id = random.choice(process_context_cache["recipes"])
    else:
        # Fallback if not loaded yet
        recipe_id = f"RECIPE_{random.randint(1, 10):02d}"

    metadata = {
        "lot_id": f"LOT_2025_{lot_number:03d}",
        "wafer_id": f"W_{lot_number:03d}_{wafer_number:02d}",
        "recipe_id": recipe_id,
        "slurry_batch": slurry_batch,
        "operator_id": f"OP_{random.randint(100, 200)}"
    }

    # Log when problematic batch is used
    if is_excursion and slurry_batch in process_context_cache.get("problematic_batches", []):
        logger.info(f"🚨 Generated excursion metadata with PROBLEMATIC batch: {slurry_batch}")

    return metadata

async def demo_data_generator():
    """Generate normal sensor data with occasional anomalies - parallel for all equipment"""
    global demo_mode_active

    # Updated to include all 6 standardized equipment tools (2025-01-03)
    equipment_ids = ["CMP_TOOL_01", "CMP_TOOL_02", "ETCH_01", "ETCH_02", "LITHO_01", "LITHO_02"]

    logger.info(f"Demo data generator started - Interval: {DEMO_INTERVAL_SECONDS}s, Excursion probability: {DEMO_EXCURSION_PROBABILITY}")
    logger.info(f"Generating parallel data for {len(equipment_ids)} equipment - {60 // (120 // DEMO_INTERVAL_SECONDS)} data points per 2 minutes")

    while demo_mode_active:
        try:
            # Generate timestamp once for all equipment in this batch
            timestamp = datetime.now(timezone.utc)

            # Collect data for all equipment
            bulk_data = []
            excursion_count = 0
            particle_excursion_count = 0

            # Pick at most ONE equipment to have excursion (prevents multiple simultaneous Bedrock calls)
            excursion_equipment = None
            if random.random() < DEMO_EXCURSION_PROBABILITY:
                excursion_equipment = random.choice(equipment_ids)

            for equipment_id in equipment_ids:
                # Only the selected equipment gets excursion
                is_excursion = (equipment_id == excursion_equipment)
                if is_excursion:
                    excursion_count += 1

                # Generate sensor data for this equipment
                data = {
                    "equipment_id": equipment_id,
                    "process_step": equipment_id.split("_")[0],
                    "timestamp": timestamp,  # Use same timestamp for batch consistency
                    "metrics": generate_demo_metrics(equipment_id, is_excursion),
                    "metadata": generate_demo_metadata(is_excursion)
                }

                bulk_data.append(data)

                # Track particle excursions for logging
                if data['metrics']['particle_count'] > 1000:
                    particle_excursion_count += 1

            # Use bulk write for all equipment data
            writer = SensorDataWriter(mongodb_uri=MDB_URI, database=MDB_DATABASE_NAME)
            result = writer.bulk_write_sensor_data(bulk_data)
            writer.close()

            if result["sensor_events"]["inserted"] > 0 or result["process_sensor_ts"]["inserted"] > 0:
                logger.info(f"Demo batch generated: {len(bulk_data)} equipment readings, "
                           f"{excursion_count} excursions, {particle_excursion_count} particle alerts expected")

                # Log details if there were excursions
                if particle_excursion_count > 0:
                    excursion_equipment = [d["equipment_id"] for d in bulk_data if d["metrics"]["particle_count"] > 1000]
                    logger.warning(f"Particle excursions on: {', '.join(excursion_equipment)} - Alerts will be created")
            else:
                logger.error(f"Failed to write demo batch: {result.get('errors', [])}")

            # Wait for next interval
            await asyncio.sleep(DEMO_INTERVAL_SECONDS)

        except asyncio.CancelledError:
            logger.info("Demo data generator cancelled")
            break
        except Exception as e:
            logger.error(f"Error in demo data generator: {e}")
            # Continue running even if one iteration fails
            await asyncio.sleep(DEMO_INTERVAL_SECONDS)

    logger.info("Demo data generator stopped")

# ============================================================================

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
wafer_monitoring_task = None

# Global MongoDB async client
mongodb_client = None

# WebSocket Manager for real-time updates
ws_manager = get_websocket_manager()

@app.on_event("startup")
async def startup_event():
    """
    Initialize monitoring services on application startup
    """
    global excursion_detector, correlation_engine, rca_generator, alert_manager, monitoring_active, mongodb_client

    logger.info("Initializing monitoring services on startup...")

    try:
        # Initialize async MongoDB client
        mongodb_client = AsyncIOMotorClient(MDB_URI)
        
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

        # Initialize alert manager (sync setup)
        alert_manager.initialize()

        # Set monitoring as active and auto-start monitoring loops
        monitoring_active = True

        # Auto-start monitoring loops on startup
        global monitoring_task, wafer_monitoring_task
        monitoring_task = asyncio.create_task(run_monitoring_loop())
        wafer_monitoring_task = asyncio.create_task(run_wafer_monitoring_loop())

        logger.info("✅ Monitoring services initialized successfully on startup")
        logger.info("Services ready: ExcursionDetector, CorrelationEngine, RCAGenerator, AlertManager")
        logger.info("✅ Monitoring loops auto-started (sensor + wafer defects)")

        # Initialize Phase 3 services
        await initialize_phase3_services()

    except Exception as e:
        logger.error(f"❌ Failed to initialize monitoring services on startup: {e}")
        logger.warning("Services will be initialized on first use")

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
    Start real-time monitoring loop (services already initialized on startup)
    """
    global excursion_detector, correlation_engine, rca_generator, alert_manager, monitoring_active, monitoring_task, wafer_monitoring_task

    try:
        # Check if services are already initialized (from startup)
        if not all([excursion_detector, correlation_engine, rca_generator, alert_manager]):
            logger.info("Services not initialized on startup, initializing now...")

            # Initialize services if not already done
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

            # Initialize alert manager (sync setup)
            alert_manager.initialize()

        # Check if monitoring loops are already running
        if (monitoring_task and not monitoring_task.done()) or (wafer_monitoring_task and not wafer_monitoring_task.done()):
            return {
                "status": "already_running",
                "message": "Monitoring loops are already active",
                "services": {
                    "excursion_detector": "active",
                    "correlation_engine": "active",
                    "rca_generator": "active",
                    "alert_manager": "active",
                    "sensor_monitoring": "active" if monitoring_task and not monitoring_task.done() else "stopped",
                    "wafer_monitoring": "active" if wafer_monitoring_task and not wafer_monitoring_task.done() else "stopped"
                }
            }

        # Start monitoring loops in background (parallel execution)
        monitoring_active = True
        monitoring_task = asyncio.create_task(run_monitoring_loop())
        wafer_monitoring_task = asyncio.create_task(run_wafer_monitoring_loop())

        logger.info("Real-time monitoring loops started (sensor + wafer)")
        return {
            "status": "started",
            "message": "Real-time monitoring loops started (sensor + wafer defects)",
            "services": {
                "excursion_detector": "active",
                "correlation_engine": "active",
                "rca_generator": "active",
                "alert_manager": "active",
                "sensor_monitoring": "active",
                "wafer_monitoring": "active"
            }
        }

    except Exception as e:
        logger.error(f"Error starting monitoring loop: {e}")
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
        
        alerts = alert_manager.get_active_alerts(
            severity=severity_enum,
            alert_type=alert_type_enum,
            equipment_id=equipment_id,
            limit=limit
        )

        # Convert ObjectIds for JSON serialization
        alerts = convert_objectids(alerts)

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
        
        alert = alert_manager.get_alert_by_id(alert_id)
        
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        # Get alert history
        history = alert_manager.get_alert_history(alert_id)

        # Convert ObjectIds
        alert = convert_objectids(alert)
        history = convert_objectids(history)

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
        
        alert = alert_manager.get_alert_by_id(alert_id)
        
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        # Perform correlation analysis if not already done (skip if AI agents enabled)
        if not alert.get("correlation_analysis") and not USE_AI_AGENTS:
            # Trigger async correlation analysis
            asyncio.create_task(run_alert_correlation(alert_id))

            # Trigger RCA for critical alerts
            if alert.get("severity") == "critical":
                asyncio.create_task(run_alert_rca(alert_id, AlertSeverity.CRITICAL))

            return {
                "alert_id": alert_id,
                "message": "Analysis triggered. Check back in a few seconds.",
                "status": "processing"
            }

        # Convert ObjectIds
        alert = convert_objectids(alert)

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

        return response
        
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
        
        success = alert_manager.acknowledge_alert(alert_id, acknowledged_by, notes)
        
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
        
        success = alert_manager.update_alert_status(
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
        
        stats = alert_manager.get_alert_statistics(time_window_hours)
        
        return stats
        
    except Exception as e:
        logger.error(f"Error retrieving alert statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/alerts/{alert_id}/fix")
async def fix_equipment_issue(alert_id: str):
    """
    Fix equipment issue by injecting healthy sensor data and resolving the alert
    This simulates a maintenance action that fixes the equipment
    """
    try:
        if not alert_manager:
            raise HTTPException(status_code=503, detail="Alert manager not initialized")
        
        # Get the alert details
        alert = alert_manager.get_alert_by_id(alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
        
        equipment_id = alert.get("equipment_id")
        if not equipment_id:
            raise HTTPException(status_code=400, detail="Alert has no associated equipment")
        
        # Use async MongoDB client
        db = mongodb_client[MDB_DATABASE_NAME]
        sensor_collection = db[MDB_TIMESERIES_COLLECTION]
        
        # Get the process step for this equipment
        last_reading = await sensor_collection.find_one(
            {"equipment_id": equipment_id},
            sort=[("timestamp", -1)]
        )
        
        process_step = last_reading.get("process_step", "UNKNOWN") if last_reading else "UNKNOWN"
        
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
        
        # Insert healthy reading into time series
        result = await sensor_collection.insert_one(healthy_reading)
        
        if not result.inserted_id:
            raise HTTPException(status_code=500, detail="Failed to insert healthy sensor data")
        
        # Now resolve the alert
        resolution_notes = f"Equipment fixed - Healthy sensor data injected. Particle count reduced to {healthy_reading['metrics']['particle_count']}"
        success = alert_manager.update_alert_status(
            alert_id=alert_id,
            status=AlertStatus.RESOLVED,
            updated_by="system",
            notes=resolution_notes
        )
        
        if not success:
            logger.warning(f"Alert {alert_id} could not be resolved after fix")
        
        # Log the fix action
        logger.info(f"Fixed equipment {equipment_id} for alert {alert_id}")
        
        return {
            "status": "success",
            "message": f"Equipment {equipment_id} fixed successfully",
            "alert_id": alert_id,
            "new_metrics": healthy_reading["metrics"],
            "alert_resolved": success
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fixing equipment for alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================== Real-time Monitoring Dashboard APIs ======================

@app.get("/kpi/statistics")
async def get_kpi_statistics():
    """
    Get comprehensive KPI statistics for dashboard
    Optimized to run all aggregations in parallel
    """
    try:
        # Use async MongoDB client from app startup
        db = mongodb_client[MDB_DATABASE_NAME]
        
        # Define all aggregation pipelines
        wafer_pipeline = [
            {"$sort": {"inspection_timestamp": -1}},
            {"$limit": 10},
            {"$group": {
                "_id": None,
                "avg_yield": {"$avg": "$defect_summary.yield_percentage"},
                "latest_yield": {"$first": "$defect_summary.yield_percentage"},
                "total_wafers": {"$sum": 1}
            }}
        ]
        
        alert_pipeline = [
            {"$match": {"status": {"$in": ["open", "acknowledged"]}}},
            {"$group": {
                "_id": "$severity",
                "count": {"$sum": 1}
            }}
        ]
        
        resolution_pipeline = [
            {"$match": {
                "status": "resolved",
                "resolved_at": {"$exists": True},
                "timestamp": {"$exists": True}
            }},
            {"$limit": 50},
            {"$project": {
                "resolution_time_ms": {
                    "$subtract": ["$resolved_at", "$timestamp"]
                }
            }},
            {"$group": {
                "_id": None,
                "avg_resolution_ms": {"$avg": "$resolution_time_ms"},
                "count": {"$sum": 1}
            }}
        ]
        
        equipment_pipeline = [
            {"$sort": {"timestamp": -1}},
            {"$group": {
                "_id": "$equipment_id",
                "latest": {"$first": "$$ROOT"}
            }},
            {"$project": {
                "rf_power": "$latest.metrics.rf_power",
                "particle_count": "$latest.metrics.particle_count"
            }}
        ]
        
        # Execute all aggregations in parallel using asyncio.gather
        import asyncio
        
        # Create async tasks for each aggregation
        wafer_task = db.wafer_defects.aggregate(wafer_pipeline).to_list(length=None)
        alert_task = db.alerts.aggregate(alert_pipeline).to_list(length=None)
        resolution_task = db.alerts.aggregate(resolution_pipeline).to_list(length=None)
        equipment_task = db.process_sensor_ts.aggregate(equipment_pipeline).to_list(length=None)
        
        # Run all tasks in parallel
        wafer_stats, alert_results, resolution_stats, equipment_results = await asyncio.gather(
            wafer_task,
            alert_task,
            resolution_task,
            equipment_task
        )
        
        # Process results (same logic as before, but now with parallel data)
        current_yield = wafer_stats[0]["latest_yield"] if wafer_stats else 94.2
        avg_yield = wafer_stats[0]["avg_yield"] if wafer_stats else 94.2
        
        # Process alert counts
        alert_counts = {item["_id"]: item["count"] for item in alert_results}
        total_alerts = sum(alert_counts.values())
        critical_alerts = alert_counts.get("critical", 0) + alert_counts.get("high", 0)
        
        # Calculate average resolution time
        avg_resolution_minutes = 12  # Default
        if resolution_stats and resolution_stats[0].get("avg_resolution_ms"):
            avg_resolution_minutes = resolution_stats[0]["avg_resolution_ms"] / 60000
        
        # Calculate cost savings
        baseline_yield = 92.0
        yield_improvement = max(0, current_yield - baseline_yield)
        wafers_per_month = 10000
        revenue_per_wafer = 5000  # $5000 per wafer
        cost_savings = (yield_improvement / 100) * wafers_per_month * revenue_per_wafer
        
        # Calculate equipment utilization
        total_utilization = 0
        equipment_count = 0
        for eq in equipment_results:
            if eq.get("rf_power"):
                utilization = min(100, (eq["rf_power"] / 1500) * 100)
                total_utilization += utilization
                equipment_count += 1
        
        avg_utilization = total_utilization / equipment_count if equipment_count > 0 else 75
        
        # Calculate trend value
        trend_value = round(current_yield - avg_yield, 1) if avg_yield else 0
        
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
                    "trendValue": max(0, 30 - avg_resolution_minutes),
                    "trendLabel": "% improvement",
                    "thresholds": {"critical": 60, "warning": 30, "good": 15}
                },
                "savings": {
                    "label": "Cost Savings",
                    "value": round(cost_savings / 1000000, 1),
                    "unit": "M",
                    "prefix": "$",
                    "trend": "up" if cost_savings > 2000000 else "down",
                    "trendValue": round((cost_savings / 2000000) * 100 - 100),
                    "period": "This Month",
                    "thresholds": {"critical": 0, "warning": 1, "good": 2}
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
        
    except Exception as e:
        logger.error(f"Error calculating KPI statistics: {e}")
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


@app.post("/sensors/write")
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
    try:
        # Ensure timestamp is datetime object
        if "timestamp" not in data:
            data["timestamp"] = datetime.now(timezone.utc)
        elif isinstance(data["timestamp"], str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"].replace('Z', '+00:00'))

        # Validate required fields
        if "equipment_id" not in data:
            raise HTTPException(status_code=400, detail="equipment_id is required")
        if "metrics" not in data:
            raise HTTPException(status_code=400, detail="metrics are required")

        # Add process step if not provided
        if "process_step" not in data:
            data["process_step"] = data["equipment_id"].split("_")[0]

        # Use SensorDataWriter for dual writes to both collections
        writer = SensorDataWriter(mongodb_uri=MDB_URI, database=MDB_DATABASE_NAME)
        result = writer.write_sensor_data(data)
        writer.close()

        # Log the results
        if result["success"]:
            logger.info(f"Sensor data written for {data['equipment_id']}: "
                       f"particle_count={data['metrics'].get('particle_count', 0)}, "
                       f"sensor_events_id={result.get('sensor_events')}, "
                       f"process_sensor_ts_id={result.get('process_sensor_ts')}")
        else:
            logger.warning(f"Partial write for {data['equipment_id']}: {result.get('errors', [])}")

        # Return success if at least one write succeeded
        if result["success"]:
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
            raise HTTPException(
                status_code=500,
                detail=f"Failed to write sensor data: {result.get('errors', [])}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error accepting sensor data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
    min_yield: Optional[float] = Query(None, description="Minimum yield percentage"),
    include_visualization: bool = Query(False, description="Include die_map and defects for visualization")
):
    """
    Get latest wafer inspection results with optional visualization data
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

            # Build projection based on include_visualization flag
            projection = None
            if not include_visualization:
                # Exclude die_map and limit defects when not needed for visualization
                projection = {"die_map": 0}  # Exclude die_map to reduce payload

            # Get latest wafers
            if projection:
                wafers = list(wafer_collection.find(query, projection).sort("inspection_timestamp", -1).limit(limit))
            else:
                wafers = list(wafer_collection.find(query).sort("inspection_timestamp", -1).limit(limit))

            # Process wafers based on visualization flag
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
                    # When including visualization, still remove base64 images but keep die_map
                    if "ink_map" in wafer:
                        if "thumbnail_base64" in wafer["ink_map"]:
                            wafer["ink_map"]["has_thumbnail"] = True
                            del wafer["ink_map"]["thumbnail_base64"]  # Remove to reduce size
                        if "full_image_base64" in wafer["ink_map"]:
                            wafer["ink_map"]["has_full_image"] = True
                            del wafer["ink_map"]["full_image_base64"]  # Remove to reduce size

            wafers = convert_objectids(wafers)

            return {
                "count": len(wafers),
                "wafers": wafers,
                "visualization_included": include_visualization
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


@app.get("/wafers/yield-timeline")
async def get_yield_timeline(
    limit: int = Query(50, description="Number of wafers to include in timeline"),
    include_alerts: bool = Query(True, description="Include alert markers")
):
    """
    Get yield trend timeline data for charting
    Returns wafer yield data with optional alert markers for correlation visualization
    """
    try:
        with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector:
            wafer_collection = mdb_connector.get_collection("wafer_defects")
            alert_collection = mdb_connector.get_collection("alerts")

            # Get latest wafers sorted by inspection time
            wafers = list(wafer_collection.find()
                        .sort("inspection_timestamp", -1)
                        .limit(limit))

            # Reverse to get chronological order for chart
            wafers.reverse()

            # Extract timeline data
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

            # Get alerts in same timeframe if requested
            alert_markers = []
            if include_alerts and timeline_data:
                start_time = timeline_data[0]["timestamp"]
                end_time = timeline_data[-1]["timestamp"]

                alerts = list(alert_collection.find({
                    "timestamp": {"$gte": start_time, "$lte": end_time}
                }).sort("timestamp", 1))

                for alert in alerts:
                    alert_markers.append({
                        "alert_id": alert.get("alert_id"),
                        "timestamp": alert.get("timestamp"),
                        "severity": alert.get("severity"),
                        "equipment_id": alert.get("equipment_id"),
                        "excursion_type": alert.get("source_data", {}).get("excursion_type")
                    })

            # Convert MongoDB dates to ISO strings
            timeline_data = convert_objectids(timeline_data)
            alert_markers = convert_objectids(alert_markers)

            return {
                "timeline": timeline_data,
                "alert_markers": alert_markers,
                "count": len(timeline_data),
                "timeframe": {
                    "start": timeline_data[0]["timestamp"] if timeline_data else None,
                    "end": timeline_data[-1]["timestamp"] if timeline_data else None
                },
                "stats": {
                    "avg_yield": sum(d["yield_percentage"] for d in timeline_data) / len(timeline_data) if timeline_data else 0,
                    "min_yield": min(d["yield_percentage"] for d in timeline_data) if timeline_data else 0,
                    "max_yield": max(d["yield_percentage"] for d in timeline_data) if timeline_data else 0
                }
            }

    except Exception as e:
        logger.error(f"Error fetching yield timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/wafers/inject")
async def inject_test_wafer():
    """
    Inject a test wafer defect without excursion link for testing wafer monitoring
    This simulates wafers from manual inspection or batch imports
    """
    try:
        # Connect to MongoDB
        with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector:
            wafer_collection = mdb_connector.get_collection("wafer_defects")

            # Generate a unique wafer ID
            wafer_count = wafer_collection.count_documents({})
            wafer_id = f"W_TEST_{wafer_count + 1:04d}"

            # Create test wafer with high severity but no excursion link
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
            result = wafer_collection.insert_one(test_wafer)

            logger.info(f"Test wafer injected: {wafer_id} with {test_wafer['defect_summary']['yield_percentage']:.1f}% yield")

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

    except Exception as e:
        logger.error(f"Error injecting test wafer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/wafers/{wafer_id}/visualization")
async def get_wafer_visualization(wafer_id: str):
    """
    Get wafer data formatted for visualization in frontend.
    Returns die_map and defect data for rendering wafer maps.

    MongoDB Features: Document queries for complex nested data
    """
    try:
        with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector:
            wafer_collection = mdb_connector.get_collection("wafer_defects")

            # Query wafer from MongoDB
            wafer = wafer_collection.find_one({"wafer_id": wafer_id})

            if not wafer:
                raise HTTPException(status_code=404, detail=f"Wafer {wafer_id} not found")

            # Convert ObjectId to string if present
            if "_id" in wafer:
                wafer["_id"] = str(wafer["_id"])

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
        raise
    except Exception as e:
        logger.error(f"Error fetching wafer visualization: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/wafers/visualization/batch")
async def get_batch_wafer_visualization(
    request: Dict[str, List[str]]  # Expects {"wafer_ids": ["W_001", "W_002", ...]}
):
    """
    Get visualization data for multiple wafers.
    Useful for comparative analysis and batch visualization.

    MongoDB Features: Bulk queries with $in operator
    """
    try:
        wafer_ids = request.get("wafer_ids", [])

        if not wafer_ids:
            raise HTTPException(status_code=400, detail="No wafer IDs provided")

        if len(wafer_ids) > 50:  # Limit batch size
            raise HTTPException(status_code=400, detail="Maximum 50 wafers per batch request")

        with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector:
            wafer_collection = mdb_connector.get_collection("wafer_defects")

            # Query multiple wafers at once
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

            # Check for missing wafers
            missing_ids = list(set(wafer_ids) - set(found_ids))

            return {
                "wafers": results,
                "count": len(results),
                "requested": len(wafer_ids),
                "missing_wafers": missing_ids if missing_ids else None
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching batch wafer visualization: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/equipment/status")
async def get_equipment_status():
    """
    Get equipment fleet status matrix - OPTIMIZED
    Uses alerts collection as single source of truth for excursions
    """
    try:
        # Use async MongoDB client
        db = mongodb_client[MDB_DATABASE_NAME]
        sensor_collection = db[MDB_TIMESERIES_COLLECTION]
        alerts_collection = db["alerts"]

        # Get latest reading per equipment (without status calculation)
        pipeline = [
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

        # Execute aggregation asynchronously with allowDiskUse for large datasets
        cursor = sensor_collection.aggregate(pipeline, allowDiskUse=True)
        equipment_list = await cursor.to_list(length=None)

        # Get all open alerts for equipment
        open_alerts = await alerts_collection.find({
            "status": {"$in": ["open", "acknowledged"]},
            "equipment_id": {"$exists": True}
        }).to_list(length=None)

        # Create a map of equipment_id to highest severity alert
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

        # Sort equipment within each process group
        for process in equipment_matrix:
            equipment_matrix[process].sort(key=lambda x: x["equipment_id"])

        return {
            "matrix": equipment_matrix,
            "total_equipment": len(equipment_list),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error fetching equipment status: {e}")
        # Return cached/default data on error for better UX
        return {
            "matrix": {},
            "total_equipment": 0,
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


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
    # Connect with WebSocket manager
    client_id = await ws_manager.connect(
        websocket=websocket,
        connection_type=ConnectionType.ALERTS
    )

    try:
        while True:
            # Keep connection alive and wait for messages
            data = await websocket.receive_text()

            # Handle client messages (subscriptions, filters, etc.)
            await ws_manager.handle_client_message(client_id, data)

    except WebSocketDisconnect:
        await ws_manager.disconnect(client_id)
        logger.info(f"Alert WebSocket client {client_id} disconnected")
    except Exception as e:
        logger.error(f"Alert WebSocket error for {client_id}: {e}")
        await ws_manager.disconnect(client_id)


@app.websocket("/ws/sensors")
async def websocket_sensors(websocket: WebSocket):
    """
    WebSocket endpoint for real-time sensor data streaming
    """
    # Connect with WebSocket manager
    client_id = await ws_manager.connect(
        websocket=websocket,
        connection_type=ConnectionType.SENSORS
    )

    try:
        with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector:
            sensor_collection = mdb_connector.get_collection("sensor_events")  # Use real-time collection
            last_update_time = datetime.utcnow()

            while True:
                # Use wait_for to handle both incoming messages and periodic updates
                try:
                    # Try to receive a message with a 2-second timeout
                    data = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=2.0
                    )

                    # Handle client messages (subscriptions, filters, etc.)
                    await ws_manager.handle_client_message(client_id, data)

                except asyncio.TimeoutError:
                    # No message received, check if it's time to send sensor update
                    current_time = datetime.utcnow()
                    time_since_update = (current_time - last_update_time).total_seconds()

                    if time_since_update >= 2.0:  # Send update every 2 seconds
                        try:
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

                            if sensors:
                                # Send update to client
                                success = await ws_manager.send_json_to_client(
                                    client_id,
                                    {
                                        "type": "sensor_update",
                                        "timestamp": datetime.now(timezone.utc).isoformat(),
                                        "data": sensors
                                    }
                                )

                                # If send failed, connection is likely dead
                                if not success:
                                    logger.warning(f"Failed to send sensor update to {client_id}")
                                    break

                            last_update_time = current_time

                        except Exception as e:
                            logger.error(f"Error sending sensor update: {e}")

    except WebSocketDisconnect:
        await ws_manager.disconnect(client_id)
        logger.info(f"Sensor WebSocket client {client_id} disconnected")
    except Exception as e:
        logger.error(f"Sensor WebSocket error for {client_id}: {e}")
        await ws_manager.disconnect(client_id)


@app.websocket("/ws/wafers")
async def websocket_wafers(websocket: WebSocket):
    """
    WebSocket endpoint for real-time wafer updates
    """
    manager = get_websocket_manager()
    client_id = await manager.connect(
        websocket,
        connection_type=ConnectionType.WAFERS
    )

    try:
        with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector:
            wafer_collection = mdb_connector.get_collection("wafer_defects")
            last_update_time = datetime.utcnow()

            while True:
                # Use wait_for to handle both incoming messages and periodic updates
                try:
                    # Try to receive a message with a 5-second timeout
                    data = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=5.0
                    )

                    # Handle client messages (subscriptions, filters, etc.)
                    await manager.handle_client_message(client_id, data)

                except asyncio.TimeoutError:
                    # No message received, check if it's time to send wafer update
                    current_time = datetime.utcnow()
                    time_since_update = (current_time - last_update_time).total_seconds()

                    if time_since_update >= 5.0:  # Send update every 5 seconds
                        try:
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

                                # Send to client using manager
                                success = await manager.send_to_client(client_id, {
                                    "type": "wafer_update",
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "wafer": latest_wafer
                                })

                                # If send failed, connection is likely dead
                                if not success:
                                    logger.warning(f"Failed to send wafer update to {client_id}")
                                    break

                            last_update_time = current_time

                        except Exception as e:
                            logger.error(f"Error sending wafer update: {e}")

    except WebSocketDisconnect:
        logger.info(f"Wafer WebSocket client {client_id} disconnected")
        await manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"Wafer WebSocket error for {client_id}: {e}")
        await manager.disconnect(client_id)


async def run_alert_correlation(alert_id: str):
    """Run correlation analysis in background"""
    try:
        alert = alert_manager.get_alert_by_id(alert_id)
        if not alert:
            return

        # Use existing CorrelationEngine - pass the MongoDB _id as string
        correlation_engine = CorrelationEngine(MDB_URI)
        # Convert ObjectId to string for the analyze_alert method
        mongo_id = str(alert["_id"]) if "_id" in alert else alert_id
        correlations = await correlation_engine.analyze_alert(mongo_id)

        # NOTE: CorrelationEngine already stores results in 'correlation_analysis' field
        # No need to duplicate in 'correlation_data' field

        # Notify via WebSocket
        await notify_websocket_clients({
            "type": "correlation_complete",
            "alert_id": alert_id,
            "correlations": correlations
        })

        logger.info(f"✅ Correlation analysis completed for alert {alert_id}")
    except Exception as e:
        logger.error(f"Correlation failed for {alert_id}: {e}")


async def run_alert_rca(alert_id: str, severity: AlertSeverity):
    """Run RCA for critical alerts"""
    if severity != AlertSeverity.CRITICAL:
        return

    try:
        alert = alert_manager.get_alert_by_id(alert_id)
        if not alert:
            return

        # Use existing RCAGenerator - pass the MongoDB _id as string
        rca_gen = RCAGenerator(MDB_URI)
        # Convert ObjectId to string for the generate_rca_hints method
        mongo_id = str(alert["_id"]) if "_id" in alert else alert_id
        rca_results = await rca_gen.generate_rca_hints(mongo_id)

        # NOTE: RCAGenerator already stores results in 'rca_hints' field
        # No need to duplicate in 'rca_recommendations' field

        # Notify via WebSocket
        await notify_websocket_clients({
            "type": "rca_complete",
            "alert_id": alert_id,
            "rca": rca_results
        })

        logger.info(f"🔍 RCA analysis completed for critical alert {alert_id}")
    except Exception as e:
        logger.error(f"RCA failed for {alert_id}: {e}")


async def generate_delayed_wafer_defect(excursion_data: Dict[str, Any], delay_seconds: int = 10):
    """
    Generate wafer defect after delay to simulate inspection time

    Args:
        excursion_data: Dictionary containing excursion details
        delay_seconds: Delay in seconds (10 for demo, 7200 for realistic)
    """
    try:
        # Wait to simulate inspection delay
        logger.info(f"Scheduling wafer generation for alert {excursion_data.get('alert_id')} in {delay_seconds} seconds")
        await asyncio.sleep(delay_seconds)

        # Initialize wafer generator
        s3_bucket_uri = os.getenv("S3_BUCKET_URI")
        wafer_generator = WaferGenerator(
            mongodb_uri=MDB_URI,
            database=MDB_DATABASE_NAME,
            s3_bucket_uri=s3_bucket_uri
        )

        # Generate wafer based on excursion type
        wafer_record = await wafer_generator.generate_excursion_wafer(excursion_data)

        # Save to MongoDB
        wafer_id = wafer_generator.save_wafer(wafer_record)

        logger.info(f"✅ Generated wafer {wafer_record['wafer_id']} with {wafer_record['defect_summary']['defect_pattern']} "
                   f"pattern ({wafer_record['defect_summary']['yield_percentage']:.1f}% yield) for alert {excursion_data.get('alert_id')}")

        # Notify WebSocket clients about new wafer
        await notify_websocket_clients({
            "type": "new_wafer_defect",
            "wafer_id": wafer_record['wafer_id'],
            "lot_id": wafer_record['lot_id'],
            "pattern": wafer_record['defect_summary']['defect_pattern'],
            "yield_percentage": wafer_record['defect_summary']['yield_percentage'],
            "severity": wafer_record['defect_summary']['severity'],
            "linked_alert_id": excursion_data.get('alert_id'),
            "equipment_id": excursion_data.get('equipment_id'),
            "timestamp": wafer_record['inspection_timestamp']
        })

        # Clean up
        wafer_generator.cleanup()

    except Exception as e:
        logger.error(f"Error generating wafer defect for alert {excursion_data.get('alert_id')}: {e}")


async def run_monitoring_loop():
    """
    Background task for continuous monitoring using MongoDB change streams
    """
    global monitoring_active

    logger.info("Starting real-time monitoring loop with change streams")

    try:
        # Get async MongoDB connection
        async_client = AsyncIOMotorClient(MDB_URI)
        async_db = async_client[MDB_DATABASE_NAME]
        sensor_events_collection = async_db["sensor_events"]

        # Define change stream pipeline to watch for inserts
        pipeline = [
            {"$match": {"operationType": "insert"}}
        ]

        # Start watching the sensor_events collection
        async with sensor_events_collection.watch(pipeline) as stream:
            logger.info("✅ Change stream connected - monitoring sensor_events collection")

            while monitoring_active:
                try:
                    # Wait for the next change event
                    async for change in stream:
                        if not monitoring_active:
                            break

                        # Get the new sensor data
                        sensor_data = change.get("fullDocument")
                        if not sensor_data:
                            continue

                        logger.debug(f"New sensor data from {sensor_data.get('equipment_id')}")

                        # Check for excursions (thresholds)
                        excursion_detected = False
                        excursion_type = None
                        excursion_value = None

                        metrics = sensor_data.get("metrics", {})

                        # Check particle count threshold
                        particle_count = metrics.get("particle_count", 0)
                        if particle_count > 1000:
                            excursion_detected = True
                            excursion_type = "particle_excursion"
                            excursion_value = particle_count
                            logger.warning(f"⚠️ Particle excursion detected: {particle_count} on {sensor_data.get('equipment_id')}")

                        # Check RF power drift
                        rf_power = metrics.get("rf_power", 0)
                        equipment_id = sensor_data.get("equipment_id", "")
                        if "CMP" in equipment_id and abs(rf_power - 1450) > 100:  # CMP baseline is 1450W, threshold >100W
                            excursion_detected = True
                            excursion_type = "rf_power_drift"
                            excursion_value = rf_power
                            logger.warning(f"⚠️ RF power drift detected: {rf_power}W on {equipment_id}")
                        elif "ETCH" in equipment_id and abs(rf_power - 1200) > 100:  # ETCH baseline is 1200W, threshold >100W
                            excursion_detected = True
                            excursion_type = "rf_power_drift"
                            excursion_value = rf_power
                            logger.warning(f"⚠️ RF power drift detected: {rf_power}W on {equipment_id}")
                        elif "LITHO" in equipment_id and abs(rf_power - 800) > 100:  # LITHO baseline is 800W, threshold >100W
                            excursion_detected = True
                            excursion_type = "rf_power_drift"
                            excursion_value = rf_power
                            logger.warning(f"⚠️ RF power drift detected: {rf_power}W on {equipment_id}")

                        # Check temperature drift
                        temperature = metrics.get("temperature", 0)
                        if "CMP" in equipment_id and abs(temperature - 65) > 5:
                            excursion_detected = True
                            excursion_type = "temperature_drift"
                            excursion_value = temperature
                            logger.warning(f"⚠️ Temperature drift detected: {temperature}°C on {equipment_id}")

                        # Create alert if excursion detected
                        if excursion_detected and alert_manager:
                            # Prepare excursion data
                            excursion = {
                                "equipment_id": sensor_data.get("equipment_id"),
                                "timestamp": sensor_data.get("timestamp"),
                                "excursion_type": excursion_type,
                                "value": excursion_value,
                                "metrics": metrics,
                                "metadata": sensor_data.get("metadata", {}),
                                "description": f"{excursion_type.replace('_', ' ').title()}: {excursion_value}"
                            }

                            # Determine severity based on excursion type and value
                            severity = determine_severity(excursion)

                            # === AI MULTI-AGENT FILTERING (if enabled) ===
                            should_create_alert = True
                            monitoring_decision = None

                            if USE_AI_AGENTS:
                                try:
                                    logger.info(f"🤖 Running AI Monitoring Agent for {equipment_id}")

                                    # Create initial state for monitoring agent
                                    temp_alert_id = str(ObjectId())
                                    agent_state = create_initial_state(
                                        alert_id=temp_alert_id,
                                        equipment_id=equipment_id,
                                        excursion_type=excursion_type,
                                        severity=severity.value,
                                        metrics=metrics,
                                        metadata=sensor_data.get("metadata", {})
                                    )

                                    # Run monitoring agent (filters false positives)
                                    agent_result = await monitoring_agent_tool(agent_state)
                                    monitoring_decision = agent_result.get("monitoring_decision", {})

                                    # Check agent's decision
                                    should_create_alert = monitoring_decision.get("create_alert", True)

                                    if not should_create_alert:
                                        logger.info(f"🚫 Alert FILTERED by AI Agent: {monitoring_decision.get('reasoning')}")
                                        logger.info(f"   Confidence: {monitoring_decision.get('confidence'):.2f}, Pattern: {monitoring_decision.get('pattern_detected')}")
                                    else:
                                        logger.info(f"✅ Alert APPROVED by AI Agent: {monitoring_decision.get('reasoning')}")
                                        logger.info(f"   Confidence: {monitoring_decision.get('confidence'):.2f}, Pattern: {monitoring_decision.get('pattern_detected')}")

                                except Exception as agent_error:
                                    logger.error(f"⚠️ AI Agent error (fail-safe: creating alert): {agent_error}")
                                    should_create_alert = True  # Fail-safe: create alert on error

                            # Create alert only if not filtered
                            if not should_create_alert:
                                # Log filtered alert but don't create it
                                logger.info(f"📊 Excursion detected but FILTERED: {excursion_type} on {equipment_id}")
                                continue

                            # Create alert
                            alert_id = alert_manager.create_alert(
                                alert_type=AlertType.EXCURSION,
                                severity=severity,
                                title=f"{excursion_type.replace('_', ' ').title()} on {equipment_id}",
                                description=excursion["description"],
                                source_data=excursion,
                                equipment_id=equipment_id,
                                lot_id=sensor_data.get("metadata", {}).get("lot_id"),
                                wafer_id=sensor_data.get("metadata", {}).get("wafer_id")
                            )

                            logger.info(f"🚨 Alert created: {alert_id} for {excursion_type} on {equipment_id}")

                            # === RUN INVESTIGATION AGENT (if AI enabled) ===
                            if USE_AI_AGENTS and should_create_alert:
                                try:
                                    # Small delay to ensure alert is committed to MongoDB
                                    await asyncio.sleep(0.1)

                                    logger.info(f"🔬 Running Investigation Agent for alert {alert_id}")

                                    # Get the alert to extract MongoDB _id (same approach as run_alert_correlation)
                                    alert_doc = alert_manager.get_alert_by_id(alert_id)
                                    if not alert_doc:
                                        logger.error(f"   ❌ Alert {alert_id} not found in DB after creation")
                                        raise ValueError(f"Alert {alert_id} not found")

                                    # Extract MongoDB _id (the actual ObjectId used by CorrelationEngine)
                                    mongo_id = str(alert_doc["_id"]) if "_id" in alert_doc else alert_id
                                    logger.info(f"   🔑 Using MongoDB _id: {mongo_id} (from alert {alert_id})")

                                    # Update state with MongoDB _id for correlation engine
                                    agent_state['alert_id'] = mongo_id

                                    # Run investigation agent
                                    investigation_result = await investigation_agent_tool(agent_state)

                                    # Log investigation results
                                    key_findings = investigation_result.get('key_findings', [])
                                    logger.info(f"   ✅ Investigation complete: {len(key_findings)} key findings")

                                    # Update alert with investigation results in MongoDB
                                    if key_findings:
                                        alert_manager.alerts_collection.update_one(
                                            {"_id": ObjectId(mongo_id)},  # Use mongo_id, not alert_id!
                                            {"$set": {
                                                "ai_investigation": {
                                                    "key_findings": key_findings,
                                                    "summary": investigation_result.get('investigation_summary'),
                                                    "correlation_confidence": investigation_result.get('correlation_results', {}).get('confidence_score', 0),
                                                    "affected_wafers": investigation_result.get('correlation_results', {}).get('affected_wafers', {}).get('total', 0)
                                                }
                                            }}
                                        )
                                        logger.info(f"   💾 Investigation results saved to alert {alert_id} (MongoDB _id: {mongo_id})")

                                    # === RUN RCA AGENT (nested in investigation success) ===
                                    try:
                                        logger.info(f"🔍 Running RCA Agent for alert {alert_id}")

                                        # Update state with investigation results for RCA context
                                        agent_state['investigation_summary'] = investigation_result.get('investigation_summary', '')
                                        agent_state['key_findings'] = investigation_result.get('key_findings', [])
                                        agent_state['correlation_results'] = investigation_result.get('correlation_results', {})

                                        # Run RCA agent
                                        rca_result = await rca_agent_tool(agent_state)

                                        # Log RCA results
                                        validated_causes = rca_result.get('validated_causes', [])
                                        logger.info(f"   ✅ RCA complete: {len(validated_causes)} validated root causes")

                                        # Update alert with RCA results in MongoDB
                                        if validated_causes:
                                            alert_manager.alerts_collection.update_one(
                                                {"_id": ObjectId(mongo_id)},
                                                {"$set": {
                                                    "ai_rca": {
                                                        "validated_causes": validated_causes,
                                                        "validation": rca_result.get('rca_validation'),
                                                        "recommendations": rca_result.get('rca_patterns', {}).get('recommendations', []),
                                                        "confidence": rca_result.get('rca_patterns', {}).get('overall_confidence', 0)
                                                    }
                                                }}
                                            )
                                            logger.info(f"   💾 RCA results saved to alert {alert_id} (MongoDB _id: {mongo_id})")

                                        # === RUN SUPERVISOR SYNTHESIS (aggregates all agent outputs) ===
                                        try:
                                            logger.info(f"🎯 Running Supervisor Synthesis for alert {alert_id}")

                                            # Aggregate all agent results
                                            supervisor_result = await supervisor_synthesis_agent(
                                                monitoring_result=agent_result,
                                                investigation_result=investigation_result,
                                                rca_result=rca_result,
                                                alert_context={
                                                    'equipment_id': equipment_id,
                                                    'excursion_type': excursion_type,
                                                    'alert_id': alert_id
                                                }
                                            )

                                            # Log supervisor results
                                            risk_level = supervisor_result.get('risk_level', 'Unknown')
                                            overall_confidence = supervisor_result.get('overall_confidence', 0)
                                            logger.info(f"   ✅ Supervisor synthesis complete")
                                            logger.info(f"   🎯 Risk Level: {risk_level}, Overall Confidence: {overall_confidence:.0%}")

                                            # Update alert with supervisor synthesis
                                            supervisor_synthesis = supervisor_result.get('supervisor_synthesis', '')
                                            if supervisor_synthesis:
                                                alert_manager.alerts_collection.update_one(
                                                    {"_id": ObjectId(mongo_id)},
                                                    {"$set": {
                                                        "ai_supervisor": {
                                                            "synthesis": supervisor_synthesis,
                                                            "risk_level": risk_level,
                                                            "overall_confidence": overall_confidence,
                                                            "agent_summary": supervisor_result.get('agent_outputs', {})
                                                        }
                                                    }}
                                                )
                                                logger.info(f"   💾 Supervisor synthesis saved to alert {alert_id} (MongoDB _id: {mongo_id})")

                                        except Exception as supervisor_error:
                                            logger.error(f"⚠️ Supervisor Synthesis error: {supervisor_error}")

                                    except Exception as rca_error:
                                        logger.error(f"⚠️ RCA Agent error: {rca_error}")

                                except Exception as investigation_error:
                                    logger.error(f"⚠️ Investigation Agent error: {investigation_error}")

                            # Notify WebSocket clients
                            await notify_websocket_clients({
                                "type": "new_alert",
                                "alert_id": alert_id,
                                "severity": severity.value,
                                "equipment_id": equipment_id,
                                "excursion_type": excursion_type,
                                "value": excursion_value,
                                "timestamp": sensor_data.get("timestamp").isoformat() if hasattr(sensor_data.get("timestamp"), 'isoformat') else str(sensor_data.get("timestamp"))
                            })

                            # Trigger correlation analysis for all alerts (skip if AI agents enabled)
                            if not USE_AI_AGENTS:
                                asyncio.create_task(run_alert_correlation(alert_id))

                            # Trigger RCA for critical alerts only (skip if AI agents enabled)
                            if not USE_AI_AGENTS:
                                asyncio.create_task(run_alert_rca(alert_id, severity))

                            # Schedule wafer defect generation (with delay to simulate inspection)
                            asyncio.create_task(generate_delayed_wafer_defect({
                                'alert_id': alert_id,
                                'equipment_id': equipment_id,
                                'excursion_type': excursion_type,
                                'severity': severity.value,
                                'timestamp': sensor_data.get('timestamp'),
                                'metrics': metrics,
                                'metadata': sensor_data.get('metadata', {})  # Pass metadata for process context!
                            }, delay_seconds=10))  # 10 seconds for demo, can be 7200 for realistic

                        # Also check if this is just a normal update to broadcast
                        elif not excursion_detected:
                            # Broadcast normal sensor update to WebSocket clients
                            await notify_websocket_clients({
                                "type": "sensor_update",
                                "equipment_id": sensor_data.get("equipment_id"),
                                "metrics": metrics,
                                "timestamp": sensor_data.get("timestamp").isoformat() if hasattr(sensor_data.get("timestamp"), 'isoformat') else str(sensor_data.get("timestamp"))
                            })

                except asyncio.CancelledError:
                    logger.info("Monitoring loop cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error processing change stream event: {e}")
                    # Continue monitoring despite errors
                    continue

    except Exception as e:
        logger.error(f"Failed to establish change stream: {e}")
        logger.info("Falling back to polling mode...")

        # Fallback to polling if change streams fail
        while monitoring_active:
            try:
                # Simple polling logic as backup
                await asyncio.sleep(30)
                logger.debug("Polling mode check (change streams unavailable)")

            except Exception as poll_error:
                logger.error(f"Error in polling mode: {poll_error}")
                await asyncio.sleep(60)

    finally:
        if 'async_client' in locals():
            async_client.close()
        logger.info("Monitoring loop stopped")


async def run_wafer_monitoring_loop():
    """
    Background task for monitoring new wafer defects and generating alerts
    Watches for high-severity wafers that aren't already linked to excursion alerts
    """
    global monitoring_active

    logger.info("Starting wafer defect monitoring loop with change streams")

    try:
        # Get async MongoDB connection
        async_client = AsyncIOMotorClient(MDB_URI)
        async_db = async_client[MDB_DATABASE_NAME]
        wafer_defects_collection = async_db["wafer_defects"]

        # Define change stream pipeline to watch for inserts
        pipeline = [
            {"$match": {"operationType": "insert"}}
        ]

        # Start watching the wafer_defects collection
        async with wafer_defects_collection.watch(pipeline) as stream:
            logger.info("✅ Change stream connected - monitoring wafer_defects collection")

            while monitoring_active:
                try:
                    # Wait for the next change event
                    async for change in stream:
                        if not monitoring_active:
                            break

                        # Get the new wafer data
                        wafer_data = change.get("fullDocument")
                        if not wafer_data:
                            continue

                        wafer_id = wafer_data.get("wafer_id")
                        logger.debug(f"New wafer detected: {wafer_id}")

                        # Check if this wafer is already linked to an excursion alert
                        process_context = wafer_data.get("process_context", {})
                        if "excursion_alert_id" in process_context:
                            logger.debug(f"Wafer {wafer_id} already linked to alert {process_context['excursion_alert_id']}, skipping")
                            continue

                        # Get defect summary
                        defect_summary = wafer_data.get("defect_summary", {})
                        severity = defect_summary.get("severity", "low")
                        yield_pct = defect_summary.get("yield_percentage", 100)
                        defect_pattern = defect_summary.get("defect_pattern", "random")

                        # Only create alerts for high-severity wafers
                        if severity != "high":
                            logger.debug(f"Wafer {wafer_id} severity is {severity}, not creating alert")
                            continue

                        # Determine alert type based on defect characteristics
                        if defect_pattern in ["clustered", "systematic"]:
                            alert_type = AlertType.DEFECT_CLUSTER
                            title = f"Defect Cluster Detected on {wafer_id}"
                            description = f"{defect_pattern.title()} defect pattern detected with {yield_pct:.1f}% yield"
                        elif yield_pct < 85:
                            alert_type = AlertType.YIELD_DROP
                            title = f"Severe Yield Drop on {wafer_id}"
                            description = f"Yield dropped to {yield_pct:.1f}% on wafer {wafer_id}"
                        else:
                            alert_type = AlertType.DEFECT_CLUSTER
                            title = f"High Severity Defects on {wafer_id}"
                            description = wafer_data.get("description", f"High severity {defect_pattern} defects detected")

                        # Determine alert severity based on yield
                        if yield_pct < 70:
                            alert_severity = AlertSeverity.CRITICAL
                        elif yield_pct < 85:
                            alert_severity = AlertSeverity.HIGH
                        else:
                            alert_severity = AlertSeverity.MEDIUM

                        # Create alert using AlertManager
                        if alert_manager:
                            alert_id = alert_manager.create_alert(
                                alert_type=alert_type,
                                severity=alert_severity,
                                title=title,
                                description=description,
                                source_data={
                                    "wafer_id": wafer_id,
                                    "lot_id": wafer_data.get("lot_id"),
                                    "defect_summary": defect_summary,
                                    "inspection_timestamp": wafer_data.get("inspection_timestamp"),
                                    "process_context": process_context,
                                    "defects": wafer_data.get("defects", [])[:5]  # Include first 5 defects
                                },
                                equipment_id=process_context.get("equipment_used", [None])[0] if process_context.get("equipment_used") else None,
                                lot_id=wafer_data.get("lot_id"),
                                wafer_id=wafer_id
                            )

                            logger.info(f"🚨 Wafer alert created: {alert_id} for {wafer_id} ({defect_pattern}, {yield_pct:.1f}% yield)")

                            # Notify WebSocket clients
                            await notify_websocket_clients({
                                "type": "wafer_alert",
                                "alert_id": alert_id,
                                "wafer_id": wafer_id,
                                "severity": alert_severity.value,
                                "yield_percentage": yield_pct,
                                "defect_pattern": defect_pattern,
                                "timestamp": wafer_data.get("inspection_timestamp")
                            })

                            # Trigger correlation analysis for wafer alerts too (skip if AI agents enabled)
                            if not USE_AI_AGENTS:
                                asyncio.create_task(run_alert_correlation(alert_id))

                            # Trigger RCA for critical wafer alerts (skip if AI agents enabled)
                            if not USE_AI_AGENTS and alert_severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH]:
                                asyncio.create_task(run_alert_rca(alert_id, alert_severity))

                except asyncio.CancelledError:
                    logger.info("Wafer monitoring loop cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error processing wafer change stream event: {e}")
                    # Continue monitoring despite errors
                    continue

    except Exception as e:
        logger.error(f"Failed to establish wafer change stream: {e}")
        logger.info("Wafer monitoring fallback not implemented - requires change streams")

    finally:
        if 'async_client' in locals():
            async_client.close()
        logger.info("Wafer monitoring loop stopped")


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
    manager = get_websocket_manager()
    
    # Convert ObjectIds before sending
    message_converted = convert_objectids(message)
    
    # Determine connection type based on message content
    connection_type = None
    if "alert" in message.get("type", "").lower():
        connection_type = ConnectionType.ALERTS
    elif "sensor" in message.get("type", "").lower():
        connection_type = ConnectionType.SENSORS
    elif "wafer" in message.get("type", "").lower():
        connection_type = ConnectionType.WAFERS
    
    # Broadcast message
    sent_count = await manager.broadcast(
        message_converted,
        connection_type=connection_type
    )
    
    if sent_count > 0:
        logger.info(f"Notified {sent_count} WebSocket clients")
    else:
        logger.debug("No WebSocket clients to notify")


# =============================================
# Phase 3: Semantic Search API Endpoints
# =============================================

from services.semantic_search import SemanticSearchService
from services.embedding_service import EmbeddingService

# Initialize semantic search service
semantic_search_service = None
embedding_service = None

async def initialize_phase3_services():
    """Initialize Phase 3 services"""
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
    manager = get_websocket_manager()
    client_id = await manager.connect(
        websocket,
        connection_type=ConnectionType.AGENT,
        metadata={"session_id": session_id}
    )
    
    try:
        from agent_sessions import AgentSessionManager
        import asyncio
        
        session_manager = AgentSessionManager()
        
        while True:
            # Get session updates
            session = await session_manager.get_session(session_id)
            
            if session:
                # Send current state
                await manager.send_to_client(client_id, {
                    "type": "update",
                    "session_id": session_id,
                    "status": session.get("status"),
                    "updates": session.get("updates", [])
                })
                
                # Check if session is complete
                if session.get("status") in ["completed", "failed"]:
                    await manager.send_to_client(client_id, {
                        "type": "complete",
                        "session_id": session_id,
                        "result": session.get("result")
                    })
                    break
            
            await asyncio.sleep(1)  # Poll every second
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}, client {client_id}")
        await manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        await manager.disconnect(client_id)


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


# ============================================================================
# Demo Mode Endpoints
# ============================================================================

async def reset_demo_collections():
    """
    Reset process_sensor_ts with fresh demo data

    Creates:
    1. Baseline normal readings (last 1 hour) for statistical context
    2. Anomalous patterns for AI agent testing

    NO vector embeddings - too slow for demo (6-9 second overhead)
    """
    try:
        logger.info("🔄 Resetting demo collections...")

        # Get MongoDB connection
        async_client = AsyncIOMotorClient(MDB_URI)
        async_db = async_client[MDB_DATABASE_NAME]

        # ========== STEP 1: CLEAR OLD DATA ==========
        # Delete demo data (keep production data if timestamp < 1 hour ago)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)

        # Clear recent data from process_sensor_ts
        delete_result = await async_db.process_sensor_ts.delete_many({
            "timestamp": {"$gte": cutoff_time}
        })
        logger.info(f"Cleared {delete_result.deleted_count} recent records from process_sensor_ts")

        # ========== STEP 2: SEED BASELINE DATA (Last 1 Hour) ==========
        logger.info("Seeding baseline normal readings for statistical context...")

        equipment_ids = ["CMP_TOOL_01", "CMP_TOOL_02", "ETCH_01", "ETCH_02", "LITHO_01", "LITHO_02"]
        baseline_data = []

        # Generate 60 normal readings per equipment (1 per minute for last hour)
        for minutes_ago in range(60, 0, -1):
            timestamp = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)

            for equipment_id in equipment_ids:
                data = {
                    "equipment_id": equipment_id,
                    "process_step": equipment_id.split("_")[0],
                    "timestamp": timestamp,
                    "metrics": generate_demo_metrics(equipment_id, is_excursion=False),
                    "metadata": generate_demo_metadata(is_excursion=False)
                }
                baseline_data.append(data)

        # Bulk insert baseline data ONLY to process_sensor_ts (no alerts!)
        if baseline_data:
            # Write ONLY to process_sensor_ts to avoid triggering change stream alerts
            result = await async_db.process_sensor_ts.insert_many(baseline_data)
            logger.info(f"Seeded {len(result.inserted_ids)} baseline readings to process_sensor_ts only (no alerts)")

        # ========== STEP 3: SEED ANOMALOUS PATTERNS (Last 10 Minutes) ==========
        logger.info("Seeding anomalous patterns for AI agent testing...")

        anomaly_data = []

        # Create 3 different anomaly types for testing
        anomaly_scenarios = [
            {
                "equipment_id": "CMP_TOOL_01",
                "pattern": "drift",
                "minutes_ago": 10,
                "stages": 5,
                "baseline": 450,
                "target": 1500
            },
            {
                "equipment_id": "ETCH_01",
                "pattern": "spike",
                "minutes_ago": 8,
                "stages": 3,
                "value": 2000
            },
            {
                "equipment_id": "LITHO_01",
                "pattern": "false_positive",
                "minutes_ago": 5,
                "value": 1100
            }
        ]

        for scenario in anomaly_scenarios:
            eq_id = scenario["equipment_id"]

            if scenario["pattern"] == "drift":
                # Gradual increase
                for stage in range(scenario["stages"]):
                    timestamp = datetime.now(timezone.utc) - timedelta(
                        minutes=scenario["minutes_ago"] - stage
                    )

                    particle_count = scenario["baseline"] + (
                        (scenario["target"] - scenario["baseline"]) * (stage / scenario["stages"])
                    )

                    metrics = generate_demo_metrics(eq_id, is_excursion=False)
                    metrics["particle_count"] = int(particle_count)

                    anomaly_data.append({
                        "equipment_id": eq_id,
                        "process_step": eq_id.split("_")[0],
                        "timestamp": timestamp,
                        "metrics": metrics,
                        "metadata": generate_demo_metadata(is_excursion=True)
                    })

            elif scenario["pattern"] == "spike":
                # Sustained spike
                for stage in range(scenario["stages"]):
                    timestamp = datetime.now(timezone.utc) - timedelta(
                        minutes=scenario["minutes_ago"] - stage
                    )

                    metrics = generate_demo_metrics(eq_id, is_excursion=False)
                    metrics["particle_count"] = scenario["value"] + random.randint(-50, 50)

                    anomaly_data.append({
                        "equipment_id": eq_id,
                        "process_step": eq_id.split("_")[0],
                        "timestamp": timestamp,
                        "metrics": metrics,
                        "metadata": generate_demo_metadata(is_excursion=True)
                    })

            elif scenario["pattern"] == "false_positive":
                # Single spike then normal
                for stage in range(2):
                    timestamp = datetime.now(timezone.utc) - timedelta(
                        minutes=scenario["minutes_ago"] - stage
                    )

                    metrics = generate_demo_metrics(eq_id, is_excursion=False)
                    if stage == 0:
                        metrics["particle_count"] = scenario["value"]
                    # stage 1 returns to normal (already normal from generate_demo_metrics)

                    anomaly_data.append({
                        "equipment_id": eq_id,
                        "process_step": eq_id.split("_")[0],
                        "timestamp": timestamp,
                        "metrics": metrics,
                        "metadata": generate_demo_metadata(is_excursion=stage == 0)
                    })

        # Bulk insert anomaly data ONLY to process_sensor_ts (no alerts!)
        if anomaly_data:
            # Write ONLY to process_sensor_ts to avoid triggering change stream alerts
            result = await async_db.process_sensor_ts.insert_many(anomaly_data)
            logger.info(f"Seeded {len(result.inserted_ids)} anomalous readings to process_sensor_ts only (no alerts)")

        async_client.close()

        logger.info("✅ Demo collections reset complete!")

        return {
            "baseline_readings": len(baseline_data),
            "anomalous_readings": len(anomaly_data)
        }

    except Exception as e:
        logger.error(f"Failed to reset demo collections: {e}")
        raise


@app.post("/demo/start")
async def start_demo_mode():
    """Start demo mode data generation"""
    global demo_mode_active, demo_task

    if demo_mode_active:
        return {
            "status": "already_running",
            "message": "Demo mode is already active",
            "interval_seconds": DEMO_INTERVAL_SECONDS,
            "excursion_probability": DEMO_EXCURSION_PROBABILITY
        }

    try:
        # ========== LOAD REAL PROCESS CONTEXT IDs ==========
        await load_process_context_ids()
        # ===================================================

        # ========== RESET & SEED COLLECTIONS ==========
        reset_stats = await reset_demo_collections()
        logger.info(f"Collections reset: {reset_stats}")
        # ==============================================

        # Initialize pattern state for realistic anomaly scenarios
        initialize_pattern_state()

        # Set demo mode active flag
        demo_mode_active = True

        # Create and start the demo task
        demo_task = asyncio.create_task(demo_data_generator())

        logger.info("Demo mode started successfully with pattern-based anomaly generation")

        return {
            "status": "started",
            "message": "Demo mode started successfully",
            "reset_stats": reset_stats,
            "interval_seconds": DEMO_INTERVAL_SECONDS,
            "excursion_probability": DEMO_EXCURSION_PROBABILITY,
            "equipment_ids": ["CMP_TOOL_01", "CMP_TOOL_02", "ETCH_01", "ETCH_02", "LITHO_01", "LITHO_02"]
        }

    except Exception as e:
        demo_mode_active = False
        logger.error(f"Failed to start demo mode: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start demo mode: {str(e)}")


@app.post("/demo/stop")
async def stop_demo_mode():
    """Stop demo mode data generation and cleanup recent alerts"""
    global demo_mode_active, demo_task

    if not demo_mode_active:
        return {
            "status": "not_running",
            "message": "Demo mode is not active"
        }

    try:
        # Set flag to stop the generator
        demo_mode_active = False

        # Cancel the task if it exists (don't wait for it)
        if demo_task and not demo_task.done():
            demo_task.cancel()
            # Don't await - just let it cancel in background

        demo_task = None

        # Clean up alerts created in last 2 hours (demo session)
        alerts_deleted = 0
        try:
            if alert_manager:
                cutoff_time = datetime.now() - timedelta(hours=2)
                result = alert_manager.alerts_collection.delete_many({
                    "created_at": {"$gte": cutoff_time}
                })
                alerts_deleted = result.deleted_count
                logger.info(f"Cleaned up {alerts_deleted} recent demo alerts")
        except Exception as e:
            logger.error(f"Error cleaning up alerts: {e}")

        logger.info("Demo mode stopped successfully")

        return {
            "status": "stopped",
            "message": "Demo mode stopped successfully",
            "alerts_cleaned": alerts_deleted
        }

    except Exception as e:
        logger.error(f"Error stopping demo mode: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop demo mode: {str(e)}")


@app.post("/alerts/resolve-all")
async def resolve_all_alerts():
    """Resolve all unresolved alerts in the collection"""
    try:
        if not alert_manager:
            raise HTTPException(status_code=500, detail="Alert manager not initialized")

        # Update all alerts that are not resolved
        result = alert_manager.alerts_collection.update_many(
            {
                "status": {"$ne": "resolved"}
            },
            {
                "$set": {
                    "status": "resolved",
                    "resolved_at": datetime.now(),
                    "resolution": "Bulk resolved via API",
                    "updated_by": "system"
                }
            }
        )

        logger.info(f"Bulk resolved {result.modified_count} alerts")

        return {
            "success": True,
            "message": f"Successfully resolved {result.modified_count} alerts",
            "alerts_resolved": result.modified_count,
            "alerts_matched": result.matched_count
        }
    except Exception as e:
        logger.error(f"Error resolving all alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/demo/inject-excursion")
async def inject_excursion(request: Dict[str, Any] = Body(...)):
    """
    Manually inject an excursion into the sensor data

    Expected payload:
    {
        "equipment_id": "CMP_TOOL_01",  # Required
        "excursion_type": "particle",   # Optional: "particle", "rf_power", "temperature"
        "particle_count": 2500,          # Optional: Override specific metric
        "metadata": {...}                # Optional: Override metadata
    }
    """
    try:
        # Get equipment ID (required)
        equipment_id = request.get("equipment_id")
        if not equipment_id:
            raise HTTPException(status_code=400, detail="equipment_id is required")

        # Generate base metrics with excursion
        metrics = generate_demo_metrics(equipment_id, is_excursion=True)

        # Apply specific excursion type if requested
        excursion_type = request.get("excursion_type", "particle")
        if excursion_type == "particle":
            metrics["particle_count"] = request.get("particle_count", random.randint(1500, 3000))
        elif excursion_type == "rf_power":
            metrics["rf_power"] = request.get("rf_power", metrics["rf_power"] + random.uniform(100, 200))
        elif excursion_type == "temperature":
            metrics["temperature"] = request.get("temperature", metrics["temperature"] + random.uniform(3, 5))

        # Override any specific metrics provided
        for key in ["particle_count", "rf_power", "temperature", "chamber_pressure", "flow_rate"]:
            if key in request and key not in ["excursion_type", "equipment_id", "metadata"]:
                metrics[key] = request[key]

        # Generate or use provided metadata (use problematic batch for excursions)
        metadata = request.get("metadata", generate_demo_metadata(is_excursion=True))

        # If slurry_batch is provided specifically, use it
        if "slurry_batch" in request:
            metadata["slurry_batch"] = request["slurry_batch"]

        # Create the sensor data
        data = {
            "equipment_id": equipment_id,
            "process_step": equipment_id.split("_")[0],
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "metrics": metrics,
            "metadata": metadata
        }

        # Write to both collections using SensorDataWriter
        writer = SensorDataWriter(mongodb_uri=MDB_URI, database=MDB_DATABASE_NAME)
        result = writer.write_sensor_data(data)
        writer.close()

        if result["success"]:
            logger.warning(f"Manual excursion injected for {equipment_id}: particle_count={metrics['particle_count']}")

            excursion_details = []
            if metrics["particle_count"] > 1000:
                excursion_details.append(f"Particle: {metrics['particle_count']}")
            if abs(metrics["rf_power"] - 1450) > 100:
                excursion_details.append(f"RF Power: {metrics['rf_power']}")
            if abs(metrics["temperature"] - 65) > 2:
                excursion_details.append(f"Temperature: {metrics['temperature']}")

            return {
                "status": "excursion_injected",
                "message": f"Excursion injected for {equipment_id}",
                "equipment_id": equipment_id,
                "excursion_type": excursion_type,
                "excursions_triggered": excursion_details,
                "metrics": metrics,
                "metadata": metadata,
                "sensor_events_id": result.get("sensor_events"),
                "process_sensor_ts_id": result.get("process_sensor_ts"),
                "note": "Alert will be created within 3 seconds, wafer will be generated after 10 seconds"
            }
        else:
            raise HTTPException(status_code=500, detail=f"Failed to write excursion data: {result.get('errors', [])}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error injecting excursion: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to inject excursion: {str(e)}")


@app.get("/demo/status")
async def get_demo_status():
    """Get demo mode status with parallel equipment updates"""
    global demo_mode_active, demo_task

    # Simple status without database queries to avoid blocking
    task_running = demo_task is not None

    # Calculate rates for parallel equipment updates (updated to 6 equipment - 2025-01-03)
    intervals_per_minute = 60 / DEMO_INTERVAL_SECONDS
    intervals_per_hour = 3600 / DEMO_INTERVAL_SECONDS
    equipment_count = 6  # Updated from 4 to 6 to include all standardized equipment

    # Total data points (all equipment report each interval)
    total_per_minute = equipment_count * intervals_per_minute
    total_per_hour = equipment_count * intervals_per_hour
    total_per_2min = equipment_count * (120 / DEMO_INTERVAL_SECONDS)

    return {
        "active": demo_mode_active,
        "task_running": task_running,
        "interval_seconds": DEMO_INTERVAL_SECONDS,
        "excursion_probability": DEMO_EXCURSION_PROBABILITY,
        "equipment_ids": ["CMP_TOOL_01", "CMP_TOOL_02", "ETCH_01", "ETCH_02", "LITHO_01", "LITHO_02"],
        "parallel_mode": True,
        "expected_rate": {
            "per_interval": f"{equipment_count} readings (all equipment)",
            "per_minute": f"{total_per_minute:.0f} readings",
            "per_2_minutes": f"{total_per_2min:.0f} readings",
            "per_hour": f"{total_per_hour:.0f} readings",
            "excursions_per_hour": f"{total_per_hour * DEMO_EXCURSION_PROBABILITY:.0f}",
            "particle_alerts_per_hour": f"{total_per_hour * DEMO_EXCURSION_PROBABILITY * 0.7:.0f}"  # ~70% of excursions are particle
        },
        "note": "Parallel mode: All 6 standardized equipment report simultaneously each interval"
    }


@app.post("/demo/reset")
async def reset_demo_to_healthy_state():
    """
    Complete demo reset: Fix all equipment and restore healthy yield
    Stops demo mode, resolves alerts, injects healthy sensors, and generates high-yield wafers
    """
    global demo_mode_active, demo_task

    try:
        results = {
            "alerts_resolved": 0,
            "healthy_sensors_injected": 0,
            "healthy_wafers_generated": 0,
            "new_yield": None,
            "demo_stopped": False,
            "excursion_data_cleared": 0
        }

        # Step 0: Stop demo mode first to prevent new excursions
        if demo_mode_active:
            logger.info("Stopping demo mode before reset...")
            demo_mode_active = False

            # Cancel the demo task if it exists
            if demo_task and not demo_task.done():
                demo_task.cancel()
            demo_task = None

            results["demo_stopped"] = True
            logger.info("Demo mode stopped successfully")

            # Wait for monitoring service to process the stop
            # Give extra time to ensure all pending operations complete
            await asyncio.sleep(5)

        # Step 1: Resolve all open/acknowledged alerts
        if alert_manager:
            unresolved_alerts = alert_manager.alerts_collection.find({
                "status": {"$in": ["open", "acknowledged"]}
            })
            alert_ids = [str(alert["_id"]) for alert in unresolved_alerts]

            if alert_ids:
                update_result = alert_manager.alerts_collection.update_many(
                    {"status": {"$in": ["open", "acknowledged"]}},
                    {
                        "$set": {
                            "status": "resolved",
                            "resolved_at": datetime.now(),
                            "resolution": "Demo reset - all equipment restored to healthy state",
                            "updated_by": "demo_reset"
                        }
                    }
                )
                results["alerts_resolved"] = update_result.modified_count
                logger.info(f"Demo reset: Resolved {results['alerts_resolved']} alerts")

        # Step 1.5: Clear recent excursion sensor data
        # This prevents monitoring service from re-detecting old excursions
        try:
            sensor_collection = mongodb_client[MDB_DATABASE_NAME][MDB_TIMESERIES_COLLECTION]

            # Delete sensor readings with excursions from last 2 hours
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=2)
            delete_result = sensor_collection.delete_many({
                "timestamp": {"$gte": cutoff_time},
                "$or": [
                    {"metrics.particle_count": {"$gt": 1000}},
                    {"metrics.rf_power": {"$gt": 1400}},
                    {"metrics.temperature": {"$gt": 75}}
                ]
            })

            results["excursion_data_cleared"] = delete_result.deleted_count
            logger.info(f"Cleared {delete_result.deleted_count} excursion sensor readings")
        except Exception as e:
            logger.error(f"Error clearing excursion data: {e}")

        # Step 2: Inject healthy sensor data for all equipment
        # NOTE: Sensor injection is DISABLED to prevent RF power drift detection
        # Equipment health is determined by open alerts, not sensor values
        # Sensor readings will update naturally with next monitoring cycle
        equipment_ids = ["CMP_TOOL_01", "CMP_TOOL_02", "ETCH_01", "LITHO_01"]

        # DISABLED: Sensor injection causes new alerts due to RF power drift detection
        # writer = SensorDataWriter(mongodb_uri=MDB_URI, database=MDB_DATABASE_NAME)
        # for equipment_id in equipment_ids:
        #     healthy_data = {...}
        #     result = writer.write_sensor_data(healthy_data)
        #     if result["success"]:
        #         results["healthy_sensors_injected"] += 1
        # writer.close()

        results["healthy_sensors_injected"] = 0  # Disabled
        logger.info(f"Demo reset: Sensor injection disabled (equipment health determined by alerts)")

        # Step 3: Generate healthy wafers to improve yield
        wafer_generator = WaferGenerator(
            mongodb_uri=MDB_URI,
            database=MDB_DATABASE_NAME,
            s3_bucket_uri=os.getenv("S3_BUCKET_URI")
        )

        # Generate 4 healthy wafers (one per equipment) with 95-98% yield
        for i, equipment_id in enumerate(equipment_ids):
            healthy_wafer_data = {
                "alert_id": f"reset_{datetime.now().timestamp()}",
                "equipment_id": equipment_id,
                "excursion_type": "recovery",  # Will map to low defect rate
                "severity": "low",
                "timestamp": datetime.now(timezone.utc),
                "metrics": {
                    "particle_count": 400,
                    "rf_power": 1200,
                    "chamber_pressure": 45,
                    "temperature": 65,
                    "flow_rate": 200
                }
            }

            # Generate wafer with very low defect rate for high yield
            wafer_doc = await wafer_generator.generate_excursion_wafer(healthy_wafer_data)

            # Override pattern to ensure healthy yield
            wafer_doc["defect_summary"]["defect_pattern"] = "random"
            wafer_doc["defect_summary"]["severity"] = "low"
            # Ensure high yield (95-98%)
            wafer_doc["defect_summary"]["yield_percentage"] = 95 + random.uniform(0, 3)
            wafer_doc["defect_summary"]["total_defects"] = random.randint(5, 15)
            wafer_doc["description"] = f"Post-recovery verification wafer from {equipment_id} - Equipment restored to healthy state"

            wafer_generator.wafer_collection.insert_one(wafer_doc)
            results["healthy_wafers_generated"] += 1

        # Step 4: Calculate new average yield (before cleanup)
        latest_wafers = list(wafer_generator.db["wafer_defects"].find()
                           .sort("inspection_timestamp", -1)
                           .limit(10))

        # Now cleanup after we're done with the database
        wafer_generator.cleanup()

        if latest_wafers:
            avg_yield = sum(w["defect_summary"]["yield_percentage"] for w in latest_wafers) / len(latest_wafers)
            results["new_yield"] = round(avg_yield, 1)

        # Step 5: Wait for monitoring service to sync
        # Give monitoring service time to process the healthy data
        logger.info("Waiting for monitoring service to sync...")
        await asyncio.sleep(3)

        # Verify no new alerts were created
        new_alerts_count = 0
        if alert_manager:
            new_alerts_count = alert_manager.alerts_collection.count_documents({
                "status": {"$in": ["open", "acknowledged"]},
                "timestamp": {"$gte": datetime.now(timezone.utc) - timedelta(seconds=10)}
            })

            if new_alerts_count > 0:
                logger.warning(f"Warning: {new_alerts_count} new alerts created during reset")
                results["warning"] = f"{new_alerts_count} new alerts created during reset"

        logger.info(f"Demo reset complete: {results}")

        return {
            "status": "success",
            "message": "Demo reset to healthy state complete",
            **results,
            "equipment_status": "All equipment restored to healthy operating conditions",
            "expected_kpi_changes": {
                "yield": f"~{results['new_yield']}%" if results['new_yield'] else "95-98%",
                "active_alerts": new_alerts_count,
                "equipment_health": "All healthy"
            }
        }

    except Exception as e:
        logger.error(f"Error during demo reset: {e}")
        raise HTTPException(status_code=500, detail=f"Demo reset failed: {str(e)}")