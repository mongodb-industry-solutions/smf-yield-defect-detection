"""
Supervisor Agent Prompts
Prompt templates for the supervisor agent to generate comprehensive quality control reports
"""

def build_supervisor_synthesis_prompt(
    alert_context: dict,
    monitoring_analysis: dict,
    investigation_analysis: dict,
    rca_analysis: dict,
    troubleshooting_guides: dict
) -> str:
    """
    Build Supervisor agent prompt to synthesize comprehensive quality control report

    The Supervisor agent aggregates insights from ALL previous agents:
    1. Monitoring insights (pattern detection, risk level)
    2. Investigation findings (problematic materials, evidence quality)
    3. RCA analysis (validated root causes, recommendations)
    4. Troubleshooting guides (actionable solutions from knowledge base)

    Then uses LLM to create a comprehensive quality control report with:
    - Executive summary
    - Cross-agent synthesis
    - Quality control metrics
    - Prioritized recommendations
    - Risk assessment
    - Lessons learned

    Args:
        alert_context: Alert metadata (equipment_id, severity, timestamp)
        monitoring_analysis: Output from monitoring agent
        investigation_analysis: Output from investigation agent
        rca_analysis: Output from RCA agent
        troubleshooting_guides: Tool output from troubleshooting guide search

    Returns:
        Prompt string for Claude to generate comprehensive QC report
    """

    # Extract alert context
    equipment_id = alert_context.get('equipment_id', 'UNKNOWN')
    severity = alert_context.get('severity', 'UNKNOWN')
    alert_id = alert_context.get('alert_id', 'UNKNOWN')
    timestamp = alert_context.get('timestamp', 'UNKNOWN')

    # ========== MONITORING AGENT INSIGHTS ==========
    monitoring_llm = monitoring_analysis.get('llm_interpretation', {})
    monitoring_risk_level = monitoring_llm.get('risk_level', 'UNKNOWN')
    monitoring_pattern = monitoring_llm.get('pattern_detected', 'unknown')
    monitoring_insights = monitoring_llm.get('key_insights', [])
    monitoring_confidence = monitoring_llm.get('confidence', 0)

    monitoring_summary = f"""Risk Level: {monitoring_risk_level} (Confidence: {monitoring_confidence:.2f})
Pattern Detected: {monitoring_pattern}
Key Insights:
{chr(10).join([f'  - {insight}' for insight in monitoring_insights])}"""

    # ========== INVESTIGATION AGENT FINDINGS ==========
    investigation_llm = investigation_analysis.get('llm_synthesis', {})
    investigation_findings = investigation_llm.get('key_findings', [])
    problematic_materials = investigation_llm.get('problematic_materials', [])
    evidence_quality = investigation_llm.get('evidence_quality', 'unknown')

    materials_summary = "None identified"
    if problematic_materials:
        materials_details = []
        for material in problematic_materials[:5]:  # Top 5
            mat_type = material.get('type', 'unknown')
            mat_id = material.get('id', 'unknown')
            mat_severity = material.get('severity', 'unknown')
            mat_issue = material.get('issue', 'No description')
            materials_details.append(
                f"  - {mat_type.upper()}: {mat_id} (Severity: {mat_severity})\n    Issue: {mat_issue}"
            )
        materials_summary = "\n".join(materials_details)

    investigation_summary = f"""Evidence Quality: {evidence_quality}
Key Findings:
{chr(10).join([f'  - {finding}' for finding in investigation_findings])}

Problematic Materials:
{materials_summary}"""

    # ========== RCA AGENT ANALYSIS ==========
    rca_llm = rca_analysis.get('llm_synthesis', {})
    validated_root_causes = rca_llm.get('validated_root_causes', [])
    rca_confidence = rca_llm.get('overall_confidence', 0)
    rca_reasoning = rca_llm.get('reasoning', 'N/A')
    rca_recommendations = rca_llm.get('recommendations', [])

    root_causes_summary = "None identified"
    if validated_root_causes:
        rc_details = []
        for rc in validated_root_causes:
            rc_cause = rc.get('root_cause', 'Unknown')
            rc_confidence = rc.get('confidence', 'unknown')
            rc_evidence = rc.get('supporting_evidence', [])
            rc_details.append(
                f"  - {rc_cause} (Confidence: {rc_confidence})\n"
                f"    Evidence: {', '.join(rc_evidence[:2])}"
            )
        root_causes_summary = "\n".join(rc_details)

    rca_recommendations_summary = "None provided"
    if rca_recommendations:
        rec_details = []
        for rec in rca_recommendations[:5]:  # Top 5
            rec_action = rec.get('action', 'Unknown')
            rec_priority = rec.get('priority', 'unknown')
            rec_timeline = rec.get('timeline', 'unknown')
            rec_details.append(
                f"  - [{rec_priority.upper()}] {rec_action} (Timeline: {rec_timeline})"
            )
        rca_recommendations_summary = "\n".join(rec_details)

    rca_summary = f"""Overall Confidence: {rca_confidence:.2f}

Validated Root Causes:
{root_causes_summary}

RCA Reasoning:
{rca_reasoning}

RCA Recommendations:
{rca_recommendations_summary}"""

    # ========== TROUBLESHOOTING GUIDES ==========
    troubleshooting_docs = troubleshooting_guides.get('knowledge_documents', [])
    troubleshooting_summary = "No troubleshooting guides found"

    if troubleshooting_docs:
        guide_details = [
            f"  Found {len(troubleshooting_docs)} relevant troubleshooting guides:",
            ""
        ]
        for guide in troubleshooting_docs[:3]:  # Top 3 most relevant
            guide_title = guide.get('title', 'Untitled')
            guide_problem = guide.get('problem_description', 'N/A')
            guide_score = guide.get('score', 0)
            guide_effectiveness = guide.get('effectiveness_score', 0)
            solutions = guide.get('solutions', [])

            guide_details.append(
                f"  📘 {guide_title} (Relevance: {guide_score:.2f}, Effectiveness: {guide_effectiveness:.2f})\n"
                f"     Problem: {guide_problem[:150]}...\n"
                f"     Solutions: {len(solutions)} actionable steps identified"
            )
        troubleshooting_summary = "\n".join(guide_details)

    # Build the comprehensive prompt
    prompt = f"""You are a Supervisor Agent for semiconductor manufacturing quality control. You synthesize insights from multiple AI agents and knowledge sources to create a comprehensive quality control report with actionable recommendations for yield improvement.

ALERT CONTEXT:
- Alert ID: {alert_id}
- Equipment: {equipment_id}
- Severity: {severity}
- Timestamp: {timestamp}

================================================================================
MONITORING AGENT INSIGHTS:
================================================================================
{monitoring_summary}

================================================================================
INVESTIGATION AGENT FINDINGS:
================================================================================
{investigation_summary}

================================================================================
RCA AGENT ANALYSIS:
================================================================================
{rca_summary}

================================================================================
TROUBLESHOOTING GUIDES (Knowledge Base):
================================================================================
{troubleshooting_summary}

================================================================================
YOUR TASK:
================================================================================
Synthesize ALL agent insights and knowledge sources to create a comprehensive quality control report. Your report will be used by process engineers, quality control managers, and operations leadership to:
1. Understand the full scope of the defect issue
2. Implement corrective actions
3. Prevent recurrence
4. Improve overall yield

Respond with JSON only:

{{
  "executive_summary": "2-3 paragraph high-level overview of the issue, impact, root causes, and resolution path. Written for management audience.",

  "cross_agent_synthesis": {{
    "monitoring_insights": "Key takeaways from monitoring agent pattern detection",
    "investigation_insights": "Key takeaways from investigation agent evidence gathering",
    "rca_insights": "Key takeaways from RCA agent root cause validation",
    "knowledge_base_insights": "Key takeaways from troubleshooting guides and historical knowledge"
  }},

  "quality_control_report": {{
    "affected_products": [
      {{
        "product_type": "wafer|lot|batch",
        "identifier": "Wafer ID or Lot number",
        "estimated_impact": "Description of impact"
      }}
    ],
    "yield_impact": {{
      "estimated_wafers_affected": 150,
      "estimated_yield_loss_percent": 12.5,
      "estimated_cost_impact_usd": 500000,
      "confidence_level": "high|medium|low"
    }},
    "quality_metrics": {{
      "defect_density": "high|medium|low",
      "process_capability": "within_spec|borderline|out_of_spec",
      "containment_status": "contained|spreading|unknown",
      "time_to_detection": "Description of how quickly the issue was detected"
    }}
  }},

  "recommendations": [
    {{
      "category": "immediate_containment|corrective_action|preventive_measure|process_improvement",
      "priority": "critical|high|medium|low",
      "action": "Specific, actionable description of what to do",
      "rationale": "Why this action is needed (link to root causes/evidence)",
      "expected_impact": "Quantified or described impact on yield/quality",
      "timeline": "immediate|1-3 days|1-2 weeks|1+ month",
      "responsible_team": "Process Engineering|Maintenance|Quality|Manufacturing|...",
      "success_metrics": ["Metric 1 to track", "Metric 2 to track"],
      "dependencies": ["Optional: prerequisite actions or resources needed"]
    }}
  ],

  "risk_assessment": {{
    "recurrence_risk": "high|medium|low",
    "recurrence_risk_rationale": "Explanation of why recurrence is likely/unlikely",
    "escalation_needed": true|false,
    "escalation_rationale": "When and why to escalate to senior leadership",
    "monitoring_plan": "Describe ongoing monitoring strategy to prevent recurrence"
  }},

  "lessons_learned": [
    "Lesson 1: What went wrong and why (process breakdown, design flaw, etc.)",
    "Lesson 2: What worked well in detection and response (early detection, fast root cause, etc.)",
    "Lesson 3: What could be improved in future incidents"
  ],

  "overall_confidence": 0.92
}}

IMPORTANT GUIDELINES:
- Executive summary should be clear, concise, and suitable for non-technical leadership
- Cross-reference and validate findings across all agents - flag any contradictions
- Prioritize recommendations by impact and urgency (critical actions first)
- Quantify yield impact where possible using data from investigation agent
- Link each recommendation to specific root causes from RCA agent
- Include specific solutions from troubleshooting guides in your recommendations
- Success metrics should be measurable and time-bound
- If agent confidence scores are low (<0.5), acknowledge uncertainty in your report
- Focus on actionable next steps - this report drives operational decisions

Respond ONLY with valid JSON, no additional text."""

    return prompt
