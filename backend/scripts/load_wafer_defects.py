#!/usr/bin/env python3
"""
Load wafer_defects.json into MongoDB
"""

import asyncio
import logging
import json
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def load_wafer_defects():
    """Load wafer defects from JSON file into MongoDB"""

    logger.info("=" * 60)
    logger.info("Loading Wafer Defects into MongoDB")
    logger.info("=" * 60)

    # MongoDB connection
    mongodb_uri = os.getenv("MONGODB_URI")
    client = AsyncIOMotorClient(mongodb_uri)
    db = client["smf-yield-defect"]

    # Path to JSON file
    json_file = "data_generation/old_Data/wafer_defects.json"

    if not os.path.exists(json_file):
        logger.error(f"File not found: {json_file}")
        return

    logger.info(f"\n1. Reading JSON file: {json_file}")

    try:
        with open(json_file, 'r') as f:
            wafer_data = json.load(f)

        logger.info(f"   Loaded {len(wafer_data)} wafer defects from JSON")
    except Exception as e:
        logger.error(f"Error reading JSON file: {e}")
        client.close()
        return

    # Clear existing wafer defects collection
    logger.info("\n2. Clearing existing wafer_defects collection...")
    collection = db["wafer_defects"]
    delete_result = await collection.delete_many({})
    logger.info(f"   Deleted {delete_result.deleted_count} existing wafer defects")

    # Insert new data in batches
    logger.info("\n3. Inserting new wafer defects...")

    batch_size = 100
    total_inserted = 0

    for i in range(0, len(wafer_data), batch_size):
        batch = wafer_data[i:i + batch_size]
        result = await collection.insert_many(batch)
        total_inserted += len(result.inserted_ids)
        logger.info(f"   Inserted batch {i//batch_size + 1}: {total_inserted}/{len(wafer_data)} wafers")

    logger.info(f"\n✓ Successfully inserted {total_inserted} wafer defects")

    # Verify
    logger.info("\n4. Verification...")
    count = await collection.count_documents({})
    logger.info(f"   Total wafers in collection: {count}")

    # Show samples by defect pattern
    patterns = ["edge", "systematic", "clustered", "random"]
    for pattern in patterns:
        sample = await collection.find_one({"defect_summary.defect_pattern": pattern})
        if sample:
            logger.info(f"\n   {pattern.upper()} sample (Wafer {sample['wafer_id']}):")
            logger.info(f"     Description: {sample['description'][:80]}...")

    client.close()

    logger.info("\n" + "=" * 60)
    logger.info("✓ Wafer defects loaded successfully!")
    logger.info("=" * 60)
    logger.info("\nNext step: Run 'uv run python scripts/regenerate_wafer_embeddings.py'")


if __name__ == "__main__":
    asyncio.run(load_wafer_defects())
