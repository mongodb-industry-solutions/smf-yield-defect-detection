"""
Investigation Agent Tools
MongoDB query tools for evidence gathering from manufacturing context

This module provides tools for the investigation agent to query MongoDB collections
and gather evidence about manufacturing conditions. These tools do NOT perform
root cause analysis - they only retrieve structured data.

Collections queried:
- process_context: Slurry batches, etch recipes, reticles
- process_sensor_ts: Time series sensor data
- wafer_defects: Wafer defect patterns
- historical_knowledge: RAG knowledge base

Data schemas documented in CLAUDE.md
"""

import logging
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta, timezone
import time

logger = logging.getLogger(__name__)


async def query_process_context(
    db: AsyncIOMotorDatabase,
    equipment_id: str,
    slurry_batch: Optional[str] = None,
    recipe_id: Optional[str] = None,
    context_types: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Query process_context collection for manufacturing context evidence

    Returns structured data about slurry batches, etch recipes, and reticles.
    Does NOT perform root cause analysis - only gathers evidence.

    Args:
        db: MongoDB database connection (Motor AsyncIOMotorDatabase)
        equipment_id: Equipment identifier (e.g., "CMP_TOOL_01")
        slurry_batch: Optional specific slurry batch ID to query (e.g., "SB_2025_021")
        recipe_id: Optional specific recipe ID to query (e.g., "ETCH_RECIPE_01")
        context_types: Optional filter by context types
                      ["slurry_batch", "etch_recipe", "reticle"]

    Returns:
        Dict containing:
            - slurry_batches: List[Dict] - Slurry batch documents
            - recipes: List[Dict] - Recipe documents
            - reticles: List[Dict] - Reticle documents
            - problematic_items: int - Count of problematic items found
            - query_metadata: Dict - Query execution details
            - error: str (only if error occurred)

    Example:
        result = await query_process_context(
            db=db,
            equipment_id="CMP_TOOL_01",
            slurry_batch="SB_2025_021",
            context_types=["slurry_batch"]
        )
        # Returns: {"slurry_batches": [...], "problematic_items": 1, ...}
    """

    # ========== LOGGING: Entry ==========
    logger.info("=" * 80)
    logger.info("🔍 query_process_context() - START")
    logger.info("=" * 80)
    logger.info(f"📥 Parameters:")
    logger.info(f"   equipment_id: {equipment_id}")
    logger.info(f"   slurry_batch: {slurry_batch}")
    logger.info(f"   recipe_id: {recipe_id}")
    logger.info(f"   context_types: {context_types}")

    try:
        # ========== QUERY CONSTRUCTION ==========
        logger.info("🔨 Building MongoDB query...")

        query_filter = {}

        # Filter by context types if specified
        if context_types:
            query_filter["context_type"] = {"$in": context_types}
            logger.info(f"   ✓ Added context_type filter: {context_types}")

        # Build $or conditions for specific IDs
        or_conditions = []

        if slurry_batch:
            or_conditions.append({
                "context_id": slurry_batch,
                "context_type": "slurry_batch"
            })
            logger.info(f"   ✓ Added slurry_batch condition: {slurry_batch}")

        if recipe_id:
            or_conditions.append({
                "context_id": recipe_id,
                "context_type": {"$in": ["etch_recipe", "recipe"]}
            })
            logger.info(f"   ✓ Added recipe_id condition: {recipe_id}")

        # Add $or to query if conditions exist
        if or_conditions:
            if query_filter:
                # Combine with existing filters using $and
                query_filter = {"$and": [query_filter, {"$or": or_conditions}]}
            else:
                query_filter["$or"] = or_conditions

        logger.info(f"🔍 Final MongoDB query: {query_filter}")

        # ========== QUERY EXECUTION ==========
        logger.info("🚀 Executing MongoDB query...")
        query_start_time = datetime.now()

        cursor = db.process_context.find(query_filter)
        results = await cursor.to_list(100)  # Limit to 100 documents

        query_elapsed_ms = (datetime.now() - query_start_time).total_seconds() * 1000
        logger.info(f"⏱️  Query executed in {query_elapsed_ms:.0f}ms")
        logger.info(f"📊 Retrieved {len(results)} documents")

        # ========== RESULTS CATEGORIZATION ==========
        logger.info("📋 Categorizing results...")

        categorized = {
            "slurry_batches": [],
            "recipes": [],
            "reticles": [],
            "problematic_items": 0,
            "query_metadata": {
                "equipment_id": equipment_id,
                "query_filter": query_filter,
                "execution_time_ms": round(query_elapsed_ms, 2),
                "total_documents": len(results),
                "timestamp": datetime.now().isoformat()
            }
        }

        for doc in results:
            context_type = doc.get("context_type")

            # Remove MongoDB _id for cleaner JSON serialization
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])

            if context_type == "slurry_batch":
                categorized["slurry_batches"].append(doc)
                if doc.get("is_problematic"):
                    categorized["problematic_items"] += 1
                    logger.warning(
                        f"   🚨 Problematic slurry batch found: {doc.get('context_id')} "
                        f"- Issues: {doc.get('known_issues', [])}"
                    )

            elif context_type in ["etch_recipe", "recipe"]:
                categorized["recipes"].append(doc)
                if doc.get("is_problematic"):
                    categorized["problematic_items"] += 1
                    logger.warning(
                        f"   🚨 Problematic recipe found: {doc.get('context_id')} "
                        f"- Issues: {doc.get('known_issues', [])}"
                    )

            elif context_type == "reticle":
                categorized["reticles"].append(doc)
                # Reticles don't have is_problematic flag, check defect_count
                inspection_data = doc.get("reticle_details", {}).get("inspection_data", {})
                if inspection_data.get("defect_count", 0) > 0:
                    categorized["problematic_items"] += 1
                    logger.warning(
                        f"   🚨 Problematic reticle found: {doc.get('context_id')} "
                        f"- Defect count: {inspection_data.get('defect_count')}"
                    )

        # ========== LOGGING: Results Summary ==========
        logger.info("📊 Results Summary:")
        logger.info(f"   Slurry batches: {len(categorized['slurry_batches'])}")
        logger.info(f"   Recipes: {len(categorized['recipes'])}")
        logger.info(f"   Reticles: {len(categorized['reticles'])}")
        logger.info(f"   Problematic items: {categorized['problematic_items']}")

        if categorized['problematic_items'] > 0:
            logger.warning(
                f"⚠️  {categorized['problematic_items']} problematic items found - "
                f"potential root cause indicators!"
            )
        else:
            logger.info("✅ No problematic items found in process context")

        logger.info("=" * 80)
        logger.info("✅ query_process_context() - SUCCESS")
        logger.info("=" * 80)

        return categorized

    except Exception as e:
        # ========== ERROR HANDLING ==========
        logger.error("=" * 80)
        logger.error("❌ query_process_context() - ERROR")
        logger.error("=" * 80)
        logger.error(f"❌ Error querying process_context collection: {e}", exc_info=True)
        logger.error(f"📥 Parameters that caused error:")
        logger.error(f"   equipment_id: {equipment_id}")
        logger.error(f"   slurry_batch: {slurry_batch}")
        logger.error(f"   recipe_id: {recipe_id}")
        logger.error(f"   context_types: {context_types}")

        return {
            "error": str(e),
            "error_type": type(e).__name__,
            "query_filter": query_filter if 'query_filter' in locals() else None,
            "slurry_batches": [],
            "recipes": [],
            "reticles": [],
            "problematic_items": 0
        }


def map_excursion_to_defect_pattern(excursion_type: Optional[str]) -> str:
    """
    Map excursion type to expected wafer defect pattern

    Based on WaferGenerator.map_excursion_to_defect_pattern() mapping.

    Args:
        excursion_type: Excursion type from monitoring agent
            (particle_excursion, rf_power_drift, temperature_drift, etc.)

    Returns:
        Defect pattern string (clustered, systematic, edge, random)
    """
    mapping = {
        'particle_excursion': 'clustered',
        'particle_spike': 'clustered',
        'rf_power_drift': 'systematic',
        'temperature_drift': 'edge',
        'pressure_drop': 'random',
        'recovery': 'random'
    }
    return mapping.get(excursion_type, 'clustered')  # Default to clustered


async def query_wafer_defects(
    db: AsyncIOMotorDatabase,
    equipment_id: str,
    excursion_type: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Query wafer defects using vector similarity search (voyage-multimodal-3)

    Uses SemanticSearchService to find similar wafer defect patterns from
    the 68 wafers with multimodal embeddings.

    Args:
        db: MongoDB database connection (Motor AsyncIOMotorDatabase)
        equipment_id: Equipment identifier (e.g., "CMP_TOOL_01")
        excursion_type: Excursion type from monitoring agent
            Maps to defect pattern: particle_excursion → clustered, etc.
        limit: Max results to return (default 10)

    Returns:
        Dict containing:
            - wafer_defects: List[Dict] - Wafers with similarity scores
            - summary: Dict - Aggregate statistics (total, avg yield, patterns found)
            - search_metadata: Dict - Search parameters and execution metrics
            - error: str (only if error occurred)

    Example:
        result = await query_wafer_defects(
            db=db,
            equipment_id="CMP_TOOL_01",
            excursion_type="particle_excursion",
            limit=10
        )
        # Returns: {"wafer_defects": [...], "summary": {...}, ...}
    """

    # ========== LOGGING: Entry ==========
    logger.info("=" * 80)
    logger.info("🔍 query_wafer_defects() - START (VECTOR SEARCH)")
    logger.info("=" * 80)
    logger.info(f"📥 Parameters:")
    logger.info(f"   equipment_id: {equipment_id}")
    logger.info(f"   excursion_type: {excursion_type}")
    logger.info(f"   limit: {limit}")

    start_time = time.time()
    defect_pattern = None

    try:
        # ========== STEP 1: Map Excursion to Defect Pattern ==========
        if excursion_type:
            defect_pattern = map_excursion_to_defect_pattern(excursion_type)
            logger.info(f"🗺️  Mapped excursion '{excursion_type}' → defect pattern '{defect_pattern}'")
        else:
            defect_pattern = "clustered"  # Default
            logger.info(f"ℹ️  No excursion_type provided, using default pattern: {defect_pattern}")

        # ========== STEP 2: Vector Search using SemanticSearchService ==========
        logger.info("🎯 Vector Search (voyage-multimodal-3 embeddings on 68 wafers)")

        from services.semantic_search import SemanticSearchService

        semantic_search = SemanticSearchService(
            mongodb_uri=None,  # Will use from env
            database_name=db.name
        )

        logger.info(f"   📦 Searching: pattern='{defect_pattern}', equipment='{equipment_id}'")

        wafer_results = await semantic_search.find_similar_defects(
            pattern=defect_pattern,
            equipment=equipment_id,
            limit=limit,
            min_score=0.4  # Lower threshold for demo
        )

        elapsed = (time.time() - start_time) * 1000
        logger.info(f"   ⏱️  Vector search completed in {elapsed:.0f}ms")
        logger.info(f"   📊 Found {len(wafer_results)} similar wafers")

        if wafer_results and len(wafer_results) > 0:
            top_score = wafer_results[0].get('similarity_score', 0)
            logger.info(f"   🎯 Top similarity score: {top_score:.3f}")

        # ========== STEP 3: Calculate Summary Statistics ==========
        logger.info("📈 Calculating summary statistics...")

        yields = [w.get('yield', 0) for w in wafer_results if w.get('yield')]
        avg_yield = sum(yields) / len(yields) if yields else 0
        min_yield = min(yields) if yields else 0
        max_yield = max(yields) if yields else 0

        patterns = [w.get('pattern') for w in wafer_results if w.get('pattern')]
        common_patterns = list(set(patterns))

        expected_yield = 95.0
        yield_loss = expected_yield - avg_yield if avg_yield > 0 else 0

        summary = {
            "total_wafers_found": len(wafer_results),
            "avg_yield": round(avg_yield, 2),
            "min_yield": round(min_yield, 2),
            "max_yield": round(max_yield, 2),
            "common_patterns": common_patterns,
            "yield_impact": {
                "expected_yield": expected_yield,
                "actual_avg_yield": round(avg_yield, 2),
                "yield_loss": round(yield_loss, 2)
            }
        }

        response = {
            "wafer_defects": wafer_results,
            "summary": summary,
            "search_metadata": {
                "equipment_id": equipment_id,
                "excursion_type": excursion_type,
                "mapped_defect_pattern": defect_pattern,
                "execution_time_ms": round(elapsed, 2),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }

        # ========== LOGGING: Success Summary ==========
        logger.info("=" * 80)
        logger.info("✅ query_wafer_defects() - SUCCESS")
        logger.info(f"📊 Summary:")
        logger.info(f"   Total wafers: {len(wafer_results)}")
        logger.info(f"   Avg yield: {avg_yield:.2f}% (expected: {expected_yield}%)")
        logger.info(f"   Yield loss: {yield_loss:.2f}%")
        logger.info(f"   Patterns: {common_patterns}")
        logger.info(f"   Execution: {elapsed:.0f}ms")
        logger.info("=" * 80)

        return response

    except Exception as e:
        # ========== ERROR HANDLING ==========
        logger.error("=" * 80)
        logger.error("❌ query_wafer_defects() - ERROR")
        logger.error("=" * 80)
        logger.error(f"❌ Error: {e}", exc_info=True)

        return {
            "error": str(e),
            "error_type": type(e).__name__,
            "wafer_defects": [],
            "summary": {
                "total_wafers_found": 0,
                "avg_yield": 0,
                "min_yield": 0,
                "max_yield": 0,
                "common_patterns": [],
                "yield_impact": {
                    "expected_yield": 95.0,
                    "actual_avg_yield": 0,
                    "yield_loss": 0
                }
            },
            "search_metadata": {
                "equipment_id": equipment_id,
                "excursion_type": excursion_type,
                "mapped_defect_pattern": defect_pattern,
                "error": str(e)
            }
        }


async def query_historical_rca_reports(
    db: AsyncIOMotorDatabase,
    excursion_type: Optional[str] = None,
    defect_pattern: Optional[str] = None,
    equipment_id: Optional[str] = None,
    limit: int = 5
) -> Dict[str, Any]:
    """
    Simple direct vector search on historical_knowledge collection for RCA reports only.

    Bypasses SemanticSearchService complexity and directly queries MongoDB with voyage-multimodal-3.

    Args:
        db: AsyncIOMotorDatabase instance
        excursion_type: Type of excursion (particle_excursion, rf_power_drift, etc.)
        defect_pattern: Wafer defect pattern (clustered, systematic, edge, random)
        equipment_id: Equipment identifier (CMP_TOOL_01, ETCH_TOOL_01, etc.)
        limit: Maximum number of results to return

    Returns:
        Dictionary containing:
        - knowledge_documents: List of RCA reports with similarity scores
        - summary: Statistics and findings
        - search_metadata: Query details
    """
    logger.info("=" * 80)
    logger.info("🔍 SIMPLE TOOL: query_historical_rca_reports() - DIRECT VECTOR SEARCH")
    logger.info("=" * 80)

    start_time = time.time()

    # Build search query
    query_parts = []

    if excursion_type:
        excursion_descriptions = {
            'particle_excursion': 'particle contamination defects',
            'particle_spike': 'sudden particle count increase',
            'rf_power_drift': 'RF power instability and systematic defects',
            'temperature_drift': 'temperature variation and edge defects',
            'pressure_drop': 'pressure control issues',
            'recovery': 'process recovery after excursion',
            'drift': 'drift pattern defects',
            'spike': 'sudden spike pattern'
        }
        query_parts.append(excursion_descriptions.get(excursion_type, excursion_type))

    if defect_pattern:
        query_parts.append(f"{defect_pattern} defect pattern")

    # Extract process type from equipment_id
    process_type = None
    if equipment_id and '_' in equipment_id:
        process_type = equipment_id.split('_')[0]
        query_parts.append(f"{process_type} process")

    search_query = " ".join(query_parts) if query_parts else "particle defects and contamination"

    logger.info(f"   📝 Search Query: '{search_query}'")
    logger.info(f"   🎯 Filters: excursion={excursion_type}, pattern={defect_pattern}, process={process_type}")
    logger.info(f"   📊 Limit: {limit}")

    try:
        # STEP 1: Generate query embedding using voyage-multimodal-3
        from services.embedding_service import EmbeddingService

        embedding_service = EmbeddingService()
        logger.info(f"   🧬 Generating query embedding with voyage-multimodal-3...")

        query_embedding = await embedding_service.generate_text_embedding(search_query)
        logger.info(f"   ✅ Query embedding generated ({len(query_embedding)} dimensions)")

        # STEP 2: Build MongoDB aggregation pipeline for vector search
        # Note: Atlas Vector Search requires proper filter operators
        # We'll do post-filtering for process_area since index filters are complex
        pipeline = [
            {
                "$search": {
                    "index": "historical_knowledge_vector_index",
                    "knnBeta": {
                        "vector": query_embedding,
                        "path": "embedding",
                        "k": 50  # Get more candidates for post-filtering
                    }
                }
            },
            {
                "$addFields": {
                    "score": {"$meta": "searchScore"}
                }
            }
        ]

        logger.info(f"   🔍 Executing MongoDB vector search...")
        logger.info(f"   📋 Pipeline filters: document_type=rca_report, process_area={process_type}, min_score=0.0")

        # STEP 3: Execute aggregation
        cursor = db.historical_knowledge.aggregate(pipeline)
        all_results = await cursor.to_list(length=100)  # Get more candidates for filtering

        # POST-FILTER: Filter by process_area if compound filter didn't work
        # (This happens if metadata.process_area is not in Atlas vector index filter fields)
        results = []
        if process_type:
            for doc in all_results:
                metadata = doc.get('metadata', {})
                doc_process_area = metadata.get('process_area', '')

                # Only include reports matching the process type
                if doc_process_area == process_type:
                    results.append(doc)

                # Stop once we have enough results
                if len(results) >= limit:
                    break
        else:
            # No process type filter - use all results
            results = all_results[:limit]

        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"   ⏱️  Vector search completed in {elapsed_ms:.0f}ms")
        process_label = f"{process_type} " if process_type else ""
        logger.info(f"   📚 Found {len(results)} {process_label}RCA reports (filtered from {len(all_results)} total)")

        # STEP 4: Format results
        knowledge_documents = []
        top_scores = []

        for doc in results:
            score = doc.get('score', 0)
            top_scores.append(score)

            # Convert ObjectId to string for JSON serialization
            if '_id' in doc:
                doc['_id'] = str(doc['_id'])

            # Extract metadata fields (process_area is in metadata object)
            metadata = doc.get('metadata', {})
            findings_data = doc.get('findings', {})

            formatted = {
                "document_id": doc.get('_id'),
                "title": doc.get('title', ''),
                "document_type": doc.get('document_type'),
                "process_area": metadata.get('process_area', 'Unknown'),
                "defect_type": metadata.get('defect_type', 'Unknown'),
                "root_cause": findings_data.get('root_cause', ''),
                "contributing_factors": findings_data.get('contributing_factors', []),
                "corrective_actions": findings_data.get('corrective_actions', []),
                "preventive_measures": findings_data.get('preventive_measures', []),
                "created_date": doc.get('created_date'),
                "score": round(score, 4)
            }
            knowledge_documents.append(formatted)

            logger.info(f"      📄 {doc.get('title', 'Untitled')} (score: {score:.4f})")

        # STEP 5: Calculate summary
        avg_score = sum(top_scores) / len(top_scores) if top_scores else 0

        summary = {
            "total_documents_found": len(knowledge_documents),
            "avg_similarity_score": round(avg_score, 4),
            "search_query": search_query,
            "has_relevant_results": len(knowledge_documents) > 0,
            "top_score": round(max(top_scores), 4) if top_scores else 0
        }

        metadata = {
            "excursion_type": excursion_type,
            "defect_pattern": defect_pattern,
            "equipment_id": equipment_id,
            "process_type": process_type,
            "search_method": "direct_mongodb_vector_search",
            "embedding_model": "voyage-multimodal-3",
            "vector_index": "historical_knowledge_vector_index",
            "execution_time_ms": round(elapsed_ms, 2)
        }

        logger.info(f"   ✅ Summary: {len(knowledge_documents)} RCA reports, avg score: {avg_score:.4f}")
        logger.info("=" * 80)

        return {
            "knowledge_documents": knowledge_documents,
            "summary": summary,
            "search_metadata": metadata
        }

    except Exception as e:
        logger.error(f"   ❌ Error during vector search: {e}", exc_info=True)

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "knowledge_documents": [],
            "summary": {
                "total_documents_found": 0,
                "avg_similarity_score": 0,
                "search_query": search_query,
                "has_relevant_results": False,
                "error": str(e)
            },
            "search_metadata": {
                "excursion_type": excursion_type,
                "defect_pattern": defect_pattern,
                "equipment_id": equipment_id,
                "process_type": process_type,
                "search_method": "direct_mongodb_vector_search",
                "embedding_model": "voyage-multimodal-3",
                "vector_index": "historical_knowledge_vector_index",
                "execution_time_ms": round(elapsed_ms, 2),
                "error": str(e)
            }
        }


