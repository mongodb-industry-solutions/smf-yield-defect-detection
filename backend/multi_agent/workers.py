"""
Multi-Agent Worker Agents
Worker agents for alert analysis workflow
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
import os
from multi_agent.simple_bedrock import call_claude
from bson import ObjectId
import time
from datetime import timezone

logger = logging.getLogger(__name__)


async def get_equipment_statistical_context(equipment_id: str, db, current_particle_count: float = 0) -> dict:
    """
    Get statistical context using MongoDB time series aggregations

    Calculates avg, max, min, stddev from last 1 hour of readings
    Performance: 10-50ms (practical for real-time)

    Args:
        equipment_id: Equipment identifier
        db: MongoDB database instance
        current_particle_count: Current reading for deviation calculation

    Returns:
        Statistical context dict with averages, ranges, and deviations
    """
    logger.info(f"📊 Fetching statistical context for {equipment_id}")

    try:
        pipeline = [
            {
                "$match": {
                    "equipment_id": equipment_id,
                    "timestamp": {"$gte": datetime.utcnow() - timedelta(hours=1)}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "avg_particles": {"$avg": "$metrics.particle_count"},
                    "max_particles": {"$max": "$metrics.particle_count"},
                    "min_particles": {"$min": "$metrics.particle_count"},
                    "stddev_particles": {"$stdDevPop": "$metrics.particle_count"},
                    "readings_count": {"$sum": 1}
                }
            }
        ]

        # Query process_sensor_ts for historical statistical analysis (time series collection)
        stats = await db.process_sensor_ts.aggregate(pipeline).to_list(1)

        if stats and stats[0]:
            s = stats[0]
            # Calculate sigma deviation
            if s.get('stddev_particles', 0) > 0:
                s['deviation_sigma'] = round(
                    (current_particle_count - s['avg_particles']) / s['stddev_particles'],
                    2
                )
            else:
                s['deviation_sigma'] = 0

            logger.info(f"   ✅ Stats retrieved: avg={s.get('avg_particles', 0):.1f}, "
                       f"stddev={s.get('stddev_particles', 0):.1f}, "
                       f"deviation={s.get('deviation_sigma', 0):.1f}σ")
            return s

        logger.warning(f"   ⚠️ No historical data found for {equipment_id}")
        return {}

    except Exception as e:
        logger.error(f"   ❌ Failed to get statistical context: {e}")
        return {}


async def monitoring_agent_tool(state: dict) -> dict:
    """
    Monitoring Agent: Proactively filters false positives

    Uses:
    - MongoDB Time Series Statistical Context (10-50ms aggregations)
    - LLM reasoning (Claude Haiku for speed + cost)

    Input: Alert context with sensor readings
    Output: Decision (create_alert: true/false) + reasoning + confidence

    Args:
        state: AlertAnalysisState dict

    Returns:
        Updated state with monitoring_decision and statistical_context
    """
    logger.info(f"🔵 [MONITORING AGENT] Starting analysis for alert {state['alert_id']}")
    logger.info(f"🔵    Equipment: {state['equipment_id']}, Type: {state['excursion_type']}")

    current_metrics = state.get('metrics', {})
    equipment_id = state['equipment_id']
    current_particle_count = current_metrics.get('particle_count', 0)

    # Get statistical context (fast MongoDB aggregation)
    client = AsyncIOMotorClient(os.getenv('MONGODB_URI'))
    db = client[os.getenv('MDB_DATABASE_NAME', 'smf-yield-defect')]

    stats = await get_equipment_statistical_context(equipment_id, db, current_particle_count)

    # Calculate deviation percentage
    if stats.get('avg_particles'):
        stats['deviation_pct'] = round(
            ((current_particle_count / stats['avg_particles']) - 1) * 100,
            1
        )
    else:
        stats['deviation_pct'] = 0

    logger.info(f"🔵    📈 Current vs Average: {stats.get('deviation_pct', 0):+.1f}% "
               f"({stats.get('deviation_sigma', 0):.1f}σ)")

    # Build LLM prompt with statistical context
    avg_particles = stats.get('avg_particles')
    min_particles = stats.get('min_particles')
    max_particles = stats.get('max_particles')
    stddev_particles = stats.get('stddev_particles')

    avg_str = f"{avg_particles:.1f}" if avg_particles is not None else "N/A"
    min_str = f"{min_particles:.0f}" if min_particles is not None else "N/A"
    max_str = f"{max_particles:.0f}" if max_particles is not None else "N/A"
    stddev_str = f"{stddev_particles:.1f}" if stddev_particles is not None else "N/A"

    stats_text = f"""
