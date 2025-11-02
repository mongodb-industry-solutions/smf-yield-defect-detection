#!/usr/bin/env python3
"""
Regenerate embeddings for wafer_defects collection
Uses voyage-multimodal-3 to create embeddings from updated descriptions and images
"""

import asyncio
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.embedding_pipeline import EmbeddingPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def regenerate_wafer_embeddings():
    """Regenerate embeddings for all wafer defects"""

    logger.info("=" * 60)
    logger.info("Wafer Defect Embedding Regeneration")
    logger.info("=" * 60)
    logger.info("\nThis will:")
    logger.info("  1. Read all wafer defects from MongoDB")
    logger.info("  2. Generate multimodal embeddings (text + images)")
    logger.info("  3. Store embeddings back in wafer_defects collection")
    logger.info("\nUsing: voyage-multimodal-3 (1024-dimensional vectors)")
    logger.info("=" * 60)

    # Initialize pipeline
    pipeline = EmbeddingPipeline()
    await pipeline.initialize()

    # Process only wafer defects
    logger.info("\nProcessing wafer defects...")
    result = await pipeline.process_wafer_defects()

    # Display results
    logger.info("\n" + "=" * 60)
    logger.info("Embedding Generation Complete")
    logger.info("=" * 60)
    logger.info(f"✓ Total processed: {result['processed']} wafers")
    logger.info(f"✓ Multimodal embeddings: {result['multimodal']} (text + image)")
    logger.info(f"✓ Text-only embeddings: {result['processed'] - result['multimodal']}")
    logger.info(f"✗ Errors: {result['errors']}")

    if result['errors'] > 0:
        logger.warning("\nSome wafers had errors - check logs above for details")

    # Cleanup
    pipeline.cleanup()

    logger.info("\n✓ Embeddings regenerated successfully!")

    return result


if __name__ == "__main__":
    asyncio.run(regenerate_wafer_embeddings())
