#!/usr/bin/env python3
"""
Generate historical knowledge base including RCA reports and troubleshooting guides.
This data will be used for RAG (Retrieval Augmented Generation) in later phases.
"""

import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any


def generate_rca_reports(count: int = 50) -> List[Dict[str, Any]]:
    """
    Generate Root Cause Analysis reports for historical incidents.
    
    Args:
        count: Number of RCA reports to generate
        
    Returns:
        List of RCA report documents
    """
    reports = []
    
    # Templates for different types of issues
    root_causes = [
        {
            "type": "particle_contamination",
            "causes": [
                "Degraded slurry filter allowing large particles through",
                "Chamber contamination from previous process",
                "Worn pad conditioning disk shedding particles",
                "Slurry line contamination from improper cleaning",
                "Particle shedding from degraded chamber components"
            ],
            "factors": [
                "Extended run time without preventive maintenance",
                "Delayed filter replacement schedule",
                "Inadequate chamber cleaning procedure",
                "Slurry batch quality variation",
                "Environmental control system failure"
            ],
            "actions": [
                "Replace slurry filter immediately",
                "Perform full chamber wet clean",
                "Replace pad conditioning disk",
                "Flush and clean slurry delivery lines",
                "Update PM schedule to prevent recurrence"
            ]
        },
        {
            "type": "etch_uniformity",
            "causes": [
                "RF power distribution imbalance",
                "Gas flow controller drift",
                "Chamber pressure instability",
                "Electrode erosion causing plasma non-uniformity",
                "Temperature gradient across wafer"
            ],
            "factors": [
                "Aging RF generator components",
                "MFC calibration drift",
                "Vacuum pump performance degradation",
                "Insufficient electrode cooling",
                "Chiller temperature fluctuation"
            ],
            "actions": [
                "Recalibrate RF power system",
                "Replace or recalibrate MFCs",
                "Service vacuum pump and check for leaks",
                "Inspect and clean electrodes",
                "Verify chiller operation and setpoints"
            ]
        },
        {
            "type": "lithography_defects",
            "causes": [
                "Reticle contamination with particles",
                "Focus drift during exposure",
                "Overlay misalignment between layers",
                "Resist thickness variation",
                "Light source intensity fluctuation"
            ],
            "factors": [
                "Improper reticle handling procedures",
                "Autofocus system calibration error",
                "Stage positioning accuracy degradation",
                "Resist coating uniformity issues",
                "Lamp aging beyond specification"
            ],
            "actions": [
                "Clean or replace contaminated reticle",
                "Recalibrate autofocus system",
                "Perform stage maintenance and calibration",
                "Optimize resist spin coating parameters",
                "Replace exposure lamp"
            ]
        }
    ]
    
    equipment_types = ["CMP", "ETCH", "LITHO", "CVD", "PVD"]
    
    for i in range(count):
        # Select random issue type
        issue_type = random.choice(root_causes)
        equipment = random.choice(equipment_types)
        
        # Generate timeline
        incident_date = datetime.now() - timedelta(days=random.randint(30, 365))
        
        # Select specific causes and actions
        root_cause = random.choice(issue_type["causes"])
        contributing_factors = random.sample(issue_type["factors"], k=random.randint(2, 3))
        corrective_actions = random.sample(issue_type["actions"], k=random.randint(2, 3))
        
        # Calculate impact
        wafers_affected = random.randint(25, 500)
        yield_loss = round(random.uniform(5, 25), 1)
        cost_impact = wafers_affected * yield_loss * 100  # Simplified cost calculation
        resolution_time = random.randint(2, 12)
        
        report = {
            "_id": f"RCA_{incident_date.strftime('%Y%m%d')}_{i+1:03d}",
            "document_type": "rca_report",
            "title": f"RCA: {equipment} {issue_type['type'].replace('_', ' ').title()} - {incident_date.strftime('%B %Y')}",
            "incident_date": incident_date.isoformat() + "Z",
            "created_date": (incident_date + timedelta(days=random.randint(1, 7))).isoformat() + "Z",
            
            "content": f"""
Root Cause Analysis Report
==========================

Executive Summary:
A {issue_type['type'].replace('_', ' ')} issue was detected on {equipment} equipment resulting in {yield_loss}% yield loss across {wafers_affected} wafers. The incident was resolved within {resolution_time} hours.

Timeline:
- Detection: Automated monitoring detected anomaly
- Investigation: Engineering team identified {root_cause}
- Resolution: Corrective actions implemented
- Validation: Process returned to baseline

Root Cause:
{root_cause}

Contributing Factors:
{chr(10).join(f'• {factor}' for factor in contributing_factors)}

Corrective Actions:
{chr(10).join(f'• {action}' for action in corrective_actions)}

Preventive Measures:
• Update preventive maintenance schedule
• Implement additional monitoring parameters
• Review and update operating procedures
• Conduct training for operators

Impact Assessment:
- Wafers Affected: {wafers_affected}
- Yield Loss: {yield_loss}%
- Estimated Cost Impact: ${cost_impact:,.0f}
- Resolution Time: {resolution_time} hours

Lessons Learned:
Early detection through enhanced monitoring could have reduced impact by 50%. Recommend implementing real-time particle monitoring with tighter control limits.

Recommendations:
1. Increase monitoring frequency for critical parameters
2. Establish tighter control limits for particle counts
3. Implement predictive maintenance based on tool usage
4. Regular training updates for operational staff
            """,
            
            "metadata": {
                "process_area": equipment,
                "defect_type": issue_type['type'],
                "severity": "high" if yield_loss > 15 else "medium" if yield_loss > 8 else "low",
                "resolution_time_hours": resolution_time,
                "cost_impact_usd": cost_impact,
                "effectiveness_score": round(random.uniform(0.7, 0.95), 2)
            },
            
            "findings": {
                "root_cause": root_cause,
                "contributing_factors": contributing_factors,
                "corrective_actions": corrective_actions,
                "preventive_measures": [
                    "Update PM schedule",
                    "Enhance monitoring parameters",
                    "Implement predictive analytics"
                ]
            },
            
            "tags": [equipment.lower(), issue_type['type'], "particle", "contamination", "yield_loss"],
            "author": random.choice(["John Smith", "Jane Doe", "Mike Johnson", "Sarah Williams"]),
            "related_incidents": [f"INC_2024_{random.randint(100, 999)}" for _ in range(random.randint(0, 3))]
        }
        
        reports.append(report)
    
    return reports


