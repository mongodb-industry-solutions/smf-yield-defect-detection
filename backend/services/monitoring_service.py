"""
Monitoring Service - Background monitoring loops for sensor and wafer defect detection

This service encapsulates all real-time monitoring logic including:
- Sensor event monitoring via MongoDB change streams
- Wafer defect monitoring via MongoDB change streams
- Excursion detection and alert creation
- Traditional correlation and RCA analysis
- WebSocket notifications for real-time updates

All business logic extracted from main.py for better separation of concerns.
"""

import logging
import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from services.alert_manager import AlertManager, AlertSeverity, AlertStatus, AlertType
from services.websocket_manager import WebSocketManager, ConnectionType
from services.wafer_generator import WaferGenerator
from utils import convert_objectids

# Import centralized threshold configuration
from config.thresholds import (
    get_thresholds,
    get_active_threshold_mode,
    get_particle_count_thresholds,
    get_rf_power_thresholds,
    get_temperature_thresholds
)

logger = logging.getLogger(__name__)


class MonitoringService:
    """
    Service for managing real-time monitoring of sensor events.

    Responsibilities:
    - Monitor sensor_events collection for excursions
    - Create alerts based on detection rules
    - Send WebSocket notifications for real-time updates
    """
    
    def __init__(
        self,
        alert_manager: AlertManager,
        ws_manager: WebSocketManager,
        wafer_generator: WaferGenerator,
        config: Dict[str, Any]
    ):
        """
        Initialize MonitoringService with required dependencies.

        Args:
            alert_manager: AlertManager instance for creating and managing alerts
            ws_manager: WebSocketManager for real-time notifications
            wafer_generator: WaferGenerator for creating wafer defects
            config: Configuration dict with keys:
                - mdb_uri: MongoDB connection URI
                - mdb_database_name: Database name
        """
        self.alert_manager = alert_manager
        self.ws_manager = ws_manager
        self.wafer_generator = wafer_generator

        # Configuration
        self.mdb_uri = config['mdb_uri']
        self.mdb_database_name = config['mdb_database_name']

        # State management
        self.monitoring_active = False

        # Alert deduplication window (MongoDB-based, global across all instances)
        self.deduplication_window_seconds = 5  # Skip alerts within 5 seconds

        logger.info("✅ MonitoringService initialized")
        logger.info(f"   🔒 Alert Deduplication: {self.deduplication_window_seconds}s window (MongoDB-based)")
    
    def stop_monitoring(self):
        """Stop all monitoring loops by setting the active flag to False."""
        self.monitoring_active = False
        logger.info("🛑 Monitoring service stopped")
    
    def _is_duplicate_alert(self, async_db, equipment_id: str, excursion_type: str, root_cause: str = None) -> bool:
        """
        Check if an alert was recently created for this equipment/excursion/root_cause.
        Uses MongoDB to detect duplicates across multiple monitoring instances.

        Args:
            async_db: Async MongoDB database instance
            equipment_id: Equipment identifier
            excursion_type: Type of excursion (always "particle_excursion" in new logic)
            root_cause: Root cause of excursion (temperature_drift or rf_power_drift)

        Returns:
            True if a duplicate alert was created within deduplication window
        """
        # Check MongoDB for recent alerts (global deduplication across all instances)
        # MongoDB stores datetimes as naive UTC, so we need naive datetime for comparison
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=self.deduplication_window_seconds)
        cutoff_time_naive = cutoff_time.replace(tzinfo=None)  # Remove timezone for MongoDB query

        # Use synchronous MongoDB client from alert_manager for immediate check
        # (AlertManager uses sync MongoClient for performance)
        import pymongo
        sync_client = pymongo.MongoClient(self.mdb_uri)
        sync_db = sync_client[self.mdb_database_name]
        alerts_collection = sync_db["alerts"]

        # Build query to check for same equipment and root cause
        query = {
            "equipment_id": equipment_id,
            "alert_type": "excursion",
            "timestamp": {"$gte": cutoff_time_naive}
        }

        # Add root_cause check to differentiate between temperature and RF power excursions
        if root_cause:
            query["source_data.root_cause"] = root_cause

        recent_alert = alerts_collection.find_one(query, sort=[("timestamp", pymongo.DESCENDING)])

        sync_client.close()

        if recent_alert:
            # MongoDB returns naive datetimes, make it timezone-aware for comparison
            alert_timestamp = recent_alert["timestamp"]
            if alert_timestamp.tzinfo is None:
                alert_timestamp = alert_timestamp.replace(tzinfo=timezone.utc)

            time_diff = (datetime.now(timezone.utc) - alert_timestamp).total_seconds()

            # Handle edge case: if time_diff is negative, the alert has wrong timezone
            # This can happen with old alerts created before timezone fixes
            # Skip deduplication for these old alerts (they're from different timezone)
            if time_diff < 0:
                logger.warning(f"⚠️  Found old alert with timezone mismatch (time_diff={time_diff:.1f}s), "
                             f"skipping deduplication for alert_id={recent_alert.get('alert_id', 'unknown')}")
                return False

            logger.info(f"🚫 DUPLICATE ALERT BLOCKED: {excursion_type} (root cause: {root_cause}) on {equipment_id} "
                       f"(last alert {time_diff:.1f}s ago, alert_id={recent_alert.get('alert_id', 'unknown')})")
            return True

        return False
    
    def _record_alert_creation(self, equipment_id: str, excursion_type: str):
        """
        No-op function kept for backward compatibility.
        Deduplication now uses MongoDB queries instead of in-memory cache.

        Args:
            equipment_id: Equipment identifier
            excursion_type: Type of excursion
        """
        pass  # MongoDB-based deduplication doesn't need in-memory tracking
    
    # ============================================================================
    # Helper Methods
    # ============================================================================
    
    def determine_severity(self, excursion: Dict[str, Any]) -> AlertSeverity:
        """
        Determine alert severity based on excursion data using centralized thresholds.
        All pattern-based excursions (drift, spike, oscillation) should be CRITICAL.
        
        Args:
            excursion: Dictionary containing excursion metrics and metadata
            
        Returns:
            AlertSeverity enum value (CRITICAL, HIGH, MEDIUM, or LOW)
        """
        metrics = excursion.get('metrics', {})
        thresholds = get_thresholds()

        # Check particle count using centralized thresholds
        particle_count = metrics.get('particle_count', 0)
        particle_thresholds = thresholds["particle_count"]
        if particle_count > particle_thresholds["critical"]:
            return AlertSeverity.CRITICAL
        elif particle_count > particle_thresholds["high"]:
            return AlertSeverity.HIGH

        # Check RF power drift using centralized thresholds
        rf_power = metrics.get('rf_power', 0)
        rf_thresholds = thresholds["rf_power_drift"]
        if rf_power > rf_thresholds["critical"]:
            return AlertSeverity.CRITICAL
        elif rf_power > rf_thresholds["high"]:
            return AlertSeverity.HIGH

        # Default to CRITICAL for any excursion (patterns should always be critical)
        return AlertSeverity.CRITICAL
    
    async def notify_websocket_clients(self, message: Dict[str, Any]):
        """
        Send message to all connected WebSocket clients.

        Args:
            message: Dictionary containing message data to broadcast
        """
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
        sent_count = await self.ws_manager.broadcast(
            message_converted,
            connection_type=connection_type
        )

        if sent_count > 0:
            logger.info(f"Notified {sent_count} WebSocket clients")
        else:
            logger.debug("No WebSocket clients to notify")

    async def generate_delayed_wafer_defect(self, excursion_data: Dict[str, Any], delay_seconds: int = 10):
        """
        Generate wafer defect after delay to simulate inspection time.
        
        Args:
            excursion_data: Dictionary containing excursion details
            delay_seconds: Delay in seconds (10 for demo, 7200 for realistic)
        """
        try:
            # Wait to simulate inspection delay
            logger.info(f"Scheduling wafer generation for alert {excursion_data.get('alert_id')} in {delay_seconds} seconds")
            await asyncio.sleep(delay_seconds)

            # Generate wafer based on excursion type
            wafer_record = await self.wafer_generator.generate_excursion_wafer(excursion_data)

            # Save to MongoDB
            wafer_id = self.wafer_generator.save_wafer(wafer_record)

            logger.info(f"✅ Generated wafer {wafer_record['wafer_id']} with {wafer_record['defect_summary']['defect_pattern']} "
                       f"pattern ({wafer_record['defect_summary']['yield_percentage']:.1f}% yield) for alert {excursion_data.get('alert_id')}")

            # Notify WebSocket clients about new wafer
            await self.notify_websocket_clients({
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

            # NOTE: Do NOT call cleanup() here - it closes the MongoDB client
            # and breaks subsequent wafer generations. Cleanup is handled by
            # the service shutdown lifecycle in main.py

        except Exception as e:
            logger.error(f"Error generating wafer defect for alert {excursion_data.get('alert_id')}: {e}")
    
    # ============================================================================
    # Monitoring Loops
    # ============================================================================
    
    async def start_sensor_monitoring(self):
        """
        Background task for continuous monitoring using MongoDB change streams.
        Monitors sensor_events collection for excursions and creates alerts.
        """
        logger.info("Starting real-time monitoring loop with change streams")

        try:
            # Get async MongoDB connection
            async_client = AsyncIOMotorClient(self.mdb_uri)
            async_db = async_client[self.mdb_database_name]
            sensor_events_collection = async_db["sensor_events"]

            # Define change stream pipeline to watch for inserts
            pipeline = [
                {"$match": {"operationType": "insert"}}
            ]

            # Start watching the sensor_events collection
            async with sensor_events_collection.watch(pipeline) as stream:
                logger.info("✅ Change stream connected - monitoring sensor_events collection")

                while self.monitoring_active:
                    try:
                        # Wait for the next change event
                        async for change in stream:
                            if not self.monitoring_active:
                                break

                            # Get the new sensor data
                            sensor_data = change.get("fullDocument")
                            if not sensor_data:
                                continue

                            logger.debug(f"New sensor data from {sensor_data.get('equipment_id')}")

                            # Check for excursions (thresholds)
                            # Particle excursion is a SYMPTOM, not a standalone cause
                            # Only detect root causes: temperature_drift and rf_power_drift
                            excursion_detected = False
                            root_cause = None
                            excursion_value = None

                            metrics = sensor_data.get("metrics", {})
                            equipment_id = sensor_data.get("equipment_id", "")
                            particle_count = metrics.get("particle_count", 0)

                            # Get centralized thresholds
                            thresholds = get_thresholds()
                            rf_thresholds = thresholds["rf_power_drift"]
                            temp_thresholds = thresholds["temperature_drift"]

                            # Check RF power drift using centralized baselines and thresholds
                            rf_power = metrics.get("rf_power", 0)
                            process_step = sensor_data.get("process_step", "")
                            if process_step in rf_thresholds:
                                rf_config = rf_thresholds[process_step]
                                baseline = rf_config["baseline"]
                                threshold = rf_config["threshold"]
                                if abs(rf_power - baseline) >= threshold:
                                    excursion_detected = True
                                    root_cause = "rf_power_drift"
                                    excursion_value = rf_power
                                    logger.warning(f"⚠️ Root cause detected - RF power drift: {rf_power}W (baseline {baseline}W) on {equipment_id}, particle count: {particle_count}")

                            # Check temperature drift using centralized baselines and thresholds
                            temperature = metrics.get("temperature", 0)
                            if process_step in temp_thresholds:
                                temp_config = temp_thresholds[process_step]
                                baseline = temp_config["baseline"]
                                threshold = temp_config["threshold"]
                                if abs(temperature - baseline) >= threshold:  # Note: >= not > to catch exactly at threshold
                                    excursion_detected = True
                                    root_cause = "temperature_drift"
                                    excursion_value = temperature
                                    logger.warning(f"⚠️ Root cause detected - Temperature drift: {temperature}°C (baseline {baseline}°C) on {equipment_id}, particle count: {particle_count}")

                            # Create alert if excursion detected
                            if excursion_detected and self.alert_manager:
                                # Extract metadata for easier access
                                metadata = sensor_data.get("metadata", {})

                                # Alert type is always "particle_excursion" (the symptom)
                                # Root cause determines wafer pattern
                                excursion_type = "particle_excursion"

                                # Prepare excursion data with root cause
                                excursion = {
                                    "equipment_id": sensor_data.get("equipment_id"),
                                    "timestamp": sensor_data.get("timestamp"),
                                    "excursion_type": excursion_type,
                                    "root_cause": root_cause,  # Store root cause for tracking
                                    "value": particle_count,  # Show particle count as the symptom value
                                    "root_cause_value": excursion_value,  # Store root cause value (temp or RF)
                                    "metrics": metrics,
                                    "metadata": metadata,
                                    "description": f"Particle Excursion: {particle_count}",
                                    # Include scenario metadata at top level for easier access by agentic AI
                                    "scenario_id": metadata.get("scenario_id"),  # "gradual_drift", etc.
                                    "pattern_type": metadata.get("pattern_type"),  # "drift", "spike", "oscillation"
                                    "is_lot_processing_scenario": metadata.get("is_lot_processing_scenario", False)
                                }

                                # Determine severity based on excursion type and value
                                severity = self.determine_severity(excursion)

                                # === DEDUPLICATION CHECK ===
                                # Skip if same equipment/excursion/root_cause within 5 seconds
                                # (Prevents duplicates from demo mode + manual injection collisions)
                                # Check root_cause to allow different root causes (temperature vs RF power)
                                if self._is_duplicate_alert(async_db, equipment_id, excursion_type, root_cause):
                                    continue

                                # Create alert
                                alert_id = self.alert_manager.create_alert(
                                    alert_type=AlertType.EXCURSION,
                                    severity=severity,
                                    title=f"Particle Excursion on {equipment_id}",
                                    description=excursion["description"],
                                    source_data=excursion,
                                    equipment_id=equipment_id,
                                    lot_id=sensor_data.get("metadata", {}).get("lot_id"),
                                    wafer_id=sensor_data.get("metadata", {}).get("wafer_id")
                                )

                                logger.info(f"🚨 Alert created: {alert_id} for particle_excursion (root cause: {root_cause}) on {equipment_id}")

                                # Record alert creation for deduplication tracking
                                self._record_alert_creation(equipment_id, excursion_type)

                                # Notify WebSocket clients
                                await self.notify_websocket_clients({
                                    "type": "new_alert",
                                    "alert_id": alert_id,
                                    "severity": severity.value,
                                    "equipment_id": equipment_id,
                                    "excursion_type": excursion_type,
                                    "root_cause": root_cause,
                                    "value": particle_count,
                                    "timestamp": sensor_data.get("timestamp").isoformat() if hasattr(sensor_data.get("timestamp"), 'isoformat') else str(sensor_data.get("timestamp"))
                                })

                                # Schedule wafer defect generation (with delay to simulate inspection)
                                # Use root_cause as excursion_type for wafer pattern determination
                                asyncio.create_task(self.generate_delayed_wafer_defect({
                                    'alert_id': alert_id,
                                    'equipment_id': equipment_id,
                                    'excursion_type': root_cause,  # Use root cause for wafer pattern
                                    'severity': severity.value,
                                    'timestamp': sensor_data.get('timestamp'),
                                    'metrics': metrics,
                                    'metadata': sensor_data.get('metadata', {})  # Pass metadata for process context!
                                }, delay_seconds=0))  # 10 seconds for demo, can be 7200 for realistic

                            # Also check if this is just a normal update to broadcast
                            elif not excursion_detected:
                                # Broadcast normal sensor update to WebSocket clients
                                await self.notify_websocket_clients({
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
            while self.monitoring_active:
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
