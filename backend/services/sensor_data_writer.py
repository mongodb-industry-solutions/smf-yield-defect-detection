"""
Sensor Data Writer Service
Implements dual-write pattern for both real-time monitoring and historical analysis.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import BulkWriteError, PyMongoError
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)


class SensorDataWriter:
    """
    Handles dual writing of sensor data to both:
    1. sensor_events - Regular collection for real-time monitoring (change streams)
    2. process_sensor_ts - Time series collection for historical analysis
    """

    def __init__(self, mongodb_uri: str, database: str = "smf-yield-defect"):
        """
        Initialize the sensor data writer.

        Args:
            mongodb_uri: MongoDB connection string
            database: Database name
        """
        # Sync client for time series (better performance)
        self.client = MongoClient(mongodb_uri)
        self.db = self.client[database]

        # Async client for real-time events
        self.async_client = AsyncIOMotorClient(mongodb_uri)
        self.async_db = self.async_client[database]

        # Collections
        self.sensor_events = self.db["sensor_events"]  # Regular collection
        self.process_sensor_ts = self.db["process_sensor_ts"]  # Time series collection

        # Async collections
        self.async_sensor_events = self.async_db["sensor_events"]

        logger.info("SensorDataWriter initialized")

    def write_sensor_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synchronously write sensor data to both collections.

        Args:
            data: Sensor data document

        Returns:
            Dict with insert results
        """
        results = {
            "sensor_events": None,
            "process_sensor_ts": None,
            "success": False,
            "errors": []
        }

        # Ensure timestamp is datetime object
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"].replace('Z', '+00:00'))

        try:
            # Write to sensor_events (for real-time monitoring)
            try:
                result_events = self.sensor_events.insert_one(data.copy())
                results["sensor_events"] = str(result_events.inserted_id)
                logger.debug(f"Inserted into sensor_events: {result_events.inserted_id}")
            except Exception as e:
                logger.error(f"Failed to insert into sensor_events: {e}")
                results["errors"].append(f"sensor_events: {str(e)}")

            # Write to process_sensor_ts (for historical analysis)
            try:
                result_ts = self.process_sensor_ts.insert_one(data.copy())
                results["process_sensor_ts"] = str(result_ts.inserted_id)
                logger.debug(f"Inserted into process_sensor_ts: {result_ts.inserted_id}")
            except Exception as e:
                logger.error(f"Failed to insert into process_sensor_ts: {e}")
                results["errors"].append(f"process_sensor_ts: {str(e)}")

            # Mark success if at least one write succeeded
            results["success"] = bool(results["sensor_events"] or results["process_sensor_ts"])

        except Exception as e:
            logger.error(f"Unexpected error in dual write: {e}")
            results["errors"].append(f"general: {str(e)}")

        return results

    async def write_sensor_data_async(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Asynchronously write sensor data to both collections.

        Args:
            data: Sensor data document

        Returns:
            Dict with insert results
        """
        results = {
            "sensor_events": None,
            "process_sensor_ts": None,
            "success": False,
            "errors": []
        }

        # Ensure timestamp is datetime object
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"].replace('Z', '+00:00'))

        try:
            # Parallel writes using asyncio.gather
            tasks = []

            # Task 1: Write to sensor_events
            async def write_events():
                try:
                    result = await self.async_sensor_events.insert_one(data.copy())
                    return "sensor_events", str(result.inserted_id), None
                except Exception as e:
                    return "sensor_events", None, str(e)

            # Task 2: Write to process_sensor_ts (using sync in thread)
            async def write_timeseries():
                try:
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None,
                        self.process_sensor_ts.insert_one,
                        data.copy()
                    )
                    return "process_sensor_ts", str(result.inserted_id), None
                except Exception as e:
                    return "process_sensor_ts", None, str(e)

            # Execute both writes in parallel
            write_results = await asyncio.gather(write_events(), write_timeseries())

            # Process results
            for collection, inserted_id, error in write_results:
                if inserted_id:
                    results[collection] = inserted_id
                    logger.debug(f"Inserted into {collection}: {inserted_id}")
                if error:
                    results["errors"].append(f"{collection}: {error}")
                    logger.error(f"Failed to insert into {collection}: {error}")

            # Mark success if at least one write succeeded
            results["success"] = bool(results["sensor_events"] or results["process_sensor_ts"])

        except Exception as e:
            logger.error(f"Unexpected error in async dual write: {e}")
            results["errors"].append(f"general: {str(e)}")

        return results

    def bulk_write_sensor_data(self, data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Bulk write sensor data to both collections.

        Args:
            data_list: List of sensor data documents

        Returns:
            Dict with bulk insert results
        """
        results = {
            "sensor_events": {"inserted": 0, "failed": 0},
            "process_sensor_ts": {"inserted": 0, "failed": 0},
            "total": len(data_list),
            "errors": []
        }

        if not data_list:
            return results

        # Ensure all timestamps are datetime objects
        for data in data_list:
            if isinstance(data.get("timestamp"), str):
                data["timestamp"] = datetime.fromisoformat(data["timestamp"].replace('Z', '+00:00'))

        # Bulk write to sensor_events
        try:
            result_events = self.sensor_events.insert_many([d.copy() for d in data_list])
            results["sensor_events"]["inserted"] = len(result_events.inserted_ids)
            logger.info(f"Bulk inserted {len(result_events.inserted_ids)} into sensor_events")
        except BulkWriteError as bwe:
            results["sensor_events"]["inserted"] = bwe.details.get('nInserted', 0)
            results["sensor_events"]["failed"] = len(data_list) - results["sensor_events"]["inserted"]
            results["errors"].append(f"sensor_events bulk write error: {bwe.details}")
            logger.error(f"Bulk write error for sensor_events: {bwe.details}")
        except Exception as e:
            results["sensor_events"]["failed"] = len(data_list)
            results["errors"].append(f"sensor_events: {str(e)}")
            logger.error(f"Failed bulk insert to sensor_events: {e}")

        # Bulk write to process_sensor_ts
        try:
            result_ts = self.process_sensor_ts.insert_many([d.copy() for d in data_list])
            results["process_sensor_ts"]["inserted"] = len(result_ts.inserted_ids)
            logger.info(f"Bulk inserted {len(result_ts.inserted_ids)} into process_sensor_ts")
        except BulkWriteError as bwe:
            results["process_sensor_ts"]["inserted"] = bwe.details.get('nInserted', 0)
            results["process_sensor_ts"]["failed"] = len(data_list) - results["process_sensor_ts"]["inserted"]
            results["errors"].append(f"process_sensor_ts bulk write error: {bwe.details}")
            logger.error(f"Bulk write error for process_sensor_ts: {bwe.details}")
        except Exception as e:
            results["process_sensor_ts"]["failed"] = len(data_list)
            results["errors"].append(f"process_sensor_ts: {str(e)}")
            logger.error(f"Failed bulk insert to process_sensor_ts: {e}")

        return results

    def get_latest_from_realtime(self, equipment_id: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """
        Get latest sensor data from real-time collection.

        Args:
            equipment_id: Optional equipment filter
            limit: Number of records to return

        Returns:
            List of sensor documents
        """
        query = {}
        if equipment_id:
            query["equipment_id"] = equipment_id

        cursor = self.sensor_events.find(query).sort("timestamp", -1).limit(limit)
        return list(cursor)

    def get_historical_data(
        self,
        start_time: datetime,
        end_time: datetime,
        equipment_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Get historical sensor data from time series collection.

        Args:
            start_time: Start of time range
            end_time: End of time range
            equipment_id: Optional equipment filter

        Returns:
            List of sensor documents
        """
        query = {
            "timestamp": {
                "$gte": start_time,
                "$lte": end_time
            }
        }
        if equipment_id:
            query["equipment_id"] = equipment_id

        cursor = self.process_sensor_ts.find(query).sort("timestamp", 1)
        return list(cursor)

    def close(self):
        """Close database connections."""
        self.client.close()
        self.async_client.close()
        logger.info("SensorDataWriter connections closed")


# Example usage
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Initialize writer
    writer = SensorDataWriter(os.getenv("MONGODB_URI"))

    # Test data
    test_data = {
        "timestamp": datetime.utcnow(),
        "equipment_id": "CMP_TOOL_01",
        "process_step": "CMP",
        "metrics": {
            "particle_count": 850,
            "rf_power": 1450.5,
            "chamber_pressure": 45.2,
            "temperature": 65.3,
            "flow_rate": 200.5
        },
        "metadata": {
            "lot_id": "LOT_2025_001",
            "wafer_id": "W_001",
            "recipe_id": "CMP_RECIPE_01",
            "operator_id": "OP_100"
        }
    }

    # Test synchronous write
    print("Testing synchronous dual write...")
    result = writer.write_sensor_data(test_data)
    print(f"Result: {result}")

    # Test bulk write
    print("\nTesting bulk write...")
    bulk_data = []
    for i in range(5):
        data = test_data.copy()
        data["timestamp"] = datetime.utcnow()
        data["metadata"]["wafer_id"] = f"W_{i:03d}"
        bulk_data.append(data)

    bulk_result = writer.bulk_write_sensor_data(bulk_data)
    print(f"Bulk result: {bulk_result}")

    # Test retrieval
    print("\nTesting data retrieval...")
    latest = writer.get_latest_from_realtime(limit=3)
    print(f"Latest {len(latest)} records from real-time collection")

    # Close connections
    writer.close()