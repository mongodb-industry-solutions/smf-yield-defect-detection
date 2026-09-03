"""
Background service for automatic sensor data cleanup.

Since process_sensor_ts is a timeseries collection, we can't add TTL index
after creation. This service runs hourly to delete EXCURSION sensor readings
older than 1 hour, while preserving normal baseline readings for historical charts.
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

class SensorCleanupService:
    """
    Automatically deletes EXCURSION sensor readings older than 1 hour.
    Keeps normal baseline readings for historical charts and analytics.
    Runs cleanup every 1 hour to align with TTL duration.
    """

    def __init__(self, mongodb_uri: str, database_name: str):
        """
        Initialize sensor cleanup service.

        Args:
            mongodb_uri: MongoDB connection string
            database_name: Database name containing process_sensor_ts collection
        """
        app_name = os.getenv("APP_NAME", "devrel-demo-vectorsearch-langgraph-semiconductor")
        self.client = AsyncIOMotorClient(mongodb_uri, appname=app_name)
        self.db = self.client[database_name]
        self.sensor_collection = self.db["process_sensor_ts"]
        self.ttl_hours = 1  # Delete sensors older than 1 hour
        self.cleanup_interval = 3600  # Run every 1 hour (matches TTL)

    async def cleanup_old_sensors(self):
        """
        Delete EXCURSION sensor readings older than TTL duration.
        Only deletes readings with anomalous values (high particle count, temp, or RF power).
        Keeps normal baseline readings for historical charts.

        Returns:
            int: Number of documents deleted
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.ttl_hours)

        try:
            # Only delete EXCURSION data (not normal baseline readings)
            result = await self.sensor_collection.delete_many({
                "timestamp": {"$lt": cutoff_time},
                "$or": [
                    {"metrics.particle_count": {"$gt": 1000}},  # Excursion threshold
                    {"metrics.rf_power": {"$gt": 1400}},         # Excursion threshold
                    {"metrics.temperature": {"$gt": 75}}         # Excursion threshold
                ]
            })

            deleted_count = result.deleted_count
            if deleted_count > 0:
                logger.info(
                    f"🧹 Sensor cleanup: Deleted {deleted_count} excursion readings "
                    f"older than {self.ttl_hours} hour(s) (keeps baseline data)"
                )

            return deleted_count

        except Exception as e:
            logger.error(f"❌ Sensor cleanup error: {e}", exc_info=True)
            return 0

    async def start(self):
        """
        Start background cleanup task.
        Runs indefinitely, cleaning up old sensors every hour.
        """
        logger.info(
            f"🚀 Sensor cleanup service started "
            f"(TTL: {self.ttl_hours}h, interval: {self.cleanup_interval/60:.0f} min)"
        )

        while True:
            try:
                await self.cleanup_old_sensors()
                await asyncio.sleep(self.cleanup_interval)
            except Exception as e:
                logger.error(f"❌ Sensor cleanup loop error: {e}", exc_info=True)
                # Continue running even if cleanup fails
                await asyncio.sleep(self.cleanup_interval)

    async def stop(self):
        """Stop cleanup service and close MongoDB connection"""
        logger.info("🛑 Sensor cleanup service stopped")
        self.client.close()
