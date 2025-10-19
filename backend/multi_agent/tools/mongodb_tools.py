"""
MongoDB Aggregation Tools

Pure MongoDB query functions for scenario analysis.
Each function is stateless, reusable, and testable in isolation.
"""

import time
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


async def get_multifacet_statistics(db, scenario_id: str) -> Dict:
    """
    Execute $facet aggregation for parallel statistical analysis.
    
    Performs 4 parallel aggregations:
    - Overall statistics (avg, min, max, stddev, count)
    - Threshold violations (count of readings > 1000)
    - Hourly breakdown (avg/min/max per hour)
    - Anomaly window statistics
    
    Args:
        db: MongoDB database instance
        scenario_id: Scenario identifier
        
    Returns:
        Dict with keys: overall_stats, threshold_violations, hourly_stats, anomaly_data, elapsed_ms
    """
    start_time = time.time()
    
    stats_pipeline = [
        {"$match": {"metadata.scenario_id": scenario_id}},
        {
            "$facet": {
                # Overall statistics
                "overall_stats": [{
                    "$group": {
                        "_id": None,
                        "avg_particles": {"$avg": "$metrics.particle_count"},
                        "max_particles": {"$max": "$metrics.particle_count"},
                        "min_particles": {"$min": "$metrics.particle_count"},
                        "stddev_particles": {"$stdDevPop": "$metrics.particle_count"},
                        "readings_count": {"$sum": 1}
                    }
                }],
                
                # Threshold violations
                "threshold_violations": [
                    {"$match": {"metrics.particle_count": {"$gt": 1000}}},
                    {"$count": "violation_count"}
                ],
                
                # Hourly breakdown
                "hourly_stats": [
                    {
                        "$group": {
                            "_id": {
                                "$dateToString": {
                                    "format": "%Y-%m-%d %H:00",
                                    "date": "$timestamp"
                                }
                            },
                            "hour_avg": {"$avg": "$metrics.particle_count"},
                            "hour_max": {"$max": "$metrics.particle_count"},
                            "hour_min": {"$min": "$metrics.particle_count"}
                        }
                    },
                    {"$sort": {"_id": 1}}
                ],
                
                # Anomaly window data
                "anomaly_data": [
                    {"$match": {"metadata.scenario_label": "anomaly"}},
                    {
                        "$group": {
                            "_id": None,
                            "anomaly_avg": {"$avg": "$metrics.particle_count"},
                            "anomaly_max": {"$max": "$metrics.particle_count"},
                            "anomaly_count": {"$sum": 1}
                        }
                    }
                ]
            }
        }
    ]
    
    stats_result = await db.scenario_time_series.aggregate(stats_pipeline).to_list(1)
    stats_data = stats_result[0] if stats_result else {}
    
    elapsed_ms = (time.time() - start_time) * 1000
    
    # Extract results
    overall = stats_data.get('overall_stats', [{}])[0]
    violations = stats_data.get('threshold_violations', [{}])[0]
    hourly = stats_data.get('hourly_stats', [])
    anomaly = stats_data.get('anomaly_data', [{}])[0]
    
    return {
        "overall": overall,
        "violations": violations,
        "hourly": hourly,
        "anomaly": anomaly,
        "elapsed_ms": elapsed_ms
    }


async def get_rolling_window_analysis(db, scenario_id: str, 
                                       window_sizes: List[int] = [5, 10, 30]) -> Dict:
    """
    Execute $setWindowFields for rolling average calculations.
    
    Calculates rolling averages using MongoDB's window functions:
    - 5-minute rolling average
    - 10-minute rolling average
    - 30-minute rolling average
    
    Args:
        db: MongoDB database instance
        scenario_id: Scenario identifier
        window_sizes: List of window sizes in minutes (default: [5, 10, 30])
        
    Returns:
        Dict with keys: data (list of rolling avg data points), peaks, elapsed_ms
    """
    start_time = time.time()
    
    rolling_pipeline = [
        {"$match": {"metadata.scenario_id": scenario_id}},
        {"$sort": {"timestamp": 1}},
        {
            "$setWindowFields": {
                "sortBy": {"timestamp": 1},
                "output": {
                    "rolling_5min_avg": {
                        "$avg": "$metrics.particle_count",
                        "window": {"documents": [-4, 0]}  # 5 readings (5 minutes)
                    },
                    "rolling_10min_avg": {
                        "$avg": "$metrics.particle_count",
                        "window": {"documents": [-9, 0]}  # 10 readings
                    },
                    "rolling_30min_avg": {
                        "$avg": "$metrics.particle_count",
                        "window": {"documents": [-29, 0]}  # 30 readings
                    }
                }
            }
        },
        {
            "$project": {
                "timestamp": 1,
                "particle_count": "$metrics.particle_count",
                "rolling_5min_avg": 1,
                "rolling_10min_avg": 1,
                "rolling_30min_avg": 1,
                "_id": 0  # Exclude ObjectId from results
            }
        }
    ]
    
    rolling_result = await db.scenario_time_series.aggregate(rolling_pipeline).to_list(200)
    
    elapsed_ms = (time.time() - start_time) * 1000
    
    # Find peaks in rolling averages
    peaks = {}
    if rolling_result:
        max_5min = max(rolling_result, key=lambda x: x.get('rolling_5min_avg', 0))
        max_10min = max(rolling_result, key=lambda x: x.get('rolling_10min_avg', 0))
        peaks = {
            "5min_max": max_5min.get('rolling_5min_avg', 0),
            "10min_max": max_10min.get('rolling_10min_avg', 0)
        }
    
    return {
        "data": rolling_result,
        "peaks": peaks,
        "data_points": len(rolling_result),
        "elapsed_ms": elapsed_ms
    }


