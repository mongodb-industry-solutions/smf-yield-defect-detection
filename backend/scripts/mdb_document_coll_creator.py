#!/usr/bin/env python3
"""
MongoDB Document Collection Creator for SMF Yield Defect Detection.
Creates document collections for wafer defects, process context, and historical knowledge.
"""

import os
import logging
from pymongo import MongoClient, ASCENDING, TEXT
from pymongo.errors import CollectionInvalid, OperationFailure
from dotenv import load_dotenv
from typing import Dict, List, Any

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DocumentCollectionCreator:
    """Creates and configures MongoDB document collections for SMF data."""
    
    def __init__(self):
        """Initialize MongoDB connection."""
        self.mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
        self.database_name = "smf-yield-defect"
        self.appname = os.getenv("APP_NAME", "devrel-demo-vectorsearch-langgraph-semiconductor")
        self.client = MongoClient(self.mongodb_uri, appname=self.appname)
        self.db = self.client[self.database_name]
        logger.info(f"Connected to MongoDB database: {self.database_name}")
    
    def create_wafer_defects_collection(self) -> Dict[str, Any]:
        """
        Create wafer_defects collection with appropriate indexes.
        
        Returns:
            Dictionary with creation status and details
        """
        collection_name = "wafer_defects"
        
        try:
            # Check if collection exists
            if collection_name in self.db.list_collection_names():
                logger.info(f"Collection '{collection_name}' already exists")
                return {
                    "status": "exists",
                    "collection": collection_name,
                    "message": "Collection already exists"
                }
            
            # Create collection
            collection = self.db.create_collection(collection_name)
            logger.info(f"Created collection: {collection_name}")
            
            # Create indexes for efficient querying
            indexes_created = []
            
            # Index on wafer_id for unique identification
            collection.create_index("wafer_id", unique=True)
            indexes_created.append("wafer_id (unique)")
            
            # Index on lot_id for batch queries
            collection.create_index("lot_id")
            indexes_created.append("lot_id")
            
            # Index on inspection timestamp for time-based queries
            collection.create_index([("inspection_timestamp", ASCENDING)])
            indexes_created.append("inspection_timestamp")
            
            # Compound index for equipment and timestamp
            collection.create_index([
                ("process_context.equipment_used", ASCENDING),
                ("inspection_timestamp", ASCENDING)
            ])
            indexes_created.append("equipment_used + timestamp")
            
            # Index on defect pattern for pattern analysis
            collection.create_index("defect_summary.defect_pattern")
            indexes_created.append("defect_pattern")
            
            # Index on severity for priority queries
            collection.create_index("defect_summary.severity")
            indexes_created.append("severity")
            
            # Text index on description for text search
            collection.create_index([("description", TEXT)])
            indexes_created.append("description (text)")
            
            logger.info(f"Created indexes: {', '.join(indexes_created)}")
            
            return {
                "status": "created",
                "collection": collection_name,
                "indexes": indexes_created,
                "message": f"Successfully created collection with {len(indexes_created)} indexes"
            }
            
        except Exception as e:
            logger.error(f"Error creating collection '{collection_name}': {e}")
            return {
                "status": "error",
                "collection": collection_name,
                "error": str(e)
            }
    
    def create_process_context_collection(self) -> Dict[str, Any]:
        """
        Create process_context collection for slurry batches, recipes, etc.
        
        Returns:
            Dictionary with creation status and details
        """
        collection_name = "process_context"
        
        try:
            # Check if collection exists
            if collection_name in self.db.list_collection_names():
                logger.info(f"Collection '{collection_name}' already exists")
                return {
                    "status": "exists",
                    "collection": collection_name,
                    "message": "Collection already exists"
                }
            
            # Create collection
            collection = self.db.create_collection(collection_name)
            logger.info(f"Created collection: {collection_name}")
            
            # Create indexes
            indexes_created = []
            
            # Index on context_id for unique identification
            collection.create_index("context_id", unique=True)
            indexes_created.append("context_id (unique)")
            
            # Index on context_type for filtering
            collection.create_index("context_type")
            indexes_created.append("context_type")
            
            # Index for problematic items
            collection.create_index("is_problematic")
            indexes_created.append("is_problematic")
            
            # Compound index for type and QC status
            collection.create_index([
                ("context_type", ASCENDING),
                ("slurry_details.qc_status", ASCENDING)
            ])
            indexes_created.append("type + qc_status")
            
            logger.info(f"Created indexes: {', '.join(indexes_created)}")
            
            return {
                "status": "created",
                "collection": collection_name,
                "indexes": indexes_created,
                "message": f"Successfully created collection with {len(indexes_created)} indexes"
            }
            
        except Exception as e:
            logger.error(f"Error creating collection '{collection_name}': {e}")
            return {
                "status": "error",
                "collection": collection_name,
                "error": str(e)
            }
    
    def create_historical_knowledge_collection(self) -> Dict[str, Any]:
        """
        Create historical_knowledge collection for RCA reports and guides.
        
        Returns:
            Dictionary with creation status and details
        """
        collection_name = "historical_knowledge"
        
        try:
            # Check if collection exists
            if collection_name in self.db.list_collection_names():
                logger.info(f"Collection '{collection_name}' already exists")
                return {
                    "status": "exists",
                    "collection": collection_name,
                    "message": "Collection already exists"
                }
            
            # Create collection
            collection = self.db.create_collection(collection_name)
            logger.info(f"Created collection: {collection_name}")
            
            # Create indexes
            indexes_created = []
            
            # Index on document_type
            collection.create_index("document_type")
            indexes_created.append("document_type")
            
            # Index on metadata fields
            collection.create_index("metadata.process_area")
            indexes_created.append("process_area")
            
            collection.create_index("metadata.defect_type")
            indexes_created.append("defect_type")
            
            collection.create_index("metadata.severity")
            indexes_created.append("severity")
            
            # Text index on content for full-text search
            collection.create_index([
                ("title", TEXT),
                ("content", TEXT)
            ])
            indexes_created.append("title + content (text)")
            
            # Index on tags for categorization
            collection.create_index("tags")
            indexes_created.append("tags")
            
            # Index on created_date for recent documents
            collection.create_index([("created_date", ASCENDING)])
            indexes_created.append("created_date")
            
            logger.info(f"Created indexes: {', '.join(indexes_created)}")
            
            return {
                "status": "created",
                "collection": collection_name,
                "indexes": indexes_created,
                "message": f"Successfully created collection with {len(indexes_created)} indexes"
            }
            
        except Exception as e:
            logger.error(f"Error creating collection '{collection_name}': {e}")
            return {
                "status": "error",
                "collection": collection_name,
                "error": str(e)
            }
    
    def create_all_collections(self) -> Dict[str, Any]:
        """
        Create all document collections.
        
        Returns:
            Summary of all collection creation results
        """
        results = {
            "wafer_defects": self.create_wafer_defects_collection(),
            "process_context": self.create_process_context_collection(),
            "historical_knowledge": self.create_historical_knowledge_collection()
        }
        
        # Summary
        created = sum(1 for r in results.values() if r["status"] == "created")
        existing = sum(1 for r in results.values() if r["status"] == "exists")
        errors = sum(1 for r in results.values() if r["status"] == "error")
        
        summary = {
            "total_collections": len(results),
            "created": created,
            "existing": existing,
            "errors": errors,
            "details": results
        }
        
        logger.info(f"Collection creation summary: {created} created, {existing} existing, {errors} errors")
        
        return summary
    
    def drop_all_collections(self) -> Dict[str, Any]:
        """
        Drop all SMF collections (use with caution).
        
        Returns:
            Summary of dropped collections
        """
        collections = ["wafer_defects", "process_context", "historical_knowledge"]
        dropped = []
        
        for collection_name in collections:
            try:
                if collection_name in self.db.list_collection_names():
                    self.db.drop_collection(collection_name)
                    dropped.append(collection_name)
                    logger.info(f"Dropped collection: {collection_name}")
            except Exception as e:
                logger.error(f"Error dropping collection '{collection_name}': {e}")
        
        return {
            "dropped": dropped,
            "count": len(dropped),
            "message": f"Dropped {len(dropped)} collections"
        }


def main():
    """Main function to create all collections."""
    creator = DocumentCollectionCreator()
    
    print("=" * 60)
    print("MongoDB Document Collection Creator for SMF")
    print("=" * 60)
    
    # Create all collections
    results = creator.create_all_collections()
    
    print(f"\nSummary:")
    print(f"  - Collections created: {results['created']}")
    print(f"  - Collections existing: {results['existing']}")
    print(f"  - Errors: {results['errors']}")
    
    # Display details
    print("\nDetails:")
    for collection, details in results['details'].items():
        status_symbol = "✓" if details['status'] in ['created', 'exists'] else "✗"
        print(f"  {status_symbol} {collection}: {details.get('message', details.get('error'))}")
        if details['status'] == 'created' and 'indexes' in details:
            print(f"    Indexes: {', '.join(details['indexes'])}")
    
    print("\n✓ Document collections setup complete!")


if __name__ == "__main__":
    main()