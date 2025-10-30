"""
Demo Mode Router - Endpoints for demo data generation and control

This router provides endpoints to:
- Start/stop demo mode
- Check demo status
- Reset demo environment
- Inject test excursions and patterns
"""

import logging
import os
import random
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Body

from config.demo_config import DEMO_EXCURSION_PROBABILITY
from services.demo_mode_service import DemoModeService
from services.wafer_generator import WaferGenerator
from services.sensor_data_writer import SensorDataWriter

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="",
    tags=["Demo Mode"],
    responses={404: {"description": "Not found"}},
)

# Global service instances (will be initialized by dependency injection)
demo_service: DemoModeService | None = None
alert_manager_instance = None
mongodb_client_instance = None
mongodb_config = {}


def set_demo_service(service: DemoModeService):
    """
    Set the demo service instance for the router
    
    Args:
        service: DemoModeService instance
    """
    global demo_service
    demo_service = service
    logger.info("✅ Demo service injected into router")


def set_dependencies(alert_manager, mongodb_client, config: dict):
    """
    Set the global dependencies needed by demo mode endpoints
    
    Args:
        alert_manager: AlertManager instance
        mongodb_client: MongoDB async client instance  
        config: Dict with mongodb_uri, database_name, timeseries_collection, etc.
    """
    global alert_manager_instance, mongodb_client_instance, mongodb_config
    alert_manager_instance = alert_manager
    mongodb_client_instance = mongodb_client
    mongodb_config = config
    logger.info("✅ Demo mode dependencies injected into router")


def get_demo_service() -> DemoModeService:
    """
    Get the demo service instance
    
    Returns:
        DemoModeService instance
        
    Raises:
        HTTPException: If demo service not initialized
    """
    if demo_service is None:
        logger.error("❌ Demo service not initialized")
        raise HTTPException(
            status_code=500,
            detail="Demo service not initialized"
        )
    return demo_service


@router.get("/api/demo/seed-status")
async def check_seed_status():
    """
    Check if demo seed data exists and is fresh (last 15 minutes)
    
    This endpoint checks for a seed marker document in the demo_metadata collection
    to determine if baseline data has been seeded recently. Used by frontend to
    determine if initial seeding is needed on app load.
    
    Returns:
        Dict with seed status information:
        - seeded: bool - True if data is fresh (< 15 minutes old)
        - last_seed_time: str | None - ISO timestamp of last seed
        - age_minutes: float | None - Age of seed data in minutes
        - needs_refresh: bool - True if seed is missing or stale
    """
    logger.info("📊 GET /api/demo/seed-status - Checking seed data freshness")
    
    try:
        if not mongodb_client_instance or not mongodb_config:
            raise HTTPException(status_code=500, detail="MongoDB not configured")
        
        db = mongodb_client_instance[mongodb_config["database_name"]]
        
        # Check for seed marker document in demo_metadata collection
        seed_marker = await db.demo_metadata.find_one({"_id": "seed_marker"})
        
        if not seed_marker:
            logger.info("❌ No seed marker found - data needs seeding")
            return {
                "seeded": False,
                "last_seed_time": None,
                "age_minutes": None,
                "needs_refresh": True
            }
        
        last_seed_time = seed_marker.get("seeded_at")
        if not last_seed_time:
            logger.info("❌ Seed marker exists but missing timestamp - needs seeding")
            return {
                "seeded": False,
                "last_seed_time": None,
                "age_minutes": None,
                "needs_refresh": True
            }
        
        # Calculate age of seed data
        # Ensure both datetimes are timezone-aware
        now = datetime.now(timezone.utc)
        if last_seed_time.tzinfo is None:
            # Make timezone-aware if needed
            last_seed_time = last_seed_time.replace(tzinfo=timezone.utc)
        
        age = now - last_seed_time
        age_minutes = age.total_seconds() / 60
        
        # Check if refresh needed (older than 15 minutes)
        needs_refresh = age_minutes > 15
        
        logger.info(
            f"✅ Seed status: seeded={not needs_refresh}, "
            f"age={age_minutes:.1f} minutes"
        )
        
        return {
            "seeded": not needs_refresh,
            "last_seed_time": last_seed_time.isoformat(),
            "age_minutes": round(age_minutes, 1),
            "needs_refresh": needs_refresh
        }
        
    except Exception as e:
        logger.error(f"❌ Error checking seed status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check seed status: {str(e)}"
        )