def generate_troubleshooting_guides(count: int = 20) -> List[Dict[str, Any]]:
    """
    Generate troubleshooting guides for common issues.
    
    Args:
        count: Number of guides to generate
        
    Returns:
        List of troubleshooting guide documents
    """
    guides = []
    
    issue_types = [
        {
            "name": "Particle Excursion",
            "symptoms": [
                "Sudden increase in particle count >1000",
                "Clustered defects on wafer maps",
                "Yield drop >10% within single lot"
            ],
            "diagnostics": [
                "Check slurry filter pressure differential",
                "Verify chamber particle sensor readings",
                "Review recent maintenance activities"
            ],
            "solutions": {
                "Slurry contamination": "Replace slurry batch and filter, flush lines",
                "Chamber contamination": "Perform wet clean and particle check",
                "Pad degradation": "Replace polishing pad and condition"
            }
        },
        {
            "name": "Etch Rate Drift",
            "symptoms": [
                "Etch rate variation >15%",
                "Non-uniform pattern across wafer",
                "Endpoint detection errors"
            ],
            "diagnostics": [
                "Verify RF power stability",
                "Check gas flow rates and ratios",
                "Measure chamber pressure stability"
            ],
            "solutions": {
                "RF power issue": "Recalibrate RF system, check matching network",
                "Gas flow problem": "Recalibrate MFCs, check for leaks",
                "Pressure instability": "Service vacuum pump, check throttle valve"
            }
        },
        {
            "name": "Overlay Error",
            "symptoms": [
                "Overlay measurement >5nm",
                "Pattern shift between layers",
                "Edge die failures"
            ],
            "diagnostics": [
                "Check stage repeatability",
                "Verify alignment mark quality",
                "Review exposure dose settings"
            ],
            "solutions": {
                "Stage drift": "Recalibrate stage, check servo motors",
                "Alignment issue": "Clean alignment marks, adjust recognition parameters",
                "Thermal expansion": "Verify temperature control, allow stabilization time"
            }
        }
    ]
    
    for i in range(count):
        issue = random.choice(issue_types)
        
        guide = {
            "_id": f"GUIDE_{i+1:03d}",
            "document_type": "troubleshooting_guide",
            "title": f"Troubleshooting Guide: {issue['name']}",
            "created_date": (datetime.now() - timedelta(days=random.randint(30, 180))).isoformat() + "Z",
            "last_updated": (datetime.now() - timedelta(days=random.randint(1, 30))).isoformat() + "Z",
            
            "content": f"""
Troubleshooting Guide: {issue['name']}
{'=' * (len(issue['name']) + 22)}

Quick Reference Guide for {issue['name']} Issues

Common Symptoms:
{chr(10).join(f'• {symptom}' for symptom in issue['symptoms'])}

Diagnostic Steps:
{chr(10).join(f'{i+1}. {diag}' for i, diag in enumerate(issue['diagnostics']))}

Potential Causes and Solutions:
{chr(10).join(f'{chr(10)}{cause}:{chr(10)}  → Solution: {solution}' for cause, solution in issue['solutions'].items())}

Escalation Criteria:
• If issue persists after initial troubleshooting
• If yield loss exceeds 15%
• If multiple tools show same symptoms

Emergency Response:
1. Stop processing immediately
2. Quarantine affected lots
3. Notify yield engineering team
4. Document all observations

Prevention Tips:
• Monitor trends daily
• Maintain control charts
• Follow PM schedule strictly
• Regular operator training

Contact Information:
• Yield Engineering: ext. 1234
• Equipment Support: ext. 5678
• Emergency: ext. 911
            """,
            
            "metadata": {
                "issue_type": issue['name'].lower().replace(' ', '_'),
                "applicable_tools": random.sample(["CMP", "ETCH", "LITHO", "CVD"], k=random.randint(1, 3)),
                "urgency_level": random.choice(["low", "medium", "high"]),
                "estimated_mttr_hours": random.randint(1, 8)
            },
            
            "tags": [tag.lower() for tag in issue['name'].split()] + ["troubleshooting", "guide"],
            "author": "Engineering Team",
            "version": f"1.{random.randint(0, 5)}"
        }
        
        guides.append(guide)
    
    return guides