STATISTICAL CONTEXT (Last 1 Hour via MongoDB):
- Average Particle Count: {avg_str}
- Range: {min_str} to {max_str}
- Std Deviation: {stddev_str}
- Current vs Avg: {stats.get('deviation_pct', 0):+.1f}% ({stats.get('deviation_sigma', 0):.1f}σ)
- Readings Analyzed: {stats.get('readings_count', 0)}
"""

    prompt = f"""You are a monitoring agent for semiconductor manufacturing. Analyze sensor data to determine if an alert should be created.

EQUIPMENT: {equipment_id}

CURRENT READING:
- Particle Count: {current_metrics.get('particle_count', 'N/A')}
- RF Power: {current_metrics.get('rf_power', 'N/A')}W
- Temperature: {current_metrics.get('temperature', 'N/A')}°C

{stats_text}

DECISION CRITERIA:

CREATE ALERT (create_alert=true) if:
- Statistical deviation >2.5σ (highly unusual)
- Deviation >30% from hourly average
- Clear trend: drift, sustained spike, oscillation

FILTER ALERT (create_alert=false) if:
- Statistical deviation <1.5σ (within normal variation)
- Deviation <15% from average
- Single isolated spike with no trend (likely sensor glitch)

Respond ONLY with valid JSON:
{{
  "create_alert": true,
  "reasoning": "Brief explanation referencing statistical deviation",
  "confidence": 0.85,
  "pattern_detected": "drift"
}}

