from db.mdb import MongoDBConnector

import logging
import datetime

import json
from bson import ObjectId
from pydantic import BaseModel

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi import APIRouter

from config.config_loader import ConfigLoader
from utils import convert_objectids, format_document

from db.mdb import MongoDBConnector

from agent_workflow_graph import create_workflow_graph
from agent_state import AgentState
from agent_checkpointer import AgentCheckpointer

import os
from dotenv import load_dotenv

load_dotenv()

# Load configuration
config = ConfigLoader()
# Get configuration values
# MongoDB URI
MDB_URI = os.getenv("MONGODB_URI")
# Database
MDB_DATABASE_NAME = config.get("MDB_DATABASE_NAME")
# Collections
MDB_HISTORICAL_RECOMMENDATIONS_COLLECTION = config.get("MDB_HISTORICAL_RECOMMENDATIONS_COLLECTION")
MDB_AGENT_SESSIONS_COLLECTION = config.get("MDB_AGENT_SESSIONS_COLLECTION")
MDB_EMBEDDINGS_COLLECTION = config.get("MDB_EMBEDDINGS_COLLECTION")
MDB_EMBEDDINGS_COLLECTION_VS_FIELD = config.get("MDB_EMBEDDINGS_COLLECTION_VS_FIELD")
MDB_TIMESERIES_COLLECTION = config.get("MDB_TIMESERIES_COLLECTION")
MDB_LOGS_COLLECTION = config.get("MDB_LOGS_COLLECTION")
MDB_AGENT_PROFILES_COLLECTION = config.get("MDB_AGENT_PROFILES_COLLECTION")
AGENT_PROFILE_CHOSEN_ID = config.get("AGENT_PROFILE_CHOSEN_ID")
# Checkpointer
MDB_CHECKPOINTER_COLLECTION = config.get("MDB_CHECKPOINTER_COLLECTION")
MDB_CHECKPOINTER_WRITES = MDB_CHECKPOINTER_COLLECTION + "_writes"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter()

@app.get("/")
async def read_root(request: Request):
    return {"message": "Server is running"}


@app.get("/run-agent")
async def run_agent(query_reported: str = Query("Default query reported by the user", description="Query reported text")):
    """Run the agent with the given query.

    Args:
        query_reported (str, optional): _description_. Defaults to Query("Default query reported by the user", description="Query reported text").

    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_
    """
    initial_state: AgentState = {
        "query_reported": query_reported,
        "chain_of_thought": "",
        "timeseries_data": [],
        "embedding_vector": [],
        "historical_recommendations_list": [],
        "recommendation_text": "",
        "next_step": "reasoning_node",
        "updates": [],
        "thread_id": ""
    }
    thread_id = f"thread_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    initial_state["thread_id"] = thread_id
    config = {"configurable": {"thread_id": thread_id}}
    try:
        logger.info(f"Running agent for thread ID: {thread_id}")
        mongodb_saver = AgentCheckpointer(database_name=MDB_DATABASE_NAME, collection_name=MDB_CHECKPOINTER_COLLECTION).create_mongodb_saver()
        if mongodb_saver:
            with mongodb_saver as checkpointer:
                workflow = create_workflow_graph(checkpointer=checkpointer)
                final_state = workflow.invoke(initial_state, config=config)
                final_state = convert_objectids(final_state)
        else:
            workflow = create_workflow_graph()
            final_state = workflow.invoke(initial_state, config=config)
            final_state = convert_objectids(final_state)
        final_state["thread_id"] = thread_id
        
        try:
            with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector: 
                session_metadata = {
                    "thread_id": thread_id,
                    "query_reported": query_reported,
                    "created_at": datetime.datetime.now(datetime.timezone.utc),
                    "status": "completed",
                    "recommendation": final_state["recommendation_text"]
                }
                session_metadata = convert_objectids(session_metadata)
                mdb_connector.insert_one(collection_name=MDB_AGENT_SESSIONS_COLLECTION, document=session_metadata)
                return final_state
        except Exception as e:
            logger.info(f"[MongoDB] Error storing session metadata: {e}")
            return final_state
    except Exception as e:
        logger.info(f"[Error] An error occurred during execution: {e}")
        logger.info(f"You can resume this session later using thread ID: {thread_id}")
        try:
            with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector: 
                session_metadata = {
                    "thread_id": thread_id,
                    "query_reported": query_reported,
                    "created_at": datetime.datetime.now(datetime.timezone.utc),
                    "status": "error",
                    "error_message": str(e)
                }
                session_metadata = convert_objectids(session_metadata)
                mdb_connector.insert_one(collection_name=MDB_AGENT_SESSIONS_COLLECTION, document=session_metadata)
                logger.info("[MongoDB] Error state recorded in session metadata")
        except Exception as db_error:
                logger.info(f"[MongoDB] Error storing session error state: {db_error}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/resume-agent")
