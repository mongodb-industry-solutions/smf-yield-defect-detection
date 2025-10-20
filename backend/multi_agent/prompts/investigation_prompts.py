"""
Investigation Agent Prompts
Prompt templates for the investigation agent to synthesize evidence from MongoDB queries
"""

def build_investigation_synthesis_prompt(
    monitoring_analysis: dict,
    process_context_evidence: dict,
    wafer_defects_evidence: dict = None
) -> str:
    """
    Build investigation agent prompt to synthesize evidence from all MongoDB tools

    The investigation agent calls ALL tools sequentially, then uses LLM to:
    1. Identify key findings from the evidence
    2. Highlight problematic items discovered
    3. Connect evidence to monitoring agent's insights
    4. Provide structured summary for downstream agents (RCA agent)

    Args:
        monitoring_analysis: Output from monitoring agent
        process_context_evidence: Results from query_process_context()
        wafer_defects_evidence: Results from query_wafer_defects() (optional)

    Returns:
        Prompt string for Claude to synthesize evidence
    """

    # Extract monitoring analysis fields
    risk_level = monitoring_analysis.get('risk_level', 'UNKNOWN')
    pattern = monitoring_analysis.get('pattern_detected', 'unknown')
    equipment_id = monitoring_analysis.get('equipment_id', 'UNKNOWN')
    key_insights = monitoring_analysis.get('key_insights', [])

    # Extract process context findings
    problematic_items = process_context_evidence.get('problematic_items', 0)
    slurry_batches = process_context_evidence.get('slurry_batches', [])
    recipes = process_context_evidence.get('recipes', [])

    # Build slurry batch summary
    slurry_summary = "None found"
    if slurry_batches:
        slurry_details = []
        for batch in slurry_batches:
            batch_id = batch.get('context_id', 'Unknown')
            is_problematic = batch.get('is_problematic', False)
            issues = batch.get('known_issues', [])
            status = "🚨 PROBLEMATIC" if is_problematic else "✅ Normal"
            slurry_details.append(f"  - {batch_id}: {status}")
            if issues:
                for issue in issues:
                    issue_desc = issue.get('description', 'Unknown issue') if isinstance(issue, dict) else str(issue)
                    slurry_details.append(f"    Issue: {issue_desc}")
        slurry_summary = "\n".join(slurry_details)

    # Build recipe summary
    recipe_summary = "None found"
    if recipes:
        recipe_details = []
        for recipe in recipes:
            recipe_id = recipe.get('context_id', 'Unknown')
            is_problematic = recipe.get('is_problematic', False)
            status = "🚨 PROBLEMATIC" if is_problematic else "✅ Normal"
            recipe_details.append(f"  - {recipe_id}: {status}")
        recipe_summary = "\n".join(recipe_details)

    # Build wafer defects summary (vector search results)
    wafer_summary = "Not queried"
    if wafer_defects_evidence:
        summary = wafer_defects_evidence.get('summary', {})
        wafers = wafer_defects_evidence.get('wafer_defects', [])

        if wafers:
            total = summary.get('total_wafers_found', 0)
            avg_yield = summary.get('avg_yield', 0)
            patterns = summary.get('common_patterns', [])

            wafer_details = [
                f"  Total Similar Wafers Found: {total}",
                f"  Average Yield: {avg_yield:.1f}%",
                f"  Common Defect Patterns: {', '.join(patterns)}",
                f"",
                f"  Top Similar Wafers (by vector similarity):"
            ]

            for wafer in wafers[:3]:  # Show top 3
                wafer_id = wafer.get('wafer_id', 'Unknown')
                wafer_yield = wafer.get('yield', 0)
                pattern = wafer.get('pattern', 'unknown')
                similarity = wafer.get('similarity_score', 0)
                wafer_details.append(
                    f"    - {wafer_id}: {wafer_yield:.1f}% yield, '{pattern}' pattern, {similarity:.2f} similarity"
                )

            wafer_summary = "\n".join(wafer_details)
        else:
            wafer_summary = "No similar wafers found in vector search"

    prompt = f"""You are an investigation agent for semiconductor manufacturing. You have gathered evidence from MongoDB about a detected anomaly.

MONITORING AGENT ANALYSIS:
- Risk Level: {risk_level}
- Pattern Detected: {pattern}
- Equipment: {equipment_id}
- Key Insights from Monitoring Agent:
{chr(10).join([f'  - {insight}' for insight in key_insights])}

EVIDENCE GATHERED FROM MONGODB:

1. Process Context (Slurry Batches):
{slurry_summary}

2. Process Context (Recipes):
{recipe_summary}

3. Wafer Defects (Vector Search - Voyage Multimodal-3):
{wafer_summary}

4. Problematic Items Found: {problematic_items}

YOUR TASK:
Synthesize the evidence and provide a structured summary that:
1. Identifies the most significant findings from ALL evidence sources
2. Analyzes vector search results (wafer yield patterns indicate severity)
3. Connects evidence to monitoring agent's insights
4. Highlights problematic materials/recipes if found
5. Assesses evidence quality (strong/moderate/weak)

Respond with JSON only:

{{
  "key_findings": [
    "Finding 1 with specific details",
    "Finding 2 with specific details"
  ],
  "problematic_materials": [
    {{"type": "slurry_batch", "id": "SB_2025_021", "severity": "high", "issue": "Description"}}
  ],
  "evidence_quality": "strong|moderate|weak",
  "correlation_with_monitoring": "How evidence supports/contradicts monitoring insights",
  "recommended_next_steps": [
    "Action 1",
    "Action 2"
  ]
}}

IMPORTANT:
- Be specific with batch IDs and issue descriptions
- Focus on problematic items (they are the likely root causes)
- If no problematic items found, suggest alternative investigation paths
- Respond ONLY with valid JSON, no additional text"""

    return prompt
