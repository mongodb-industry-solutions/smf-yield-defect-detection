#!/usr/bin/env python3
"""
Script to clean up test/debug equipment entries from time series collection
"""

from pymongo import MongoClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def cleanup_test_equipment():
    """Remove test/debug equipment entries from process_sensor_ts collection"""

    # Connect to MongoDB
    client = MongoClient(os.getenv('MONGODB_URI'))
    db = client['smf-yield-defect']
    sensor_collection = db['process_sensor_ts']

    print(f"Connected to MongoDB database: {db.name}")
    print(f"Cleaning up collection: process_sensor_ts")

    # Define test equipment IDs to remove
    test_equipment_ids = [
        'TEST_CMP_01',
        'DEBUG_TEST_01',
        'DEBUG_TEST_02',
        'DEBUG_TEST_03',
        'RESTART_TEST_01'
    ]

    # Get count before cleanup
    total_before = sensor_collection.count_documents({})
    test_count = sensor_collection.count_documents({
        'equipment_id': {'$in': test_equipment_ids}
    })

    print(f"\nBefore cleanup:")
    print(f"  Total documents: {total_before}")
    print(f"  Test documents to remove: {test_count}")

    if test_count == 0:
        print("\nNo test equipment entries found. Collection is clean!")
        return

    # Show sample of test entries before deletion
    print(f"\nTest equipment entries to be removed:")
    for equip_id in test_equipment_ids:
        count = sensor_collection.count_documents({'equipment_id': equip_id})
        if count > 0:
            print(f"  - {equip_id}: {count} documents")

    # Perform cleanup
    result = sensor_collection.delete_many({
        'equipment_id': {'$in': test_equipment_ids}
    })

    print(f"\nDeleted {result.deleted_count} test equipment documents")

    # Get count after cleanup
    total_after = sensor_collection.count_documents({})

    print(f"\nAfter cleanup:")
    print(f"  Total documents: {total_after}")
    print(f"  Documents removed: {total_before - total_after}")

    # List remaining unique equipment IDs
    pipeline = [
        {'$group': {'_id': '$equipment_id'}},
        {'$sort': {'_id': 1}}
    ]

    remaining_equipment = list(sensor_collection.aggregate(pipeline))

    print(f"\nRemaining real equipment ({len(remaining_equipment)} unique):")
    for eq in remaining_equipment:
        equip_id = eq['_id']
        count = sensor_collection.count_documents({'equipment_id': equip_id})
        latest = sensor_collection.find_one(
            {'equipment_id': equip_id},
            sort=[('timestamp', -1)]
        )
        process = latest.get('process_step', 'UNKNOWN') if latest else 'UNKNOWN'
        print(f"  - {equip_id} ({process}): {count} documents")

    client.close()
    print("\nCleanup complete!")

if __name__ == "__main__":
    cleanup_test_equipment()