"""
Excursion Detector Service
Real-time monitoring of sensor data using MongoDB Change Streams
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
import logging
from typing import Dict, Any, Optional, List
from bson import ObjectId
import os
from dotenv import load_dotenv

load_dotenv()

class ExcursionDetector:
    def __init__(self, mongodb_uri: str = None, database: str = "smf-yield-defect"):
        """Initialize the excursion detector with MongoDB connection"""
        self.mongodb_uri = mongodb_uri or os.getenv("MONGODB_URI")
        self.appname = os.getenv("APP_NAME", "devrel-demo-vectorsearch-langgraph-semiconductor")
        self.client = AsyncIOMotorClient(self.mongodb_uri, appname=self.appname)
        self.db = self.client[database]
        self.alerts_collection = self.db.alerts
        # Use sensor_events collection for real-time monitoring (supports change streams)
        self.sensor_collection = self.db.sensor_events  # Changed from process_sensor_ts
        # Keep reference to time series collection for historical queries
        self.timeseries_collection = self.db.process_sensor_ts
        self.logger = logging.getLogger(__name__)
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Threshold configuration
        self.thresholds = {
            "CMP": {
                "particle_count": {"value": 1000, "type": "absolute"},
                "rf_power": {"value": 100, "type": "drift"},
                "temperature": {"value": 2, "type": "drift"}
            },
            "ETCH": {
                "particle_count": {"value": 800, "type": "absolute"},
                "rf_power": {"value": 150, "type": "drift"},
                "chamber_pressure": {"value": 5, "type": "drift"}
            },
            "LITHO": {
                "overlay_error": {"value": 5, "type": "absolute"},
                "focus_drift": {"value": 2, "type": "drift"}
            }
        }
        
        # Store baseline values for drift detection
        self.baselines = {}
        self.monitoring_active = False
        self.monitoring_task = None
    
    async def initialize_baselines(self):
        """Initialize baseline values for drift detection"""
        self.logger.info("Initializing baseline values...")
        
        # Get latest sensor readings for each equipment
        pipeline = [
            {"$sort": {"timestamp": -1}},
            {"$group": {
                "_id": "$equipment_id",
                "latest": {"$first": "$$ROOT"}
            }}
        ]
        
        cursor = self.sensor_collection.aggregate(pipeline)
        async for doc in cursor:
            equipment_id = doc["_id"]
            metrics = doc["latest"]["metrics"]
            self.baselines[equipment_id] = metrics
            self.logger.info(f"Baseline set for {equipment_id}: {metrics}")
    
    async def start_monitoring(self):
        """Start monitoring sensor streams for excursions"""
        if self.monitoring_active:
            self.logger.warning("Monitoring is already active")
            return
        
        self.monitoring_active = True
        await self.initialize_baselines()
        
        # Define the change stream pipeline
        pipeline = [
            {
                '$match': {
                    'operationType': 'insert'
                }
            }
        ]
        
        self.logger.info("Starting Change Stream monitoring...")
        
        try:
            # Watch the time series collection
            async with self.sensor_collection.watch(
                pipeline, 
                full_document='updateLookup'
            ) as stream:
                self.logger.info("Change Stream connected successfully")
                
                async for change in stream:
                    if not self.monitoring_active:
                        break
                    
                    # Process the new sensor data
                    if 'fullDocument' in change:
                        await self.process_sensor_data(change['fullDocument'])
        
        except Exception as e:
            self.logger.error(f"Error in Change Stream monitoring: {e}")
            self.monitoring_active = False
            raise
    
    async def process_sensor_data(self, sensor_data: dict):
        """Process incoming sensor data and check for excursions"""
        equipment_id = sensor_data.get('equipment_id')
        process_step = sensor_data.get('process_step')
        metrics = sensor_data.get('metrics', {})
        
        self.logger.debug(f"Processing data from {equipment_id}: {metrics}")
        
        # Check thresholds for this process step
        if process_step not in self.thresholds:
            return
        
        violations = []
        process_thresholds = self.thresholds[process_step]
        
        for metric_name, threshold_config in process_thresholds.items():
            if metric_name not in metrics:
                continue
            
            current_value = metrics[metric_name]
            threshold_value = threshold_config["value"]
            threshold_type = threshold_config["type"]
            
            if threshold_type == "absolute":
                # Check absolute threshold
                if current_value > threshold_value:
                    violations.append({
                        "metric": metric_name,
                        "current_value": current_value,
                        "threshold": threshold_value,
                        "type": "absolute",
                        "deviation": current_value - threshold_value
                    })
            
            elif threshold_type == "drift":
                # Check drift from baseline
                if equipment_id in self.baselines and metric_name in self.baselines[equipment_id]:
                    baseline_value = self.baselines[equipment_id][metric_name]
                    drift = abs(current_value - baseline_value)
                    
                    if drift > threshold_value:
                        violations.append({
                            "metric": metric_name,
                            "current_value": current_value,
                            "baseline": baseline_value,
                            "threshold": threshold_value,
                            "type": "drift",
                            "deviation": drift
                        })
        
        # Generate alert if violations found
        if violations:
            await self.generate_alert(sensor_data, violations)
        
        # Update baseline for this equipment (moving average)
        if equipment_id not in self.baselines:
            self.baselines[equipment_id] = {}
        
        for metric_name, value in metrics.items():
            if metric_name in self.baselines[equipment_id]:
                # Moving average with weight 0.1 for new value
                old_value = self.baselines[equipment_id][metric_name]
                self.baselines[equipment_id][metric_name] = 0.9 * old_value + 0.1 * value
            else:
                self.baselines[equipment_id][metric_name] = value
    
    async def generate_alert(self, sensor_data: dict, violations: List[dict]):
        """Generate and store an alert for detected excursions"""
        
        # Calculate severity based on violations
        severity = self.calculate_severity(violations)
        
        # Create alert document
        alert = {
            "_id": ObjectId(),
            "timestamp": datetime.utcnow(),
            "alert_type": "excursion",
            "severity": severity,
            "equipment_id": sensor_data.get('equipment_id'),
            "process_step": sensor_data.get('process_step'),
            "sensor_data": {
                "timestamp": sensor_data.get('timestamp'),
                "metrics": sensor_data.get('metrics'),
                "metadata": sensor_data.get('metadata')
            },
            "violations": violations,
            "status": "open",
            "assigned_to": None,
            "acknowledged": False,
            "acknowledged_by": None,
            "acknowledged_at": None,
            "resolution": None,
            "notes": [],
            "correlation_analysis": None,
            "rca_hints": None
        }
        
        # Store alert in database
        result = await self.alerts_collection.insert_one(alert)
        
        self.logger.warning(
            f"ALERT GENERATED - ID: {result.inserted_id}, "
            f"Severity: {severity}, Equipment: {sensor_data.get('equipment_id')}, "
            f"Violations: {[v['metric'] for v in violations]}"
        )
        
        # Trigger downstream analysis (will be implemented with correlation engine)
        asyncio.create_task(self.trigger_analysis(str(result.inserted_id)))
        
        return str(result.inserted_id)
    
    def calculate_severity(self, violations: List[dict]) -> str:
        """Calculate alert severity based on violations"""
        
        # Count critical violations
        critical_metrics = ['particle_count', 'overlay_error']
        critical_count = sum(1 for v in violations if v['metric'] in critical_metrics)
        
        # Calculate maximum deviation percentage
        max_deviation_pct = 0
        for violation in violations:
            if violation['type'] == 'absolute':
                deviation_pct = (violation['deviation'] / violation['threshold']) * 100
            else:  # drift
                deviation_pct = (violation['deviation'] / violation['threshold']) * 100
            max_deviation_pct = max(max_deviation_pct, deviation_pct)
        
        # Determine severity
        if critical_count > 0 and max_deviation_pct > 100:
            return "critical"
        elif critical_count > 0 or max_deviation_pct > 50:
            return "high"
        elif len(violations) > 2 or max_deviation_pct > 25:
            return "medium"
        else:
            return "low"
    
    async def stop_monitoring(self):
        """Stop the monitoring service"""
        self.logger.info("Stopping monitoring service...")
        self.monitoring_active = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
    
    async def get_active_alerts(self, limit: int = 100) -> List[dict]:
        """Get active (open) alerts"""
        cursor = self.alerts_collection.find(
            {"status": "open"}
        ).sort("timestamp", -1).limit(limit)
        
        alerts = []
        async for alert in cursor:
            alert['_id'] = str(alert['_id'])
            alerts.append(alert)
        
        return alerts
    
    async def acknowledge_alert(self, alert_id: str, user: str) -> bool:
        """Acknowledge an alert"""
        result = await self.alerts_collection.update_one(
            {"_id": ObjectId(alert_id)},
            {
                "$set": {
                    "acknowledged": True,
                    "acknowledged_by": user,
                    "acknowledged_at": datetime.utcnow(),
                    "status": "acknowledged"
                }
            }
        )
        
        return result.modified_count > 0
    
    async def resolve_alert(self, alert_id: str, resolution: str, user: str) -> bool:
        """Resolve an alert with resolution notes"""
        result = await self.alerts_collection.update_one(
            {"_id": ObjectId(alert_id)},
            {
                "$set": {
                    "status": "resolved",
                    "resolution": resolution,
                    "resolved_by": user,
                    "resolved_at": datetime.utcnow()
                }
            }
        )
        
        return result.modified_count > 0
    
    async def add_note_to_alert(self, alert_id: str, note: str, user: str) -> bool:
        """Add a note to an alert"""
        note_entry = {
            "timestamp": datetime.utcnow(),
            "user": user,
            "note": note
        }
        
        result = await self.alerts_collection.update_one(
            {"_id": ObjectId(alert_id)},
            {"$push": {"notes": note_entry}}
        )
        
        return result.modified_count > 0

# Standalone function to run the monitoring service
async def run_monitoring():
    """Run the monitoring service standalone"""
    detector = ExcursionDetector()
    
    try:
        await detector.start_monitoring()
    except KeyboardInterrupt:
        await detector.stop_monitoring()
        print("Monitoring stopped")

if __name__ == "__main__":
    # Run the monitoring service
    asyncio.run(run_monitoring())