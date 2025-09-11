"""
RCA (Root Cause Analysis) Hint Generator
Generates intelligent RCA hints based on patterns and historical data
Enhanced with vector similarity search for Phase 3
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import logging
import os
from dotenv import load_dotenv
import numpy as np
from collections import Counter

load_dotenv()

class RCAGenerator:
    def __init__(self, mongodb_uri: str = None, database: str = "smf-yield-defect", use_semantic_search: bool = True):
        """Initialize the RCA generator with optional semantic search"""
        self.mongodb_uri = mongodb_uri or os.getenv("MONGODB_URI")
        self.client = AsyncIOMotorClient(self.mongodb_uri)
        self.db = self.client[database]
        
        # Collections
        self.alerts_collection = self.db.alerts
        self.historical_knowledge_collection = self.db.historical_knowledge
        self.process_context_collection = self.db.process_context
        
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Initialize semantic search for Phase 3
        self.use_semantic_search = use_semantic_search
        self.semantic_search = None
        if self.use_semantic_search:
            try:
                from services.semantic_search import SemanticSearchService
                self.semantic_search = SemanticSearchService(
                    mongodb_uri=self.mongodb_uri,
                    database_name=database
                )
                self.logger.info("Semantic search enabled for enhanced RCA")
            except Exception as e:
                self.logger.warning(f"Semantic search not available: {e}")
                self.use_semantic_search = False
        
        # Define RCA patterns and rules
        self.rca_patterns = self._initialize_rca_patterns()
    
    def _initialize_rca_patterns(self) -> Dict[str, Any]:
        """Initialize RCA patterns based on domain knowledge"""
        return {
            "particle_excursion": {
                "conditions": {
                    "metric": "particle_count",
                    "threshold": 1000
                },
                "probable_causes": [
                    {
                        "cause": "Degraded slurry filter",
                        "confidence": 0.8,
                        "indicators": ["slurry_batch_correlation", "gradual_increase"],
                        "actions": [
                            "Check slurry filter condition and replace if necessary",
                            "Verify slurry quality from supplier",
                            "Review filter replacement schedule"
                        ]
                    },
                    {
                        "cause": "Chamber contamination",
                        "confidence": 0.7,
                        "indicators": ["clustered_defects", "post_maintenance"],
                        "actions": [
                            "Perform chamber wet clean",
                            "Check chamber seal integrity",
                            "Review previous process run materials"
                        ]
                    },
                    {
                        "cause": "Worn pad conditioning disk",
                        "confidence": 0.6,
                        "indicators": ["edge_defects", "pad_life_exceeded"],
                        "actions": [
                            "Replace pad conditioning disk",
                            "Adjust conditioning parameters",
                            "Check pad wear patterns"
                        ]
                    }
                ]
            },
            "rf_power_drift": {
                "conditions": {
                    "metric": "rf_power",
                    "drift": 100
                },
                "probable_causes": [
                    {
                        "cause": "RF generator degradation",
                        "confidence": 0.75,
                        "indicators": ["gradual_drift", "power_instability"],
                        "actions": [
                            "Calibrate RF generator",
                            "Check RF cable connections",
                            "Monitor generator temperature"
                        ]
                    },
                    {
                        "cause": "Impedance mismatch",
                        "confidence": 0.65,
                        "indicators": ["sudden_change", "recipe_change"],
                        "actions": [
                            "Verify matching network settings",
                            "Check electrode spacing",
                            "Review process gas composition"
                        ]
                    }
                ]
            },
            "temperature_drift": {
                "conditions": {
                    "metric": "temperature",
                    "drift": 2
                },
                "probable_causes": [
                    {
                        "cause": "Chiller malfunction",
                        "confidence": 0.8,
                        "indicators": ["temperature_fluctuation", "coolant_flow"],
                        "actions": [
                            "Check chiller operation and setpoint",
                            "Verify coolant flow rate",
                            "Inspect heat exchanger condition"
                        ]
                    },
                    {
                        "cause": "Heater element degradation",
                        "confidence": 0.6,
                        "indicators": ["slow_response", "age_factor"],
                        "actions": [
                            "Test heater element resistance",
                            "Check temperature controller calibration",
                            "Review heater duty cycle"
                        ]
                    }
                ]
            },
            "clustered_defects": {
                "conditions": {
                    "pattern": "clustered",
                    "yield_drop": 5
                },
                "probable_causes": [
                    {
                        "cause": "Localized contamination source",
                        "confidence": 0.85,
                        "indicators": ["specific_location", "particle_count"],
                        "actions": [
                            "Inspect wafer handling system",
                            "Check for particle shedding components",
                            "Review cleanroom environmental data"
                        ]
                    },
                    {
                        "cause": "Non-uniform process distribution",
                        "confidence": 0.7,
                        "indicators": ["center_to_edge", "flow_pattern"],
                        "actions": [
                            "Verify gas flow uniformity",
                            "Check showerhead condition",
                            "Adjust process parameters for uniformity"
                        ]
                    }
                ]
            },
            "edge_defects": {
                "conditions": {
                    "pattern": "edge",
                    "yield_drop": 3
                },
                "probable_causes": [
                    {
                        "cause": "Edge exclusion zone issue",
                        "confidence": 0.75,
                        "indicators": ["consistent_edge_location", "bevel_area"],
                        "actions": [
                            "Adjust edge exclusion settings",
                            "Check wafer centering",
                            "Review edge bead removal process"
                        ]
                    },
                    {
                        "cause": "Wafer handling damage",
                        "confidence": 0.65,
                        "indicators": ["mechanical_marks", "transport_related"],
                        "actions": [
                            "Inspect robot end effector",
                            "Check wafer cassette condition",
                            "Review handling sequence and speeds"
                        ]
                    }
                ]
            }
        }
    
    async def generate_rca_hints(self, alert_id: str) -> Dict[str, Any]:
        """Generate RCA hints for a given alert"""
        self.logger.info(f"Generating RCA hints for alert {alert_id}")
        
        # Get alert and correlation analysis
        alert = await self.alerts_collection.find_one({"_id": ObjectId(alert_id)})
        if not alert:
            raise ValueError(f"Alert {alert_id} not found")
        
        correlation_analysis = alert.get("correlation_analysis", {})
        
        # Identify applicable RCA patterns
        applicable_patterns = await self._identify_patterns(alert, correlation_analysis)
        
        # Search historical knowledge
        similar_cases = await self._search_similar_cases(alert)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            applicable_patterns, 
            similar_cases,
            correlation_analysis
        )
        
        # Calculate confidence scores
        overall_confidence = self._calculate_overall_confidence(recommendations)
        
        # Prepare RCA hints
        rca_hints = {
            "alert_id": alert_id,
            "generated_at": datetime.utcnow(),
            "identified_patterns": applicable_patterns,
            "recommendations": recommendations,
            "similar_historical_cases": similar_cases,
            "confidence_score": overall_confidence,
            "suggested_priority": self._determine_priority(alert, recommendations)
        }
        
        # Store RCA hints in alert
        await self.alerts_collection.update_one(
            {"_id": ObjectId(alert_id)},
            {"$set": {"rca_hints": rca_hints}}
        )
        
        self.logger.info(f"RCA hints generated for alert {alert_id}")
        return rca_hints
    
    async def _identify_patterns(self, alert: dict, 
                                 correlation_analysis: dict) -> List[Dict[str, Any]]:
        """Identify applicable RCA patterns based on alert and correlations"""
        
        identified_patterns = []
        violations = alert.get("violations", [])
        
        # Check metric-based patterns
        for violation in violations:
            metric = violation.get("metric")
            
            # Check particle excursion
            if metric == "particle_count" and violation.get("current_value", 0) > 1000:
                pattern = self.rca_patterns["particle_excursion"]
                identified_patterns.append({
                    "pattern_type": "particle_excursion",
                    "trigger": f"Particle count: {violation['current_value']}",
                    "probable_causes": self._filter_causes(
                        pattern["probable_causes"],
                        correlation_analysis
                    )
                })
            
            # Check RF power drift
            elif metric == "rf_power" and violation.get("type") == "drift":
                pattern = self.rca_patterns["rf_power_drift"]
                identified_patterns.append({
                    "pattern_type": "rf_power_drift",
                    "trigger": f"RF power drift: {violation['deviation']}W",
                    "probable_causes": self._filter_causes(
                        pattern["probable_causes"],
                        correlation_analysis
                    )
                })
            
            # Check temperature drift
            elif metric == "temperature" and violation.get("type") == "drift":
                pattern = self.rca_patterns["temperature_drift"]
                identified_patterns.append({
                    "pattern_type": "temperature_drift",
                    "trigger": f"Temperature drift: {violation['deviation']}°C",
                    "probable_causes": self._filter_causes(
                        pattern["probable_causes"],
                        correlation_analysis
                    )
                })
        
        # Check spatial pattern-based RCA
        spatial_patterns = correlation_analysis.get("correlations", {}).get("spatial", {})
        dominant_patterns = spatial_patterns.get("dominant_patterns", [])
        
        for pattern_info in dominant_patterns:
            pattern_name = pattern_info.get("pattern")
            
            if pattern_name == "clustered" and pattern_name in self.rca_patterns:
                pattern = self.rca_patterns["clustered_defects"]
                identified_patterns.append({
                    "pattern_type": "clustered_defects",
                    "trigger": f"Clustered defects: {pattern_info['frequency']} wafers",
                    "probable_causes": self._filter_causes(
                        pattern["probable_causes"],
                        correlation_analysis
                    )
                })
            
            elif pattern_name == "edge" and "edge_defects" in self.rca_patterns:
                pattern = self.rca_patterns["edge_defects"]
                identified_patterns.append({
                    "pattern_type": "edge_defects",
                    "trigger": f"Edge defects: {pattern_info['frequency']} wafers",
                    "probable_causes": self._filter_causes(
                        pattern["probable_causes"],
                        correlation_analysis
                    )
                })
        
        return identified_patterns
    
    def _filter_causes(self, causes: List[Dict], 
                      correlation_analysis: dict) -> List[Dict]:
        """Filter and rank probable causes based on correlation analysis"""
        
        filtered_causes = []
        
        for cause in causes:
            # Adjust confidence based on correlation indicators
            adjusted_confidence = cause["confidence"]
            
            # Check for supporting indicators in correlation analysis
            indicators_found = 0
            for indicator in cause.get("indicators", []):
                if self._check_indicator(indicator, correlation_analysis):
                    indicators_found += 1
            
            if indicators_found > 0:
                # Boost confidence if indicators are present
                adjusted_confidence = min(1.0, adjusted_confidence + 0.1 * indicators_found)
                
                filtered_causes.append({
                    "cause": cause["cause"],
                    "confidence": round(adjusted_confidence, 2),
                    "actions": cause["actions"],
                    "supporting_evidence": indicators_found
                })
        
        # Sort by confidence
        filtered_causes.sort(key=lambda x: x["confidence"], reverse=True)
        
        return filtered_causes[:3]  # Return top 3 causes
    
    def _check_indicator(self, indicator: str, correlation_analysis: dict) -> bool:
        """Check if an indicator is present in correlation analysis"""
        
        correlations = correlation_analysis.get("correlations", {})
        
        # Check various indicators
        if indicator == "slurry_batch_correlation":
            batch_data = correlations.get("batch", {})
            return len(batch_data.get("suspect_batches", [])) > 0
        
        elif indicator == "clustered_defects":
            spatial = correlations.get("spatial", {})
            patterns = spatial.get("dominant_patterns", [])
            return any(p.get("pattern") == "clustered" for p in patterns)
        
        elif indicator == "edge_defects":
            spatial = correlations.get("spatial", {})
            patterns = spatial.get("dominant_patterns", [])
            return any(p.get("pattern") == "edge" for p in patterns)
        
        elif indicator == "gradual_increase":
            temporal = correlations.get("temporal", {})
            return temporal.get("correlation_strength", 0) > 0.5
        
        elif indicator == "post_maintenance":
            equipment = correlations.get("equipment", {})
            return equipment.get("maintenance_due", False)
        
        return False
    
    async def _search_similar_cases(self, alert: dict) -> List[Dict[str, Any]]:
        """Search for similar historical cases using semantic search if available"""
        
        # Use semantic search if available (Phase 3)
        if self.use_semantic_search and self.semantic_search:
            return await self._search_similar_cases_semantic(alert)
        
        # Fallback to traditional search
        # Build search criteria based on alert
        search_criteria = {
            "metadata.document_type": "rca_report"
        }
        
        # Add process area if available
        process_step = alert.get("process_step")
        if process_step:
            search_criteria["metadata.process_area"] = process_step
        
        # Search for similar cases
        cursor = self.historical_knowledge_collection.find(
            search_criteria
        ).sort("metadata.resolution_time_hours", 1).limit(5)
        
        similar_cases = []
        async for doc in cursor:
            # Extract relevant information
            case_summary = {
                "title": doc.get("title", ""),
                "root_cause": self._extract_root_cause(doc.get("content", "")),
                "resolution_time": doc.get("metadata", {}).get("resolution_time_hours", 0),
                "defect_type": doc.get("metadata", {}).get("defect_type", ""),
                "relevance_score": self._calculate_relevance(doc, alert)
            }
            similar_cases.append(case_summary)
        
        # Sort by relevance
        similar_cases.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        return similar_cases[:3]  # Return top 3 most relevant
    
    async def _search_similar_cases_semantic(self, alert: dict) -> List[Dict[str, Any]]:
        """Search for similar cases using semantic search (Phase 3)"""
        try:
            # Initialize semantic search if needed
            if self.semantic_search and not hasattr(self.semantic_search, '_initialized'):
                await self.semantic_search.initialize()
                self.semantic_search._initialized = True
            
            # Build semantic query from alert
            query_parts = []
            
            # Add alert type and description
            if alert.get("alert_type"):
                query_parts.append(alert["alert_type"])
            if alert.get("description"):
                query_parts.append(alert["description"])
            
            # Add excursion details
            if alert.get("excursion_details"):
                details = alert["excursion_details"]
                metric = details.get("metric")
                value = details.get("value")
                if metric:
                    query_parts.append(f"{metric} excursion")
                    if value:
                        query_parts.append(f"{metric} value {value}")
            
            # Add equipment context
            if alert.get("affected_equipment"):
                query_parts.append(f"equipment {alert['affected_equipment']}")
            
            # Add process step
            if alert.get("process_step"):
                query_parts.append(f"process {alert['process_step']}")
            
            query = " ".join(query_parts)
            
            # Search for similar RCA reports
            results = await self.semantic_search.search_knowledge_base(
                query=query,
                document_types=["rca_report"],
                limit=5,
                min_score=0.6
            )
            
            # Format results
            similar_cases = []
            for result in results:
                case_summary = {
                    "title": result.get("title", ""),
                    "root_cause": result.get("metadata", {}).get("root_cause", 
                                  self._extract_root_cause(result.get("content", ""))),
                    "resolution_time": result.get("metadata", {}).get("resolution_time_hours", 0),
                    "defect_type": result.get("metadata", {}).get("defect_type", ""),
                    "relevance_score": result.get("score", 0),
                    "semantic_match": True  # Flag to indicate semantic search was used
                }
                similar_cases.append(case_summary)
            
            self.logger.info(f"Found {len(similar_cases)} similar cases using semantic search")
            return similar_cases[:3]  # Return top 3 most relevant
            
        except Exception as e:
            self.logger.warning(f"Semantic search failed, falling back to traditional search: {e}")
            # Set flag to avoid retrying
            self.use_semantic_search = False
            # Fallback to traditional search logic
            return await self._search_similar_cases(alert)
    
    def _extract_root_cause(self, content: str) -> str:
        """Extract root cause from RCA report content"""
        # Simple extraction - look for "Root Cause:" in content
        lines = content.split('\n')
        for line in lines:
            if "Root Cause:" in line:
                return line.replace("Root Cause:", "").strip()
        return "Root cause not specified"
    
    def _calculate_relevance(self, historical_case: dict, alert: dict) -> float:
        """Calculate relevance score between historical case and current alert"""
        
        relevance = 0.0
        
        # Check process area match
        if historical_case.get("metadata", {}).get("process_area") == alert.get("process_step"):
            relevance += 0.3
        
        # Check defect type match
        violations = alert.get("violations", [])
        if violations:
            main_metric = violations[0].get("metric", "")
            if "particle" in main_metric and historical_case.get("metadata", {}).get("defect_type") == "particle":
                relevance += 0.4
        
        # Consider resolution time (prefer faster resolutions)
        resolution_time = historical_case.get("metadata", {}).get("resolution_time_hours", 24)
        if resolution_time < 4:
            relevance += 0.3
        elif resolution_time < 8:
            relevance += 0.2
        else:
            relevance += 0.1
        
        return round(relevance, 2)
    
    def _generate_recommendations(self, patterns: List[Dict], 
                                 similar_cases: List[Dict],
                                 correlation_analysis: dict) -> List[Dict[str, Any]]:
        """Generate actionable recommendations"""
        
        recommendations = []
        
        # Generate recommendations from identified patterns
        for pattern in patterns:
            for cause in pattern.get("probable_causes", [])[:2]:  # Top 2 causes per pattern
                recommendation = {
                    "title": f"Investigate: {cause['cause']}",
                    "confidence": cause["confidence"],
                    "actions": cause["actions"],
                    "pattern": pattern["pattern_type"],
                    "priority": self._calculate_action_priority(cause, correlation_analysis)
                }
                recommendations.append(recommendation)
        
        # Add insights from similar cases
        if similar_cases and similar_cases[0]["relevance_score"] > 0.5:
            top_case = similar_cases[0]
            recommendations.append({
                "title": f"Historical precedent: {top_case['root_cause']}",
                "confidence": top_case["relevance_score"],
                "actions": [
                    f"Review similar case: {top_case['title']}",
                    f"Expected resolution time: {top_case['resolution_time']} hours",
                    "Apply lessons learned from previous incident"
                ],
                "pattern": "historical",
                "priority": "medium"
            })
        
        # Add correlation-based recommendations
        correlations = correlation_analysis.get("correlations", {})
        
        # Batch-specific recommendation
        batch_data = correlations.get("batch", {})
        if batch_data.get("suspect_batches"):
            worst_batch = batch_data["suspect_batches"][0]
            recommendations.append({
                "title": f"Material quality issue: Batch {worst_batch['batch_id']}",
                "confidence": 0.7,
                "actions": [
                    f"Quarantine remaining wafers from batch {worst_batch['batch_id']}",
                    "Request quality report from material supplier",
                    "Consider switching to alternate batch"
                ],
                "pattern": "batch_correlation",
                "priority": "high" if worst_batch["yield"] < 90 else "medium"
            })
        
        # Sort recommendations by priority and confidence
        recommendations.sort(key=lambda x: (
            {"high": 3, "medium": 2, "low": 1}.get(x["priority"], 0),
            x["confidence"]
        ), reverse=True)
        
        return recommendations[:5]  # Return top 5 recommendations
    
    def _calculate_action_priority(self, cause: Dict, 
                                   correlation_analysis: dict) -> str:
        """Calculate priority for an action"""
        
        # High priority if confidence > 0.8 and yield impact > 5%
        temporal = correlation_analysis.get("correlations", {}).get("temporal", {})
        yield_impact = temporal.get("yield_impact", 0)
        
        if cause["confidence"] > 0.8 and yield_impact > 5:
            return "high"
        elif cause["confidence"] > 0.6 or yield_impact > 3:
            return "medium"
        else:
            return "low"
    
    def _calculate_overall_confidence(self, recommendations: List[Dict]) -> float:
        """Calculate overall confidence in RCA hints"""
        
        if not recommendations:
            return 0.0
        
        # Weighted average of top recommendations
        weights = [0.4, 0.3, 0.2, 0.1, 0.0]  # Weights for top 5
        total_confidence = 0.0
        total_weight = 0.0
        
        for i, rec in enumerate(recommendations[:5]):
            weight = weights[i] if i < len(weights) else 0.0
            total_confidence += rec["confidence"] * weight
            total_weight += weight
        
        if total_weight > 0:
            return round(total_confidence / total_weight, 3)
        
        return 0.0
    
    def _determine_priority(self, alert: dict, recommendations: List[Dict]) -> str:
        """Determine overall priority for the alert"""
        
        # Consider alert severity
        severity = alert.get("severity", "medium")
        
        # Consider recommendation priorities
        if recommendations:
            top_priority = recommendations[0].get("priority", "medium")
            
            # Combine severity and recommendation priority
            if severity == "critical" or top_priority == "high":
                return "urgent"
            elif severity == "high" or top_priority == "medium":
                return "high"
            else:
                return "normal"
        
        return "normal"