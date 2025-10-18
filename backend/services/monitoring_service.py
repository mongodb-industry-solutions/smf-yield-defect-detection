"""
Monitoring Service - Background monitoring loops for sensor and wafer defect detection

This service encapsulates all real-time monitoring logic including:
- Sensor event monitoring via MongoDB change streams
- Wafer defect monitoring via MongoDB change streams
- Excursion detection and alert creation
- AI multi-agent integration (monitoring, investigation, RCA, supervisor)
- WebSocket notifications for real-time updates

All business logic extracted from main.py for better separation of concerns.
"""

import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from services.alert_manager import AlertManager, AlertSeverity, AlertStatus, AlertType
from services.websocket_manager import WebSocketManager, ConnectionType
from services.wafer_generator import WaferGenerator
from services.correlation_engine import CorrelationEngine
from services.rca_generator import RCAGenerator
from multi_agent import create_initial_state
from multi_agent.workers import monitoring_agent_tool, investigation_agent_tool, rca_agent_tool
from multi_agent.supervisor import supervisor_synthesis_agent
from utils import convert_objectids

logger = logging.getLogger(__name__)


class MonitoringService:
    """
    Service for managing real-time monitoring of sensor events and wafer defects.
    
    Responsibilities:
    - Monitor sensor_events collection for excursions
    - Monitor wafer_defects collection for high-severity wafers
    - Create alerts based on detection rules
    - Run AI multi-agent analysis pipeline (if enabled)
    - Send WebSocket notifications for real-time updates
    """
    
    def __init__(
        self,
        alert_manager: AlertManager,
        ws_manager: WebSocketManager,
        wafer_generator: WaferGenerator,
        correlation_engine: CorrelationEngine,
        rca_generator: RCAGenerator,
        config: Dict[str, Any]
    ):
        """
        Initialize MonitoringService with required dependencies.
        
        Args:
            alert_manager: AlertManager instance for creating and managing alerts
            ws_manager: WebSocketManager for real-time notifications
            wafer_generator: WaferGenerator for creating wafer defects
            correlation_engine: CorrelationEngine for alert correlation analysis
            rca_generator: RCAGenerator for root cause analysis
            config: Configuration dict with keys:
                - mdb_uri: MongoDB connection URI
                - mdb_database_name: Database name
                - use_ai_agents: Boolean flag for AI agent integration
        """
        self.alert_manager = alert_manager
        self.ws_manager = ws_manager
        self.wafer_generator = wafer_generator
        self.correlation_engine = correlation_engine
        self.rca_generator = rca_generator
        
        # Configuration
        self.mdb_uri = config['mdb_uri']
        self.mdb_database_name = config['mdb_database_name']
        self.use_ai_agents = config['use_ai_agents']
        
        # State management
        self.monitoring_active = False
        
        logger.info("✅ MonitoringService initialized")
        logger.info(f"   🤖 AI Multi-Agent System: {'ENABLED' if self.use_ai_agents else 'DISABLED'}")
    
    def stop_monitoring(self):
        """Stop all monitoring loops by setting the active flag to False."""
        self.monitoring_active = False
        logger.info("🛑 Monitoring service stopped")
    
    # ============================================================================
    # Helper Methods
    # ============================================================================
    
    def determine_severity(self, excursion: Dict[str, Any]) -> AlertSeverity:
        """
        Determine alert severity based on excursion data.
        All pattern-based excursions (drift, spike, oscillation) should be CRITICAL.
        
        Args:
            excursion: Dictionary containing excursion metrics and metadata
            
        Returns:
            AlertSeverity enum value (CRITICAL, HIGH, MEDIUM, or LOW)
        """
        metrics = excursion.get('metrics', {})

        # Check particle count - lowered threshold to ensure all patterns are CRITICAL
        particle_count = metrics.get('particle_count', 0)
        if particle_count > 1000:  # Changed from 2000 to catch all pattern excursions
            return AlertSeverity.CRITICAL
        elif particle_count > 800:  # Adjusted for edge cases
            return AlertSeverity.HIGH

        # Check RF power drift - lowered threshold to ensure all patterns are CRITICAL
        rf_power = metrics.get('rf_power', 0)
        if rf_power > 100:  # Changed from 150 to catch all pattern excursions
            return AlertSeverity.CRITICAL
        elif rf_power > 80:  # Adjusted for edge cases
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
    
    async def run_alert_correlation(self, alert_id: str):
        """
        Run correlation analysis in background for an alert.
        
        Args:
            alert_id: Alert ID to run correlation analysis for
        """
        try:
            alert = self.alert_manager.get_alert_by_id(alert_id)
            if not alert:
                return

            # Use existing CorrelationEngine - pass the MongoDB _id as string
            correlation_engine = CorrelationEngine(self.mdb_uri)
            # Convert ObjectId to string for the analyze_alert method
            mongo_id = str(alert["_id"]) if "_id" in alert else alert_id
            correlations = await correlation_engine.analyze_alert(mongo_id)

            # NOTE: CorrelationEngine already stores results in 'correlation_analysis' field
            # No need to duplicate in 'correlation_data' field

            # Notify via WebSocket
            await self.notify_websocket_clients({
                "type": "correlation_complete",
                "alert_id": alert_id,
                "correlations": correlations
            })

            logger.info(f"✅ Correlation analysis completed for alert {alert_id}")
        except Exception as e:
            logger.error(f"Correlation failed for {alert_id}: {e}")
    
    async def run_alert_rca(self, alert_id: str, severity: AlertSeverity):
        """
        Run RCA for critical alerts.
        
        Args:
            alert_id: Alert ID to run RCA analysis for
            severity: Alert severity level
        """
        if severity != AlertSeverity.CRITICAL:
            return

        try:
            alert = self.alert_manager.get_alert_by_id(alert_id)
            if not alert:
                return

            # Use existing RCAGenerator - pass the MongoDB _id as string
            rca_gen = RCAGenerator(self.mdb_uri)
            # Convert ObjectId to string for the generate_rca_hints method
            mongo_id = str(alert["_id"]) if "_id" in alert else alert_id
            rca_results = await rca_gen.generate_rca_hints(mongo_id)

            # NOTE: RCAGenerator already stores results in 'rca_hints' field
            # No need to duplicate in 'rca_recommendations' field

            # Notify via WebSocket
            await self.notify_websocket_clients({
                "type": "rca_complete",
                "alert_id": alert_id,
                "rca": rca_results
            })

            logger.info(f"🔍 RCA analysis completed for critical alert {alert_id}")
        except Exception as e:
            logger.error(f"RCA failed for {alert_id}: {e}")
    
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

            # Clean up
            self.wafer_generator.cleanup()

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
                            excursion_detected = False
                            excursion_type = None
                            excursion_value = None

                            metrics = sensor_data.get("metrics", {})

                            # Check particle count threshold
                            particle_count = metrics.get("particle_count", 0)
                            if particle_count > 1000:
                                excursion_detected = True
                                excursion_type = "particle_excursion"
                                excursion_value = particle_count
                                logger.warning(f"⚠️ Particle excursion detected: {particle_count} on {sensor_data.get('equipment_id')}")

                            # Check RF power drift
                            rf_power = metrics.get("rf_power", 0)
                            equipment_id = sensor_data.get("equipment_id", "")
                            if "CMP" in equipment_id and abs(rf_power - 1450) > 100:  # CMP baseline is 1450W, threshold >100W
                                excursion_detected = True
                                excursion_type = "rf_power_drift"
                                excursion_value = rf_power
                                logger.warning(f"⚠️ RF power drift detected: {rf_power}W on {equipment_id}")
                            elif "ETCH" in equipment_id and abs(rf_power - 1200) > 100:  # ETCH baseline is 1200W, threshold >100W
                                excursion_detected = True
                                excursion_type = "rf_power_drift"
                                excursion_value = rf_power
                                logger.warning(f"⚠️ RF power drift detected: {rf_power}W on {equipment_id}")
                            elif "LITHO" in equipment_id and abs(rf_power - 800) > 100:  # LITHO baseline is 800W, threshold >100W
                                excursion_detected = True
                                excursion_type = "rf_power_drift"
                                excursion_value = rf_power
                                logger.warning(f"⚠️ RF power drift detected: {rf_power}W on {equipment_id}")

                            # Check temperature drift
                            temperature = metrics.get("temperature", 0)
                            if "CMP" in equipment_id and abs(temperature - 65) > 5:
                                excursion_detected = True
                                excursion_type = "temperature_drift"
                                excursion_value = temperature
                                logger.warning(f"⚠️ Temperature drift detected: {temperature}°C on {equipment_id}")

                            # Create alert if excursion detected
                            if excursion_detected and self.alert_manager:
                                # Prepare excursion data
                                excursion = {
                                    "equipment_id": sensor_data.get("equipment_id"),
                                    "timestamp": sensor_data.get("timestamp"),
                                    "excursion_type": excursion_type,
                                    "value": excursion_value,
                                    "metrics": metrics,
                                    "metadata": sensor_data.get("metadata", {}),
                                    "description": f"{excursion_type.replace('_', ' ').title()}: {excursion_value}"
                                }

                                # Determine severity based on excursion type and value
                                severity = self.determine_severity(excursion)

                                # === AI MULTI-AGENT FILTERING (if enabled) ===
                                should_create_alert = True
                                monitoring_decision = None

                                if self.use_ai_agents:
                                    try:
                                        logger.info(f"🤖 Running AI Monitoring Agent for {equipment_id}")

                                        # Create initial state for monitoring agent
                                        temp_alert_id = str(ObjectId())
                                        agent_state = create_initial_state(
                                            alert_id=temp_alert_id,
                                            equipment_id=equipment_id,
                                            excursion_type=excursion_type,
                                            severity=severity.value,
                                            metrics=metrics,
                                            metadata=sensor_data.get("metadata", {})
                                        )

                                        # Run monitoring agent (filters false positives)
                                        agent_result = await monitoring_agent_tool(agent_state)
                                        monitoring_decision = agent_result.get("monitoring_decision", {})

                                        # Check agent's decision
                                        should_create_alert = monitoring_decision.get("create_alert", True)

                                        if not should_create_alert:
                                            logger.info(f"🚫 Alert FILTERED by AI Agent: {monitoring_decision.get('reasoning')}")
                                            logger.info(f"   Confidence: {monitoring_decision.get('confidence'):.2f}, Pattern: {monitoring_decision.get('pattern_detected')}")
                                        else:
                                            logger.info(f"✅ Alert APPROVED by AI Agent: {monitoring_decision.get('reasoning')}")
                                            logger.info(f"   Confidence: {monitoring_decision.get('confidence'):.2f}, Pattern: {monitoring_decision.get('pattern_detected')}")

                                    except Exception as agent_error:
                                        logger.error(f"⚠️ AI Agent error (fail-safe: creating alert): {agent_error}")
                                        should_create_alert = True  # Fail-safe: create alert on error

                                # Create alert only if not filtered
                                if not should_create_alert:
                                    # Log filtered alert but don't create it
                                    logger.info(f"📊 Excursion detected but FILTERED: {excursion_type} on {equipment_id}")
                                    continue

                                # Create alert
                                alert_id = self.alert_manager.create_alert(
                                    alert_type=AlertType.EXCURSION,
                                    severity=severity,
                                    title=f"{excursion_type.replace('_', ' ').title()} on {equipment_id}",
                                    description=excursion["description"],
                                    source_data=excursion,
                                    equipment_id=equipment_id,
                                    lot_id=sensor_data.get("metadata", {}).get("lot_id"),
                                    wafer_id=sensor_data.get("metadata", {}).get("wafer_id")
                                )

                                logger.info(f"🚨 Alert created: {alert_id} for {excursion_type} on {equipment_id}")

                                # === SAVE MONITORING DECISION (if AI enabled) ===
                                if self.use_ai_agents and monitoring_decision:
                                    try:
                                        # Get the alert document to extract MongoDB _id
                                        alert_doc = self.alert_manager.get_alert_by_id(alert_id)
                                        if alert_doc:
                                            mongo_id = str(alert_doc["_id"]) if "_id" in alert_doc else alert_id

                                            # Get statistical context from agent result
                                            stats = agent_result.get('statistical_context', {})

                                            # Save monitoring decision to alert with statistical context
                                            self.alert_manager.alerts_collection.update_one(
                                                {"_id": ObjectId(mongo_id)},
                                                {"$set": {
                                                    "monitoring_decision": {
                                                        "create_alert": monitoring_decision.get('create_alert', True),
                                                        "confidence": monitoring_decision.get('confidence', 0),
                                                        "pattern_detected": monitoring_decision.get('pattern_detected', 'unknown'),
                                                        "reasoning": monitoring_decision.get('reasoning', ''),
                                                        "statistical_context": {
                                                            "avg_particles": stats.get('avg_particles'),
                                                            "max_particles": stats.get('max_particles'),
                                                            "min_particles": stats.get('min_particles'),
                                                            "stddev_particles": stats.get('stddev_particles'),
                                                            "deviation_sigma": stats.get('deviation_sigma', 0),
                                                            "deviation_pct": stats.get('deviation_pct', 0),
                                                            "readings_count": stats.get('readings_count', 0)
                                                        }
                                                    }
                                                }}
                                            )
                                            logger.info(f"   💾 Monitoring decision saved to alert {alert_id}")
                                            logger.info(f"   📊 Statistical context: {stats.get('deviation_sigma', 0):.1f}σ, {stats.get('deviation_pct', 0):+.1f}%")
                                    except Exception as save_error:
                                        logger.error(f"   ❌ Failed to save monitoring decision: {save_error}")

                                # === RUN INVESTIGATION AGENT (if AI enabled) ===
                                if self.use_ai_agents and should_create_alert:
                                    try:
                                        # Small delay to ensure alert is committed to MongoDB
                                        await asyncio.sleep(0.1)

                                        logger.info(f"🔬 Running Investigation Agent for alert {alert_id}")

                                        # Get the alert to extract MongoDB _id (same approach as run_alert_correlation)
                                        alert_doc = self.alert_manager.get_alert_by_id(alert_id)
                                        if not alert_doc:
                                            logger.error(f"   ❌ Alert {alert_id} not found in DB after creation")
                                            raise ValueError(f"Alert {alert_id} not found")

                                        # Extract MongoDB _id (the actual ObjectId used by CorrelationEngine)
                                        mongo_id = str(alert_doc["_id"]) if "_id" in alert_doc else alert_id
                                        logger.info(f"   🔑 Using MongoDB _id: {mongo_id} (from alert {alert_id})")

                                        # Update state with MongoDB _id for correlation engine
                                        agent_state['alert_id'] = mongo_id

                                        # Run investigation agent
                                        investigation_result = await investigation_agent_tool(agent_state)

                                        # Log investigation results
                                        key_findings = investigation_result.get('key_findings', [])
                                        logger.info(f"   ✅ Investigation complete: {len(key_findings)} key findings")

                                        # Update alert with investigation results in MongoDB
                                        if key_findings:
                                            self.alert_manager.alerts_collection.update_one(
                                                {"_id": ObjectId(mongo_id)},  # Use mongo_id, not alert_id!
                                                {"$set": {
                                                    "ai_investigation": {
                                                        "key_findings": key_findings,
                                                        "summary": investigation_result.get('investigation_summary'),
                                                        "correlation_confidence": investigation_result.get('correlation_results', {}).get('confidence_score', 0),
                                                        "affected_wafers": investigation_result.get('correlation_results', {}).get('affected_wafers', {}).get('total', 0)
                                                    }
                                                }}
                                            )
                                            logger.info(f"   💾 Investigation results saved to alert {alert_id} (MongoDB _id: {mongo_id})")

                                        # === RUN RCA AGENT (nested in investigation success) ===
                                        try:
                                            logger.info(f"🔍 Running RCA Agent for alert {alert_id}")

                                            # Update state with investigation results for RCA context
                                            agent_state['investigation_summary'] = investigation_result.get('investigation_summary', '')
                                            agent_state['key_findings'] = investigation_result.get('key_findings', [])
                                            agent_state['correlation_results'] = investigation_result.get('correlation_results', {})

                                            # Run RCA agent
                                            rca_result = await rca_agent_tool(agent_state)

                                            # Log RCA results
                                            validated_causes = rca_result.get('validated_causes', [])
                                            logger.info(f"   ✅ RCA complete: {len(validated_causes)} validated root causes")

                                            # Update alert with RCA results in MongoDB
                                            if validated_causes:
                                                self.alert_manager.alerts_collection.update_one(
                                                    {"_id": ObjectId(mongo_id)},
                                                    {"$set": {
                                                        "ai_rca": {
                                                            "validated_causes": validated_causes,
                                                            "validation": rca_result.get('rca_validation'),
                                                            "recommendations": rca_result.get('rca_patterns', {}).get('recommendations', []),
                                                            "confidence": rca_result.get('rca_patterns', {}).get('overall_confidence', 0)
                                                        }
                                                    }}
                                                )
                                                logger.info(f"   💾 RCA results saved to alert {alert_id} (MongoDB _id: {mongo_id})")

                                            # === RUN SUPERVISOR SYNTHESIS (aggregates all agent outputs) ===
                                            try:
                                                logger.info(f"🎯 Running Supervisor Synthesis for alert {alert_id}")

                                                # Aggregate all agent results
                                                supervisor_result = await supervisor_synthesis_agent(
                                                    monitoring_result=agent_result,
                                                    investigation_result=investigation_result,
                                                    rca_result=rca_result,
                                                    alert_context={
                                                        'equipment_id': equipment_id,
                                                        'excursion_type': excursion_type,
                                                        'alert_id': alert_id
                                                    }
                                                )

                                                # Log supervisor results
                                                risk_level = supervisor_result.get('risk_level', 'Unknown')
                                                overall_confidence = supervisor_result.get('overall_confidence', 0)
                                                logger.info(f"   ✅ Supervisor synthesis complete")
                                                logger.info(f"   🎯 Risk Level: {risk_level}, Overall Confidence: {overall_confidence:.0%}")

                                                # Update alert with supervisor synthesis
                                                supervisor_synthesis = supervisor_result.get('supervisor_synthesis', '')
                                                if supervisor_synthesis:
                                                    self.alert_manager.alerts_collection.update_one(
                                                        {"_id": ObjectId(mongo_id)},
                                                        {"$set": {
                                                            "ai_supervisor": {
                                                                "synthesis": supervisor_synthesis,
                                                                "risk_level": risk_level,
                                                                "overall_confidence": overall_confidence,
                                                                "agent_summary": supervisor_result.get('agent_outputs', {})
                                                            }
                                                        }}
                                                    )
                                                    logger.info(f"   💾 Supervisor synthesis saved to alert {alert_id} (MongoDB _id: {mongo_id})")

                                            except Exception as supervisor_error:
                                                logger.error(f"⚠️ Supervisor Synthesis error: {supervisor_error}")

                                        except Exception as rca_error:
                                            logger.error(f"⚠️ RCA Agent error: {rca_error}")

                                    except Exception as investigation_error:
                                        logger.error(f"⚠️ Investigation Agent error: {investigation_error}")

                                # Notify WebSocket clients
                                await self.notify_websocket_clients({
                                    "type": "new_alert",
                                    "alert_id": alert_id,
                                    "severity": severity.value,
                                    "equipment_id": equipment_id,
                                    "excursion_type": excursion_type,
                                    "value": excursion_value,
                                    "timestamp": sensor_data.get("timestamp").isoformat() if hasattr(sensor_data.get("timestamp"), 'isoformat') else str(sensor_data.get("timestamp"))
                                })

                                # Trigger correlation analysis for all alerts (skip if AI agents enabled)
                                if not self.use_ai_agents:
                                    asyncio.create_task(self.run_alert_correlation(alert_id))

                                # Trigger RCA for critical alerts only (skip if AI agents enabled)
                                if not self.use_ai_agents:
                                    asyncio.create_task(self.run_alert_rca(alert_id, severity))

                                # Schedule wafer defect generation (with delay to simulate inspection)
                                asyncio.create_task(self.generate_delayed_wafer_defect({
                                    'alert_id': alert_id,
                                    'equipment_id': equipment_id,
                                    'excursion_type': excursion_type,
                                    'severity': severity.value,
                                    'timestamp': sensor_data.get('timestamp'),
                                    'metrics': metrics,
                                    'metadata': sensor_data.get('metadata', {})  # Pass metadata for process context!
                                }, delay_seconds=10))  # 10 seconds for demo, can be 7200 for realistic

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
    
    async def start_wafer_monitoring(self):
        """
        Background task for monitoring new wafer defects and generating alerts.
        Watches for high-severity wafers that aren't already linked to excursion alerts.
        """
        logger.info("Starting wafer defect monitoring loop with change streams")

        try:
            # Get async MongoDB connection
            async_client = AsyncIOMotorClient(self.mdb_uri)
            async_db = async_client[self.mdb_database_name]
            wafer_defects_collection = async_db["wafer_defects"]

            # Define change stream pipeline to watch for inserts
            pipeline = [
                {"$match": {"operationType": "insert"}}
            ]

            # Start watching the wafer_defects collection
            async with wafer_defects_collection.watch(pipeline) as stream:
                logger.info("✅ Change stream connected - monitoring wafer_defects collection")

                while self.monitoring_active:
                    try:
                        # Wait for the next change event
                        async for change in stream:
                            if not self.monitoring_active:
                                break

                            # Get the new wafer data
                            wafer_data = change.get("fullDocument")
                            if not wafer_data:
                                continue

                            wafer_id = wafer_data.get("wafer_id")
                            logger.debug(f"New wafer detected: {wafer_id}")

                            # Check if this wafer is already linked to an excursion alert
                            process_context = wafer_data.get("process_context", {})
                            if "excursion_alert_id" in process_context:
                                logger.debug(f"Wafer {wafer_id} already linked to alert {process_context['excursion_alert_id']}, skipping")
                                continue

                            # Get defect summary
                            defect_summary = wafer_data.get("defect_summary", {})
                            severity = defect_summary.get("severity", "low")
                            yield_pct = defect_summary.get("yield_percentage", 100)
                            defect_pattern = defect_summary.get("defect_pattern", "random")

                            # Only create alerts for high-severity wafers
                            if severity != "high":
                                logger.debug(f"Wafer {wafer_id} severity is {severity}, not creating alert")
                                continue

                            # Determine alert type based on defect characteristics
                            if defect_pattern in ["clustered", "systematic"]:
                                alert_type = AlertType.DEFECT_CLUSTER
                                title = f"Defect Cluster Detected on {wafer_id}"
                                description = f"{defect_pattern.title()} defect pattern detected with {yield_pct:.1f}% yield"
                            elif yield_pct < 85:
                                alert_type = AlertType.YIELD_DROP
                                title = f"Severe Yield Drop on {wafer_id}"
                                description = f"Yield dropped to {yield_pct:.1f}% on wafer {wafer_id}"
                            else:
                                alert_type = AlertType.DEFECT_CLUSTER
                                title = f"High Severity Defects on {wafer_id}"
                                description = wafer_data.get("description", f"High severity {defect_pattern} defects detected")

                            # Determine alert severity based on yield
                            # All pattern-induced defects should be critical
                            if yield_pct < 85:
                                alert_severity = AlertSeverity.CRITICAL
                            else:
                                alert_severity = AlertSeverity.HIGH

                            # Create alert using AlertManager
                            if self.alert_manager:
                                alert_id = self.alert_manager.create_alert(
                                    alert_type=alert_type,
                                    severity=alert_severity,
                                    title=title,
                                    description=description,
                                    source_data={
                                        "wafer_id": wafer_id,
                                        "lot_id": wafer_data.get("lot_id"),
                                        "defect_summary": defect_summary,
                                        "inspection_timestamp": wafer_data.get("inspection_timestamp"),
                                        "process_context": process_context,
                                        "defects": wafer_data.get("defects", [])[:5]  # Include first 5 defects
                                    },
                                    equipment_id=process_context.get("equipment_used", [None])[0] if process_context.get("equipment_used") else None,
                                    lot_id=wafer_data.get("lot_id"),
                                    wafer_id=wafer_id
                                )

                                logger.info(f"🚨 Wafer alert created: {alert_id} for {wafer_id} ({defect_pattern}, {yield_pct:.1f}% yield)")

                                # Notify WebSocket clients
                                await self.notify_websocket_clients({
                                    "type": "wafer_alert",
                                    "alert_id": alert_id,
                                    "wafer_id": wafer_id,
                                    "severity": alert_severity.value,
                                    "yield_percentage": yield_pct,
                                    "defect_pattern": defect_pattern,
                                    "timestamp": wafer_data.get("inspection_timestamp")
                                })

                                # Trigger correlation analysis for wafer alerts too (skip if AI agents enabled)
                                if not self.use_ai_agents:
                                    asyncio.create_task(self.run_alert_correlation(alert_id))

                                # Trigger RCA for critical wafer alerts (skip if AI agents enabled)
                                if not self.use_ai_agents and alert_severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH]:
                                    asyncio.create_task(self.run_alert_rca(alert_id, alert_severity))

                    except asyncio.CancelledError:
                        logger.info("Wafer monitoring loop cancelled")
                        break
                    except Exception as e:
                        logger.error(f"Error processing wafer change stream event: {e}")
                        # Continue monitoring despite errors
                        continue

        except Exception as e:
            logger.error(f"Failed to establish wafer change stream: {e}")
            logger.info("Wafer monitoring fallback not implemented - requires change streams")

        finally:
            if 'async_client' in locals():
                async_client.close()
            logger.info("Wafer monitoring loop stopped")