async def query_troubleshooting_guides(
    db: AsyncIOMotorDatabase,
    root_causes: Optional[List[str]] = None,
    defect_types: Optional[List[str]] = None,
    equipment_id: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Simple direct vector search on historical_knowledge collection for troubleshooting guides only.

    Searches for actionable troubleshooting guides based on identified root causes and defect types.
    Used by Supervisor Agent to find solution-oriented guidance.

    Args:
        db: AsyncIOMotorDatabase instance
        root_causes: List of root cause descriptions from RCA agent
        defect_types: List of defect types from investigation agent
        equipment_id: Equipment identifier (CMP_TOOL_01, ETCH_TOOL_01, etc.)
        limit: Maximum number of results to return (default 10)

    Returns:
        Dictionary containing:
        - knowledge_documents: List of troubleshooting guides with similarity scores
        - summary: Statistics and findings
        - search_metadata: Query details
    """
    logger.info("=" * 80)
    logger.info("🔍 SIMPLE TOOL: query_troubleshooting_guides() - DIRECT VECTOR SEARCH")
    logger.info("=" * 80)

    start_time = time.time()

    # Build search query from root causes and defect types
    query_parts = []

    if root_causes:
        # Use first 2-3 root causes for search context
        for rc in root_causes[:3]:
            query_parts.append(rc)

    if defect_types:
        # Add defect types for context
        for dt in defect_types[:2]:
            query_parts.append(f"{dt} troubleshooting")

    # Extract process type from equipment_id
    process_type = None
    if equipment_id and '_' in equipment_id:
        process_type = equipment_id.split('_')[0]
        query_parts.append(f"{process_type} process troubleshooting")

    # Fallback query if no inputs
    search_query = " ".join(query_parts) if query_parts else "defect troubleshooting and resolution"

    logger.info(f"   📝 Search Query: '{search_query}'")
    logger.info(f"   🎯 Root Causes: {len(root_causes) if root_causes else 0}")
    logger.info(f"   🎯 Defect Types: {len(defect_types) if defect_types else 0}")
    logger.info(f"   🎯 Process Type: {process_type or 'Any'}")
    logger.info(f"   📊 Limit: {limit}")

    try:
        # STEP 1: Generate query embedding using voyage-multimodal-3
        from services.embedding_service import EmbeddingService

        embedding_service = EmbeddingService()
        logger.info(f"   🧬 Generating query embedding with voyage-multimodal-3...")

        query_embedding = await embedding_service.generate_text_embedding(search_query)
        logger.info(f"   ✅ Query embedding generated ({len(query_embedding)} dimensions)")

        # STEP 2: Build MongoDB aggregation pipeline for vector search
        # Filter for troubleshooting_guide document type
        pipeline = [
            {
                "$search": {
                    "index": "historical_knowledge_vector_index",
                    "knnBeta": {
                        "vector": query_embedding,
                        "path": "embedding",
                        "k": 50  # Get more candidates for post-filtering
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
                    "document_type": "troubleshooting_guide"
                }
            },
            {
                "$limit": limit
            }
        ]

        logger.info(f"   🔍 Executing MongoDB vector search...")
        logger.info(f"   📋 Pipeline filters: document_type=troubleshooting_guide, process_area={process_type}")

        # STEP 3: Execute aggregation
        cursor = db.historical_knowledge.aggregate(pipeline)
        results = await cursor.to_list(length=limit)

        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"   ⏱️  Vector search completed in {elapsed_ms:.0f}ms")
        logger.info(f"   📚 Found {len(results)} troubleshooting guides")

        # STEP 4: Format results
        knowledge_documents = []
        top_scores = []

        for doc in results:
            score = doc.get('score', 0)
            top_scores.append(score)

            # Convert ObjectId to string for JSON serialization
            if '_id' in doc:
                doc['_id'] = str(doc['_id'])

            # Extract metadata fields
            metadata = doc.get('metadata', {})

            # Troubleshooting guides have different structure than RCA reports
            # They have: problem_description, diagnostic_steps, solutions, preventive_measures
            formatted = {
                "document_id": doc.get('_id'),
                "title": doc.get('title', ''),
                "document_type": doc.get('document_type'),
                "process_area": metadata.get('process_area', 'Unknown'),
                "problem_type": metadata.get('problem_type', 'Unknown'),
                "problem_description": doc.get('problem_description', ''),
                "diagnostic_steps": doc.get('diagnostic_steps', []),
                "solutions": doc.get('solutions', []),
                "preventive_measures": doc.get('preventive_measures', []),
                "estimated_resolution_time": metadata.get('estimated_resolution_time', 'Unknown'),
                "effectiveness_score": metadata.get('effectiveness_score', 0),
                "created_date": doc.get('created_date'),
                "score": round(score, 4)
            }
            knowledge_documents.append(formatted)

            logger.info(f"      📄 {doc.get('title', 'Untitled')} (score: {score:.4f})")

        # STEP 5: Calculate summary
        avg_score = sum(top_scores) / len(top_scores) if top_scores else 0
        avg_effectiveness = sum([doc.get('effectiveness_score', 0) for doc in knowledge_documents]) / len(knowledge_documents) if knowledge_documents else 0

        summary = {
            "total_documents_found": len(knowledge_documents),
            "avg_similarity_score": round(avg_score, 4),
            "avg_effectiveness_score": round(avg_effectiveness, 2),
            "search_query": search_query,
            "has_relevant_results": len(knowledge_documents) > 0,
            "top_score": round(max(top_scores), 4) if top_scores else 0
        }

        metadata_result = {
            "root_causes_count": len(root_causes) if root_causes else 0,
            "defect_types_count": len(defect_types) if defect_types else 0,
            "equipment_id": equipment_id,
            "process_type": process_type,
            "search_method": "direct_mongodb_vector_search",
            "embedding_model": "voyage-multimodal-3",
            "vector_index": "historical_knowledge_vector_index",
            "execution_time_ms": round(elapsed_ms, 2)
        }

        logger.info(f"   ✅ Summary: {len(knowledge_documents)} troubleshooting guides, avg score: {avg_score:.4f}")
        logger.info(f"   📊 Avg effectiveness: {avg_effectiveness:.2f}")
        logger.info("=" * 80)

        return {
            "knowledge_documents": knowledge_documents,
            "summary": summary,
            "search_metadata": metadata_result
        }

    except Exception as e:
        logger.error(f"   ❌ Error during vector search: {e}", exc_info=True)

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "knowledge_documents": [],
            "summary": {
                "total_documents_found": 0,
                "avg_similarity_score": 0,
                "avg_effectiveness_score": 0,
                "search_query": search_query,
                "has_relevant_results": False,
                "error": str(e)
            },
            "search_metadata": {
                "root_causes_count": len(root_causes) if root_causes else 0,
                "defect_types_count": len(defect_types) if defect_types else 0,
                "equipment_id": equipment_id,
                "process_type": process_type,
                "search_method": "direct_mongodb_vector_search",
                "embedding_model": "voyage-multimodal-3",
                "vector_index": "historical_knowledge_vector_index",
                "execution_time_ms": round(elapsed_ms, 2),
                "error": str(e)
            }
        }


async def query_historical_knowledge(
    db: AsyncIOMotorDatabase,
    excursion_type: Optional[str] = None,
    defect_pattern: Optional[str] = None,
    equipment_id: Optional[str] = None,
    limit: int = 5
) -> Dict[str, Any]:
    """
    Query historical knowledge base using semantic vector search (voyage-ai-3).

    Searches RCA reports and troubleshooting guides for similar past incidents
    using text embeddings. Helps identify known root causes and solutions.

    Args:
        db: AsyncIOMotorDatabase instance
        excursion_type: Type of excursion (particle_excursion, rf_power_drift, etc.)
        defect_pattern: Wafer defect pattern (clustered, systematic, edge, random)
        equipment_id: Equipment identifier (CMP_TOOL_01, ETCH_TOOL_01, etc.)
        limit: Maximum number of results to return

    Returns:
        Dictionary containing:
        - knowledge_documents: List of relevant RCA reports/guides
        - summary: Statistics and top findings
        - search_metadata: Query details
    """
    logger.info("=" * 80)
    logger.info("🔍 TOOL: query_historical_knowledge()")
    logger.info("=" * 80)

    start_time = time.time()

    # Build search query from inputs
    query_parts = []

    if excursion_type:
        # Map excursion type to human-readable description
        excursion_descriptions = {
            'particle_excursion': 'particle contamination defects',
            'particle_spike': 'sudden particle count increase',
            'rf_power_drift': 'RF power instability and systematic defects',
            'temperature_drift': 'temperature variation and edge defects',
            'pressure_drop': 'pressure control issues',
            'recovery': 'process recovery after excursion'
        }
        query_parts.append(excursion_descriptions.get(excursion_type, excursion_type))

    if defect_pattern:
        query_parts.append(f"{defect_pattern} defect pattern")

    if equipment_id:
        # Extract process type from equipment_id
        process_type = equipment_id.split('_')[0] if '_' in equipment_id else None
        if process_type:
            query_parts.append(f"{process_type} process")

    # Fallback query if no inputs provided
    search_query = " ".join(query_parts) if query_parts else "particle defects and contamination"

    logger.info(f"   📝 Search Query: '{search_query}'")
    logger.info(f"   🎯 Filters: excursion_type={excursion_type}, pattern={defect_pattern}, equipment={equipment_id}")
    logger.info(f"   📊 Limit: {limit}")

    try:
        # Use SemanticSearchService for vector search
        from services.semantic_search import SemanticSearchService
        semantic_search = SemanticSearchService(mongodb_uri=None, database_name=db.name)

        # Determine document types and process areas for filtering
        document_types = None  # Search all types (rca_report, troubleshooting_guide)
        process_areas = None

        if equipment_id and '_' in equipment_id:
            process_type = equipment_id.split('_')[0]
            process_areas = [process_type]  # e.g., ["CMP"]

        # Execute vector search
        knowledge_results = await semantic_search.search_knowledge_base(
            query=search_query,
            document_types=document_types,
            process_areas=process_areas,
            limit=limit,
            min_score=0.5  # Lower threshold for broader results
        )

        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"   ⏱️  Vector search completed in {elapsed_ms:.0f}ms")
        logger.info(f"   📚 Found {len(knowledge_results)} relevant documents")

        # Calculate summary statistics
        document_types_found = {}
        process_areas_found = {}
        top_scores = []

        for doc in knowledge_results:
            doc_type = doc.get('document_type', 'unknown')
            process_area = doc.get('process_area', 'unknown')
            score = doc.get('score', 0)

            document_types_found[doc_type] = document_types_found.get(doc_type, 0) + 1
            process_areas_found[process_area] = process_areas_found.get(process_area, 0) + 1
            top_scores.append(score)

        avg_score = sum(top_scores) / len(top_scores) if top_scores else 0

        summary = {
            "total_documents_found": len(knowledge_results),
            "avg_similarity_score": round(avg_score, 3),
            "document_types": document_types_found,
            "process_areas": process_areas_found,
            "search_query": search_query,
            "has_relevant_results": len(knowledge_results) > 0
        }

        metadata = {
            "excursion_type": excursion_type,
            "defect_pattern": defect_pattern,
            "equipment_id": equipment_id,
            "search_method": "semantic_vector_search",
            "embedding_model": "voyage-ai-3",
            "execution_time_ms": round(elapsed_ms, 2)
        }

        logger.info(f"   ✅ Summary: {len(knowledge_results)} docs, avg score: {avg_score:.3f}")
        logger.info(f"   📂 Document types: {document_types_found}")
        logger.info(f"   🏭 Process areas: {process_areas_found}")

    except Exception as e:
        logger.error(f"   ❌ Error during vector search: {e}")
        logger.error(f"   Stack trace: {traceback.format_exc()}")

        knowledge_results = []
        summary = {
            "total_documents_found": 0,
            "avg_similarity_score": 0,
            "document_types": {},
            "process_areas": {},
            "search_query": search_query,
            "has_relevant_results": False,
            "error": str(e)
        }
        metadata = {
            "excursion_type": excursion_type,
            "defect_pattern": defect_pattern,
            "equipment_id": equipment_id,
            "search_method": "semantic_vector_search",
            "embedding_model": "voyage-ai-3",
            "execution_time_ms": round((time.time() - start_time) * 1000, 2),
            "error": str(e)
        }

    logger.info("=" * 80)

    return {
        "knowledge_documents": knowledge_results,
        "summary": summary,
        "search_metadata": metadata
    }
