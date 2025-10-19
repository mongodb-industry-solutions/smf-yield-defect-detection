"""
Scenario Analysis Prompt Templates

Reusable prompt builders for Claude LLM analysis of scenario data.
"""

from typing import Dict


def build_scenario_analysis_prompt(
    metadata: Dict,
    statistics: Dict,
    trend: Dict,
    comparative: Dict
) -> str:
    """
    Build Claude prompt for scenario analysis interpretation.
    
    Creates a comprehensive prompt that includes:
    - Scenario metadata (title, equipment, pattern type)
    - MongoDB statistical analysis results
    - Trend analysis data
    - Comparative window analysis
    - Ground truth (root cause, duration)
    
    Args:
        metadata: Scenario metadata dict (from load_scenario_metadata)
        statistics: Statistical analysis results (from get_multifacet_statistics)
        trend: Trend detection results (from detect_trend)
        comparative: Comparative window results (from get_comparative_windows)
        
    Returns:
        Formatted prompt string for Claude API
    """
    # Extract statistics
    overall = statistics.get('overall', {})
    violations = statistics.get('violations', {})
    anomaly = statistics.get('anomaly', {})
    
    # Extract trend data
    trend_direction = trend.get('direction', 'UNKNOWN')
    trend_change = trend.get('change_pct', 0)
    first_avg = trend.get('first_avg', 0)
    last_avg = trend.get('last_avg', 0)
    
    # Extract comparative data
    baseline = comparative.get('baseline', {})
    anomaly_comp = comparative.get('anomaly', {})
    deviation_pct = comparative.get('deviation_pct', 0)
    
    prompt = f"""Analyze this semiconductor manufacturing time series scenario:

SCENARIO: {metadata.get('title', 'Unknown')}
Equipment: {metadata.get('equipment_id', 'Unknown')}
Pattern Type: {metadata.get('pattern_type', 'Unknown')}
Duration: {metadata.get('duration_minutes', 0)} minutes

MONGODB STATISTICAL ANALYSIS:
- Overall Average: {overall.get('avg_particles', 0):.1f} particles
- Range: {overall.get('min_particles', 0):.0f} - {overall.get('max_particles', 0):.0f}
- Std Deviation: {overall.get('stddev_particles', 0):.1f}
- Threshold Violations: {violations.get('violation_count', 0)} readings above 1000

TREND ANALYSIS:
- Direction: {trend_direction}
- Change: {trend_change:+.1f}% (first 30min vs last 30min)
- First period avg: {first_avg:.1f}
- Last period avg: {last_avg:.1f}

COMPARATIVE WINDOWS:
- Baseline: {baseline.get('avg', 0):.1f} ± {baseline.get('stddev', 0):.1f} particles
- Anomaly Window: {anomaly_comp.get('avg', 0):.1f} ± {anomaly_comp.get('stddev', 0):.1f} particles (peak: {anomaly_comp.get('max', 0):.0f})
- Deviation: {deviation_pct:+.1f}% from baseline

GROUND TRUTH:
- Root Cause: {metadata.get('root_cause', 'Unknown')}
- Anomaly Duration: {metadata.get('anomaly_window', {}).get('end_minute', 0) - metadata.get('anomaly_window', {}).get('start_minute', 0)} minutes

Your task:
1. Provide risk assessment (LOW/MEDIUM/HIGH) with confidence score
2. Identify 3 key statistical insights that support the root cause
3. Suggest 2-3 immediate actions based on the pattern
4. Explain what MongoDB features made this analysis possible

Respond in JSON format:
{{
  "risk_level": "HIGH",
  "confidence": 0.89,
  "pattern_detected": "{metadata.get('pattern_type', 'unknown')}",
  "key_insights": ["insight 1", "insight 2", "insight 3"],
  "recommended_actions": ["action 1", "action 2"],
  "mongodb_showcase": "Brief explanation of MongoDB features used"
}}"""
    
    return prompt

