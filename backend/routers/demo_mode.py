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
        "mode": "charts" | "agentic"    // Optional: Mode indicator (agentic sets probability to 0)
    }
    
    Returns detailed information about:
    - Start status
    - Configuration (mode, interval, excursion probability)
    - Reset statistics (baseline and anomalous readings seeded)
    - Equipment list
    """
    logger.info(f"🎬 POST /demo/start - Starting demo mode with config: {request}")
    
    try:
        service = get_demo_service()
        
        # Extract parameters from request
        mode = request.get("mode", "charts")
        custom_probability = request.get("excursion_probability")
        
        # Start demo mode through service
        result = await service.start_demo_mode(
            mode=mode,
            custom_probability=custom_probability
        )
        
        logger.info(f"✅ Demo mode started: {result['status']}")
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
        
        # Get original probability from env (default to 0.05)
        import os
        original_prob = float(os.getenv("DEMO_EXCURSION_PROBABILITY", "0.05"))
        
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
    Complete demo reset: Fix all equipment and restore healthy yield
    Stops demo mode, resolves alerts, injects healthy sensors, and generates high-yield wafers
    
    Returns information about:
    - Demo stopped status
    - Alerts resolved count
    - Excursion data cleared count
    - Healthy wafers generated count  
    - New average yield percentage
    - Equipment status and expected KPI changes
    """
    logger.info("🔄 POST /demo/reset - Resetting demo to healthy state")
    
    try:
        service = get_demo_service()
        
        results = {
            "alerts_resolved": 0,
            "healthy_sensors_injected": 0,
            "healthy_wafers_generated": 0,
            "new_yield": None,
            "demo_stopped": False,
            "excursion_data_cleared": 0
        }
        
        # Step 0: Stop demo mode first to prevent new excursions
        if service.is_active():
            logger.info("🛑 Stopping demo mode before reset...")
            original_prob = float(os.getenv("DEMO_EXCURSION_PROBABILITY", "0.05"))
            await service.stop_demo_mode(restore_probability=original_prob)
            results["demo_stopped"] = True
            logger.info("✅ Demo mode stopped successfully")
            
            # Wait for monitoring service to process the stop
            await asyncio.sleep(5)
        
        # Step 1: Resolve all open/acknowledged alerts
        if alert_manager_instance:
            unresolved_alerts = alert_manager_instance.alerts_collection.find({
                "status": {"$in": ["open", "acknowledged"]}
            })
            alert_ids = [str(alert["_id"]) for alert in unresolved_alerts]
            
            if alert_ids:
                update_result = alert_manager_instance.alerts_collection.update_many(
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
                logger.info(f"✅ Demo reset: Resolved {results['alerts_resolved']} alerts")
        
        # Step 1.5: Clear recent excursion sensor data
        # This prevents monitoring service from re-detecting old excursions
        try:
            if mongodb_client_instance and mongodb_config:
                sensor_collection = mongodb_client_instance[mongodb_config["database_name"]][
                    mongodb_config["timeseries_collection"]
                ]
                
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
                logger.info(f"✅ Cleared {delete_result.deleted_count} excursion sensor readings")
        except Exception as e:
            logger.error(f"❌ Error clearing excursion data: {e}")
        
        # Step 2: Inject healthy sensor data for all equipment
        # NOTE: Sensor injection is DISABLED to prevent RF power drift detection
        # Equipment health is determined by open alerts, not sensor values
        # Sensor readings will update naturally with next monitoring cycle
        equipment_ids = ["CMP_TOOL_01", "CMP_TOOL_02", "ETCH_01", "LITHO_01"]
        
        results["healthy_sensors_injected"] = 0  # Disabled
        logger.info(f"ℹ️  Demo reset: Sensor injection disabled (equipment health determined by alerts)")
        
        # Step 3: Generate healthy wafers to improve yield
        if mongodb_config:
            wafer_generator = WaferGenerator(
                mongodb_uri=mongodb_config["mongodb_uri"],
                database=mongodb_config["database_name"],
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
            "message": "Demo reset to healthy state complete",
            **results,
            "equipment_status": "All equipment restored to healthy operating conditions",
            "expected_kpi_changes": {
                "yield": f"~{results['new_yield']}%" if results['new_yield'] else "95-98%",
                "active_alerts": new_alerts_count,
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
    Manually inject an excursion into the sensor data
    
    Expected payload:
    {
        "equipment_id": "CMP_TOOL_01",  # Required
        "excursion_type": "particle",   # Optional: "particle", "rf_power", "temperature"
        "particle_count": 2500,          # Optional: Override specific metric
        "metadata": {...}                # Optional: Override metadata
    }
    
    Returns information about:
    - Injection status
    - Equipment ID
    - Excursion type and triggered values
    - Sensor event and timeseries IDs
    - Note about alert/wafer generation timing
    """
    logger.info(f"💉 POST /demo/inject-excursion - Injecting excursion: {request}")
    
    try:
        service = get_demo_service()
        
        # Get equipment ID (required)
        equipment_id = request.get("equipment_id")
        if not equipment_id:
            logger.error("❌ Missing required parameter: equipment_id")
            raise HTTPException(status_code=400, detail="equipment_id is required")
        
        # Generate base metrics with excursion
        metrics = service.generate_demo_metrics(equipment_id, is_excursion=True)
        
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
                logger.error(f"❌ Failed to write excursion data: {result.get('errors', [])}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to write excursion data: {result.get('errors', [])}"
                )
        else:
            raise HTTPException(status_code=500, detail="MongoDB config not available")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error injecting excursion: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to inject excursion: {str(e)}"
        )

@router.post("/demo/inject-pattern")
async def inject_pattern(request: Dict[str, Any] = Body(...)):
    """
    Manually inject a pattern-based excursion that evolves over time
    
    Expected payload:
    {
        "equipment_id": "CMP_TOOL_01",     # Required
        "pattern": "drift|spike|false_positive|oscillation",  # Required
        "target_value": 2000                # Optional: Override target particle count
    }
    
    Patterns:
    - drift: Gradual increase over 5-8 readings (filter degradation)
    - spike: Sudden persistent issue for 3-5 readings (equipment malfunction)
    - false_positive: Single spike then immediate return (sensor glitch - AI should filter)
    - oscillation: Cyclic up/down pattern for 6-10 readings (recurring process issue)
    
    Returns information about:
    - Injection status
    - Equipment ID and pattern type
    - Baseline and target values
    - Total stages
    - Note about pattern evolution timing
    """
    logger.info(f"🌊 POST /demo/inject-pattern - Injecting pattern: {request}")
    
    try:
        service = get_demo_service()
        
        equipment_id = request.get("equipment_id")
        pattern = request.get("pattern")
        target_value = request.get("target_value")
        
        # Inject pattern through service
        result = service.inject_pattern(
            equipment_id=equipment_id,
            pattern=pattern,
            target_value=target_value
        )
        
        logger.info(f"✅ Pattern injected: {result['pattern']} for {result['equipment_id']}")
        return result
        
    except ValueError as e:
        # Validation errors from service
        logger.error(f"❌ Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error injecting pattern: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to inject pattern: {str(e)}"
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

