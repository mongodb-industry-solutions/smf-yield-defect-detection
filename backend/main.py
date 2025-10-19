from db.mdb import MongoDBConnector

import logging
from datetime import datetime, timedelta, timezone
import time

from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.config_loader import ConfigLoader
from utils import convert_objectids

# Import Phase 2 services
from services.excursion_detector import ExcursionDetector
from services.correlation_engine import CorrelationEngine
from services.rca_generator import RCAGenerator
from services.alert_manager import AlertManager, AlertSeverity, AlertStatus, AlertType
from services.websocket_manager import get_websocket_manager, ConnectionType
from services.wafer_generator import WaferGenerator
from services.sensor_data_writer import SensorDataWriter
from services.monitoring_service import MonitoringService

# Import Multi-Agent System (Phase 3)
from multi_agent import create_initial_state
from multi_agent.workers import monitoring_agent_tool, investigation_agent_tool, rca_agent_tool
from multi_agent.supervisor import supervisor_synthesis_agent

# Import routers
from routers import demo_mode as demo_mode_router
from routers import semantic_search as semantic_search_router
from routers import collections as collections_router
from routers import alerts as alerts_router
from routers import wafers as wafers_router
from routers import ai_agents as ai_agents_router
from routers import monitoring as monitoring_router
from routers import sensors as sensors_router
from routers import equipment as equipment_router
from routers import kpi as kpi_router
from routers import websockets as websockets_router
from routers import dashboard as dashboard_router

import os
from dotenv import load_dotenv
import asyncio

# Import centralized threshold configuration for startup logging
from config.thresholds import log_threshold_configuration

load_dotenv()

# Log threshold configuration on startup
log_threshold_configuration()

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

# Demo Mode Configuration (used for service initialization)
DEMO_MODE_ENABLED = os.getenv("DEMO_MODE_ENABLED", "false").lower() == "true"
DEMO_INTERVAL_SECONDS = int(os.getenv("DEMO_INTERVAL_SECONDS", "60"))  # 60 seconds (1 minute) for continuous Atlas Charts visualization
DEMO_EXCURSION_PROBABILITY = float(os.getenv("DEMO_EXCURSION_PROBABILITY", "0.05"))  # 5% excursion rate for realistic monitoring

# Demo Mode Global State - MOVED TO DemoModeService
# (Service is initialized in startup_event and injected into demo_mode router)

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
# Demo Mode Functions - MOVED TO services/demo_mode_service.py
# ============================================================================
# All demo mode business logic has been extracted to DemoModeService class
# See: backend/services/demo_mode_service.py
# 
# Moved functions:
# - load_process_context_ids()
# - generate_demo_metrics()
# - generate_demo_metadata()
# - demo_data_generator()
# ============================================================================

app = FastAPI()

# Add timing middleware to log all requests with duration
@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000  # Convert to milliseconds

    # Skip logging for static assets and frequent polling endpoints
    skip_paths = ['/favicon.ico', '/static/']
    should_log = not any(skip in request.url.path for skip in skip_paths)

    if should_log:
        if process_time > 100:  # Only log slow requests (>100ms)
            logger.warning(f"⏱️  SLOW REQUEST [{request.method}] {request.url.path} - {process_time:.0f}ms")
        else:
            logger.info(f"⏱️  [{request.method}] {request.url.path} - {process_time:.0f}ms")

    response.headers["X-Process-Time"] = f"{process_time:.2f}"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# Monitoring Service (handles sensor and wafer monitoring loops)
monitoring_service = None

# ============================================================================
# Demo Mode Service and Router Setup
# ============================================================================
# Import demo mode service
from services.demo_mode_service import DemoModeService

# Initialize demo service instance (will be fully configured in startup event)
demo_service_instance: DemoModeService | None = None

# Include demo mode router
app.include_router(demo_mode_router.router)
logger.info("✅ Demo mode router included")

# Include semantic search router
app.include_router(semantic_search_router.router)
logger.info("✅ Semantic search router included")

# Include collections router
app.include_router(collections_router.router)
logger.info("✅ Collections router included")

# Include alerts router
app.include_router(alerts_router.router)
logger.info("✅ Alerts router included")

# Include wafers router
app.include_router(wafers_router.router)
logger.info("✅ Wafers router included")

# Include AI agents router
app.include_router(ai_agents_router.router)
logger.info("✅ AI agents router included")

# Include monitoring router
app.include_router(monitoring_router.router)
logger.info("✅ Monitoring router included")