async def detect_trend(db, scenario_id: str) -> Dict:
    """
    Compare first 30min vs last 30min to detect trend direction.
    
    Uses MongoDB aggregation to split data into first and last 30-minute windows
    and calculates average particle count for each to determine trend.
    
    Args:
        db: MongoDB database instance
        scenario_id: Scenario identifier
        
    Returns:
        Dict with keys: first_avg, last_avg, change_pct, direction, elapsed_ms
    """
    start_time = time.time()
    
    # Calculate trend by comparing first 30 min vs last 30 min
    trend_pipeline = [
        {"$match": {"metadata.scenario_id": scenario_id}},
        {"$sort": {"timestamp": 1}},
        {
            "$facet": {
                "first_30": [
                    {"$limit": 30},
                    {"$group": {"_id": None, "avg": {"$avg": "$metrics.particle_count"}}}
                ],
                "last_30": [
                    {"$skip": 90},
                    {"$limit": 30},
                    {"$group": {"_id": None, "avg": {"$avg": "$metrics.particle_count"}}}
                ]
            }
        }
    ]
    
    trend_result = await db.scenario_time_series.aggregate(trend_pipeline).to_list(1)
    trend_data = trend_result[0] if trend_result else {}
    
    first_30_avg = trend_data.get('first_30', [{}])[0].get('avg', 0)
    last_30_avg = trend_data.get('last_30', [{}])[0].get('avg', 0)
    
    trend_change = ((last_30_avg / first_30_avg) - 1) * 100 if first_30_avg > 0 else 0
    trend_direction = "INCREASING" if trend_change > 10 else ("DECREASING" if trend_change < -10 else "STABLE")
    
    elapsed_ms = (time.time() - start_time) * 1000
    
    return {
        "first_avg": first_30_avg,
        "last_avg": last_30_avg,
        "change_pct": trend_change,
        "direction": trend_direction,
        "elapsed_ms": elapsed_ms
    }


async def get_comparative_windows(db, scenario_id: str) -> Dict:
    """
    Compare baseline vs anomaly vs recovery periods using $facet.
    
    Analyzes three time windows:
    - Baseline: First 30 minutes of normal operation
    - Anomaly: The anomaly window from scenario metadata
    - Recovery: Post-anomaly period (if exists)
    
    Args:
        db: MongoDB database instance
        scenario_id: Scenario identifier
        
    Returns:
        Dict with keys: baseline, anomaly, recovery, deviation_pct, elapsed_ms
    """
    start_time = time.time()
    
    # Get baseline, anomaly, and recovery periods
    comparative_pipeline = [
        {"$match": {"metadata.scenario_id": scenario_id}},
        {"$sort": {"timestamp": 1}},
        {
            "$facet": {
                "baseline": [
                    {"$match": {"metadata.scenario_label": "normal"}},
                    {"$limit": 30},
                    {
                        "$group": {
                            "_id": None,
                            "avg": {"$avg": "$metrics.particle_count"},
                            "stddev": {"$stdDevPop": "$metrics.particle_count"}
                        }
                    }
                ],
                "anomaly": [
                    {"$match": {"metadata.scenario_label": "anomaly"}},
                    {
                        "$group": {
                            "_id": None,
                            "avg": {"$avg": "$metrics.particle_count"},
                            "stddev": {"$stdDevPop": "$metrics.particle_count"},
                            "max": {"$max": "$metrics.particle_count"}
                        }
                    }
                ],
                "recovery": [
                    {"$match": {"metadata.scenario_label": "normal"}},
                    {"$skip": 90},
                    {
                        "$group": {
                            "_id": None,
                            "avg": {"$avg": "$metrics.particle_count"}
                        }
                    }
                ]
            }
        }
    ]
    
    comparative_result = await db.scenario_time_series.aggregate(comparative_pipeline).to_list(1)
    comparative_data = comparative_result[0] if comparative_result else {}
    
    baseline_stats = comparative_data.get('baseline', [{}])[0] if comparative_data.get('baseline') else {}
    anomaly_stats = comparative_data.get('anomaly', [{}])[0] if comparative_data.get('anomaly') else {}
    recovery_stats = comparative_data.get('recovery', [{}])[0] if comparative_data.get('recovery') else {}
    
    baseline_avg = baseline_stats.get('avg', 0)
    anomaly_avg = anomaly_stats.get('avg', 0)
    deviation_pct = ((anomaly_avg / baseline_avg) - 1) * 100 if baseline_avg > 0 else 0
    
    elapsed_ms = (time.time() - start_time) * 1000
    
    return {
        "baseline": baseline_stats,
        "anomaly": anomaly_stats,
        "recovery": recovery_stats,
        "deviation_pct": deviation_pct,
        "elapsed_ms": elapsed_ms
    }