@router.post("/api/demo/initialize-seed")
async def initialize_seed():
    """
    One-time initialization of demo seed data
    
    This endpoint performs a complete seeding of baseline and anomalous data:
    1. Clears recent demo data (last 1 hour)
    2. Seeds 1 hour of baseline sensor data (360 readings: 60 min × 6 equipment)
    3. Seeds 3 anomaly patterns (13 readings total)
    4. Sets seed marker timestamp in demo_metadata collection
    
    NOTE: This does NOT create alerts or wafers - those are generated automatically
    by the monitoring service when it detects excursions via change streams.
    
    Returns:
        Dict with initialization results:
        - success: bool - True if seeding completed successfully
        - seeded_at: str - ISO timestamp when seeding completed
        - stats: Dict with baseline_readings, anomalous_readings counts
        - total_time_ms: float - Time taken for seeding operation
    """
    logger.info("🌱 POST /api/demo/initialize-seed - Starting one-time seed initialization")
    
    try:
        import time
        start_time = time.time()
        
        service = get_demo_service()
        
        # Load process context IDs first (needed for metadata generation)
        await service.load_process_context_ids()
        
        # Call reset_demo_collections which seeds baseline + anomalies
        # This method already exists in DemoModeService and does exactly what we need:
        # - Clears recent data (last 1 hour)
        # - Seeds 60 minutes of baseline data (60 readings per equipment)
        # - Seeds 3 anomaly patterns
        reset_stats = await service.reset_demo_collections()
        
        logger.info(f"✅ Seed data generated: {reset_stats}")
        
        # Set seed marker in database
        if not mongodb_client_instance or not mongodb_config:
            raise HTTPException(status_code=500, detail="MongoDB not configured")
        
        db = mongodb_client_instance[mongodb_config["database_name"]]
        seed_time = datetime.now(timezone.utc)
        
        await db.demo_metadata.update_one(
            {"_id": "seed_marker"},
            {
                "$set": {
                    "seeded_at": seed_time,
                    "seed_stats": reset_stats
                }
            },
            upsert=True
        )
        
        total_time_ms = (time.time() - start_time) * 1000
        
        logger.info(
            f"✅ Seed initialization complete in {total_time_ms:.0f}ms - "
            f"{reset_stats['baseline_readings']} baseline + {reset_stats['anomalous_readings']} anomalies"
        )
        
        return {
            "success": True,
            "seeded_at": seed_time.isoformat(),
            "stats": reset_stats,
            "total_time_ms": round(total_time_ms, 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error during seed initialization: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Seed initialization failed: {str(e)}"
        )


@router.get("/demo/status")
async def get_demo_status():
    """
    Get demo mode status with parallel equipment updates
    
    Returns detailed information about:
    - Current demo mode state (active/inactive)
    - Configuration (interval, excursion probability)
    - Expected data generation rates
    - Equipment list
    """
    logger.info("📊 GET /demo/status - Fetching demo mode status")
    
    try:
        service = get_demo_service()
        status = service.get_status()
        
        logger.info(f"✅ Demo status retrieved: active={status['active']}")
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting demo status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get demo status: {str(e)}"
        )


