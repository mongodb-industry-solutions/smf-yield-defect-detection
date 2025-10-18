"""
Collections Router
Handles utility endpoints for MongoDB collection operations
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/collections",
    tags=["Collections"],
    responses={404: {"description": "Not found"}},
)

# Dependencies (injected from main.py on startup)
mongodb_connector_class = None
mongodb_uri = None
database_name = None
convert_objectids_func = None

def set_dependencies(connector_class, uri: str, db_name: str, convert_func):
    """
    Inject dependencies from main.py
    """
    global mongodb_connector_class, mongodb_uri, database_name, convert_objectids_func
    mongodb_connector_class = connector_class
    mongodb_uri = uri
    database_name = db_name
    convert_objectids_func = convert_func
    logger.info("✅ Collections dependencies injected into router")


@router.get("/{collection_name}/latest")
async def get_latest_collection_documents(
    collection_name: str,
    limit: int = Query(default=1, ge=1, le=10, description="Number of documents to fetch (1-10)")
):
    """
    Fetch latest N documents from a specified MongoDB collection.

    Args:
        collection_name: Name of the collection (e.g., 'historical_knowledge', 'wafer_defects')
        limit: Number of documents to return (default 1, max 10)

    Returns:
        List of latest documents from the collection
    """
    logger.info(f"📥 GET /collections/{collection_name}/latest - Request received: limit={limit}")
    
    try:
        if not mongodb_connector_class or not mongodb_uri or not database_name:
            logger.error("❌ MongoDB dependencies not initialized")
            raise HTTPException(status_code=503, detail="Database not available")
        
        logger.debug(f"🔧 Fetching latest {limit} documents from collection '{collection_name}'...")
        with mongodb_connector_class(uri=mongodb_uri, database_name=database_name) as mdb_connector:
            collection = mdb_connector.db[collection_name]

            # Fetch latest documents sorted by _id descending (newest first)
            cursor = collection.find().sort("_id", -1).limit(limit)
            documents = list(cursor)

            # Convert ObjectIds to strings for JSON serialization
            formatted_docs = [convert_objectids_func(doc) for doc in documents]

            response = {
                "collection": collection_name,
                "count": len(formatted_docs),
                "limit": limit,
                "documents": formatted_docs
            }
            
            logger.info(f"✅ GET /collections/{collection_name}/latest - Success: {len(formatted_docs)} documents")
            return response
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ GET /collections/{collection_name}/latest - Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching documents: {str(e)}")


logger.info("📦 Collections router initialized")

