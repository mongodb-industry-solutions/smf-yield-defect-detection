#!/usr/bin/env python3
"""
Generate and load sensor data directly into MongoDB process_sensor_ts collection.
Regenerates historical baseline data for Atlas charts.
"""
import sys
import os
from pathlib import Path

# Add parent directory to path to import generate_sensor_data
sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv
from data_generation.generate_sensor_data import generate_sensor_data

# Load environment variables
load_dotenv()

def load_sensor_data_to_mongodb(days: int = 30):
    """
    Generate sensor data and load directly into MongoDB.

    Args:
        days: Number of days of historical data to generate
    """
    # Get MongoDB connection details
    mongodb_uri = os.getenv("MONGODB_URI")
    database_name = os.getenv("DATABASE_NAME", "smf-yield-defect")

    if not mongodb_uri:
        raise ValueError("MONGODB_URI environment variable not set")

    print(f"🔧 Connecting to MongoDB ({database_name})...")
    app_name = os.getenv("APP_NAME", "devrel-demo-vectorsearch-langgraph-semiconductor")
    client = MongoClient(mongodb_uri, appname=app_name)
    db = client[database_name]
    collection = db["process_sensor_ts"]

    print(f"📊 Generating {days} days of sensor data...")
    sensor_data, anomalies = generate_sensor_data(days=days)

    print(f"✅ Generated {len(sensor_data)} sensor records")
    print(f"✅ Found {len(anomalies)} anomaly events")

    # Clear existing data (optional - comment out if you want to preserve existing data)
    print("\n⚠️  Clearing existing sensor data...")
    delete_result = collection.delete_many({})
    print(f"   Deleted {delete_result.deleted_count} existing records")

    # Insert new data in batches
    batch_size = 1000
    total_inserted = 0

    print(f"\n📥 Inserting data into MongoDB (batch size: {batch_size})...")

    for i in range(0, len(sensor_data), batch_size):
        batch = sensor_data[i:i + batch_size]

        # Convert datetime objects to UTC timezone-aware
        for record in batch:
            if isinstance(record['timestamp'], datetime) and record['timestamp'].tzinfo is None:
                record['timestamp'] = record['timestamp'].replace(tzinfo=timezone.utc)

        try:
            result = collection.insert_many(batch, ordered=False)
            total_inserted += len(result.inserted_ids)

            # Progress indicator
            progress = (total_inserted / len(sensor_data)) * 100
            print(f"   Progress: {total_inserted}/{len(sensor_data)} ({progress:.1f}%)")

        except Exception as e:
            print(f"   ⚠️  Batch insert error: {e}")
            # Continue with next batch

    print(f"\n✅ Successfully inserted {total_inserted} sensor records")

    # Verify data
    count = collection.count_documents({})
    print(f"✅ Verified: {count} documents in process_sensor_ts collection")

    # Show date range
    oldest = collection.find_one(sort=[("timestamp", 1)])
    newest = collection.find_one(sort=[("timestamp", -1)])

    if oldest and newest:
        print(f"\n📅 Data Range:")
        print(f"   Oldest: {oldest['timestamp']}")
        print(f"   Newest: {newest['timestamp']}")

    # Show equipment breakdown
    print(f"\n🔧 Equipment Breakdown:")
    pipeline = [
        {"$group": {"_id": "$equipment_id", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    for result in collection.aggregate(pipeline):
        print(f"   {result['_id']}: {result['count']} records")

    # Show anomaly count
    anomaly_count = collection.count_documents({"metadata.anomaly_flag": True})
    print(f"\n⚠️  Anomaly Records: {anomaly_count}")

    client.close()
    print("\n🎉 Data loading complete!")
    print(f"\n💡 Your Atlas charts should now have {days} days of historical data")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Load sensor data into MongoDB")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days of historical data to generate (default: 30)"
    )
    parser.add_argument(
        "--preserve",
        action="store_true",
        help="Preserve existing data (don't clear collection before inserting)"
    )

    args = parser.parse_args()

    if args.preserve:
        print("⚠️  Running in PRESERVE mode - existing data will NOT be deleted")
        # Comment out the delete_many line in the function

    try:
        load_sensor_data_to_mongodb(days=args.days)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