@router.post("/demo/start")
async def start_demo_mode(request: Dict[str, Any] = Body(default={})):
    """
    Start demo mode data generation

    Request body (optional):
    {
        "excursion_probability": 0.05,  // Optional: Override excursion probability (0 = no anomalies)
        "mode": "charts" | "agentic",   // Optional: Mode indicator (agentic sets probability to 0)
        "scenario": "continuous" | "lot_processing_drift" | "lot_processing_spike" | "lot_processing_oscillation"
                   // Optional: Demo scenario (default: continuous)
    }

    Returns detailed information about:
    - Start status
    - Configuration (mode, interval, excursion probability)
    - Scenario details (lot processing: 25 wafers in 3 minutes)
    - Equipment list
    """
    logger.info(f"🎬 POST /demo/start - Starting demo mode with config: {request}")

    try:
        service = get_demo_service()

        # Extract parameters from request
        mode = request.get("mode", "charts")
        custom_probability = request.get("excursion_probability")
        scenario = request.get("scenario", "continuous")

        # If lot processing scenario, optionally reset collections for clean slate
        if scenario.startswith("lot_processing_"):
            pattern = scenario.split("_")[-1]  # Extract: drift, spike, or oscillation
            logger.info(f"📦 Lot processing {pattern} scenario requested - preparing clean environment")
            # Optionally reset collections for clean demo
            # await service.reset_demo_collections()  # Uncomment if you want fresh data

        # Start demo mode through service
        result = await service.start_demo_mode(
            mode=mode,
            custom_probability=custom_probability,
            scenario=scenario
        )

        logger.info(f"✅ Demo mode started: {result['status']} - scenario: {scenario}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error starting demo mode: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start demo mode: {str(e)}"
        )


@router.post("/demo/stop")
async def stop_demo_mode():
    """
    Stop demo mode data generation and cleanup recent alerts
    
    Returns information about:
    - Stop status
    - Note about monitoring loops (continue running)
    """
    logger.info("🛑 POST /demo/stop - Stopping demo mode")
    
    try:
        service = get_demo_service()

        # Get original probability from centralized config
        original_prob = DEMO_EXCURSION_PROBABILITY

        # Stop demo mode through service
        result = await service.stop_demo_mode(restore_probability=original_prob)
        
        logger.info(f"✅ Demo mode stopped: {result['status']}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error stopping demo mode: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop demo mode: {str(e)}"
        )


