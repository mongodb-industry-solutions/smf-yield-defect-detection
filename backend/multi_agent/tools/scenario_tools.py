"""
Scenario Analysis Coordination Tools

High-level orchestration functions that coordinate MongoDB tools
for comprehensive scenario analysis.
"""

import logging
import time
from typing import Optional, Dict
from datetime import datetime, timedelta
from multi_agent.tools.mongodb_tools import (
    get_multifacet_statistics,
    get_rolling_window_analysis,
    detect_trend,
    get_comparative_windows
)

logger = logging.getLogger(__name__)


async def _regenerate_scenario_with_current_time(db, scenario_id: str) -> bool:
    """
    Regenerate a specific scenario with current timestamps.
    
    Dynamically generates fresh scenario data when requested, ensuring
    demo data always appears recent and relevant.
    
    Args:
        db: MongoDB database instance
        scenario_id: Scenario to regenerate
        
    Returns:
        True if successful, False otherwise
    """
    logger.info(f"🔄 Regenerating scenario '{scenario_id}' with current timestamps...")
    
    try:
        # Import scenario generator functions
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "data_generation"))
        from generate_scenarios import (
            generate_gradual_drift_scenario,
            generate_sudden_spike_scenario,
            generate_oscillating_pattern_scenario,
            generate_scenario_metadata
        )
        
        # Map scenario_id to generator function
        generators = {
            "gradual_drift": (generate_gradual_drift_scenario, 0),
            "sudden_spike": (generate_sudden_spike_scenario, 1),
            "oscillating_pattern": (generate_oscillating_pattern_scenario, 2)
        }
        
        if scenario_id not in generators:
            logger.error(f"❌ Unknown scenario: {scenario_id}")
            return False
        
        generator_func, metadata_index = generators[scenario_id]
        
        # Generate fresh data with current timestamps
        scenario_data = generator_func()
        metadata_list = generate_scenario_metadata()
        metadata = metadata_list[metadata_index]
        
        # Delete old scenario data
        await db.scenario_time_series.delete_many({"metadata.scenario_id": scenario_id})
        await db.scenario_metadata.delete_one({"scenario_id": scenario_id})
        
        # Insert fresh data
        if scenario_data:
            await db.scenario_time_series.insert_many(scenario_data)
        await db.scenario_metadata.insert_one(metadata)
        
        logger.info(f"✅ Scenario regenerated: {len(scenario_data)} readings inserted")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to regenerate scenario: {e}")
        import traceback
        traceback.print_exc()
        return False


async def load_scenario_metadata(db, scenario_id: str) -> Optional[Dict]:
    """
    Load scenario metadata from MongoDB with auto-refresh.
    
    Automatically regenerates scenario with current timestamps if:
    - Scenario doesn't exist
    - Scenario data is older than 30 minutes
    
    This ensures demo scenarios always appear recent and relevant.
    
    Args:
        db: MongoDB database instance
        scenario_id: Scenario identifier
        
    Returns:
        Metadata dict or None if not found
    """
    logger.info(f"\n📋 [STEP 1] Loading scenario metadata...")
    metadata_start = time.time()
    
    metadata = await db.scenario_metadata.find_one({"scenario_id": scenario_id})
    
    # Check if scenario needs regeneration
    should_regenerate = False
    
    if not metadata:
        logger.info(f"   ⚠️  Scenario not found, will generate fresh data")
        should_regenerate = True
    else:
        # Check if data is stale (older than 30 minutes)
        # Get the most recent timestamp from time series data
        recent_reading = await db.scenario_time_series.find_one(
            {"metadata.scenario_id": scenario_id},
            sort=[("timestamp", -1)]
        )
        
        if recent_reading and 'timestamp' in recent_reading:
            data_age = datetime.now() - recent_reading['timestamp']
            if data_age > timedelta(minutes=30):
                logger.info(f"   ⚠️  Scenario data is {data_age.total_seconds()/60:.1f} minutes old, regenerating...")
                should_regenerate = True
    
    # Regenerate if needed
    if should_regenerate:
        success = await _regenerate_scenario_with_current_time(db, scenario_id)
        if not success:
            logger.error(f"❌ Failed to regenerate scenario")
            return None
        
        # Reload metadata after regeneration
        metadata = await db.scenario_metadata.find_one({"scenario_id": scenario_id})
    
    if not metadata:
        logger.error(f"❌ Scenario {scenario_id} not found after regeneration attempt")
        return None
    
    logger.info(f"✅ Metadata loaded in {(time.time() - metadata_start)*1000:.0f}ms")
    logger.info(f"   Title: {metadata['title']}")
    logger.info(f"   Equipment: {metadata['equipment_id']}")
    logger.info(f"   Pattern: {metadata['pattern_type']}")
    logger.info(f"   Duration: {metadata['duration_minutes']} minutes ({metadata['data_points']} readings)")
    
    return metadata


