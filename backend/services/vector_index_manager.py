"""
Vector Index Manager for Phase 3
Manages MongoDB Atlas Vector Search indexes
"""

import os
import logging
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import asyncio
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VectorIndexManager:
    """Manages MongoDB Atlas Vector Search indexes"""
    
    def __init__(self, mongodb_uri: str = None, database_name: str = "smf-yield-defect"):
        """
        Initialize the vector index manager
        
        Args:
            mongodb_uri: MongoDB connection string
            database_name: Database name
        """
        self.mongodb_uri = mongodb_uri or os.getenv("MONGODB_URI")
        self.client = AsyncIOMotorClient(self.mongodb_uri)
        self.db = self.client[database_name]
        
        # Vector index configurations
        self.vector_indexes = {
            "historical_knowledge_vector_index": {
                "collection": "historical_knowledge",
                "definition": {
                    "mappings": {
                        "dynamic": True,
                        "fields": {
                            "embedding": {
                                "type": "knnVector",
                                "dimensions": 1024,
                                "similarity": "cosine"
                            },
                            "document_type": {
                                "type": "string"
                            },
                            "process_area": {
                                "type": "string"
                            },
                            "defect_type": {
                                "type": "string"
                            }
                        }
                    }
                }
            },
            "wafer_defects_vector_index": {
                "collection": "wafer_defects",
                "definition": {
                    "mappings": {
                        "dynamic": True,
                        "fields": {
                            "embedding": {
                                "type": "knnVector",
                                "dimensions": 1024,
                                "similarity": "cosine"
                            },
                            "defect_summary.defect_pattern": {
                                "type": "string"
                            },
                            "defect_summary.severity": {
                                "type": "string"
                            },
                            "process_context.equipment_used": {
                                "type": "string"
                            }
                        }
                    }
                }
            },
            "alerts_vector_index": {
                "collection": "alerts",
                "definition": {
                    "mappings": {
                        "dynamic": True,
                        "fields": {
                            "embedding": {
                                "type": "knnVector",
                                "dimensions": 1024,
                                "similarity": "cosine"
                            },
                            "alert_type": {
                                "type": "string"
                            },
                            "severity": {
                                "type": "string"
                            },
                            "equipment": {
                                "type": "string"
                            }
                        }
                    }
                }
            }
        }

        # Text search index configurations (Atlas Search for full-text)
        self.text_indexes = {
            "wafer_defects_text_index": {
                "collection": "wafer_defects",
                "definition": {
                    "mappings": {
                        "dynamic": False,
                        "fields": {
                            "description": {
                                "type": "string",
                                "analyzer": "lucene.standard"
                            },
                            "equipment_id": {
                                "type": "string"
                            },
                            "defect_summary.defect_pattern": {
                                "type": "string",
                                "analyzer": "lucene.standard"
                            }
                        }
                    }
                }
            },
            "historical_knowledge_text_index": {
                "collection": "historical_knowledge",
                "definition": {
                    "mappings": {
                        "dynamic": False,
                        "fields": {
                            "title": {
                                "type": "string",
                                "analyzer": "lucene.standard"
                            },
                            "content": {
                                "type": "string",
                                "analyzer": "lucene.standard"
                            },
                            "equipment_id": {
                                "type": "string"
                            }
                        }
                    }
                }
            }
        }

        logger.info("Vector Index Manager initialized")
    
    async def create_search_index(
        self,
        collection_name: str,
        index_name: str,
        index_definition: Dict[str, Any]
    ) -> bool:
        """
        Create a vector search index using MongoDB command
        
        Args:
            collection_name: Name of the collection
            index_name: Name of the index
            index_definition: Index definition
            
        Returns:
            Success status
        """
        try:
            # Create search index using MongoDB command
            result = await self.db.command({
                "createSearchIndexes": collection_name,
                "indexes": [{
                    "name": index_name,
                    "definition": index_definition
                }]
            })
            
            logger.info(f"Created vector index {index_name} on {collection_name}")
            return True
            
        except Exception as e:
            # Check if index already exists
            if "already exists" in str(e).lower():
                logger.info(f"Vector index {index_name} already exists on {collection_name}")
                return True
            else:
                logger.error(f"Error creating vector index {index_name}: {e}")
                return False
    
    async def list_search_indexes(self, collection_name: str) -> List[Dict[str, Any]]:
        """
        List all search indexes for a collection
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            List of search indexes
        """
        try:
            # List search indexes
            cursor = self.db[collection_name].aggregate([
                {"$listSearchIndexes": {}}
            ])
            
            indexes = []
            async for index in cursor:
                indexes.append(index)
            
            return indexes
            
        except Exception as e:
            logger.error(f"Error listing search indexes for {collection_name}: {e}")
            return []
    
    async def drop_search_index(self, collection_name: str, index_name: str) -> bool:
        """
        Drop a search index
        
        Args:
            collection_name: Name of the collection
            index_name: Name of the index to drop
            
        Returns:
            Success status
        """
        try:
            # Drop search index using MongoDB command
            result = await self.db.command({
                "dropSearchIndex": collection_name,
                "name": index_name
            })
            
            logger.info(f"Dropped vector index {index_name} from {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error dropping vector index {index_name}: {e}")
            return False
    
    async def initialize_all_indexes(self) -> Dict[str, bool]:
        """
        Initialize all vector search indexes
        
        Returns:
            Dictionary with index names and creation status
        """
        results = {}
        
        for index_name, config in self.vector_indexes.items():
            collection_name = config["collection"]
            definition = config["definition"]
            
            # Create the index
            success = await self.create_search_index(
                collection_name=collection_name,
                index_name=index_name,
                index_definition=definition
            )
            
            results[index_name] = success
            
            if success:
                logger.info(f"✓ {index_name} initialized successfully")
            else:
                logger.warning(f"✗ {index_name} initialization failed")
        
        return results
    
    async def verify_indexes(self) -> Dict[str, Dict[str, Any]]:
        """
        Verify all vector search indexes
        
        Returns:
            Dictionary with index verification details
        """
        verification_results = {}
        
        for index_name, config in self.vector_indexes.items():
            collection_name = config["collection"]
            
            # List indexes for this collection
            indexes = await self.list_search_indexes(collection_name)
            
            # Find the specific index
            index_found = False
            index_details = None
            
            for index in indexes:
                if index.get("name") == index_name:
                    index_found = True
                    index_details = {
                        "status": index.get("status", "unknown"),
                        "queryable": index.get("queryable", False),
                        "latestDefinition": index.get("latestDefinition", {})
                    }
                    break
            
            verification_results[index_name] = {
                "collection": collection_name,
                "exists": index_found,
                "details": index_details
            }
            
            if index_found:
                logger.info(f"✓ {index_name}: Found (status: {index_details.get('status')})")
            else:
                logger.warning(f"✗ {index_name}: Not found")
        
        return verification_results
    
    async def wait_for_indexes_ready(
        self,
        timeout_seconds: int = 300,
        check_interval: int = 10
    ) -> bool:
        """
        Wait for all indexes to become queryable
        
        Args:
            timeout_seconds: Maximum time to wait
            check_interval: Seconds between checks
            
        Returns:
            True if all indexes are ready, False if timeout
        """
        start_time = datetime.now()
        
        while (datetime.now() - start_time).total_seconds() < timeout_seconds:
            verification = await self.verify_indexes()
            
            all_ready = True
            for index_name, details in verification.items():
                if not details["exists"]:
                    all_ready = False
                    logger.info(f"Waiting for {index_name} to be created...")
                elif details["details"] and not details["details"].get("queryable"):
                    all_ready = False
                    status = details["details"].get("status", "unknown")
                    logger.info(f"Waiting for {index_name} to become queryable (status: {status})...")
            
            if all_ready:
                logger.info("All vector indexes are ready!")
                return True
            
            await asyncio.sleep(check_interval)
        
        logger.warning(f"Timeout waiting for indexes after {timeout_seconds} seconds")
        return False
    
    def cleanup(self):
        """Clean up resources"""
        self.client.close()
        logger.info("Vector Index Manager cleaned up")


# Example usage and testing
if __name__ == "__main__":
    async def test_vector_index_manager():
        manager = VectorIndexManager()
        
        # Initialize all indexes
        logger.info("Initializing vector search indexes...")
        results = await manager.initialize_all_indexes()
        
        # Print results
        print("\nInitialization Results:")
        for index_name, success in results.items():
            status = "✓" if success else "✗"
            print(f"  {status} {index_name}")
        
        # Verify indexes
        print("\nVerifying indexes...")
        verification = await manager.verify_indexes()
        
        print("\nVerification Results:")
        for index_name, details in verification.items():
            print(f"\n  {index_name}:")
            print(f"    Collection: {details['collection']}")
            print(f"    Exists: {details['exists']}")
            if details['details']:
                print(f"    Status: {details['details'].get('status')}")
                print(f"    Queryable: {details['details'].get('queryable')}")
        
        # Wait for indexes to be ready
        print("\nWaiting for indexes to become queryable...")
        ready = await manager.wait_for_indexes_ready(timeout_seconds=60)
        
        if ready:
            print("\n✓ All vector indexes are ready for use!")
        else:
            print("\n✗ Some indexes are not ready yet")
        
        manager.cleanup()
    
    asyncio.run(test_vector_index_manager())