@router.post("/demo/reset")
async def reset_demo_to_healthy_state():
    """
    Complete demo reset: Delete all demo data and restore healthy state
    Stops demo mode, deletes auto-generated alerts, deletes demo wafers, and clears excursion data

    Returns information about:
    - Demo stopped status
    - Alerts deleted count (auto-generated alerts only)
    - Wafers deleted count (wafers without embeddings)
    - Excursion data cleared count
    - Equipment status and expected KPI changes
    """
    logger.info("🔄 POST /demo/reset - Resetting demo to healthy state")
    
    try:
        service = get_demo_service()
        
        results = {
            "alerts_deleted": 0,
            "wafers_deleted": 0,
            "healthy_sensors_injected": 0,
            "healthy_wafers_generated": 0,
            "new_yield": None,
            "demo_stopped": False,
            "excursion_data_cleared": 0
        }
        
        # Step 0: Stop demo mode first to prevent new excursions
        if service.is_active():
            logger.info("🛑 Stopping demo mode before reset...")
            original_prob = DEMO_EXCURSION_PROBABILITY
            await service.stop_demo_mode(restore_probability=original_prob)
            results["demo_stopped"] = True
            logger.info("✅ Demo mode stopped successfully")
            
            # Wait for monitoring service to process the stop
            await asyncio.sleep(5)
        
        # Step 1: Delete all auto-generated alerts
        if alert_manager_instance:
            # Delete all auto-generated alerts (demo alerts)
            delete_result = alert_manager_instance.alerts_collection.delete_many({
                "auto_generated": True
            })

            results["alerts_deleted"] = delete_result.deleted_count
            logger.info(f"✅ Demo reset: Deleted {results['alerts_deleted']} auto-generated alerts")
        
        # Step 1.5: Clear recent excursion sensor data
        # This prevents monitoring service from re-detecting old excursions
        try:
            if mongodb_client_instance and mongodb_config:
                sensor_collection = mongodb_client_instance[mongodb_config["database_name"]][
                    mongodb_config["timeseries_collection"]
                ]
                
                # Delete sensor readings with excursions from last 2 hours
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=2)
                delete_result = await sensor_collection.delete_many({
                    "timestamp": {"$gte": cutoff_time},
                    "$or": [
                        {"metrics.particle_count": {"$gt": 1000}},
                        {"metrics.rf_power": {"$gt": 1400}},
                        {"metrics.temperature": {"$gt": 75}}
                    ]
                })
                
                results["excursion_data_cleared"] = delete_result.deleted_count
                logger.info(f"✅ Cleared {delete_result.deleted_count} excursion sensor readings")
        except Exception as e:
            logger.error(f"❌ Error clearing excursion data: {e}")

        # Step 1.6: Delete wafers without embeddings (demo-generated wafers)
        try:
            if mongodb_client_instance and mongodb_config:
                wafer_collection = mongodb_client_instance[mongodb_config["database_name"]]["wafer_defects"]

                # Delete wafers that don't have embedding field
                delete_result = await wafer_collection.delete_many({
                    "embedding": {"$exists": False}
                })

                results["wafers_deleted"] = delete_result.deleted_count
                logger.info(f"✅ Deleted {delete_result.deleted_count} demo-generated wafers (no embeddings)")
        except Exception as e:
            logger.error(f"❌ Error deleting demo wafers: {e}")
            results["wafers_deleted"] = 0

        # Step 2: Inject healthy sensor data for all equipment
        # NOTE: Sensor injection is DISABLED to prevent RF power drift detection
        # Equipment health is determined by open alerts, not sensor values
        # Sensor readings will update naturally with next monitoring cycle
        equipment_ids = ["CMP_TOOL_01", "CMP_TOOL_02", "ETCH_01", "LITHO_01","ETCH_02", "LITHO_02"]
        
        results["healthy_sensors_injected"] = 0  # Disabled
        logger.info(f"ℹ️  Demo reset: Sensor injection disabled (equipment health determined by alerts)")
        
        # # Step 3: Generate healthy wafers to improve yield
        # if mongodb_config:
        #     wafer_generator = WaferGenerator(
        #         mongodb_uri=mongodb_config["mongodb_uri"],
        #         database=mongodb_config["database_name"],
        #         s3_bucket_uri=os.getenv("S3_BUCKET_URI")
        #     )
            
        #     # Generate 4 healthy wafers (one per equipment) with 95-98% yield
        #     for i, equipment_id in enumerate(equipment_ids):
        #         healthy_wafer_data = {
        #             "alert_id": f"reset_{datetime.now().timestamp()}",
        #             "equipment_id": equipment_id,
        #             "excursion_type": "recovery",  # Will map to low defect rate
        #             "severity": "low",
        #             "timestamp": datetime.now(timezone.utc),
        #             "metrics": {
        #                 "particle_count": 400,
        #                 "rf_power": 1200,
        #                 "chamber_pressure": 45,
        #                 "temperature": 65,
        #                 "flow_rate": 200
        #             }
        #         }
                
        #         # Generate wafer with very low defect rate for high yield
        #         wafer_doc = await wafer_generator.generate_excursion_wafer(healthy_wafer_data)
                
        #         # Override pattern to ensure healthy yield
        #         wafer_doc["defect_summary"]["defect_pattern"] = "random"
        #         wafer_doc["defect_summary"]["severity"] = "low"
        #         # Ensure high yield (95-98%)
        #         wafer_doc["defect_summary"]["yield_percentage"] = 95 + random.uniform(0, 3)
        #         wafer_doc["defect_summary"]["total_defects"] = random.randint(5, 15)
        #         wafer_doc["description"] = f"Post-recovery verification wafer from {equipment_id} - Equipment restored to healthy state"
                
        #         wafer_generator.wafer_collection.insert_one(wafer_doc)
        #         results["healthy_wafers_generated"] += 1
            
        #     # Step 4: Calculate new average yield (before cleanup)
        #     latest_wafers = list(wafer_generator.db["wafer_defects"].find()
        #                        .sort("inspection_timestamp", -1)
        #                        .limit(10))
            
        #     # Now cleanup after we're done with the database
        #     wafer_generator.cleanup()
            
        #     if latest_wafers:
        #         avg_yield = sum(w["defect_summary"]["yield_percentage"] for w in latest_wafers) / len(latest_wafers)
        #         results["new_yield"] = round(avg_yield, 1)
        
        # Step 5: Wait for monitoring service to sync
        # Give monitoring service time to process the healthy data
        logger.info("⏳ Waiting for monitoring service to sync...")
        await asyncio.sleep(3)
        
        # Verify no new alerts were created
        new_alerts_count = 0
        if alert_manager_instance:
            new_alerts_count = alert_manager_instance.alerts_collection.count_documents({
                "status": {"$in": ["open", "acknowledged"]},
                "timestamp": {"$gte": datetime.now(timezone.utc) - timedelta(seconds=10)}
            })
            
            if new_alerts_count > 0:
                logger.warning(f"⚠️  Warning: {new_alerts_count} new alerts created during reset")
                results["warning"] = f"{new_alerts_count} new alerts created during reset"
        
        logger.info(f"✅ Demo reset complete: {results}")
        
        return {
            "status": "success",
            "message": "Demo reset complete - all demo data cleared",
            **results,
            "equipment_status": "All equipment restored to healthy operating conditions",
            "expected_kpi_changes": {
                "yield": f"~{results['new_yield']}%" if results['new_yield'] else "95-98%",
                "active_alerts": 0,  # All auto-generated alerts deleted
                "equipment_health": "All healthy"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error during demo reset: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Demo reset failed: {str(e)}"
        )

@router.post("/demo/inject-excursion")
async def inject_excursion(request: Dict[str, Any] = Body(...)):
    """
    Manually inject an excursion into the sensor data (physics-based causal model)

    AUTO-PAUSES demo mode during injection to prevent collision/duplicate alerts.

    PHYSICS-BASED MODEL: Particle count is CALCULATED from root cause (temperature or RF power).
    This reflects the real causal relationship in semiconductor manufacturing.

    Expected payload:
    {
        "equipment_id": "CMP_TOOL_01",     # Required
        "excursion_type": "temperature" | "rf_power",  # Required: root cause type
        "temperature": 72.0,                # Optional: explicit temperature value (°C)
        "rf_power": 1600.0,                 # Optional: explicit RF power value (W)
        "metadata": {...},                  # Optional: override metadata
        "auto_resume_demo": false,          # Optional: auto-resume demo after injection

        # DISCOURAGED (testing only):
        "particle_count": 2500              # Optional: bypass physics, logs warning
    }

    Returns information about:
    - Injection status
    - Equipment ID
    - Excursion type and triggered values (including calculated particle count)
    - Sensor event and timeseries IDs
    - Demo mode state (paused/resumed)
    - Physics calculation details
    - Note about alert/wafer generation timing
    """
    logger.info(f"💉 POST /demo/inject-excursion - Injecting excursion: {request}")
    
    try:
        service = get_demo_service()
        
        # === STEP 1: Pause demo mode if active to prevent collision ===
        demo_was_active = service.demo_mode_active
        auto_resume = request.get("auto_resume_demo", True)  # Default: auto-resume to allow multiple injections
        
        logger.info(f"🔍 Demo mode check: active={demo_was_active}, auto_resume={auto_resume}")
        
        if demo_was_active:
            logger.info("⏸️  Pausing demo mode to prevent collision with manual injection...")
            stop_result = await service.stop_demo_mode()
            logger.info(f"   ✅ Demo mode paused: {stop_result['status']}")
            # Wait briefly for demo loop to fully stop
            await asyncio.sleep(0.5)
        
        # Get equipment ID (required)
        equipment_id = request.get("equipment_id")
        if not equipment_id:
            logger.error("❌ Missing required parameter: equipment_id")
            raise HTTPException(status_code=400, detail="equipment_id is required")
        
        # Generate base NORMAL metrics (not excursion to avoid random type selection)
        metrics = service.generate_demo_metrics(equipment_id, is_excursion=False)

        # Store baseline particle count before modification
        baseline_particle_count = metrics["particle_count"]

        # Get equipment type for threshold lookups
        equipment_type = equipment_id.split("_")[0]  # CMP, ETCH, LITHO

        # Apply specific excursion type (root cause) if requested
        excursion_type = request.get("excursion_type", "temperature")  # Default to temperature
        logger.info(f"   💉 Injecting {excursion_type} excursion for {equipment_id} (physics-based)")

        # PHYSICS-BASED MODEL: Apply root cause, then calculate particle count
        if excursion_type == "rf_power":
            # Calculate baseline for equipment type
            from config.thresholds import get_thresholds
            thresholds = get_thresholds()
            baseline_rf = thresholds["rf_power_drift"].get(
                equipment_type,
                thresholds["rf_power_drift"]["CMP"]
            )["baseline"]

            # Apply RF power drift (use provided value or generate)
            metrics["rf_power"] = request.get("rf_power", baseline_rf + random.uniform(120, 200))
            logger.info(f"   ⚡ RF power set to: {metrics['rf_power']:.1f}W (baseline: {baseline_rf}W)")

        elif excursion_type == "temperature":
            # Calculate baseline for equipment type
            from config.thresholds import get_thresholds
            thresholds = get_thresholds()
            baseline_temp = thresholds["temperature_drift"].get(
                equipment_type,
                thresholds["temperature_drift"]["CMP"]
            )["baseline"]

            # Apply temperature drift (use provided value or generate)
            metrics["temperature"] = request.get("temperature", baseline_temp + random.uniform(6, 10))
            logger.info(f"   🌡️  Temperature set to: {metrics['temperature']:.1f}°C (baseline: {baseline_temp}°C)")

        # Check if explicit particle_count override provided (DISCOURAGED - bypasses physics)
        if "particle_count" in request:
            logger.warning(
                f"⚠️  MANUAL PARTICLE COUNT OVERRIDE: {request['particle_count']} - "
                f"Bypassing physics-based calculation (use for testing only)"
            )
            metrics["particle_count"] = request["particle_count"]
        else:
            # CALCULATE particle count from root cause (RECOMMENDED - physics-based)
            metrics["particle_count"] = service.calculate_particle_count_from_root_cause(
                equipment_type=equipment_type,
                root_cause=f"{excursion_type}_drift",
                root_cause_value=metrics["temperature"] if excursion_type == "temperature" else metrics["rf_power"],
                baseline_particle_count=baseline_particle_count
            )
            logger.info(
                f"   ✅ Physics calculation: {excursion_type} → particle_count={metrics['particle_count']} "
                f"(baseline: {baseline_particle_count})"
            )

        # Override any other specific metrics provided
        for key in ["chamber_pressure", "flow_rate"]:
            if key in request:
                metrics[key] = request[key]
        
        # Generate or use provided metadata (use problematic batch for excursions)
        metadata = request.get("metadata", service.generate_demo_metadata(is_excursion=True))
        
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
        if mongodb_config:
            writer = SensorDataWriter(
                mongodb_uri=mongodb_config["mongodb_uri"],
                database=mongodb_config["database_name"]
            )
            result = writer.write_sensor_data(data)
            writer.close()
            
            if result["success"]:
                logger.warning(f"🚨 Manual excursion injected for {equipment_id}: particle_count={metrics['particle_count']}")
                
                excursion_details = []
                if metrics["particle_count"] > 1000:
                    excursion_details.append(f"Particle: {metrics['particle_count']}")
                if abs(metrics["rf_power"] - 1450) > 100:
                    excursion_details.append(f"RF Power: {metrics['rf_power']}")
                if abs(metrics["temperature"] - 65) > 2:
                    excursion_details.append(f"Temperature: {metrics['temperature']}")
                
                # === STEP 3: Resume demo mode if it was active and auto_resume is enabled ===
                demo_resume_status = None
                if demo_was_active and auto_resume:
                    # Brief pause for log ordering (alert creation happens asynchronously via change stream)
                    logger.info("✅ Excursion injected - alert will be created asynchronously")
                    await asyncio.sleep(0.1)

                    logger.info("▶️  Resuming demo mode...")
                    resume_result = await service.start_demo_mode(mode="charts")
                    demo_resume_status = resume_result["status"]
                    logger.info(f"   ✅ Demo mode resumed: {demo_resume_status}")
                
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
                    "demo_mode": {
                        "was_active": demo_was_active,
                        "paused_for_injection": demo_was_active,
                        "auto_resumed": demo_was_active and auto_resume,
                        "resume_status": demo_resume_status
                    },
                    "note": "Alert creation and wafer generation are processing asynchronously. Check via WebSocket or API for updates."
                }
            else:
                logger.error(f"❌ Failed to write excursion data: {result.get('errors', [])}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to write excursion data: {result.get('errors', [])}"
                )
        else:
            raise HTTPException(status_code=500, detail="MongoDB config not available")
            
    except HTTPException:
        # Resume demo mode if it was active and an error occurred
        if 'demo_was_active' in locals() and demo_was_active and 'auto_resume' in locals() and auto_resume:
            try:
                logger.warning("⚠️  Error occurred, attempting to resume demo mode...")
                await service.start_demo_mode(mode="charts")
            except Exception as resume_error:
                logger.error(f"❌ Failed to resume demo mode after error: {resume_error}")
        raise
    except Exception as e:
        # Resume demo mode if it was active and an error occurred
        if 'demo_was_active' in locals() and demo_was_active and 'auto_resume' in locals() and auto_resume:
            try:
                logger.warning("⚠️  Error occurred, attempting to resume demo mode...")
                await service.start_demo_mode(mode="charts")
            except Exception as resume_error:
                logger.error(f"❌ Failed to resume demo mode after error: {resume_error}")
        logger.error(f"❌ Error injecting excursion: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to inject excursion: {str(e)}"
        )

@router.post("/alerts/resolve-all")
async def resolve_all_alerts():
    """
    Resolve all unresolved alerts in the collection
    
    This endpoint bulk resolves all alerts that are not already resolved.
    Useful for demo resets or cleaning up test data.
    
    Returns information about:
    - Success status
    - Message with count
    - Alerts resolved count
    - Alerts matched count
    """
    logger.info("🔄 POST /alerts/resolve-all - Bulk resolving all alerts")
    
    try:
        if not alert_manager_instance:
            logger.error("❌ Alert manager not initialized")
            raise HTTPException(status_code=500, detail="Alert manager not initialized")
        
        # Update all alerts that are not resolved
        result = alert_manager_instance.alerts_collection.update_many(
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
        
        logger.info(f"✅ Bulk resolved {result.modified_count} alerts")
        
        return {
            "success": True,
            "message": f"Successfully resolved {result.modified_count} alerts",
            "alerts_resolved": result.modified_count,
            "alerts_matched": result.matched_count
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error resolving all alerts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


logger.info("📦 Demo mode router initialized")

