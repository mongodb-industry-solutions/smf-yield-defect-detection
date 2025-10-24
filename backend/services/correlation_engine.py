"""
Correlation Engine Service
Analyzes correlations between sensor anomalies and wafer defects
"""
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import logging
import os
from dotenv import load_dotenv
from collections import defaultdict, Counter

load_dotenv()

class CorrelationEngine:
    def __init__(self, mongodb_uri: str = None, database: str = "smf-yield-defect"):
        """Initialize the correlation engine"""
        self.mongodb_uri = mongodb_uri or os.getenv("MONGODB_URI")
        self.client = AsyncIOMotorClient(self.mongodb_uri)
        self.db = self.client[database]
        
        # Collections
        self.alerts_collection = self.db.alerts
        self.wafer_defects_collection = self.db.wafer_defects
        # Use sensor_events for recent data, process_sensor_ts for historical
        self.sensor_collection = self.db.sensor_events  # For real-time correlation
        self.timeseries_collection = self.db.process_sensor_ts  # For historical analysis
        self.process_context_collection = self.db.process_context
        self.historical_knowledge_collection = self.db.historical_knowledge
        
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    async def analyze_alert(self, alert_id: str) -> Dict[str, Any]:
        """Main entry point for analyzing an alert"""
        self.logger.info(f"Starting correlation analysis for alert {alert_id}")

        # Get alert details - try by alert_id field first (for scenario alerts), then by _id ObjectId
        alert = await self.alerts_collection.find_one({"alert_id": alert_id})
        if not alert:
            # Try legacy _id ObjectId format for backward compatibility
            try:
                alert = await self.alerts_collection.find_one({"_id": ObjectId(alert_id)})
            except:
                pass

        if not alert:
            raise ValueError(f"Alert {alert_id} not found")
        
        # Define time windows for analysis
        # Use source_data timestamp (actual excursion time) for correlation
        # Wafers are inspected 2-4 hours AFTER excursion, so we need to look forward in time
        alert_time = alert.get('source_data', {}).get('timestamp') or alert['timestamp']
        equipment_id = alert['equipment_id']

        # Time windows: before excursion, during excursion, after excursion (when inspection happens)
        windows = {
            "pre_alert": (alert_time - timedelta(hours=8), alert_time - timedelta(hours=1)),
            "alert_window": (alert_time - timedelta(hours=1), alert_time + timedelta(hours=2)),
            "post_alert": (alert_time + timedelta(hours=2), alert_time + timedelta(hours=8))  # Captures inspection delay
        }
        
        # Find affected wafers
        affected_wafers = await self.find_affected_wafers(equipment_id, windows)

        # Perform various correlation analyses
        correlations = {
            "temporal": await self.temporal_correlation(alert, affected_wafers, windows),
            "batch": await self.batch_correlation(affected_wafers),
            "recipe": await self.recipe_correlation(affected_wafers),
            "spatial": await self.spatial_correlation(affected_wafers),
            "equipment": await self.equipment_correlation(equipment_id, alert_time),
            "process_context": await self.process_context_correlation(alert)
        }
        
        # FIX: Map problematic slurry batches from process_context to batch.suspect_batches
        # This ensures problematic materials are surfaced in suspect_batches for UI/dashboard
        problematic_materials = correlations.get("process_context", {}).get("problematic_materials", [])
        if problematic_materials:
            # Extract slurry batches from problematic materials
            suspect_batches_from_materials = [
                {
                    "batch_id": mat["id"],
                    "type": mat["type"],
                    "confidence": 0.8 if mat.get("is_problematic") else 0.5,
                    "issues": mat.get("issues", []),
                    "is_problematic": mat.get("is_problematic", False),
                    "source": "process_context"  # Mark source
                }
                for mat in problematic_materials
                if mat.get("is_problematic") and mat.get("type") == "slurry_batch"
            ]

            # Merge with existing suspect_batches (avoid duplicates)
            existing_batches = correlations.get("batch", {}).get("suspect_batches", [])
            existing_batch_ids = {b.get("batch_id") for b in existing_batches}

            # Add problematic batches that aren't already in suspect_batches
            for batch in suspect_batches_from_materials:
                if batch["batch_id"] not in existing_batch_ids:
                    existing_batches.insert(0, batch)  # Insert at beginning for visibility

            # Update correlations
            if "batch" not in correlations:
                correlations["batch"] = {}
            correlations["batch"]["suspect_batches"] = existing_batches

        # Calculate overall confidence score
        confidence_score = self.calculate_confidence(correlations)

        # Generate insights
        insights = self.generate_insights(correlations)

        # Prepare result
        result = {
            "alert_id": alert_id,
            "analysis_timestamp": datetime.utcnow(),
            "equipment_id": equipment_id,
            "alert_severity": alert.get('severity'),
            "affected_wafers": {
                "total": len(affected_wafers['all']),
                "pre_alert": len(affected_wafers['pre_alert']),
                "during_alert": len(affected_wafers['alert_window']),
                "post_alert": len(affected_wafers['post_alert'])
            },
            "correlations": correlations,
            "confidence_score": confidence_score,
            "insights": insights
        }
        
        # Store correlation results in alert - use alert_id field (works for both scenario and legacy alerts)
        await self.alerts_collection.update_one(
            {"alert_id": alert_id},
            {"$set": {"correlation_analysis": result}}
        )
        
        self.logger.info(f"Correlation analysis completed for alert {alert_id}")
        return result
    
    async def find_affected_wafers(self, equipment_id: str, 
                                   windows: Dict[str, Tuple]) -> Dict[str, List]:
        """Find wafers processed on equipment during time windows"""
        affected_wafers = {
            "all": [],
            "pre_alert": [],
            "alert_window": [],
            "post_alert": []
        }
        
        for window_name, (start_time, end_time) in windows.items():
            # Convert datetime to ISO string format for comparison (wafer timestamps are strings)
            start_time_str = start_time.isoformat() + "Z" if hasattr(start_time, 'isoformat') else start_time
            end_time_str = end_time.isoformat() + "Z" if hasattr(end_time, 'isoformat') else end_time

            pipeline = [
                {
                    '$match': {
                        'process_context.equipment_used': {'$in': [equipment_id]},  # Fixed: Array field requires $in operator
                        'inspection_timestamp': {
                            '$gte': start_time_str,  # Fixed: Compare strings to strings
                            '$lte': end_time_str
                        }
                    }
                },
                {
                    '$sort': {'inspection_timestamp': 1}
                }
            ]
            
            cursor = self.wafer_defects_collection.aggregate(pipeline)
            wafers = await cursor.to_list(length=None)
            
            affected_wafers[window_name] = wafers
            affected_wafers["all"].extend(wafers)
        
        self.logger.info(f"Found {len(affected_wafers['all'])} affected wafers")
        return affected_wafers
    
    async def temporal_correlation(self, alert: dict, affected_wafers: Dict[str, List],
                                  windows: Dict[str, Tuple]) -> Dict[str, Any]:
        """Analyze temporal correlation between alert and defects"""
        
        if not affected_wafers['all']:
            return {
                "correlation_strength": 0,
                "yield_impact": 0,
                "defect_rate_change": 0,
                "time_lag_hours": None
            }
        
        # Calculate yield statistics for each window
        window_stats = {}
        for window_name in ['pre_alert', 'alert_window', 'post_alert']:
            wafers = affected_wafers[window_name]
            if wafers:
                yields = [w['defect_summary']['yield_percentage'] for w in wafers]
                defect_counts = [w['defect_summary']['failed_dies'] for w in wafers]
                
                window_stats[window_name] = {
                    "avg_yield": np.mean(yields),
                    "std_yield": np.std(yields),
                    "avg_defects": np.mean(defect_counts),
                    "wafer_count": len(wafers)
                }
            else:
                window_stats[window_name] = {
                    "avg_yield": 100,
                    "std_yield": 0,
                    "avg_defects": 0,
                    "wafer_count": 0
                }
        
        # Calculate yield drop
        baseline_yield = window_stats['pre_alert']['avg_yield']
        alert_yield = window_stats['alert_window']['avg_yield']
        post_yield = window_stats['post_alert']['avg_yield']
        
        yield_drop = baseline_yield - min(alert_yield, post_yield)
        
        # Calculate defect rate change
        baseline_defects = window_stats['pre_alert']['avg_defects']
        alert_defects = window_stats['alert_window']['avg_defects']
        defect_increase = alert_defects - baseline_defects if baseline_defects > 0 else 0
        
        # Calculate time lag to first significant defect
        time_lag_hours = None
        alert_time = alert.get('source_data', {}).get('timestamp') or alert['timestamp']

        for wafer in affected_wafers['alert_window'] + affected_wafers['post_alert']:
            if wafer['defect_summary']['yield_percentage'] < baseline_yield - 5:  # 5% threshold
                # Convert string timestamp to datetime for comparison
                wafer_time_str = wafer['inspection_timestamp']
                wafer_time = datetime.fromisoformat(wafer_time_str.replace('Z', '+00:00'))
                # Make alert_time timezone aware if needed
                if alert_time.tzinfo is None:
                    from datetime import timezone
                    alert_time = alert_time.replace(tzinfo=timezone.utc)
                time_lag_hours = (wafer_time - alert_time).total_seconds() / 3600
                break
        
        # Calculate correlation strength (0-1 scale)
        correlation_strength = min(1.0, yield_drop / 20)  # Normalize to 20% max drop
        
        return {
            "correlation_strength": round(correlation_strength, 3),
            "yield_impact": round(yield_drop, 2),
            "defect_rate_change": round(defect_increase, 1),
            "time_lag_hours": round(time_lag_hours, 2) if time_lag_hours else None,
            "window_statistics": window_stats
        }
    
    async def batch_correlation(self, affected_wafers: Dict[str, List]) -> Dict[str, Any]:
        """Analyze correlation with material batches"""

        all_wafers = affected_wafers['all']
        if not all_wafers:
            return {"suspect_batches": [], "batch_impact": {}}
        
        # Analyze slurry batches
        batch_stats = defaultdict(lambda: {
            "wafer_count": 0,
            "total_yield": 0,
            "defect_patterns": [],
            "failed_dies": [],
            "is_problematic": False  # Track if batch is known to be problematic
        })

        for wafer in all_wafers:
            slurry_batch = wafer.get('process_context', {}).get('slurry_batch')
            if slurry_batch:
                batch_stats[slurry_batch]["wafer_count"] += 1
                batch_stats[slurry_batch]["total_yield"] += wafer['defect_summary']['yield_percentage']
                batch_stats[slurry_batch]["defect_patterns"].append(
                    wafer['defect_summary'].get('defect_pattern', 'unknown')
                )
                batch_stats[slurry_batch]["failed_dies"].append(
                    wafer['defect_summary']['failed_dies']
                )
        
        # Calculate statistics for each batch
        batch_analysis = {}
        for batch_id, stats in batch_stats.items():
            if stats["wafer_count"] > 0:
                avg_yield = stats["total_yield"] / stats["wafer_count"]
                pattern_counts = Counter(stats["defect_patterns"])
                dominant_pattern = pattern_counts.most_common(1)[0][0] if pattern_counts else "unknown"
                
                # Check if batch is problematic in process_context collection
                context_id = batch_id
                if batch_id.startswith("SLURRY_BATCH_"):
                    parts = batch_id.split("_")
                    if len(parts) >= 3:
                        context_id = f"SB_{parts[2]}_{parts[3].zfill(3)}"

                # Query process_context collection for batch status
                batch_doc = await self.process_context_collection.find_one({
                    "context_id": context_id
                })

                is_problematic = batch_doc.get("is_problematic", False) if batch_doc else False

                batch_analysis[batch_id] = {
                    "avg_yield": round(avg_yield, 2),
                    "wafer_count": stats["wafer_count"],
                    "dominant_pattern": dominant_pattern,
                    "avg_failed_dies": round(np.mean(stats["failed_dies"]), 1),
                    "pattern_distribution": dict(pattern_counts),
                    "is_problematic": is_problematic  # Add problematic flag
                }
        
        # Identify suspect batches (lowest yield)
        if batch_analysis:
            sorted_batches = sorted(batch_analysis.items(), key=lambda x: x[1]["avg_yield"])
            suspect_batches = [
                {
                    "batch_id": batch_id,
                    "yield": info["avg_yield"],
                    "wafer_count": info["wafer_count"],
                    "dominant_pattern": info["dominant_pattern"],
                    "is_problematic": info.get("is_problematic", False)
                }
                for batch_id, info in sorted_batches[:3]  # Top 3 worst batches
            ]
        else:
            suspect_batches = []
        
        return {
            "suspect_batches": suspect_batches,
            "batch_impact": batch_analysis
        }
    
    async def recipe_correlation(self, affected_wafers: Dict[str, List]) -> Dict[str, Any]:
        """Analyze correlation with process recipes"""
        
        all_wafers = affected_wafers['all']
        if not all_wafers:
            return {"recipe_impact": {}, "worst_recipe": None}
        
        # Get recipe information from metadata
        recipe_stats = defaultdict(lambda: {
            "wafer_count": 0,
            "total_yield": 0,
            "defect_types": []
        })
        
        for wafer in all_wafers:
            # Get recipe from sensor metadata
            metadata = wafer.get('metadata', {})
            recipe_id = metadata.get('recipe_id')
            
            if recipe_id:
                recipe_stats[recipe_id]["wafer_count"] += 1
                recipe_stats[recipe_id]["total_yield"] += wafer['defect_summary']['yield_percentage']
                
                # Collect defect types
                for defect in wafer.get('defects', []):
                    recipe_stats[recipe_id]["defect_types"].append(defect.get('type', 'unknown'))
        
        # Calculate statistics
        recipe_analysis = {}
        for recipe_id, stats in recipe_stats.items():
            if stats["wafer_count"] > 0:
                avg_yield = stats["total_yield"] / stats["wafer_count"]
                defect_type_counts = Counter(stats["defect_types"])
                
                recipe_analysis[recipe_id] = {
                    "avg_yield": round(avg_yield, 2),
                    "wafer_count": stats["wafer_count"],
                    "common_defects": dict(defect_type_counts.most_common(3))
                }
        
        # Find worst performing recipe
        worst_recipe = None
        if recipe_analysis:
            worst_recipe = min(recipe_analysis.items(), key=lambda x: x[1]["avg_yield"])
            worst_recipe = {
                "recipe_id": worst_recipe[0],
                **worst_recipe[1]
            }
        
        return {
            "recipe_impact": recipe_analysis,
            "worst_recipe": worst_recipe
        }
    
    async def process_context_correlation(self, alert: dict) -> Dict[str, Any]:
        """
        Check if alert relates to known problematic process materials
        Queries process_context collection for materials referenced in alert
        """

        # Extract material references from alert metadata
        source_data = alert.get("source_data", {})
        metadata = source_data.get("metadata", {})

        problematic_materials = []
        material_checks = {}

        # Check slurry batch
        if slurry_batch := metadata.get("slurry_batch"):
            # Map common naming patterns to context IDs
            # Handle both "SB_2025_XXX" and "SLURRY_BATCH_2025_XXX" formats
            context_id = slurry_batch
            if slurry_batch.startswith("SLURRY_BATCH_"):
                # Convert SLURRY_BATCH_2025_001 to SB_2025_001
                parts = slurry_batch.split("_")
                if len(parts) >= 3:
                    context_id = f"SB_{parts[2]}_{parts[3].zfill(3)}"

            batch_doc = await self.process_context_collection.find_one({
                "context_id": context_id
            })

            if batch_doc:
                material_checks["slurry_batch"] = {
                    "id": slurry_batch,
                    "context_id": context_id,
                    "is_problematic": batch_doc.get("is_problematic", False),
                    "qc_status": batch_doc.get("slurry_details", {}).get("qc_status"),
                    "large_particle_count": batch_doc.get("slurry_details", {}).get("large_particle_count")
                }

                if batch_doc.get("is_problematic"):
                    problematic_materials.append({
                        "type": "slurry_batch",
                        "id": slurry_batch,
                        "context_id": context_id,
                        "is_problematic": True,  # Include this field!
                        "issues": batch_doc.get("known_issues", []),
                        "details": {
                            "qc_status": batch_doc.get("slurry_details", {}).get("qc_status"),
                            "large_particle_count": batch_doc.get("slurry_details", {}).get("large_particle_count"),
                            "manufacturer": batch_doc.get("slurry_details", {}).get("manufacturer")
                        }
                    })

        # Check recipe
        if recipe_id := metadata.get("recipe_id"):
            # Map recipe ID formats
            context_id = recipe_id
            if recipe_id.startswith("RECIPE_"):
                # Convert RECIPE_CMP_01 to ETCH_RECIPE_01 or CMP_RECIPE_01
                parts = recipe_id.split("_")
                if len(parts) >= 3:
                    context_id = f"{parts[1]}_RECIPE_{parts[2]}"

            recipe_doc = await self.process_context_collection.find_one({
                "$or": [
                    {"context_id": recipe_id},
                    {"context_id": context_id}
                ]
            })

            if recipe_doc:
                material_checks["recipe"] = {
                    "id": recipe_id,
                    "context_id": recipe_doc.get("context_id"),
                    "is_problematic": recipe_doc.get("is_problematic", False),
                    "validation_status": recipe_doc.get("validation_status")
                }

                if recipe_doc.get("is_problematic"):
                    problematic_materials.append({
                        "type": "recipe",
                        "id": recipe_id,
                        "context_id": recipe_doc.get("context_id"),
                        "is_problematic": True,  # Include this field!
                        "issues": recipe_doc.get("known_issues", []),
                        "details": {
                            "validation_status": recipe_doc.get("validation_status"),
                            "process_type": recipe_doc.get("recipe_details", {}).get("process_type")
                        }
                    })

        # Check reticle
        if reticle_id := metadata.get("reticle_id"):
            reticle_doc = await self.process_context_collection.find_one({
                "context_id": reticle_id
            })

            if reticle_doc:
                # Check for wear based on exposures
                usage_stats = reticle_doc.get("usage_statistics", {})
                total_exposures = usage_stats.get("total_exposures", 0)
                is_worn = total_exposures > 2500  # Consider worn after 2500 exposures

                material_checks["reticle"] = {
                    "id": reticle_id,
                    "is_problematic": reticle_doc.get("is_problematic", False) or is_worn,
                    "total_exposures": total_exposures,
                    "condition": reticle_doc.get("inspection_data", {}).get("condition")
                }

                if reticle_doc.get("is_problematic") or is_worn:
                    problematic_materials.append({
                        "type": "reticle",
                        "id": reticle_id,
                        "issues": reticle_doc.get("known_issues", []) +
                                 ([{"description": f"High wear - {total_exposures} exposures", "severity": "medium"}] if is_worn else []),
                        "details": {
                            "total_exposures": total_exposures,
                            "condition": reticle_doc.get("inspection_data", {}).get("condition"),
                            "defect_count": reticle_doc.get("inspection_data", {}).get("defect_count")
                        }
                    })

        # Calculate confidence based on problematic materials found
        confidence = 0.0
        if problematic_materials:
            # Higher confidence if multiple problematic materials
            confidence = min(0.95, 0.6 + (len(problematic_materials) * 0.2))

            # Boost confidence for critical issues
            for material in problematic_materials:
                for issue in material.get("issues", []):
                    if issue.get("severity") == "high":
                        confidence = min(1.0, confidence + 0.15)

        return {
            "problematic_materials": problematic_materials,
            "material_checks": material_checks,
            "correlation_found": len(problematic_materials) > 0,
            "confidence": round(confidence, 3)
        }

    async def spatial_correlation(self, affected_wafers: Dict[str, List]) -> Dict[str, Any]:
        """Analyze spatial patterns in defects"""

        all_wafers = affected_wafers['all']
        if not all_wafers:
            return {"dominant_patterns": [], "pattern_frequency": {}}

        # Count defect patterns
        pattern_counts = Counter()
        pattern_yields = defaultdict(list)
        
        for wafer in all_wafers:
            pattern = wafer['defect_summary'].get('defect_pattern', 'unknown')
            pattern_counts[pattern] += 1
            pattern_yields[pattern].append(wafer['defect_summary']['yield_percentage'])
        
        # Calculate average yield for each pattern
        pattern_analysis = {}
        for pattern, count in pattern_counts.items():
            yields = pattern_yields[pattern]
            pattern_analysis[pattern] = {
                "frequency": count,
                "percentage": round((count / len(all_wafers)) * 100, 1),
                "avg_yield": round(np.mean(yields), 2),
                "yield_std": round(np.std(yields), 2)
            }
        
        # Identify dominant patterns
        dominant_patterns = [
            {"pattern": pattern, **stats}
            for pattern, stats in sorted(
                pattern_analysis.items(),
                key=lambda x: x[1]["frequency"],
                reverse=True
            )[:3]
        ]
        
        return {
            "dominant_patterns": dominant_patterns,
            "pattern_frequency": pattern_analysis
        }
    
    async def equipment_correlation(self, equipment_id: str, 
                                   alert_time: datetime) -> Dict[str, Any]:
        """Analyze equipment-specific patterns"""
        
        # Get recent sensor data for the equipment
        start_time = alert_time - timedelta(hours=24)
        end_time = alert_time + timedelta(hours=1)
        
        pipeline = [
            {
                '$match': {
                    'equipment_id': equipment_id,
                    'timestamp': {
                        '$gte': start_time,
                        '$lte': end_time
                    }
                }
            },
            {
                '$sort': {'timestamp': 1}
            }
        ]
        
        cursor = self.sensor_collection.aggregate(pipeline)
        sensor_data = await cursor.to_list(length=None)
        
        if not sensor_data:
            return {
                "maintenance_due": False,
                "utilization_rate": 0,
                "recent_anomalies": 0
            }
        
        # Calculate equipment statistics
        # Check for maintenance patterns (simplified)
        timestamps = [d['timestamp'] for d in sensor_data]
        time_diffs = np.diff([t.timestamp() for t in timestamps])
        
        # If there are large gaps, might indicate maintenance
        maintenance_due = bool(np.max(time_diffs) > 3600) if len(time_diffs) > 0 else False
        
        # Calculate utilization rate
        total_time = (end_time - start_time).total_seconds() / 3600
        active_time = len(sensor_data) * 0.5  # Assuming 30-min intervals
        utilization_rate = min(100, (active_time / total_time) * 100)
        
        # Count recent anomalies (particle count > 1000)
        recent_anomalies = sum(
            1 for d in sensor_data 
            if d.get('metrics', {}).get('particle_count', 0) > 1000
        )
        
        return {
            "maintenance_due": maintenance_due,
            "utilization_rate": round(utilization_rate, 1),
            "recent_anomalies": recent_anomalies,
            "data_points": len(sensor_data)
        }
    
    def calculate_confidence(self, correlations: Dict[str, Any]) -> float:
        """Calculate overall confidence score for the correlation analysis

        Enhanced algorithm that properly values strong evidence:
        - Base score starts at 0.30 (30% baseline)
        - Add confidence for each type of evidence found
        - Cap at 0.85 to leave room for uncertainty
        """

        base_score = 0.30  # Start with 30% baseline confidence

        # Add confidence for temporal correlation (strong predictor)
        temporal = correlations.get("temporal", {})
        if temporal.get("correlation_strength", 0) > 0.5:
            base_score += 0.15
        elif temporal.get("correlation_strength", 0) > 0.3:
            base_score += 0.08

        # Add confidence for problematic materials (highest value indicator)
        process_context = correlations.get("process_context", {})
        problematic_materials = process_context.get("problematic_materials", [])
        if problematic_materials:
            # Strong boost for known problematic materials
            base_score += 0.25
            # Additional boost for multiple problematic materials
            if len(problematic_materials) > 1:
                base_score += 0.10

        # Add confidence for batch correlation
        batch = correlations.get("batch", {})
        suspect_batches = batch.get("suspect_batches", [])
        if suspect_batches:
            # Check if any suspect batch is marked as problematic
            has_problematic_batch = any(b.get("is_problematic", False) for b in suspect_batches)
            if has_problematic_batch:
                base_score += 0.15  # Strong evidence
            else:
                base_score += 0.08  # Weak evidence (just low yield)

        # Add confidence for equipment maintenance patterns
        equipment = correlations.get("equipment", {})
        if equipment.get("maintenance_due", False):
            base_score += 0.10

        # Add confidence for multiple recent anomalies
        recent_anomalies = equipment.get("recent_anomalies", 0)
        if recent_anomalies > 5:
            base_score += 0.12
        elif recent_anomalies > 2:
            base_score += 0.06

        # Add confidence for dominant spatial patterns
        spatial = correlations.get("spatial", {})
        dominant_patterns = spatial.get("dominant_patterns", [])
        if dominant_patterns:
            # Strong pattern (>50% of wafers)
            if dominant_patterns[0].get("percentage", 0) > 50:
                base_score += 0.10
            else:
                base_score += 0.05

        # Add confidence for yield impact
        if temporal.get("yield_impact", 0) > 10:
            base_score += 0.10
        elif temporal.get("yield_impact", 0) > 5:
            base_score += 0.05

        # Cap at 0.85 (leave room for uncertainty)
        confidence = min(0.85, base_score)

        return round(confidence, 3)
    
    def generate_insights(self, correlations: Dict[str, Any]) -> List[str]:
        """Generate human-readable insights from correlation analysis"""
        
        insights = []
        
        # Temporal insights
        temporal = correlations.get("temporal", {})
        yield_impact = temporal.get("yield_impact", 0)
        if yield_impact > 5:
            insights.append(
                f"Significant yield drop of {yield_impact:.1f}% detected "
                f"following the excursion event"
            )
        
        time_lag_hours = temporal.get("time_lag_hours")
        if time_lag_hours is not None:
            insights.append(
                f"Defects appeared approximately {time_lag_hours:.1f} hours "
                f"after the sensor excursion"
            )
        
        # Batch insights
        batch = correlations.get("batch", {})
        if batch.get("suspect_batches"):
            worst_batch = batch["suspect_batches"][0]
            batch_yield = worst_batch.get('yield', 0)
            insights.append(
                f"Slurry batch {worst_batch.get('batch_id', 'unknown')} shows poor performance "
                f"with {batch_yield:.1f}% yield"
            )
        
        # Spatial insights
        spatial = correlations.get("spatial", {})
        if spatial.get("dominant_patterns"):
            pattern = spatial["dominant_patterns"][0]
            pattern_name = pattern.get('pattern', 'unknown')
            pattern_pct = pattern.get('percentage', 0)
            insights.append(
                f"Dominant defect pattern is '{pattern_name}' "
                f"occurring in {pattern_pct:.1f}% of wafers"
            )

        # Recipe insights
        recipe = correlations.get("recipe", {})
        if recipe.get("worst_recipe"):
            worst = recipe["worst_recipe"]
            recipe_id = worst.get('recipe_id', 'unknown')
            avg_yield = worst.get('avg_yield', 0)
            insights.append(
                f"Recipe {recipe_id} associated with lower yields "
                f"({avg_yield:.1f}%)"
            )
        
        # Equipment insights
        equipment = correlations.get("equipment", {})
        if equipment.get("maintenance_due"):
            insights.append("Equipment shows patterns suggesting maintenance may be needed")
        
        if equipment.get("recent_anomalies", 0) > 5:
            insights.append(
                f"Equipment has experienced {equipment['recent_anomalies']} "
                f"anomalies in the past 24 hours"
            )

        # Process context insights
        process_context = correlations.get("process_context", {})
        if process_context.get("problematic_materials"):
            for material in process_context["problematic_materials"]:
                material_type = material["type"].replace("_", " ").title()
                material_id = material["id"]
                issues = material.get("issues", [])

                if material["type"] == "slurry_batch":
                    details = material.get("details", {})
                    particle_count = details.get("large_particle_count", 0)
                    insights.append(
                        f"{material_type} {material_id} is known to be problematic "
                        f"(particle count: {particle_count}, QC status: {details.get('qc_status', 'unknown')})"
                    )
                elif material["type"] == "recipe":
                    insights.append(
                        f"{material_type} {material_id} has validation issues "
                        f"({material.get('details', {}).get('validation_status', 'unknown')} status)"
                    )
                elif material["type"] == "reticle":
                    details = material.get("details", {})
                    exposures = details.get("total_exposures", 0)
                    insights.append(
                        f"{material_type} {material_id} shows wear issues "
                        f"({exposures} exposures, condition: {details.get('condition', 'unknown')})"
                    )

        return insights