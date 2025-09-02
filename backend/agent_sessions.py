import logging

from langgraph.checkpoint.mongodb import MongoDBSaver
from db.mdb import MongoDBConnector
from config.config_loader import ConfigLoader

import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class AgentSessions(MongoDBConnector):
    def __init__(self, collection_name: str=None, uri=None, database_name: str = None, appname: str = None):
        """
        AgentCheckpointer class to save agent states to MongoDB.

        Args:
            collection_name (str, optional): Collection name. Default is MDB_AGENT_SESSIONS_COLLECTION.
            uri (str, optional): MongoDB URI. Default parent class value.
            database_name (str, optional): Database name. Default parent class value.
            appname (str, optional): Application name. Default parent class value.
        """
        super().__init__(uri, database_name, appname)

        # Load configuration
        config = ConfigLoader()
        # Get the MongoDB checkpointer collection name from the config
        MDB_AGENT_SESSIONS_COLLECTION = config.get("MDB_AGENT_SESSIONS_COLLECTION")
        self.collection_name = collection_name or MDB_AGENT_SESSIONS_COLLECTION
        self.sessions_collection = self.get_collection(collection_name)
        logger.info("AgentSessions initialized")


    def list_available_sessions(self):
        """
        List available sessions in MongoDB.

        Returns:
            bool: True if sessions are available, False otherwise.
        """
        mongo_uri = self.uri
        if not mongo_uri:
            logger.warning("[MongoDB] MONGO_URI not set. Cannot retrieve sessions.")
            return None
        try:
            logger.info(f"[MongoDB] Initializing AgentSessions!")
            recent_sessions = list(self.sessions_collection.find().sort("created_at", -1).limit(10))
            if not recent_sessions:
                logging.warning("No previous sessions found.")
                return False
            logger.info(f"\n=== Recent Sessions ===")
            logger.info("ID | Time | Query | Status")
            logger.info("-" * 70)
            for session in recent_sessions:
                thread_id = session.get("thread_id", "unknown")
                created_at = session.get("created_at", "unknown")
                query = session.get("query_reported", "unknown")
                status = session.get("status", "unknown")
                if len(query) > 30:
                    query = query[:27] + "..."
                if isinstance(created_at, datetime.datetime):
                    created_at = created_at.strftime("%Y-%m-%d %H:%M")
                logger.info(f"{thread_id} | {created_at} | {query} | {status}")
            return True
        except Exception as e:
            logger.error(f"[MongoDB] Error retrieving sessions: {e}")
            return False