#!/usr/bin/env python3
"""
Load historical knowledge into MongoDB and generate embeddings
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
from services.embedding_pipeline import EmbeddingPipeline

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def load_historical_knowledge():
    """Load historical knowledge from JSON file into MongoDB"""

    logger.info("=" * 60)
    logger.info("Loading Historical Knowledge into MongoDB")
    logger.info("=" * 60)

    # MongoDB connection
    mongodb_uri = os.getenv("MONGODB_URI")
    client = AsyncIOMotorClient(mongodb_uri)
    db = client["smf-yield-defect"]

    # Path to JSON file
    json_file = "data_generation/equipment_wafer_defects/historical_knowledge_manuals.json"

    if not os.path.exists(json_file):
        logger.error(f"File not found: {json_file}")
        client.close()
        return False

    logger.info(f"\n1. Reading JSON file: {json_file}")

    try:
        with open(json_file, 'r') as f:
            knowledge_data = json.load(f)

        logger.info(f"   Loaded {len(knowledge_data)} historical knowledge documents from JSON")
    except Exception as e:
        logger.error(f"Error reading JSON file: {e}")
        client.close()
        return False

    # Analyze document types
    rca_reports = [d for d in knowledge_data if d['document_type'] == 'RCA Report']
    tech_manuals = [d for d in knowledge_data if d['document_type'] == 'Technical Manual']

    logger.info(f"   • RCA Reports: {len(rca_reports)}")
    logger.info(f"   • Technical Manuals: {len(tech_manuals)}")

    # Clear existing historical knowledge collection
    logger.info("\n2. Clearing existing historical_knowledge collection...")
    collection = db["historical_knowledge"]
    delete_result = await collection.delete_many({})
    logger.info(f"   Deleted {delete_result.deleted_count} existing documents")

    # Insert new data
    logger.info("\n3. Inserting new historical knowledge...")

    result = await collection.insert_many(knowledge_data)
    total_inserted = len(result.inserted_ids)
    logger.info(f"   ✓ Inserted {total_inserted} historical knowledge documents")

    # Verify
    logger.info("\n4. Verification...")
    count = await collection.count_documents({})
    logger.info(f"   Total documents in collection: {count}")

    # Show breakdown
    edge_count = await collection.count_documents({"defect_pattern": "edge"})
    systematic_count = await collection.count_documents({"defect_pattern": "systematic"})

    logger.info(f"\n   By Defect Pattern:")
    logger.info(f"     Edge (Temperature Drift): {edge_count}")
    logger.info(f"     Systematic (RF/Pressure Drift): {systematic_count}")

    client.close()

    logger.info("\n" + "=" * 60)
    logger.info("✓ Historical knowledge loaded successfully!")
    logger.info("=" * 60)

    return True


async def generate_embeddings():
    """Generate embeddings for historical knowledge"""

    logger.info("\n" + "=" * 60)
    logger.info("Generating Embeddings for Historical Knowledge")
    logger.info("=" * 60)
    logger.info("\nThis will:")
    logger.info("  1. Read all historical knowledge from MongoDB")
    logger.info("  2. Generate text embeddings using voyage-multimodal-3")
    logger.info("  3. Store embeddings back in historical_knowledge collection")
    logger.info("\nUsing: voyage-multimodal-3 (1024-dimensional vectors)")
    logger.info("=" * 60)

    # Initialize pipeline
    pipeline = EmbeddingPipeline()
    await pipeline.initialize()

    # Process historical knowledge
    logger.info("\nProcessing historical knowledge documents...")
    result = await pipeline.process_historical_knowledge()

    # Display results
    logger.info("\n" + "=" * 60)
    logger.info("Embedding Generation Complete")
    logger.info("=" * 60)
    logger.info(f"✓ Total processed: {result['processed']} documents")
    logger.info(f"✗ Errors: {result['errors']}")

    if result['errors'] > 0:
        logger.warning("\nSome documents had errors - check logs above for details")

    # Cleanup
    pipeline.cleanup()

    logger.info("\n✓ Historical knowledge embeddings generated successfully!")

    return result


async def main():
    """Main execution function"""

    # Step 1: Load JSON data into MongoDB
    success = await load_historical_knowledge()

    if not success:
        logger.error("Failed to load historical knowledge. Exiting.")
        return

    # Step 2: Generate embeddings
    await generate_embeddings()

    logger.info("\n" + "=" * 60)
    logger.info("✓ COMPLETE! Historical knowledge loaded and embedded")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
