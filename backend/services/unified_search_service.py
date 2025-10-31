"""
Unified Search Service
Provides semantic search capabilities across multiple collections:
- wafer_defects: Multimodal vector search (voyage-multimodal-3)
- process_context: Text-based search on manufacturing context
- historical_knowledge: Vector search on RCA reports and troubleshooting guides

Usage:
    service = UnifiedSearchService()
    results = await service.search_all("particle excursion due to padding wear")
"""

import os
import logging
import asyncio
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from enum import Enum
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from dotenv import load_dotenv

from services.embedding_service import EmbeddingService

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SearchMode(str, Enum):
    """Search mode options for unified search"""
    TEXT = "text"  # Atlas Search (full-text, BM25)
    VECTOR = "vector"  # Vector similarity search
    HYBRID = "hybrid"  # Combined text + vector using $rankFusion


class UnifiedSearchService:
    """
    Unified search service for querying across wafer_defects, process_context,
    and historical_knowledge collections using appropriate search methods.
    """

    def __init__(self, mongodb_uri: str = None, database_name: str = "smf-yield-defect"):
        """
        Initialize the unified search service

        Args:
            mongodb_uri: MongoDB connection string
            database_name: Database name
        """
        self.mongodb_uri = mongodb_uri or os.getenv("MONGODB_URI")
        self.client = AsyncIOMotorClient(self.mongodb_uri)
        self.db = self.client[database_name]

        # Initialize embedding service for vector searches
        self.embedding_service = EmbeddingService(
            mongodb_uri=self.mongodb_uri,
            database_name=database_name
        )

        # Vector index names
        self.wafer_vector_index = "wafer_defects_vector_index"
        self.knowledge_vector_index = "historical_knowledge_vector_index"

        # Text search index names (Atlas Search)
        self.wafer_text_index = "wafer_defects_text_index"
        self.knowledge_text_index = "historical_knowledge_text_index"

        logger.info(f"UnifiedSearchService initialized for database: {database_name}")

    async def initialize(self):
        """Initialize the service"""
        await self.embedding_service.initialize()
        logger.info("UnifiedSearchService ready")

    async def search_all(
        self,
        query: str,
        limit_per_collection: int = 5,
        search_mode: str = "vector",
        equipment_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search across all collections in parallel

        Args:
            query: Search query text (e.g., "particle excursion due to padding wear")
            limit_per_collection: Max results per collection
            search_mode: Search mode - "text", "vector", or "hybrid"
            equipment_id: Optional equipment filter for wafer results

        Returns:
            Dict containing:
                - wafer_results: List of wafer defects
                - knowledge_results: List of RCA reports/guides
                - summary: Overall statistics
                - query_metadata: Search execution details
        """
        logger.info("=" * 80)
        logger.info("🔍 UNIFIED SEARCH - search_all()")
        logger.info("=" * 80)
        logger.info(f"📝 Query: '{query}'")
        logger.info(f"🔧 Search Mode: {search_mode}")
        logger.info(f"📊 Limit per collection: {limit_per_collection}")
        logger.info(f"🏭 Equipment Filter: {equipment_id or 'None'}")

        start_time = time.time()

        try:
            # Execute all searches in parallel using asyncio.gather()
            wafer_task = self.search_wafers(query, equipment_id=equipment_id, limit=limit_per_collection, search_mode=search_mode)
            knowledge_task = self.search_historical_knowledge(query, document_types=None, limit=limit_per_collection, search_mode=search_mode)

            wafer_results, knowledge_results = await asyncio.gather(
                wafer_task, knowledge_task, return_exceptions=True
            )

            # Handle exceptions from individual searches
            if isinstance(wafer_results, Exception):
                logger.error(f"❌ Wafer search failed: {wafer_results}")
                wafer_results = {"results": [], "summary": {"total_found": 0}}
            if isinstance(knowledge_results, Exception):
                logger.error(f"❌ Knowledge search failed: {knowledge_results}")
                knowledge_results = {"results": [], "summary": {"total_found": 0}}

            elapsed_ms = (time.time() - start_time) * 1000

            # Calculate summary statistics
            total_results = (
                len(wafer_results.get("results", [])) +
                len(knowledge_results.get("results", []))
            )

            summary = {
                "total_results": total_results,
                "wafer_count": len(wafer_results.get("results", [])),
                "knowledge_count": len(knowledge_results.get("results", [])),
                "execution_time_ms": round(elapsed_ms, 2),
                "search_mode": search_mode
            }

            logger.info("=" * 80)
            logger.info("✅ UNIFIED SEARCH - SUCCESS")
            logger.info(f"📊 Total results: {total_results} ({summary['wafer_count']} wafers, "
                       f"{summary['knowledge_count']} knowledge)")
            logger.info(f"⏱️  Execution time: {elapsed_ms:.0f}ms")
            logger.info("=" * 80)

            return {
                "wafer_results": wafer_results.get("results", []),
                "knowledge_results": knowledge_results.get("results", []),
                "summary": summary,
                "query_metadata": {
                    "query": query,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "execution_time_ms": round(elapsed_ms, 2)
                }
            }

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"❌ Unified search error: {e}", exc_info=True)

            return {
                "wafer_results": [],
                "knowledge_results": [],
                "summary": {
                    "total_results": 0,
                    "wafer_count": 0,
                    "knowledge_count": 0,
                    "execution_time_ms": round(elapsed_ms, 2),
                    "search_mode": search_mode,
                    "error": str(e)
                },
                "query_metadata": {
                    "query": query,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "execution_time_ms": round(elapsed_ms, 2),
                    "error": str(e)
                }
            }

    async def search_wafers(
        self,
        query: str,
        equipment_id: Optional[str] = None,
        limit: int = 10,
        search_mode: str = "vector"
    ) -> Dict[str, Any]:
        """
        Search wafer defects using text, vector, or hybrid search

        Args:
            query: Search query (e.g., "clustered defects", "edge pattern")
            equipment_id: Optional equipment filter (e.g., "CMP_TOOL_01")
            limit: Maximum number of results
            search_mode: Search mode - "text", "vector", or "hybrid"

        Returns:
            Dict containing:
                - results: List of wafer defects with scores
                - summary: Search statistics
                - search_metadata: Query execution details
        """
        logger.info(f"🔍 search_wafers() - {search_mode.upper()} SEARCH")
        logger.info(f"   Query: '{query}', Equipment: {equipment_id}, Limit: {limit}")

        start_time = time.time()

        try:
            # Route to appropriate search pipeline based on search_mode
            if search_mode == SearchMode.TEXT:
                pipeline = await self._build_text_search_pipeline_wafers(query, equipment_id, limit)
                search_method = "atlas_text_search"
            elif search_mode == SearchMode.HYBRID:
                pipeline = await self._build_hybrid_search_pipeline_wafers(query, equipment_id, limit)
                search_method = "hybrid_search_rankfusion"
            else:  # Default to vector
                pipeline = await self._build_vector_search_pipeline_wafers(query, equipment_id, limit)
                search_method = "vector_search"

            # Execute search
            cursor = self.db.wafer_defects.aggregate(pipeline)
            results = await cursor.to_list(length=limit * 2)  # Get more results for safety

            elapsed_ms = (time.time() - start_time) * 1000

            # Format results
            formatted_results = []
            for doc in results:
                # Convert ObjectId to string
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])

                defect_summary = doc.get("defect_summary", {})
                formatted = {
                    "collection_source": "wafer_defects",
                    "wafer_id": doc.get("wafer_id"),
                    "lot_id": doc.get("lot_id"),
                    "defect_pattern": defect_summary.get("defect_pattern"),
                    "yield_percentage": defect_summary.get("yield_percentage"),
                    "failed_dies": defect_summary.get("failed_dies"),
                    "severity": defect_summary.get("severity"),
                    "equipment_id": doc.get("equipment_id"),
                    "inspection_timestamp": doc.get("inspection_timestamp"),
                    "score": round(doc.get("score", 0), 4),
                    # Full visualization data for frontend
                    "ink_map": doc.get("ink_map"),  # 25x25 grid + thumbnails
                    "defects": doc.get("defects", []),  # Defect coordinates array
                    "defect_summary": defect_summary,  # Full summary object
                    "description": doc.get("description"),  # Defect description
                    "process_context": doc.get("process_context", {})  # Equipment/recipe context
                }
                formatted_results.append(formatted)

            # Calculate summary
            avg_yield = sum([r["yield_percentage"] for r in formatted_results if r.get("yield_percentage")]) / len(formatted_results) if formatted_results else 0
            patterns = [r["defect_pattern"] for r in formatted_results if r.get("defect_pattern")]
            unique_patterns = list(set(patterns))

            summary = {
                "total_found": len(formatted_results),
                "avg_yield": round(avg_yield, 2),
                "defect_patterns": unique_patterns,
                "execution_time_ms": round(elapsed_ms, 2)
            }

            logger.info(f"   ✅ Found {len(formatted_results)} wafers, avg yield: {avg_yield:.2f}%")

            return {
                "results": formatted_results,
                "summary": summary,
                "search_metadata": {
                    "query": query,
                    "equipment_id": equipment_id,
                    "search_mode": search_mode,
                    "search_method": search_method,
                    "embedding_model": "voyage-multimodal-3" if search_mode != SearchMode.TEXT else None,
                    "execution_time_ms": round(elapsed_ms, 2)
                }
            }

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"   ❌ Wafer search error: {e}", exc_info=True)

            return {
                "results": [],
                "summary": {
                    "total_found": 0,
                    "avg_yield": 0,
                    "defect_patterns": [],
                    "execution_time_ms": round(elapsed_ms, 2),
                    "error": str(e)
                },
                "search_metadata": {
                    "query": query,
                    "equipment_id": equipment_id,
                    "search_mode": search_mode,
                    "search_method": f"{search_mode}_search",
                    "execution_time_ms": round(elapsed_ms, 2),
                    "error": str(e)
                }
            }

    async def _build_text_search_pipeline_wafers(
        self,
        query: str,
        equipment_id: Optional[str],
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Build Atlas Text Search pipeline for wafer defects

        Uses compound query with filter clause for equipment filtering at database level.
        """
        # Build compound query
        compound_query = {
            "must": [{
                "text": {
                    "query": query,
                    "path": ["description", "defect_summary.defect_pattern"],
                    "fuzzy": {
                        "maxEdits": 1
                    }
                }
            }]
        }

        # Add equipment filter at database level using filter clause
        if equipment_id:
            compound_query["filter"] = [{
                "text": {
                    "query": equipment_id,
                    "path": "equipment_id"
                }
            }]
            logger.info(f"   🔧 Equipment filter applied in query: {equipment_id}")

        pipeline = [
            {
                "$search": {
                    "index": self.wafer_text_index,
                    "compound": compound_query
                }
            },
            {
                "$addFields": {
                    "score": {"$meta": "searchScore"}
                }
            },
            {
                "$limit": limit
            }
        ]

        return pipeline

    async def _build_vector_search_pipeline_wafers(
        self,
        query: str,
        equipment_id: Optional[str],
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Build Vector Search pipeline for wafer defects

        Uses compound query with filter clause for equipment filtering at database level.
        """
        # Generate query embedding
        query_embedding = await self.embedding_service.generate_text_embedding(query)
        logger.info(f"   🧬 Query embedding generated ({len(query_embedding)} dimensions)")

        # Build compound query with filter
        search_query = {
            "index": self.wafer_vector_index,
            "knnBeta": {
                "vector": query_embedding,
                "path": "embedding",
                "k": limit
            }
        }

        # Add equipment filter using compound query
        if equipment_id:
            pipeline = [
                {
                    "$search": {
                        "index": self.wafer_vector_index,
                        "compound": {
                            "must": [{
                                "knnBeta": {
                                    "vector": query_embedding,
                                    "path": "embedding",
                                    "k": limit * 3  # Get more candidates for filtering
                                }
                            }],
                            "filter": [{
                                "text": {
                                    "query": equipment_id,
                                    "path": "equipment_id"
                                }
                            }]
                        }
                    }
                },
                {
                    "$addFields": {
                        "score": {"$meta": "searchScore"}
                    }
                },
                {
                    "$limit": limit
                }
            ]
            logger.info(f"   🔧 Equipment filter applied in query: {equipment_id}")
        else:
            pipeline = [
                {
                    "$search": search_query
                },
                {
                    "$addFields": {
                        "score": {"$meta": "searchScore"}
                    }
                },
                {
                    "$limit": limit
                }
            ]

        return pipeline

    async def _build_hybrid_search_pipeline_wafers(
        self,
        query: str,
        equipment_id: Optional[str],
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Build Hybrid Search pipeline using $rankFusion (MongoDB 8.1+)

        Combines text and vector search results for best of both worlds.
        Equipment filter is applied AFTER $rankFusion using $match for reliability.
        """
        # Generate query embedding for vector search
        query_embedding = await self.embedding_service.generate_text_embedding(query)
        logger.info(f"   🧬 Query embedding generated ({len(query_embedding)} dimensions)")

        # Build text search sub-pipeline (no filter - get more candidates)
        text_search = {
            "index": self.wafer_text_index,
            "text": {
                "query": query,
                "path": ["description", "defect_summary.defect_pattern"],
                "fuzzy": {
                    "maxEdits": 1
                }
            }
        }

        # Build vector search sub-pipeline (no filter - get more candidates)
        vector_search = {
            "index": self.wafer_vector_index,
            "knnBeta": {
                "vector": query_embedding,
                "path": "embedding",
                "k": limit * 10  # Get many more candidates before filtering
            }
        }

        # Use $rankFusion to combine results, then filter
        pipeline = [
            {
                "$rankFusion": {
                    "input": {
                        "pipelines": {
                            "textSearch": [
                                {"$search": text_search},
                                {"$limit": limit * 10}  # More candidates
                            ],
                            "vectorSearch": [
                                {"$search": vector_search},
                                {"$limit": limit * 10}  # More candidates
                            ]
                        }
                    }
                }
            },
            {
                "$project": {
                    "score": {"$meta": "searchScore"},
                    "wafer_id": 1,
                    "lot_id": 1,
                    "equipment_id": 1,
                    "description": 1,
                    "defect_summary": 1,
                    "defects": 1,
                    "ink_map": 1,
                    "inspection_timestamp": 1,
                    "process_context": 1
                }
            }
        ]

        # Apply equipment filter AFTER $rankFusion using $match
        if equipment_id:
            pipeline.append({
                "$match": {
                    "equipment_id": equipment_id
                }
            })
            logger.info(f"   🔧 Equipment filter applied after RRF: {equipment_id}")

        # Final limit after filtering
        pipeline.append({"$limit": limit})

        logger.info(f"   🔀 Hybrid search: combining text + vector results with RRF scoring")

        return pipeline

    # async def search_process_context(
    #     self,
    #     query: str,
    #     context_types: Optional[List[str]] = None,
    #     limit: int = 10
    # ) -> Dict[str, Any]:
    #     """
    #     Search process context using text-based search

    #     Args:
    #         query: Search query (e.g., "slurry batch", "padding wear")
    #         context_types: Filter by types ["slurry_batch", "etch_recipe", "reticle"]
    #         limit: Maximum number of results

    #     Returns:
    #         Dict containing:
    #             - results: List of process context items with scores
    #             - summary: Search statistics
    #             - search_metadata: Query execution details
    #     """
    #     logger.info("🔍 search_process_context() - TEXT SEARCH")
    #     logger.info(f"   Query: '{query}', Types: {context_types}, Limit: {limit}")

    #     start_time = time.time()

    #     try:
    #         # Build MongoDB query using $regex for text matching
    #         # Search across multiple text fields
    #         query_filter = {
    #             "$or": [
    #                 {"context_id": {"$regex": query, "$options": "i"}},
    #                 {"slurry_details.manufacturer": {"$regex": query, "$options": "i"}},
    #                 {"slurry_details.composition": {"$regex": query, "$options": "i"}},
    #                 {"recipe_details.recipe_name": {"$regex": query, "$options": "i"}},
    #                 {"reticle_details.reticle_id": {"$regex": query, "$options": "i"}},
    #                 {"known_issues": {"$regex": query, "$options": "i"}}
    #             ]
    #         }

    #         # Add context type filter if specified
    #         if context_types:
    #             query_filter["context_type"] = {"$in": context_types}

    #         # Execute query
    #         cursor = self.db.process_context.find(query_filter).limit(limit)
    #         results = await cursor.to_list(length=limit)

    #         elapsed_ms = (time.time() - start_time) * 1000

    #         # Format results
    #         formatted_results = []
    #         for doc in results:
    #             # Convert ObjectId to string
    #             if "_id" in doc:
    #                 doc["_id"] = str(doc["_id"])

    #             context_type = doc.get("context_type")
    #             formatted = {
    #                 "collection_source": "process_context",
    #                 "context_type": context_type,
    #                 "context_id": doc.get("context_id"),
    #                 "is_problematic": doc.get("is_problematic", False),
    #                 "known_issues": doc.get("known_issues", []),
    #                 "score": 0.8,  # Fixed relevance score for text matches
    #                 # Full nested objects for frontend visualization
    #                 "slurry_details": doc.get("slurry_details", {}),
    #                 "recipe_details": doc.get("recipe_details", {}),
    #                 "reticle_details": doc.get("reticle_details", {})
    #             }

    #             # Add type-specific quick access fields (for backward compatibility)
    #             if context_type == "slurry_batch":
    #                 slurry = doc.get("slurry_details", {})
    #                 formatted.update({
    #                     "manufacturer": slurry.get("manufacturer"),
    #                     "composition": slurry.get("composition"),
    #                     "qc_status": slurry.get("qc_status"),
    #                     "large_particle_count": slurry.get("large_particle_count")
    #                 })
    #             elif context_type == "etch_recipe":
    #                 recipe = doc.get("recipe_details", {})
    #                 formatted.update({
    #                     "recipe_name": recipe.get("recipe_name"),
    #                     "process_type": recipe.get("process_type")
    #                 })
    #             elif context_type == "reticle":
    #                 reticle = doc.get("reticle_details", {})
    #                 inspection = reticle.get("inspection_data", {})
    #                 formatted.update({
    #                     "reticle_id": reticle.get("reticle_id"),
    #                     "layer": reticle.get("layer"),
    #                     "defect_count": inspection.get("defect_count", 0)
    #                 })

    #             formatted_results.append(formatted)

    #         # Calculate summary
    #         problematic_count = sum([1 for r in formatted_results if r.get("is_problematic")])
    #         types_found = list(set([r["context_type"] for r in formatted_results]))

    #         summary = {
    #             "total_found": len(formatted_results),
    #             "problematic_items": problematic_count,
    #             "context_types": types_found,
    #             "execution_time_ms": round(elapsed_ms, 2)
    #         }

    #         logger.info(f"   ✅ Found {len(formatted_results)} process context items "
    #                    f"({problematic_count} problematic)")

    #         return {
    #             "results": formatted_results,
    #             "summary": summary,
    #             "search_metadata": {
    #                 "query": query,
    #                 "context_types": context_types,
    #                 "search_method": "text_regex_search",
    #                 "execution_time_ms": round(elapsed_ms, 2)
    #             }
    #         }

    #     except Exception as e:
    #         elapsed_ms = (time.time() - start_time) * 1000
    #         logger.error(f"   ❌ Process context search error: {e}", exc_info=True)

    #         return {
    #             "results": [],
    #             "summary": {
    #                 "total_found": 0,
    #                 "problematic_items": 0,
    #                 "context_types": [],
    #                 "execution_time_ms": round(elapsed_ms, 2),
    #                 "error": str(e)
    #             },
    #             "search_metadata": {
    #                 "query": query,
    #                 "context_types": context_types,
    #                 "search_method": "text_regex_search",
    #                 "execution_time_ms": round(elapsed_ms, 2),
    #                 "error": str(e)
    #             }
    #         }

    async def search_historical_knowledge(
        self,
        query: str,
        document_types: Optional[List[str]] = None,
        limit: int = 10,
        search_mode: str = "vector"
    ) -> Dict[str, Any]:
        """
        Search historical knowledge using text, vector, or hybrid search

        Args:
            query: Search query (e.g., "particle contamination root cause")
            document_types: Filter by types ["rca_report", "troubleshooting_guide"]
            limit: Maximum number of results
            search_mode: Search mode - "text", "vector", or "hybrid"

        Returns:
            Dict containing:
                - results: List of RCA reports/guides with scores + full content
                - summary: Search statistics
                - search_metadata: Query execution details
        """
        logger.info(f"🔍 search_historical_knowledge() - {search_mode.upper()} SEARCH")
        logger.info(f"   Query: '{query}', Types: {document_types}, Limit: {limit}")

        start_time = time.time()

        try:
            # Route to appropriate search pipeline based on search_mode
            if search_mode == SearchMode.TEXT:
                pipeline = await self._build_text_search_pipeline_knowledge(query, document_types, limit)
                search_method = "atlas_text_search"
            elif search_mode == SearchMode.HYBRID:
                pipeline = await self._build_hybrid_search_pipeline_knowledge(query, document_types, limit)
                search_method = "hybrid_search_rankfusion"
            else:  # Default to vector
                pipeline = await self._build_vector_search_pipeline_knowledge(query, document_types, limit)
                search_method = "vector_search"

            # Execute search
            cursor = self.db.historical_knowledge.aggregate(pipeline)
            results = await cursor.to_list(length=limit * 2)  # Get more results for safety

            elapsed_ms = (time.time() - start_time) * 1000

            # Format results
            formatted_results = []
            for doc in results:
                # Convert ObjectId to string
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])

                metadata = doc.get("metadata", {})
                findings = doc.get("findings", {})
                doc_type = doc.get("document_type")

                formatted = {
                    "collection_source": "historical_knowledge",
                    "document_id": doc.get("_id"),
                    "document_type": doc_type,
                    "title": doc.get("title"),
                    "process_area": metadata.get("process_area"),
                    "defect_type": metadata.get("defect_type"),
                    "score": round(doc.get("score", 0), 4),
                    
                    # Full document content for frontend visualization
                    "content": doc.get("content"),  # Full RCA/guide text
                    "findings": findings,  # Complete findings object
                    "metadata": metadata,  # Full metadata
                    "solutions": doc.get("solutions", [])  # Full solutions array
                }

                # Add type-specific fields (backward compatibility)
                if doc_type == "rca_report":
                    formatted.update({
                        "root_cause": findings.get("root_cause"),
                        "corrective_actions": findings.get("corrective_actions", []),
                        "resolution_time_hours": metadata.get("resolution_time_hours")
                    })
                elif doc_type == "troubleshooting_guide":
                    formatted.update({
                        "problem_type": metadata.get("problem_type"),
                        "estimated_resolution_time": metadata.get("estimated_resolution_time")
                    })

                formatted_results.append(formatted)

            # Calculate summary
            doc_types = {}
            for r in formatted_results:
                dt = r["document_type"]
                doc_types[dt] = doc_types.get(dt, 0) + 1

            avg_score = sum([r["score"] for r in formatted_results]) / len(formatted_results) if formatted_results else 0

            summary = {
                "total_found": len(formatted_results),
                "document_types": doc_types,
                "avg_similarity_score": round(avg_score, 4),
                "execution_time_ms": round(elapsed_ms, 2)
            }

            logger.info(f"   ✅ Found {len(formatted_results)} knowledge documents, "
                       f"avg score: {avg_score:.4f}")

            return {
                "results": formatted_results,
                "summary": summary,
                "search_metadata": {
                    "query": query,
                    "document_types": document_types,
                    "search_mode": search_mode,
                    "search_method": search_method,
                    "embedding_model": "voyage-multimodal-3" if search_mode != SearchMode.TEXT else None,
                    "execution_time_ms": round(elapsed_ms, 2)
                }
            }

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"   ❌ Historical knowledge search error: {e}", exc_info=True)

            return {
                "results": [],
                "summary": {
                    "total_found": 0,
                    "document_types": {},
                    "avg_similarity_score": 0,
                    "execution_time_ms": round(elapsed_ms, 2),
                    "error": str(e)
                },
                "search_metadata": {
                    "query": query,
                    "document_types": document_types,
                    "search_mode": search_mode,
                    "search_method": f"{search_mode}_search",
                    "execution_time_ms": round(elapsed_ms, 2),
                    "error": str(e)
                }
            }

    async def _build_text_search_pipeline_knowledge(
        self,
        query: str,
        document_types: Optional[List[str]],
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Build Atlas Text Search pipeline for historical knowledge

        Uses compound query with filter clause for document type filtering.
        """
        # Build compound query
        compound_query = {
            "must": [{
                "text": {
                    "query": query,
                    "path": ["title", "content"],
                    "fuzzy": {
                        "maxEdits": 1
                    }
                }
            }]
        }

        # Add document type filter at database level
        if document_types:
            compound_query["filter"] = [{
                "text": {
                    "query": document_types,
                    "path": "document_type"
                }
            }]
            logger.info(f"   📄 Document type filter applied: {document_types}")

        pipeline = [
            {
                "$search": {
                    "index": self.knowledge_text_index,
                    "compound": compound_query
                }
            },
            {
                "$addFields": {
                    "score": {"$meta": "searchScore"}
                }
            },
            {
                "$limit": limit
            }
        ]

        return pipeline

    async def _build_vector_search_pipeline_knowledge(
        self,
        query: str,
        document_types: Optional[List[str]],
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Build Vector Search pipeline for historical knowledge

        Uses $match stage for document type filtering (post-search).
        """
        # Generate query embedding
        query_embedding = await self.embedding_service.generate_text_embedding(query)
        logger.info(f"   🧬 Query embedding generated ({len(query_embedding)} dimensions)")

        pipeline = [
            {
                "$search": {
                    "index": self.knowledge_vector_index,
                    "knnBeta": {
                        "vector": query_embedding,
                        "path": "embedding",
                        "k": limit * 2 if document_types else limit
                    }
                }
            },
            {
                "$addFields": {
                    "score": {"$meta": "searchScore"}
                }
            }
        ]

        # Add document type filter using $match (post-search)
        if document_types:
            pipeline.append({
                "$match": {
                    "document_type": {"$in": document_types}
                }
            })
            logger.info(f"   📄 Document type filter applied: {document_types}")

        pipeline.append({"$limit": limit})

        return pipeline

    async def _build_hybrid_search_pipeline_knowledge(
        self,
        query: str,
        document_types: Optional[List[str]],
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Build Hybrid Search pipeline using $rankFusion (MongoDB 8.1+)

        Combines text and vector search for historical knowledge.
        Document type filter is applied AFTER $rankFusion using $match for reliability.
        """
        # Generate query embedding for vector search
        query_embedding = await self.embedding_service.generate_text_embedding(query)
        logger.info(f"   🧬 Query embedding generated ({len(query_embedding)} dimensions)")

        # Build text search sub-pipeline (no filter - get more candidates)
        text_search = {
            "index": self.knowledge_text_index,
            "text": {
                "query": query,
                "path": ["title", "content"],
                "fuzzy": {
                    "maxEdits": 1
                }
            }
        }

        # Build vector search sub-pipeline (no filter - get more candidates)
        vector_search = {
            "index": self.knowledge_vector_index,
            "knnBeta": {
                "vector": query_embedding,
                "path": "embedding",
                "k": limit * 10  # Get many more candidates before filtering
            }
        }

        # Use $rankFusion to combine results, then filter
        pipeline = [
            {
                "$rankFusion": {
                    "input": {
                        "pipelines": {
                            "textSearch": [
                                {"$search": text_search},
                                {"$limit": limit * 10}  # More candidates
                            ],
                            "vectorSearch": [
                                {"$search": vector_search},
                                {"$limit": limit * 10}  # More candidates
                            ]
                        }
                    }
                }
            },
            {
                "$project": {
                    "score": {"$meta": "searchScore"},
                    "title": 1,
                    "content": 1,
                    "document_type": 1,
                    "metadata": 1,
                    "findings": 1,
                    "solutions": 1
                }
            }
        ]

        # Apply document type filter AFTER $rankFusion using $match
        if document_types:
            pipeline.append({
                "$match": {
                    "document_type": {"$in": document_types}
                }
            })
            logger.info(f"   📄 Document type filter applied after RRF: {document_types}")

        # Final limit after filtering
        pipeline.append({"$limit": limit})

        logger.info(f"   🔀 Hybrid search: combining text + vector results with RRF scoring")

        return pipeline

    def cleanup(self):
        """Clean up resources"""
        self.client.close()
        self.embedding_service.cleanup()
        logger.info("UnifiedSearchService cleaned up")

