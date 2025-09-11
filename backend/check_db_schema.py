"""
Database Schema Verification Script
Checks the current state of MongoDB collections and relationships
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
from datetime import datetime
import json

load_dotenv()

async def check_database_schema():
    """Comprehensive database schema check"""
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
    db = client["smf-yield-defect"]
    
    print("\n" + "="*60)
    print("DATABASE SCHEMA VERIFICATION")
    print("="*60)
    
    # 1. Check collections exist
    print("\n1. COLLECTIONS:")
    collections = await db.list_collection_names()
    # Filter out system collections
    user_collections = [c for c in collections if not c.startswith('system.')]
    for coll in sorted(user_collections):
        try:
            count = await db[coll].count_documents({})
            print(f"   - {coll}: {count} documents")
        except Exception as e:
            print(f"   - {coll}: Error counting - {e}")
    
    # 2. Check if process_sensor_ts is time series
    print("\n2. TIME SERIES CHECK:")
    coll_info = await db.command("listCollections", filter={"name": "process_sensor_ts"})
    for coll in coll_info['cursor']['firstBatch']:
        if coll['name'] == 'process_sensor_ts':
            if 'timeseries' in coll['options']:
                print(f"   ✅ process_sensor_ts IS a time series collection")
                print(f"      TimeField: {coll['options']['timeseries'].get('timeField')}")
                print(f"      MetaField: {coll['options']['timeseries'].get('metaField')}")
                print(f"      Granularity: {coll['options']['timeseries'].get('granularity')}")
            else:
                print(f"   ❌ process_sensor_ts is NOT a time series collection")
    
    # 3. Check ID formats
    print("\n3. ID FORMAT ANALYSIS:")
    
    # Check wafer IDs in different collections
    print("\n   Wafer ID Formats:")
    
    # Alerts collection
    alerts_sample = await db.alerts.find_one({"wafer_id": {"$exists": True}})
    if alerts_sample:
        print(f"   - alerts.wafer_id: {alerts_sample.get('wafer_id')}")
    
    # Wafer defects collection
    defects_sample = await db.wafer_defects.find_one()
    if defects_sample:
        print(f"   - wafer_defects.wafer_id: {defects_sample.get('wafer_id')}")
    
    # Check equipment IDs
    print("\n   Equipment ID Formats:")
    
    # Alerts
    alerts_equip = await db.alerts.find_one({"equipment_id": {"$exists": True}})
    if alerts_equip:
        print(f"   - alerts.equipment_id: {alerts_equip.get('equipment_id')}")
    
    # Sensor data
    sensor_equip = await db.process_sensor_ts.find_one()
    if sensor_equip:
        print(f"   - process_sensor_ts.equipment_id: {sensor_equip.get('equipment_id')}")
    
    # Wafer defects
    defects_equip = await db.wafer_defects.find_one({"process_context.equipment_used": {"$exists": True}})
    if defects_equip:
        print(f"   - wafer_defects.equipment: {defects_equip.get('process_context', {}).get('equipment_used')}")
    
    # 4. Check relationships between collections
    print("\n4. COLLECTION RELATIONSHIPS:")
    
    # Check if wafer_defects references process_context
    print("\n   Wafer Defects → Process Context:")
    defect_with_context = await db.wafer_defects.find_one(
        {"process_context.slurry_batch": {"$exists": True}}
    )
    if defect_with_context:
        batch_id = defect_with_context.get("process_context", {}).get("slurry_batch")
        print(f"   - Sample batch reference: {batch_id}")
        
        # Check if this batch exists in process_context
        context_doc = await db.process_context.find_one({"context_id": batch_id})
        if context_doc:
            print(f"   ✅ Batch {batch_id} found in process_context collection")
        else:
            print(f"   ❌ Batch {batch_id} NOT found in process_context collection")
    
    # Check alerts → wafer_defects relationship
    print("\n   Alerts → Wafer Defects:")
    alert_with_wafer = await db.alerts.find_one({"wafer_id": {"$exists": True}})
    if alert_with_wafer:
        wafer_id = alert_with_wafer.get("wafer_id")
        print(f"   - Alert references wafer: {wafer_id}")
        
        # Try to find this wafer in defects
        defect = await db.wafer_defects.find_one({"wafer_id": wafer_id})
        if defect:
            print(f"   ✅ Wafer {wafer_id} found in wafer_defects")
        else:
            print(f"   ❌ Wafer {wafer_id} NOT found in wafer_defects")
    
    # 5. Check for ID format consistency
    print("\n5. ID CONSISTENCY ANALYSIS:")
    
    # Sample multiple wafer IDs
    print("\n   Wafer ID Samples:")
    wafer_ids_alerts = await db.alerts.distinct("wafer_id")
    wafer_ids_defects = await db.wafer_defects.distinct("wafer_id")
    
    print(f"   - Alerts wafer IDs (first 5): {wafer_ids_alerts[:5]}")
    print(f"   - Defects wafer IDs (first 5): {wafer_ids_defects[:5]}")
    
    # Check for overlap
    alerts_set = set(wafer_ids_alerts)
    defects_set = set(wafer_ids_defects)
    overlap = alerts_set.intersection(defects_set)
    
    if overlap:
        print(f"   ✅ Found {len(overlap)} matching wafer IDs between collections")
    else:
        print(f"   ❌ NO matching wafer IDs between alerts and wafer_defects")
    
    # Equipment ID samples
    print("\n   Equipment ID Samples:")
    equip_alerts = await db.alerts.distinct("equipment_id")
    equip_sensor = await db.process_sensor_ts.distinct("equipment_id")
    
    print(f"   - Alerts equipment IDs (first 5): {equip_alerts[:5]}")
    print(f"   - Sensor equipment IDs (first 5): {equip_sensor[:5]}")
    
    # 6. Check indexes
    print("\n6. INDEXES:")
    for coll_name in ['alerts', 'wafer_defects', 'process_sensor_ts', 'process_context']:
        indexes = await db[coll_name].index_information()
        print(f"\n   {coll_name}:")
        for idx_name, idx_info in indexes.items():
            if idx_name != '_id_':
                print(f"   - {idx_name}: {idx_info.get('key')}")
    
    # 7. Check embeddings
    print("\n7. EMBEDDINGS STATUS:")
    
    # Check embedding fields
    collections_to_check = [
        ('historical_knowledge', 'embedding'),
        ('wafer_defects', 'embedding'),
        ('alerts', 'embedding')
    ]
    
    for coll_name, embed_field in collections_to_check:
        total = await db[coll_name].count_documents({})
        with_embedding = await db[coll_name].count_documents({embed_field: {"$exists": True}})
        percent = (with_embedding/total*100) if total > 0 else 0
        print(f"   - {coll_name}: {with_embedding}/{total} have embeddings ({percent:.1f}%)")
    
    # 8. Check for empty/stale collections
    print("\n8. EMPTY/STALE COLLECTIONS:")
    for coll in user_collections:
        try:
            count = await db[coll].count_documents({})
            if count == 0:
                print(f"   ❌ {coll} is EMPTY")
            elif count < 5:
                print(f"   ⚠️  {coll} has only {count} documents")
        except:
            pass
    
    print("\n" + "="*60)
    print("VERIFICATION COMPLETE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(check_database_schema())