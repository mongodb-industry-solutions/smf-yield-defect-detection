from db.mdb import MongoDBConnector

import datetime
import logging

from config.config_loader import ConfigLoader
from config.prompts import get_chain_of_thoughts_prompt, get_llm_recommendation_prompt
from utils import convert_objectids
from bedrock.anthropic_chat_completions import BedrockAnthropicChatCompletions

from loader import CSVLoader
import csv

from agent_state import AgentState
from embedder import Embedder
from agent_profiles import AgentProfiles
from mdb_timeseries_coll_creator import TimeSeriesCollectionCreator
from mdb_vector_search_idx_creator import VectorSearchIDXCreator

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class AgentTools(MongoDBConnector):
    def __init__(self, collection_name: str=None, uri=None, database_name: str=None, appname: str=None):
        """
        AgentTools class to perform various actions for the agent.

        Args:
            collection_name (str): Collection name. Default is None.
            uri (str, optional): MongoDB URI. Default parent class value.
            database_name (str, optional): Database name. Default parent class value.
            appname (str, optional): Application name. Default parent class value.
        """
        super().__init__(uri, database_name, appname)

        # Load configuration
        config = ConfigLoader()
        self.config = config

        # Get configuration values
        self.csv_data = self.config.get("CSV_DATA")
        self.mdb_timeseries_collection = self.config.get("MDB_TIMESERIES_COLLECTION")
        self.mdb_timeseries_timefield = self.config.get("MDB_TIMESERIES_TIMEFIELD")
        self.mdb_timeseries_granularity = self.config.get("MDB_TIMESERIES_GRANULARITY")
        self.default_timeseries_data = self.config.get("DEFAULT_TIMESERIES_DATA")
        self.critical_conditions_config = self.config.get("CRITICAL_CONDITIONS")
        self.mdb_embeddings_collection = self.config.get("MDB_EMBEDDINGS_COLLECTION")
        self.mdb_embeddings_collection_vs_field = self.config.get("MDB_EMBEDDINGS_COLLECTION_VS_FIELD")
        self.mdb_vs_index = self.config.get("MDB_VS_INDEX")
        self.default_similar_queries = self.config.get("DEFAULT_SIMILAR_QUERIES")
        self.mdb_agent_profiles_collection = self.config.get("MDB_AGENT_PROFILES_COLLECTION")
        self.agent_profile_chosen_id = self.config.get("AGENT_PROFILE_CHOSEN_ID")
        self.embeddings_model_id = self.config.get("EMBEDDINGS_MODEL_ID")
        self.embeddings_model_name = self.config.get("EMBEDDINGS_MODEL_NAME")
        self.chatcompletions_model_id = self.config.get("CHATCOMPLETIONS_MODEL_ID")
        self.chatcompletions_model_name = self.config.get("CHATCOMPLETIONS_MODEL_NAME")
        self.mdb_historical_recommendations_collection = self.config.get("MDB_HISTORICAL_RECOMMENDATIONS_COLLECTION")

        if collection_name:
            # Set the collection name
            self.collection_name = collection_name
            self.collection = self.get_collection(self.collection_name)

    def get_data_from_csv(self, state: dict) -> dict:
        """
        Reads data from a CSV file and dynamically infers field names.
        """
        message = "[Tool] Retrieved data from CSV file."
        logger.info(message)

        # Load CSV data
        csv_loader = CSVLoader(filepath=self.csv_data, collection_name=self.mdb_timeseries_collection)
        csv_filepath = csv_loader.filepath

        data_records = []
        with open(csv_filepath, "r") as file:
            reader = csv.DictReader(file)  # Automatically infers field names from the header row
            for row in reader:
                data_records.append(row)

        state.setdefault("updates", []).append(message)
        return {"timeseries_data": data_records, "thread_id": state.get("thread_id", "")}

    def get_data_from_mdb(self, state: dict) -> dict:
        """
        Reads data from a MongoDB collection and dynamically infers field names.
        """
        message = "[Tool] Retrieved data from MongoDB collection."
        logger.info(message)

        data_records = []
        for record in self.collection.find():
            # Convert MongoDB ObjectIds to strings
            record = convert_objectids(record)
            data_records.append(record)

        state.setdefault("updates", []).append(message)
        return {"timeseries_data": data_records, "thread_id": state.get("thread_id", "")}
    
    def evaluate_critical_conditions(self, timeseries_data) -> list:
        """
        Evaluate critical conditions dynamically based on configuration.

        Args:
            timeseries_data (list): A list of time-series records.

        Returns:
            list: A list of critical condition messages.
        """
        critical_conditions = []
        for record in timeseries_data:
            for key, condition in self.critical_conditions_config.items():
                try:
                    value = float(record.get(key, 0))
                    threshold = condition["threshold"]
                    condition_operator = condition["condition"]
                    if (
                        (condition_operator == ">" and value > threshold) or
                        (condition_operator == "<" and value < threshold)
                    ):
                        critical_conditions.append(condition["message"].format(value=value))
                except (ValueError, KeyError) as e:
                    logger.error(f"[Warning] Error parsing values for {key}: {e}")
        return critical_conditions

    def vector_search(self, state: dict) -> dict:
        """Performs a vector search in a MongoDB collection."""
        message = "[Tool] Performing MongoDB Atlas Vector Search"
        logger.info(message)

        # Set default update message
        state.setdefault("updates", []).append(message)
        # Get embedding key
        if state.get("embedding_key"):
            embedding_key = state["embedding_key"]
        elif self.collection_name:
            embedding_key = self.mdb_embeddings_collection_vs_field
        else:
            # Default embedding key
            embedding_key = "embedding"

        logger.info(f"Embedding key: {embedding_key}")
        # Get the embedding vector from the state
        embedding = state.get("embedding_vector", [])

        try:
            logger.info("Checking Vector Search Index...")
            # Instantiate the VectorSearchIDXCreator class
            vector_index_creator = VectorSearchIDXCreator()
            vector_index_creator_result = vector_index_creator.create_index()
            logger.info(vector_index_creator_result)
        except Exception as e:
            logger.error(f"[MongoDB] Error checking vector search index: {e}")
            state.setdefault("updates", []).append("[MongoDB] Error checking vector search.")

        try:
            # Perform vector search
            if self.collection is not None:
                pipeline = [
                    {
                        "$vectorSearch": {
                            "index": self.mdb_vs_index,
                            "path": embedding_key,
                            "queryVector": embedding,
                            "numCandidates": 5,
                            "limit": 2
                        }
                    }
                ]
                # Execute the aggregation pipeline
                results = list(self.collection.aggregate(pipeline))
                # Format the results
                for result in results:
                    if "_id" in result:
                        # result["_id"] = str(result["_id"])
                        # It's not necessary to process the _id field, so removing it!
                        del result["_id"]
                    if self.mdb_embeddings_collection_vs_field in result:
                        # Removing the embedding field from the results
                        del result[self.mdb_embeddings_collection_vs_field]
            else:
                logger.info("[MongoDB] No collection set for vector search.")
                logger.info("Setting default similar queries.")
                similar_queries = self.default_similar_queries
                state.setdefault("updates", []).append("[MongoDB] No collection set for vector search. Using default similar queries.")
            if results:
                logger.info(f"[MongoDB] Retrieved similar data from vector search.")
                state.setdefault("updates", []).append("[MongoDB] Retrieved similar data.")
                similar_queries = results
                logger.info(f"Similar queries - Vector Search results: {similar_queries}")
            else:
                logger.info(f"[MongoDB] No similar data found. Returning default message.")
                state.setdefault("updates", []).append("[MongoDB] No similar data found.")
                similar_queries = [{"query": "No similar queries found", "recommendation": "No immediate action based on past data."}]
        except Exception as e:
            logger.error(f"Error during MongoDB Vector Search operation: {e}")
            state.setdefault("updates", []).append("[MongoDB] Error during Vector Search operation.")
            similar_queries = [{"query": "MongoDB Vector Search operation error", "recommendation": "Please try again later."}]

        return {"historical_recommendations_list": similar_queries}

    def generate_chain_of_thought(self, state: AgentState) -> AgentState:
        """Generates the chain of thought for the agent."""
        logger.info("[LLM Chain-of-Thought Reasoning]")
        # Instantiate the AgentProfiles class
        profiler = AgentProfiles(collection_name=self.mdb_agent_profiles_collection)
        # Get the agent profile
        p = profiler.get_agent_profile(agent_id=self.agent_profile_chosen_id)
        # Get the Query Reported from the state
        query_reported = state["query_reported"]

        CHAIN_OF_THOUGHTS_PROMPT = get_chain_of_thoughts_prompt(
            agent_profile=p["profile"],
            agent_rules=p["rules"],
            agent_instructions=p["instructions"],
            agent_goals=p["goals"],
            query_reported=query_reported,
            agent_motive=p["goals"],
            agent_kind_of_data=p["kind_of_data"],
            embedding_model_name=self.embeddings_model_name,
            chat_completion_model_name=self.chatcompletions_model_name
        )
        logger.info("Chain-of-Thought Reasoning Prompt:")
        logger.info(CHAIN_OF_THOUGHTS_PROMPT)

        try:
            # Instantiate the chat completion model
            chat_completions = BedrockAnthropicChatCompletions(model_id=self.chatcompletions_model_id)
            # Generate a chain of thought based on the prompt
            chain_of_thought = chat_completions.predict(CHAIN_OF_THOUGHTS_PROMPT)
        except Exception as e:
            logger.error(f"Error generating chain of thought: {e}")
            chain_of_thought = (
                "1. Consume data.\n"
                "2. Generate an embedding for the query.\n"
                "3. Perform a vector search on past recommendations.\n"
                "4. Persist data into MongoDB.\n"
                "5. Generate a final summary and recommendation."
            )

        logger.info("Chain-of-Thought Reasoning:")
        logger.info(chain_of_thought)
        state.setdefault("updates", []).append("Chain-of-thought generated.")
        return {**state, "chain_of_thought": chain_of_thought, "next_step": "get_data_from_csv_tool"}
    
    @staticmethod
    def process_data(state: AgentState) -> AgentState:
        """Processes the data."""
        state.setdefault("updates", []).append("Data processed.")
        state["next_step"] = "embedding_node"
        return state

    def get_query_embedding(self, state: AgentState) -> AgentState:
        """Generates the query embedding."""
        logger.info("[Action] Generating Query Embedding...")
        state.setdefault("updates", []).append("Generating query embedding...")

        # Get the query text
        text = state["query_reported"]

        try: 
            # Instantiate the Embedder
            embedder = Embedder(collection_name=self.mdb_embeddings_collection)
            embedding = embedder.get_embedding(text)
            state.setdefault("updates", []).append("Query embedding generated!")
            logger.info("Query embedding generated!")
        except Exception as e:
            logger.error(f"Error generating query embedding: {e}")
            state.setdefault("updates", []).append("Error generating query embedding; using dummy vector.")
            embedding = [0.0] * 1024
        return {**state, "embedding_vector": embedding, "next_step": "vector_search_tool"}
    
    @staticmethod
    def process_vector_search(state: AgentState) -> AgentState:
        """Processes the vector search results."""
        state.setdefault("updates", []).append("Vector search results processed.")
        state["next_step"] = "persistence_node"
        return state
    
    def persist_data(self, state: AgentState) -> AgentState:
        """
        Persists the data into MongoDB.
        """
        state.setdefault("updates", []).append("Persisting data to MongoDB...")
        logger.info("[Action] Persisting data to MongoDB...")

        try:
            # Instantiate the TimeSeriesCollectionCreator class
            logger.info("Checking Time Series Collection...")
            ts_coll_result = TimeSeriesCollectionCreator().create_timeseries_collection(
                    collection_name=self.mdb_timeseries_collection,
                    time_field=self.mdb_timeseries_timefield,
                    granularity=self.mdb_timeseries_granularity
            )
            logger.info(ts_coll_result)
            # Get the MongoDB collection
            timeseries_collection_name = self.mdb_timeseries_collection
            timeseries_collection = self.get_collection(self.mdb_timeseries_collection)
        except Exception as e:
            logger.error(f"Error creating time series collection: {e}")
            state.setdefault("updates", []).append("Error creating time series collection.")

        if timeseries_collection is not None:
            combined_data = {
                "query_reported": state["query_reported"],
                "timeseries": state["timeseries_data"],
                "similar_queries": state["historical_recommendations_list"],
                "thread_id": state.get("thread_id", "")
            }
            try:
                # Persist each record in the time-series data
                for record in combined_data["timeseries"]:
                    try:
                        # Parse timestamp and convert values dynamically
                        record["timestamp"] = datetime.datetime.strptime(record["timestamp"], "%Y-%m-%dT%H:%M:%SZ")
                        for key in record:
                            if key != "timestamp" and key != "thread_id":
                                record[key] = float(record[key])
                    except Exception as e:
                        logger.error(f"Error processing record: {e}")
                    record["thread_id"] = state.get("thread_id", "")
                    record = convert_objectids(record)
                    # TODO: REMOVE THIS LOGGER STATEMENT
                    logger.info(f"Persisting record: {record}")
                    timeseries_collection.insert_one(record)

                logger.info(f"[MongoDB] Data persisted in {timeseries_collection_name} collection.")

                # Persist logs
                coll_logs = self.db["logs"]
                log_entry = {
                    "thread_id": state.get("thread_id", ""),
                    "query_reported": combined_data["query_reported"],
                    "similar_queries": combined_data["similar_queries"],
                    "created_at": datetime.datetime.now(datetime.timezone.utc)
                }
                log_entry = convert_objectids(log_entry)
                coll_logs.insert_one(log_entry)
                state.setdefault("updates", []).append("Data persisted to MongoDB.")
            except Exception as e:
                logger.error(f"Error persisting data to MongoDB: {e}")
                state.setdefault("updates", []).append("Error persisting data to MongoDB.")
        else:
            state.setdefault("updates", []).append("No MongoDB collection set for persistence.")
            logger.info("No MongoDB collection set for persistence.")

        return {**state, "next_step": "recommendation_node"}
        
    def get_llm_recommendation(self, state: AgentState) -> AgentState:
        """Generates the LLM recommendation."""
        state.setdefault("updates", []).append("Generating final recommendation...")
        logger.info("[Final Answer] Generating final recommendation...")
        
        # Use default timeseries data if none is provided
        timeseries_data = state.get("timeseries_data", [])
        if not timeseries_data:
            state.setdefault("updates", []).append("No timeseries data; using default values.")
            logger.warning("[Warning] No timeseries data available. Using default values.")
            timeseries_data = self.default_timeseries_data

        # Evaluate critical conditions
        critical_conditions = self.evaluate_critical_conditions(timeseries_data)
        critical_info = "CRITICAL ALERT: " + ", ".join(critical_conditions) + "\n\n" if critical_conditions else ""

        # Instantiate the AgentProfiles class
        profiler = AgentProfiles(collection_name=self.mdb_agent_profiles_collection)
        # Get the agent profile
        p = profiler.get_agent_profile(agent_id=self.agent_profile_chosen_id)

        # Generate the LLM recommendation prompt
        LLM_RECOMMENDATION_PROMPT = get_llm_recommendation_prompt(
            agent_role=p["role"],
            agent_kind_of_data=p["kind_of_data"],
            critical_info=critical_info,
            timeseries_data=timeseries_data,
            historical_recommendations_list=state.get("historical_recommendations_list", [])
        )
        logger.info("LLM Recommendation Prompt:")
        logger.info(LLM_RECOMMENDATION_PROMPT)

        try:
            # Instantiate the chat completion model
            chat_completions = BedrockAnthropicChatCompletions(model_id=self.chatcompletions_model_id)
            # Generate a chain of thought based on the prompt
            llm_recommendation = chat_completions.predict(LLM_RECOMMENDATION_PROMPT)
        except Exception as e:
            logger.error(f"Error generating LLM recommendation: {e}")
            llm_recommendation = "Unable to generate recommendation at this time."

        logger.info("LLM Recommendation:")
        logger.info(llm_recommendation)
        state.setdefault("updates", []).append("Final recommendation generated.")

        try:
            recommendation_record = {
                "thread_id": state.get("thread_id", ""),
                "timestamp": datetime.datetime.now(datetime.timezone.utc),
                "query_reported": state["query_reported"],
                "timeseries_data": timeseries_data,
                "historical_recommendations": state.get("historical_recommendations_list", []),
                "recommendation": llm_recommendation
            }
            recommendation_record = convert_objectids(recommendation_record)
            self.collection.insert_one(recommendation_record)
            state.setdefault("updates", []).append("Recommendation stored in MongoDB.")
            logger.info("[MongoDB] Recommendation stored in historical records")
        except Exception as e:
            logger.error(f"Error storing recommendation in MongoDB: {e}")
            state.setdefault("updates", []).append("Error storing recommendation in MongoDB.")

        return {**state, "recommendation_text": llm_recommendation, "next_step": "end"}



