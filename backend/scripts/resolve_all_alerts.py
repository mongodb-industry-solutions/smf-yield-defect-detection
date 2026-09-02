#!/usr/bin/env python3
"""
Script to resolve all open alerts
"""

from pymongo import MongoClient
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def resolve_all_alerts():
    """Resolve all open alerts"""

    # Connect to MongoDB
    client = MongoClient(os.getenv('MONGODB_URI'), appname=os.getenv('APP_NAME', 'devrel-fastapi-smf-yield-defect-detection'))
    db = client['smf-yield-defect']
    alerts_collection = db['alerts']

    print(f"Connected to MongoDB database: {db.name}")

    # Get count of open alerts
    open_count = alerts_collection.count_documents({'status': 'open'})
    print(f"Found {open_count} open alerts")

    if open_count > 0:
        # List open alerts before resolving
        print("\nOpen alerts to be resolved:")
        open_alerts = list(alerts_collection.find({'status': 'open'}))
        for alert in open_alerts:
            print(f"  - {alert['alert_id']}: {alert['equipment_id']} ({alert['severity']})")

        # Resolve all open alerts
        result = alerts_collection.update_many(
            {'status': 'open'},
            {
                '$set': {
                    'status': 'resolved',
                    'resolved_at': datetime.utcnow(),
                    'resolution': 'Manually resolved for testing',
                    'updated_at': datetime.utcnow()
                }
            }
        )
        print(f"\n✅ Resolved {result.modified_count} alerts")

    # Final count
    remaining_open = alerts_collection.count_documents({'status': 'open'})
    print(f"\nRemaining open alerts: {remaining_open}")

    client.close()
    print("\nDone!")

if __name__ == "__main__":
    resolve_all_alerts()