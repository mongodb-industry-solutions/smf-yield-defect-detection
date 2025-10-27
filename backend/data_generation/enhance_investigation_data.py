#!/usr/bin/env python3
"""
Enhanced Investigation Data Generator
Adds enriched fields to process_context and wafer_defects while preserving backward compatibility
"""

import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import uuid

# Load scenario metadata for alignment
def load_scenario_metadata() -> Dict[str, Any]:
    """Load scenario metadata for generating scenario-specific data"""
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))

    try:
        with open(os.path.join(script_dir, 'scenario_metadata.json'), 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Warning: scenario_metadata.json not found, using defaults")
        return {
            "gradual_drift": {
                "equipment_id": "CMP_TOOL_01",
                "duration_minutes": 120,
                "pattern": "progressive degradation"
            },
            "sudden_spike": {
                "equipment_id": "ETCH_01",
                "duration_minutes": 60,
                "pattern": "abrupt contamination"
            },
            "oscillating_pattern": {
                "equipment_id": "CMP_TOOL_02",
                "duration_minutes": 120,
                "pattern": "cyclic variation"
            }
        }

# ============== ENHANCEMENT FUNCTIONS FOR EXISTING DATA ==============

def enhance_existing_process_context(data: List[Dict]) -> List[Dict]:
    """
    Add new fields to existing process_context records without breaking structure
    Preserves ALL original fields, only adds enhancements
    """
    enhanced_data = []
    scenario_metadata = load_scenario_metadata()

    for item in data:
        # Create a deep copy to preserve original
        enhanced_item = json.loads(json.dumps(item))

        # Only enhance problematic items
        if item.get('is_problematic', False):
            context_type = item.get('context_type')

            if context_type == 'slurry_batch':
                # Add scenario context based on existing issues
                enhanced_item['scenario_context'] = generate_scenario_context_for_slurry(
                    item, scenario_metadata
                )

                # Enhance existing issues with specific details
                enhanced_item['enhanced_issues'] = enhance_slurry_issues(item)

                # Add impact metrics
                enhanced_item['impact_metrics'] = generate_impact_metrics(item)

            elif context_type == 'etch_recipe':
                # Add drift analysis for recipes
                enhanced_item['drift_analysis'] = generate_drift_analysis(item)

                # Link to scenarios if problematic
                enhanced_item['scenario_linkage'] = generate_recipe_scenario_linkage(item)

            elif context_type == 'reticle':
                # Add defect analysis for reticles
                enhanced_item['defect_analysis'] = generate_reticle_defect_analysis(item)

        enhanced_data.append(enhanced_item)

    return enhanced_data

def generate_scenario_context_for_slurry(item: Dict, metadata: Dict) -> Dict:
    """Generate scenario context based on slurry batch issues"""
    # Map issue descriptions to scenarios
    issue_desc = ""
    if item.get('known_issues'):
        issue_desc = item['known_issues'][0].get('description', '').lower()

    if 'particle' in issue_desc:
        scenario = random.choice(['gradual_drift', 'sudden_spike'])
    elif 'ph drift' in issue_desc:
        scenario = 'gradual_drift'
    elif 'contamination' in issue_desc:
        scenario = 'sudden_spike'
    else:
        scenario = random.choice(list(metadata.keys()))

    # Generate temporal alignment
    base_time = datetime.now() - timedelta(days=random.randint(1, 30))

    return {
        "scenario_id": scenario,
        "correlation_confidence": round(random.uniform(0.75, 0.95), 2),
        "temporal_alignment": f"{base_time.isoformat()}Z to {(base_time + timedelta(hours=2)).isoformat()}Z",
        "detection_lag_minutes": random.randint(5, 30)
    }

def enhance_slurry_issues(item: Dict) -> Dict:
    """Enhance generic issue descriptions with specific details"""
    known_issues = item.get('known_issues', [])

    if not known_issues:
        return {}

    issue = known_issues[0]
    desc = issue.get('description', '').lower()

    # Generate specific root causes based on generic descriptions
    if 'contamination' in desc:
        contaminant = random.choice(['Iron', 'Copper', 'Organic residue', 'Silicon dioxide'])
        level = random.randint(100, 500)
        return {
            "root_cause": f"{contaminant} contamination {level}ppb from supplier tank",
            "detection_method": "ICP-MS analysis during incoming QC",
            "affected_metrics": ["particle_count", "defect_density", "yield"],
            "remediation_taken": "Batch quarantined, supplier notified, tank cleaned",
            "contamination_level_ppb": level,
            "spec_limit_ppb": 50
        }

    elif 'particle' in desc:
        size = random.randint(100, 300)
        count = random.randint(1000, 5000)
        return {
            "root_cause": f"Filter breakthrough causing {size}nm particles",
            "detection_method": "Liquid particle counter alert",
            "affected_metrics": ["particle_count", "scratch_density"],
            "remediation_taken": "Filter replaced, system flushed",
            "particle_size_nm": size,
            "particle_count_per_ml": count
        }

    elif 'ph drift' in desc:
        ph_change = round(random.uniform(0.3, 0.8), 1)
        return {
            "root_cause": f"Chemical degradation during storage, pH shifted by {ph_change}",
            "detection_method": "Routine pH monitoring",
            "affected_metrics": ["etch_rate", "selectivity", "uniformity"],
            "remediation_taken": "pH adjustment attempted, batch marked for limited use",
            "ph_drift_value": ph_change,
            "days_since_manufacture": random.randint(30, 90)
        }

    else:
        return {
            "root_cause": "Under investigation",
            "detection_method": "Process excursion alert",
            "affected_metrics": ["yield"],
            "remediation_taken": "Batch on hold pending analysis"
        }

def generate_impact_metrics(item: Dict) -> Dict:
    """Generate impact metrics based on issue severity"""
    severity = 'medium'
    if item.get('known_issues'):
        severity = item['known_issues'][0].get('severity', 'medium')

    if severity == 'high':
        yield_impact = round(random.uniform(-15, -8), 1)
        wafer_count = random.randint(40, 100)
    elif severity == 'medium':
        yield_impact = round(random.uniform(-8, -3), 1)
        wafer_count = random.randint(20, 40)
    else:
        yield_impact = round(random.uniform(-3, -1), 1)
        wafer_count = random.randint(5, 20)

    return {
        "yield_degradation": yield_impact,
        "affected_wafer_count": wafer_count,
        "defect_signature": random.choice(["clustered_particles", "edge_defects", "random_particles"]),
        "estimated_revenue_impact_k": round(abs(yield_impact) * wafer_count * 0.5, 1)
    }

def generate_drift_analysis(item: Dict) -> Dict:
    """Generate drift analysis for recipes"""
    recipe_details = item.get('recipe_details', {})

    return {
        "rf_power_drift": random.randint(-50, 150),
        "pressure_stability": round(random.uniform(0.6, 0.95), 2),
        "temperature_drift_c": round(random.uniform(-2, 2), 1),
        "last_calibration": (datetime.now() - timedelta(days=random.randint(5, 30))).isoformat() + "Z",
        "drift_rate_per_day": round(random.uniform(0.1, 2), 2),
        "within_spec": random.choice([True, False])
    }

def generate_recipe_scenario_linkage(item: Dict) -> Dict:
    """Generate scenario linkage for problematic recipes"""
    return {
        "scenario_id": "oscillating_pattern",
        "parameter_cycling": True,
        "cycle_period_minutes": random.randint(15, 30),
        "amplitude_percent": random.randint(5, 15),
        "affected_parameter": random.choice(["rf_power", "pressure", "gas_flow"])
    }

def generate_reticle_defect_analysis(item: Dict) -> Dict:
    """Generate defect analysis for reticles"""
    return {
        "defect_type": random.choice(["chrome_defect", "pellicle_damage", "particle_contamination"]),
        "defect_count": random.randint(1, 10),
        "critical_defects": random.randint(0, 3),
        "defect_size_nm": random.randint(50, 200),
        "impact_on_yield": round(random.uniform(-5, -1), 1)
    }

# ============== WAFER DEFECTS ENHANCEMENT ==============

def enhance_wafer_defects(wafers: List[Dict]) -> List[Dict]:
    """
    Enhance wafer defects with equipment_id and correlation fields
    Preserves ALL original fields
    """
    enhanced_wafers = []

    for wafer in wafers:
        # Deep copy to preserve original
        enhanced_wafer = json.loads(json.dumps(wafer))

        # Fill missing equipment_id based on lot pattern
        if enhanced_wafer.get('equipment_id') is None:
            enhanced_wafer['equipment_id'] = map_lot_to_equipment(enhanced_wafer.get('lot_id', ''))

        # Add process context
        enhanced_wafer['process_context'] = generate_wafer_process_context(enhanced_wafer)

        # Add excursion correlation
        enhanced_wafer['excursion_correlation'] = generate_excursion_correlation(enhanced_wafer)

        # Add enhanced pattern analysis
        pattern = enhanced_wafer.get('defect_summary', {}).get('defect_pattern', 'random')
        enhanced_wafer['enhanced_pattern_analysis'] = generate_pattern_analysis(pattern)

        enhanced_wafers.append(enhanced_wafer)

    return enhanced_wafers

def map_lot_to_equipment(lot_id: str) -> str:
    """Map lot_id to equipment_id based on patterns"""
    if not lot_id:
        return random.choice(['CMP_TOOL_01', 'CMP_TOOL_02', 'ETCH_01', 'ETCH_02'])

    # Extract lot number
    try:
        lot_num = int(lot_id.split('_')[-1])
    except (ValueError, IndexError):
        lot_num = 1

    # Map based on lot number patterns
    if lot_num % 4 == 0:
        return 'CMP_TOOL_01'
    elif lot_num % 4 == 1:
        return 'CMP_TOOL_02'
    elif lot_num % 4 == 2:
        return 'ETCH_01'
    else:
        return 'ETCH_02'

def generate_wafer_process_context(wafer: Dict) -> Dict:
    """Generate process context for wafer"""
    lot_num = 1
    try:
        lot_num = int(wafer.get('lot_id', 'LOT_2025_001').split('_')[-1])
    except:
        pass

    # Generate correlated batch/recipe IDs
    slurry_batch_num = 1 + (lot_num % 50)
    recipe_num = 1 + (lot_num % 20)

    return {
        "slurry_batch": f"SB_2025_{slurry_batch_num:03d}",
        "recipe_id": f"ETCH_RECIPE_{recipe_num:02d}",
        "process_timestamp": (datetime.now() - timedelta(hours=random.randint(1, 48))).isoformat() + "Z",
        "chamber_clean_count": random.randint(100, 500),
        "process_step": random.choice(["CMP", "ETCH", "DEPOSITION", "LITHOGRAPHY"])
    }

def generate_excursion_correlation(wafer: Dict) -> Dict:
    """Generate excursion correlation data"""
    base_time = datetime.now() - timedelta(hours=random.randint(1, 24))
    alert_id = f"ALT-{base_time.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"

    return {
        "linked_excursion": alert_id,
        "temporal_offset_minutes": random.randint(5, 60),
        "confidence": round(random.uniform(0.7, 0.95), 2),
        "correlation_method": random.choice(["temporal", "pattern_matching", "equipment_trace"]),
        "excursion_type": random.choice(["particle_excursion", "rf_power_drift", "temperature_excursion"])
    }

def generate_pattern_analysis(pattern_type: str) -> Dict:
    """Generate enhanced pattern analysis"""
    analysis = {
        "pattern_confidence": round(random.uniform(0.85, 0.98), 2),
        "classification_method": "CNN_model_v2.1"
    }

    if pattern_type == 'clustered':
        analysis.update({
            "cluster_count": random.randint(3, 12),
            "cluster_size_avg_mm": round(random.uniform(0.5, 2), 1),
            "radial_distribution": False,
            "edge_concentration": random.choice([True, False]),
            "center_concentration": random.choice([True, False])
        })
    elif pattern_type == 'edge':
        analysis.update({
            "edge_width_mm": round(random.uniform(2, 5), 1),
            "edge_uniformity": round(random.uniform(0.6, 0.9), 2),
            "radial_distribution": True,
            "edge_concentration": True,
            "center_concentration": False
        })
    else:  # random
        analysis.update({
            "defect_density_per_cm2": round(random.uniform(0.1, 2), 2),
            "uniformity_index": round(random.uniform(0.4, 0.7), 2),
            "radial_distribution": False,
            "edge_concentration": False,
            "center_concentration": False
        })

    return analysis

# ============== NEW PROBLEMATIC ITEMS GENERATION ==============

def generate_new_problematic_slurry_batches(count: int = 30) -> List[Dict]:
    """
    Generate new problematic slurry batches with full structure
    IDs: SB_2025_100 to SB_2025_129
    """
    batches = []
    scenarios = ['gradual_drift'] * 10 + ['sudden_spike'] * 10 + ['oscillating_pattern'] * 10
    random.shuffle(scenarios)

    for i in range(count):
        batch_id = f"SB_2025_{100 + i:03d}"
        scenario = scenarios[i] if i < len(scenarios) else random.choice(['gradual_drift', 'sudden_spike'])

        # Generate base structure (matching original schema)
        batch = {
            "_id": batch_id,
            "context_type": "slurry_batch",
            "context_id": batch_id,
            "slurry_details": {
                "manufacturer": random.choice(["PureFlow", "ChemCorp", "NanoSlurry Inc", "Advanced Materials"]),
                "composition": random.choice(["Ceria-based", "Silica-based", "Alumina-based"]),
                "particle_size_nm": random.randint(80, 150),
                "ph_level": round(random.uniform(9.5, 11.5), 1),
                "manufacture_date": (datetime.now() - timedelta(days=random.randint(30, 180))).isoformat() + "Z",
                "expiry_date": (datetime.now() + timedelta(days=random.randint(30, 180))).isoformat() + "Z",
                "qc_status": random.choice(["passed", "conditional", "failed"]),
                "large_particle_count": random.randint(5, 50)
            },
            "usage_history": generate_usage_history(scenario),
            "known_issues": generate_scenario_specific_issues(scenario),
            "is_problematic": True
        }

        # Add enhancement fields
        batch['scenario_context'] = {
            "scenario_id": scenario,
            "correlation_confidence": round(random.uniform(0.8, 0.95), 2),
            "temporal_alignment": generate_temporal_alignment(scenario),
            "detection_lag_minutes": random.randint(5, 45)
        }

        batch['enhanced_issues'] = generate_scenario_specific_enhanced_issues(scenario)
        batch['impact_metrics'] = generate_scenario_impact_metrics(scenario)

        batches.append(batch)

    return batches

def generate_usage_history(scenario: str) -> List[Dict]:
    """Generate usage history aligned with scenario"""
    history = []
    equipment_map = {
        'gradual_drift': 'CMP_TOOL_01',
        'sudden_spike': 'ETCH_01',
        'oscillating_pattern': 'CMP_TOOL_02'
    }

    primary_equipment = equipment_map.get(scenario, 'CMP_TOOL_01')

    # Generate 2-5 usage entries
    for j in range(random.randint(2, 5)):
        base_time = datetime.now() - timedelta(days=random.randint(1, 30))
        history.append({
            "timestamp": (base_time + timedelta(hours=j*8)).isoformat() + "Z",
            "equipment_id": primary_equipment if j == 0 else random.choice([primary_equipment, 'CMP_TOOL_02', 'ETCH_01']),
            "wafers_processed": random.randint(10, 50),
            "issues_reported": j == 0  # First usage shows issues
        })

    return history

def generate_scenario_specific_issues(scenario: str) -> List[Dict]:
    """Generate known issues specific to scenario"""
    issue_templates = {
        'gradual_drift': [
            "Progressive particle count increase observed",
            "Viscosity drift detected during extended use",
            "Filter loading causing contamination buildup"
        ],
        'sudden_spike': [
            "Sudden contamination detected - source under investigation",
            "Abrupt particle spike - possible tank breach",
            "Contamination event during transfer"
        ],
        'oscillating_pattern': [
            "Cyclic quality variation observed",
            "Periodic contamination pattern detected",
            "Mixing inconsistency causing oscillations"
        ]
    }

    descriptions = issue_templates.get(scenario, ["Generic quality issue"])

    return [{
        "date": (datetime.now() - timedelta(days=random.randint(1, 10))).isoformat() + "Z",
        "description": random.choice(descriptions),
        "severity": "high" if scenario == 'sudden_spike' else random.choice(["medium", "high"])
    }]

def generate_scenario_specific_enhanced_issues(scenario: str) -> Dict:
    """Generate enhanced issues with specific root causes per scenario"""
    templates = {
        'gradual_drift': {
            "root_cause": f"Filter degradation causing progressive contamination, particle count increased from 800 to 1200/ml over 2 hours",
            "detection_method": "Trend analysis of inline particle counter",
            "affected_metrics": ["particle_count", "defect_density", "yield"],
            "remediation_taken": "Filter replacement scheduled, batch limited to non-critical lots",
            "degradation_rate": "150 particles/ml per hour",
            "time_to_critical": "4 hours"
        },
        'sudden_spike': {
            "root_cause": f"Tank contamination event at {datetime.now().isoformat()}Z, iron contamination 2800ppb",
            "detection_method": "Inline contamination sensor alert",
            "affected_metrics": ["particle_count", "metal_contamination", "yield"],
            "remediation_taken": "Immediate quarantine, tank isolated, emergency cleaning initiated",
            "contamination_level_ppb": 2800,
            "time_to_detection_minutes": 5
        },
        'oscillating_pattern': {
            "root_cause": "Pump cavitation causing periodic mixing variations, 20-minute cycle",
            "detection_method": "Statistical process control chart violation",
            "affected_metrics": ["uniformity", "particle_distribution", "removal_rate"],
            "remediation_taken": "Pump maintenance scheduled, flow rate adjusted",
            "cycle_period_minutes": 20,
            "amplitude_variation_percent": 15
        }
    }

    return templates.get(scenario, {
        "root_cause": "Under investigation",
        "detection_method": "Process excursion",
        "affected_metrics": ["yield"],
        "remediation_taken": "Batch on hold"
    })

def generate_scenario_impact_metrics(scenario: str) -> Dict:
    """Generate impact metrics specific to scenario"""
    impacts = {
        'gradual_drift': {
            "yield_degradation": -12.5,
            "affected_wafer_count": 75,
            "defect_signature": "progressive_clustering",
            "estimated_revenue_impact_k": 187.5,
            "progression_type": "linear",
            "final_yield": 82.5
        },
        'sudden_spike': {
            "yield_degradation": -20.0,
            "affected_wafer_count": 25,
            "defect_signature": "sudden_contamination",
            "estimated_revenue_impact_k": 250.0,
            "response_time_minutes": 15,
            "containment_success": True
        },
        'oscillating_pattern': {
            "yield_degradation": -8.0,
            "affected_wafer_count": 100,
            "defect_signature": "cyclic_variation",
            "estimated_revenue_impact_k": 200.0,
            "cycles_observed": 6,
            "peak_to_peak_variation": 10.0
        }
    }

    base = impacts.get(scenario, {
        "yield_degradation": -5.0,
        "affected_wafer_count": 20,
        "defect_signature": "unknown",
        "estimated_revenue_impact_k": 50.0
    })

    # Add some variation
    base["yield_degradation"] = round(base["yield_degradation"] + random.uniform(-2, 2), 1)
    base["affected_wafer_count"] = base["affected_wafer_count"] + random.randint(-10, 10)

    return base

def generate_temporal_alignment(scenario: str) -> str:
    """Generate temporal alignment for scenario"""
    base_time = datetime.now() - timedelta(days=random.randint(1, 7))

    duration_map = {
        'gradual_drift': 120,  # 2 hours
        'sudden_spike': 30,    # 30 minutes
        'oscillating_pattern': 180  # 3 hours
    }

    duration = duration_map.get(scenario, 60)
    end_time = base_time + timedelta(minutes=duration)

    return f"{base_time.isoformat()}Z to {end_time.isoformat()}Z"

def generate_new_problematic_recipes(count: int = 20) -> List[Dict]:
    """
    Generate new problematic recipes with full structure
    IDs: ETCH_RECIPE_50 to ETCH_RECIPE_69
    """
    recipes = []

    for i in range(count):
        recipe_id = f"ETCH_RECIPE_{50 + i:02d}"

        # Base structure matching original schema
        recipe = {
            "_id": recipe_id,
            "context_type": "etch_recipe",
            "context_id": recipe_id,
            "recipe_details": {
                "process_type": random.choice(["Oxide Etch", "Poly Etch", "Metal Etch"]),
                "rf_power_watts": random.randint(1000, 1500),
                "chamber_pressure_mtorr": round(random.uniform(25, 40), 1),
                "temperature_c": random.randint(40, 80),
                "gas_flows": {
                    "CF4": random.randint(20, 80),
                    "CHF3": random.randint(30, 100),
                    "O2": random.randint(10, 50)
                },
                "etch_time_seconds": random.randint(120, 200),
                "etch_rate_nm_per_min": random.randint(100, 200),
                "etch_rate_variance_percent": round(random.uniform(2, 10), 1),
                "selectivity": round(random.uniform(5, 20), 1)
            },
            "validation_status": random.choice(["validated", "conditional", "needs_revalidation"]),
            "last_updated": (datetime.now() - timedelta(days=random.randint(1, 60))).isoformat() + "Z",
            "usage_count": random.randint(50, 500),
            "known_issues": [
                {
                    "date": (datetime.now() - timedelta(days=random.randint(1, 30))).isoformat() + "Z",
                    "description": "Parameter drift observed during extended runs",
                    "severity": random.choice(["medium", "high"])
                }
            ] if i % 3 == 0 else [],
            "is_problematic": i % 3 == 0  # Every 3rd recipe is problematic
        }

        # Add enhancement fields for problematic recipes
        if recipe['is_problematic']:
            recipe['drift_analysis'] = {
                "rf_power_drift": random.randint(50, 200),
                "pressure_stability": round(random.uniform(0.5, 0.7), 2),
                "temperature_drift_c": round(random.uniform(2, 5), 1),
                "last_calibration": (datetime.now() - timedelta(days=random.randint(10, 60))).isoformat() + "Z",
                "drift_rate_per_day": round(random.uniform(1, 5), 2),
                "within_spec": False
            }

            recipe['scenario_linkage'] = {
                "scenario_id": "oscillating_pattern",
                "parameter_cycling": True,
                "cycle_period_minutes": random.randint(15, 30),
                "amplitude_percent": random.randint(10, 20),
                "affected_parameter": random.choice(["rf_power", "pressure", "gas_flow_CF4"])
            }

        recipes.append(recipe)

    return recipes

# ============== MAIN EXECUTION ==============

def main():
    """Main execution function"""
    print("=" * 60)
    print("Investigation Data Enhancement Script")
    print("=" * 60)

    # Load existing data
    print("\n1. Loading existing data...")

    import os

    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))

    try:
        with open(os.path.join(script_dir, 'process_context.json'), 'r') as f:
            existing_process_context = json.load(f)
        print(f"   Loaded {len(existing_process_context)} process_context items")
    except FileNotFoundError:
        print("   ERROR: process_context.json not found")
        existing_process_context = []

    try:
        with open(os.path.join(script_dir, 'wafer_defects.json'), 'r') as f:
            existing_wafer_defects = json.load(f)
        print(f"   Loaded {len(existing_wafer_defects)} wafer_defects items")
    except FileNotFoundError:
        print("   ERROR: wafer_defects.json not found")
        existing_wafer_defects = []

    # Enhance existing data
    print("\n2. Enhancing existing data (backward compatible)...")
    enhanced_process_context = enhance_existing_process_context(existing_process_context)
    enhanced_wafer_defects = enhance_wafer_defects(existing_wafer_defects)

    print(f"   Enhanced {len(enhanced_process_context)} process_context items")
    print(f"   Enhanced {len(enhanced_wafer_defects)} wafer_defects items")

    # Generate new problematic items
    print("\n3. Generating new problematic items...")
    new_slurry_batches = generate_new_problematic_slurry_batches(30)
    new_recipes = generate_new_problematic_recipes(20)

    print(f"   Generated {len(new_slurry_batches)} new problematic slurry batches")
    print(f"   Generated {len(new_recipes)} new problematic recipes")

    # Combine data
    print("\n4. Combining data...")
    final_process_context = enhanced_process_context + new_slurry_batches + new_recipes
    final_wafer_defects = enhanced_wafer_defects

    # Save enhanced data
    print("\n5. Saving enhanced data...")

    # Save to enhanced directory to preserve originals
    enhanced_dir = os.path.join(script_dir, 'enhanced')
    os.makedirs(enhanced_dir, exist_ok=True)

    with open(os.path.join(enhanced_dir, 'process_context_enhanced.json'), 'w') as f:
        json.dump(final_process_context, f, indent=2)
    print(f"   Saved {len(final_process_context)} items to enhanced/process_context_enhanced.json")

    with open(os.path.join(enhanced_dir, 'wafer_defects_enhanced.json'), 'w') as f:
        json.dump(final_wafer_defects, f, indent=2)
    print(f"   Saved {len(final_wafer_defects)} items to enhanced/wafer_defects_enhanced.json")

    # Generate summary statistics
    print("\n6. Summary Statistics:")
    print(f"   Total process_context items: {len(final_process_context)}")

    problematic_count = sum(1 for item in final_process_context if item.get('is_problematic', False))
    print(f"   Problematic items: {problematic_count}")

    enhanced_count = sum(1 for item in final_process_context if 'scenario_context' in item or 'enhanced_issues' in item)
    print(f"   Items with enhancements: {enhanced_count}")

    wafers_with_equipment = sum(1 for w in final_wafer_defects if w.get('equipment_id') is not None)
    print(f"   Wafers with equipment_id: {wafers_with_equipment}/{len(final_wafer_defects)}")

    print("\n✅ Enhancement complete!")
    print("   Original data preserved in original files")
    print("   Enhanced data saved in enhanced/ directory")

if __name__ == "__main__":
    main()