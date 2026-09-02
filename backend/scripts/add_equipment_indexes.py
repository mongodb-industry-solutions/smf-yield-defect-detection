#!/usr/bin/env python3
"""
Add indexes to improve equipment status query performance
"""

from pymongo import MongoClient, DESCENDING
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def add_performance_indexes():
    """Add indexes for equipment status queries"""

    # Connect to MongoDB
    client = MongoClient(os.getenv('MONGODB_URI'), appname=os.getenv('APP_NAME', 'devrel-fastapi-smf-yield-defect-detection'))
    db = client['smf-yield-defect']
    sensor_collection = db['process_sensor_ts']

    print(f"Connected to MongoDB database: {db.name}")
    print(f"Adding indexes to: process_sensor_ts\n")

    # Create compound index for equipment status query
    # This index will dramatically speed up the aggregation pipeline
    indexes_to_create = [
        # Compound index for the $match and $sort stages
        {
            'name': 'timestamp_equipment_idx',
            'keys': [('timestamp', DESCENDING), ('equipment_id', 1)],
            'description': 'For equipment status queries'
        },
        # Single field index for equipment grouping
        {
            'name': 'equipment_id_idx',
            'keys': [('equipment_id', 1)],
            'description': 'For equipment grouping'
        }
    ]

    for idx in indexes_to_create:
        try:
            result = sensor_collection.create_index(
                idx['keys'],
                name=idx['name']
            )
            print(f"✅ Created index: {idx['name']}")
            print(f"   Description: {idx['description']}")
        except Exception as e:
            if 'already exists' in str(e):
                print(f"ℹ️  Index {idx['name']} already exists")
            else:
                print(f"❌ Error creating index {idx['name']}: {e}")

    # List all indexes
    print("\n📊 All indexes on process_sensor_ts:")
    for idx in sensor_collection.list_indexes():
        print(f"   - {idx['name']}: {idx.get('key', {})}")

    client.close()
    print("\n✅ Index optimization complete!")

if __name__ == "__main__":
    add_performance_indexes()