Valid pattern_detected values: "drift", "spike", "oscillation", "normal_variation", "single_spike"
"""

    try:
        # Call Claude via simple Bedrock client (uses your existing AWS SSO session)
        logger.info(f"🔵    🤖 Invoking Claude Haiku for decision...")

        response = call_claude(prompt, temperature=0.2, max_tokens=300)
        decision = json.loads(response)

        # Validate response
        required_fields = ["create_alert", "reasoning", "confidence"]
        if not all(field in decision for field in required_fields):
            logger.error(f"🔵    ❌ Invalid LLM response, missing required fields")
            raise ValueError(f"Missing required fields in LLM response: {decision}")

        logger.info(f"🔵    ✅ Decision: {'CREATE ALERT' if decision['create_alert'] else 'FILTER'}")
        logger.info(f"🔵    📊 Confidence: {decision['confidence']:.2f}, Pattern: {decision.get('pattern_detected', 'unknown')}")
        logger.info(f"🔵    💡 Reasoning: {decision['reasoning']}")

        # Return updated state
        return {
            "monitoring_decision": decision,
            "statistical_context": stats,
            "workflow_stage": "investigation" if decision['create_alert'] else "complete"
        }

    except json.JSONDecodeError as e:
        logger.error(f"🔵    ❌ Failed to parse LLM response as JSON: {e}")
        logger.error(f"🔵    Raw response: {response}")
        # Fail-safe: create alert on error
        return {
            "monitoring_decision": {
                "create_alert": True,
                "reasoning": f"LLM response parsing failed, creating alert as fail-safe",
                "confidence": 0.5,
                "pattern_detected": "error"
            },
            "statistical_context": stats,
            "workflow_stage": "investigation"
        }

    except Exception as e:
        logger.error(f"🔵    ❌ Monitoring agent error: {e}")
        # Fail-safe: create alert on error
        return {
            "monitoring_decision": {
                "create_alert": True,
                "reasoning": f"Agent error: {str(e)}, creating alert as fail-safe",
                "confidence": 0.5,
                "pattern_detected": "error"
            },
            "statistical_context": stats,
            "workflow_stage": "investigation"
        }

    finally:
        client.close()


async def investigation_agent_tool(state: dict) -> dict:
    """
    Investigation Agent: Wraps CorrelationEngine with LLM interpretation

    Uses:
    - Existing CorrelationEngine service (reuse existing code!)
    - LLM to interpret raw correlation data into actionable insights

    Input: Alert that passed monitoring filter
    Output: Correlation results + key findings + LLM interpretation

    Args:
        state: AlertAnalysisState dict with alert_id

    Returns:
        Updated state with correlation_results, investigation_summary, and key_findings
    """
    logger.info(f"🟠 [INVESTIGATION AGENT] Starting correlation analysis for alert {state['alert_id']}")
    logger.info(f"🟠    Equipment: {state.get('equipment_id')}, Excursion: {state.get('excursion_type')}")

    alert_id = state['alert_id']
    logger.info(f"🟠    🔑 Using alert_id (ObjectId): {alert_id}, type: {type(alert_id)}")

    try:
        # Import CorrelationEngine (reuse existing service!)
        from services.correlation_engine import CorrelationEngine

        logger.info(f"🟠    🔄 Initializing CorrelationEngine...")
        logger.info(f"📊    Querying wafer_defects, process_context, alerts collections...")

        # Initialize engine and run analysis
        engine = CorrelationEngine()
        logger.info(f"🟠    🔍 Running correlation analysis with ObjectId: {alert_id}...")

        correlation_data = await engine.analyze_alert(alert_id)

        # Log key metrics
        confidence = correlation_data.get('confidence_score', 0)
        affected_wafers_data = correlation_data.get('affected_wafers', {})
        affected_total = affected_wafers_data.get('total', 0)

        logger.info(f"🟠    📊 Correlation complete: {confidence:.0%} confidence, {affected_total} wafers affected")
        logger.info(f"🟠    📈 Wafer breakdown: Pre={affected_wafers_data.get('pre_alert', 0)}, "
                   f"During={affected_wafers_data.get('during_alert', 0)}, "
                   f"Post={affected_wafers_data.get('post_alert', 0)}")

        # Extract key correlation data for LLM prompt
        correlations = correlation_data.get('correlations', {})
        temporal = correlations.get('temporal', {})
        batch = correlations.get('batch', {})
        spatial = correlations.get('spatial', {})
        process_context = correlations.get('process_context', {})

        # Log detailed correlation findings
        logger.info(f"🟠    🔍 Temporal: {temporal.get('yield_impact', 0):.1f}% yield drop, "
                   f"{temporal.get('correlation_strength', 0):.2f} strength")
        logger.info(f"🟠    🧪 Batch: {len(batch.get('suspect_batches', []))} suspect batches")
        logger.info(f"🟠    📐 Spatial: {len(spatial.get('dominant_patterns', []))} dominant patterns")
        logger.info(f"🟠    ⚠️  Problematic materials: {len(process_context.get('problematic_materials', []))}")

        # Build concise summary for LLM
        prompt = f"""Analyze semiconductor manufacturing correlation data and provide key findings.

CORRELATION ANALYSIS RESULTS:

Affected Wafers: {affected_total}
- Pre-alert: {correlation_data.get('affected_wafers', {}).get('pre_alert', 0)}
- During alert: {correlation_data.get('affected_wafers', {}).get('during_alert', 0)}
- Post-alert: {correlation_data.get('affected_wafers', {}).get('post_alert', 0)}

