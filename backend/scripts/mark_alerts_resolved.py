#!/usr/bin/env python3
"""
Script to mark old alerts as resolved to improve performance
"""

from pymongo import MongoClient
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def mark_alerts_resolved(count=65):
    """Mark specified number of alerts as resolved"""

    # Connect to MongoDB
    client = MongoClient(os.getenv('MONGODB_URI'), appname=os.getenv('APP_NAME', 'devrel-fastapi-smf-yield-defect-detection'))
    db = client['smf-yield-defect']
    alerts_collection = db['alerts']

    print(f"Connected to MongoDB database: {db.name}")

    # Check current status
    total_alerts = alerts_collection.count_documents({})
    open_alerts = alerts_collection.count_documents({'status': 'open'})
    print(f"\nCurrent status:")
    print(f"  Total alerts: {total_alerts}")
    print(f"  Open alerts: {open_alerts}")

    if open_alerts == 0:
        print("No open alerts to update")
        return

    # Get oldest alerts to mark as resolved
    alerts_to_update = list(alerts_collection.find(
        {'status': 'open'},
        {'_id': 1, 'alert_id': 1, 'severity': 1}
    ).sort('timestamp', 1).limit(count))

    print(f"\nFound {len(alerts_to_update)} alerts to update")

    if len(alerts_to_update) > 0:
        # Update them to resolved status
        result = alerts_collection.update_many(
            {'_id': {'$in': [alert['_id'] for alert in alerts_to_update]}},
            {
                '$set': {
                    'status': 'resolved',
                    'resolved_at': datetime.utcnow(),
                    'resolution': 'Auto-resolved for performance optimization',
                    'resolution_notes': 'Bulk resolved to reduce active alert count',
                    'updated_at': datetime.utcnow()
                }
            }
        )

        print(f"Updated {result.modified_count} alerts to resolved status")

        # Show some of the updated alerts
        print("\nSample updated alerts:")
        for alert in alerts_to_update[:5]:
            print(f"  - {alert.get('alert_id', 'N/A')} (severity: {alert.get('severity', 'N/A')})")

    # Check final status
    remaining_open = alerts_collection.count_documents({'status': 'open'})
    resolved_count = alerts_collection.count_documents({'status': 'resolved'})

    print(f"\nFinal status:")
    print(f"  Open alerts: {remaining_open}")
    print(f"  Resolved alerts: {resolved_count}")
    print(f"  Total alerts: {total_alerts}")

    # Show remaining open alerts
    if remaining_open > 0:
        print(f"\nRemaining {remaining_open} open alerts:")
        open_alerts = alerts_collection.find(
            {'status': 'open'},
            {'alert_id': 1, 'severity': 1, 'alert_type': 1, 'timestamp': 1}
        ).sort('timestamp', -1)

        for alert in open_alerts:
            timestamp = alert.get('timestamp', 'N/A')
            if hasattr(timestamp, 'isoformat'):
                timestamp = timestamp.isoformat()
            print(f"  - {alert.get('alert_id', 'N/A')}: {alert.get('severity', 'N/A')} - {alert.get('alert_type', 'N/A')} ({timestamp})")

    client.close()
    print("\nDone!")

if __name__ == "__main__":
    mark_alerts_resolved(65)