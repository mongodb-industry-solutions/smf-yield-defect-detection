#!/usr/bin/env python3
"""
Seed MongoDB with pre-defined failure scenarios for time series analysis demonstration.

This script loads scenario data into the scenario_time_series and scenario_metadata collections.
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()


async def seed_scenarios():
    """Load scenario data into MongoDB."""
    
    print("=" * 60)
    print("Seeding MongoDB with Scenario Data")
    print("=" * 60)
    
    # Connect to MongoDB
    mongodb_uri = os.getenv("MONGODB_URI")
    database_name = os.getenv("MDB_DATABASE_NAME", "smf-yield-defect")
    
    if not mongodb_uri:
        print("❌ Error: MONGODB_URI not set in environment")
        return
    
    print(f"\n🔗 Connecting to MongoDB...")
    print(f"   Database: {database_name}")
    
    client = AsyncIOMotorClient(mongodb_uri)
    db = client[database_name]
    
    try:
        # Test connection
        await client.admin.command('ping')
        print("✅ Connected to MongoDB")
        
        # Load scenario data files
        data_dir = Path(__file__).parent.parent / "data_generation"
        
        scenario_file = data_dir / "scenario_time_series.json"
        metadata_file = data_dir / "scenario_metadata.json"
        
        if not scenario_file.exists():
            print(f"\n❌ Error: {scenario_file} not found")
            print("   Run: uv run python data_generation/generate_scenarios.py")
            return
        
        print(f"\n📂 Loading scenario data from {scenario_file.name}...")
        with open(scenario_file, 'r') as f:
            scenario_data = json.load(f)
        
        print(f"📂 Loading metadata from {metadata_file.name}...")
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        # Parse timestamps in scenario data
        for reading in scenario_data:
            if isinstance(reading['timestamp'], str):
                reading['timestamp'] = datetime.fromisoformat(reading['timestamp'].replace('Z', '+00:00'))
        
        # Clear existing scenario data
        print(f"\n🗑️  Clearing existing scenario data...")
        await db.scenario_time_series.delete_many({})
        await db.scenario_metadata.delete_many({})
        print("✅ Existing data cleared")
        
        # Insert scenario time series data
        print(f"\n💾 Inserting {len(scenario_data)} time series readings...")
        result = await db.scenario_time_series.insert_many(scenario_data)
        print(f"✅ Inserted {len(result.inserted_ids)} time series readings")
        
        # Insert metadata
        print(f"\n💾 Inserting {len(metadata)} scenario metadata documents...")
        result = await db.scenario_metadata.insert_many(metadata)
        print(f"✅ Inserted {len(result.inserted_ids)} metadata documents")
        
        # Create indexes for efficient querying
        print(f"\n🔍 Creating indexes...")
        
        # Index on scenario_id and timestamp for time series queries
        await db.scenario_time_series.create_index([
            ("metadata.scenario_id", 1),
            ("timestamp", 1)
        ])
        print("✅ Created index: (scenario_id, timestamp)")
        
        # Index on equipment_id for equipment-specific queries
        await db.scenario_time_series.create_index([("equipment_id", 1)])
        print("✅ Created index: (equipment_id)")
        
        # Index on scenario_id for metadata lookups
        await db.scenario_metadata.create_index([("scenario_id", 1)], unique=True)
        print("✅ Created index: (scenario_id) unique")
        
        # Verify data
        print(f"\n✅ Verification:")
        count = await db.scenario_time_series.count_documents({})
        print(f"   - Time series readings: {count}")
        
        count = await db.scenario_metadata.count_documents({})
        print(f"   - Metadata documents: {count}")
        
        # Show scenario breakdown
        print(f"\n📊 Scenario Breakdown:")
        for meta in metadata:
            count = await db.scenario_time_series.count_documents({
                "metadata.scenario_id": meta['scenario_id']
            })
            print(f"   - {meta['title']}: {count} readings ({meta['equipment_id']})")
        
        print("\n" + "=" * 60)
        print("✅ Scenario seeding complete!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Start backend: uv run uvicorn main:app --reload")
        print("2. List scenarios: curl http://localhost:8000/ai-agents/scenarios")
        print("3. Analyze: curl -X POST http://localhost:8000/ai-agents/analyze-scenario/gradual_drift")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()
        print("\n🔌 MongoDB connection closed")


if __name__ == "__main__":
    asyncio.run(seed_scenarios())

