import os
import pandas as pd
import logging
from db.mdb import MongoDBConnector
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class CSVLoader(MongoDBConnector):
    """
    Class to handle loading CSV files into Pandas DataFrames with error handling.
    """
    def __init__(self, filepath: str, collection_name: str, delimiter: str = ',', encoding: str = 'utf-8',
                 uri=None, database_name: str = None, appname: str = None):
        """
        Initialize the CSVLoader with a relative file path and optional delimiter and encoding.
        The filepath will be resolved relative to the script's directory.

        Args:
            filepath (str): Relative path to the CSV file.
            collection_name (str): Collection name.
            delimiter (str, optional): Delimiter for the CSV file. Defaults to ",".
            encoding (str, optional): Encoding for the CSV file. Defaults to "utf-8".
            uri (str, optional): MongoDB URI. Defaults to None.
            database_name (str, optional): Database name. Defaults to None.
            appname (str, optional): Application name. Defaults to None.
        """
        super().__init__(uri, database_name, appname)
        relative_path = filepath
        self.collection_name = collection_name
        self.collection = self.get_collection(self.collection_name)

        # Get the directory of the current script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Always treat the provided filepath as relative and join with the script's directory
        self.filepath = os.path.join(script_dir, relative_path)
        
        # Check if the file exists at the resolved path
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"File not found: {self.filepath}")
        
        self.delimiter = delimiter
        self.encoding = encoding

    def load(self) -> pd.DataFrame:
        """
        Load the CSV file into a Pandas DataFrame.
        :return: Pandas DataFrame
        """
        try:
            df = pd.read_csv(self.filepath, delimiter=self.delimiter, encoding=self.encoding)
            logger.info(f"Successfully loaded CSV file: {self.filepath}")
            return df
        except FileNotFoundError:
            logger.error(f"File not found: {self.filepath}")
            raise
        except pd.errors.ParserError:
            logger.error(f"Parsing error occurred while reading file: {self.filepath}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while loading file: {self.filepath} - {e}")
            raise

    def store(self, df: pd.DataFrame, overwrite: bool=True) -> dict:
        """
        Store the Pandas DataFrame into MongoDB. The DataFrame is converted to a list of dictionaries
        and inserted into the MongoDB collection. If overwrite is True, existing records will be replaced.

        Args:
            :param df: Pandas DataFrame to store
            :param overwrite: Boolean to overwrite existing records. Defaults to True.

        Returns:
            :return: Dictionary with status and message
        """
        try:
            # Convert the DataFrame to a list of dictionaries
            records = df.to_dict(orient="records")
            
            # Convert 'timestamp' field to BSON UTC datetime if it exists
            for record in records:
                if 'timestamp' in record:
                    record['timestamp'] = datetime.strptime(record['timestamp'], "%Y-%m-%dT%H:%M:%SZ")

            # Check if the collection should be overwritten
            if overwrite:
                # Drop all records in the collection
                self.collection.delete_many({})
                logger.info(f"Deleted all records in MongoDB collection: {self.collection_name}")
            
            # Insert the records into the MongoDB collection
            result = self.collection.insert_many(records)
            logger.info(f"Successfully stored DataFrame to MongoDB collection: {self.collection_name}")
            return {"status": "success", "message": f"Inserted {len(result.inserted_ids)} records"}
        except Exception as e:
            logger.error(f"Error storing DataFrame to MongoDB collection: {self.collection_name} - {e}")
            raise