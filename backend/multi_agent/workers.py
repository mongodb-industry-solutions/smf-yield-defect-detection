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
