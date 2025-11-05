"""
Wafer Generator Service
Dynamically generates wafer defect images in response to equipment excursions
"""

import os
import sys
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import numpy as np
from pymongo import MongoClient
import logging

# Add parent directory to path to import from data_generation
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_generation.generate_wafer_images import generate_wafer_map, S3ImageUploader

logger = logging.getLogger(__name__)


class WaferGenerator:
    """
    Service for generating wafer defect images dynamically based on equipment excursions
    """

    def __init__(self, mongodb_uri: str, database: str = "smf-yield-defect", s3_bucket_uri: Optional[str] = None):
        """
        Initialize the wafer generator service

        Args:
            mongodb_uri: MongoDB connection string
            database: Database name
            s3_bucket_uri: Optional S3 bucket URI for full-resolution images
        """
        self.mongodb_uri = mongodb_uri
        self.database = database
        self.client = MongoClient(mongodb_uri)
        self.db = self.client[database]
        self.wafer_collection = self.db["wafer_defects"]

        # Initialize S3 uploader if configured
        self.s3_uploader = None
        if s3_bucket_uri:
            try:
                self.s3_uploader = S3ImageUploader(s3_bucket_uri)
                logger.info("S3 uploader initialized for wafer images")
            except Exception as e:
                logger.warning(f"S3 uploader initialization failed: {e}. Will use base64 storage.")

    def map_excursion_to_defect_pattern(self, excursion_type: str) -> tuple[str, float]:
        """
        Map excursion type to defect pattern and base defect rate

        Returns:
            Tuple of (pattern_type, base_defect_rate)
        """
        pattern_map = {
            'particle_excursion': ('clustered', 0.25),    # 25% defect rate for particle contamination
            'particle_spike': ('clustered', 0.30),        # 30% for severe particle spike
            'rf_power_drift': ('systematic', 0.20),       # 20% for RF drift
            'temperature_drift': ('edge', 0.15),          # 15% for temperature issues
            'pressure_drop': ('random', 0.10),            # 10% for pressure variations
            'recovery': ('random', 0.03),                 # 3% defect rate = 97% yield for recovery
        }

        return pattern_map.get(excursion_type, ('random', 0.08))

    async def generate_excursion_wafer(self, excursion_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a wafer defect image based on excursion data
        Follows the exact schema from wafer_defects.json

        Args:
            excursion_data: Dictionary containing excursion details
                - alert_id: Associated alert ID
                - equipment_id: Equipment that had excursion
                - excursion_type: Type of excursion
                - severity: Severity level
                - timestamp: When excursion occurred
                - metrics: Sensor metrics at time of excursion

        Returns:
            Generated wafer defect record matching existing schema
        """
        # Extract excursion details
        alert_id = excursion_data.get('alert_id')
        equipment_id = excursion_data.get('equipment_id')
        excursion_type = excursion_data.get('excursion_type')
        severity = excursion_data.get('severity', 'medium')
        timestamp = excursion_data.get('timestamp')
        metrics = excursion_data.get('metrics', {})

        # Map excursion to defect pattern
        pattern_type, base_defect_rate = self.map_excursion_to_defect_pattern(excursion_type)

        # Adjust defect rate based on severity
        severity_multiplier = {
            'critical': 1.5,
            'high': 1.2,
            'medium': 1.0,
            'low': 0.8
        }
        defect_rate = base_defect_rate * severity_multiplier.get(severity, 1.0)

        # Scale defect rate based on particle count magnitude (UNIVERSAL - applies to ALL excursion types)
        # Higher particle counts should produce lower yields (higher defect rates)
        # This is realistic because particle count is the SYMPTOM that directly affects yield,
        # regardless of root cause (temperature, RF power, etc.)
        particle_count = metrics.get('particle_count', 0)
        if particle_count > 1000:
            # Threshold: 1000 = baseline critical, scale linearly up to 3000
            scale_factor = min(2.0, 1.0 + (particle_count - 1000) / 2000)  # 1.0x to 2.0x
            original_defect_rate = defect_rate
            defect_rate = min(0.50, defect_rate * scale_factor)  # Cap at 50% defect rate
            logger.info(
                f"Particle-based yield scaling: {particle_count} particles → "
                f"defect_rate {original_defect_rate:.2%} → {defect_rate:.2%} "
                f"(excursion_type: {excursion_type})"
            )

        # Use wafer_id from sensor metadata to maintain correlation
        # This ensures wafer defect image links to the actual wafer from sensor data
        wafer_id = excursion_data.get('metadata', {}).get('wafer_id')
        lot_id = excursion_data.get('metadata', {}).get('lot_id')

        # Fallback: Generate unique IDs if metadata missing (shouldn't happen in normal flow)
        if not wafer_id:
            logger.warning(f"No wafer_id in metadata for alert {alert_id}, generating fallback ID")
            last_wafer = self.wafer_collection.find_one(
                sort=[("wafer_id", -1)],
                projection={"wafer_id": 1}
            )
            if last_wafer and last_wafer.get("wafer_id", "").startswith("W_"):
                try:
                    last_num = int(last_wafer["wafer_id"].split("_")[1])
                    wafer_count = last_num + 1
                except (IndexError, ValueError):
                    wafer_count = self.wafer_collection.count_documents({}) + 1
            else:
                wafer_count = self.wafer_collection.count_documents({}) + 1
            wafer_id = f"W_{wafer_count:04d}"

        # Generate wafer map with appropriate defect pattern
        logger.info(
            f"Generating wafer for alert {alert_id}: "
            f"{excursion_type} → {pattern_type} pattern | "
            f"Particle count: {particle_count} | "
            f"Final defect rate: {defect_rate:.2%} | "
            f"Expected yield: ~{(1-defect_rate)*100:.1f}%"
        )
        wafer_data = generate_wafer_map(
            pattern_type=pattern_type,
            defect_rate=defect_rate,
            s3_uploader=self.s3_uploader,
            wafer_id=wafer_id
        )

        # Calculate inspection timestamp (simulating 2-4 hour delay from excursion)
        # Use the excursion timestamp, not current time
        delay_hours = np.random.uniform(2, 4)  # Realistic inspection delay
        if isinstance(timestamp, str):
            excursion_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        else:
            excursion_time = timestamp
        inspection_time = excursion_time

        # lot_id already set from metadata above (line 109), skip regeneration

        # Create defect description based on pattern (matching existing format)
        if pattern_type == "clustered":
            description = f"Clustered particle defects observed in quadrant {np.random.choice(['upper-right', 'lower-left', 'center'])}, likely contamination from {equipment_id.split('_')[0]} process"
        elif pattern_type == "edge":
            description = f"Edge die failures detected, possible handling damage or process uniformity issue in {equipment_id}"
        elif pattern_type == "systematic":
            description = f"Systematic pattern defects, potential reticle or stepper issue in {equipment_id}"
        else:
            description = f"Random defects across wafer, baseline yield loss from {equipment_id.split('_')[0]} process"

        # Determine severity based on yield (matching existing thresholds)
        yield_pct = wafer_data["statistics"]["yield_percentage"]
        if yield_pct < 85:
            wafer_severity = "high"
        elif yield_pct < 92:
            wafer_severity = "medium"
        else:
            wafer_severity = "low"

        # Build ink_map structure (matching existing schema)
        ink_map = {
            "thumbnail_base64": wafer_data["thumbnail_base64"],
            "thumbnail_size": wafer_data["thumbnail_size"],
            "format": "PNG"
        }

        # Add full image reference (S3 URL or base64 fallback)
        if "full_image_url" in wafer_data:
            ink_map["full_image_url"] = wafer_data["full_image_url"]
            ink_map["full_image_size"] = wafer_data["full_image_size"]
        elif "full_image_base64" in wafer_data:
            ink_map["full_image_base64"] = wafer_data["full_image_base64"]
            ink_map["full_image_size"] = wafer_data["full_image_size"]

        # Build record matching exact schema from wafer_defects.json
        record = {
            "wafer_id": wafer_id,
            "lot_id": lot_id,
            "inspection_timestamp": inspection_time.isoformat() + "Z",
            "inspection_timestamp_date": inspection_time,  # Date field for TTL index
            "ink_map": ink_map,
            "defect_summary": {
                "total_dies": wafer_data["statistics"]["total_dies"],
                "failed_dies": wafer_data["statistics"]["failed_dies"],
                "yield_percentage": wafer_data["statistics"]["yield_percentage"],
                "defect_pattern": pattern_type,
                "severity": wafer_severity
            },
            "die_map": wafer_data["die_map"],
            "defects": [
                {
                    "type": "particle" if pattern_type == "clustered" else "process",
                    "location": loc,
                    "size_um": round(np.random.uniform(0.1, 2.0), 2),
                    "confidence": round(np.random.uniform(0.85, 0.99), 2)
                }
                for loc in wafer_data["defect_locations"][:10]  # Limit to 10 defects
            ],
            "description": description,
            "process_context": {
                "last_process_step": equipment_id.split("_")[0],
                "equipment_used": [equipment_id],
                "slurry_batch": excursion_data.get('metadata', {}).get('slurry_batch', f"SB_2025_{np.random.randint(1, 51):03d}"),  # Use real slurry_batch from sensor metadata!
                "recipe_id": excursion_data.get('metadata', {}).get('recipe_id', f"RECIPE_{np.random.randint(1, 10):02d}"),  # Use real recipe_id
                "clean_cycle": np.random.randint(100, 200)
            }
        }

        # Add link to the alert that triggered this wafer generation
        # This is stored in process_context to maintain compatibility
        record["process_context"]["excursion_alert_id"] = alert_id

        return record

    def save_wafer(self, wafer_record: Dict[str, Any]) -> str:
        """
        Save wafer defect record to MongoDB
        Checks for duplicates and only inserts if wafer_id doesn't exist

        Returns:
            Inserted document ID (or existing ID if duplicate)
        """
        wafer_id = wafer_record['wafer_id']

        # Check if wafer already exists
        existing = self.wafer_collection.find_one({'wafer_id': wafer_id}, {'_id': 1})

        if existing:
            logger.warning(f"Wafer {wafer_id} already exists with ID: {existing['_id']} - skipping duplicate insert")
            return str(existing['_id'])

        # Insert new wafer
        result = self.wafer_collection.insert_one(wafer_record)
        logger.info(f"✅ New wafer {wafer_id} saved with ID: {result.inserted_id}")
        return str(result.inserted_id)

    def cleanup(self):
        """Clean up database connections"""
        if self.client:
            self.client.close()