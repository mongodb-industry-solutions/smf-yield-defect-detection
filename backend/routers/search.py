"""
Unified Search Router
Provides REST API endpoints for searching across multiple collections

Endpoints:
- POST /search/unified: Search all collections in parallel
- POST /search/wafers: Search wafer defects only
- POST /search/process-context: Search process context only
- POST /search/knowledge: Search historical knowledge only
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import logging

from services.unified_search_service import UnifiedSearchService

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/search", tags=["Search"])

# Initialize service (singleton pattern)
_search_service = None


def get_search_service() -> UnifiedSearchService:
    """Dependency injection for search service"""
    global _search_service
    if _search_service is None:
        _search_service = UnifiedSearchService()
    return _search_service


# ============================================================================
# Request/Response Models
# ============================================================================

class UnifiedSearchRequest(BaseModel):
    """Request model for unified search across all collections"""
    query: str = Field(
        ...,
        description="Search query text",
        example="particle excursion due to padding wear"
    )
    limit_per_collection: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum results per collection"
    )


class WaferSearchRequest(BaseModel):
    """Request model for wafer defect search"""
    query: str = Field(
        ...,
        description="Search query for wafer defects",
        example="clustered defects with low yield"
    )
    equipment_id: Optional[str] = Field(
        default=None,
        description="Filter by equipment ID",
        example="CMP_TOOL_01"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of results"
    )


class ProcessContextSearchRequest(BaseModel):
    """Request model for process context search"""
    query: str = Field(
        ...,
        description="Search query for process context",
        example="padding wear slurry batch"
    )
    context_types: Optional[List[str]] = Field(
        default=None,
        description="Filter by context types: slurry_batch, etch_recipe, reticle",
        example=["slurry_batch"]
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of results"
    )


class HistoricalKnowledgeSearchRequest(BaseModel):
    """Request model for historical knowledge search"""
    query: str = Field(
        ...,
        description="Search query for RCA reports and troubleshooting guides",
        example="particle contamination root cause analysis"
    )
    document_types: Optional[List[str]] = Field(
        default=None,
        description="Filter by document types: rca_report, troubleshooting_guide",
        example=["rca_report"]
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of results"
    )


class SearchResponse(BaseModel):
    """Generic search response model"""
    results: List[Dict[str, Any]] = Field(
        description="Search results with relevance scores"
    )
    summary: Dict[str, Any] = Field(
        description="Summary statistics"
    )
    search_metadata: Dict[str, Any] = Field(
        description="Query execution metadata"
    )


class UnifiedSearchResponse(BaseModel):
    """Response model for unified search"""
    wafer_results: List[Dict[str, Any]] = Field(
        description="Wafer defect search results"
    )
    process_context_results: List[Dict[str, Any]] = Field(
        description="Process context search results"
    )
    knowledge_results: List[Dict[str, Any]] = Field(
        description="Historical knowledge search results"
    )
    summary: Dict[str, Any] = Field(
        description="Overall search summary"
    )
    query_metadata: Dict[str, Any] = Field(
        description="Query execution metadata"
    )


# ============================================================================
# API Endpoints
# ============================================================================

@router.post(
    "/unified",
    response_model=UnifiedSearchResponse,
    summary="Unified Search Across All Collections",
    description="""
    Search across wafer_defects, process_context, and historical_knowledge collections in parallel.
    
    **Example Queries:**
    - "particle excursion due to padding wear"
    - "clustered defects with slurry contamination"
    - "edge defects caused by temperature drift"
    
    **Search Methods:**
    - wafer_defects: Multimodal vector search (voyage-multimodal-3)
    - process_context: Text-based regex search
    - historical_knowledge: Vector search on RCA reports and troubleshooting guides
    
    **Returns:** Combined results from all three collections with relevance scores
    """
)
async def unified_search(
    request: UnifiedSearchRequest,
    service: UnifiedSearchService = Depends(get_search_service)
) -> UnifiedSearchResponse:
    """
    Execute unified search across all collections
    
    This endpoint searches wafer_defects, process_context, and historical_knowledge
    collections in parallel, providing a comprehensive view of relevant data.
    """
    try:
        logger.info(f"🔍 Unified search request: '{request.query}'")
        
        result = await service.search_all(
            query=request.query,
            limit_per_collection=request.limit_per_collection
        )
        
        return UnifiedSearchResponse(**result)
    
    except Exception as e:
        logger.error(f"❌ Unified search error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Unified search failed: {str(e)}"
        )


@router.post(
    "/wafers",
    response_model=SearchResponse,
    summary="Search Wafer Defects",
    description="""
    Search wafer defects using multimodal vector search (voyage-multimodal-3).
    
    **Example Queries:**
    - "clustered defects"
    - "edge pattern with low yield"
    - "systematic defects on CMP tool"
    
    **Search Fields:**
    - Defect patterns (clustered, edge, systematic, random)
    - Yield percentages
    - Equipment associations
    - Defect severity
    
    **Returns:** Wafer defects with similarity scores and defect details
    """
)
async def search_wafers(
    request: WaferSearchRequest,
    service: UnifiedSearchService = Depends(get_search_service)
) -> SearchResponse:
    """
    Search wafer defects using vector similarity
    
    Uses multimodal embeddings to find wafers with similar defect patterns
    and characteristics based on the search query.
    """
    try:
        logger.info(f"🔍 Wafer search request: '{request.query}'")
        
        result = await service.search_wafers(
            query=request.query,
            equipment_id=request.equipment_id,
            limit=request.limit
        )
        
        return SearchResponse(**result)
    
    except Exception as e:
        logger.error(f"❌ Wafer search error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Wafer search failed: {str(e)}"
        )


@router.post(
    "/process-context",
    response_model=SearchResponse,
    summary="Search Process Context",
    description="""
    Search process context (slurry batches, etch recipes, reticles) using text-based search.
    
    **Example Queries:**
    - "padding wear"
    - "slurry batch contamination"
    - "PureFlow manufacturer"
    - "problematic batches"
    
    **Context Types:**
    - slurry_batch: Chemical slurries with quality data
    - etch_recipe: Process recipes with parameters
    - reticle: Lithography reticles with inspection data
    
    **Search Fields:**
    - Context IDs and batch numbers
    - Manufacturers and compositions
    - Known issues and quality status
    - Problematic item flags
    
    **Returns:** Process context items with relevance scores and quality indicators
    """
)
async def search_process_context(
    request: ProcessContextSearchRequest,
    service: UnifiedSearchService = Depends(get_search_service)
) -> SearchResponse:
    """
    Search process context using text matching
    
    Searches across slurry batches, etch recipes, and reticles to find
    manufacturing context related to the query.
    """
    try:
        logger.info(f"🔍 Process context search request: '{request.query}'")
        
        result = await service.search_process_context(
            query=request.query,
            context_types=request.context_types,
            limit=request.limit
        )
        
        return SearchResponse(**result)
    
    except Exception as e:
        logger.error(f"❌ Process context search error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Process context search failed: {str(e)}"
        )


@router.post(
    "/knowledge",
    response_model=SearchResponse,
    summary="Search Historical Knowledge",
    description="""
    Search historical knowledge base (RCA reports and troubleshooting guides) using vector search.
    
    **Example Queries:**
    - "particle contamination root cause"
    - "slurry filter degradation solutions"
    - "CMP process troubleshooting"
    - "edge defect preventive measures"
    
    **Document Types:**
    - rca_report: Root cause analysis reports from past incidents
    - troubleshooting_guide: Procedural guides for problem resolution
    
    **Search Fields:**
    - Root causes and contributing factors
    - Corrective actions and solutions
    - Defect types and process areas
    - Preventive measures
    
    **Returns:** RCA reports and guides with similarity scores and actionable recommendations
    """
)
async def search_historical_knowledge(
    request: HistoricalKnowledgeSearchRequest,
    service: UnifiedSearchService = Depends(get_search_service)
) -> SearchResponse:
    """
    Search historical knowledge using vector similarity
    
    Uses embeddings to find relevant RCA reports and troubleshooting guides
    based on the search query.
    """
    try:
        logger.info(f"🔍 Historical knowledge search request: '{request.query}'")
        
        result = await service.search_historical_knowledge(
            query=request.query,
            document_types=request.document_types,
            limit=request.limit
        )
        
        return SearchResponse(**result)
    
    except Exception as e:
        logger.error(f"❌ Historical knowledge search error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Historical knowledge search failed: {str(e)}"
        )


@router.get(
    "/health",
    summary="Search Service Health Check",
    description="Check if the search service is operational"
)
async def search_health() -> Dict[str, Any]:
    """Health check endpoint for search service"""
    try:
        service = get_search_service()
        return {
            "status": "healthy",
            "service": "UnifiedSearchService",
            "database": service.db.name,
            "vector_indexes": {
                "wafer_defects": service.wafer_index,
                "historical_knowledge": service.knowledge_index
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "service": "UnifiedSearchService",
            "error": str(e)
        }

