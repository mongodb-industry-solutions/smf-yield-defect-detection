#!/usr/bin/env python3
"""
Script to clean up test alerts and keep only alerts for real equipment
"""

from pymongo import MongoClient
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def cleanup_test_alerts():
    """Remove alerts for test equipment and keep only real equipment alerts"""

    # Connect to MongoDB
    client = MongoClient(os.getenv('MONGODB_URI'), appname=os.getenv('APP_NAME', 'devrel-demo-vectorsearch-langgraph-semiconductor'))
    db = client['smf-yield-defect']
    alerts_collection = db['alerts']
    sensor_collection = db['process_sensor_ts']

    print(f"Connected to MongoDB database: {db.name}")
    print(f"Cleaning up alerts collection")

    # Get list of REAL equipment from sensor time series
    pipeline = [
        {'$group': {'_id': '$equipment_id'}},
        {'$sort': {'_id': 1}}
    ]
    real_equipment = [eq['_id'] for eq in sensor_collection.aggregate(pipeline)]

    print(f"\nReal equipment found in sensor data ({len(real_equipment)}):")
    for eq_id in real_equipment:
        print(f"  - {eq_id}")

    # Get all open alerts
    all_alerts = list(alerts_collection.find({'status': 'open'}))
    total_alerts = len(all_alerts)

    print(f"\nTotal open alerts before cleanup: {total_alerts}")

    # Identify alerts to remove (equipment not in real list)
    alerts_to_remove = []
    alerts_to_keep = []

    for alert in all_alerts:
        eq_id = alert.get('equipment_id', 'UNKNOWN')
        if eq_id not in real_equipment:
            alerts_to_remove.append({
                'alert_id': alert.get('alert_id'),
                'equipment_id': eq_id,
                'severity': alert.get('severity')
            })
        else:
            alerts_to_keep.append({
                'alert_id': alert.get('alert_id'),
                'equipment_id': eq_id,
                'severity': alert.get('severity')
            })

    print(f"\nAlerts to REMOVE ({len(alerts_to_remove)}):")
    for alert in alerts_to_remove:
        print(f"  - {alert['alert_id']}: {alert['equipment_id']} ({alert['severity']})")

    print(f"\nAlerts to KEEP ({len(alerts_to_keep)}):")
    for alert in alerts_to_keep:
        print(f"  - {alert['alert_id']}: {alert['equipment_id']} ({alert['severity']})")

    if len(alerts_to_remove) > 0:
        # Remove alerts for non-existent equipment
        alert_ids_to_remove = [a['alert_id'] for a in alerts_to_remove]
        result = alerts_collection.update_many(
            {'alert_id': {'$in': alert_ids_to_remove}},
            {
                '$set': {
                    'status': 'resolved',
                    'resolved_at': datetime.utcnow(),
                    'resolution': 'Auto-resolved: Test equipment removed',
                    'updated_at': datetime.utcnow()
                }
            }
        )
        print(f"\n✅ Resolved {result.modified_count} test equipment alerts")

    # Now check if we need to create alerts for critical equipment
    print(f"\n--- Checking for missing alerts ---")

    # Get latest sensor readings for each equipment
    latest_pipeline = [
        {'$sort': {'timestamp': -1}},
        {'$group': {
            '_id': '$equipment_id',
            'latest': {'$first': '$$ROOT'}
        }}
    ]

    latest_readings = list(sensor_collection.aggregate(latest_pipeline))

    critical_equipment = []
    for reading in latest_readings:
        eq_id = reading['_id']
        metrics = reading['latest'].get('metrics', {})
        particle_count = metrics.get('particle_count', 0)

        # Check if critical (>1000 particles)
        if particle_count > 1000:
            critical_equipment.append({
                'equipment_id': eq_id,
                'particle_count': particle_count,
                'process_step': reading['latest'].get('process_step', 'UNKNOWN')
            })

    print(f"\nEquipment with critical particle counts:")
    for eq in critical_equipment:
        print(f"  - {eq['equipment_id']}: {eq['particle_count']} particles")

        # Check if alert already exists for this equipment
        existing_alert = alerts_collection.find_one({
            'equipment_id': eq['equipment_id'],
            'status': 'open'
        })

        if not existing_alert:
            print(f"    ⚠️  No active alert found for {eq['equipment_id']} - should create one!")

    # Get final count
    remaining_open = alerts_collection.count_documents({'status': 'open'})
    print(f"\nFinal open alerts count: {remaining_open}")

    client.close()
    print("\n✅ Cleanup complete!")

if __name__ == "__main__":
    cleanup_test_alerts()