Temporal Correlation:
- Yield Impact: {temporal.get('yield_impact', 0):.1f}% drop
- Correlation Strength: {temporal.get('correlation_strength', 0):.2f}
- Defect Rate Change: +{temporal.get('defect_rate_change', 0):.0f} defects
- Time Lag: {temporal.get('time_lag_hours', 'N/A')} hours

Batch Analysis:
- Suspect Batches: {len(batch.get('suspect_batches', []))}
{chr(10).join([f"  • {b.get('batch_id')}: {b.get('avg_yield', 0):.1f}% yield ({b.get('wafer_count', 0)} wafers)" for b in batch.get('suspect_batches', [])[:3]])}

Spatial Patterns:
{chr(10).join([f"  • {p.get('pattern')}: {p.get('frequency', 0)} wafers ({p.get('avg_yield', 0):.1f}% avg yield)" for p in spatial.get('dominant_patterns', [])[:3]])}

Problematic Materials:
{chr(10).join([f"  • {m.get('type')}: {m.get('id')} - {', '.join([i.get('severity', '') + ' issue' for i in m.get('issues', [])[:2]])}" for m in process_context.get('problematic_materials', [])[:2]]) if process_context.get('problematic_materials') else '  None detected'}

Overall Confidence: {confidence:.0%}

Provide:
1. Top 3 key findings (be specific with numbers, yields, batch IDs)
2. Overall significance (1-2 sentences on business impact)

Be concise, technical, and focus on actionable insights."""

        # Call Claude for interpretation
        logger.info(f"🟠    🤖 Invoking Claude Haiku for interpretation...")
        logger.info(f"🟠    📝 Prompt length: {len(prompt)} chars")

        response = call_claude(prompt, temperature=0.2, max_tokens=400)

        logger.info(f"🟠    ✅ LLM response received ({len(response)} chars)")

        # Parse response to extract key findings
        lines = response.strip().split('\n')
        key_findings = []
        for line in lines:
            stripped = line.strip()
            # Look for bullet points or numbered items
            if stripped and (stripped[0] in ('•', '-', '1', '2', '3', '*') or stripped.startswith('- ')):
                # Clean up the finding
                finding = stripped.lstrip('•-123*. ').strip()
                if finding and len(finding) > 10:  # Meaningful findings only
                    key_findings.append(finding)

        # Take top 3 findings
        key_findings = key_findings[:3]

        logger.info(f"🟠    ✅ Investigation complete")
        logger.info(f"🟠    📋 Key findings extracted: {len(key_findings)}")
        for i, finding in enumerate(key_findings, 1):
            logger.info(f"🟠       {i}. {finding[:100]}{'...' if len(finding) > 100 else ''}")

        logger.info(f"🟠    🎯 Next stage: RCA")

        # Return updated state
        return {
            "correlation_results": correlation_data,
            "investigation_summary": response,
            "key_findings": key_findings,
            "workflow_stage": "rca"  # Proceed to RCA stage
        }

    except ValueError as e:
        # Alert not found error
        logger.error(f"🟠    ❌ Alert not found: {e}")
        return {
            "correlation_results": {},
            "investigation_summary": f"Alert {alert_id} not found in database",
            "key_findings": [],
            "workflow_stage": "complete"  # Can't proceed without alert
        }

    except Exception as e:
        logger.error(f"🟠    ❌ Investigation agent error: {e}")
        # Return minimal results, allow workflow to continue
        return {
            "correlation_results": {},
            "investigation_summary": f"Investigation failed: {str(e)}",
            "key_findings": [],
            "workflow_stage": "rca"  # Still try RCA even if investigation fails
        }


async def rca_agent_tool(state: dict) -> dict:
    """
    RCA Agent (Worker 3): Root Cause Analysis with LLM validation

    Uses:
    - Existing RCAGenerator service (reuses existing code!)
    - LLM to validate and prioritize pattern-based recommendations

    Returns to supervisor for next decision
    """

    alert_id = state.get('alert_id')
    equipment_id = state.get('equipment_id', 'Unknown')
    excursion_type = state.get('excursion_type', 'Unknown')

    logger.info(f"🟣 [RCA AGENT] Starting root cause analysis for alert {alert_id}")
    logger.info(f"🟣    Equipment: {equipment_id}, Excursion: {excursion_type}")

    try:
        from services.rca_generator import RCAGenerator

        logger.info(f"🟣    🔄 Initializing RCAGenerator...")
        logger.info(f"📊    Querying historical_knowledge collection...")
        rca_gen = RCAGenerator()

        logger.info(f"🟣    🔍 Running pattern-based RCA analysis...")
        rca_data = await rca_gen.generate_rca_hints(alert_id)

        # Extract top recommendations
        recommendations = rca_data.get('recommendations', [])
        logger.info(f"🟣    📋 Generated {len(recommendations)} RCA recommendations")

        # Log top recommendations
        for i, rec in enumerate(recommendations[:3], 1):
            logger.info(f"🟣       {i}. {rec.get('title', 'Unknown')} "
                       f"(confidence: {rec.get('confidence', 0):.0%})")

        # Get investigation summary for validation context
        investigation_summary = state.get('investigation_summary', '')
        key_findings = state.get('key_findings', [])
        correlation_confidence = state.get('correlation_results', {}).get('confidence_score', 0)

        # Build context for LLM validation
        recs_text = "\n".join([
            f"{i+1}. {rec.get('title', 'Unknown')} ({rec.get('confidence', 0):.0%} confidence)"
            for i, rec in enumerate(recommendations[:5])
        ])

        findings_text = "\n".join([f"• {f}" for f in key_findings[:3]]) if key_findings else "No investigation findings available"

        # LLM validates and synthesizes recommendations
        prompt = f"""You are analyzing root cause recommendations for a semiconductor manufacturing alert.

