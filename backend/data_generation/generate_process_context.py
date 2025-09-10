#!/usr/bin/env python3
"""
Generate process context data including slurry batches, etch recipes, and reticles.
Links certain batches/recipes to defect patterns for correlation.
"""

import json
import random
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any


def generate_slurry_batches(count: int = 50) -> List[Dict[str, Any]]:
    """
    Generate slurry batch data with some problematic batches.
    
    Args:
        count: Number of batches to generate
        
    Returns:
        List of slurry batch records
    """
    batches = []
    manufacturers = ["ChemCorp", "SlurryTech", "PureFlow", "NanoSlurry"]
    compositions = ["Silica-based", "Ceria-based", "Alumina-based", "Diamond"]
    
    # Mark specific batches as problematic (10% of batches)
    problematic_indices = random.sample(range(count), k=int(count * 0.1))
    
    for i in range(count):
        batch_id = f"SB_2025_{i+1:03d}"
        is_problematic = i in problematic_indices
        
        # Base values
        manufacturer = random.choice(manufacturers)
        composition = random.choice(compositions)
        particle_size = random.randint(80, 150)
        ph_level = round(random.uniform(9.5, 11.0), 1)
        
        # Problematic batches have issues
        if is_problematic:
            large_particle_count = random.randint(25, 50)  # High contamination
            qc_status = "marginal"
            issues = [
                {
                    "date": (datetime.now() - timedelta(days=random.randint(1, 10))).isoformat() + "Z",
                    "description": random.choice([
                        "Elevated large particle count detected",
                        "Viscosity outside specification",
                        "pH drift observed during storage",
                        "Contamination suspected"
                    ]),
                    "severity": random.choice(["medium", "high"])
                }
            ]
        else:
            large_particle_count = random.randint(5, 15)  # Normal range
            qc_status = "passed"
            issues = []
        
        batch = {
            "_id": batch_id,
            "context_type": "slurry_batch",
            "context_id": batch_id,
            "slurry_details": {
                "manufacturer": manufacturer,
                "composition": composition,
                "particle_size_nm": particle_size,
                "ph_level": ph_level,
                "manufacture_date": (datetime.now() - timedelta(days=random.randint(30, 90))).isoformat() + "Z",
                "expiry_date": (datetime.now() + timedelta(days=random.randint(30, 180))).isoformat() + "Z",
                "qc_status": qc_status,
                "large_particle_count": large_particle_count
            },
            "usage_history": [
                {
                    "timestamp": (datetime.now() - timedelta(days=random.randint(1, 20))).isoformat() + "Z",
                    "equipment_id": f"CMP_TOOL_{random.randint(1, 2):02d}",
                    "wafers_processed": random.randint(10, 50),
                    "issues_reported": is_problematic and random.random() > 0.5
                }
                for _ in range(random.randint(1, 5))
            ],
            "known_issues": issues,
            "is_problematic": is_problematic  # Flag for correlation
        }
        
        batches.append(batch)
    
    return batches


def generate_etch_recipes(count: int = 20) -> List[Dict[str, Any]]:
    """
    Generate etch recipe data with some causing issues.
    
    Args:
        count: Number of recipes to generate
        
    Returns:
        List of etch recipe records
    """
    recipes = []
    process_types = ["Oxide Etch", "Poly Etch", "Metal Etch", "Nitride Etch"]
    gas_mixtures = {
        "Oxide Etch": ["CF4", "CHF3", "O2"],
        "Poly Etch": ["Cl2", "HBr", "O2"],
        "Metal Etch": ["BCl3", "Cl2", "Ar"],
        "Nitride Etch": ["SF6", "O2", "Ar"]
    }
    
    # Mark specific recipes as problematic (10% of recipes)
    problematic_indices = random.sample(range(count), k=max(2, int(count * 0.1)))
    
    for i in range(count):
        recipe_id = f"ETCH_RECIPE_{i+1:02d}"
        process_type = random.choice(process_types)
        is_problematic = i in problematic_indices
        
        # Recipe parameters
        if is_problematic:
            # Problematic recipes have parameter drift
            rf_power = random.randint(1400, 1800)  # Outside normal range
            pressure = round(random.uniform(15, 50), 1)  # Unstable
            etch_rate_variance = round(random.uniform(15, 25), 1)  # High variance
            issues = ["Parameter drift detected", "Non-uniform etch rate"]
        else:
            rf_power = random.randint(1200, 1400)  # Normal range
            pressure = round(random.uniform(25, 35), 1)  # Stable
            etch_rate_variance = round(random.uniform(2, 8), 1)  # Low variance
            issues = []
        
        recipe = {
            "_id": recipe_id,
            "context_type": "etch_recipe",
            "context_id": recipe_id,
            "recipe_details": {
                "process_type": process_type,
                "rf_power_watts": rf_power,
                "chamber_pressure_mtorr": pressure,
                "temperature_c": random.randint(40, 80),
                "gas_flows": {
                    gas: random.randint(20, 100) 
                    for gas in gas_mixtures[process_type]
                },
                "etch_time_seconds": random.randint(30, 180),
                "etch_rate_nm_per_min": random.randint(50, 200),
                "etch_rate_variance_percent": etch_rate_variance,
                "selectivity": round(random.uniform(5, 20), 1)
            },
            "validation_status": "marginal" if is_problematic else "validated",
            "last_updated": (datetime.now() - timedelta(days=random.randint(1, 60))).isoformat() + "Z",
            "usage_count": random.randint(10, 500),
            "known_issues": issues,
            "is_problematic": is_problematic
        }
        
        recipes.append(recipe)
    
    return recipes