# Include sensors router
app.include_router(sensors_router.router)
logger.info("✅ Sensors router included")

# Include equipment router
app.include_router(equipment_router.router)
logger.info("✅ Equipment router included")

# Include KPI router
app.include_router(kpi_router.router)
logger.info("✅ KPI router included")

# Include WebSocket router
app.include_router(websockets_router.router)
logger.info("✅ WebSocket router included")

# Include Dashboard Preload router (with /api prefix)
app.include_router(dashboard_router.router, prefix="/api")
logger.info("✅ Dashboard preload router included")

# ============================================================================

# ============================================================================
# Startup Helper Functions
# ============================================================================

def _initialize_core_services():
    """
    Initialize core monitoring services with connection reuse
    
    Returns:
        dict: Dictionary containing initialized services
    """
    logger.info("=" * 60)
    logger.info("🚀 Initializing core services with connection pooling...")
    logger.info("=" * 60)
    
    # Initialize async MongoDB client
    logger.info("📊 Creating MongoDB async client...")
    mongo_client = AsyncIOMotorClient(MDB_URI)
    logger.info("   ✅ MongoDB async client created")
    
    # Initialize monitoring services
    logger.info("🔧 Initializing monitoring services...")
    
    logger.info("   📡 Creating ExcursionDetector...")
    excursion_det = ExcursionDetector(
        mongodb_uri=MDB_URI,
        database=MDB_DATABASE_NAME
    )
    
    logger.info("   🔗 Creating CorrelationEngine (connection pool)...")
    correlation_eng = CorrelationEngine(
        mongodb_uri=MDB_URI,
        database=MDB_DATABASE_NAME
    )
    
    logger.info("   🔍 Creating RCAGenerator (connection pool)...")
    rca_gen = RCAGenerator(
        mongodb_uri=MDB_URI,
        database=MDB_DATABASE_NAME
    )
    
    logger.info("   🚨 Creating AlertManager...")
    alert_mgr = AlertManager(
        mongodb_uri=MDB_URI,
        database_name=MDB_DATABASE_NAME
    )
    alert_mgr.initialize()
    
    logger.info("   🧪 Creating WaferGenerator...")
    s3_bucket_uri = os.getenv("S3_BUCKET_URI")
    wafer_gen = WaferGenerator(
        mongodb_uri=MDB_URI,
        database=MDB_DATABASE_NAME,
        s3_bucket_uri=s3_bucket_uri
    )
    
    logger.info("   📺 Creating MonitoringService with shared service instances...")
    monitoring_svc = MonitoringService(
        alert_manager=alert_mgr,
        ws_manager=ws_manager,
        wafer_generator=wafer_gen,
        correlation_engine=correlation_eng,  # ✅ Passing instance for reuse
        rca_generator=rca_gen,               # ✅ Passing instance for reuse
        config={
            'mdb_uri': MDB_URI,
            'mdb_database_name': MDB_DATABASE_NAME,
            'use_ai_agents': USE_AI_AGENTS
        }
    )
    
    logger.info("=" * 60)
    logger.info("✅ All core services initialized successfully!")
    logger.info("   ♻️  Connection reuse enabled for:")
    logger.info("      - CorrelationEngine → MonitoringService")
    logger.info("      - RCAGenerator → MonitoringService")
    logger.info("=" * 60)
    
    return {
        'mongodb_client': mongo_client,
        'excursion_detector': excursion_det,
        'correlation_engine': correlation_eng,
        'rca_generator': rca_gen,
        'alert_manager': alert_mgr,
        'wafer_generator': wafer_gen,
        'monitoring_service': monitoring_svc
    }


def _initialize_demo_service(alert_mgr, mongo_client):
    """
    Initialize Demo Mode Service
    
    Args:
        alert_mgr: AlertManager instance
        mongo_client: AsyncIOMotorClient instance
        
    Returns:
        DemoModeService: Initialized demo service instance
    """
    logger.info("🎬 Initializing Demo Mode Service...")
    
    demo_svc = DemoModeService(
        mongodb_uri=MDB_URI,
        database_name=MDB_DATABASE_NAME,
        demo_interval_seconds=DEMO_INTERVAL_SECONDS,
        demo_excursion_probability=DEMO_EXCURSION_PROBABILITY
    )
    
    # Inject demo service into router
    demo_mode_router.set_demo_service(demo_svc)
    
    # Inject dependencies for demo mode router
    demo_mode_router.set_dependencies(
        alert_manager=alert_mgr,
        mongodb_client=mongo_client,
        config={
            "mongodb_uri": MDB_URI,
            "database_name": MDB_DATABASE_NAME,
            "timeseries_collection": MDB_TIMESERIES_COLLECTION
        }
    )
    logger.info("✅ Demo Mode Service initialized and injected into router")
    
    return demo_svc