PATTERN-BASED RCA RECOMMENDATIONS:
{recs_text}

INVESTIGATION FINDINGS (from correlation analysis):
{findings_text}

CORRELATION CONFIDENCE: {correlation_confidence:.0%}

Your task:
1. Do the RCA recommendations align with the investigation findings? (Yes/No + brief reason)
2. Which top 2 root causes should be prioritized based on the evidence?
3. Any additional insights to consider?

Respond in 3-4 sentences. Be concise and specific."""

        logger.info(f"🟣    🤖 Calling Claude for RCA validation...")
        validation_response = call_claude(prompt, temperature=0.3, max_tokens=300)

        logger.info(f"🟣    ✅ RCA validation complete")
        logger.info(f"🟣    📝 Validation: {validation_response[:150]}...")

        # Extract validated causes (high confidence recommendations)
        validated_causes = [
            rec.get('title', 'Unknown')
            for rec in recommendations[:3]
            if rec.get('confidence', 0) > 0.5
        ]

        logger.info(f"🟣    ✅ {len(validated_causes)} high-confidence root causes identified")
        for i, cause in enumerate(validated_causes, 1):
            logger.info(f"🟣       {i}. {cause}")

        logger.info(f"🟣    🎯 Next stage: Supervisor")

        # Return updated state
        return {
            "rca_patterns": rca_data,
            "rca_validation": validation_response,
            "validated_causes": validated_causes,
            "workflow_stage": "complete"  # RCA is final stage
        }

    except ValueError as e:
        # Alert not found error
        logger.error(f"🟣    ❌ Alert not found: {e}")
        return {
            "rca_patterns": {},
            "rca_validation": f"Alert {alert_id} not found in database",
            "validated_causes": [],
            "workflow_stage": "complete"
        }

    except Exception as e:
        logger.error(f"🟣    ❌ RCA agent error: {e}")
        # Return minimal results
        return {
            "rca_patterns": {},
            "rca_validation": f"RCA analysis failed: {str(e)}",
            "validated_causes": [],
            "workflow_stage": "complete"
        }


async def analyze_scenario_tool(scenario_id: str, db) -> dict:
    """
    UPDATED VERSION - NO DEDUPLICATION - Creates NEW alert every time
    Scenario Analysis Agent Tool (Orchestration Layer)
    
    Analyzes pre-seeded failure scenarios using advanced MongoDB aggregations to showcase
    MongoDB's time series capabilities. Designed for <5 second execution time.
    
    Creates ONE alert per scenario (with deduplication) to demonstrate full monitoring flow.
    
    Architecture:
    - Orchestrates modular tool functions from multi_agent.tools
    - Each responsibility (MongoDB queries, alerts, prompts) is separated
    - Maintains comprehensive logging for demo purposes
    
    Workflow:
    1. Load metadata (scenario_tools.load_scenario_metadata)
    2. Check/create alert (alert_tools)
    3. Run MongoDB analysis (scenario_tools.perform_comprehensive_analysis)
    4. Generate Claude insights (prompts.build_scenario_analysis_prompt + simple_bedrock)
    5. Return comprehensive results
    
    MongoDB Aggregations Demonstrated (via mongodb_tools):
    - Multi-facet statistical summary ($facet)
    - Rolling window analysis ($setWindowFields)
    - Trend detection (linear regression)
    - Comparative window analysis (baseline vs anomaly vs recovery)
    
    Args:
        scenario_id: Scenario identifier (gradual_drift, sudden_spike, oscillating_pattern)
        db: MongoDB database instance
        
    Returns:
        Comprehensive analysis including MongoDB query results, alert info, and Claude insights
        
    Reduced from ~450 lines to ~80 lines via tool extraction
    """
    # Import modular tools
    from multi_agent.tools.scenario_tools import (
        load_scenario_metadata,
        perform_comprehensive_analysis
    )
    from multi_agent.tools.alert_tools import (
        check_existing_scenario_alert,
        create_scenario_alert
    )
    from multi_agent.prompts.scenario_prompts import (
        build_scenario_analysis_prompt
    )
    
    logger.info("=" * 80)
    logger.info(f"🔍 [SCENARIO ANALYZER] Starting comprehensive analysis for: {scenario_id}")
    logger.info("=" * 80)
    
    overall_start = time.time()
    alert_id = None
    alert_created = False  # Initialize to False, will be set to True when alert is created
    
    try:
        # ===== Step 1: Load Scenario Metadata =====
        metadata = await load_scenario_metadata(db, scenario_id)
        if not metadata:
            return {"error": f"Scenario {scenario_id} not found"}
        
        # ===== Steps 2-5: Execute Comprehensive MongoDB Analysis FIRST =====
        # Execute MongoDB analysis before alert creation so we can include results in alert
        analysis_results = await perform_comprehensive_analysis(db, scenario_id)
        
        # ===== Step 6: Claude Analysis (Before Alert Creation) =====
        logger.info(f"\n🧠 [STEP 6] Invoking Claude for insight generation...")
        logger.info(f"   Model: anthropic.claude-3-haiku-20240307-v1:0")
        claude_start = time.time()
        
        # Build comprehensive prompt using template
        prompt = build_scenario_analysis_prompt(
            metadata,
            analysis_results['statistics'],
            analysis_results['trend'],
            analysis_results['comparative']
        )
        
        logger.info(f"   📝 Prompt length: {len(prompt)} characters")
        
        claude_response = call_claude(prompt, temperature=0.2, max_tokens=600)
        claude_analysis = json.loads(claude_response)
        
        claude_elapsed = (time.time() - claude_start) * 1000
        logger.info(f"⚡ [CLAUDE] Analysis completed in {claude_elapsed:.0f}ms")
        logger.info(f"   🎯 Risk Level: {claude_analysis.get('risk_level', 'UNKNOWN')}")
        logger.info(f"   📊 Confidence: {claude_analysis.get('confidence', 0):.2f}")
        logger.info(f"   🔍 Pattern: {claude_analysis.get('pattern_detected', 'unknown')}")
        
        # Create comprehensive analysis summary for alert's monitoring_agent_analysis field
        # This includes BOTH MongoDB results AND Claude's LLM interpretation
        mongodb_analysis_for_alert = {
            "statistical_summary": {
                "avg_particle_count": round(analysis_results['statistics']['overall'].get('avg_particles', 0), 1),
                "min": int(analysis_results['statistics']['overall'].get('min_particles', 0)),
                "max": int(analysis_results['statistics']['overall'].get('max_particles', 0)),
                "stddev": round(analysis_results['statistics']['overall'].get('stddev_particles', 0), 1),
                "threshold_violations": analysis_results['statistics']['violations'].get('violation_count', 0),
                "readings_analyzed": analysis_results['statistics']['overall'].get('readings_count', 0)
            },
            "trend_analysis": {
                "direction": analysis_results['trend']['direction'],
                "change_percentage": round(analysis_results['trend']['change_pct'], 1),
                "first_period_avg": round(analysis_results['trend']['first_avg'], 1),
                "last_period_avg": round(analysis_results['trend']['last_avg'], 1)
            },
            "comparative_windows": {
                "baseline_avg": round(analysis_results['comparative']['baseline'].get('avg', 0), 1),
                "baseline_stddev": round(analysis_results['comparative']['baseline'].get('stddev', 0), 1),
                "anomaly_avg": round(analysis_results['comparative']['anomaly'].get('avg', 0), 1),
                "anomaly_max": int(analysis_results['comparative']['anomaly'].get('max', 0)),
                "deviation_pct": round(analysis_results['comparative']['deviation_pct'], 1)
            },
            "execution_metrics": analysis_results['execution_metrics'],
            # NEW: Add Claude's LLM interpretation
            "llm_interpretation": {
                "risk_level": claude_analysis.get('risk_level', 'UNKNOWN'),
                "confidence": claude_analysis.get('confidence', 0),
                "pattern_detected": claude_analysis.get('pattern_detected', 'unknown'),
                "key_insights": claude_analysis.get('key_insights', []),
                "recommended_actions": claude_analysis.get('recommended_actions', []),
                "mongodb_showcase": claude_analysis.get('mongodb_showcase', '')
            }
        }
        
        # ===== Step 1.5: Create New Alert (No Deduplication) =====
        logger.info(f"\n🚨 [ALERT CREATION] Creating new alert - NO DEDUPLICATION! VERSION 2")
        logger.info(f"   📋 About to call create_scenario_alert for scenario: {scenario_id}")
        
        # Always create new alert with unique ID (no deduplication)
        # This allows multiple alerts for the same scenario
        alert_id = await create_scenario_alert(db, scenario_id, metadata, mongodb_analysis_for_alert)
        alert_created = True
        
        logger.info(f"   ✅ New alert created with ID: {alert_id}")
        logger.info(f"   ✅ alert_created flag set to: {alert_created}")
        
        # ===== Final Summary =====
        overall_elapsed = (time.time() - overall_start) * 1000
        mongodb_time = analysis_results['execution_metrics']['mongodb_total_ms']
        
        # Extract statistics for response building
        overall = analysis_results['statistics']['overall']
        violations = analysis_results['statistics']['violations']
        rolling_result = analysis_results['rolling_windows']['data']
        trend = analysis_results['trend']
        comparative = analysis_results['comparative']
        
        logger.info(f"\n" + "=" * 80)
        logger.info(f"📋 [SUMMARY] Analysis Complete")
        logger.info(f"=" * 80)
        logger.info(f"   ⏱️  Total Time: {overall_elapsed:.0f}ms")
        logger.info(f"   🗄️  MongoDB Queries: {mongodb_time:.0f}ms (4 aggregations)")
        logger.info(f"   🤖 Claude Analysis: {claude_elapsed:.0f}ms")
        logger.info(f"   📊 Data Points Analyzed: {overall.get('readings_count', 0)}")
        logger.info(f"   🎯 Risk: {claude_analysis.get('risk_level', 'UNKNOWN')} ({claude_analysis.get('confidence', 0):.0%} confidence)")
        if alert_created:
            logger.info(f"   🚨 Alert Created: {alert_id}")
        else:
            logger.info(f"   ℹ️  Using Existing Alert: {alert_id}")
        logger.info("=" * 80 + "\n")
        
        # Build comprehensive response
        return {
            "scenario_id": scenario_id,
            "alert_info": {
                "alert_id": alert_id,
                "alert_created": alert_created,
                "message": "New alert created" if alert_created else "Using existing alert (deduplication)"
            },
            "scenario_metadata": {
                "title": metadata['title'],
                "description": metadata['description'],
                "equipment_id": metadata['equipment_id'],
                "duration_minutes": metadata['duration_minutes'],
                "data_points": metadata['data_points'],
                "pattern_type": metadata['pattern_type'],
                "root_cause": metadata['root_cause']
            },
            "execution_metrics": {
                "total_time_ms": round(overall_elapsed, 0),
                "mongodb_time_ms": round(mongodb_time, 0),
                "claude_time_ms": round(claude_elapsed, 0),
                "queries_executed": 4
            },
            "mongodb_analysis": {
                "statistical_summary": {
                    "avg_particle_count": round(overall.get('avg_particles', 0), 1),
                    "min": int(overall.get('min_particles', 0)),
                    "max": int(overall.get('max_particles', 0)),
                    "stddev": round(overall.get('stddev_particles', 0), 1),
                    "threshold_violations": violations.get('violation_count', 0),
                    "readings_analyzed": overall.get('readings_count', 0)
                },
                "trend_analysis": {
                    "direction": trend['direction'],
                    "change_percentage": round(trend['change_pct'], 1),
                    "first_period_avg": round(trend['first_avg'], 1),
                    "last_period_avg": round(trend['last_avg'], 1)
                },
                "comparative_windows": {
                    "baseline": {
                        "avg": round(comparative['baseline'].get('avg', 0), 1),
                        "stddev": round(comparative['baseline'].get('stddev', 0), 1)
                    },
                    "anomaly": {
                        "avg": round(comparative['anomaly'].get('avg', 0), 1),
                        "stddev": round(comparative['anomaly'].get('stddev', 0), 1),
                        "max": int(comparative['anomaly'].get('max', 0)),
                        "deviation_from_baseline_pct": round(comparative['deviation_pct'], 1)
                    },
                    "recovery": {
                        "avg": round(comparative['recovery'].get('avg', 0), 1)
                    }
                },
                "rolling_windows": {
                    "data_points": len(rolling_result),
                    "sample_data": rolling_result[:10] if rolling_result else []  # First 10 points for visualization
                }
            },
            "agent_analysis": claude_analysis,
            "mongodb_showcase": {
                "features_demonstrated": [
                    "$facet - Parallel aggregation pipelines for multi-dimensional analysis",
                    "$setWindowFields - Rolling window calculations without client-side processing",
                    "$group with complex expressions - Trend detection and statistical analysis",
                    "Time-based $match - Efficient indexed queries on time series data"
                ],
                "performance_highlight": f"Analyzed {overall.get('readings_count', 0)} time series data points with 4 complex aggregations in {mongodb_time:.0f}ms",
                "total_analysis_time": f"{overall_elapsed:.0f}ms (target: <5000ms) ✅"
            }
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse Claude response: {e}")
        logger.error(f"   Raw response: {claude_response if 'claude_response' in locals() else 'N/A'}")
        return {"error": "Failed to parse Claude response", "details": str(e)}
    
    except Exception as e:
        logger.error(f"❌ Scenario analysis error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": "Scenario analysis failed", "details": str(e)}
