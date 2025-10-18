"""
Monitoring Router
Handles real-time monitoring service control endpoints
"""
import logging
import asyncio
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks

# Import MonitoringService
from services.monitoring_service import MonitoringService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/monitoring",
    tags=["Monitoring"],
    responses={404: {"description": "Not found"}},
)

# Dependencies (injected from main.py on startup)
monitoring_service_instance: MonitoringService | None = None
monitoring_active_flag: bool = False
monitoring_task_ref: asyncio.Task | None = None
wafer_monitoring_task_ref: asyncio.Task | None = None


def set_dependencies(
    monitoring_service: MonitoringService,
    monitoring_active: bool,
    monitoring_task: asyncio.Task | None,
    wafer_monitoring_task: asyncio.Task | None
):
    """
    Inject dependencies from main.py
    
    Args:
        monitoring_service: MonitoringService instance that handles all monitoring logic
        monitoring_active: Current monitoring state flag
        monitoring_task: Reference to sensor monitoring task
        wafer_monitoring_task: Reference to wafer monitoring task
    """
    global monitoring_service_instance, monitoring_active_flag
    global monitoring_task_ref, wafer_monitoring_task_ref
    
    monitoring_service_instance = monitoring_service
    monitoring_active_flag = monitoring_active
    monitoring_task_ref = monitoring_task
    wafer_monitoring_task_ref = wafer_monitoring_task
    
    logger.info("✅ Monitoring dependencies injected into router")


def get_monitoring_state():
    """Get current monitoring state"""
    return {
        "monitoring_service": monitoring_service_instance,
        "monitoring_active": monitoring_active_flag,
        "monitoring_task": monitoring_task_ref,
        "wafer_monitoring_task": wafer_monitoring_task_ref
    }


def set_monitoring_active(active: bool):
    """Set monitoring active flag"""
    global monitoring_active_flag
    monitoring_active_flag = active
    if monitoring_service_instance:
        monitoring_service_instance.monitoring_active = active


def set_monitoring_tasks(monitoring_task: asyncio.Task | None, wafer_task: asyncio.Task | None):
    """Update task references"""
    global monitoring_task_ref, wafer_monitoring_task_ref
    monitoring_task_ref = monitoring_task
    wafer_monitoring_task_ref = wafer_task


logger.info("📦 Monitoring router initialized")


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.post("/start")
async def start_monitoring(background_tasks: BackgroundTasks):
    """
    Start real-time monitoring loops (MonitoringService already initialized on startup)
    """
    logger.info(f"📥 POST /monitoring/start - Request to start monitoring services")
    
    try:
        # Get current state
        state = get_monitoring_state()
        
        # Check if MonitoringService is initialized
        if not state["monitoring_service"]:
            logger.error("❌ MonitoringService not initialized - this should not happen")
            raise HTTPException(status_code=500, detail="MonitoringService not initialized")

        # Check if monitoring loops are already running
        if ((state["monitoring_task"] and not state["monitoring_task"].done()) or 
            (state["wafer_monitoring_task"] and not state["wafer_monitoring_task"].done())):
            logger.info("⚠️ Monitoring loops already active")
            return {
                "status": "already_running",
                "message": "Monitoring loops are already active",
                "services": {
                    "monitoring_service": "active",
                    "sensor_monitoring": "active" if state["monitoring_task"] and not state["monitoring_task"].done() else "stopped",
                    "wafer_monitoring": "active" if state["wafer_monitoring_task"] and not state["wafer_monitoring_task"].done() else "stopped"
                }
            }

        # Start monitoring loops in background (parallel execution)
        set_monitoring_active(True)
        monitoring_task = asyncio.create_task(monitoring_service_instance.start_sensor_monitoring())
        wafer_monitoring_task = asyncio.create_task(monitoring_service_instance.start_wafer_monitoring())
        set_monitoring_tasks(monitoring_task, wafer_monitoring_task)

        logger.info("✅ POST /monitoring/start - Success: Real-time monitoring loops started (sensor + wafer)")
        return {
            "status": "started",
            "message": "Real-time monitoring loops started (sensor + wafer defects)",
            "services": {
                "monitoring_service": "active",
                "sensor_monitoring": "active",
                "wafer_monitoring": "active"
            }
        }

    except Exception as e:
        logger.error(f"❌ POST /monitoring/start - Error: {e}", exc_info=True)
        set_monitoring_active(False)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_monitoring():
    """
    Stop real-time monitoring services
    """
    logger.info(f"📥 POST /monitoring/stop - Request to stop monitoring services")
    
    try:
        state = get_monitoring_state()
        
        if not state["monitoring_active"]:
            logger.info("⚠️ Monitoring is not active")
            return {"status": "not_running", "message": "Monitoring is not active"}
        
        logger.info("⚙️ Stopping monitoring...")
        set_monitoring_active(False)
        
        # Stop monitoring service (sets internal flag to False)
        if state["monitoring_service"]:
            state["monitoring_service"].stop_monitoring()
            logger.debug("   MonitoringService stopped")
        
        logger.info("✅ POST /monitoring/stop - Success: Monitoring services stopped")
        return {
            "status": "stopped",
            "message": "Real-time monitoring services stopped"
        }
        
    except Exception as e:
        logger.error(f"❌ POST /monitoring/stop - Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_monitoring_status():
    """
    Get current monitoring status
    """
    logger.info(f"📥 GET /monitoring/status - Fetching monitoring status")
    
    try:
        state = get_monitoring_state()
        
        status = {
            "monitoring_active": state["monitoring_active"],
            "services": {
                "monitoring_service": "active" if state["monitoring_service"] else "inactive",
                "sensor_monitoring": "active" if (state["monitoring_task"] and not state["monitoring_task"].done()) else "stopped",
                "wafer_monitoring": "active" if (state["wafer_monitoring_task"] and not state["wafer_monitoring_task"].done()) else "stopped"
            }
        }
        
        logger.info(f"✅ GET /monitoring/status - Success: monitoring_active={state['monitoring_active']}")
        return status
        
    except Exception as e:
        logger.error(f"❌ GET /monitoring/status - Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

