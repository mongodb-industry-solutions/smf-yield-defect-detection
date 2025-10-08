"""
Semantic Search Service for Phase 3
Provides semantic search capabilities using vector embeddings
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import numpy as np

from services.embedding_service import EmbeddingService

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SemanticSearchService:
    """Service for semantic search using vector embeddings"""
    
    def __init__(self, mongodb_uri: str = None, database_name: str = "smf-yield-defect"):
        """
        Initialize the semantic search service
        
        Args:
            mongodb_uri: MongoDB connection string
            database_name: Database name
        """
        self.mongodb_uri = mongodb_uri or os.getenv("MONGODB_URI")
        self.client = AsyncIOMotorClient(self.mongodb_uri)
        self.db = self.client[database_name]
        
        # Initialize embedding service
        self.embedding_service = EmbeddingService(
            mongodb_uri=self.mongodb_uri,
            database_name=database_name
        )
        
        # Search configurations
        self.search_configs = {
            "historical_knowledge": {
                "index_name": "historical_knowledge_vector_index",
                "collection": "historical_knowledge",
                "default_limit": 10,
                "min_score": 0.7
            },
            "wafer_defects": {
                "index_name": "wafer_defects_vector_index",
                "collection": "wafer_defects",
                "default_limit": 10,
                "min_score": 0.75
            },
            "alerts": {
                "index_name": "alerts_vector_index",
                "collection": "alerts",
                "default_limit": 10,
                "min_score": 0.7
            }
        }
        
        logger.info("Semantic Search Service initialized")
    
    async def initialize(self):
        """Initialize the service"""
        await self.embedding_service.initialize()
        logger.info("Semantic Search Service ready")
    
    async def search_knowledge_base(
        self,
        query: str,
        document_types: Optional[List[str]] = None,
        process_areas: Optional[List[str]] = None,
        limit: int = 10,
        min_score: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search the historical knowledge base semantically
        
        Args:
            query: Search query text
            document_types: Filter by document types (rca_report, troubleshooting_guide, etc.)
            process_areas: Filter by process areas (CMP, ETCH, LITHO, etc.)
            limit: Maximum number of results
            min_score: Minimum similarity score
            
        Returns:
            List of relevant documents with scores
        """
        try:
            # Generate query embedding
            query_embedding = await self.embedding_service.generate_text_embedding(query)
            
            # Build search pipeline
            pipeline = [
                {
                    "$search": {
                        "index": "historical_knowledge_vector_index",
                        "knnBeta": {
                            "vector": query_embedding,
                            "path": "embedding",
                            "k": limit * 3  # Get more candidates for filtering
                        }
                    }
                },
                {
                    "$addFields": {
                        "score": {"$meta": "searchScore"}
                    }
                },
                {
                    "$match": {
                        "score": {"$gte": min_score}
                    }
                }
            ]
            
            # Add filters if specified
            filters = {}
            if document_types:
                filters["document_type"] = {"$in": document_types}
            if process_areas:
                filters["process_area"] = {"$in": process_areas}
            
            if filters:
                pipeline.insert(3, {"$match": filters})
            
            # Add limit
            pipeline.append({"$limit": limit})
            
            # Execute search
            collection = self.db["historical_knowledge"]
            results = await collection.aggregate(pipeline).to_list(length=None)
            
            # Format results
            formatted_results = []
            for doc in results:
                formatted_results.append({
                    "id": str(doc["_id"]),
                    "title": doc.get("title"),
                    "document_type": doc.get("document_type"),
                    "process_area": doc.get("process_area"),
                    "defect_type": doc.get("defect_type"),
                    "content": doc.get("content", "")[:500] + "...",  # Truncate content
                    "summary": doc.get("summary"),
                    "score": doc.get("score"),
                    "metadata": doc.get("metadata", {}),
                    "findings": doc.get("findings", {})  # Include findings for root cause extraction
                })
            
            logger.info(f"Knowledge search for '{query[:50]}...' returned {len(formatted_results)} results")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error searching knowledge base: {e}")
            return []
    
    async def find_similar_defects(
        self,
        wafer_id: Optional[str] = None,
        pattern: Optional[str] = None,
        equipment: Optional[str] = None,
        image_data: Optional[str] = None,
        limit: int = 10,
        min_score: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Find similar wafer defects using vector similarity
        
        Args:
            wafer_id: Reference wafer ID to find similar defects
            pattern: Defect pattern to search for
            equipment: Filter by equipment
            image_data: Base64 encoded image for visual similarity
            limit: Maximum number of results
            min_score: Minimum similarity score
            
        Returns:
            List of similar defect records with scores
        """
        try:
            # Get query embedding based on input
            if wafer_id:
                # Get the reference wafer's embedding
                wafer = await self.db["wafer_defects"].find_one({"wafer_id": wafer_id})
                if not wafer or "embedding" not in wafer:
                    logger.warning(f"No embedding found for wafer {wafer_id}")
                    return []
                query_embedding = wafer["embedding"]
                
            elif image_data:
                # Generate multimodal embedding from image
                context = f"Defect pattern: {pattern}" if pattern else None
                query_embedding = await self.embedding_service.generate_image_embedding(
                    image_data=image_data,
                    text_context=context
                )
                
            elif pattern:
                # Generate text embedding from pattern description
                query_text = f"Wafer defect with {pattern} pattern"
                if equipment:
                    query_text += f" from {equipment}"
                query_embedding = await self.embedding_service.generate_text_embedding(query_text)
                
            else:
                logger.warning("No valid input for defect similarity search")
                return []
            
            # Build search pipeline
            pipeline = [
                {
                    "$search": {
                        "index": "wafer_defects_vector_index",
                        "knnBeta": {
                            "vector": query_embedding,
                            "path": "embedding",
                            "k": limit * 2
                        }
                    }
                },
                {
                    "$addFields": {
                        "score": {"$meta": "searchScore"}
                    }
                },
                {
                    "$match": {
                        "score": {"$gte": min_score}
                    }
                }
            ]
            
            # Add equipment filter if specified (wafers store equipment in array field)
            if equipment:
                pipeline.insert(3, {"$match": {"process_context.equipment_used": {"$in": [equipment]}}})
            
            # Exclude the reference wafer if searching by wafer_id
            if wafer_id:
                pipeline.insert(3, {"$match": {"wafer_id": {"$ne": wafer_id}}})
            
            # Add limit
            pipeline.append({"$limit": limit})
            
            # Execute search
            collection = self.db["wafer_defects"]
            results = await collection.aggregate(pipeline).to_list(length=None)
            
            # Format results
            formatted_results = []
            for doc in results:
                # Extract equipment from array (get first if available)
                equipment_array = doc.get("process_context", {}).get("equipment_used", [])
                equipment_str = equipment_array[0] if equipment_array else "N/A"

                # Get yield percentage from defect_summary
                yield_pct = doc.get("defect_summary", {}).get("yield_percentage", 0)

                # Get full thumbnail (don't truncate for frontend display)
                thumbnail_base64 = doc.get("ink_map", {}).get("thumbnail_base64", "")

                formatted_results.append({
                    "wafer_id": doc.get("wafer_id"),
                    "lot_id": doc.get("lot_id"),
                    "pattern": doc.get("defect_summary", {}).get("defect_pattern"),  # Frontend expects "pattern"
                    "equipment": equipment_str,
                    "yield": yield_pct,  # Frontend expects "yield"
                    "inspection_timestamp": doc.get("inspection_timestamp"),
                    "defect_summary": doc.get("defect_summary"),
                    "similarity_score": doc.get("score"),  # Frontend expects "similarity_score"
                    "thumbnail_base64": thumbnail_base64 if thumbnail_base64 else None  # Frontend expects "thumbnail_base64"
                })
            
            logger.info(f"Defect similarity search returned {len(formatted_results)} results")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error finding similar defects: {e}")
            return []
    
    async def search_similar_alerts(
        self,
        alert_description: str,
        alert_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 10,
        min_score: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search for similar alerts using semantic similarity
        
        Args:
            alert_description: Alert description or context
            alert_type: Filter by alert type
            severity: Filter by severity
            limit: Maximum number of results
            min_score: Minimum similarity score
            
        Returns:
            List of similar alerts with scores
        """
        try:
            # Generate query embedding
            query_embedding = await self.embedding_service.generate_text_embedding(alert_description)
            
            # Build search pipeline
            pipeline = [
                {
                    "$search": {
                        "index": "alerts_vector_index",
                        "knnBeta": {
                            "vector": query_embedding,
                            "path": "embedding",
                            "k": limit * 2
                        }
                    }
                },
                {
                    "$addFields": {
                        "score": {"$meta": "searchScore"}
                    }
                },
                {
                    "$match": {
                        "score": {"$gte": min_score}
                    }
                }
            ]
            
            # Add filters
            filters = {}
            if alert_type:
                filters["alert_type"] = alert_type
            if severity:
                filters["severity"] = severity
            
            if filters:
                pipeline.insert(3, {"$match": filters})
            
            # Add limit
            pipeline.append({"$limit": limit})
            
            # Execute search
            collection = self.db["alerts"]
            results = await collection.aggregate(pipeline).to_list(length=None)
            
            # Format results
            formatted_results = []
            for doc in results:
                formatted_results.append({
                    "alert_id": str(doc["_id"]),
                    "alert_type": doc.get("alert_type"),
                    "severity": doc.get("severity"),
                    "description": doc.get("description"),
                    "affected_equipment": doc.get("affected_equipment"),
                    "status": doc.get("status"),
                    "created_at": doc.get("created_at"),
                    "score": doc.get("score"),
                    "excursion_details": doc.get("excursion_details")
                })
            
            logger.info(f"Alert similarity search returned {len(formatted_results)} results")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error searching similar alerts: {e}")
            return []
    
    async def hybrid_search(
        self,
        query: str,
        collections: List[str] = None,
        limit_per_collection: int = 5
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Perform hybrid search across multiple collections
        
        Args:
            query: Search query
            collections: Collections to search (default: all)
            limit_per_collection: Results per collection
            
        Returns:
            Dictionary with results from each collection
        """
        try:
            if not collections:
                collections = ["historical_knowledge", "wafer_defects", "alerts"]
            
            results = {}
            
            # Search each collection
            tasks = []
            
            if "historical_knowledge" in collections:
                tasks.append(self.search_knowledge_base(
                    query=query,
                    limit=limit_per_collection
                ))
            
            if "wafer_defects" in collections:
                tasks.append(self.find_similar_defects(
                    pattern=query,  # Use query as pattern description
                    limit=limit_per_collection
                ))
            
            if "alerts" in collections:
                tasks.append(self.search_similar_alerts(
                    alert_description=query,
                    limit=limit_per_collection
                ))
            
            # Execute searches in parallel
            search_results = await asyncio.gather(*tasks)
            
            # Map results to collections
            for i, collection in enumerate(collections):
                if i < len(search_results):
                    results[collection] = search_results[i]
            
            total_results = sum(len(r) for r in results.values())
            logger.info(f"Hybrid search for '{query[:50]}...' returned {total_results} total results")
            
            return results
            
        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            return {}
    
    async def get_context_for_rca(
        self,
        alert_id: str,
        max_documents: int = 5
    ) -> Dict[str, Any]:
        """
        Get relevant context for Root Cause Analysis
        
        Args:
            alert_id: Alert ID to analyze
            max_documents: Maximum documents per category
            
        Returns:
            Context with similar cases, guides, and defects
        """
        try:
            # Get the alert
            alert = await self.db["alerts"].find_one({"_id": alert_id})
            if not alert:
                logger.warning(f"Alert {alert_id} not found")
                return {}
            
            # Build context query
            context_query = f"{alert.get('alert_type', '')} {alert.get('description', '')}"
            if alert.get("excursion_details"):
                details = alert["excursion_details"]
                context_query += f" {details.get('metric', '')} exceeds {details.get('threshold', '')}"
            
            # Search for similar historical cases
            similar_cases = await self.search_knowledge_base(
                query=context_query,
                document_types=["rca_report"],
                limit=max_documents
            )
            
            # Search for relevant guides
            troubleshooting_guides = await self.search_knowledge_base(
                query=context_query,
                document_types=["troubleshooting_guide"],
                limit=max_documents
            )
            
            # Search for similar alerts
            similar_alerts = await self.search_similar_alerts(
                alert_description=context_query,
                severity=alert.get("severity"),
                limit=max_documents
            )
            
            # If equipment is specified, find similar defects
            similar_defects = []
            if alert.get("affected_equipment"):
                similar_defects = await self.find_similar_defects(
                    equipment=alert["affected_equipment"],
                    limit=max_documents
                )
            
            context = {
                "alert": {
                    "id": str(alert["_id"]),
                    "type": alert.get("alert_type"),
                    "description": alert.get("description"),
                    "severity": alert.get("severity"),
                    "equipment": alert.get("affected_equipment")
                },
                "similar_cases": similar_cases,
                "troubleshooting_guides": troubleshooting_guides,
                "similar_alerts": similar_alerts,
                "similar_defects": similar_defects,
                "context_query": context_query,
                "timestamp": datetime.now()
            }
            
            logger.info(f"Generated RCA context for alert {alert_id}")
            return context
            
        except Exception as e:
            logger.error(f"Error getting RCA context: {e}")
            return {}
    
    def cleanup(self):
        """Clean up resources"""
        self.embedding_service.cleanup()
        self.client.close()
        logger.info("Semantic Search Service cleaned up")


# Example usage
if __name__ == "__main__":
    async def test_semantic_search():
        service = SemanticSearchService()
        await service.initialize()
        
        # Test knowledge base search
        print("\n1. Testing knowledge base search...")
        knowledge_results = await service.search_knowledge_base(
            query="particle contamination in CMP process",
            document_types=["rca_report"],
            limit=5
        )
        print(f"Found {len(knowledge_results)} relevant documents")
        if knowledge_results:
            print(f"Top result: {knowledge_results[0]['title']} (score: {knowledge_results[0]['score']:.3f})")
        
        # Test defect similarity search
        print("\n2. Testing defect similarity search...")
        defect_results = await service.find_similar_defects(
            pattern="clustered",
            equipment="CMP_Tool_01",
            limit=5
        )
        print(f"Found {len(defect_results)} similar defects")
        if defect_results:
            print(f"Top match: {defect_results[0]['wafer_id']} (score: {defect_results[0]['score']:.3f})")
        
        # Test alert similarity search
        print("\n3. Testing alert similarity search...")
        alert_results = await service.search_similar_alerts(
            alert_description="High particle count detected in CMP process",
            severity="high",
            limit=5
        )
        print(f"Found {len(alert_results)} similar alerts")
        
        # Test hybrid search
        print("\n4. Testing hybrid search...")
        hybrid_results = await service.hybrid_search(
            query="temperature drift causing defects",
            limit_per_collection=3
        )
        for collection, results in hybrid_results.items():
            print(f"  {collection}: {len(results)} results")
        
        service.cleanup()
    
    asyncio.run(test_semantic_search())