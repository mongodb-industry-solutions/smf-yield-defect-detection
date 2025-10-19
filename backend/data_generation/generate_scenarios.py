#!/usr/bin/env python3
"""
Generate pre-defined failure scenarios for MongoDB time series analysis demonstration.

Each scenario demonstrates a different failure pattern with exactly ONE threshold excursion
to trigger a single alert, showcasing MongoDB's analytical capabilities.
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
import random


def generate_gradual_drift_scenario() -> List[Dict[str, Any]]:
    """
    Scenario 1: Gradual Drift Pattern
    
    Particle count slowly increases from 450 → 1150 over 2 hours.
    Only ONE spike crosses threshold (1000) to trigger single alert.
    Demonstrates: Rolling averages, trend detection, slope calculation
    
    Returns:
        List of 120 sensor readings (1 reading per minute for 2 hours)
    """
    readings = []
    # Use current time minus 2 hours for fresh, recent data
    base_time = datetime.now() - timedelta(hours=2)
    
    # Parameters for drift pattern
    start_value = 450
    end_value = 1150
    total_minutes = 120
    
    for minute in range(total_minutes):
        timestamp = base_time + timedelta(minutes=minute)
        
        # Linear drift with realistic noise
        progress = minute / total_minutes
        base_particle_count = start_value + (end_value - start_value) * progress
        
        # Add realistic noise (±30 particles)
        noise = random.uniform(-30, 30)
        particle_count = int(base_particle_count + noise)
        
        # Ensure we cross threshold only once around minute 75
        if minute == 75:
            particle_count = 1050  # Single threshold breach
        elif minute > 75:
            # Stay above threshold after first breach
            particle_count = max(particle_count, 1020)
        
        readings.append({
            "timestamp": timestamp,
            "equipment_id": "CMP_TOOL_01",
            "process_step": "CMP",
            "metrics": {
                "particle_count": particle_count,
                "rf_power": 1450 + random.uniform(-15, 15),
                "chamber_pressure": 45 + random.uniform(-1.5, 1.5),
                "temperature": 65 + random.uniform(-0.8, 0.8),
                "flow_rate": 200 + random.uniform(-8, 8)
            },
            "metadata": {
                "lot_id": "LOT_2025_DRIFT",
                "wafer_id": "W_DRIFT_01",
                "recipe_id": "RECIPE_01",
                "slurry_batch": "SB_2025_021",  # Problematic batch
                "operator_id": "OP_150",
                "scenario_id": "gradual_drift",
                "scenario_label": "anomaly" if minute >= 75 else "normal"
            }
        })
    
    return readings


def generate_sudden_spike_scenario() -> List[Dict[str, Any]]:
    """
    Scenario 2: Sudden Spike Pattern
    
    Normal operation → sudden spike (1200) → return to normal.
    Only ONE spike crosses threshold to trigger single alert.
    Demonstrates: Anomaly detection, recovery analysis, comparative windows
    
    Returns:
        List of 120 sensor readings
    """
    readings = []
    # Use current time minus 90 minutes for recent data (staggered from drift)
    base_time = datetime.now() - timedelta(minutes=90)
    
    normal_value = 450
    spike_minute = 60  # Spike at 1 hour mark
    spike_value = 1200
    
    for minute in range(120):
        timestamp = base_time + timedelta(minutes=minute)
        
        # Normal operation except for spike
        if minute == spike_minute:
            # Single sharp spike
            particle_count = spike_value
        else:
            # Normal range with noise
            particle_count = int(normal_value + random.uniform(-40, 40))
        
        readings.append({
            "timestamp": timestamp,
            "equipment_id": "ETCH_01",
            "process_step": "ETCH",
            "metrics": {
                "particle_count": particle_count,
                "rf_power": 1200 + random.uniform(-12, 12),
                "chamber_pressure": 35 + random.uniform(-1.2, 1.2),
                "temperature": 70 + random.uniform(-0.6, 0.6),
                "flow_rate": 150 + random.uniform(-6, 6)
            },
            "metadata": {
                "lot_id": "LOT_2025_SPIKE",
                "wafer_id": "W_SPIKE_01",
                "recipe_id": "RECIPE_02",
                "slurry_batch": "SB_2025_003",  # Normal batch
                "operator_id": "OP_160",
                "scenario_id": "sudden_spike",
                "scenario_label": "anomaly" if minute == spike_minute else "normal"
            }
        })
    
    return readings


def generate_oscillating_pattern_scenario() -> List[Dict[str, Any]]:
    """
    Scenario 3: Oscillating Pattern
    
    Regular fluctuations between 600-1100 (equipment instability).
    Only ONE peak crosses threshold (1000) to trigger single alert.
    Demonstrates: Periodicity detection, frequency analysis, pattern recognition
    
    Returns:
        List of 120 sensor readings
    """
    readings = []
    # Use current time minus 60 minutes for most recent data
    base_time = datetime.now() - timedelta(minutes=60)
    
    base_value = 750
    amplitude = 250  # Oscillates ±250 from base
    period_minutes = 30  # Complete cycle every 30 minutes
    
    for minute in range(120):
        timestamp = base_time + timedelta(minutes=minute)
        
        # Sine wave oscillation
        import math
        phase = (2 * math.pi * minute) / period_minutes
        oscillation = amplitude * math.sin(phase)
        
        particle_count = int(base_value + oscillation + random.uniform(-20, 20))
        
        # Ensure only ONE peak crosses threshold (at minute 45, second peak)
        if minute == 45:
            particle_count = 1050  # Single threshold breach
        elif abs(minute - 45) < 5:
            # Keep other peaks just below threshold
            particle_count = min(particle_count, 980)
        
        readings.append({
            "timestamp": timestamp,
            "equipment_id": "CMP_TOOL_02",
            "process_step": "CMP",
            "metrics": {
                "particle_count": particle_count,
                "rf_power": 1450 + random.uniform(-18, 18),
                "chamber_pressure": 45 + random.uniform(-1.8, 1.8),
                "temperature": 65 + random.uniform(-0.9, 0.9),
                "flow_rate": 200 + random.uniform(-9, 9)
            },
            "metadata": {
                "lot_id": "LOT_2025_OSC",
                "wafer_id": "W_OSC_01",
                "recipe_id": "RECIPE_03",
                "slurry_batch": "SB_2025_043",  # Problematic batch
                "operator_id": "OP_170",
                "scenario_id": "oscillating_pattern",
                "scenario_label": "anomaly" if abs(minute - 45) < 3 else "normal"
            }
        })
    
    return readings


def generate_scenario_metadata() -> List[Dict[str, Any]]:
    """
    Generate metadata for each scenario including ground truth labels.
    
    Returns:
        List of scenario metadata documents
    """
    return [
        {
            "scenario_id": "gradual_drift",
            "title": "Gradual Particle Drift Pattern",
            "description": "Particle count slowly increases from 450 to 1150 over 2 hours due to filter degradation",
            "equipment_id": "CMP_TOOL_01",
            "lot_id": "LOT_2025_DRIFT",  # Added for downstream agent analysis
            "wafer_id": "W_DRIFT_01",  # Added for downstream agent analysis
            "duration_minutes": 120,
            "data_points": 120,
            "pattern_type": "drift",
            "root_cause": "Filter degradation allowing progressive particle accumulation",
            "anomaly_window": {
                "start_minute": 75,
                "end_minute": 120,
                "peak_minute": 120,
                "peak_value": 1150
            },
            "expected_insights": [
                "Linear increasing trend with high R² value",
                "Rolling averages show consistent upward trajectory",
                "Gradual nature suggests component wear, not contamination"
            ]
        },
        {
            "scenario_id": "sudden_spike",
            "title": "Sudden Particle Spike Event",
            "description": "Sharp particle spike to 1200 during normal operation, likely due to contamination event",
            "equipment_id": "ETCH_01",
            "lot_id": "LOT_2025_SPIKE",  # Added for downstream agent analysis
            "wafer_id": "W_SPIKE_01",  # Added for downstream agent analysis
            "duration_minutes": 120,
            "data_points": 120,
            "pattern_type": "spike",
            "root_cause": "Transient contamination event or chamber door seal failure",
            "anomaly_window": {
                "start_minute": 60,
                "end_minute": 60,
                "peak_minute": 60,
                "peak_value": 1200
            },
            "expected_insights": [
                "Single isolated spike with rapid return to baseline",
                "High deviation from rolling average (>10σ)",
                "Short duration suggests transient event, not systemic issue"
            ]
        },
        {
            "scenario_id": "oscillating_pattern",
            "title": "Oscillating Particle Pattern",
            "description": "Regular fluctuations between 600-1100 indicating equipment instability or process variation",
            "equipment_id": "CMP_TOOL_02",
            "lot_id": "LOT_2025_OSC",  # Added for downstream agent analysis
            "wafer_id": "W_OSC_01",  # Added for downstream agent analysis
            "duration_minutes": 120,
            "data_points": 120,
            "pattern_type": "oscillation",
            "root_cause": "Equipment instability (pressure control issues or pad conditioning cycle effects)",
            "anomaly_window": {
                "start_minute": 43,
                "end_minute": 48,
                "peak_minute": 45,
                "peak_value": 1050
            },
            "expected_insights": [
                "Periodic pattern with ~30 minute cycle",
                "Consistent amplitude suggests systematic cause",
                "Requires equipment calibration or process parameter adjustment"
            ]
        }
    ]


def main():
    """Generate and save scenario data."""
    print("=" * 60)
    print("Generating MongoDB Time Series Scenario Data")
    print("=" * 60)
    
    # Generate scenarios
    print("\n📊 Generating scenarios...")
    drift_data = generate_gradual_drift_scenario()
    spike_data = generate_sudden_spike_scenario()
    oscillating_data = generate_oscillating_pattern_scenario()
    
    # Combine all scenarios
    all_scenarios = drift_data + spike_data + oscillating_data
    
    print(f"✓ Gradual Drift: {len(drift_data)} readings (CMP_TOOL_01)")
    print(f"✓ Sudden Spike: {len(spike_data)} readings (ETCH_01)")
    print(f"✓ Oscillating Pattern: {len(oscillating_data)} readings (CMP_TOOL_02)")
    print(f"✓ Total: {len(all_scenarios)} readings")
    
    # Generate metadata
    metadata = generate_scenario_metadata()
    
    # Save scenario data
    output_file = "scenario_time_series.json"
    with open(output_file, 'w') as f:
        json.dump(all_scenarios, f, indent=2, default=str)
    
    print(f"\n💾 Saved sensor data to: {output_file}")
    
    # Save metadata
    metadata_file = "scenario_metadata.json"
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"💾 Saved metadata to: {metadata_file}")
    
    # Print statistics
    print("\n📈 Statistics:")
    for scenario in metadata:
        print(f"\n  {scenario['title']}:")
        print(f"    - ID: {scenario['scenario_id']}")
        print(f"    - Equipment: {scenario['equipment_id']}")
        print(f"    - Pattern: {scenario['pattern_type']}")
        print(f"    - Anomaly: minutes {scenario['anomaly_window']['start_minute']}-{scenario['anomaly_window']['end_minute']}")
        print(f"    - Peak: {scenario['anomaly_window']['peak_value']} particles at minute {scenario['anomaly_window']['peak_minute']}")
        print(f"    - Root Cause: {scenario['root_cause']}")
    
    print("\n" + "=" * 60)
    print("✅ Scenario generation complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Run: uv run python scripts/seed_scenarios.py")
    print("2. Test: curl http://localhost:8000/ai-agents/scenarios")
    print("3. Analyze: curl -X POST http://localhost:8000/ai-agents/analyze-scenario/gradual_drift")


if __name__ == "__main__":
    main()

