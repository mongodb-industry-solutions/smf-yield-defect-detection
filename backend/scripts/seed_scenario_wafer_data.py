#!/usr/bin/env python3
"""
Seed wafer defect and process context data for scenarios.

Takes existing data from JSON files, copies 3 records, renames IDs to match
scenario lot/wafer IDs, and inserts into MongoDB for downstream agent analysis.
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import copy

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()


async def seed_scenario_wafer_data():
    """Load existing data, rename IDs for scenarios, and insert into MongoDB."""
    
    print("=" * 70)
    print("Seeding Scenario Wafer Defects and Process Context")
    print("=" * 70)
    
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
        
        # Load existing data files
        data_dir = Path(__file__).parent.parent / "data_generation"
        
        wafer_file = data_dir / "wafer_defects.json"
        context_file = data_dir / "process_context.json"
        
        if not wafer_file.exists():
            print(f"\n❌ Error: {wafer_file} not found")
            return
        
        if not context_file.exists():
            print(f"\n❌ Error: {context_file} not found")
            return
        
        print(f"\n📂 Loading existing data...")
        with open(wafer_file, 'r') as f:
            wafer_defects = json.load(f)
        print(f"   ✓ Loaded {len(wafer_defects)} wafer defects")
        
        with open(context_file, 'r') as f:
            process_contexts = json.load(f)
        print(f"   ✓ Loaded {len(process_contexts)} process context records")
        
        # === Find records by pattern ===
        print(f"\n🔍 Finding records by pattern...")
        
        clustered_wafer = next(
            (w for w in wafer_defects if w['defect_summary']['defect_pattern'] == 'clustered'),
            None
        )
        random_wafer = next(
            (w for w in wafer_defects if w['defect_summary']['defect_pattern'] == 'random'),
            None
        )
        systematic_wafer = next(
            (w for w in wafer_defects if w['defect_summary']['defect_pattern'] == 'systematic'),
            None
        )
        
        if not all([clustered_wafer, random_wafer, systematic_wafer]):
            print("❌ Error: Could not find all required patterns")
            return
        
        print(f"   ✓ Found clustered pattern wafer")
        print(f"   ✓ Found random pattern wafer")
        print(f"   ✓ Found systematic pattern wafer")
        
        # Find problematic process contexts
        problematic_slurries = [
            c for c in process_contexts 
            if c.get('context_type') == 'slurry_batch' and c.get('is_problematic')
        ]
        problematic_recipes = [
            c for c in process_contexts 
            if c.get('context_type') == 'etch_recipe'
        ]
        
        if len(problematic_slurries) < 2:
            print("❌ Error: Need at least 2 problematic slurry batches")
            return
        
        if len(problematic_recipes) < 1:
            print("❌ Error: Need at least 1 etch recipe")
            return
        
        print(f"   ✓ Found {len(problematic_slurries)} problematic slurry batches")
        print(f"   ✓ Found {len(problematic_recipes)} etch recipes")
        
        # === Create scenario wafer defects ===
        print(f"\n🔧 Creating scenario wafer defects...")
        
        scenario_wafers = []
        
        # 1. Gradual Drift (clustered pattern)
        drift_wafer = copy.deepcopy(clustered_wafer)
        drift_wafer['wafer_id'] = 'W_DRIFT_01'
        drift_wafer['lot_id'] = 'LOT_2025_DRIFT'
        drift_wafer['process_context']['equipment_used'] = ['CMP_TOOL_01']
        drift_wafer['process_context']['last_process_step'] = 'CMP'
        drift_wafer['process_context']['slurry_batch'] = 'SB_2025_021'
        drift_wafer['description'] = "Clustered particle defects from gradual filter degradation in CMP_TOOL_01"
        scenario_wafers.append(drift_wafer)
        print(f"   ✓ Created W_DRIFT_01 (clustered pattern)")
        
        # 2. Sudden Spike (random pattern)
        spike_wafer = copy.deepcopy(random_wafer)
        spike_wafer['wafer_id'] = 'W_SPIKE_01'
        spike_wafer['lot_id'] = 'LOT_2025_SPIKE'
        spike_wafer['process_context']['equipment_used'] = ['ETCH_01']
        spike_wafer['process_context']['last_process_step'] = 'ETCH'
        # Remove slurry_batch for ETCH, add recipe reference
        spike_wafer['process_context'].pop('slurry_batch', None)
        spike_wafer['process_context']['etch_recipe'] = 'ETCH_RECIPE_21'
        spike_wafer['description'] = "Random defects from transient contamination event in ETCH_01"
        scenario_wafers.append(spike_wafer)
        print(f"   ✓ Created W_SPIKE_01 (random pattern)")
        
        # 3. Oscillating Pattern (systematic pattern)
        osc_wafer = copy.deepcopy(systematic_wafer)
        osc_wafer['wafer_id'] = 'W_OSC_01'
        osc_wafer['lot_id'] = 'LOT_2025_OSC'
        osc_wafer['process_context']['equipment_used'] = ['CMP_TOOL_02']
        osc_wafer['process_context']['last_process_step'] = 'CMP'
        osc_wafer['process_context']['slurry_batch'] = 'SB_2025_022'
        osc_wafer['description'] = "Systematic pattern defects from equipment instability in CMP_TOOL_02"
        scenario_wafers.append(osc_wafer)
        print(f"   ✓ Created W_OSC_01 (systematic pattern)")
        
        # === Create scenario process contexts ===
        print(f"\n🔧 Creating scenario process contexts...")
        
        scenario_contexts = []
        
        # 1. SB_2025_021 (for gradual_drift)
        slurry_1 = copy.deepcopy(problematic_slurries[0])
        slurry_1['_id'] = 'SB_2025_021'
        slurry_1['context_id'] = 'SB_2025_021'
        slurry_1['slurry_details']['qc_status'] = 'marginal'
        slurry_1['known_issues'] = [{
            "date": "2025-10-19T08:00:00Z",
            "description": "Filter degradation causing elevated large particle count",
            "severity": "high"
        }]
        slurry_1['is_problematic'] = True
        scenario_contexts.append(slurry_1)
        print(f"   ✓ Created SB_2025_021 (slurry batch)")
        
        # 2. ETCH_RECIPE_21 (for sudden_spike)
        recipe = copy.deepcopy(problematic_recipes[0])
        recipe['_id'] = 'ETCH_RECIPE_21'
        recipe['context_id'] = 'ETCH_RECIPE_21'
        recipe['known_issues'] = [{
            "date": "2025-10-19T10:00:00Z",
            "description": "Transient chamber contamination event",
            "severity": "high"
        }]
        recipe['is_problematic'] = True
        scenario_contexts.append(recipe)
        print(f"   ✓ Created ETCH_RECIPE_21 (etch recipe)")
        
        # 3. SB_2025_022 (for oscillating_pattern)
        slurry_2 = copy.deepcopy(problematic_slurries[1] if len(problematic_slurries) > 1 else problematic_slurries[0])
        slurry_2['_id'] = 'SB_2025_022'
        slurry_2['context_id'] = 'SB_2025_022'
        slurry_2['slurry_details']['qc_status'] = 'marginal'
        slurry_2['known_issues'] = [{
            "date": "2025-10-19T12:00:00Z",
            "description": "Pressure control instability causing viscosity variation",
            "severity": "high"
        }]
        slurry_2['is_problematic'] = True
        scenario_contexts.append(slurry_2)
        print(f"   ✓ Created SB_2025_022 (slurry batch)")
        
        # === Insert into MongoDB ===
        print(f"\n💾 Inserting into MongoDB...")
        
        # Delete any existing scenario data first
        await db.wafer_defects.delete_many({
            "wafer_id": {"$in": ["W_DRIFT_01", "W_SPIKE_01", "W_OSC_01"]}
        })
        await db.process_context.delete_many({
            "context_id": {"$in": ["SB_2025_021", "ETCH_RECIPE_21", "SB_2025_022"]}
        })
        print(f"   ✓ Cleared existing scenario data")
        
        # Insert wafer defects
        result = await db.wafer_defects.insert_many(scenario_wafers)
        print(f"   ✓ Inserted {len(result.inserted_ids)} wafer defects")
        
        # Insert process contexts
        result = await db.process_context.insert_many(scenario_contexts)
        print(f"   ✓ Inserted {len(result.inserted_ids)} process contexts")
        
        # === Verification ===
        print(f"\n✅ Verification:")
        
        wafer_count = await db.wafer_defects.count_documents({
            "wafer_id": {"$in": ["W_DRIFT_01", "W_SPIKE_01", "W_OSC_01"]}
        })
        print(f"   - Wafer defects: {wafer_count}/3")
        
        context_count = await db.process_context.count_documents({
            "context_id": {"$in": ["SB_2025_021", "ETCH_RECIPE_21", "SB_2025_022"]}
        })
        print(f"   - Process contexts: {context_count}/3")
        
        # Show details
        print(f"\n📊 Scenario Data Summary:")
        for wafer in scenario_wafers:
            print(f"\n   {wafer['wafer_id']} (Lot: {wafer['lot_id']})")
            print(f"      - Pattern: {wafer['defect_summary']['defect_pattern']}")
            print(f"      - Yield: {wafer['defect_summary']['yield_percentage']:.1f}%")
            print(f"      - Equipment: {wafer['process_context']['equipment_used'][0]}")
            if 'slurry_batch' in wafer['process_context']:
                print(f"      - Slurry: {wafer['process_context']['slurry_batch']}")
            if 'etch_recipe' in wafer['process_context']:
                print(f"      - Recipe: {wafer['process_context']['etch_recipe']}")
        
        print("\n" + "=" * 70)
        print("✅ Scenario wafer data seeding complete!")
        print("=" * 70)
        print("\nDownstream agents can now query by lot_id/wafer_id:")
        print("  - W_DRIFT_01 / LOT_2025_DRIFT")
        print("  - W_SPIKE_01 / LOT_2025_SPIKE")
        print("  - W_OSC_01 / LOT_2025_OSC")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()
        print("\n🔌 MongoDB connection closed")


if __name__ == "__main__":
    asyncio.run(seed_scenario_wafer_data())

