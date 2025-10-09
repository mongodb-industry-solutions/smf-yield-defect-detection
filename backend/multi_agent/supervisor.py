"""
Supervisor Synthesis Agent
Aggregates outputs from all worker agents and generates comprehensive analysis
"""

import logging
from typing import Dict, Any
from multi_agent.simple_bedrock import call_claude

logger = logging.getLogger(__name__)


async def supervisor_synthesis_agent(
    monitoring_result: dict,
    investigation_result: dict,
    rca_result: dict,
    alert_context: dict
) -> dict:
    """
    Supervisor Synthesis Agent: Aggregates all agent outputs into comprehensive report

    Takes outputs from:
    - Monitoring Agent (pattern detection, confidence)
    - Investigation Agent (correlation analysis, key findings)
    - RCA Agent (root causes, recommendations)

    Generates:
    - Executive Summary
    - Prioritized Action Items for yield improvement
    - Risk Assessment
    - Quality Control Recommendations

    Args:
        monitoring_result: Output from monitoring agent
        investigation_result: Output from investigation agent
        rca_result: Output from RCA agent
        alert_context: Original alert context

    Returns:
        Comprehensive synthesis with action items and recommendations
    """

    equipment_id = alert_context.get('equipment_id', 'Unknown')
    excursion_type = alert_context.get('excursion_type', 'Unknown')

    logger.info(f"🎯 [SUPERVISOR] Starting synthesis for {equipment_id}")
    logger.info(f"   Aggregating outputs from 3 worker agents...")

    # Extract key information from each agent
    monitoring_confidence = monitoring_result.get('monitoring_decision', {}).get('confidence', 0)
    monitoring_pattern = monitoring_result.get('monitoring_decision', {}).get('pattern_detected', 'unknown')
    monitoring_reasoning = monitoring_result.get('monitoring_decision', {}).get('reasoning', 'N/A')

    logger.info(f"   📊 Monitoring Agent Output:")
    logger.info(f"      Pattern: {monitoring_pattern}, Confidence: {monitoring_confidence:.0%}")
    logger.info(f"      Reasoning: {monitoring_reasoning[:100]}...")

    key_findings = investigation_result.get('key_findings', [])
    correlation_confidence = investigation_result.get('correlation_results', {}).get('confidence_score', 0)
    affected_wafers = investigation_result.get('correlation_results', {}).get('affected_wafers', {}).get('total', 0)
    investigation_summary = investigation_result.get('investigation_summary', 'No investigation data')

    logger.info(f"   🔬 Investigation Agent Output:")
    logger.info(f"      Affected Wafers: {affected_wafers}, Correlation Confidence: {correlation_confidence:.0%}")
    logger.info(f"      Key Findings: {len(key_findings)}")
    for i, finding in enumerate(key_findings[:3], 1):
        logger.info(f"         {i}. {finding[:80]}...")

    validated_causes = rca_result.get('validated_causes', [])
    rca_validation = rca_result.get('rca_validation', 'No RCA validation')
    rca_recommendations = rca_result.get('rca_patterns', {}).get('recommendations', [])

    logger.info(f"   🔍 RCA Agent Output:")
    logger.info(f"      Validated Causes: {len(validated_causes)}")
    for i, cause in enumerate(validated_causes, 1):
        logger.info(f"         {i}. {cause}")
    logger.info(f"      Recommendations: {len(rca_recommendations)}")

    # Build comprehensive context for supervisor
    findings_text = "\n".join([f"  • {f}" for f in key_findings[:3]]) if key_findings else "  No findings"
    causes_text = "\n".join([f"  • {c}" for c in validated_causes[:3]]) if validated_causes else "  No causes identified"

    # Get top RCA recommendations with actions
    rca_actions_text = ""
    for i, rec in enumerate(rca_recommendations[:2], 1):
        title = rec.get('title', 'Unknown')
        actions = rec.get('actions', [])
        rca_actions_text += f"\n  {i}. {title}:\n"
        for action in actions[:2]:
            rca_actions_text += f"     - {action}\n"

    if not rca_actions_text:
        rca_actions_text = "  No specific actions recommended"

    # Supervisor LLM prompt - focuses on actionable insights
    prompt = f"""You are a semiconductor manufacturing quality control supervisor analyzing a comprehensive multi-agent analysis.

ALERT CONTEXT:
- Equipment: {equipment_id}
- Issue Type: {excursion_type}
- Affected Wafers: {affected_wafers}

MONITORING AGENT ANALYSIS:
- Pattern Detected: {monitoring_pattern}
- Confidence: {monitoring_confidence:.0%}
- Assessment: {monitoring_reasoning}

INVESTIGATION FINDINGS:
- Correlation Confidence: {correlation_confidence:.0%}
- Key Findings:
{findings_text}

ROOT CAUSE ANALYSIS:
- Validated Causes:
{causes_text}
- Recommended Actions:
{rca_actions_text}

YOUR TASK:
Generate a concise quality control report with:

1. EXECUTIVE SUMMARY (2-3 sentences):
   - What happened and severity
   - Business impact

2. YIELD IMPROVEMENT ACTIONS (Top 3, prioritized):
   - Immediate actions to prevent yield loss
   - Each action should be specific and measurable

3. RISK ASSESSMENT:
   - Risk Level: [Critical/High/Medium/Low]
   - Brief justification (1 sentence)

4. QUALITY CONTROL RECOMMENDATIONS (2-3 items):
   - Process improvements
   - Preventive measures

Keep it actionable and specific. Focus on what engineers should DO, not just what happened."""

    logger.info(f"   🤖 Calling Claude for supervisor synthesis...")
    logger.info(f"   📝 Prompt includes: {len(prompt)} characters")

    try:
        synthesis_response = call_claude(prompt, temperature=0.2, max_tokens=600)

        logger.info(f"   ✅ Supervisor synthesis complete")
        logger.info(f"   📋 Generated comprehensive quality control report ({len(synthesis_response)} chars)")

        # Log first few lines of synthesis
        synthesis_lines = synthesis_response.split('\n')
        logger.info(f"   📄 Synthesis Preview:")
        for i, line in enumerate(synthesis_lines[:5], 1):
            if line.strip():
                logger.info(f"      {line[:100]}...")

        # Extract risk level from response (simple heuristic)
        risk_level = "Medium"  # Default
        if "Critical" in synthesis_response or "critical" in synthesis_response:
            risk_level = "Critical"
        elif "High" in synthesis_response or "high" in synthesis_response:
            risk_level = "High"
        elif "Low" in synthesis_response or "low" in synthesis_response:
            risk_level = "Low"

        # Calculate overall confidence (weighted average)
        overall_confidence = (
            monitoring_confidence * 0.3 +  # Monitoring weight
            correlation_confidence * 0.4 +  # Investigation weight (highest)
            0.8 * 0.3  # RCA weight (assume 80% if causes found)
        ) if validated_causes else (monitoring_confidence * 0.5 + correlation_confidence * 0.5)

        logger.info(f"   🎯 Final Results:")
        logger.info(f"      Risk Level: {risk_level}")
        logger.info(f"      Overall Confidence: {overall_confidence:.0%}")
        logger.info(f"      Aggregated: {len(key_findings)} findings, {len(validated_causes)} causes, {len(rca_recommendations)} recommendations")

        return {
            "supervisor_synthesis": synthesis_response,
            "risk_level": risk_level,
            "overall_confidence": round(overall_confidence, 2),
            "agent_outputs": {
                "monitoring": {
                    "pattern": monitoring_pattern,
                    "confidence": monitoring_confidence,
                    "reasoning": monitoring_reasoning
                },
                "investigation": {
                    "affected_wafers": affected_wafers,
                    "correlation_confidence": correlation_confidence,
                    "key_findings_count": len(key_findings)
                },
                "rca": {
                    "validated_causes_count": len(validated_causes),
                    "recommendations_count": len(rca_recommendations)
                }
            },
            "workflow_stage": "complete"
        }

    except Exception as e:
        logger.error(f"   ❌ Supervisor synthesis error: {e}")
        return {
            "supervisor_synthesis": f"Synthesis failed: {str(e)}",
            "risk_level": "Unknown",
            "overall_confidence": 0.5,
            "agent_outputs": {},
            "workflow_stage": "complete"
        }