# Define tools
def get_data_from_csv_tool(state: dict) -> dict:
    "Reads data from a CSV file."
    agent_tools = AgentTools()
    return agent_tools.get_data_from_csv(state=state)

def get_data_from_mdb_tool(state: dict) -> dict:
    "Reads data from a MongoDB collection."
    # Load configuration
    config = ConfigLoader()
    # Get the MongoDB collection name
    mdb_timeseries_collection = config.get("MDB_TIMESERIES_COLLECTION")
    # Instantiate the AgentTools class
    agent_tools = AgentTools(collection_name=mdb_timeseries_collection)
    return agent_tools.get_data_from_mdb(state)

def vector_search_tool(state: dict) -> dict:
    """Performs a vector search in a MongoDB collection."""
    # Load configuration
    config = ConfigLoader()
    # Get the MongoDB collection name
    mdb_embeddings_collection = config.get("MDB_EMBEDDINGS_COLLECTION")
    # Instantiate the AgentTools class
    agent_tools = AgentTools(collection_name=mdb_embeddings_collection)
    return agent_tools.vector_search(state=state)

def generate_chain_of_thought_tool(state: AgentState) -> AgentState:
    """Generates the chain of thought for the agent."""
    agent_tools = AgentTools()
    return agent_tools.generate_chain_of_thought(state=state)

def process_data_tool(state: AgentState) -> AgentState:
    """Processes the data."""
    agent_tools = AgentTools()
    return agent_tools.process_data(state=state)

def get_query_embedding_tool(state: AgentState) -> AgentState:
    """Generates the query embedding."""
    agent_tools = AgentTools()
    return agent_tools.get_query_embedding(state=state)

def process_vector_search_tool(state: AgentState) -> AgentState:
    """Processes the vector search results."""
    agent_tools = AgentTools()
    return agent_tools.process_vector_search(state=state)

def persist_data_tool(state: AgentState) -> AgentState:
    """Persists the data into MongoDB."""
    # Instantiate the AgentTools class
    agent_tools = AgentTools()
    return agent_tools.persist_data(state=state)

def get_llm_recommendation_tool(state: AgentState) -> AgentState:
    """Generates the LLM recommendation."""
    # Load configuration
    config = ConfigLoader()
    # Get the MongoDB collection name
    mdb_historical_recommendations_collection = config.get("MDB_HISTORICAL_RECOMMENDATIONS_COLLECTION")
    # Instantiate the AgentTools class
    agent_tools = AgentTools(collection_name=mdb_historical_recommendations_collection)
    return agent_tools.get_llm_recommendation(state=state)
