import os
import logging

from db.mdb import MongoDBConnector
from config.config_loader import ConfigLoader
from bedrock.cohere_embeddings import BedrockCohereEnglishEmbeddings

from dotenv import load_dotenv
import os
from tqdm import tqdm

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class Embedder(MongoDBConnector):
    def __init__(self, collection_name: str=None, uri=None, database_name: str = None, appname: str = None):
        """
        Embedder class to generate embeddings for text data stored in MongoDB.

        Args:
            collection_name (str, optional): Collection name. Default is MDB_EMBEDDINGS_COLLECTION.
            uri (str, optional): MongoDB URI. Default parent class value.
            database_name (str, optional): Database name. Default parent class value.
            appname (str, optional): Application name. Default parent class value.
        """
        super().__init__(uri, database_name, appname)

        # Load configuration
        config = ConfigLoader()
        # Get the MongoDB vectors collection name from the config
        MDB_EMBEDDINGS_COLLECTION = config.get("MDB_EMBEDDINGS_COLLECTION")
        self.collection_name = collection_name or MDB_EMBEDDINGS_COLLECTION
        self.collection = self.get_collection(self.collection_name)

    @staticmethod
    def get_embedding(text: str) -> BedrockCohereEnglishEmbeddings:
        """Generate an embedding for the given text using Bedrock Cohere English Embeddings.

        Args:
            text (str): Text to generate an embedding for.

        Returns:
            BedrockCohereEnglishEmbeddings: Embedding for the given text.
        """
        # Check for valid input
        if not text or not isinstance(text, str):
            logging.error("Invalid input. Please provide a valid text input.")
            return None

        # Load configuration
        config = ConfigLoader()
        # Load Cohere English model ID from config
        model_id = config.get("EMBEDDINGS_MODEL_ID")

        # Example usage of the BedrockCohereEnglishEmbeddings class.
        embeddings = BedrockCohereEnglishEmbeddings(
            model_id=model_id,
            region_name=os.getenv("AWS_REGION")
        )

        try:
            # Call the predict method to generate embeddings
            embedding = embeddings.predict(text)
            return embedding
        except Exception as e:
            print(f"Error in get_embedding: {e}")
            return None

    def embed(self, attribute_name: str, overwrite: bool = True):
        """
        Generate embeddings for a specified attribute in the MongoDB collection and store them.

        Args:
            attribute_name (str): The attribute name to generate embeddings for.
            overwrite (bool): Whether to overwrite existing embeddings. Default is True.
        """
        # Check if the attribute exists in the collection
        sample_doc = self.collection.find_one()
        if attribute_name not in sample_doc:
            logger.error(
                f"Attribute '{attribute_name}' not found in the collection.")
            return

        # Get the total number of documents for the progress bar
        total_docs = self.collection.count_documents({})

        # Process each document in the collection
        for doc in tqdm(self.collection.find(), desc="Embedding documents", total=total_docs):
            text = doc.get(attribute_name)
            if text:
                embedding_field = f"{attribute_name}_embedding"
                if not overwrite and embedding_field in doc:
                    logger.info(
                        f"Skipping document with _id: {doc['_id']} as '{embedding_field}' already exists.")
                    continue

                embedding = self.get_embedding(text)
                if embedding is not None:
                    self.collection.update_one(
                        {"_id": doc["_id"]},
                        {"$set": {embedding_field: embedding}}
                    )
                else:
                    logger.error(
                        f"Failed to generate embedding for document with _id: {doc['_id']}")

        logger.info(
            f"Successfully embedded '{attribute_name}' in the collection.")
        return {"status": "success", "message": "Embedding completed in attribute '{attribute_name}' for all documents."}

# ==================
# Example usage
# ==================


if __name__ == "__main__":

    # Example usage
    embedder = Embedder()
    embedder.embed(attribute_name="query", overwrite=True)
