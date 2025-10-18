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

# Configure logging
logger = logging.getLogger(__name__)


class DemoModeService:
    """
    Service class for managing demo mode functionality
    
    Handles:
    - Demo mode state (active, background tasks)
    - Pattern-based excursion generation (drift, spike, false_positive, oscillation)
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
        
        # Pattern state for realistic anomaly scenarios
        # Structure: {equipment_id: {"pattern": "drift", "stage": 3, "baseline_value": 450, ...}}
        self.equipment_pattern_state: Dict[str, Dict[str, Any]] = {}
        
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
        
        logger.info(
            f"🎬 DemoModeService initialized - "
            f"Interval: {demo_interval_seconds}s, "
            f"Excursion probability: {demo_excursion_probability}"
        )
    
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
    
    def initialize_pattern_state(self):
        """Initialize pattern state for realistic demo scenarios with industry-aligned patterns"""
        self.equipment_pattern_state = {}
        
        for eq_id in self.equipment_ids:
            self.equipment_pattern_state[eq_id] = {
                "pattern": "normal",
                "stage": 0,
                "baseline_value": None,
                "target_value": None,
                "started_at": None,
                "total_stages": 0
            }
        
        logger.info("✅ Initialized pattern-based demo state for realistic anomaly scenarios")
    
    def should_create_pattern(self, equipment_id: str) -> bool:
        """
        Decide if equipment should start a new pattern based on demo_excursion_probability
        
        Args:
            equipment_id: Equipment identifier
            
        Returns:
            bool: True if should create a new pattern
        """
        state = self.equipment_pattern_state.get(equipment_id, {})
        
        # Already in a pattern? Continue it
        if state.get("pattern") != "normal":
            return False
        
        # Use global excursion probability (will be 0 in agentic mode)
        return random.random() < self.demo_excursion_probability
    
    def get_pattern_metrics(self, equipment_id: str, base_metrics: dict) -> tuple:
        """
        Generate metrics following realistic industry patterns for monitoring agent validation
        
        Patterns based on industry research (NVIDIA NV-Tesseract, semiconductor fab operations):
        - drift: Gradual increase (filter degradation, contamination buildup)
        - spike: Sudden persistent issue (equipment malfunction)
        - false_positive: Single spike returning to normal (sensor glitch, transient)
        - oscillation: Recurring pattern (cyclic process issue)
        
        Args:
            equipment_id: Equipment identifier
            base_metrics: Base metrics dict to modify
            
        Returns:
            tuple: (metrics_dict, is_real_excursion_bool)
        """
        state = self.equipment_pattern_state.get(equipment_id, {})
        
        # Initialize new pattern if needed
        if state.get("pattern") == "normal" and self.should_create_pattern(equipment_id):
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
                state["target_value"] = random.randint(2000, 3500)  # CRITICAL severity range
                state["total_stages"] = random.randint(5, 8)  # 5-8 readings to reach target
                logger.info(
                    f"📈 {equipment_id}: Starting DRIFT pattern "
                    f"({state['baseline_value']} → {state['target_value']} over {state['total_stages']} readings)"
                )
            elif pattern_type == "spike":
                state["target_value"] = random.randint(2500, 4000)  # CRITICAL severity range
                state["total_stages"] = random.randint(3, 5)  # Persist 3-5 readings
                logger.info(
                    f"⚡ {equipment_id}: Starting SPIKE pattern "
                    f"(value: {state['target_value']}, persists: {state['total_stages']} readings)"
                )
            elif pattern_type == "false_positive":
                state["target_value"] = random.randint(1050, 1200)  # Just over threshold
                state["total_stages"] = 1  # Single spike only
                logger.info(
                    f"🔔 {equipment_id}: Starting FALSE_POSITIVE pattern "
                    f"(spike to {state['target_value']}, immediate return)"
                )
            elif pattern_type == "oscillation":
                state["target_value"] = random.randint(2000, 3000)  # CRITICAL severity range
                state["total_stages"] = random.randint(6, 10)
                logger.info(
                    f"🌊 {equipment_id}: Starting OSCILLATION pattern "
                    f"(amplitude: {state['target_value']}, cycles: {state['total_stages']})"
                )
        
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
                # Reset particle count to baseline after pattern completes
                metrics["particle_count"] = baseline
                logger.info(
                    f"✅ {equipment_id}: DRIFT pattern completed ({baseline} → {target}), "
                    f"particle count reset to baseline"
                )
        
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
                # Reset particle count to baseline after pattern completes
                metrics["particle_count"] = state["baseline_value"]
                logger.info(f"✅ {equipment_id}: SPIKE pattern completed, particle count reset to baseline")
        
        elif pattern == "false_positive":
            # Single spike then immediate return (sensor glitch - LLM should filter this!)
            if state["stage"] == 0:
                metrics["particle_count"] = state["target_value"]
                logger.info(
                    f"🔔 {equipment_id}: FALSE_POSITIVE spike at {state['target_value']} "
                    f"(monitoring agent should filter)"
                )
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
            
            # Only trigger alert on FIRST stage of the pattern (one pattern = one alert)
            # Even though oscillation exceeds threshold multiple times, we only want ONE alert
            is_real_excursion = (stage == 0)
            
            state["stage"] += 1
            
            if state["stage"] >= state["total_stages"]:
                state["pattern"] = "normal"
                state["stage"] = 0
                # Reset particle count to baseline after pattern completes
                metrics["particle_count"] = baseline
                logger.info(f"✅ {equipment_id}: OSCILLATION pattern completed, particle count reset to baseline")
        
        return metrics, is_real_excursion
    
    def generate_demo_metrics(self, equipment_id: str, is_excursion: bool = False) -> dict:
        """
        Generate realistic sensor metrics with pattern-based anomalies for monitoring agent validation
        
        Args:
            equipment_id: Equipment identifier
            is_excursion: Whether to generate an excursion (fallback if pattern state not initialized)
            
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
        equipment_type = equipment_id.split("_")[0]
        # Map CMP to CMP_TOOL in base_metrics
        if equipment_type == "CMP":
            equipment_type = "CMP_TOOL"
        metrics = base_metrics.get(equipment_type, base_metrics["CMP_TOOL"]).copy()
        
        # Use pattern-based generation if pattern state exists
        if equipment_id in self.equipment_pattern_state:
            metrics, _ = self.get_pattern_metrics(equipment_id, metrics)
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
            f"Interval: {self.demo_interval_seconds}s, "
            f"Excursion probability: {self.demo_excursion_probability}"
        )
        logger.info(
            f"📊 Generating parallel data for {len(self.equipment_ids)} equipment - "
            f"{60 // (120 // self.demo_interval_seconds)} data points per 2 minutes"
        )
        
        while self.demo_mode_active:
            try:
                # Generate timestamp once for all equipment in this batch
                timestamp = datetime.now(timezone.utc)
                
                # Collect data for all equipment
                bulk_data = []
                excursion_count = 0
                particle_excursion_count = 0
                
                # Pick at most ONE equipment to have excursion (prevents multiple simultaneous Bedrock calls)
                excursion_equipment = None
                if random.random() < self.demo_excursion_probability:
                    excursion_equipment = random.choice(self.equipment_ids)
                
                for equipment_id in self.equipment_ids:
                    # Only the selected equipment gets excursion
                    is_excursion = (equipment_id == excursion_equipment)
                    if is_excursion:
                        excursion_count += 1
                    
                    # Generate sensor data for this equipment
                    data = {
                        "equipment_id": equipment_id,
                        "process_step": equipment_id.split("_")[0],
                        "timestamp": timestamp,  # Use same timestamp for batch consistency
                        "metrics": self.generate_demo_metrics(equipment_id, is_excursion),
                        "metadata": self.generate_demo_metadata(is_excursion)
                    }
                    
                    bulk_data.append(data)
                    
                    # Track particle excursions for logging
                    if data['metrics']['particle_count'] > 1000:
                        particle_excursion_count += 1
                
                # Use bulk write for all equipment data
                writer = SensorDataWriter(mongodb_uri=self.mongodb_uri, database=self.database_name)
                result = writer.bulk_write_sensor_data(bulk_data)
                writer.close()
                
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
    
    async def start_demo_mode(self, mode: str = "charts", custom_probability: Optional[float] = None) -> Dict[str, Any]:
        """
        Start demo mode data generation
        
        Args:
            mode: Mode indicator ("charts" or "agentic")
            custom_probability: Optional custom excursion probability
            
        Returns:
            Dict with start status and configuration
        """
        if self.demo_mode_active:
            logger.warning("⚠️  Demo mode already active")
            return {
                "status": "already_running",
                "message": "Demo mode is already active",
                "interval_seconds": self.demo_interval_seconds,
                "excursion_probability": self.demo_excursion_probability
            }
        
        try:
            # Store original probability for restoration later
            original_probability = self.demo_excursion_probability
            
            logger.info(f"🎬 Demo start request - mode: {mode}")
            
            # Check if mode is "agentic" - if so, set probability to 0
            if mode == "agentic":
                self.demo_excursion_probability = 0.0
                logger.info("🤖 Agentic AI mode: Setting excursion probability to 0 (manual pattern injection only)")
            elif custom_probability is not None:
                self.demo_excursion_probability = float(custom_probability)
                logger.info(f"🎲 Overriding excursion probability to {self.demo_excursion_probability}")
            
            # ========== LOAD REAL PROCESS CONTEXT IDs ==========
            await self.load_process_context_ids()
            # ===================================================
            
            # ========== RESET & SEED COLLECTIONS ==========
            reset_stats = await self.reset_demo_collections()
            logger.info(f"✅ Collections reset: {reset_stats}")
            # ==============================================
            
            # Initialize pattern state for realistic anomaly scenarios
            self.initialize_pattern_state()
            
            # Set demo mode active flag
            self.demo_mode_active = True
            
            # Create and start the demo task
            self.demo_task = asyncio.create_task(self.demo_data_generator())
            
            log_msg = f"🎬 Demo mode started successfully with excursion probability: {self.demo_excursion_probability}"
            if mode == "agentic":
                log_msg += " (Agentic AI mode - anomalies disabled for manual pattern injection)"
            logger.info(log_msg)
            
            return {
                "status": "started",
                "message": "Demo mode started successfully",
                "mode": mode,
                "reset_stats": reset_stats,
                "interval_seconds": self.demo_interval_seconds,
                "excursion_probability": self.demo_excursion_probability,
                "original_probability": original_probability,
                "equipment_ids": self.equipment_ids
            }
            
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
            
            logger.info("✅ Demo mode stopped successfully")
            
            return {
                "status": "stopped",
                "message": "Demo mode stopped successfully",
                "note": "Sensor data will stop generating. Monitoring loops continue running."
            }
            
        except Exception as e:
            logger.error(f"❌ Error stopping demo mode: {e}", exc_info=True)
            raise Exception(f"Failed to stop demo mode: {str(e)}")
    
    def inject_pattern(self, equipment_id: str, pattern: str, target_value: Optional[int] = None) -> Dict[str, Any]:
        """
        Manually inject a pattern-based excursion that evolves over time
        
        Args:
            equipment_id: Equipment identifier
            pattern: Pattern type ("drift", "spike", "false_positive", "oscillation")
            target_value: Optional override for target particle count
            
        Returns:
            Dict with injection status and pattern details
            
        Raises:
            ValueError: If equipment_id, pattern is invalid or pattern not in valid list
        """
        if not equipment_id:
            raise ValueError("equipment_id is required")
        
        if not pattern:
            raise ValueError("pattern is required")
        
        valid_patterns = ["drift", "spike", "false_positive", "oscillation"]
        if pattern not in valid_patterns:
            raise ValueError(
                f"Invalid pattern: {pattern}. Must be one of: {', '.join(valid_patterns)}"
            )
        
        # Get current baseline from normal metrics
        base_metrics = self.generate_demo_metrics(equipment_id, is_excursion=False)
        baseline_value = base_metrics["particle_count"]
        
        # Initialize pattern state
        state = {
            "pattern": pattern,
            "stage": 0,
            "baseline_value": baseline_value,
            "started_at": datetime.now(timezone.utc)
        }
        
        # Set pattern-specific parameters
        if pattern == "drift":
            state["target_value"] = target_value or random.randint(2000, 3500)  # CRITICAL severity range
            state["total_stages"] = random.randint(5, 8)
            logger.info(
                f"📈 MANUAL INJECTION: {equipment_id} DRIFT pattern "
                f"({baseline_value} → {state['target_value']} over {state['total_stages']} readings)"
            )
        
        elif pattern == "spike":
            state["target_value"] = target_value or random.randint(2500, 4000)  # CRITICAL severity range
            state["total_stages"] = random.randint(3, 5)
            logger.info(
                f"⚡ MANUAL INJECTION: {equipment_id} SPIKE pattern "
                f"(value: {state['target_value']}, persists: {state['total_stages']} readings)"
            )
        
        elif pattern == "false_positive":
            state["target_value"] = target_value or random.randint(1050, 1200)
            state["total_stages"] = 1
            logger.info(
                f"🔔 MANUAL INJECTION: {equipment_id} FALSE_POSITIVE pattern "
                f"(spike to {state['target_value']}, immediate return)"
            )
        
        elif pattern == "oscillation":
            state["target_value"] = target_value or random.randint(2000, 3000)  # CRITICAL severity range
            state["total_stages"] = random.randint(6, 10)
            logger.info(
                f"🌊 MANUAL INJECTION: {equipment_id} OSCILLATION pattern "
                f"(amplitude: {state['target_value']}, cycles: {state['total_stages']})"
            )
        
        # Update equipment pattern state
        self.equipment_pattern_state[equipment_id] = state
        
        return {
            "success": True,
            "message": f"Pattern '{pattern}' injected for {equipment_id}",
            "equipment_id": equipment_id,
            "pattern": pattern,
            "baseline_value": baseline_value,
            "target_value": state["target_value"],
            "total_stages": state["total_stages"],
            "note": f"Pattern will evolve over next {state['total_stages']} demo batches (every {self.demo_interval_seconds} seconds)"
        }

