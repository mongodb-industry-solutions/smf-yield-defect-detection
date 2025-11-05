"""
Demo Mode Service - Manages all demo mode data generation and state

This service encapsulates:
- Demo mode state management (active status, background tasks)
- Pattern-based anomaly generation for realistic monitoring scenarios
- Demo data generation for sensors and wafers
- Process context caching from MongoDB
"""

import logging
import asyncio
import random
import time
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List

from motor.motor_asyncio import AsyncIOMotorClient

# Import services
from services.sensor_data_writer import SensorDataWriter

# Import centralized threshold configuration
from config.thresholds import get_thresholds, get_particle_count_thresholds

# Configure logging
logger = logging.getLogger(__name__)


class DemoModeService:
    """
    Service class for managing demo mode functionality
    
    Handles:
    - Demo mode state (active, background tasks)
    - Sensor data generation with realistic metrics
    - Process context caching from MongoDB
    """
    
    def __init__(
        self,
        mongodb_uri: str,
        database_name: str,
        demo_interval_seconds: int = 60,
        demo_excursion_probability: float = 0.0
    ):
        """
        Initialize Demo Mode Service

        Args:
            mongodb_uri: MongoDB connection URI
            database_name: Database name
            demo_interval_seconds: Interval between demo data generation cycles
            demo_excursion_probability: Probability of generating an excursion (default: 0.0 for manual-only mode)
        """
        self.mongodb_uri = mongodb_uri
        self.database_name = database_name
        self.demo_interval_seconds = demo_interval_seconds
        self.demo_excursion_probability = demo_excursion_probability
        
        # Demo mode state
        self.demo_mode_active = False
        self.demo_task: Optional[asyncio.Task] = None
        self.last_activity_time: Optional[datetime] = None  # For auto-stop tracking

        # Lot processing scenario fields
        self.demo_scenario = "continuous"  # "continuous" or "lot_processing"
        self.demo_duration_seconds = None  # None = unlimited, number = time limit
        self.demo_start_time = None
        self.scripted_excursions = []  # Predetermined excursions at specific times
        self.wafer_counter = 0  # Track wafers processed in this lot
        self.lot_id = None  # Current lot being processed

        # Process context cache (loaded from MongoDB)
        self.process_context_cache: Dict[str, Any] = {
            "problematic_batches": [],
            "normal_batches": [],
            "recipes": [],
            "loaded": False
        }
        
        # Equipment IDs for demo generation
        self.equipment_ids = [
            "CMP_TOOL_01", "CMP_TOOL_02",
            "ETCH_01", "ETCH_02",
            "LITHO_01", "LITHO_02"
        ]
        
        # Persistent sensor writer (reuse connections across batches)
        logger.info("   🔗 Initializing persistent SensorDataWriter...")
        self.sensor_writer = SensorDataWriter(
            mongodb_uri=self.mongodb_uri,
            database=self.database_name
        )
        logger.info("   ✅ SensorDataWriter connection pool created (will be reused)")
        
        logger.info(
            f"🎬 DemoModeService initialized - "
            f"Interval: {demo_interval_seconds}s, "
            f"Excursion mode: {'Manual only' if demo_excursion_probability == 0 else f'{demo_excursion_probability * 100:.0f}% auto'}"
        )
        logger.info(f"   ♻️  SensorDataWriter: Persistent connection pool (avoids per-batch overhead)")

        # Start auto-stop background task
        asyncio.create_task(self._auto_stop_task())
        logger.info(f"   🕐 Auto-stop task started (2-minute inactivity timeout)")

    async def _auto_stop_task(self):
        """
        Background task to auto-stop demo when no users are active.
        Checks every 30 seconds for inactivity.
        Stops demo if no heartbeat for 2 minutes (120 seconds).
        """
        INACTIVITY_TIMEOUT_SECONDS = 120  # 2 minutes
        CHECK_INTERVAL_SECONDS = 30  # Check every 30 seconds

        logger.info("🕐 Auto-stop task running (checks every 30s, stops after 2min inactivity)")

        while True:
            try:
                await asyncio.sleep(CHECK_INTERVAL_SECONDS)

                # Only check if demo is active
                if not self.demo_mode_active:
                    continue

                # Skip if no activity time set yet
                if self.last_activity_time is None:
                    continue

                # Calculate idle time
                idle_time = (datetime.now(timezone.utc) - self.last_activity_time).total_seconds()

                # Check if exceeded inactivity timeout
                if idle_time > INACTIVITY_TIMEOUT_SECONDS:
                    logger.info(
                        f"🛑 Auto-stopping demo mode due to inactivity "
                        f"(idle for {idle_time:.0f}s, threshold: {INACTIVITY_TIMEOUT_SECONDS}s)"
                    )
                    await self.stop_demo_mode()
                    # Reset activity time after stopping
                    self.last_activity_time = None

            except Exception as e:
                logger.error(f"❌ Auto-stop task error: {e}", exc_info=True)
                # Continue running even if error occurs
                await asyncio.sleep(CHECK_INTERVAL_SECONDS)

    def get_status(self) -> Dict[str, Any]:
        """
        Get current demo mode status
        
        Returns:
            Dict containing demo mode status information
        """
        logger.debug("📊 Getting demo mode status")
        
        task_running = self.demo_task is not None and not self.demo_task.done()
        
        # Calculate rates for parallel equipment updates
        intervals_per_minute = 60 / self.demo_interval_seconds
        intervals_per_hour = 3600 / self.demo_interval_seconds
        equipment_count = len(self.equipment_ids)
        
        # Total data points (all equipment report each interval)
        total_per_minute = equipment_count * intervals_per_minute
        total_per_hour = equipment_count * intervals_per_hour
        total_per_2min = equipment_count * (120 / self.demo_interval_seconds)
        
        status = {
            "active": self.demo_mode_active,
            "task_running": task_running,
            "scenario": self.demo_scenario,
            "interval_seconds": self.demo_interval_seconds,
            "excursion_probability": self.demo_excursion_probability,
            "equipment_ids": self.equipment_ids,
            "parallel_mode": True,
            "expected_rate": {
                "per_interval": f"{equipment_count} readings (all equipment)",
                "per_minute": f"{total_per_minute:.0f} readings",
                "per_2_minutes": f"{total_per_2min:.0f} readings",
                "per_hour": f"{total_per_hour:.0f} readings",
                "excursions_per_hour": f"{total_per_hour * self.demo_excursion_probability:.0f}",
                "particle_alerts_per_hour": f"{total_per_hour * self.demo_excursion_probability * 0.7:.0f}"  # ~70% of excursions are particle
            },
            "note": f"Parallel mode: All {equipment_count} standardized equipment report simultaneously each interval"
        }

        logger.debug(f"📊 Demo mode status: active={status['active']}, task_running={task_running}")
        return status
    
    def is_active(self) -> bool:
        """Check if demo mode is currently active"""
        return self.demo_mode_active
    
    def set_excursion_probability(self, probability: float):
        """
        Set the excursion probability
        
        Args:
            probability: New probability value (0.0 - 1.0)
        """
        old_probability = self.demo_excursion_probability
        self.demo_excursion_probability = probability
        logger.info(
            f"🎲 Excursion probability changed: {old_probability} → {probability}"
        )
    
    async def load_process_context_ids(self) -> Dict[str, Any]:
        """
        Load real process context IDs from MongoDB for demo metadata
        
        Returns:
            Dict containing process context cache with batches and recipes
        """
        if self.process_context_cache["loaded"]:
            logger.info("⚡ Using cached process context")
            return self.process_context_cache
        
        try:
            start_time = time.time()
            logger.info("🔄 Loading process context from MongoDB...")
            
            async_client = AsyncIOMotorClient(self.mongodb_uri)
            async_db = async_client[self.database_name]
            
            # Fetch problematic slurry batches
            query_start = time.time()
            problematic_cursor = async_db.process_context.find({
                "is_problematic": True,
                "context_type": "slurry_batch"
            })
            self.process_context_cache["problematic_batches"] = [
                doc["context_id"] async for doc in problematic_cursor
            ]
            logger.info(f"   ⏱️  Problematic batches query: {(time.time() - query_start)*1000:.0f}ms")
            
            # Fetch normal slurry batches
            query_start = time.time()
            normal_cursor = async_db.process_context.find({
                "is_problematic": False,
                "context_type": "slurry_batch"
            })
            self.process_context_cache["normal_batches"] = [
                doc["context_id"] async for doc in normal_cursor
            ]
            logger.info(f"   ⏱️  Normal batches query: {(time.time() - query_start)*1000:.0f}ms")
            
            # Fetch recipe IDs
            query_start = time.time()
            recipe_cursor = async_db.process_context.find({
                "context_type": "recipe"
            })
            self.process_context_cache["recipes"] = [
                doc["context_id"] async for doc in recipe_cursor
            ]
            logger.info(f"   ⏱️  Recipes query: {(time.time() - query_start)*1000:.0f}ms")
            
            self.process_context_cache["loaded"] = True
            async_client.close()
            
            total_time = (time.time() - start_time) * 1000
            logger.info(
                f"✅ Loaded process context in {total_time:.0f}ms: "
                f"{len(self.process_context_cache['problematic_batches'])} problematic batches, "
                f"{len(self.process_context_cache['normal_batches'])} normal batches, "
                f"{len(self.process_context_cache['recipes'])} recipes"
            )
            logger.info(f"📋 Problematic batches: {self.process_context_cache['problematic_batches']}")
            logger.info(f"📋 Normal batches (first 5): {self.process_context_cache['normal_batches'][:5]}")
            logger.info(f"📋 Recipes: {self.process_context_cache['recipes']}")
            
            return self.process_context_cache
            
        except Exception as e:
            logger.error(f"Failed to load process context IDs: {e}")
            # Fallback to hardcoded values if MongoDB fails
            self.process_context_cache["problematic_batches"] = [
                "SB_2025_021", "SB_2025_043", "SB_2025_045", "SB_2025_047", "SB_2025_048"
            ]
            self.process_context_cache["normal_batches"] = [
                "SB_2025_003", "SB_2025_005", "SB_2025_010", "SB_2025_011", "SB_2025_012"
            ]
            self.process_context_cache["recipes"] = [
                "RECIPE_01", "RECIPE_02", "RECIPE_03", "RECIPE_04", "RECIPE_05"
            ]
            self.process_context_cache["loaded"] = True
            return self.process_context_cache
    
    def generate_demo_metrics(self, equipment_id: str, is_excursion: bool = False) -> dict:
        """
        Generate realistic sensor metrics for equipment monitoring
        
        Args:
            equipment_id: Equipment identifier
            is_excursion: Whether to generate an excursion
            
        Returns:
            dict: Sensor metrics
        """
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
        process_step = equipment_id.split("_")[0]  # For threshold lookups: CMP, ETCH, LITHO
        equipment_type = process_step
        # Map CMP to CMP_TOOL in base_metrics
        if equipment_type == "CMP":
            equipment_type = "CMP_TOOL"
        metrics = base_metrics.get(equipment_type, base_metrics["CMP_TOOL"]).copy()
        
        # Generate excursion if requested (using physics-based causal model)
        if is_excursion:
            # Use centralized thresholds for excursion generation
            thresholds = get_thresholds()

            # PHYSICS-BASED MODEL: Pick root cause (temperature or RF power)
            # Particle count will be CALCULATED from the root cause severity
            root_cause = random.choice(["rf_power_drift", "temperature_drift"])

            # Store baseline particle count before modification
            baseline_particle_count = metrics["particle_count"]

            if root_cause == "rf_power_drift":
                # Use equipment-specific threshold to generate realistic excursion
                if process_step in thresholds["rf_power_drift"]:
                    rf_threshold = thresholds["rf_power_drift"][process_step]["threshold"]
                    baseline_rf = thresholds["rf_power_drift"][process_step]["baseline"]
                    # Generate drift above threshold (1.5x to 3x threshold)
                    drift_amount = random.uniform(rf_threshold * 1.5, rf_threshold * 3)
                    # Apply drift in random direction
                    metrics["rf_power"] = baseline_rf + (drift_amount * random.choice([-1, 1]))

                    logger.debug(f"   💉 Generated RF power excursion: {metrics['rf_power']:.1f}W (baseline: {baseline_rf}W)")

            elif root_cause == "temperature_drift":
                # Use equipment-specific threshold to generate realistic excursion
                if process_step in thresholds["temperature_drift"]:
                    temp_threshold = thresholds["temperature_drift"][process_step]["threshold"]
                    baseline_temp = thresholds["temperature_drift"][process_step]["baseline"]
                    # Generate drift above threshold (1.0x to 2x threshold)
                    drift_amount = random.uniform(temp_threshold, temp_threshold * 2)
                    # Apply drift in positive direction (temperature usually increases)
                    metrics["temperature"] = baseline_temp + drift_amount

                    logger.debug(f"   💉 Generated temperature excursion: {metrics['temperature']:.1f}°C (baseline: {baseline_temp}°C)")

            # CALCULATE particle count from root cause (physics-based)
            metrics["particle_count"] = self.calculate_particle_count_from_root_cause(
                equipment_type=process_step,
                root_cause=root_cause,
                root_cause_value=metrics["temperature"] if root_cause == "temperature_drift" else metrics["rf_power"],
                baseline_particle_count=baseline_particle_count
            )

            logger.info(
                f"   ✅ Physics-based excursion: {root_cause} → particle_count={metrics['particle_count']} "
                f"(baseline: {baseline_particle_count})"
            )
        
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
    
    def generate_demo_metadata(self, is_excursion: bool = False) -> dict:
        """
        Generate realistic metadata using REAL process context IDs from MongoDB
        
        Args:
            is_excursion: Whether this is for an excursion (influences batch selection)
            
        Returns:
            dict: Metadata with lot_id, wafer_id, recipe_id, slurry_batch, operator_id
        """
        lot_number = random.randint(1, 50)
        wafer_number = random.randint(1, 25)
        
        # Use REAL slurry batch IDs from process_context collection
        if is_excursion and random.random() < 0.7:  # 70% chance to use problematic batch during excursion
            # Use real problematic batches from MongoDB
            if self.process_context_cache["problematic_batches"]:
                slurry_batch = random.choice(self.process_context_cache["problematic_batches"])
            else:
                # Fallback if not loaded yet
                slurry_batch = "SB_2025_021"
        else:
            # Use real normal batches from MongoDB
            if self.process_context_cache["normal_batches"]:
                slurry_batch = random.choice(self.process_context_cache["normal_batches"])
            else:
                # Fallback if not loaded yet
                slurry_batch = "SB_2025_003"
        
        # Use real recipe IDs from MongoDB
        if self.process_context_cache["recipes"]:
            recipe_id = random.choice(self.process_context_cache["recipes"])
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
        if is_excursion and slurry_batch in self.process_context_cache.get("problematic_batches", []):
            logger.info(f"🚨 Generated excursion metadata with PROBLEMATIC batch: {slurry_batch}")
        
        return metadata

    def calculate_particle_count_from_root_cause(
        self,
        equipment_type: str,
        root_cause: str,
        root_cause_value: float,
        baseline_particle_count: int = 450
    ) -> int:
        """
        Calculate particle count based on root cause severity (physics-based model).

        This implements the causal relationship in semiconductor manufacturing:
        - Temperature increase → More particle generation
        - RF power drift → Plasma instability → More particle generation

        Physics Model Calibration:
        - Temperature: Each 1°C above baseline → +150-200 particles
        - RF Power: Each 50W drift → +200-250 particles

        Calibrated to match existing alert thresholds:
        - Medium alert (1000): 3-4°C drift or 110-140W drift
        - High alert (1500): 6-7°C drift or 210-260W drift
        - Critical alert (2000): 9-10°C drift or 310-380W drift

        Args:
            equipment_type: Process step (CMP, ETCH, LITHO)
            root_cause: "temperature_drift" or "rf_power_drift"
            root_cause_value: Current temperature (°C) or RF power (W)
            baseline_particle_count: Normal particle count baseline

        Returns:
            int: Calculated particle count based on root cause severity
        """
        thresholds = get_thresholds()

        if root_cause == "temperature_drift":
            # Get baseline temperature for equipment type
            baseline_temp = thresholds["temperature_drift"].get(
                equipment_type,
                thresholds["temperature_drift"]["CMP"]
            )["baseline"]

            # Calculate temperature drift magnitude
            temp_drift = abs(root_cause_value - baseline_temp)

            # Linear model: ~150-200 particles per degree Celsius
            # Using randomization to simulate natural variation
            particles_per_degree = random.uniform(150, 200)
            particle_increase = int(temp_drift * particles_per_degree)

            logger.debug(
                f"   🌡️  Temperature physics: {temp_drift:.1f}°C drift → "
                f"+{particle_increase} particles (baseline: {baseline_particle_count})"
            )

        elif root_cause == "rf_power_drift":
            # Get baseline RF power for equipment type
            baseline_rf = thresholds["rf_power_drift"].get(
                equipment_type,
                thresholds["rf_power_drift"]["CMP"]
            )["baseline"]

            # Calculate RF power drift magnitude
            rf_drift = abs(root_cause_value - baseline_rf)

            # Linear model: ~4-5 particles per watt drift
            # Equivalently: ~200-250 particles per 50W drift
            particles_per_watt = random.uniform(4, 5)
            particle_increase = int(rf_drift * particles_per_watt)

            logger.debug(
                f"   ⚡ RF power physics: {rf_drift:.1f}W drift → "
                f"+{particle_increase} particles (baseline: {baseline_particle_count})"
            )
        else:
            logger.warning(f"⚠️  Unknown root cause: {root_cause}, using baseline")
            particle_increase = 0

        calculated_particle_count = baseline_particle_count + particle_increase

        return int(calculated_particle_count)

    async def demo_data_generator(self):
        """
        Generate normal sensor data with occasional anomalies - parallel for all equipment

        This is the main async loop that generates demo data continuously while demo mode is active.
        """
        logger.info(
            f"🎬 Demo data generator started - "
            f"Scenario: {self.demo_scenario}, "
            f"Interval: {self.demo_interval_seconds}s, "
            f"Excursion probability: {self.demo_excursion_probability}"
        )

        if self.demo_scenario.startswith("lot_processing_"):
            logger.info(f"📦 Processing lot {self.lot_id}: 25 wafers over 3 minutes")
        else:
            logger.info(
                f"📊 Generating parallel data for {len(self.equipment_ids)} equipment - "
                f"{60 // (120 // self.demo_interval_seconds)} data points per 2 minutes"
            )

        while self.demo_mode_active:
            try:
                # Check time limit for lot processing
                if self.demo_duration_seconds:
                    elapsed = (datetime.now(timezone.utc) - self.demo_start_time).total_seconds()
                    if elapsed >= self.demo_duration_seconds:
                        logger.info(f"⏱️ Demo completed after {elapsed:.0f}s")
                        # Auto-stop after duration
                        await self.stop_demo_mode()
                        break

                # Increment wafer counter for lot processing
                if self.demo_scenario.startswith("lot_processing_"):
                    self.wafer_counter += 1
                    if self.wafer_counter > 25:
                        logger.info(f"✅ Lot {self.lot_id} processing complete - 25 wafers processed")
                        await self.stop_demo_mode()
                        break

                    logger.info(f"🔵 Processing wafer {self.wafer_counter}/25 in lot {self.lot_id}")

                # Generate timestamp once for all equipment in this batch
                timestamp = datetime.utcnow()

                # Collect data for all equipment
                bulk_data = []
                excursion_count = 0
                particle_excursion_count = 0

                # Handle scripted excursions for lot processing
                excursion_equipment = None
                excursion_details = None

                if self.demo_scenario.startswith("lot_processing_") and self.scripted_excursions:
                    # Check if current wafer has a scripted excursion
                    for exc in self.scripted_excursions:
                        if exc["wafer"] == self.wafer_counter:
                            excursion_equipment = exc["equipment"]
                            excursion_details = exc
                            logger.info(f"⚠️ Scripted excursion at wafer {self.wafer_counter}: {exc}")
                            break
                else:
                    # Original logic: random excursions
                    if random.random() < self.demo_excursion_probability:
                        excursion_equipment = random.choice(self.equipment_ids)

                for equipment_id in self.equipment_ids:
                    # Check if this equipment has excursion
                    is_excursion = False
                    metrics = self.generate_demo_metrics(equipment_id, False)  # Start with normal

                    if equipment_id == excursion_equipment:
                        if excursion_details:
                            # Use scripted values
                            if excursion_details["type"] == "particle":
                                metrics["particle_count"] = excursion_details["value"]
                                is_excursion = True
                        else:
                            # Random excursion
                            metrics = self.generate_demo_metrics(equipment_id, True)
                            is_excursion = True

                        if is_excursion:
                            excursion_count += 1

                    # Generate metadata with lot information if applicable
                    metadata = self.generate_demo_metadata(is_excursion)
                    # Override lot_id for BOTH continuous and lot_processing modes if persistent lot exists
                    if self.lot_id:
                        # Extract numeric lot ID from LOT_2025_1234 → 1234
                        lot_num = self.lot_id.split("_")[-1]  # Gets "1234" or "101"
                        metadata["lot_id"] = self.lot_id
                        # For lot_processing, maintain sequential wafer IDs
                        if self.demo_scenario.startswith("lot_processing_"):
                            metadata["wafer_id"] = f"W_{lot_num}_{self.wafer_counter:02d}"  # W_101_15
                        else:
                            # For continuous mode, use random wafer numbers within the lot
                            metadata["wafer_id"] = f"W_{lot_num}_{random.randint(1, 25):02d}"  # W_1234_12

                    # Generate sensor data for this equipment
                    data = {
                        "equipment_id": equipment_id,
                        "process_step": equipment_id.split("_")[0],
                        "timestamp": timestamp,  # Use same timestamp for batch consistency
                        "metrics": metrics,
                        "metadata": metadata
                    }

                    bulk_data.append(data)
                    
                    # Track particle excursions for logging
                    if data['metrics']['particle_count'] > 1000:
                        particle_excursion_count += 1
                
                # Use persistent writer - NO new connection created!
                logger.debug(f"   ♻️  Reusing SensorDataWriter connection pool for {len(bulk_data)} records")
                batch_start = time.time()
                
                result = self.sensor_writer.bulk_write_sensor_data(bulk_data)

                batch_elapsed_ms = (time.time() - batch_start) * 1000
                logger.debug(f"   ⏱️  Bulk write completed in {batch_elapsed_ms:.0f}ms (connection reused)")

                if result["sensor_events"]["inserted"] > 0 or result["process_sensor_ts"]["inserted"] > 0:
                    logger.info(
                        f"✅ Demo batch generated: {len(bulk_data)} equipment readings, "
                        f"{excursion_count} excursions, {particle_excursion_count} particle alerts expected"
                    )
                    
                    # Log details if there were excursions
                    if particle_excursion_count > 0:
                        excursion_equipment_list = [
                            d["equipment_id"] for d in bulk_data 
                            if d["metrics"]["particle_count"] > 1000
                        ]
                        logger.warning(
                            f"🚨 Particle excursions on: {', '.join(excursion_equipment_list)} - "
                            f"Alerts will be created"
                        )
                else:
                    logger.error(f"❌ Failed to write demo batch: {result.get('errors', [])}")
                
                # Wait for next interval
                await asyncio.sleep(self.demo_interval_seconds)
                
            except asyncio.CancelledError:
                logger.info("🛑 Demo data generator cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error in demo data generator: {e}", exc_info=True)
                # Continue running even if one iteration fails
                await asyncio.sleep(self.demo_interval_seconds)
        
        logger.info("🛑 Demo data generator stopped")
    
    async def reset_demo_collections(self) -> Dict[str, int]:
        """
        Reset process_sensor_ts with fresh demo data
        
        Creates:
        1. Baseline normal readings (last 1 hour) for statistical context
        2. Anomalous patterns for AI agent testing
        
        NO vector embeddings - too slow for demo (6-9 second overhead)
        
        Returns:
            Dict with counts of baseline_readings and anomalous_readings
        """
        try:
            logger.info("🔄 Resetting demo collections...")
            
            # Get MongoDB connection
            async_client = AsyncIOMotorClient(self.mongodb_uri)
            async_db = async_client[self.database_name]
            
            # ========== STEP 1: CLEAR OLD DATA ==========
            # Delete demo data (keep production data if timestamp < 1 hour ago)
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
            
            # Clear recent data from process_sensor_ts
            delete_result = await async_db.process_sensor_ts.delete_many({
                "timestamp": {"$gte": cutoff_time}
            })
            logger.info(f"✅ Cleared {delete_result.deleted_count} recent records from process_sensor_ts")
            
            # ========== STEP 2: SEED BASELINE DATA (Last 1 Hour) ==========
            logger.info("📊 Seeding baseline normal readings for statistical context...")
            
            baseline_data = []
            
            # Generate 60 normal readings per equipment (1 per minute for last hour)
            for minutes_ago in range(60, 0, -1):
                timestamp = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
                
                for equipment_id in self.equipment_ids:
                    data = {
                        "equipment_id": equipment_id,
                        "process_step": equipment_id.split("_")[0],
                        "timestamp": timestamp,
                        "metrics": self.generate_demo_metrics(equipment_id, is_excursion=False),
                        "metadata": self.generate_demo_metadata(is_excursion=False)
                    }
                    baseline_data.append(data)
            
            # Bulk insert baseline data ONLY to process_sensor_ts (no alerts!)
            if baseline_data:
                # Write ONLY to process_sensor_ts to avoid triggering change stream alerts
                result = await async_db.process_sensor_ts.insert_many(baseline_data)
                logger.info(
                    f"✅ Seeded {len(result.inserted_ids)} baseline readings to process_sensor_ts only (no alerts)"
                )
            
            # ========== STEP 3: SEED ANOMALOUS PATTERNS (Last 10 Minutes) ==========
            logger.info("🚨 Seeding anomalous patterns for AI agent testing...")
            
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
                        
                        metrics = self.generate_demo_metrics(eq_id, is_excursion=False)
                        metrics["particle_count"] = int(particle_count)
                        
                        anomaly_data.append({
                            "equipment_id": eq_id,
                            "process_step": eq_id.split("_")[0],
                            "timestamp": timestamp,
                            "metrics": metrics,
                            "metadata": self.generate_demo_metadata(is_excursion=True)
                        })
                
                elif scenario["pattern"] == "spike":
                    # Sustained spike
                    for stage in range(scenario["stages"]):
                        timestamp = datetime.now(timezone.utc) - timedelta(
                            minutes=scenario["minutes_ago"] - stage
                        )
                        
                        metrics = self.generate_demo_metrics(eq_id, is_excursion=False)
                        metrics["particle_count"] = scenario["value"] + random.randint(-50, 50)
                        
                        anomaly_data.append({
                            "equipment_id": eq_id,
                            "process_step": eq_id.split("_")[0],
                            "timestamp": timestamp,
                            "metrics": metrics,
                            "metadata": self.generate_demo_metadata(is_excursion=True)
                        })
                
                elif scenario["pattern"] == "false_positive":
                    # Single spike then normal
                    for stage in range(2):
                        timestamp = datetime.now(timezone.utc) - timedelta(
                            minutes=scenario["minutes_ago"] - stage
                        )
                        
                        metrics = self.generate_demo_metrics(eq_id, is_excursion=False)
                        if stage == 0:
                            metrics["particle_count"] = scenario["value"]
                        # stage 1 returns to normal (already normal from generate_demo_metrics)
                        
                        anomaly_data.append({
                            "equipment_id": eq_id,
                            "process_step": eq_id.split("_")[0],
                            "timestamp": timestamp,
                            "metrics": metrics,
                            "metadata": self.generate_demo_metadata(is_excursion=stage == 0)
                        })
            
            # Bulk insert anomaly data ONLY to process_sensor_ts (no alerts!)
            if anomaly_data:
                # Write ONLY to process_sensor_ts to avoid triggering change stream alerts
                result = await async_db.process_sensor_ts.insert_many(anomaly_data)
                logger.info(
                    f"✅ Seeded {len(result.inserted_ids)} anomalous readings to process_sensor_ts only (no alerts)"
                )
            
            async_client.close()
            
            logger.info("✅ Demo collections reset complete!")
            
            return {
                "baseline_readings": len(baseline_data),
                "anomalous_readings": len(anomaly_data)
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to reset demo collections: {e}", exc_info=True)
            raise

    async def start_demo_mode(
        self,
        mode: str = "charts",
        custom_probability: Optional[float] = None,
        scenario: str = "continuous",
        duration_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Start demo mode data generation

        Args:
            mode: Mode indicator ("charts", "agentic", or "lot_processing")
            custom_probability: Optional custom excursion probability
            scenario: "continuous" or "lot_processing"
            duration_seconds: Optional duration limit in seconds

        Returns:
            Dict with start status and configuration
        """
        if self.demo_mode_active:
            logger.warning("⚠️  Demo mode already active")
            return {
                "status": "already_running",
                "message": "Demo mode is already active",
                "interval_seconds": self.demo_interval_seconds,
                "excursion_probability": self.demo_excursion_probability,
                "scenario": self.demo_scenario
            }

        try:
            # Store original probability for restoration later
            original_probability = self.demo_excursion_probability

            logger.info(f"🎬 Demo start request - mode: {mode}, scenario: {scenario}")

            # Set scenario
            self.demo_scenario = scenario

            # Handle continuous mode with 2-minute auto-stop
            if scenario == "continuous":
                # Configure 2-minute continuous mode
                self.demo_duration_seconds = 120  # 2 minutes
                self.wafer_counter = 0  # Track wafers in this continuous session
                # Generate persistent lot_id (use 1001-1999 range to avoid conflicts)
                import random
                lot_number = random.randint(1001, 1999)
                self.lot_id = f"LOT_2025_{lot_number:04d}"  # e.g., LOT_2025_1234
                logger.info(f"🎯 Continuous mode: Auto-stop after 2 minutes | Lot: {self.lot_id}")

            # Apply excursion probability settings AFTER scenario configuration
            # Priority: mode == "agentic" > custom_probability parameter
            # This ensures probability control works for ALL scenarios including "continuous"
            if mode == "agentic":
                self.demo_excursion_probability = 0.0
                logger.info("🤖 Agentic AI mode: Setting excursion probability to 0 (manual pattern injection only)")
            elif custom_probability is not None:
                self.demo_excursion_probability = float(custom_probability)
                logger.info(f"🎲 Overriding excursion probability to {self.demo_excursion_probability}")

            # Set duration if provided
            if duration_seconds is not None:
                self.demo_duration_seconds = duration_seconds
            
            # ========== LOAD REAL PROCESS CONTEXT IDs ==========
            await self.load_process_context_ids()
            # ===================================================
            
            # NOTE: Seeding is now handled by separate /api/demo/initialize-seed endpoint
            # This endpoint only starts continuous data generation

            # Set demo mode active flag and start time
            self.demo_mode_active = True
            self.demo_start_time = datetime.now(timezone.utc)

            # Create and start the demo task
            self.demo_task = asyncio.create_task(self.demo_data_generator())

            log_msg = f"🎬 Demo mode started successfully"
            if scenario.startswith("lot_processing_"):
                pattern = scenario.split("_")[-1]  # drift, spike, or oscillation
                log_msg = f"📦 Lot processing ({pattern}) started: {self.lot_id} - 25 wafers in 3 minutes"
            elif mode == "agentic":
                log_msg += f" with excursion probability: {self.demo_excursion_probability} (Agentic AI mode)"
            else:
                log_msg += f" with excursion probability: {self.demo_excursion_probability}"
            logger.info(log_msg)

            result = {
                "status": "started",
                "message": "Lot processing demo started" if scenario.startswith("lot_processing_") else "Demo mode started successfully",
                "mode": mode,
                "scenario": scenario,
                "interval_seconds": self.demo_interval_seconds,
                "excursion_probability": self.demo_excursion_probability,
                "original_probability": original_probability,
                "equipment_ids": self.equipment_ids,
            }


            return result
            
        except Exception as e:
            self.demo_mode_active = False
            logger.error(f"❌ Failed to start demo mode: {e}", exc_info=True)
            raise Exception(f"Failed to start demo mode: {str(e)}")
    
    async def stop_demo_mode(self, restore_probability: float = 0.0) -> Dict[str, Any]:
        """
        Stop demo mode data generation

        Args:
            restore_probability: Probability to restore (default: 0.0 for manual-only mode)

        Returns:
            Dict with stop status
        """
        # Store final status for lot processing before stopping
        final_status = {}
        if self.demo_scenario.startswith("lot_processing_"):
            final_status = {
                "lot_id": self.lot_id,
                "wafers_processed": self.wafer_counter,
                "total_wafers": 25,
                "completion_percentage": round((self.wafer_counter / 25) * 100),
            }
            logger.info(f"📦 Lot processing stopped: {self.wafer_counter}/25 wafers processed")

        # Restore original excursion probability
        self.demo_excursion_probability = restore_probability
        logger.info(f"🔄 Restored excursion probability to {restore_probability}")

        if not self.demo_mode_active:
            logger.warning("⚠️  Demo mode not active")
            return {
                "status": "not_running",
                "message": "Demo mode is not active"
            }

        try:
            # Set flag to stop the generator
            self.demo_mode_active = False

            # Cancel the task if it exists (don't wait for it)
            if self.demo_task and not self.demo_task.done():
                self.demo_task.cancel()
                logger.info("🛑 Demo task cancellation requested")
                # Don't await - just let it cancel in background

            self.demo_task = None

            # Reset lot processing state
            self.demo_scenario = "continuous"
            self.demo_duration_seconds = None
            self.demo_start_time = None
            self.scripted_excursions = []
            self.wafer_counter = 0
            self.lot_id = None

            logger.info("✅ Demo mode stopped successfully")
            logger.info("   ℹ️  SensorDataWriter connections kept open for next demo session")
            logger.info("   💡 Connections will be closed on service shutdown via cleanup()")

            result = {
                "status": "stopped",
                "message": "Demo mode stopped successfully",
                "note": "Sensor data will stop generating. Monitoring loops continue running."
            }

            # Add lot processing final status if applicable
            if final_status:
                result["lot_processing_summary"] = final_status

            return result

        except Exception as e:
            logger.error(f"❌ Error stopping demo mode: {e}", exc_info=True)
            raise Exception(f"Failed to stop demo mode: {str(e)}")
    
    def cleanup(self):
        """Clean up resources on service shutdown"""
        logger.info("🧹 Cleaning up DemoModeService resources...")
        
        if hasattr(self, 'sensor_writer') and self.sensor_writer:
            logger.info("   🔌 Closing SensorDataWriter connections...")
            self.sensor_writer.close()
            logger.info("   ✅ SensorDataWriter connections closed gracefully")
        else:
            logger.debug("   ⏭️  No SensorDataWriter to clean up")
        
        logger.info("✅ DemoModeService cleanup complete")
