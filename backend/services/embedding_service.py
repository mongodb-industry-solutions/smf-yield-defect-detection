"""
Embedding Service for Phase 3
Handles text and multimodal embeddings using Voyage AI
"""

import os
import asyncio
import logging
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import numpy as np
import voyageai
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import hashlib
import json
from collections import OrderedDict
import base64
from PIL import Image
import io

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating and managing embeddings using Voyage AI"""
    
    def __init__(self, mongodb_uri: str = None, database_name: str = "smf-yield-defect"):
        """
        Initialize the embedding service
        
        Args:
            mongodb_uri: MongoDB connection string
            database_name: Database name
        """
        self.voyage_api_key = os.getenv("VOYAGE_API_KEY")
        if not self.voyage_api_key:
            raise ValueError("VOYAGE_API_KEY not found in environment variables")
        
        # Initialize Voyage AI client
        self.voyage_client = voyageai.Client(api_key=self.voyage_api_key)
        
        # MongoDB connection
        self.mongodb_uri = mongodb_uri or os.getenv("MONGODB_URI")
        self.appname = os.getenv("APP_NAME", "devrel-demo-vectorsearch-langgraph-semiconductor")
        self.client = AsyncIOMotorClient(self.mongodb_uri, appname=self.appname)
        self.db = self.client[database_name]
        
        # Collections  
        self.embedding_cache_collection = self.db["embedding_cache"]
        
        # Embedding models - Use multimodal for everything to ensure same vector space
        self.text_model = "voyage-multimodal-3"  # Use multimodal for text too!
        self.multimodal_model = "voyage-multimodal-3"  # For images and text
        self.model_id = "voyage-multimodal-3"  # Default model ID for compatibility
        
        # Configuration
        self.batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", "100"))
        self.cache_size = int(os.getenv("EMBEDDING_CACHE_SIZE", "1000"))
        self.embedding_dimension = 1024
        
        # In-memory cache for frequently used embeddings
        self.cache = OrderedDict()
        
        logger.info(f"Embedding Service initialized with models: {self.text_model}, {self.multimodal_model}")
    
    async def initialize(self):
        """Initialize collections and indexes"""
        try:
            # Only need to initialize cache collection
            await self.embedding_cache_collection.create_index("hash", unique=True)
            await self.embedding_cache_collection.create_index("accessed_at")
            
            logger.info("Embedding cache initialized")
        except Exception as e:
            logger.error(f"Error initializing embedding cache: {e}")
    
    def _get_cache_key(self, text: str, model: str) -> str:
        """Generate cache key for embedding"""
        content = f"{model}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    async def _get_cached_embedding(self, cache_key: str) -> Optional[List[float]]:
        """Get embedding from cache"""
        # Check in-memory cache first
        if cache_key in self.cache:
            self.cache.move_to_end(cache_key)  # LRU update
            return self.cache[cache_key]
        
        # Check database cache
        cached = await self.embedding_cache_collection.find_one({"hash": cache_key})
        if cached:
            # Update access time
            await self.embedding_cache_collection.update_one(
                {"hash": cache_key},
                {"$set": {"accessed_at": datetime.now()}}
            )
            
            # Add to in-memory cache
            embedding = cached["embedding"]
            self._add_to_memory_cache(cache_key, embedding)
            
            return embedding
        
        return None
    
    def _add_to_memory_cache(self, key: str, embedding: List[float]):
        """Add embedding to in-memory cache with LRU eviction"""
        if len(self.cache) >= self.cache_size:
            # Remove least recently used item
            self.cache.popitem(last=False)
        
        self.cache[key] = embedding
    
    async def _save_to_cache(self, cache_key: str, embedding: List[float]):
        """Save embedding to cache"""
        # Save to database cache
        await self.embedding_cache_collection.update_one(
            {"hash": cache_key},
            {
                "$set": {
                    "embedding": embedding,
                    "created_at": datetime.now(),
                    "accessed_at": datetime.now()
                }
            },
            upsert=True
        )
        
        # Add to in-memory cache
        self._add_to_memory_cache(cache_key, embedding)
    
    async def generate_text_embedding(
        self,
        text: str,
        use_cache: bool = True
    ) -> List[float]:
        """
        Generate embedding for text using Voyage AI
        
        Args:
            text: Text to embed
            use_cache: Whether to use caching
            
        Returns:
            Embedding vector
        """
        try:
            # Check cache if enabled
            if use_cache:
                cache_key = self._get_cache_key(text, self.text_model)
                cached_embedding = await self._get_cached_embedding(cache_key)
                if cached_embedding:
                    logger.debug(f"Using cached embedding for text: {text[:50]}...")
                    return cached_embedding
            
            # Generate new embedding using multimodal model for text
            logger.info(f"Generating text embedding for: {text[:50]}...")
            result = self.voyage_client.multimodal_embed(
                inputs=[[text]],  # Wrap text in list for multimodal API
                model=self.text_model,
                input_type="document"
            )
            
            embedding = result.embeddings[0]
            
            # Cache the embedding
            if use_cache:
                await self._save_to_cache(cache_key, embedding)
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating text embedding: {e}")
            raise
    
    async def generate_text_embeddings_batch(
        self,
        texts: List[str],
        use_cache: bool = True
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch
        
        Args:
            texts: List of texts to embed
            use_cache: Whether to use caching
            
        Returns:
            List of embedding vectors
        """
        try:
            embeddings = []
            texts_to_generate = []
            cache_keys = []
            cached_indices = []
            
            # Check cache for each text
            if use_cache:
                for i, text in enumerate(texts):
                    cache_key = self._get_cache_key(text, self.text_model)
                    cached_embedding = await self._get_cached_embedding(cache_key)
                    
                    if cached_embedding:
                        embeddings.append(cached_embedding)
                        cached_indices.append(i)
                    else:
                        texts_to_generate.append(text)
                        cache_keys.append(cache_key)
            else:
                texts_to_generate = texts
            
            # Generate embeddings for uncached texts in batches
            if texts_to_generate:
                logger.info(f"Generating {len(texts_to_generate)} text embeddings in batches...")
                
                for i in range(0, len(texts_to_generate), self.batch_size):
                    batch = texts_to_generate[i:i + self.batch_size]
                    # Wrap each text in a list for multimodal API
                    multimodal_batch = [[text] for text in batch]
                    
                    result = self.voyage_client.multimodal_embed(
                        inputs=multimodal_batch,
                        model=self.text_model,
                        input_type="document"
                    )
                    
                    # Cache the embeddings
                    if use_cache:
                        for j, embedding in enumerate(result.embeddings):
                            cache_key = cache_keys[i + j]
                            await self._save_to_cache(cache_key, embedding)
                    
                    embeddings.extend(result.embeddings)
            
            # Reorder embeddings to match original order if using cache
            if use_cache and cached_indices:
                final_embeddings = [None] * len(texts)
                uncached_idx = 0
                
                for i in range(len(texts)):
                    if i in cached_indices:
                        # Find the cached embedding
                        cache_idx = cached_indices.index(i)
                        final_embeddings[i] = embeddings[cache_idx]
                    else:
                        # Use the generated embedding
                        final_embeddings[i] = embeddings[len(cached_indices) + uncached_idx]
                        uncached_idx += 1
                
                return final_embeddings
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating batch text embeddings: {e}")
            raise
    
    async def generate_image_embedding(
        self,
        image_data: Union[str, bytes],
        text_context: Optional[str] = None
    ) -> List[float]:
        """
        Generate embedding for image using Voyage AI multimodal model
        
        Args:
            image_data: Base64 encoded image string or image bytes
            text_context: Optional text context for the image
            
        Returns:
            Embedding vector
        """
        try:
            from PIL import Image
            import io
            
            # Convert base64 or bytes to PIL Image
            if isinstance(image_data, str):
                # Decode base64 to bytes
                image_bytes = base64.b64decode(image_data)
            else:
                image_bytes = image_data
            
            # Create PIL Image
            pil_image = Image.open(io.BytesIO(image_bytes))
            
            # Prepare input for multimodal model
            inputs = []
            if text_context:
                inputs.append(text_context)  # Add text first
            inputs.append(pil_image)  # Add PIL image
            
            logger.info(f"Generating multimodal embedding for image{' with context' if text_context else ''}...")
            
            # Generate embedding using multimodal model
            result = self.voyage_client.multimodal_embed(
                inputs=[inputs],  # Wrap in list for batch processing
                model=self.multimodal_model,
                input_type="document"
            )
            
            embedding = result.embeddings[0]
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating image embedding: {e}")
            raise
    
    async def store_document_embedding(
        self,
        document_id: str,
        collection_name: str,
        embedding: List[float],
        embedding_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Store embedding directly in the source document
        
        Args:
            document_id: Document identifier
            collection_name: Source collection name
            embedding: Embedding vector
            embedding_type: Type of embedding (text/image/multimodal)
            metadata: Additional metadata
        """
        try:
            # Store embedding directly in the source document
            source_collection = self.db[collection_name]
            
            # Convert string ID to ObjectId if needed
            from bson import ObjectId
            try:
                doc_id = ObjectId(document_id)
            except:
                doc_id = document_id
            
            # Update the document with embedding
            result = await source_collection.update_one(
                {"_id": doc_id},
                {"$set": {
                    "embedding": embedding,
                    "embedding_type": embedding_type,
                    "embedding_model": self.text_model if embedding_type == "text" else self.multimodal_model,
                    "embedding_updated_at": datetime.now()
                }}
            )
            
            if result.modified_count > 0:
                logger.info(f"Stored {embedding_type} embedding for document {document_id} in {collection_name}")
            else:
                logger.warning(f"Document {document_id} not found in {collection_name}")
            
        except Exception as e:
            logger.error(f"Error storing embedding for document {document_id}: {e}")
            raise
    
    async def generate_embeddings_for_collection(
        self,
        collection_name: str,
        text_field: str,
        query_filter: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> int:
        """
        Generate embeddings for all documents in a collection
        
        Args:
            collection_name: Name of the collection
            text_field: Field containing text to embed
            query_filter: Optional filter for documents
            limit: Maximum number of documents to process
            
        Returns:
            Number of embeddings generated
        """
        try:
            collection = self.db[collection_name]
            query = query_filter or {}
            
            # Get documents
            cursor = collection.find(query)
            if limit:
                cursor.limit(limit)
            
            documents = await cursor.to_list(length=None)
            logger.info(f"Processing {len(documents)} documents from {collection_name}")
            
            # Process in batches
            count = 0
            for i in range(0, len(documents), self.batch_size):
                batch = documents[i:i + self.batch_size]
                
                # Extract texts
                texts = []
                doc_ids = []
                for doc in batch:
                    if text_field in doc and doc[text_field]:
                        texts.append(str(doc[text_field]))
                        doc_ids.append(str(doc["_id"]))
                
                if texts:
                    # Generate embeddings
                    embeddings = await self.generate_text_embeddings_batch(texts)
                    
                    # Store embeddings
                    for doc_id, embedding in zip(doc_ids, embeddings):
                        await self.store_document_embedding(
                            document_id=doc_id,
                            collection_name=collection_name,
                            embedding=embedding,
                            embedding_type="text"
                        )
                        count += 1
                
                logger.info(f"Processed batch {i//self.batch_size + 1}, total: {count} embeddings")
            
            return count
            
        except Exception as e:
            logger.error(f"Error generating embeddings for collection {collection_name}: {e}")
            raise
    
    async def search_similar_embeddings(
        self,
        query_embedding: List[float],
        collection_name: str,
        limit: int = 10,
        min_score: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search for similar embeddings using vector similarity
        
        Args:
            query_embedding: Query embedding vector
            collection_name: Collection to search in
            limit: Maximum number of results
            min_score: Minimum similarity score
            
        Returns:
            List of similar documents with scores
        """
        try:
            collection = self.db[collection_name]
            
            # MongoDB Vector Search query
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": f"{collection_name}_vector_index",
                        "path": "embedding",
                        "queryVector": query_embedding,
                        "numCandidates": limit * 10,
                        "limit": limit
                    }
                },
                {
                    "$addFields": {
                        "score": {"$meta": "vectorSearchScore"}
                    }
                },
                {
                    "$match": {
                        "score": {"$gte": min_score}
                    }
                }
            ]
            
            results = await collection.aggregate(pipeline).to_list(length=None)
            
            logger.info(f"Found {len(results)} similar documents in {collection_name}")
            return results
            
        except Exception as e:
            logger.error(f"Error searching similar embeddings: {e}")
            raise
    
    def cleanup(self):
        """Clean up resources"""
        self.client.close()
        logger.info("Embedding Service cleaned up")


# Example usage and testing
if __name__ == "__main__":
    async def test_embedding_service():
        service = EmbeddingService()
        await service.initialize()
        
        # Test text embedding
        text = "High particle count detected in CMP process"
        embedding = await service.generate_text_embedding(text)
        print(f"Text embedding dimension: {len(embedding)}")
        
        # Test batch embeddings
        texts = [
            "Wafer defect pattern shows edge contamination",
            "RF power drift detected in etch chamber",
            "Temperature anomaly in lithography stepper"
        ]
        embeddings = await service.generate_text_embeddings_batch(texts)
        print(f"Generated {len(embeddings)} batch embeddings")
        
        service.cleanup()
    
    asyncio.run(test_embedding_service())