def generate_reticles(count: int = 15) -> List[Dict[str, Any]]:
    """
    Generate reticle/mask data for lithography.
    
    Args:
        count: Number of reticles to generate
        
    Returns:
        List of reticle records
    """
    reticles = []
    layers = ["POLY", "METAL1", "METAL2", "VIA1", "VIA2", "CONTACT"]
    
    for i in range(count):
        reticle_id = f"RETICLE_{i+1:03d}"
        layer = random.choice(layers)
        
        # Reticle condition affects yield
        usage_count = random.randint(100, 5000)
        if usage_count > 4000:
            condition = "worn"
            defect_count = random.randint(5, 15)
            issues = ["Particle contamination", "Chrome peeling at edges"]
        elif usage_count > 2000:
            condition = "good"
            defect_count = random.randint(1, 5)
            issues = []
        else:
            condition = "excellent"
            defect_count = 0
            issues = []
        
        reticle = {
            "_id": reticle_id,
            "context_type": "reticle",
            "context_id": reticle_id,
            "reticle_details": {
                "layer": layer,
                "feature_size_nm": random.choice([7, 10, 14, 22]),
                "pattern_type": random.choice(["dense", "isolated", "mixed"]),
                "chrome_type": random.choice(["binary", "PSM", "CPL"]),
                "pellicle_installed": random.random() > 0.3,
                "manufacture_date": (datetime.now() - timedelta(days=random.randint(180, 720))).isoformat() + "Z"
            },
            "inspection_data": {
                "last_inspection": (datetime.now() - timedelta(days=random.randint(1, 30))).isoformat() + "Z",
                "defect_count": defect_count,
                "particle_count": random.randint(0, 20),
                "transmission_uniformity": round(random.uniform(98, 100), 1),
                "condition": condition
            },
            "usage_statistics": {
                "total_exposures": usage_count,
                "wafers_processed": usage_count * 25,
                "last_used": (datetime.now() - timedelta(days=random.randint(0, 7))).isoformat() + "Z"
            },
            "known_issues": issues
        }
        
        reticles.append(reticle)
    
    return reticles


def main():
    """Generate and save process context data."""
    print("Generating process context data...")
    
    # Generate all context data
    slurry_batches = generate_slurry_batches(50)
    etch_recipes = generate_etch_recipes(20)
    reticles = generate_reticles(15)
    
    # Combine all context data
    process_context = slurry_batches + etch_recipes + reticles
    
    # Save process context data
    output_file = "process_context.json"
    with open(output_file, 'w') as f:
        json.dump(process_context, f, indent=2)
    
    print(f"✓ Generated {len(slurry_batches)} slurry batches")
    print(f"✓ Generated {len(etch_recipes)} etch recipes")
    print(f"✓ Generated {len(reticles)} reticles")
    print(f"✓ Total: {len(process_context)} process context records")
    print(f"✓ Saved to {output_file}")
    
    # Print statistics
    problematic_batches = sum(1 for b in slurry_batches if b.get('is_problematic', False))
    problematic_recipes = sum(1 for r in etch_recipes if r.get('is_problematic', False))
    worn_reticles = sum(1 for r in reticles if r['inspection_data']['condition'] == 'worn')
    
    print("\nStatistics:")
    print(f"  - Problematic slurry batches: {problematic_batches} "
          f"({problematic_batches/len(slurry_batches)*100:.1f}%)")
    print(f"  - Problematic etch recipes: {problematic_recipes} "
          f"({problematic_recipes/len(etch_recipes)*100:.1f}%)")
    print(f"  - Worn reticles: {worn_reticles} "
          f"({worn_reticles/len(reticles)*100:.1f}%)")
    
    # Sample problematic items
    print("\nProblematic items for correlation:")
    for batch in slurry_batches[:3]:
        if batch.get('is_problematic'):
            print(f"  - Slurry {batch['context_id']}: "
                  f"{batch['slurry_details']['large_particle_count']} large particles")
    for recipe in etch_recipes[:3]:
        if recipe.get('is_problematic'):
            print(f"  - Recipe {recipe['context_id']}: "
                  f"{recipe['recipe_details']['etch_rate_variance_percent']:.1f}% variance")


if __name__ == "__main__":
    main()