async def _inject_router_dependencies(services, demo_svc):
    """
    Inject dependencies into all application routers
    
    Args:
        services: Dictionary containing all initialized services
        demo_svc: Initialized DemoModeService instance
    """
    logger.info("Injecting dependencies into routers...")
    
    from db.mdb import MongoDBConnector
    
    # Inject dependencies into alerts router
    alerts_router.set_dependencies(
        alert_manager=services['alert_manager'],
        convert_func=convert_objectids,
        mongodb_client=services['mongodb_client'],
        correlation_engine=services['correlation_engine'],
        use_ai_agents=USE_AI_AGENTS,
        db_name=MDB_DATABASE_NAME,
        timeseries_collection=MDB_TIMESERIES_COLLECTION
    )
    logger.info("✅ Alerts dependencies injected into router")
    
    # Inject dependencies into wafers router
    wafers_router.set_dependencies(
        connector_class=MongoDBConnector,
        convert_func=convert_objectids,
        mongodb_client=services['mongodb_client'],
        wafer_generator=None,  # Will be created on-demand in endpoints
        excursion_detector=services['excursion_detector'],
        demo_service=demo_svc,
        uri=MDB_URI,
        db_name=MDB_DATABASE_NAME,
        use_ai_agents=USE_AI_AGENTS
    )
    logger.info("✅ Wafers dependencies injected into router")
    
    # Inject dependencies into AI agents router
    ai_agents_router.set_dependencies(use_ai_agents=USE_AI_AGENTS)
    logger.info("✅ AI Agents dependencies injected into router")
    
    # Inject dependencies into monitoring router
    monitoring_router.set_dependencies(
        monitoring_service=services['monitoring_service'],
        monitoring_active=True,
        monitoring_task=None,  # Will be set after tasks are created
        wafer_monitoring_task=None
    )
    logger.info("✅ Monitoring dependencies injected into router")
    
    # Inject dependencies into sensors router
    sensors_router.set_dependencies(
        connector_class=MongoDBConnector,
        sensor_writer_class=SensorDataWriter,
        convert_func=convert_objectids,
        uri=MDB_URI,
        db_name=MDB_DATABASE_NAME,
        timeseries_collection=MDB_TIMESERIES_COLLECTION
    )
    logger.info("✅ Sensors dependencies injected into router")
    
    # Inject dependencies into equipment router
    equipment_router.set_dependencies(
        async_client=services['mongodb_client'],
        connector_class=MongoDBConnector,
        uri=MDB_URI,
        db_name=MDB_DATABASE_NAME,
        timeseries_collection=MDB_TIMESERIES_COLLECTION
    )
    logger.info("✅ Equipment dependencies injected into router")
    
    # Inject dependencies into KPI router
    kpi_router.set_dependencies(
        async_client=services['mongodb_client'],
        db_name=MDB_DATABASE_NAME
    )
    logger.info("✅ KPI dependencies injected into router")
    
    # Inject dependencies into WebSocket router
    websockets_router.set_dependencies(
        ws_manager=ws_manager,
        connector_class=MongoDBConnector,
        convert_func=convert_objectids,
        uri=MDB_URI,
        db_name=MDB_DATABASE_NAME
    )
    logger.info("✅ WebSocket dependencies injected into router")
    
    # Inject dependencies into Dashboard Preload router
    dashboard_router.set_dependencies(
        async_client=services['mongodb_client'],
        db_name=MDB_DATABASE_NAME
    )
    logger.info("✅ Dashboard preload dependencies injected into router")
    
    # Initialize Phase 3 services
    await initialize_phase3_services()
    
    # Inject dependencies into collections router
    collections_router.set_dependencies(
        connector_class=MongoDBConnector,
        uri=MDB_URI,
        db_name=MDB_DATABASE_NAME,
        convert_func=convert_objectids
    )
    logger.info("✅ Collections dependencies injected into router")