async def resume_agent(thread_id: str = Query(..., description="Thread ID to resume session")):
    """Resume the agent with the given thread ID. 
    
    Args:
        thread_id (str, optional): Thread ID to resume session. Defaults to Query(..., description="Thread ID to resume session").

    Raises:
        HTTPException: _description_
    
    Returns:
        session: The session to resume.
    """
    try:
        with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector: 
            mdb_sessions_collection = mdb_connector.get_collection(MDB_AGENT_SESSIONS_COLLECTION)
            logger.info(f"Resuming agent for thread ID: {thread_id}")
            session = mdb_sessions_collection.find_one({"thread_id": thread_id})
        if session:
            session = convert_objectids(session)
            return session
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.get("/get-sessions")
async def get_sessions():
    """Get the last 10 sessions. 
    
    Returns:
        sessions: The last 10 sessions.

    Raises:
        HTTPException
    """
    try:
        with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector:
            mdb_sessions_collection = mdb_connector.get_collection(MDB_AGENT_SESSIONS_COLLECTION)
            sessions = list(mdb_sessions_collection.find().sort("created_at", -1).limit(10))
        sessions = convert_objectids(sessions)
        return sessions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.get("/get-run-documents")
async def get_run_documents(thread_id: str = Query(..., description="Thread ID of the agent run")):
    """Get all documents for a given run. 
    
    Args:
        thread_id (str, optional): Thread ID of the agent run. Defaults to Query(..., description="Thread ID of the agent run").

    Returns:
        docs: The documents for the given run.
    """
    try:
        docs = {}

        # For collections where thread_id is stored with extra characters, use regex to find the right data
        query = {"thread_id": {"$regex": f"^{thread_id}"}}

        # Retrieve documents
        logger.info(f"Retrieving documents for thread ID: {thread_id}")
        with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector:
            mdb_historical_recommendations_collection = mdb_connector.get_collection(MDB_HISTORICAL_RECOMMENDATIONS_COLLECTION)
            mdb_agent_sessions_collection = mdb_connector.get_collection(MDB_AGENT_SESSIONS_COLLECTION)
            mdb_timeseries_collection = mdb_connector.get_collection(MDB_TIMESERIES_COLLECTION)
            mdb_logs_collection = mdb_connector.get_collection(MDB_LOGS_COLLECTION)
            mdb_agent_profiles_collection = mdb_connector.get_collection(MDB_AGENT_PROFILES_COLLECTION)
            mdb_embeddings_collection = mdb_connector.get_collection(MDB_EMBEDDINGS_COLLECTION)
            mdb_checkpoint_collection = mdb_connector.get_collection(MDB_CHECKPOINTER_COLLECTION)
        
            # Retrieve agent_sessions document
            session = mdb_agent_sessions_collection.find_one(query)

            # Retrieve historical_recommendations for the run
            historical = mdb_historical_recommendations_collection.find_one(query)

            # Retrieve 3 timeseries data points
            timeseries = list(mdb_timeseries_collection.find().limit(3))

            # Retrieve logs for the run
            log = mdb_logs_collection.find_one(query)

            # Retrieve the agent profile
            chosen_agent_id = AGENT_PROFILE_CHOSEN_ID or "DEFAULT"
            profile = mdb_agent_profiles_collection.find_one({"agent_id": chosen_agent_id})

            # Retrieve 3 queries from the embeddings collection
            queries = list(mdb_embeddings_collection.find().limit(3))

            # Retrieve the last checkpoint
            last_checkpoint = mdb_checkpoint_collection.find_one(query)
        
        logger.info(f"Formatting documents for thread ID: {thread_id}")
        # Format the documents
        docs["agent_sessions"] = format_document(session) if session else {}
        docs["historical_recommendations"] = format_document(historical) if historical else {}
        docs["agent_profile"] = format_document(profile) if profile else {}
        docs[MDB_TIMESERIES_COLLECTION] = [format_document(record) for record in timeseries] if timeseries else {}
        docs["queries"] = [format_document(record) for record in queries] if queries else {}
        docs["logs"] = format_document(log) if log else {}
        docs["last_checkpoint"] = format_document(last_checkpoint) if last_checkpoint else {}
        logger.info(f"Documents formatted for thread ID: {thread_id}")

        return docs
    except Exception as e:
        logger.error(f"Error while retrieving documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))