async def perform_comprehensive_analysis(db, scenario_id: str) -> Dict:
    """
    Orchestrate all MongoDB aggregations for scenario analysis.
    
    Executes 4 MongoDB aggregation pipelines:
    1. Multi-facet statistics ($facet)
    2. Rolling window analysis ($setWindowFields)
    3. Trend detection (time-based comparison)
    4. Comparative window analysis (baseline vs anomaly)
    
    All queries are executed and timing metrics are captured.
    
    Args:
        db: MongoDB database instance
        scenario_id: Scenario identifier
        
    Returns:
        Comprehensive dict with:
        - statistics: Multi-facet statistical results
        - rolling_windows: Rolling average data
        - trend: Trend detection results
        - comparative: Baseline vs anomaly comparison
        - execution_metrics: Timing breakdown
    """
    overall_start = time.time()
    
    # ===== Step 2: Multi-Facet Statistical Summary =====
    logger.info(f"\n📊 [STEP 2] Executing multi-facet statistical aggregation...")
    logger.info(f"   Pipeline: $facet with 4 parallel aggregations")
    
    stats_result = await get_multifacet_statistics(db, scenario_id)
    
    logger.info(f"⚡ [MONGODB] Multi-facet aggregation completed in {stats_result['elapsed_ms']:.0f}ms")
    logger.info(f"   📈 Results:")
    logger.info(f"      - Average: {stats_result['overall'].get('avg_particles', 0):.1f} particles")
    logger.info(f"      - Range: {stats_result['overall'].get('min_particles', 0):.0f} - {stats_result['overall'].get('max_particles', 0):.0f}")
    logger.info(f"      - Std Dev: {stats_result['overall'].get('stddev_particles', 0):.1f}")
    logger.info(f"      - Threshold Violations: {stats_result['violations'].get('violation_count', 0)}")
    logger.info(f"      - Anomaly Window Avg: {stats_result['anomaly'].get('anomaly_avg', 0):.1f} particles")
    
    # ===== Step 3: Rolling Window Analysis =====
    logger.info(f"\n📈 [STEP 3] Executing rolling window analysis ($setWindowFields)...")
    logger.info(f"   Window sizes: 5min, 10min, 30min")
    
    rolling_result = await get_rolling_window_analysis(db, scenario_id)
    
    logger.info(f"⚡ [MONGODB] Rolling window analysis completed in {rolling_result['elapsed_ms']:.0f}ms")
    logger.info(f"   📊 Computed {rolling_result['data_points']} rolling average data points")
    
    if rolling_result['peaks']:
        logger.info(f"   📈 Rolling Peaks:")
        logger.info(f"      - 5min max: {rolling_result['peaks']['5min_max']:.1f} particles")
        logger.info(f"      - 10min max: {rolling_result['peaks']['10min_max']:.1f} particles")
    
    # ===== Step 4: Trend Detection =====
    logger.info(f"\n🔍 [STEP 4] Detecting trends and inflection points...")
    
    trend_result = await detect_trend(db, scenario_id)
    
    logger.info(f"⚡ [MONGODB] Trend detection completed in {trend_result['elapsed_ms']:.0f}ms")
    logger.info(f"   📊 Trend Analysis:")
    logger.info(f"      - First 30min avg: {trend_result['first_avg']:.1f} particles")
    logger.info(f"      - Last 30min avg: {trend_result['last_avg']:.1f} particles")
    logger.info(f"      - Change: {trend_result['change_pct']:+.1f}%")
    logger.info(f"      - Direction: {trend_result['direction']}")
    
    # ===== Step 5: Comparative Window Analysis =====
    logger.info(f"\n🔬 [STEP 5] Comparative window analysis (baseline vs anomaly vs recovery)...")
    
    comparative_result = await get_comparative_windows(db, scenario_id)
    
    logger.info(f"⚡ [MONGODB] Comparative analysis completed in {comparative_result['elapsed_ms']:.0f}ms")
    logger.info(f"   📊 Comparative Results:")
    logger.info(f"      - Baseline: {comparative_result['baseline'].get('avg', 0):.1f} ± {comparative_result['baseline'].get('stddev', 0):.1f} particles")
    logger.info(f"      - Anomaly: {comparative_result['anomaly'].get('avg', 0):.1f} ± {comparative_result['anomaly'].get('stddev', 0):.1f} particles")
    logger.info(f"      - Deviation: {comparative_result['deviation_pct']:+.1f}% from baseline")
    logger.info(f"      - Peak: {comparative_result['anomaly'].get('max', 0):.0f} particles")
    
    # Calculate total MongoDB time
    mongodb_time_ms = (
        stats_result['elapsed_ms'] +
        rolling_result['elapsed_ms'] +
        trend_result['elapsed_ms'] +
        comparative_result['elapsed_ms']
    )
    
    return {
        "statistics": stats_result,
        "rolling_windows": rolling_result,
        "trend": trend_result,
        "comparative": comparative_result,
        "execution_metrics": {
            "mongodb_total_ms": mongodb_time_ms,
            "stats_ms": stats_result['elapsed_ms'],
            "rolling_ms": rolling_result['elapsed_ms'],
            "trend_ms": trend_result['elapsed_ms'],
            "comparative_ms": comparative_result['elapsed_ms']
        }
    }