def generate_best_practices() -> List[Dict[str, Any]]:
    """Generate best practice documents."""
    practices = [
        {
            "_id": "BP_001",
            "document_type": "best_practice",
            "title": "Best Practices for CMP Process Control",
            "content": """
CMP Process Control Best Practices

1. Slurry Management:
   - Monitor large particle counts daily
   - Replace filters per schedule
   - Verify pH and viscosity each shift
   
2. Pad Conditioning:
   - Maintain consistent down force
   - Replace disk at 80% wear
   - Monitor pad thickness hourly
   
3. Process Monitoring:
   - Track removal rate trends
   - Monitor within-wafer uniformity
   - Review particle counts per wafer
   
4. Preventive Maintenance:
   - Weekly: Clean slurry lines
   - Monthly: Full chamber clean
   - Quarterly: Major PM with parts replacement
            """,
            "tags": ["cmp", "best_practice", "process_control"]
        },
        {
            "_id": "BP_002", 
            "document_type": "best_practice",
            "title": "Particle Contamination Prevention",
            "content": """
Particle Contamination Prevention Guidelines

Sources of Particles:
- Process consumables (slurry, pads, gases)
- Equipment wear (moving parts, seals)
- Human contamination
- Environmental factors

Prevention Strategies:
1. Filtration: Multi-stage filtering for all fluids
2. Monitoring: Real-time particle detection
3. Cleaning: Regular wet cleans and purges
4. Training: Proper gowning and handling
5. Environment: Maintain cleanroom standards

Key Metrics:
- Baseline: <500 particles/wafer
- Alert: >1000 particles/wafer
- Shutdown: >2000 particles/wafer
            """,
            "tags": ["particle", "contamination", "prevention"]
        }
    ]
    
    return practices


def main():
    """Generate and save knowledge base data."""
    print("Generating knowledge base...")
    
    # Generate different types of documents
    rca_reports = generate_rca_reports(50)
    troubleshooting_guides = generate_troubleshooting_guides(20)
    best_practices = generate_best_practices()
    
    # Combine all knowledge documents
    historical_knowledge = rca_reports + troubleshooting_guides + best_practices
    
    # Save knowledge base
    output_file = "historical_knowledge.json"
    with open(output_file, 'w') as f:
        json.dump(historical_knowledge, f, indent=2)
    
    print(f"✓ Generated {len(rca_reports)} RCA reports")
    print(f"✓ Generated {len(troubleshooting_guides)} troubleshooting guides")
    print(f"✓ Generated {len(best_practices)} best practice documents")
    print(f"✓ Total: {len(historical_knowledge)} knowledge documents")
    print(f"✓ Saved to {output_file}")
    
    # Print statistics
    high_severity = sum(1 for doc in rca_reports 
                       if doc['metadata'].get('severity') == 'high')
    avg_resolution = sum(doc['metadata']['resolution_time_hours'] for doc in rca_reports) / len(rca_reports)
    total_cost_impact = sum(doc['metadata']['cost_impact_usd'] for doc in rca_reports)
    
    print("\nStatistics:")
    print(f"  - High severity incidents: {high_severity} ({high_severity/len(rca_reports)*100:.1f}%)")
    print(f"  - Average resolution time: {avg_resolution:.1f} hours")
    print(f"  - Total cost impact: ${total_cost_impact:,.0f}")
    
    # Sample documents
    print("\nSample RCA reports (first 3):")
    for report in rca_reports[:3]:
        print(f"  - {report['title']}")
        print(f"    Root cause: {report['findings']['root_cause'][:50]}...")


if __name__ == "__main__":
    main()