import logging
from pymongo.errors import DuplicateKeyError

from db.mdb import MongoDBConnector
from config.config_loader import ConfigLoader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class AgentProfiles(MongoDBConnector):
    def __init__(self, collection_name: str=None, uri: str = None, database_name: str = None, appname: str = None):
        """
        AgentProfiles class to retrieve agent profiles from MongoDB.

        Args:
            collection_name (str, optional): Collection name. Default is None and will be retrieved from the config: MDB_AGENT_PROFILES_COLLECTION.
            uri (str, optional): MongoDB URI. Default parent class value.
            database_name (str, optional): Database name. Default parent class value.
            appname (str, optional): Application name. Default parent class value.
        """
        super().__init__(uri, database_name, appname)
        # Load configuration
        config = ConfigLoader()
        # Get the MongoDB agent profiles collection name from the config
        MDB_AGENT_PROFILES_COLLECTION = config.get("MDB_AGENT_PROFILES_COLLECTION")
        self.collection_name = collection_name or MDB_AGENT_PROFILES_COLLECTION
        self.collection = self.get_collection(self.collection_name)
        # Ensure unique index on agent_id
        self.collection.create_index("agent_id", unique=True)
        logger.info(f"AgentProfiles initialized - Retrieving agent profiles from collection: {self.collection_name}")

    def get_agent_profile(self, agent_id: str, update_default: bool = False) -> dict:
        """Retrieve the agent profile for the given agent ID.
        If the agent ID is not found, return a default profile.

        Args:
            agent_id (str): Agent ID to retrieve the profile for.
            update_default (bool): Whether to update the default profile if it already exists. Default is False.

        Returns:
            dict: Agent profile for the given agent ID.
        """
        # Load configuration
        config = ConfigLoader()
        # Load Default Agent Profile from config
        default_profile = config.get("DEFAULT_AGENT_PROFILE")

        try:
            # Retrieve the agent profile from MongoDB
            profile = self.collection.find_one({"agent_id": agent_id})
            if profile:
                logger.info(f"Agent profile found for agent ID: {agent_id}")
                # Return the agent profile if found
                return profile
            else:
                # Check if the default profile already exists
                existing_default_profile = self.collection.find_one({"agent_id": "DEFAULT"})
                if existing_default_profile:
                    if update_default:
                        # Update the existing default profile
                        self.collection.update_one(
                            {"agent_id": "DEFAULT"},
                            {"$set": default_profile}
                        )
                        logger.info("Default profile updated.")
                        return default_profile
                    else:
                        logger.info("Default profile already exists. Skipping insertion.")
                        return existing_default_profile
                else:
                    # Insert the default profile into MongoDB
                    self.collection.insert_one(default_profile)
                    logger.info("Default profile inserted.")
                    # Return the default profile
                    return default_profile
        except DuplicateKeyError:
            logger.error("Duplicate agent_id found. Ensure agent_id is unique.")
            return default_profile
        except Exception as e:
            logger.error(f"Error retrieving agent profile: {e}")
            logger.warning("Returning default agent profile.")
            # Return the default profile if an error occurs
            return default_profile


# ==================
# Example usage
# ==================

if __name__ == "__main__":

    # Example usage
    profiler = AgentProfiles()
    p = profiler.get_agent_profile("MANUFACTORING_AG01")
    print(p)