"""
Alert Management System for Phase 2
Handles alert lifecycle, storage, and notification management
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum
import logging
from pymongo import MongoClient, DESCENDING
from pymongo.errors import DuplicateKeyError
from bson import ObjectId
import asyncio
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""
    CRITICAL = "critical"  # Immediate action required
    HIGH = "high"         # Urgent attention needed
    MEDIUM = "medium"     # Needs investigation
    LOW = "low"          # Informational


class AlertStatus(Enum):
    """Alert lifecycle states"""
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class AlertType(Enum):
    """Types of alerts"""
    EXCURSION = "excursion"
    DEFECT_CLUSTER = "defect_cluster"
    YIELD_DROP = "yield_drop"
    EQUIPMENT_DRIFT = "equipment_drift"
    BATCH_ISSUE = "batch_issue"


class AlertManager:
    """Manages alert lifecycle and notifications"""
    
    def __init__(self, mongodb_uri: str, database_name: str = "smf-yield-defect"):
        """
        Initialize Alert Manager
        
        Args:
            mongodb_uri: MongoDB connection string
            database_name: Database name
        """
        self.client = MongoClient(mongodb_uri)
        self.db = self.client[database_name]
        self.alerts_collection = self.db["alerts"]
        self.alert_history_collection = self.db["alert_history"]
        self.historical_knowledge_collection = self.db["historical_knowledge"]

        # Initialize semantic search service (lazy loading)
        self._semantic_search = None
        self._mongodb_uri = mongodb_uri
        self._database_name = database_name

        # Note: Call alert_manager.initialize() after creation to set up indexes
        
        # Alert thresholds and rules
        self.severity_rules = {
            "particle_count": {
                "critical": 2000,
                "high": 1500,
                "medium": 1000
            },
            "rf_power_drift": {
                "critical": 150,
                "high": 120,
                "medium": 100
            },
            "temperature_drift": {
                "critical": 5,
                "high": 3,
                "medium": 2
            },
            "yield_threshold": {
                "critical": 0.80,
                "high": 0.85,
                "medium": 0.92
            }
        }
    
    def initialize(self):
        """Initialize collections and indexes (must be called after creation)"""
        self._initialize_collections()
        logger.info("Alert Manager initialized")
        
    def _initialize_collections(self):
        """Create indexes for alert collections"""
        try:
            # Alerts collection indexes
            self.alerts_collection.create_index("alert_id", unique=True)
            self.alerts_collection.create_index([("timestamp", DESCENDING)])
            self.alerts_collection.create_index("status")
            self.alerts_collection.create_index("severity")
            self.alerts_collection.create_index("alert_type")
            self.alerts_collection.create_index("equipment_id")
            self.alerts_collection.create_index([("status", 1), ("severity", -1)])
            
            # Alert history indexes
            self.alert_history_collection.create_index("alert_id")
            self.alert_history_collection.create_index([("timestamp", DESCENDING)])
            
            logger.info("Alert collections initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing collections: {e}")

    def _get_semantic_search(self):
        """
        Lazy load semantic search service

        Returns:
            SemanticSearchService instance or None if unavailable
        """
        if self._semantic_search is None:
            try:
                from services.semantic_search import SemanticSearchService
                self._semantic_search = SemanticSearchService(
                    mongodb_uri=self._mongodb_uri,
                    database_name=self._database_name
                )
                logger.info("Semantic search service initialized for AlertManager")
            except Exception as e:
                logger.warning(f"Could not initialize semantic search: {e}")
                self._semantic_search = False  # Mark as unavailable

        return self._semantic_search if self._semantic_search is not False else None

    def create_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        description: str,
        source_data: Dict[str, Any],
        equipment_id: Optional[str] = None,
        lot_id: Optional[str] = None,
        wafer_id: Optional[str] = None
    ) -> str:
        """
        Create a new alert

        Args:
            alert_type: Type of alert
            severity: Alert severity level
            title: Alert title
            description: Detailed description
            source_data: Data that triggered the alert
            equipment_id: Equipment identifier
            lot_id: Lot identifier
            wafer_id: Wafer identifier
            
        Returns:
            Alert ID
        """
        try:
            alert_id = f"ALT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{ObjectId()}"
            
            alert_doc = {
                "alert_id": alert_id,
                "alert_type": alert_type.value,
                "severity": severity.value,
                "status": AlertStatus.OPEN.value,
                "title": title,
                "description": description,
                "timestamp": datetime.now(),
                "acknowledged_at": None,
                "resolved_at": None,
                "closed_at": None,
                "equipment_id": equipment_id,
                "lot_id": lot_id,
                "wafer_id": wafer_id,
                "source_data": source_data,
                # NOTE: Removed correlation_data and rca_recommendations fields
                # These are now set directly by CorrelationEngine and RCAGenerator
                "assigned_to": None,
                "resolution_notes": None,
                "estimated_impact": self._calculate_impact(severity, alert_type),
                "auto_generated": True,
                "notifications_sent": [],
                "escalation_level": 0
            }
            
            self.alerts_collection.insert_one(alert_doc)

            # Add to history
            self._add_to_history(alert_id, "created", f"Alert created: {title}")

            # Send notifications based on severity
            self._send_notifications(alert_id, severity)

            # Trigger async historical context search
            try:
                asyncio.create_task(self._add_historical_context_async(alert_id, alert_doc))
            except RuntimeError:
                # No event loop running (e.g., in tests)
                logger.debug("Could not create async task for historical context (no event loop)")

            logger.info(f"Alert created: {alert_id} - {title} [{severity.value}]")
            return alert_id
            
        except DuplicateKeyError:
            logger.error(f"Duplicate alert ID: {alert_id}")
            raise
        except Exception as e:
            logger.error(f"Error creating alert: {e}")
            raise

    def _build_historical_search_query(self, alert_doc: Dict[str, Any]) -> str:
        """
        Build semantic search query from alert document

        Args:
            alert_doc: Alert document

        Returns:
            Search query string
        """
        query_parts = []

        # Add alert type and description
        if alert_doc.get("alert_type"):
            query_parts.append(alert_doc["alert_type"])
        if alert_doc.get("description"):
            query_parts.append(alert_doc["description"])

        # Extract excursion context from source_data
        source_data = alert_doc.get("source_data", {})
        excursion_type = source_data.get("excursion_type", "")

        if excursion_type:
            # Convert particle_excursion -> "particle excursion"
            readable_type = excursion_type.replace("_", " ")
            query_parts.append(f"{readable_type} detected")

            # Add domain-specific keywords
            if "particle" in excursion_type:
                query_parts.append("particle contamination CMP slurry filter")
            elif "temperature" in excursion_type:
                query_parts.append("temperature drift thermal control cooling")
            elif "rf_power" in excursion_type:
                query_parts.append("RF power drift chamber condition recipe")

        # Add equipment context
        equipment_id = alert_doc.get("equipment_id", "")
        if equipment_id:
            query_parts.append(f"equipment {equipment_id}")

            # Add process-specific keywords based on equipment
            if "CMP" in equipment_id.upper():
                query_parts.append("chemical mechanical polishing slurry pad")
            elif "ETCH" in equipment_id.upper():
                query_parts.append("etching chamber plasma")
            elif "LITHO" in equipment_id.upper():
                query_parts.append("lithography reticle overlay")

        # Filter out empty strings and join
        query = " ".join(filter(None, query_parts))

        logger.debug(f"Built historical search query: {query[:100]}...")
        return query

    async def _find_similar_cases(self, alert_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find similar historical cases for an alert using semantic search

        Args:
            alert_doc: Alert document

        Returns:
            List of similar historical cases
        """
        try:
            # Get semantic search service
            semantic_search = self._get_semantic_search()
            if not semantic_search:
                logger.debug("Semantic search not available, skipping historical context")
                return []

            # Build query
            query = self._build_historical_search_query(alert_doc)
            if not query:
                logger.debug("Could not build search query, skipping historical context")
                return []

            # Initialize semantic search if needed
            if not hasattr(semantic_search, '_initialized'):
                await semantic_search.initialize()
                semantic_search._initialized = True

            # Search for similar RCA reports
            results = await semantic_search.search_knowledge_base(
                query=query,
                document_types=["rca_report"],
                limit=3,  # Top 3 most relevant
                min_score=0.6  # Minimum relevance threshold
            )

            # Format results
            formatted_cases = []
            for result in results:
                # Extract root cause (same logic as RCA generator - Fix #3)
                root_cause = (
                    result.get("findings", {}).get("root_cause") or
                    result.get("metadata", {}).get("root_cause") or
                    ""
                )

                case = {
                    "title": result.get("title", ""),
                    "root_cause": root_cause,
                    "resolution_time": result.get("metadata", {}).get("resolution_time_hours", 0),
                    "defect_type": result.get("metadata", {}).get("defect_type", ""),
                    "relevance_score": round(result.get("score", 0), 2)
                }
                formatted_cases.append(case)

            logger.info(f"Found {len(formatted_cases)} similar historical cases for alert")
            return formatted_cases

        except Exception as e:
            logger.error(f"Error finding similar historical cases: {e}")
            return []

    async def _add_historical_context_async(self, alert_id: str, alert_doc: Dict[str, Any]):
        """
        Add historical context to an alert asynchronously

        Args:
            alert_id: Alert identifier
            alert_doc: Alert document
        """
        try:
            # Search for similar cases with timeout
            historical_cases = await asyncio.wait_for(
                self._find_similar_cases(alert_doc),
                timeout=15.0  # 15 second timeout (increased for semantic search)
            )

            if not historical_cases:
                logger.debug(f"No historical cases found for alert {alert_id}")
                return

            # Update alert document with historical context in rca_analysis field
            # This ensures consistency with RCA-generated historical cases
            result = self.alerts_collection.update_one(
                {"alert_id": alert_id},
                {
                    "$set": {
                        "rca_analysis.similar_historical_cases": historical_cases,
                        "rca_analysis.historical_context_retrieved_at": datetime.now()
                    }
                }
            )

            if result.modified_count > 0:
                logger.info(f"✓ Added {len(historical_cases)} historical cases to alert {alert_id} (rca_analysis)")
            else:
                logger.warning(f"Could not update alert {alert_id} with historical context")

        except asyncio.TimeoutError:
            logger.warning(f"Historical search timeout for alert {alert_id} (>15s)")
        except Exception as e:
            logger.error(f"Error adding historical context to alert {alert_id}: {e}")

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str, notes: Optional[str] = None) -> bool:
        """
        Acknowledge an alert
        
        Args:
            alert_id: Alert identifier
            acknowledged_by: User acknowledging the alert
            notes: Optional acknowledgment notes
            
        Returns:
            Success status
        """
        try:
            result = self.alerts_collection.update_one(
                {"alert_id": alert_id, "status": AlertStatus.OPEN.value},
                {
                    "$set": {
                        "status": AlertStatus.ACKNOWLEDGED.value,
                        "acknowledged_at": datetime.now(),
                        "assigned_to": acknowledged_by,
                        "acknowledgment_notes": notes
                    }
                }
            )
            
            if result.modified_count > 0:
                self._add_to_history(
                    alert_id, 
                    "acknowledged", 
                    f"Alert acknowledged by {acknowledged_by}"
                )
                logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error acknowledging alert {alert_id}: {e}")
            return False
    
    def update_alert_status(
        self,
        alert_id: str,
        status: AlertStatus,
        updated_by: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        Update alert status
        
        Args:
            alert_id: Alert identifier
            status: New status
            updated_by: User updating the status
            notes: Optional status update notes
            
        Returns:
            Success status
        """
        try:
            update_doc = {
                "status": status.value,
                f"{status.value}_at": datetime.now()
            }
            
            if notes:
                update_doc[f"{status.value}_notes"] = notes
                
            result = self.alerts_collection.update_one(
                {"alert_id": alert_id},
                {"$set": update_doc}
            )
            
            if result.modified_count > 0:
                self._add_to_history(
                    alert_id,
                    f"status_changed_{status.value}",
                    f"Status changed to {status.value} by {updated_by}"
                )
                logger.info(f"Alert {alert_id} status changed to {status.value}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error updating alert {alert_id} status: {e}")
            return False
    
    def add_correlation_data(self, alert_id: str, correlation_data: Dict[str, Any]) -> bool:
        """
        Add correlation analysis results to an alert
        
        Args:
            alert_id: Alert identifier
            correlation_data: Correlation analysis results
            
        Returns:
            Success status
        """
        try:
            result = self.alerts_collection.update_one(
                {"alert_id": alert_id},
                {
                    "$set": {
                        "correlation_data": correlation_data,
                        "correlation_updated_at": datetime.now()
                    }
                }
            )
            
            if result.modified_count > 0:
                self._add_to_history(
                    alert_id,
                    "correlation_added",
                    "Correlation analysis results added"
                )
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error adding correlation data to alert {alert_id}: {e}")
            return False
    
    def add_rca_recommendations(self, alert_id: str, recommendations: List[Dict[str, Any]]) -> bool:
        """
        Add RCA recommendations to an alert
        
        Args:
            alert_id: Alert identifier
            recommendations: List of RCA recommendations
            
        Returns:
            Success status
        """
        try:
            result = self.alerts_collection.update_one(
                {"alert_id": alert_id},
                {
                    "$set": {
                        "rca_recommendations": recommendations,
                        "rca_updated_at": datetime.now()
                    }
                }
            )
            
            if result.modified_count > 0:
                self._add_to_history(
                    alert_id,
                    "rca_added",
                    f"Added {len(recommendations)} RCA recommendations"
                )
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error adding RCA recommendations to alert {alert_id}: {e}")
            return False
    
    def get_active_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        alert_type: Optional[AlertType] = None,
        equipment_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get active alerts with optional filtering
        
        Args:
            severity: Filter by severity
            alert_type: Filter by alert type
            equipment_id: Filter by equipment
            limit: Maximum number of alerts to return
            
        Returns:
            List of active alerts
        """
        try:
            query = {
                "status": {"$in": [
                    AlertStatus.OPEN.value,
                    AlertStatus.ACKNOWLEDGED.value,
                    AlertStatus.IN_PROGRESS.value
                ]}
            }
            
            if severity:
                query["severity"] = severity.value
            if alert_type:
                query["alert_type"] = alert_type.value
            if equipment_id:
                query["equipment_id"] = equipment_id
            
            cursor = self.alerts_collection.find(query).sort([("timestamp", -1)])
            alerts = list(cursor.limit(limit))
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error retrieving active alerts: {e}")
            return []
    
    def get_alert_by_id(self, alert_id: str) -> Optional[Dict[str, Any]]:
        """
        Get alert by ID
        
        Args:
            alert_id: Alert identifier
            
        Returns:
            Alert document or None
        """
        try:
            return self.alerts_collection.find_one({"alert_id": alert_id})
        except Exception as e:
            logger.error(f"Error retrieving alert {alert_id}: {e}")
            return None
    
    def get_alert_history(self, alert_id: str) -> List[Dict[str, Any]]:
        """
        Get alert history
        
        Args:
            alert_id: Alert identifier
            
        Returns:
            List of history entries
        """
        try:
            cursor = self.alert_history_collection.find({"alert_id": alert_id}).sort("timestamp", -1)
            return list(cursor)
        except Exception as e:
            logger.error(f"Error retrieving alert history for {alert_id}: {e}")
            return []
    
    def escalate_alert(self, alert_id: str, reason: str) -> bool:
        """
        Escalate an alert to higher priority
        
        Args:
            alert_id: Alert identifier
            reason: Escalation reason
            
        Returns:
            Success status
        """
        try:
            alert = self.get_alert_by_id(alert_id)
            if not alert:
                return False
            
            # Increase severity if not already critical
            current_severity = alert.get("severity")
            new_severity = current_severity
            
            if current_severity == AlertSeverity.LOW.value:
                new_severity = AlertSeverity.MEDIUM.value
            elif current_severity == AlertSeverity.MEDIUM.value:
                new_severity = AlertSeverity.HIGH.value
            elif current_severity == AlertSeverity.HIGH.value:
                new_severity = AlertSeverity.CRITICAL.value
            
            result = self.alerts_collection.update_one(
                {"alert_id": alert_id},
                {
                    "$set": {
                        "severity": new_severity,
                        "escalated_at": datetime.now(),
                        "escalation_reason": reason
                    },
                    "$inc": {"escalation_level": 1}
                }
            )
            
            if result.modified_count > 0:
                self._add_to_history(
                    alert_id,
                    "escalated",
                    f"Alert escalated from {current_severity} to {new_severity}: {reason}"
                )
                
                # Send escalation notifications
                self._send_escalation_notification(alert_id, new_severity, reason)
                
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error escalating alert {alert_id}: {e}")
            return False
    
    def auto_close_resolved_alerts(self, age_days: int = 7) -> int:
        """
        Automatically close resolved alerts older than specified days
        
        Args:
            age_days: Age threshold in days
            
        Returns:
            Number of alerts closed
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=age_days)
            
            result = self.alerts_collection.update_many(
                {
                    "status": AlertStatus.RESOLVED.value,
                    "resolved_at": {"$lt": cutoff_date}
                },
                {
                    "$set": {
                        "status": AlertStatus.CLOSED.value,
                        "closed_at": datetime.now(),
                        "auto_closed": True
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"Auto-closed {result.modified_count} resolved alerts")
            
            return result.modified_count
            
        except Exception as e:
            logger.error(f"Error auto-closing alerts: {e}")
            return 0
    
    def get_alert_statistics(self, time_window_hours: int = 24) -> Dict[str, Any]:
        """
        Get alert statistics for dashboard
        
        Args:
            time_window_hours: Time window for statistics
            
        Returns:
            Alert statistics
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
            
            pipeline = [
                {"$match": {"timestamp": {"$gte": cutoff_time}}},
                {
                    "$group": {
                        "_id": None,
                        "total_alerts": {"$sum": 1},
                        "by_severity": {
                            "$push": "$severity"
                        },
                        "by_status": {
                            "$push": "$status"
                        },
                        "by_type": {
                            "$push": "$alert_type"
                        },
                        "avg_resolution_time": {
                            "$avg": {
                                "$subtract": ["$resolved_at", "$timestamp"]
                            }
                        }
                    }
                }
            ]
            
            result = list(self.alerts_collection.aggregate(pipeline))
            
            if result:
                stats = result[0]
                
                # Count by category
                severity_counts = {}
                status_counts = {}
                type_counts = {}
                
                for sev in stats.get("by_severity", []):
                    severity_counts[sev] = severity_counts.get(sev, 0) + 1
                
                for status in stats.get("by_status", []):
                    status_counts[status] = status_counts.get(status, 0) + 1
                
                for alert_type in stats.get("by_type", []):
                    type_counts[alert_type] = type_counts.get(alert_type, 0) + 1
                
                return {
                    "total_alerts": stats.get("total_alerts", 0),
                    "by_severity": severity_counts,
                    "by_status": status_counts,
                    "by_type": type_counts,
                    "avg_resolution_time_ms": stats.get("avg_resolution_time"),
                    "time_window_hours": time_window_hours
                }
            
            return {
                "total_alerts": 0,
                "by_severity": {},
                "by_status": {},
                "by_type": {},
                "avg_resolution_time_ms": None,
                "time_window_hours": time_window_hours
            }
            
        except Exception as e:
            logger.error(f"Error calculating alert statistics: {e}")
            return {}
    
    def _calculate_impact(self, severity: AlertSeverity, alert_type: AlertType) -> str:
        """Calculate estimated impact based on severity and type"""
        impact_matrix = {
            (AlertSeverity.CRITICAL, AlertType.EXCURSION): "Production line stoppage likely",
            (AlertSeverity.CRITICAL, AlertType.YIELD_DROP): "Major yield loss expected",
            (AlertSeverity.HIGH, AlertType.DEFECT_CLUSTER): "Multiple wafers affected",
            (AlertSeverity.HIGH, AlertType.EQUIPMENT_DRIFT): "Process deviation increasing",
            (AlertSeverity.MEDIUM, AlertType.BATCH_ISSUE): "Batch quality compromised",
        }
        
        return impact_matrix.get(
            (severity, alert_type),
            f"{severity.value.capitalize()} {alert_type.value.replace('_', ' ')}"
        )
    
    def _add_to_history(self, alert_id: str, action: str, description: str):
        """Add entry to alert history"""
        try:
            history_entry = {
                "alert_id": alert_id,
                "timestamp": datetime.now(),
                "action": action,
                "description": description
            }
            self.alert_history_collection.insert_one(history_entry)
        except Exception as e:
            logger.error(f"Error adding to alert history: {e}")
    
    def _send_notifications(self, alert_id: str, severity: AlertSeverity):
        """Send notifications based on alert severity"""
        # In production, this would integrate with notification services
        # For now, just log the notification
        logger.info(f"Notification sent for alert {alert_id} with severity {severity.value}")
        
        # Update alert document
        self.alerts_collection.update_one(
            {"alert_id": alert_id},
            {
                "$push": {
                    "notifications_sent": {
                        "timestamp": datetime.now(),
                        "type": "initial",
                        "severity": severity.value
                    }
                }
            }
        )
    
    def _send_escalation_notification(self, alert_id: str, severity: str, reason: str):
        """Send escalation notification"""
        logger.info(f"Escalation notification sent for alert {alert_id}: {reason}")
        
        self.alerts_collection.update_one(
            {"alert_id": alert_id},
            {
                "$push": {
                    "notifications_sent": {
                        "timestamp": datetime.now(),
                        "type": "escalation",
                        "severity": severity,
                        "reason": reason
                    }
                }
            }
        )
    
    def cleanup(self):
        """Clean up resources"""
        self.client.close()
        logger.info("Alert Manager cleaned up")


# Example usage and testing
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    
    # Initialize Alert Manager
    alert_manager = AlertManager(mongodb_uri)
    
    # Create sample alerts
    sample_alert_id = alert_manager.create_alert(
        alert_type=AlertType.EXCURSION,
        severity=AlertSeverity.HIGH,
        title="High Particle Count Detected",
        description="Particle count exceeded 1500 on CMP-01",
        source_data={
            "equipment_id": "CMP-01",
            "particle_count": 1567,
            "timestamp": datetime.now().isoformat()
        },
        equipment_id="CMP-01",
        lot_id="LOT-2024-001"
    )
    
    print(f"Created alert: {sample_alert_id}")
    
    # Get active alerts
    active_alerts = alert_manager.get_active_alerts()
    print(f"Active alerts: {len(active_alerts)}")
    
    # Get statistics
    stats = alert_manager.get_alert_statistics()
    print(f"Alert statistics: {stats}")
    
    # Cleanup
    alert_manager.cleanup()