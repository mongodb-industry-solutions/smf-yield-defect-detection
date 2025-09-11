#!/usr/bin/env python3
"""
Generate synthetic sensor data for semiconductor manufacturing equipment.
Creates time-series data with realistic patterns and anomalies.
"""

import json
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any
import random


def generate_sensor_data(days: int = 30) -> List[Dict[str, Any]]:
    """
    Generate synthetic sensor data with realistic patterns and anomalies.
    
    Args:
        days: Number of days of data to generate
        
    Returns:
        List of sensor data records
    """
    # Configuration
    start_date = datetime.now() - timedelta(days=days)
    end_date = datetime.now()
    equipment_ids = ["CMP_TOOL_01", "CMP_TOOL_02", "ETCH_01", "LITHO_01"]
    
    data = []
    current_date = start_date
    
    # Track anomaly events for correlation
    anomaly_timestamps = []
    
    while current_date <= end_date:
        for equipment_id in equipment_ids:
            # Base values with daily variation
            hour_of_day = current_date.hour
            day_of_week = current_date.weekday()
            
            # Simulate lower activity during night shifts and weekends
            activity_factor = 1.0
            if hour_of_day < 6 or hour_of_day > 22:
                activity_factor = 0.7
            if day_of_week >= 5:  # Weekend
                activity_factor = 0.5
            
            # Process-specific base values
            if "CMP" in equipment_id:
                base_particle_count = 500 * activity_factor + np.sin(current_date.day * 0.2) * 100
                base_rf_power = 1200
                base_pressure = 45
                base_temp = 65
                base_flow = 200
            elif "ETCH" in equipment_id:
                base_particle_count = 300 * activity_factor
                base_rf_power = 1500
                base_pressure = 30
                base_temp = 75
                base_flow = 150
            else:  # LITHO
                base_particle_count = 200 * activity_factor
                base_rf_power = 800
                base_pressure = 20
                base_temp = 23  # Clean room temp
                base_flow = 100
            
            # Add random noise
            particle_count = base_particle_count + np.random.normal(0, 50)
            rf_power = base_rf_power + np.random.normal(0, 30)
            chamber_pressure = base_pressure + np.random.normal(0, 2)
            temperature = base_temp + np.random.normal(0, 0.5)
            flow_rate = base_flow + np.random.normal(0, 5)
            
            # Inject anomalies (5% chance)
            is_anomaly = False
            if np.random.random() < 0.05:
                is_anomaly = True
                anomaly_type = np.random.choice(['particle_spike', 'rf_drift', 'pressure_drop'])
                
                if anomaly_type == 'particle_spike':
                    # Major particle excursion
                    particle_count *= np.random.uniform(2.5, 4)
                    anomaly_timestamps.append({
                        'timestamp': current_date,
                        'equipment': equipment_id,
                        'type': 'particle_spike'
                    })
                elif anomaly_type == 'rf_drift':
                    # RF power drift
                    rf_power += np.random.uniform(150, 300) * np.random.choice([1, -1])
                else:
                    # Pressure instability
                    chamber_pressure *= np.random.uniform(0.5, 1.5)
            
            # Create record
            record = {
                "timestamp": current_date,  # Use datetime object directly for time series
                "equipment_id": equipment_id,
                "process_step": equipment_id.split("_")[0],
                "metrics": {
                    "particle_count": max(0, int(particle_count)),
                    "rf_power": max(0, round(rf_power, 1)),
                    "chamber_pressure": max(0, round(chamber_pressure, 2)),
                    "temperature": round(temperature, 2),
                    "flow_rate": max(0, round(flow_rate, 1))
                },
                "metadata": {
                    "lot_id": f"LOT_2025_{(current_date.day % 30 + 1):03d}",
                    "wafer_id": f"W_{(current_date.day % 30 + 1):03d}_{chr(65 + current_date.hour % 4)}",
                    "recipe_id": f"{equipment_id.split('_')[0]}_RECIPE_{(current_date.day % 3 + 1):02d}",
                    "operator_id": f"OP_{100 + (current_date.hour % 3)}"
                }
            }
            
            # Add anomaly flag for tracking
            if is_anomaly:
                record["metadata"]["anomaly_flag"] = True
                
            data.append(record)
        
        # Increment by 30 minutes
        current_date += timedelta(minutes=30)
    
    return data, anomaly_timestamps


def main():
    """Generate and save sensor data."""
    print("Generating sensor data...")
    
    # Generate 30 days of data
    sensor_data, anomalies = generate_sensor_data(days=30)
    
    # Save sensor data
    output_file = "sensor_data.json"
    with open(output_file, 'w') as f:
        json.dump(sensor_data, f, indent=2)
    
    print(f"✓ Generated {len(sensor_data)} sensor records")
    print(f"✓ Injected {len(anomalies)} anomaly events")
    print(f"✓ Saved to {output_file}")
    
    # Save anomaly events for correlation
    with open("anomaly_events.json", 'w') as f:
        json.dump([{
            'timestamp': a['timestamp'].isoformat() + 'Z',
            'equipment': a['equipment'],
            'type': a['type']
        } for a in anomalies], f, indent=2)
    
    # Print statistics
    print("\nStatistics:")
    print(f"  - Date range: {sensor_data[0]['timestamp']} to {sensor_data[-1]['timestamp']}")
    print(f"  - Equipment: CMP_TOOL_01, CMP_TOOL_02, ETCH_01, LITHO_01")
    print(f"  - Records per equipment: ~{len(sensor_data) // 4}")
    
    # Sample anomaly events
    if anomalies:
        print(f"\nSample anomaly events (first 3):")
        for event in anomalies[:3]:
            print(f"  - {event['timestamp'].isoformat()}: {event['type']} on {event['equipment']}")


if __name__ == "__main__":
    main()