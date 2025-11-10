#!/usr/bin/env python3
"""
Load wafer defects JSON data into MongoDB and generate embeddings.

Usage:
    uv run python scripts/load_wafer_defects_and_embed.py <json_file_path>

Example:
    uv run python scripts/load_wafer_defects_and_embed.py data_generation/wafer_defects_enhanced.json
"""

import os
import sys
import json
import asyncio
import logging
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from services.embedding_pipeline import EmbeddingPipeline

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


async def load_wafer_defects_to_mongodb(json_file_path: str, clear_existing: bool = False):
    """
    Load wafer defects from JSON file into MongoDB.

    Args:
        json_file_path: Path to the JSON file containing wafer defects
        clear_existing: If True, delete existing wafer_defects collection before loading

    Returns:
        Number of documents inserted
    """

    # Validate file path
    file_path = Path(json_file_path)
    if not file_path.exists():
        logger.error(f"File not found: {json_file_path}")
        return 0

    # MongoDB connection
    mongodb_uri = os.getenv("MONGODB_URI")
    if not mongodb_uri:
        logger.error("MONGODB_URI not found in environment variables")
        return 0

    db_name = os.getenv("MDB_DATABASE_NAME", "smf-yield-defect")

    logger.info("=" * 70)
    logger.info("Loading Wafer Defects into MongoDB")
    logger.info("=" * 70)
    logger.info(f"Source file: {json_file_path}")
    logger.info(f"Database: {db_name}")
    logger.info(f"Collection: wafer_defects")
    if clear_existing:
        logger.warning("⚠ Will DELETE existing wafer_defects collection!")

    client = AsyncIOMotorClient(mongodb_uri)
    db = client[db_name]
    collection = db["wafer_defects"]

    try:
        # Load JSON data
        logger.info(f"\nReading JSON file...")
        with open(file_path, 'r') as f:
            wafer_data = json.load(f)

        if not isinstance(wafer_data, list):
            logger.error("JSON data must be a list of wafer defect documents")
            return 0

        logger.info(f"✓ Loaded {len(wafer_data)} wafer defects from JSON")

        # Clear existing data if requested
        if clear_existing:
            logger.info("\nClearing existing wafer_defects collection...")
            result = await collection.delete_many({})
            logger.info(f"✓ Deleted {result.deleted_count} existing documents")

        # Insert data in batches
        logger.info("\nInserting wafer defects into MongoDB...")
        batch_size = 100
        total_inserted = 0

        for i in range(0, len(wafer_data), batch_size):
            batch = wafer_data[i:i + batch_size]
            result = await collection.insert_many(batch)
            total_inserted += len(result.inserted_ids)

            progress = (total_inserted / len(wafer_data)) * 100
            logger.info(f"  Progress: {total_inserted}/{len(wafer_data)} ({progress:.1f}%)")

        logger.info(f"\n✓ Successfully inserted {total_inserted} wafer defects")

        # Verify insertion
        doc_count = await collection.count_documents({})
        logger.info(f"✓ Collection now contains {doc_count} total documents")

        return total_inserted

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON file: {e}")
        return 0
    except Exception as e:
        logger.error(f"Error loading wafer defects: {e}")
        import traceback
        traceback.print_exc()
        return 0
    finally:
        client.close()


async def generate_wafer_embeddings():
    """
    Generate embeddings for wafer defects using the embedding pipeline.

    Returns:
        Dictionary with embedding generation statistics
    """

    logger.info("\n" + "=" * 70)
    logger.info("Generating Embeddings for Wafer Defects")
    logger.info("=" * 70)

    try:
        # Initialize embedding pipeline
        pipeline = EmbeddingPipeline()
        await pipeline.initialize()

        logger.info("\nProcessing wafer defects...")
        logger.info("This will:")
        logger.info("  1. Find wafer defects without embeddings")
        logger.info("  2. Generate embeddings using voyage-multimodal-3")
        logger.info("  3. Update documents with embedding field")
        logger.info("\nNote: This may take several minutes for 100+ documents\n")

        # Process wafer defects
        stats = await pipeline.process_wafer_defects()

        # Display results
        logger.info("\n" + "=" * 70)
        logger.info("Embedding Generation Results")
        logger.info("=" * 70)
        logger.info(f"Documents processed: {stats.get('processed', 0)}")
        logger.info(f"Embeddings generated: {stats.get('embeddings_generated', 0)}")
        logger.info(f"Errors: {stats.get('errors', 0)}")

        if stats.get('errors', 0) > 0:
            logger.warning("⚠ Some embeddings failed to generate. Check logs for details.")

        pipeline.cleanup()

        return stats

    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


async def main():
    """Main execution function"""

    # Parse command line arguments
    if len(sys.argv) < 2:
        logger.error("Missing required argument: JSON file path")
        logger.info("\nUsage:")
        logger.info("  uv run python scripts/load_wafer_defects_and_embed.py <json_file_path> [--clear]")
        logger.info("\nExample:")
        logger.info("  uv run python scripts/load_wafer_defects_and_embed.py data_generation/wafer_defects_enhanced.json")
        logger.info("\nOptions:")
        logger.info("  --clear    Delete existing wafer_defects collection before loading")
        sys.exit(1)

    json_file_path = sys.argv[1]
    clear_existing = "--clear" in sys.argv

    # Step 1: Load JSON data into MongoDB
    inserted_count = await load_wafer_defects_to_mongodb(json_file_path, clear_existing)

    if inserted_count == 0:
        logger.error("\n✗ Failed to load wafer defects. Aborting.")
        sys.exit(1)

    # Step 2: Generate embeddings
    stats = await generate_wafer_embeddings()

    if "error" in stats:
        logger.error("\n✗ Failed to generate embeddings")
        sys.exit(1)

    # Success summary
    logger.info("\n" + "=" * 70)
    logger.info("✓ COMPLETE!")
    logger.info("=" * 70)
    logger.info(f"Wafer defects loaded: {inserted_count}")
    logger.info(f"Embeddings generated: {stats.get('embeddings_generated', 0)}")
    logger.info("\nNext steps:")
    logger.info("  1. Verify data in MongoDB Atlas")
    logger.info("  2. Test search queries to see improved scores")
    logger.info("  3. Check AI agent responses for richer context")
    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
