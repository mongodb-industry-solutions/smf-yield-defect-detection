"""
RCA Agent Prompts
Prompt templates for the RCA agent to validate root causes using historical knowledge and correlation analysis
"""

def build_rca_synthesis_prompt(
    alert_context: dict,
    monitoring_analysis: dict,
    investigation_synthesis: dict,
    historical_knowledge: dict,
    correlation_analysis: dict
) -> str:
    """
    Build RCA agent prompt to synthesize root cause analysis

    The RCA agent combines:
    1. Monitoring insights (pattern, risk level)
    2. Investigation findings (problematic materials, evidence quality)
    3. Historical knowledge (similar RCA reports via RAG)
    4. Correlation analysis (temporal, batch, recipe, spatial, equipment)

    Then uses LLM to validate root causes with confidence scores and supporting evidence.

    Args:
        alert_context: Alert metadata (equipment_id, severity, timestamp)
        monitoring_analysis: Output from monitoring agent
        investigation_synthesis: LLM synthesis from investigation agent
        historical_knowledge: RAG search results from historical_knowledge collection
        correlation_analysis: Output from CorrelationEngine.analyze_alert()

    Returns:
        Prompt string for Claude to validate root causes
    """

    # Extract alert context
    equipment_id = alert_context.get('equipment_id', 'UNKNOWN')
    severity = alert_context.get('severity', 'UNKNOWN')
    alert_id = alert_context.get('alert_id', 'UNKNOWN')

    # Extract monitoring analysis
    risk_level = monitoring_analysis.get('risk_level', 'UNKNOWN')
    pattern = monitoring_analysis.get('pattern_detected', 'unknown')
    key_insights = monitoring_analysis.get('key_insights', [])

    # Extract investigation synthesis
    key_findings = investigation_synthesis.get('key_findings', [])
    problematic_materials = investigation_synthesis.get('problematic_materials', [])
    evidence_quality = investigation_synthesis.get('evidence_quality', 'unknown')
    correlation_with_monitoring = investigation_synthesis.get('correlation_with_monitoring', 'N/A')

    # Build problematic materials summary
    materials_summary = "None identified"
    if problematic_materials:
        materials_details = []
        for material in problematic_materials:
            mat_type = material.get('type', 'unknown')
            mat_id = material.get('id', 'unknown')
            mat_severity = material.get('severity', 'unknown')
            mat_issue = material.get('issue', 'No description')
            materials_details.append(
                f"  - {mat_type.upper()}: {mat_id} (Severity: {mat_severity})\n    Issue: {mat_issue}"
            )
        materials_summary = "\n".join(materials_details)

    # Extract historical knowledge summary
    knowledge_summary = "No similar RCA reports found"
    knowledge_docs = historical_knowledge.get('knowledge_documents', [])
    if knowledge_docs:
        knowledge_details = [
            f"  Found {len(knowledge_docs)} similar RCA reports/troubleshooting guides:",
            ""
        ]
        for doc in knowledge_docs[:3]:  # Top 3 most relevant
            doc_type = doc.get('document_type', 'unknown')
            doc_title = doc.get('title', 'Untitled')
            doc_root_cause = doc.get('root_cause', 'N/A')
            doc_relevance = doc.get('relevance_score', 0)
            knowledge_details.append(
                f"  📄 {doc_type.upper()}: {doc_title} (Relevance: {doc_relevance:.2f})\n"
                f"     Root Cause: {doc_root_cause}"
            )
        knowledge_summary = "\n".join(knowledge_details)

    # Extract correlation analysis summary
    correlation_summary = correlation_analysis.get('summary', {})
    correlation_confidence = correlation_summary.get('overall_confidence', 0)
    correlation_insights = correlation_summary.get('key_insights', [])

    # Extract correlation details
    temporal_corr = correlation_analysis.get('temporal_correlation', {})
    batch_corr = correlation_analysis.get('batch_correlation', {})
    recipe_corr = correlation_analysis.get('recipe_correlation', {})
    spatial_corr = correlation_analysis.get('spatial_correlation', {})
    equipment_corr = correlation_analysis.get('equipment_correlation', {})

    # Build correlation details summary
    correlation_details = []

    # Temporal correlation
    if temporal_corr.get('confidence_score', 0) > 0.5:
        affected_wafers = temporal_corr.get('affected_wafers', 0)
        time_window = temporal_corr.get('time_window_hours', 0)
        correlation_details.append(
            f"  🕐 Temporal: {affected_wafers} wafers affected in {time_window}h window (Confidence: {temporal_corr.get('confidence_score', 0):.2f})"
        )

    # Batch correlation
    if batch_corr.get('confidence_score', 0) > 0.5:
        suspect_batches = len(batch_corr.get('suspect_batches', []))
        correlation_details.append(
            f"  📦 Batch: {suspect_batches} suspect slurry batches identified (Confidence: {batch_corr.get('confidence_score', 0):.2f})"
        )
        for batch in batch_corr.get('suspect_batches', [])[:2]:  # Top 2
            batch_id = batch.get('batch_id', 'Unknown')
            affected_wafers = batch.get('affected_wafers', 0)
            correlation_details.append(
                f"     - {batch_id}: {affected_wafers} affected wafers"
            )

    # Recipe correlation
    if recipe_corr.get('confidence_score', 0) > 0.5:
        suspect_recipes = len(recipe_corr.get('suspect_recipes', []))
        correlation_details.append(
            f"  📋 Recipe: {suspect_recipes} suspect recipes identified (Confidence: {recipe_corr.get('confidence_score', 0):.2f})"
        )

    # Spatial correlation
    if spatial_corr.get('confidence_score', 0) > 0.5:
        pattern_type = spatial_corr.get('pattern_type', 'unknown')
        correlation_details.append(
            f"  🗺️  Spatial: {pattern_type} pattern detected (Confidence: {spatial_corr.get('confidence_score', 0):.2f})"
        )

    # Equipment correlation
    if equipment_corr.get('confidence_score', 0) > 0.5:
        correlation_details.append(
            f"  🔧 Equipment: Equipment-specific pattern detected (Confidence: {equipment_corr.get('confidence_score', 0):.2f})"
        )

    correlation_details_summary = "\n".join(correlation_details) if correlation_details else "  No strong correlations detected"

    # Build key insights summary
    insights_summary = "\n".join([f"  - {insight}" for insight in correlation_insights]) if correlation_insights else "  None"

    prompt = f"""You are a Root Cause Analysis (RCA) agent for semiconductor manufacturing. You have comprehensive data from multiple sources to validate root causes.

ALERT CONTEXT:
- Alert ID: {alert_id}
- Equipment: {equipment_id}
- Severity: {severity}

MONITORING AGENT INSIGHTS:
- Risk Level: {risk_level}
- Pattern Detected: {pattern}
- Key Insights:
{chr(10).join([f'  - {insight}' for insight in key_insights])}

INVESTIGATION AGENT FINDINGS:
- Evidence Quality: {evidence_quality}
- Key Findings:
{chr(10).join([f'  - {finding}' for finding in key_findings])}
- Correlation with Monitoring: {correlation_with_monitoring}

PROBLEMATIC MATERIALS IDENTIFIED:
{materials_summary}

HISTORICAL KNOWLEDGE (RAG Search - Similar RCA Reports):
{knowledge_summary}

CORRELATION ANALYSIS:
- Overall Confidence: {correlation_confidence:.2f}

Correlation Details:
{correlation_details_summary}

Key Insights from Correlation Engine:
{insights_summary}

YOUR TASK:
Synthesize all evidence sources to validate the root cause(s) of this manufacturing defect. Provide:

1. **Validated Root Causes**: Rank root causes by confidence (high/medium/low)
2. **Supporting Evidence**: Link each root cause to specific evidence from monitoring, investigation, historical knowledge, and correlation analysis
3. **Confidence Reasoning**: Explain why you assigned each confidence level
4. **Recommended Actions**: Prioritized list of corrective/preventive actions

Respond with JSON only:

{{
  "validated_root_causes": [
    {{
      "root_cause": "Specific root cause description",
      "confidence": "high|medium|low",
      "supporting_evidence": [
        "Evidence 1 from monitoring/investigation/correlation",
        "Evidence 2 from historical knowledge"
      ],
      "affected_materials": [
        {{"type": "slurry_batch", "id": "SB_2025_021"}}
      ]
    }}
  ],
  "overall_confidence": 0.85,
  "reasoning": "Detailed explanation of how you arrived at these conclusions, referencing specific evidence",
  "historical_precedent": "Summary of similar cases from historical knowledge",
  "recommendations": [
    {{
      "priority": "high|medium|low",
      "action": "Specific action description",
      "expected_impact": "Impact description",
      "timeline": "immediate|short-term|long-term"
    }}
  ],
  "false_positives_ruled_out": ["Reason 1", "Reason 2"]
}}

IMPORTANT:
- Cross-reference evidence across all sources (monitoring, investigation, historical, correlation)
- If correlation confidence is high (>0.7), prioritize correlation insights
- If problematic materials are identified with strong evidence, they are likely root causes
- Historical knowledge provides validation - if similar RCA reports exist, reference them
- Respond ONLY with valid JSON, no additional text"""

    return prompt
