import os
from pymongo import MongoClient
from abc import abstractmethod
from dotenv import load_dotenv
from config.config_loader import ConfigLoader

# Load environment variables from .env file
load_dotenv()

# Load configuration
config = ConfigLoader()


class MongoDBConnector:
    """ MongoDBConnector class to connect to MongoDB. 

    Args:
        uri (str, optional): MongoDB URI. Default is MONGODB_URI environment variable.
        database_name (str, optional): Database name. Default is MDB_DATABASE_NAME.
        collection_name (str, optional): Collection name. Default is None.
        appname (str, optional): Application name. Default is APP_NAME environment variable.
        filepath (str, optional): File path. Default is None.
    """

    def __init__(self, uri=None, database_name=None, collection_name=None, appname=None, filepath=None):
        self.uri = uri or os.getenv("MONGODB_URI")
        self.database_name = database_name or str(config.get("MDB_DATABASE_NAME"))
        self.appname = appname or os.getenv("APP_NAME")
        self.filepath = filepath
        self.collection_name = collection_name
        self.client = MongoClient(self.uri, appname=self.appname)
        self.db = self.client[self.database_name]

    def __enter__(self):
        """Enter the runtime context related to this object."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit the runtime context and close the MongoDB connection."""
        self.close_connection()

    def close_connection(self):
        """Close the MongoDB connection."""
        if self.client:
            self.client.close()

    @abstractmethod
    def run(self, **kwargs):
        """
        Abstract method interface defining common run method.
        """
        pass

    def get_collection(self, collection_name=None):
        """Retrieve a collection."""
        collection_name = collection_name
        return self.db[collection_name]

    def insert_one(self, collection_name: str, document):
        """Insert a single document into a collection."""
        collection = self.get_collection(collection_name)
        result = collection.insert_one(document)
        return result.inserted_id

    def insert_many(self, collection_name: str, documents):
        """Insert multiple documents into a collection."""
        collection = self.get_collection(collection_name)
        result = collection.insert_many(documents)
        return result.inserted_ids

    def find(self, collection_name: str, query={}, projection=None):
        """Retrieve documents from a collection."""
        collection = self.get_collection(collection_name)
        return list(collection.find(query, projection))

    def update_one(self, collection_name: str, query, update, upsert=False):
        """Update a single document in a collection."""
        collection = self.get_collection(collection_name)
        result = collection.update_one(query, update, upsert=upsert)
        return result.modified_count

    def update_many(self, collection_name: str, query, update, upsert=False):
        """Update multiple documents in a collection."""
        collection = self.get_collection(collection_name)
        result = collection.update_many(query, update, upsert=upsert)
        return result.modified_count

    def delete_one(self, collection_name: str, query):
        """Delete a single document from a collection."""
        collection = self.get_collection(collection_name)
        result = collection.delete_one(query)
        return result.deleted_count

    def delete_many(self, collection_name: str, query):
        """Delete multiple documents from a collection."""
        collection = self.get_collection(collection_name)
        result = collection.delete_many(query)
        return result.deleted_count
