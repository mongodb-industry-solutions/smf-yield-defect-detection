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

# LangGraph agent for automatic RCA analysis
import os
from langchain_aws import ChatBedrock
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient  # Sync client for LangGraph (required by MongoDBSaver)

# Import RCA tools
from services.rca_chat_tools import TOOLS

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
        # Increased from 5 to 15 seconds for extra safety against race conditions
        self.deduplication_window_seconds = 5  # Skip alerts within 15 seconds

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
    # Automatic RCA Analysis Methods
    # ============================================================================

    def _get_or_create_agent(self):
        """
        Initialize LangGraph ReAct agent for RCA analysis (lazy initialization).

        Uses AWS Bedrock Claude 3.5 Sonnet with MongoDB checkpointing.
        Agent is cached after first initialization for reuse.

        Returns:
            Tuple[agent, checkpointer] or (None, None) if initialization fails
        """
        # Check if agent already initialized (cache for reuse)
        if hasattr(self, '_agent') and self._agent is not None:
            return self._agent, self._checkpointer

        try:
            logger.info("Initializing LangGraph agent for automatic RCA analysis...")

            # Get AWS region (same pattern as chat.py)
            aws_region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))

            # Initialize LLM (AWS Bedrock Claude 3.5 Sonnet)
            llm = ChatBedrock(
                model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                region_name=aws_region,
                model_kwargs={
                    "temperature": 0.3,  # Lower temperature for precise RCA
                    "max_tokens": 2048
                }
            )
            logger.info(f"✅ Bedrock LLM initialized (region: {aws_region})")

            # Initialize MongoDB checkpointer (SYNC pymongo client required by LangGraph)
            try:
                sync_mongo_client = MongoClient(self.mdb_uri)
                checkpointer = MongoDBSaver(
                    sync_mongo_client,
                    self.mdb_database_name
                )
                logger.info(f"✅ MongoDB checkpointer initialized (database: {self.mdb_database_name})")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize checkpointer: {e}")
                logger.warning("⚠️ Continuing without conversation memory")
                checkpointer = None

            # Create ReAct agent
            agent = create_react_agent(
                llm,
                TOOLS,
                checkpointer=checkpointer
            )

            # Cache for reuse
            self._agent = agent
            self._checkpointer = checkpointer

            logger.info(f"✅ RCA agent initialized with {len(TOOLS)} tools")
            return agent, checkpointer

        except Exception as e:
            logger.error(f"❌ Failed to initialize RCA agent: {e}", exc_info=True)
            self._agent = None
            self._checkpointer = None
            return None, None

    async def _run_automatic_rca_analysis(self, alert_id: str, equipment_id: str, excursion_data: Dict[str, Any]):
        """
        Perform automatic RCA analysis for a new alert using LangGraph agent.

        This method:
        1. Initializes the agent (lazy init)
        2. Constructs RCA prompt with alert context
        3. Streams agent execution
        4. Stores RCA results in MongoDB alerts collection
        5. Sends WebSocket notification with results

        Args:
            alert_id: Alert identifier (e.g., "ALT-20250805210512-...")
            equipment_id: Equipment identifier (e.g., "CMP_TOOL_01")
            excursion_data: Dictionary with excursion context (matches alert source_data)
        """
        try:
            logger.info(f"🤖 Starting automatic RCA analysis for alert {alert_id}")

            # Step 1: Get or create agent
            agent, checkpointer = self._get_or_create_agent()
            if agent is None:
                logger.error(f"❌ Cannot perform RCA - agent initialization failed for alert {alert_id}")
                return

            # Step 2: Build RCA prompt with alert context
            root_cause = excursion_data.get('root_cause', 'unknown')
            excursion_type = excursion_data.get('excursion_type', 'unknown')
            timestamp = excursion_data.get('timestamp')
            metrics = excursion_data.get('metrics', {})
            metadata = excursion_data.get('metadata', {})

            # Get wafer_id and lot_id
            wafer_id = metadata.get('wafer_id', 'N/A')
            lot_id = metadata.get('lot_id', 'N/A')

            timestamp_str = timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp)

            prompt = f"""Analyze this alert and perform root cause analysis:

Alert ID: {alert_id}
Equipment: {equipment_id}
Wafer ID: {wafer_id}
Lot ID: {lot_id}
Excursion Type: {excursion_type}
Root Cause Indicator: {root_cause}
Timestamp: {timestamp_str}

Current Metrics:
- Particle Count: {metrics.get('particle_count', 'N/A')}
- Temperature: {metrics.get('temperature', 'N/A')}°C
- RF Power: {metrics.get('rf_power', 'N/A')}W
- Chamber Pressure: {metrics.get('chamber_pressure', 'N/A')} Torr
- Flow Rate: {metrics.get('flow_rate', 'N/A')} sccm

ANALYSIS INSTRUCTIONS:
Use ALL available tools to investigate:
- query_alerts: Check recent alerts for this equipment to identify patterns
- query_wafer_info: Find this wafer's defect data and similar historical patterns
- query_time_series_data: Analyze sensor behavior around the alert timestamp
- vector_search_knowledge_base: Search for similar incidents in historical RCA reports

OUTPUT FORMAT REQUIREMENTS:
1. Skip all conversational text (no "First, let me...", "I'll analyze...", "Looking at...")
2. Start directly with structured analysis
3. Use sequential numbering (write as: 1., 2., 3., 4... NOT repeated 1., 1., 1., 1...)
4. Structure with clear section headers in UPPERCASE followed by colon
5. Be concise and actionable

OUTPUT TEMPLATE:

ANALYSIS SUMMARY

1. Alert Details:
   [Describe the alert specifics and immediate observations]

2. Sensor Analysis:
   [Describe sensor behavior and anomalies from time series data]

3. Historical Pattern Matching:
   [Describe similar cases found in knowledge base and their outcomes]

4. Key Findings:
   [Synthesize cross-tool evidence into key insights]

ROOT CAUSE HYPOTHESIS

[Clear statement of primary root cause with supporting evidence from tool results]

CONFIDENCE SCORE

[Percentage with rationale based on evidence strength]

RECOMMENDED CORRECTIVE ACTIONS

Immediate Actions:
- [Specific action based on findings]
- [Specific action based on findings]

Short-term:
- [Preventive measure]
- [Process improvement]

Provide your analysis following this exact structure."""

            # Step 3: Configure agent with unique thread_id for this alert
            config = {
                "configurable": {
                    "thread_id": f"auto_rca_{alert_id}",  # Unique thread per alert
                    "checkpoint_ns": "automatic_rca"
                }
            }

            # Step 4: Execute agent and collect results
            logger.info(f"🔍 Executing RCA agent for alert {alert_id}...")

            full_response = []
            tool_calls = []

            async for event in agent.astream(
                {"messages": [("user", prompt)]},
                config=config,
                stream_mode="values"
            ):
                messages = event.get("messages", [])
                if not messages:
                    continue

                last_message = messages[-1]

                if hasattr(last_message, "type"):
                    msg_type = last_message.type

                    if msg_type == "ai":
                        content = getattr(last_message, "content", "")
                        if content:
                            full_response.append(content)

                    elif msg_type == "tool":
                        tool_name = getattr(last_message, "name", "unknown")
                        tool_calls.append(tool_name)
                        logger.info(f"  🔧 Agent called tool: {tool_name}")

            # Combine response
            rca_analysis = "\n".join(full_response)

            logger.info(f"✅ RCA analysis completed for alert {alert_id}")
            logger.info(f"   Tools used: {', '.join(set(tool_calls))}")
            logger.info(f"   Response length: {len(rca_analysis)} chars")

            # Step 5: Store RCA results in MongoDB
            await self._store_rca_results(alert_id, {
                "analysis": rca_analysis,
                "tools_used": list(set(tool_calls)),
                "timestamp": datetime.now(timezone.utc),
                "agent_model": "claude-3-5-sonnet-20241022-v2",
                "automatic": True
            })

            # Step 6: Send WebSocket notification
            await self.notify_websocket_clients({
                "type": "rca_analysis_complete",
                "alert_id": alert_id,
                "equipment_id": equipment_id,
                "analysis_summary": rca_analysis[:200] + "..." if len(rca_analysis) > 200 else rca_analysis,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

            logger.info(f"📤 RCA results stored and broadcasted for alert {alert_id}")

        except Exception as e:
            logger.error(f"❌ Error during automatic RCA analysis for alert {alert_id}: {e}", exc_info=True)

            # Store error state in MongoDB
            try:
                await self._store_rca_results(alert_id, {
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc),
                    "automatic": True
                })
            except Exception as store_error:
                logger.error(f"Failed to store RCA error: {store_error}")

    async def _store_rca_results(self, alert_id: str, rca_data: Dict[str, Any]):
        """
        Store RCA analysis results in MongoDB alerts collection.

        Updates the alert document with RCA analysis data in the 'rca_analysis' field.

        Args:
            alert_id: Alert identifier
            rca_data: Dictionary containing RCA results (analysis, tools_used, timestamp, etc.)
        """
        try:
            # Get async MongoDB connection
            async_client = AsyncIOMotorClient(self.mdb_uri)
            async_db = async_client[self.mdb_database_name]
            alerts_collection = async_db["alerts"]

            # Update alert with RCA analysis
            result = await alerts_collection.update_one(
                {"alert_id": alert_id},
                {
                    "$set": {
                        "rca_analysis": rca_data,
                        "rca_updated_at": datetime.now(timezone.utc)
                    }
                }
            )

            if result.modified_count > 0:
                logger.info(f"✅ Stored RCA results for alert {alert_id}")
            else:
                logger.warning(f"⚠️ Alert {alert_id} not found or not modified")

            async_client.close()

        except Exception as e:
            logger.error(f"❌ Failed to store RCA results for alert {alert_id}: {e}", exc_info=True)
            raise

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

                                # NOTE: RCA analysis is triggered by start_alert_rca_monitoring()
                                # which watches alerts collection for new inserts
                                # This ensures RCA runs for every alert that actually gets created

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

    async def start_alert_rca_monitoring(self):
        """
        Background task to watch alerts collection and trigger RCA for new alerts.

        This separate monitoring loop ensures RCA analysis is triggered for every
        alert that actually gets created, avoiding race conditions in sensor monitoring.
        """
        logger.info("Starting RCA monitoring loop - watching alerts collection")

        try:
            # Get async MongoDB connection
            async_client = AsyncIOMotorClient(self.mdb_uri)
            async_db = async_client[self.mdb_database_name]
            alerts_collection = async_db["alerts"]

            # Define change stream pipeline to watch for inserts only
            pipeline = [
                {"$match": {"operationType": "insert"}}
            ]

            # Start watching the alerts collection
            async with alerts_collection.watch(pipeline) as stream:
                logger.info("✅ RCA change stream connected - monitoring alerts collection")

                while self.monitoring_active:
                    try:
                        # Wait for the next change event
                        async for change in stream:
                            if not self.monitoring_active:
                                break

                            # Get the newly created alert
                            alert_doc = change.get("fullDocument")
                            if not alert_doc:
                                continue

                            alert_id = alert_doc.get("alert_id")
                            equipment_id = alert_doc.get("equipment_id")
                            alert_type = alert_doc.get("alert_type")

                            # Only trigger RCA for excursion alerts
                            if alert_type != "excursion":
                                logger.debug(f"Skipping RCA for non-excursion alert: {alert_id}")
                                continue

                            # Check if RCA already exists (avoid re-running)
                            if "rca_analysis" in alert_doc:
                                logger.debug(f"RCA already exists for alert {alert_id}, skipping")
                                continue

                            logger.info(f"🆕 New alert detected: {alert_id} - triggering RCA")

                            # Build excursion data from alert's source_data
                            source_data = alert_doc.get("source_data", {})
                            excursion_data = {
                                "equipment_id": equipment_id,
                                "timestamp": alert_doc.get("timestamp"),
                                "excursion_type": source_data.get("excursion_type", "particle_excursion"),
                                "root_cause": source_data.get("root_cause"),
                                "value": source_data.get("value"),
                                "root_cause_value": source_data.get("root_cause_value"),
                                "metrics": source_data.get("metrics", {}),
                                "metadata": source_data.get("metadata", {}),
                                "description": alert_doc.get("description")
                            }

                            # Launch automatic RCA analysis in background
                            asyncio.create_task(self._run_automatic_rca_analysis(
                                alert_id=alert_id,
                                equipment_id=equipment_id,
                                excursion_data=excursion_data
                            ))
                            logger.info(f"🚀 Launched automatic RCA analysis for {alert_id}")

                    except Exception as e:
                        logger.error(f"Error processing alert change stream event: {e}", exc_info=True)
                        # Continue monitoring despite errors
                        continue

        except Exception as e:
            logger.error(f"Failed to establish alert RCA change stream: {e}", exc_info=True)

        finally:
            if 'async_client' in locals():
                async_client.close()
            logger.info("RCA monitoring loop stopped")
