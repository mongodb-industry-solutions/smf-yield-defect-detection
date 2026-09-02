"""
Embedding Generation Pipeline for Phase 3
Processes existing data to generate embeddings
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import json
import base64
import boto3
from botocore.exceptions import ClientError
import io
from PIL import Image

from services.embedding_service import EmbeddingService

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmbeddingPipeline:
    """Pipeline for generating embeddings for existing data"""
    
    def __init__(self, mongodb_uri: str = None, database_name: str = "smf-yield-defect"):
        """
        Initialize the embedding pipeline
        
        Args:
            mongodb_uri: MongoDB connection string
            database_name: Database name
        """
        self.mongodb_uri = mongodb_uri or os.getenv("MONGODB_URI")
        self.appname = os.getenv("APP_NAME", "devrel-fastapi-smf-yield-defect-detection")
        self.client = AsyncIOMotorClient(self.mongodb_uri, appname=self.appname)
        self.db = self.client[database_name]
        
        # Initialize embedding service
        self.embedding_service = EmbeddingService(
            mongodb_uri=self.mongodb_uri,
            database_name=database_name
        )
        
        # Initialize S3 client if available
        self.s3_client = None
        self.s3_bucket = None
        s3_uri = os.getenv("S3_BUCKET_URI", "")
        if s3_uri:
            try:
                self.s3_client = boto3.client('s3')
                # Parse S3 URI
                if s3_uri.startswith("s3://"):
                    path = s3_uri[5:]
                    parts = path.split("/", 1)
                    self.s3_bucket = parts[0]
                logger.info(f"S3 client initialized for bucket: {self.s3_bucket}")
            except Exception as e:
                logger.warning(f"S3 client initialization failed: {e}")
                self.s3_client = None
        
        # Collections to process
        self.collections_config = {
            "historical_knowledge": {
                "text_fields": ["title", "content"],
                "metadata_fields": ["document_type", "defect_pattern", "equipment_id", "process_area"]
            },
            "wafer_defects": {
                "text_fields": ["wafer_id", "lot_id", "description"],
                "metadata_fields": ["defect_summary.defect_pattern", "defect_summary.severity"],
                "s3_image_field": "ink_map.full_image_url",  # S3 URL for full image
                "fallback_image_field": "ink_map.thumbnail_base64"  # Fallback to thumbnail
            },
            "alerts": {
                "text_fields": ["alert_type", "description", "affected_equipment"],
                "metadata_fields": ["severity", "status"]
            }
        }
        
        # Statistics
        self.stats = {
            "total_documents": 0,
            "embeddings_generated": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None
        }
        
        logger.info("Embedding Pipeline initialized")
    
    async def initialize(self):
        """Initialize the pipeline and services"""
        await self.embedding_service.initialize()
        logger.info("Pipeline services initialized")
    
    async def _fetch_image_from_s3(self, s3_url: str) -> Optional[str]:
        """
        Fetch image from S3 and return as base64
        
        Args:
            s3_url: S3 URL (s3://bucket/key)
            
        Returns:
            Base64 encoded image or None if failed
        """
        if not self.s3_client or not s3_url:
            return None
        
        try:
            # Parse S3 URL
            if not s3_url.startswith("s3://"):
                return None
            
            path = s3_url[5:]  # Remove s3://
            parts = path.split("/", 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else ""
            
            # Fetch from S3
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            image_data = response['Body'].read()
            
            # Convert to base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            logger.debug(f"Fetched image from S3: {s3_url}")
            return image_base64
            
        except ClientError as e:
            logger.warning(f"Failed to fetch image from S3 {s3_url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching image from S3: {e}")
            return None
    
    def _get_nested_field(self, document: Dict[str, Any], field_path: str) -> Any:
        """
        Get nested field value from document using dot notation
        
        Args:
            document: Document to extract from
            field_path: Dot-separated field path (e.g., "ink_map.full_image_url")
            
        Returns:
            Field value or None if not found
        """
        try:
            value = document
            for part in field_path.split("."):
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    return None
            return value
        except:
            return None
    
    def _create_text_content(
        self,
        document: Dict[str, Any],
        text_fields: List[str],
        metadata_fields: List[str]
    ) -> str:
        """
        Create text content for embedding from document fields
        
        Args:
            document: Document to process
            text_fields: Main text fields to include
            metadata_fields: Metadata fields to include
            
        Returns:
            Combined text content
        """
        content_parts = []
        
        # Add main text fields
        for field in text_fields:
            # Handle nested fields with dot notation
            if "." in field:
                value = self._get_nested_field(document, field)
            else:
                value = document.get(field)
            
            if value:
                if isinstance(value, str):
                    content_parts.append(value)
                elif isinstance(value, dict):
                    # Handle nested fields
                    for key, val in value.items():
                        if val:
                            content_parts.append(f"{key}: {val}")
        
        # Add metadata as context
        metadata_parts = []
        for field in metadata_fields:
            # Handle nested fields with dot notation
            if "." in field:
                value = self._get_nested_field(document, field)
                if value:
                    field_name = field.split(".")[-1]  # Use last part as field name
                    metadata_parts.append(f"{field_name}: {value}")
            else:
                value = document.get(field)
                if value:
                    if field == "metadata" and isinstance(value, dict):
                        for key, val in value.items():
                            if val:
                                metadata_parts.append(f"{key}: {val}")
                    else:
                        metadata_parts.append(f"{field}: {value}")
        
        if metadata_parts:
            content_parts.append("Context: " + ", ".join(metadata_parts))
        
        return " ".join(content_parts)
    
    async def process_historical_knowledge(self) -> Dict[str, int]:
        """
        Generate embeddings for historical knowledge documents
        
        Returns:
            Processing statistics
        """
        try:
            collection = self.db["historical_knowledge"]
            config = self.collections_config["historical_knowledge"]
            
            # Get all documents
            documents = await collection.find({}).to_list(length=None)
            logger.info(f"Processing {len(documents)} historical knowledge documents")
            
            processed = 0
            errors = 0
            
            for doc in documents:
                try:
                    # Create text content
                    text_content = self._create_text_content(
                        doc,
                        config["text_fields"],
                        config["metadata_fields"]
                    )
                    
                    # Generate embedding
                    embedding = await self.embedding_service.generate_text_embedding(
                        text_content,
                        use_cache=True
                    )
                    
                    # Store embedding
                    await self.embedding_service.store_document_embedding(
                        document_id=str(doc["_id"]),
                        collection_name="historical_knowledge",
                        embedding=embedding,
                        embedding_type="text",
                        metadata={
                            "document_type": doc.get("document_type"),
                            "defect_pattern": doc.get("defect_pattern"),
                            "equipment_id": doc.get("equipment_id"),
                            "process_area": doc.get("process_area")
                        }
                    )
                    
                    processed += 1
                    
                    if processed % 10 == 0:
                        logger.info(f"Processed {processed}/{len(documents)} knowledge documents")
                    
                except Exception as e:
                    logger.error(f"Error processing knowledge document {doc.get('_id')}: {e}")
                    errors += 1
            
            logger.info(f"✓ Historical knowledge: {processed} embeddings generated, {errors} errors")
            
            return {"processed": processed, "errors": errors}
            
        except Exception as e:
            logger.error(f"Error processing historical knowledge: {e}")
            return {"processed": 0, "errors": 1}
    
    async def process_wafer_defects(self) -> Dict[str, int]:
        """
        Generate embeddings for wafer defect records
        
        Returns:
            Processing statistics
        """
        try:
            collection = self.db["wafer_defects"]
            config = self.collections_config["wafer_defects"]
            
            # Get all documents
            documents = await collection.find({}).to_list(length=None)
            logger.info(f"Processing {len(documents)} wafer defect records")
            
            processed = 0
            errors = 0
            multimodal_count = 0
            
            for doc in documents:
                try:
                    # Create text content
                    text_content = self._create_text_content(
                        doc,
                        config["text_fields"],
                        config["metadata_fields"]
                    )
                    
                    # Add defect summary if available
                    if "defect_summary" in doc:
                        summary = doc["defect_summary"]
                        text_content += f" Defect count: {summary.get('defect_count', 0)}"
                        text_content += f" Yield impact: {summary.get('yield_impact', 0)}%"
                    
                    # Try to get image data
                    image_data = None
                    
                    # First try S3 full image
                    if config.get("s3_image_field"):
                        s3_url = self._get_nested_field(doc, config["s3_image_field"])
                        if s3_url:
                            image_data = await self._fetch_image_from_s3(s3_url)
                            if image_data:
                                logger.debug(f"Using S3 full image for {doc.get('wafer_id')}")
                    
                    # Fallback to thumbnail if S3 fetch failed
                    if not image_data and config.get("fallback_image_field"):
                        image_data = self._get_nested_field(doc, config["fallback_image_field"])
                        if image_data:
                            logger.debug(f"Using thumbnail fallback for {doc.get('wafer_id')}")
                    
                    if image_data:
                        # Generate multimodal embedding (text + image)
                        embedding = await self.embedding_service.generate_image_embedding(
                            image_data=image_data,
                            text_context=text_content
                        )
                        embedding_type = "multimodal"
                        multimodal_count += 1
                    else:
                        # Generate text-only embedding
                        embedding = await self.embedding_service.generate_text_embedding(
                            text_content,
                            use_cache=True
                        )
                        embedding_type = "text"
                    
                    # Store embedding
                    await self.embedding_service.store_document_embedding(
                        document_id=str(doc["_id"]),
                        collection_name="wafer_defects",
                        embedding=embedding,
                        embedding_type=embedding_type,
                        metadata={
                            "defect_pattern": doc.get("defect_summary", {}).get("defect_pattern"),
                            "severity": doc.get("defect_summary", {}).get("severity"),
                            "equipment_used": doc.get("process_context", {}).get("equipment_used"),
                            "yield_percentage": doc.get("defect_summary", {}).get("yield_percentage")
                        }
                    )
                    
                    processed += 1
                    
                    if processed % 10 == 0:
                        logger.info(f"Processed {processed}/{len(documents)} wafer defects")
                    
                except Exception as e:
                    logger.error(f"Error processing wafer defect {doc.get('_id')}: {e}")
                    errors += 1
            
            logger.info(f"✓ Wafer defects: {processed} embeddings ({multimodal_count} multimodal), {errors} errors")
            
            return {
                "processed": processed,
                "errors": errors,
                "multimodal": multimodal_count
            }
            
        except Exception as e:
            logger.error(f"Error processing wafer defects: {e}")
            return {"processed": 0, "errors": 1, "multimodal": 0}
    
    async def process_alerts(self) -> Dict[str, int]:
        """
        Generate embeddings for alert records
        
        Returns:
            Processing statistics
        """
        try:
            collection = self.db["alerts"]
            config = self.collections_config["alerts"]
            
            # Get all documents
            documents = await collection.find({}).to_list(length=None)
            logger.info(f"Processing {len(documents)} alert records")
            
            processed = 0
            errors = 0
            
            # Process in batches for efficiency
            batch_size = 10
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                texts = []
                doc_ids = []
                metadata_list = []
                
                for doc in batch:
                    try:
                        # Create text content
                        text_content = self._create_text_content(
                            doc,
                            config["text_fields"],
                            config["metadata_fields"]
                        )
                        
                        # Add excursion details if available
                        if "excursion_details" in doc:
                            details = doc["excursion_details"]
                            text_content += f" Metric: {details.get('metric')}"
                            text_content += f" Value: {details.get('value')}"
                            text_content += f" Threshold: {details.get('threshold')}"
                        
                        texts.append(text_content)
                        doc_ids.append(str(doc["_id"]))
                        metadata_list.append({
                            "alert_type": doc.get("alert_type"),
                            "severity": doc.get("severity"),
                            "equipment": doc.get("affected_equipment"),
                            "status": doc.get("status")
                        })
                        
                    except Exception as e:
                        logger.error(f"Error preparing alert {doc.get('_id')}: {e}")
                        errors += 1
                
                if texts:
                    try:
                        # Generate batch embeddings
                        embeddings = await self.embedding_service.generate_text_embeddings_batch(
                            texts,
                            use_cache=True
                        )
                        
                        # Store embeddings
                        for doc_id, embedding, metadata in zip(doc_ids, embeddings, metadata_list):
                            await self.embedding_service.store_document_embedding(
                                document_id=doc_id,
                                collection_name="alerts",
                                embedding=embedding,
                                embedding_type="text",
                                metadata=metadata
                            )
                            processed += 1
                        
                        logger.info(f"Processed batch {i//batch_size + 1}: {processed}/{len(documents)} alerts")
                        
                    except Exception as e:
                        logger.error(f"Error processing alert batch: {e}")
                        errors += len(texts)
            
            logger.info(f"✓ Alerts: {processed} embeddings generated, {errors} errors")
            
            return {"processed": processed, "errors": errors}
            
        except Exception as e:
            logger.error(f"Error processing alerts: {e}")
            return {"processed": 0, "errors": 1}
    
    async def run_pipeline(self) -> Dict[str, Any]:
        """
        Run the complete embedding generation pipeline
        
        Returns:
            Pipeline execution summary
        """
        logger.info("=" * 60)
        logger.info("Starting Embedding Generation Pipeline")
        logger.info("=" * 60)
        
        self.stats["start_time"] = datetime.now()
        
        # Initialize services
        await self.initialize()
        
        # Process each collection
        results = {}
        
        # Historical knowledge
        logger.info("\n1. Processing Historical Knowledge...")
        results["historical_knowledge"] = await self.process_historical_knowledge()
        
        # Wafer defects
        logger.info("\n2. Processing Wafer Defects...")
        results["wafer_defects"] = await self.process_wafer_defects()
        
        # Alerts
        logger.info("\n3. Processing Alerts...")
        results["alerts"] = await self.process_alerts()
        
        # Calculate totals
        self.stats["end_time"] = datetime.now()
        self.stats["duration"] = (self.stats["end_time"] - self.stats["start_time"]).total_seconds()
        
        total_processed = sum(r.get("processed", 0) for r in results.values())
        total_errors = sum(r.get("errors", 0) for r in results.values())
        
        self.stats["total_documents"] = total_processed + total_errors
        self.stats["embeddings_generated"] = total_processed
        self.stats["errors"] = total_errors
        
        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("Pipeline Execution Summary")
        logger.info("=" * 60)
        logger.info(f"Total documents: {self.stats['total_documents']}")
        logger.info(f"Embeddings generated: {self.stats['embeddings_generated']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info(f"Duration: {self.stats['duration']:.2f} seconds")
        logger.info("\nDetails by collection:")
        for collection, stats in results.items():
            logger.info(f"  {collection}: {stats}")
        
        return {
            "stats": self.stats,
            "results": results
        }
    
    def cleanup(self):
        """Clean up resources"""
        self.embedding_service.cleanup()
        self.client.close()
        logger.info("Embedding Pipeline cleaned up")


# Example usage
if __name__ == "__main__":
    async def test_embedding_pipeline():
        pipeline = EmbeddingPipeline()
        
        # Run the pipeline
        summary = await pipeline.run_pipeline()
        
        # Save summary to file
        with open("phase3_embedding_summary.json", "w") as f:
            json.dump(summary, f, indent=2, default=str)
        
        logger.info(f"\nSummary saved to phase3_embedding_summary.json")
        
        pipeline.cleanup()
    
    asyncio.run(test_embedding_pipeline())