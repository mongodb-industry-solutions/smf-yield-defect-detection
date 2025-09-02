import os
import logging
from dotenv import load_dotenv
from pymongo.errors import OperationFailure

from db.mdb import MongoDBConnector
from config.config_loader import ConfigLoader

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load configuration
config = ConfigLoader()
MDB_EMBEDDINGS_COLLECTION = config.get("MDB_EMBEDDINGS_COLLECTION")
MDB_VS_INDEX = config.get("MDB_VS_INDEX")
MDB_EMBEDDINGS_COLLECTION_VS_FIELD = config.get("MDB_EMBEDDINGS_COLLECTION_VS_FIELD")

class VectorSearchIDXCreator(MongoDBConnector):
    def __init__(self, collection_name: str = MDB_EMBEDDINGS_COLLECTION, uri=None, database_name: str = None, appname: str = None):
        """ VectorSearchIDXCreator class to create a vector search index in MongoDB. """
        super().__init__(uri, database_name, appname)
        self.collection_name = collection_name
        self.collection = self.get_collection(self.collection_name)
        logger.info("VectorSearchIDXCreator initialized")

    def create_index(self, index_name: str = MDB_VS_INDEX, vector_field: str = MDB_EMBEDDINGS_COLLECTION_VS_FIELD, dimensions: int = 1024, similarity_metric: str = "cosine") -> dict:
        """
        Creates a vector search index on the MongoDB collection.

        Args:
            index_name (str, optional): Index name. Default is MDB_VS_INDEX.
            vector_field (str, optional): Vector field name. Default is MDB_EMBEDDINGS_COLLECTION_VS_FIELD.
            dimensions (int, optional): Number of dimensions. Default is 1024.
            similarity_metric (str, optional): Similarity metric. Default is "cosine".

        Returns:
            dict: Index creation result
        """
        logger.info(f"Collection: {self.collection_name}")
        logger.info(f"Vector Field: {vector_field}")
        logger.info(f"Dimensions: {dimensions}")
        logger.info(f"Similarity Metric: {similarity_metric}")

        # Define the vector search index configuration
        index_config = {
            "name": index_name,
            "type": "vectorSearch",
            "definition": {
                "fields": [
                    {
                        "path": vector_field,
                        "type": "vector",
                        "numDimensions": dimensions,
                        "similarity": similarity_metric
                    }
                ]
            }
        }

        try:
            # Create the index
            self.collection.create_search_index(index_config)
            logger.info(f"Vector search index '{index_name}' created successfully.")
            return {"status": "success", "message": f"Vector search index '{index_name}' created successfully."}
        except OperationFailure as e:
            if e.code == 68:  # IndexAlreadyExists error code
                logger.info(f"Vector search index '{index_name}' already exists.")
                return {"status": "info", "message": f"Vector search index '{index_name}' already exists."}
            else:
                logger.error(f"Error creating vector search index: {e}")
                return {"status": "error", "message": f"Error creating vector search index: {e}"}
        except Exception as e:
            logger.error(f"Error creating vector search index: {e}")
            return {"status": "error", "message": f"Error creating vector search index: {e}"}

# Example usage
if __name__ == "__main__":
    vs_idx = VectorSearchIDXCreator()
    r = vs_idx.create_index()
    print(r)