@app.on_event("startup")
async def startup_event():
    """
    Initialize monitoring services on application startup
    """
    global excursion_detector, correlation_engine, rca_generator, alert_manager
    global monitoring_active, mongodb_client, demo_service_instance, monitoring_service
    global monitoring_task, wafer_monitoring_task

    logger.info("Initializing monitoring services on startup...")

    try:
        # Step 1: Initialize core services
        services = _initialize_core_services()
        
        # Unpack and assign to global variables
        mongodb_client = services['mongodb_client']
        excursion_detector = services['excursion_detector']
        correlation_engine = services['correlation_engine']
        rca_generator = services['rca_generator']
        alert_manager = services['alert_manager']
        monitoring_service = services['monitoring_service']
        
        # Step 2: Set monitoring as active and auto-start monitoring loops
        monitoring_active = True
        monitoring_service.monitoring_active = True
        
        monitoring_task = asyncio.create_task(monitoring_service.start_sensor_monitoring())
        wafer_monitoring_task = asyncio.create_task(monitoring_service.start_wafer_monitoring())
        
        logger.info("✅ Monitoring services initialized successfully on startup")
        logger.info("Services ready: ExcursionDetector, CorrelationEngine, RCAGenerator, AlertManager")
        logger.info("✅ Monitoring loops auto-started (sensor + wafer defects)")
        
        # Step 3: Initialize demo service
        demo_service_instance = _initialize_demo_service(alert_manager, mongodb_client)
        
        # Step 4: Inject dependencies into all routers
        await _inject_router_dependencies(services, demo_service_instance)
        
        logger.info("✅ All services and routers initialized successfully")
        
        # Step 5: Auto-start demo mode if configured
        AUTO_START_DEMO = os.getenv("AUTO_START_DEMO", "false").lower() == "true"
        if AUTO_START_DEMO:
            logger.info("🎬 AUTO_START_DEMO enabled - starting demo mode...")
            try:
                # Pre-load seed data
                logger.info("📊 Pre-loading seed data...")
                reset_stats = await demo_service_instance.reset_demo_collections()
                logger.info(f"   ✅ Seed data loaded: {reset_stats}")
                
                # Start demo mode
                result = await demo_service_instance.start_demo_mode(mode="charts")
                logger.info(f"   ✅ Demo mode auto-started: {result['status']}")
            except Exception as e:
                logger.error(f"   ❌ Failed to auto-start demo mode: {e}")

    except Exception as e:
        logger.error(f"❌ Failed to initialize monitoring services on startup: {e}")
        logger.warning("Services will be initialized on first use")

@app.get("/")
async def read_root(request: Request):
    return {"message": "Server is running"}


# ============================================================================
# LEGACY AGENT ENDPOINTS REMOVED
# ============================================================================
# The following OLD endpoints have been removed (replaced by Phase 4 /agent/* endpoints):
# - GET /run-agent → replaced by POST /agent/start
# - GET /resume-agent → replaced by POST /agent/resume/{session_id}
# - GET /get-sessions → replaced by GET /agent/sessions
# - GET /get-run-documents → deprecated (no replacement)
# 
# These legacy endpoints used the old create_workflow_graph() function.
# Modern endpoints use WorkflowGraphBuilder and AgentSessionManager.
# ============================================================================


# ====================== Phase 2: Real-time Monitoring Endpoints ======================
# MOVED TO routers/monitoring.py
# - POST /monitoring/start
# - POST /monitoring/stop
# - GET /monitoring/status


# ====================== Real-time Monitoring Dashboard APIs ======================

# ============================================================================
# Helper Functions - MOVED TO services/monitoring_service.py
# ============================================================================
# The following helper functions have been migrated to MonitoringService:
# - run_alert_correlation() → monitoring_service.run_alert_correlation()
# - run_alert_rca() → monitoring_service.run_alert_rca()
# - generate_delayed_wafer_defect() → monitoring_service.generate_delayed_wafer_defect()
# - determine_severity() → monitoring_service.determine_severity()
# - notify_websocket_clients() → monitoring_service.notify_websocket_clients()
# ============================================================================

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
        
        # Inject dependencies into semantic search router
        # Create async MongoDB client for embeddings endpoint
        from motor.motor_asyncio import AsyncIOMotorClient
        async_mongo_client = AsyncIOMotorClient(MDB_URI)
        
        semantic_search_router.set_dependencies(
            semantic_search_svc=semantic_search_service,
            mongodb_client=async_mongo_client,
            db_name=MDB_DATABASE_NAME
        )
        logger.info("✅ Semantic search dependencies injected into router")
        
    except Exception as e:
        logger.warning(f"Phase 3 services not available: {e}")



