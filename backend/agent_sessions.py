import logging

from langgraph.checkpoint.mongodb import MongoDBSaver
from db.mdb import MongoDBConnector
from config.config_loader import ConfigLoader
from bson import ObjectId

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
        self.sessions_collection = self.get_collection(self.collection_name)
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


class AgentSessionManager(AgentSessions):
    """Manager class for agent sessions with async support"""
    
    def __init__(self, *args, **kwargs):
        """Initialize with async MongoDB client"""
        super().__init__(*args, **kwargs)
        # Import Motor for async operations
        from motor.motor_asyncio import AsyncIOMotorClient
        import os
        
        # Create async client and collection
        mongodb_uri = self.uri or os.getenv("MONGODB_URI")
        self.async_client = AsyncIOMotorClient(mongodb_uri)
        self.async_db = self.async_client[self.database_name]
        self.async_sessions_collection = self.async_db[self.collection_name]
    
    async def create_session(self, user_id: str, query: str, metadata: dict = None):
        """Create a new agent session"""
        session_id = str(ObjectId())
        session_doc = {
            "_id": ObjectId(session_id),
            "session_id": session_id,
            "user_id": user_id,
            "query": query,
            "query_reported": query,
            "metadata": metadata or {},
            "status": "created",
            "created_at": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow(),
            "checkpoints": [],
            "updates": []
        }
        
        await self.async_sessions_collection.insert_one(session_doc)
        logger.info(f"Created session {session_id}")
        return session_id
    
    async def get_session(self, session_id: str):
        """Get a session by ID"""
        try:
            session = await self.async_sessions_collection.find_one(
                {"session_id": session_id}
            )
            if session:
                session["_id"] = str(session["_id"])
            return session
        except Exception as e:
            logger.error(f"Error getting session {session_id}: {e}")
            return None
    
    async def update_session(self, session_id: str, update_data: dict):
        """Update a session"""
        try:
            update_data["updated_at"] = datetime.datetime.utcnow()
            result = await self.async_sessions_collection.update_one(
                {"session_id": session_id},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating session {session_id}: {e}")
            return False
    
    async def list_sessions(self, limit: int = 20, status: str = None):
        """List sessions with optional filtering"""
        try:
            query = {}
            if status:
                query["status"] = status
            
            cursor = self.async_sessions_collection.find(query).sort(
                "created_at", -1
            ).limit(limit)
            
            sessions = []
            async for session in cursor:
                session["_id"] = str(session["_id"])
                sessions.append(session)
            
            return sessions
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            return []