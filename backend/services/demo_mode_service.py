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
        demo_excursion_probability: float = 0.05
    ):
        """
        Initialize Demo Mode Service

        Args:
            mongodb_uri: MongoDB connection URI
            database_name: Database name
            demo_interval_seconds: Interval between demo data generation cycles
            demo_excursion_probability: Probability of generating an excursion (0.0 - 1.0)
        """
        self.mongodb_uri = mongodb_uri
        self.database_name = database_name
        self.demo_interval_seconds = demo_interval_seconds
        self.demo_excursion_probability = demo_excursion_probability
        
        # Demo mode state
        self.demo_mode_active = False
        self.demo_task: Optional[asyncio.Task] = None

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
            f"Excursion probability: {demo_excursion_probability}"
        )
        logger.info(f"   ♻️  SensorDataWriter: Persistent connection pool (avoids per-batch overhead)")

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

        # Add lot processing specific status
        if self.demo_scenario.startswith("lot_processing_"):
            if self.demo_start_time:
                elapsed_seconds = (datetime.now(timezone.utc) - self.demo_start_time).total_seconds()
                remaining_seconds = max(0, (self.demo_duration_seconds or 0) - elapsed_seconds)
            else:
                elapsed_seconds = 0
                remaining_seconds = self.demo_duration_seconds or 0

            status["lot_processing"] = {
                "lot_id": self.lot_id,
                "current_wafer": self.wafer_counter,
                "total_wafers": 25,
                "elapsed_seconds": round(elapsed_seconds),
                "remaining_seconds": round(remaining_seconds),
                "duration_seconds": self.demo_duration_seconds,
                "progress_percentage": round((self.wafer_counter / 25) * 100) if self.wafer_counter > 0 else 0
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
        
        # Generate excursion if requested
        if is_excursion:
            # Use centralized thresholds for excursion generation
            thresholds = get_thresholds()
            excursion_type = random.choice(["particle_excursion", "rf_power_drift", "temperature_drift"])
            
            if excursion_type == "particle_excursion":
                # Generate above critical threshold
                particle_critical = thresholds["particle_count"]["critical"]
                metrics["particle_count"] = random.randint(particle_critical + 100, particle_critical + 2000)
            elif excursion_type == "rf_power_drift":
                # Use equipment-specific threshold to generate realistic excursion
                if process_step in thresholds["rf_power_drift"]:
                    rf_threshold = thresholds["rf_power_drift"][process_step]["threshold"]
                    baseline_rf = thresholds["rf_power_drift"][process_step]["baseline"]
                    # Generate drift above threshold (1.5x to 3x threshold)
                    drift_amount = random.uniform(rf_threshold * 1.5, rf_threshold * 3)
                    # Apply drift in random direction
                    metrics["rf_power"] = baseline_rf + (drift_amount * random.choice([-1, 1]))
            elif excursion_type == "temperature_drift":
                # Use equipment-specific threshold to generate realistic excursion
                if process_step in thresholds["temperature_drift"]:
                    temp_threshold = thresholds["temperature_drift"][process_step]["threshold"]
                    baseline_temp = thresholds["temperature_drift"][process_step]["baseline"]
                    # Generate drift above threshold (1.0x to 2x threshold)
                    drift_amount = random.uniform(temp_threshold, temp_threshold * 2)
                    # Apply drift in positive direction (temperature usually increases)
                    metrics["temperature"] = baseline_temp + drift_amount
        
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

    async def bulk_insert_lot_scenario(self, scenario: str) -> Dict[str, Any]:
        """
        Bulk insert all sensor data for a lot processing scenario at once (no 3-minute wait).
        Creates only ONE alert per lot for drift scenarios.

        Args:
            scenario: "lot_processing_drift", "lot_processing_spike", or "lot_processing_oscillation"

        Returns:
            Dict with lot_id, total_wafers, pattern, and sensor data insertion status
        """
        try:
            import random
            from datetime import timedelta

            # Generate unique lot number
            lot_number = random.randint(101, 999)
            lot_id = f"LOT_2025_{lot_number:03d}"
            lot_num = str(lot_number).zfill(3)

            # Extract pattern
            pattern = scenario.split("_")[-1]  # drift, spike, oscillation

            # Map lot processing scenarios to standard agentic AI scenario IDs
            # This enables reusing lot processing alerts in agentic AI mode
            SCENARIO_MAPPING = {
                "lot_processing_drift": "gradual_drift",
                "lot_processing_spike": "sudden_spike",
                "lot_processing_oscillation": "oscillating_pattern"
            }
            scenario_id_for_agents = SCENARIO_MAPPING.get(scenario, "gradual_drift")

            logger.info(f"📦 Scenario mapping: {scenario} → {scenario_id_for_agents} (agentic AI compatible)")

            # Define excursion patterns (aligned with scenario_metadata.json)
            if scenario == "lot_processing_drift":
                # Aligned with gradual_drift scenario: linear drift from 950→1150
                # Represents compressed view of scenario anomaly window (minutes 75-120)
                # Peak at 1150 matches scenario ground truth
                scripted_excursions = [
                    {"wafer": 10, "equipment": "CMP_TOOL_01", "type": "particle", "value": 950},
                    {"wafer": 11, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1020},  # MEDIUM (first breach)
                    {"wafer": 12, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1040},
                    {"wafer": 13, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1055},
                    {"wafer": 14, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1070},
                    {"wafer": 15, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1085},
                    {"wafer": 16, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1095},
                    {"wafer": 17, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1105},
                    {"wafer": 18, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1115},
                    {"wafer": 19, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1130},
                    {"wafer": 20, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1140},
                    {"wafer": 21, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1145},
                    {"wafer": 22, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1148},
                    {"wafer": 23, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1150},  # Peak (matches scenario)
                    {"wafer": 24, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1150},
                    {"wafer": 25, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1150},
                ]
            elif scenario == "lot_processing_spike":
                # Aligned with sudden_spike scenario: single spike to 1200, then return to normal
                # Equipment: ETCH_01 (matches scenario metadata)
                # Peak at 1200 matches scenario ground truth
                scripted_excursions = [
                    {"wafer": 15, "equipment": "ETCH_01", "type": "particle", "value": 1200},  # MEDIUM (single spike)
                    {"wafer": 16, "equipment": "ETCH_01", "type": "particle", "value": 450},   # Return to normal
                    {"wafer": 17, "equipment": "ETCH_01", "type": "particle", "value": 460},
                ]
            elif scenario == "lot_processing_oscillation":
                # Aligned with oscillating_pattern scenario: oscillates 600-1100, ~6-wafer period
                # Equipment: CMP_TOOL_02 (matches scenario metadata)
                # Only 1-2 peaks cross threshold at ~1050 (matches scenario peak value)
                scripted_excursions = [
                    # Cycle 1: Rising to first peak
                    {"wafer": 5, "equipment": "CMP_TOOL_02", "type": "particle", "value": 950},
                    {"wafer": 6, "equipment": "CMP_TOOL_02", "type": "particle", "value": 1000},  # Peak 1 (at threshold)
                    {"wafer": 7, "equipment": "CMP_TOOL_02", "type": "particle", "value": 900},
                    {"wafer": 8, "equipment": "CMP_TOOL_02", "type": "particle", "value": 650},

                    # Cycle 2: Rising but stay below threshold
                    {"wafer": 11, "equipment": "CMP_TOOL_02", "type": "particle", "value": 920},
                    {"wafer": 12, "equipment": "CMP_TOOL_02", "type": "particle", "value": 980},  # Near threshold but below
                    {"wafer": 13, "equipment": "CMP_TOOL_02", "type": "particle", "value": 850},
                    {"wafer": 14, "equipment": "CMP_TOOL_02", "type": "particle", "value": 630},

                    # Cycle 3: Rising to second peak (breach)
                    {"wafer": 17, "equipment": "CMP_TOOL_02", "type": "particle", "value": 940},
                    {"wafer": 18, "equipment": "CMP_TOOL_02", "type": "particle", "value": 1020},
                    {"wafer": 19, "equipment": "CMP_TOOL_02", "type": "particle", "value": 1050},  # Peak 2 (ONLY breach)
                    {"wafer": 20, "equipment": "CMP_TOOL_02", "type": "particle", "value": 880},
                    {"wafer": 21, "equipment": "CMP_TOOL_02", "type": "particle", "value": 670},

                    # Cycle 4: Partial cycle ending
                    {"wafer": 24, "equipment": "CMP_TOOL_02", "type": "particle", "value": 850},
                ]
            else:
                scripted_excursions = []

            # Create lookup dict for excursions
            excursion_map = {exc["wafer"]: exc for exc in scripted_excursions}

            # Generate sensor data for all 25 wafers
            base_time = datetime.now(timezone.utc)
            bulk_data = []

            logger.info(f"📦 Bulk generating {pattern} scenario for lot {lot_id} (25 wafers)")

            for wafer_num in range(1, 26):
                # Each wafer gets a timestamp 7.2s apart (simulates 3-minute processing)
                timestamp = base_time + timedelta(seconds=(wafer_num - 1) * 7.2)

                # Generate data for all equipment at this wafer's timestamp
                for equipment_id in self.equipment_ids:
                    # Check if this wafer/equipment has scripted excursion
                    is_excursion = False
                    metrics = self.generate_demo_metrics(equipment_id, False)

                    if wafer_num in excursion_map and equipment_id == excursion_map[wafer_num]["equipment"]:
                        exc = excursion_map[wafer_num]
                        if exc["type"] == "particle":
                            metrics["particle_count"] = exc["value"]
                            is_excursion = True

                    # Generate metadata with lot/wafer info
                    metadata = self.generate_demo_metadata(is_excursion)
                    metadata["lot_id"] = lot_id
                    metadata["wafer_id"] = f"W_{lot_num}_{wafer_num:02d}"

                    # Add scenario metadata for agentic AI integration
                    # This allows lot processing alerts to be selected and analyzed in agentic AI mode
                    metadata["scenario_id"] = scenario_id_for_agents  # "gradual_drift", "sudden_spike", etc.
                    metadata["pattern_type"] = pattern  # "drift", "spike", "oscillation"
                    metadata["is_lot_processing_scenario"] = True

                    # Mark first excursion for single alert creation
                    if is_excursion and pattern == "drift" and wafer_num == 11:
                        # For drift, mark wafer 11 (first MEDIUM breach) as the trigger
                        metadata["is_first_drift_excursion"] = True
                    elif is_excursion and pattern == "spike" and wafer_num == 15:
                        # For spike, mark wafer 15 as trigger
                        metadata["is_first_spike_excursion"] = True
                    elif is_excursion and pattern == "oscillation" and wafer_num == 12:
                        # For oscillation, mark wafer 12 as trigger
                        metadata["is_first_oscillation_excursion"] = True

                    data = {
                        "equipment_id": equipment_id,
                        "process_step": equipment_id.split("_")[0],
                        "timestamp": timestamp,
                        "metrics": metrics,
                        "metadata": metadata
                    }
                    bulk_data.append(data)

            # Bulk write all sensor data at once
            logger.info(f"💾 Inserting {len(bulk_data)} sensor readings for {lot_id}...")
            result = self.sensor_writer.bulk_write_sensor_data(bulk_data)

            logger.info(
                f"✅ Bulk insert complete: {result['sensor_events']['inserted']} sensor_events, "
                f"{result['process_sensor_ts']['inserted']} time series records"
            )

            # Return summary
            return {
                "status": "success",
                "lot_id": lot_id,
                "total_wafers": 25,
                "pattern": pattern,
                "sensor_records_inserted": len(bulk_data),
                "excursion_wafers": list(excursion_map.keys()),
                "message": f"Lot {lot_id} ({pattern}) data inserted successfully. Alerts will be generated shortly."
            }

        except Exception as e:
            logger.error(f"❌ Failed to bulk insert lot scenario: {e}", exc_info=True)
            raise Exception(f"Failed to bulk insert lot scenario: {str(e)}")

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

            # Handle lot processing scenarios (drift, spike, oscillation)
            elif scenario in ["lot_processing_drift", "lot_processing_spike", "lot_processing_oscillation"]:
                # Configure for 3-minute lot processing
                self.demo_duration_seconds = 180  # 3 minutes
                self.demo_interval_seconds = 7.2  # Process 25 wafers in 3 minutes (180/25)
                self.demo_excursion_probability = 0  # No random excursions
                self.wafer_counter = 0
                # Generate unique lot number (101-999) to avoid conflicts with continuous mode (1-50)
                # This ensures each lot processing run has unique wafer IDs
                import random
                lot_number = random.randint(101, 999)  # Use 101-999 range for lot processing
                self.lot_id = f"LOT_2025_{lot_number:03d}"  # e.g., LOT_2025_342 (matches continuous mode format)

                # Define different excursion patterns based on scenario (aligned with scenario_metadata.json)
                # NOTE: Patterns now match scenario ground truth for accurate AI agent analysis
                if scenario == "lot_processing_drift":
                    # Aligned with gradual_drift scenario: linear drift 950→1150
                    # Represents compressed view of scenario anomaly window (minutes 75-120)
                    self.scripted_excursions = [
                        {"wafer": 10, "equipment": "CMP_TOOL_01", "type": "particle", "value": 950},
                        {"wafer": 11, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1020},  # MEDIUM (first breach)
                        {"wafer": 12, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1040},
                        {"wafer": 13, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1055},
                        {"wafer": 14, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1070},
                        {"wafer": 15, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1085},
                        {"wafer": 16, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1095},
                        {"wafer": 17, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1105},
                        {"wafer": 18, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1115},
                        {"wafer": 19, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1130},
                        {"wafer": 20, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1140},
                        {"wafer": 21, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1145},
                        {"wafer": 22, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1148},
                        {"wafer": 23, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1150},  # Peak
                        {"wafer": 24, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1150},
                        {"wafer": 25, "equipment": "CMP_TOOL_01", "type": "particle", "value": 1150},
                    ]
                    logger.info(f"📦 Lot processing DRIFT: Gradual particle increase wafers 10-25 (950→1150)")

                elif scenario == "lot_processing_spike":
                    # Aligned with sudden_spike scenario: single spike to 1200, then return to normal
                    # Equipment: ETCH_01 (matches scenario metadata)
                    self.scripted_excursions = [
                        {"wafer": 15, "equipment": "ETCH_01", "type": "particle", "value": 1200},  # MEDIUM (single spike)
                        {"wafer": 16, "equipment": "ETCH_01", "type": "particle", "value": 450},   # Return to normal
                        {"wafer": 17, "equipment": "ETCH_01", "type": "particle", "value": 460},
                    ]
                    logger.info(f"📦 Lot processing SPIKE: Sudden spike at wafer 15 (1200)")

                elif scenario == "lot_processing_oscillation":
                    # Aligned with oscillating_pattern scenario: oscillates 600-1100, ~6-wafer period
                    # Equipment: CMP_TOOL_02 (matches scenario metadata)
                    self.scripted_excursions = [
                        # Cycle 1: Rising to first peak
                        {"wafer": 5, "equipment": "CMP_TOOL_02", "type": "particle", "value": 950},
                        {"wafer": 6, "equipment": "CMP_TOOL_02", "type": "particle", "value": 1000},  # Peak 1 (at threshold)
                        {"wafer": 7, "equipment": "CMP_TOOL_02", "type": "particle", "value": 900},
                        {"wafer": 8, "equipment": "CMP_TOOL_02", "type": "particle", "value": 650},
                        # Cycle 2: Rising but stay below threshold
                        {"wafer": 11, "equipment": "CMP_TOOL_02", "type": "particle", "value": 920},
                        {"wafer": 12, "equipment": "CMP_TOOL_02", "type": "particle", "value": 980},  # Near threshold but below
                        {"wafer": 13, "equipment": "CMP_TOOL_02", "type": "particle", "value": 850},
                        {"wafer": 14, "equipment": "CMP_TOOL_02", "type": "particle", "value": 630},
                        # Cycle 3: Rising to second peak (breach)
                        {"wafer": 17, "equipment": "CMP_TOOL_02", "type": "particle", "value": 940},
                        {"wafer": 18, "equipment": "CMP_TOOL_02", "type": "particle", "value": 1020},
                        {"wafer": 19, "equipment": "CMP_TOOL_02", "type": "particle", "value": 1050},  # Peak 2 (ONLY breach)
                        {"wafer": 20, "equipment": "CMP_TOOL_02", "type": "particle", "value": 880},
                        {"wafer": 21, "equipment": "CMP_TOOL_02", "type": "particle", "value": 670},
                        # Cycle 4: Partial cycle ending
                        {"wafer": 24, "equipment": "CMP_TOOL_02", "type": "particle", "value": 850},
                    ]
                    logger.info(f"📦 Lot processing OSCILLATION: Cyclic pattern wafers 5-24 (600-1100)")

            # Check if mode is "agentic" - if so, set probability to 0
            elif mode == "agentic":
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

            if scenario.startswith("lot_processing_"):
                # Determine excursion wafers based on scenario
                pattern = scenario.split("_")[-1]
                if pattern == "drift":
                    excursion_wafers = list(range(10, 18))  # 10-17
                    note = "Gradual particle increase at wafers 10-17"
                elif pattern == "spike":
                    excursion_wafers = [15, 16, 17]
                    note = "Sudden particle spike at wafer 15"
                elif pattern == "oscillation":
                    excursion_wafers = list(range(12, 20))  # 12-19
                    note = "Cyclic particle pattern at wafers 12-19"
                else:
                    excursion_wafers = [15, 16, 17]
                    note = "Particle contamination will occur"

                result["lot_processing"] = {
                    "lot_id": self.lot_id,
                    "total_wafers": 25,
                    "duration_seconds": self.demo_duration_seconds,
                    "pattern": pattern,
                    "excursions_at_wafers": excursion_wafers,
                    "note": note
                }

            return result
            
        except Exception as e:
            self.demo_mode_active = False
            logger.error(f"❌ Failed to start demo mode: {e}", exc_info=True)
            raise Exception(f"Failed to start demo mode: {str(e)}")
    
    async def stop_demo_mode(self, restore_probability: float = 0.05) -> Dict[str, Any]:
        """
        Stop demo mode data generation

        Args:
            restore_probability: Probability to restore (from environment variable)

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
