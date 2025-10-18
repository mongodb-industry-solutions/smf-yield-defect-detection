"""
Semantic Search Router
Handles all semantic search and embedding-related endpoints
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Body

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="",
    tags=["Semantic Search"],
    responses={404: {"description": "Not found"}},
)

# Dependencies (injected from main.py on startup)
semantic_search_service = None
mongodb_client_instance = None
database_name = None

def set_dependencies(semantic_search_svc, mongodb_client, db_name: str):
    """
    Inject dependencies from main.py
    """
    global semantic_search_service, mongodb_client_instance, database_name
    semantic_search_service = semantic_search_svc
    mongodb_client_instance = mongodb_client
    database_name = db_name
    logger.info("✅ Semantic search dependencies injected into router")


def get_semantic_search_service():
    """
    Get semantic search service with error handling
    """
    if semantic_search_service is None:
        logger.error("❌ Semantic search service not initialized")
        raise HTTPException(status_code=503, detail="Semantic search not available")
    return semantic_search_service


@router.post("/search/semantic")
async def semantic_search(
    query: str = Body(..., description="Search query"),
    collections: List[str] = Body(None, description="Collections to search"),
    limit: int = Body(10, description="Maximum results per collection")
):
    """
    Perform semantic search across knowledge base
    """
    logger.info(f"📥 POST /search/semantic - Request received: query='{query[:50]}...', collections={collections}, limit={limit}")
    
    try:
        service = get_semantic_search_service()
        
        logger.debug(f"🔧 Calling semantic_search_service.hybrid_search...")
        # Perform hybrid search across collections
        results = await service.hybrid_search(
            query=query,
            collections=collections,
            limit_per_collection=limit
        )
        
        total_results = sum(len(r) for r in results.values())
        response = {
            "query": query,
            "results": results,
            "total_results": total_results
        }
        
        logger.info(f"✅ POST /search/semantic - Success: {total_results} results")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ POST /search/semantic - Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search/similar-defects")
async def find_similar_defects(
    wafer_id: Optional[str] = Body(None, description="Reference wafer ID"),
    pattern: Optional[str] = Body(None, description="Defect pattern"),
    equipment: Optional[str] = Body(None, description="Equipment filter"),
    image_data: Optional[str] = Body(None, description="Base64 encoded image"),
    limit: int = Body(10, description="Maximum results")
):
    """
    Find similar wafer defects using vector similarity
    """
    logger.info(f"📥 POST /search/similar-defects - Request received: wafer_id={wafer_id}, pattern={pattern}, equipment={equipment}, has_image={bool(image_data)}, limit={limit}")
    
    try:
        service = get_semantic_search_service()
        
        logger.debug(f"🔧 Calling semantic_search_service.find_similar_defects...")
        results = await service.find_similar_defects(
            wafer_id=wafer_id,
            pattern=pattern,
            equipment=equipment,
            image_data=image_data,
            limit=limit
        )
        
        response = {
            "search_criteria": {
                "wafer_id": wafer_id,
                "pattern": pattern,
                "equipment": equipment,
                "has_image": bool(image_data)
            },
            "similar_defects": results,
            "count": len(results)
        }
        
        logger.info(f"✅ POST /search/similar-defects - Success: {len(results)} results")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ POST /search/similar-defects - Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search/rca-knowledge")
async def search_rca_knowledge(
    query: str = Body(..., description="Search query"),
    document_types: List[str] = Body(None, description="Document types to search"),
    process_areas: List[str] = Body(None, description="Process areas to filter"),
    limit: int = Body(10, description="Maximum results")
):
    """
    Search RCA knowledge base semantically
    """
    logger.info(f"📥 POST /search/rca-knowledge - Request received: query='{query[:50]}...', document_types={document_types}, process_areas={process_areas}, limit={limit}")
    
    try:
        service = get_semantic_search_service()
        
        logger.debug(f"🔧 Calling semantic_search_service.search_knowledge_base...")
        results = await service.search_knowledge_base(
            query=query,
            document_types=document_types,
            process_areas=process_areas,
            limit=limit
        )
        
        response = {
            "query": query,
            "filters": {
                "document_types": document_types,
                "process_areas": process_areas
            },
            "knowledge_documents": results,
            "count": len(results)
        }
        
        logger.info(f"✅ POST /search/rca-knowledge - Success: {len(results)} results")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ POST /search/rca-knowledge - Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/embeddings/status")
async def get_embeddings_status():
    """
    Check embedding generation status
    """
    logger.info(f"📥 GET /embeddings/status - Request received")
    
    try:
        if not mongodb_client_instance or not database_name:
            logger.error("❌ MongoDB client not initialized")
            raise HTTPException(status_code=503, detail="Database not available")
        
        logger.debug(f"🔧 Querying MongoDB for embedding counts...")
        # Get counts from collections
        db = mongodb_client_instance[database_name]
        
        # Count documents with embeddings
        historical_with_embeddings = await db.historical_knowledge.count_documents(
            {"embedding": {"$exists": True}}
        )
        historical_total = await db.historical_knowledge.count_documents({})
        
        wafer_with_embeddings = await db.wafer_defects.count_documents(
            {"embedding": {"$exists": True}}
        )
        wafer_total = await db.wafer_defects.count_documents({})
        
        alerts_with_embeddings = await db.alerts.count_documents(
            {"embedding": {"$exists": True}}
        )
        alerts_total = await db.alerts.count_documents({})
        
        response = {
            "status": "operational",
            "collections": {
                "historical_knowledge": {
                    "with_embeddings": historical_with_embeddings,
                    "total": historical_total,
                    "percentage": round(historical_with_embeddings / historical_total * 100, 2) if historical_total > 0 else 0
                },
                "wafer_defects": {
                    "with_embeddings": wafer_with_embeddings,
                    "total": wafer_total,
                    "percentage": round(wafer_with_embeddings / wafer_total * 100, 2) if wafer_total > 0 else 0
                },
                "alerts": {
                    "with_embeddings": alerts_with_embeddings,
                    "total": alerts_total,
                    "percentage": round(alerts_with_embeddings / alerts_total * 100, 2) if alerts_total > 0 else 0
                }
            }
        }
        
        logger.info(f"✅ GET /embeddings/status - Success")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ GET /embeddings/status - Error: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


logger.info("📦 Semantic search router initialized")

