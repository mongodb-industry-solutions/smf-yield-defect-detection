#!/usr/bin/env python3
"""
Load Enhanced Investigation Data into MongoDB
Loads the enhanced process_context and wafer_defects into MongoDB
"""

import json
import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from typing import Dict, List, Any

async def load_enhanced_data():
    """Load enhanced data into MongoDB"""
    print("=" * 60)
    print("Loading Enhanced Data into MongoDB")
    print("=" * 60)

    # Get MongoDB connection
    mongodb_uri = os.getenv("MONGODB_URI")
    database_name = os.getenv("MDB_DATABASE_NAME", "smf-yield-defect")

    if not mongodb_uri:
        print("ERROR: MONGODB_URI environment variable not set")
        return False

    print(f"\n1. Connecting to MongoDB...")
    print(f"   Database: {database_name}")

    client = AsyncIOMotorClient(mongodb_uri)
    db = client[database_name]

    # Get script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    enhanced_dir = os.path.join(script_dir, 'enhanced')

    # Load enhanced JSON files
    print("\n2. Loading enhanced JSON files...")

    try:
        with open(os.path.join(enhanced_dir, 'process_context_enhanced.json'), 'r') as f:
            process_context_data = json.load(f)
        print(f"   Loaded {len(process_context_data)} process_context items")
    except FileNotFoundError:
        print("   ERROR: process_context_enhanced.json not found")
        return False

    try:
        with open(os.path.join(enhanced_dir, 'wafer_defects_enhanced.json'), 'r') as f:
            wafer_defects_data = json.load(f)
        print(f"   Loaded {len(wafer_defects_data)} wafer_defects items")
    except FileNotFoundError:
        print("   ERROR: wafer_defects_enhanced.json not found")
        return False

    # Backup existing collections (optional)
    print("\n3. Creating backup of existing collections...")

    try:
        # Get current timestamp for backup names
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Check if collections exist and have data
        process_count = await db.process_context.count_documents({})
        wafer_count = await db.wafer_defects.count_documents({})

        if process_count > 0:
            # Create backup collection name
            backup_name = f"process_context_backup_{timestamp}"
            # Use aggregation to copy collection
            pipeline = [{"$out": backup_name}]
            await db.process_context.aggregate(pipeline).to_list(None)
            print(f"   Backed up {process_count} process_context docs to {backup_name}")
        else:
            print("   No existing process_context data to backup")

        if wafer_count > 0:
            backup_name = f"wafer_defects_backup_{timestamp}"
            pipeline = [{"$out": backup_name}]
            await db.wafer_defects.aggregate(pipeline).to_list(None)
            print(f"   Backed up {wafer_count} wafer_defects docs to {backup_name}")
        else:
            print("   No existing wafer_defects data to backup")

    except Exception as e:
        print(f"   Warning: Backup failed: {e}")
        print("   Continuing anyway...")

    # Clear existing collections and insert enhanced data
    print("\n4. Updating collections with enhanced data...")

    try:
        # Process context collection
        print("   Updating process_context collection...")

        # Clear existing data
        delete_result = await db.process_context.delete_many({})
        print(f"      Removed {delete_result.deleted_count} existing documents")

        # Insert enhanced data
        if process_context_data:
            # Convert _id fields to proper format if needed
            for item in process_context_data:
                if '_id' in item and isinstance(item['_id'], str):
                    # Keep string _id as is (MongoDB will handle it)
                    pass

            insert_result = await db.process_context.insert_many(process_context_data)
            print(f"      Inserted {len(insert_result.inserted_ids)} enhanced documents")

        # Wafer defects collection
        print("   Updating wafer_defects collection...")

        # Clear existing data
        delete_result = await db.wafer_defects.delete_many({})
        print(f"      Removed {delete_result.deleted_count} existing documents")

        # Insert enhanced data
        if wafer_defects_data:
            insert_result = await db.wafer_defects.insert_many(wafer_defects_data)
            print(f"      Inserted {len(insert_result.inserted_ids)} enhanced documents")

    except Exception as e:
        print(f"   ERROR: Failed to update collections: {e}")
        return False

    # Verify the data
    print("\n5. Verifying loaded data...")

    # Count documents
    process_count = await db.process_context.count_documents({})
    problematic_count = await db.process_context.count_documents({"is_problematic": True})
    enhanced_count = await db.process_context.count_documents({"scenario_context": {"$exists": True}})

    wafer_count = await db.wafer_defects.count_documents({})
    wafer_with_equipment = await db.wafer_defects.count_documents({"equipment_id": {"$ne": None}})
    wafer_with_correlation = await db.wafer_defects.count_documents({"excursion_correlation": {"$exists": True}})

    print(f"   Process Context:")
    print(f"      Total documents: {process_count}")
    print(f"      Problematic items: {problematic_count}")
    print(f"      Items with scenario_context: {enhanced_count}")

    print(f"   Wafer Defects:")
    print(f"      Total documents: {wafer_count}")
    print(f"      Wafers with equipment_id: {wafer_with_equipment}")
    print(f"      Wafers with excursion_correlation: {wafer_with_correlation}")

    # Test a query to ensure data is accessible
    print("\n6. Testing sample queries...")

    # Find a problematic slurry batch with enhancements
    sample = await db.process_context.find_one({
        "is_problematic": True,
        "scenario_context": {"$exists": True}
    })

    if sample:
        print(f"   ✅ Found enhanced problematic item: {sample.get('context_id')}")
        if 'enhanced_issues' in sample:
            root_cause = sample['enhanced_issues'].get('root_cause', 'N/A')
            print(f"      Root cause: {root_cause[:80]}...")

    # Find a wafer with correlation
    wafer_sample = await db.wafer_defects.find_one({
        "excursion_correlation": {"$exists": True}
    })

    if wafer_sample:
        print(f"   ✅ Found wafer with correlation: {wafer_sample.get('wafer_id')}")
        equipment = wafer_sample.get('equipment_id', 'N/A')
        print(f"      Equipment: {equipment}")

    # Close connection
    client.close()

    print("\n" + "=" * 60)
    print("✅ Enhanced data successfully loaded into MongoDB!")
    print("=" * 60)

    return True

async def verify_investigation_agent_access():
    """Quick test to verify investigation agent can access enhanced data"""
    print("\n7. Testing investigation agent compatibility...")

    mongodb_uri = os.getenv("MONGODB_URI")
    database_name = os.getenv("MDB_DATABASE_NAME", "smf-yield-defect")

    client = AsyncIOMotorClient(mongodb_uri)
    db = client[database_name]

    # Simulate investigation agent query
    query_filter = {
        "$or": [
            {"context_id": "SB_2025_043", "context_type": "slurry_batch"},
            {"context_id": "ETCH_RECIPE_01", "context_type": {"$in": ["etch_recipe", "recipe"]}}
        ]
    }

    results = await db.process_context.find(query_filter).to_list(100)

    print(f"   Investigation agent query returned {len(results)} results")

    for doc in results[:2]:
        print(f"   - {doc.get('context_id')}: problematic={doc.get('is_problematic', False)}")
        if 'scenario_context' in doc:
            print(f"     Has enhancement: scenario={doc['scenario_context'].get('scenario_id')}")

    client.close()
    print("   ✅ Investigation agent queries work with enhanced data")

def main():
    """Main execution"""
    # Load .env file if it exists
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"Loaded environment from {env_path}")

    # Run async function
    success = asyncio.run(load_enhanced_data())

    if success:
        # Also test investigation agent access
        asyncio.run(verify_investigation_agent_access())

    return 0 if success else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())