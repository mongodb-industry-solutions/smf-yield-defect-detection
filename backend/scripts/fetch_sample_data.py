"""
Script to fetch sample documents from MongoDB collections and save them as JSON files.
This allows the frontend to load data instantly without API calls.
"""
import json
import os
from pathlib import Path
from db.mdb import MongoDBConnector
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MDB_URI = os.getenv("MONGODB_URI")
MDB_DATABASE_NAME = os.getenv("MDB_DATABASE_NAME", "smf_yield_defect_detection")

# Collections to fetch
COLLECTIONS = {
    'historical_knowledge': 'latest',  # Get latest document
    'wafer_defects': 'oldest',  # Get oldest document
    'alerts': 'latest',  # Get latest document
    'process_context': 'latest',  # Get latest document
    'process_sensor_ts': 'latest'  # Get latest document
}

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent / "frontend" / "data" / "sample_collections"

def fetch_and_save_samples():
    """Fetch sample documents and save them as JSON files."""

    # Create output directory if it doesn't exist
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Fetching sample documents from MongoDB...")
    print(f"Database: {MDB_DATABASE_NAME}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("-" * 60)

    with MongoDBConnector(uri=MDB_URI, database_name=MDB_DATABASE_NAME) as mdb_connector:
        for collection_name, fetch_type in COLLECTIONS.items():
            try:
                collection = mdb_connector.db[collection_name]

                # Fetch document based on type
                if fetch_type == 'latest':
                    # Get newest document (sort by _id descending)
                    document = collection.find_one(sort=[("_id", -1)])
                else:  # oldest
                    # Get oldest document (sort by _id ascending)
                    document = collection.find_one(sort=[("_id", 1)])

                if document:
                    # Convert ObjectId to string for JSON serialization
                    if '_id' in document:
                        document['_id'] = str(document['_id'])

                    # Save to JSON file
                    output_file = OUTPUT_DIR / f"{collection_name}.json"
                    with open(output_file, 'w') as f:
                        json.dump(document, f, indent=2, default=str)

                    print(f"✓ {collection_name}: Saved {fetch_type} document to {output_file.name}")
                else:
                    print(f"✗ {collection_name}: No documents found")

            except Exception as e:
                print(f"✗ {collection_name}: Error - {str(e)}")

    print("-" * 60)
    print(f"Sample documents saved to: {OUTPUT_DIR}")

if __name__ == "__main__":
    fetch_and_save_samples()
