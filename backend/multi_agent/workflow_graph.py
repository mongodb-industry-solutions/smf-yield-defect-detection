"""
LangGraph Workflow for Multi-Agent Alert Analysis

This module defines a LangGraph StateGraph that orchestrates the 4-agent pipeline:
1. Monitoring Agent - Pattern detection and false positive filtering
2. Investigation Agent - Evidence gathering and correlation analysis
3. RCA Agent - Root cause analysis with vector search
4. Supervisor Agent - Comprehensive QC report synthesis

The workflow uses conditional routing to skip investigation if monitoring filters the alert.
"""

import logging
import os
from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from motor.motor_asyncio import AsyncIOMotorClient
from multi_agent.alert_analysis_state import AlertAnalysisState
from multi_agent.workers import (
    monitoring_agent_tool,
    investigation_agent_tool,
    rca_agent_tool
)
from multi_agent.supervisor import supervisor_synthesis_agent

logger = logging.getLogger(__name__)


def should_continue_to_investigation(state: AlertAnalysisState) -> Literal["investigation", "END"]:
    """
    Conditional router after monitoring agent

    Only proceed to investigation if monitoring agent determines alert should be created.
    This implements the false positive filtering logic.

    Args:
        state: Current workflow state

    Returns:
        "investigation" if alert should be created, "END" otherwise
    """
    monitoring_decision = state.get("monitoring_decision")

    if not monitoring_decision:
        logger.warning("🔀 [ROUTER] No monitoring decision found, skipping to END")
        return "END"

    create_alert = monitoring_decision.get("create_alert", False)
    confidence = monitoring_decision.get("confidence", 0)

    if create_alert:
        logger.info(f"🔀 [ROUTER] Alert approved (confidence: {confidence:.0%}) → Proceeding to Investigation")
        return "investigation"
    else:
        logger.info(f"🔀 [ROUTER] Alert filtered (confidence: {confidence:.0%}) → Skipping to END")
        return "END"


async def wrapped_monitoring_agent(state: AlertAnalysisState) -> dict:
    """Wrapper for monitoring agent - reads monitoring_agent_analysis from alert and adds to state"""
    logger.info("🔵 [LANGGRAPH] Executing Monitoring Agent...")
    result = await monitoring_agent_tool(state)

    # CRITICAL: Read monitoring_agent_analysis from alert document and add to state
    # This allows downstream agents (investigation, RCA, supervisor) to access monitoring analysis
    alert_id = state.get("alert_id")
    if alert_id:
        try:
            client = AsyncIOMotorClient(os.getenv('MONGODB_URI'))
            db = client[os.getenv('MDB_DATABASE_NAME', 'smf-yield-defect')]

            alert = await db.alerts.find_one({"alert_id": alert_id})
            if alert and 'monitoring_agent_analysis' in alert:
                result['monitoring_agent_analysis'] = alert['monitoring_agent_analysis']
                logger.info(f"✅ [LANGGRAPH] Added monitoring_agent_analysis to state for downstream agents")

            client.close()
        except Exception as e:
            logger.error(f"❌ [LANGGRAPH] Failed to read monitoring analysis from alert: {e}")

    logger.info(f"🔵 [LANGGRAPH] Monitoring Agent complete, workflow_stage: {result.get('workflow_stage')}")
    return result


async def wrapped_investigation_agent(state: AlertAnalysisState) -> dict:
    """Wrapper for investigation agent with MongoDB persistence"""
    logger.info("🟠 [LANGGRAPH] Executing Investigation Agent...")

    import time
    agent_start = time.time()
    result = await investigation_agent_tool(state)
    agent_elapsed = (time.time() - agent_start) * 1000

    # Save investigation analysis to alert document in MongoDB
    alert_id = state["alert_id"]
    logger.info(f"💾 [LANGGRAPH] Saving investigation_agent_analysis to alert: {alert_id}")

    try:
        client = AsyncIOMotorClient(os.getenv('MONGODB_URI'))
        db = client[os.getenv('MDB_DATABASE_NAME', 'smf-yield-defect')]

        # Extract data from new investigation agent structure
        process_context_evidence = result.get("process_context_evidence", {})
        wafer_defects_evidence = result.get("wafer_defects_evidence", {})
        investigation_synthesis = result.get("investigation_synthesis", {})
        tool_times = result.get("tool_execution_times", {})

        # Build investigation_agent_analysis matching sequential workflow structure
        investigation_analysis = {
            "tool_outputs": {
                "process_context": {
                    "execution_time_ms": tool_times.get("process_context_ms", 0),
                    "slurry_batches_found": len(process_context_evidence.get('slurry_batches', [])),
                    "recipes_found": len(process_context_evidence.get('recipes', [])),
                    "reticles_found": len(process_context_evidence.get('reticles', [])),
                    "problematic_items": process_context_evidence.get('problematic_items', 0),
                    "raw_data": {
                        "slurry_batches": process_context_evidence.get('slurry_batches', []),
                        "recipes": process_context_evidence.get('recipes', []),
                        "reticles": process_context_evidence.get('reticles', [])
                    }
                },
                "wafer_defects": {
                    "execution_time_ms": tool_times.get("wafer_defects_ms", 0),
                    "wafers_found": wafer_defects_evidence.get('summary', {}).get('total_wafers_found', 0),
                    "avg_yield": wafer_defects_evidence.get('summary', {}).get('avg_yield', 0),
                    "yield_loss": wafer_defects_evidence.get('summary', {}).get('yield_impact', {}).get('yield_loss', 0),
                    "search_type": "vector_similarity",
                    "raw_data": {
                        "wafers": wafer_defects_evidence.get('wafer_defects', [])
                    }
                }
            },
            "llm_synthesis": investigation_synthesis,
            "execution_time_ms": tool_times.get("total_ms", round(agent_elapsed, 2))
        }

        await db.alerts.update_one(
            {"alert_id": alert_id},
            {"$set": {"investigation_agent_analysis": investigation_analysis}}
        )

        client.close()
        logger.info(f"✅ [LANGGRAPH] Investigation analysis saved to DB (matching sequential structure)")
        logger.info(f"   📊 Process context: {investigation_analysis['tool_outputs']['process_context']['problematic_items']} problematic items")
        logger.info(f"   📊 Wafer defects: {investigation_analysis['tool_outputs']['wafer_defects']['wafers_found']} wafers found")
        logger.info(f"   🎯 Evidence quality: {investigation_synthesis.get('evidence_quality', 'unknown')}")
    except Exception as e:
        logger.error(f"❌ [LANGGRAPH] Failed to save investigation analysis: {e}")

    logger.info(f"🟠 [LANGGRAPH] Investigation Agent complete, workflow_stage: {result.get('workflow_stage')}")
    return result


async def wrapped_rca_agent(state: AlertAnalysisState) -> dict:
    """Wrapper for RCA agent with MongoDB persistence - MATCHES SEQUENTIAL WORKFLOW"""
    logger.info("🟣 [LANGGRAPH] Executing RCA Agent...")

    result = await rca_agent_tool(state)

    # Save RCA analysis to alert document in MongoDB
    alert_id = state["alert_id"]
    logger.info(f"💾 [LANGGRAPH] Saving rca_agent_analysis to alert: {alert_id}")

    try:
        client = AsyncIOMotorClient(os.getenv('MONGODB_URI'))
        db = client[os.getenv('MDB_DATABASE_NAME', 'smf-yield-defect')]

        # Extract data from new RCA agent structure
        historical_knowledge_output = result.get("historical_knowledge_output", {})
        correlation_output = result.get("correlation_output", {})
        rca_synthesis = result.get("rca_synthesis", {})
        tool_execution_times = result.get("tool_execution_times", {})

        # Build rca_agent_analysis matching sequential workflow structure
        rca_analysis = {
            "tool_outputs": {
                "historical_knowledge": {
                    "execution_time_ms": historical_knowledge_output.get("execution_time_ms", 0),
                    "documents_found": historical_knowledge_output.get("documents_found", 0),
                    "search_parameters": historical_knowledge_output.get("search_parameters", {}),
                    "raw_data": historical_knowledge_output.get("raw_data", {})
                },
                "correlation_analysis": {
                    "execution_time_ms": correlation_output.get("execution_time_ms", 0),
                    "confidence_score": correlation_output.get("confidence_score", 0),
                    "raw_data": correlation_output.get("raw_data", {})
                }
            },
            "llm_synthesis": rca_synthesis,
            "execution_time_ms": tool_execution_times.get("total_ms", 0)
        }

        await db.alerts.update_one(
            {"alert_id": alert_id},
            {"$set": {"rca_agent_analysis": rca_analysis}}
        )

        client.close()
        logger.info(f"✅ [LANGGRAPH] RCA analysis saved to DB (matching sequential structure)")
        logger.info(f"   Documents found: {historical_knowledge_output.get('documents_found', 0)}")
        logger.info(f"   Root causes: {len(rca_synthesis.get('validated_root_causes', []))}")
        logger.info(f"   Confidence: {rca_synthesis.get('overall_confidence', 0):.2f}")
    except Exception as e:
        logger.error(f"❌ [LANGGRAPH] Failed to save RCA analysis: {e}")

    logger.info(f"🟣 [LANGGRAPH] RCA Agent complete, workflow_stage: {result.get('workflow_stage')}")
    return result


async def wrapped_supervisor_agent(state: AlertAnalysisState) -> dict:
    """
    Wrapper for supervisor agent to adapt interface

    The supervisor expects individual agent results, so we extract them from state
    """
    logger.info("🟢 [LANGGRAPH] Executing Supervisor Agent...")

    # Call NEW supervisor_agent_tool (matches sequential workflow with troubleshooting guides)
    from multi_agent.workers import supervisor_agent_tool
    result = await supervisor_agent_tool(state)

    # Save supervisor analysis to alert document in MongoDB
    alert_id = state["alert_id"]
    logger.info(f"💾 [LANGGRAPH] Saving supervisor_agent_analysis to alert: {alert_id}")

    try:
        client = AsyncIOMotorClient(os.getenv('MONGODB_URI'))
        db = client[os.getenv('MDB_DATABASE_NAME', 'smf-yield-defect')]

        # Extract data from new supervisor agent structure (matches sequential workflow)
        # These are prefixed with _ to avoid conflicting with state fields
        troubleshooting_guides_output = result.get("_troubleshooting_guides_output", {})
        supervisor_synthesis = result.get("_supervisor_synthesis", {})
        tool_execution_times = result.get("_tool_execution_times", {})

        # Build supervisor_agent_analysis matching sequential workflow structure
        supervisor_analysis = {
            "tool_outputs": {
                "troubleshooting_guides": {
                    "execution_time_ms": troubleshooting_guides_output.get("execution_time_ms", 0),
                    "documents_found": troubleshooting_guides_output.get("documents_found", 0),
                    "search_parameters": troubleshooting_guides_output.get("search_parameters", {}),
                    "raw_data": troubleshooting_guides_output.get("raw_data", {})
                }
            },
            "llm_synthesis": supervisor_synthesis,
            "execution_time_ms": tool_execution_times.get("total_ms", 0)
        }

        await db.alerts.update_one(
            {"alert_id": alert_id},
            {"$set": {"supervisor_agent_analysis": supervisor_analysis}}
        )

        client.close()
        logger.info(f"✅ [LANGGRAPH] Supervisor analysis saved to DB (matching sequential structure)")
    except Exception as e:
        logger.error(f"❌ [LANGGRAPH] Failed to save supervisor analysis: {e}")

    logger.info(f"🟢 [LANGGRAPH] Supervisor Agent complete, workflow_stage: {result.get('workflow_stage')}")
    return result


def _extract_recommendations_from_synthesis(synthesis_text: str) -> list:
    """Extract recommendations from supervisor synthesis text"""
    recommendations = []
    lines = synthesis_text.split('\n')
    in_recommendations = False

    for line in lines:
        stripped = line.strip()
        # Look for recommendations section
        if 'YIELD IMPROVEMENT' in stripped.upper() or 'ACTIONS' in stripped.upper():
            in_recommendations = True
            continue

        # Extract numbered or bulleted items
        if in_recommendations and stripped:
            if stripped[0] in ('1', '2', '3', '4', '5', '-', '•', '*'):
                rec = stripped.lstrip('12345-•*. ').strip()
                if rec and len(rec) > 10:
                    recommendations.append(rec)
                    if len(recommendations) >= 5:  # Limit to top 5
                        break

        # Stop at next section
        if in_recommendations and stripped and stripped[0].isupper() and ':' in stripped:
            if 'RISK' in stripped.upper() or 'QUALITY' in stripped.upper():
                break

    return recommendations


def create_alert_workflow(checkpointer=None, start_from="monitoring"):
    """
    Create LangGraph StateGraph for alert analysis workflow

    This function builds a graph with 4 agent nodes and conditional routing:
    - Monitoring Agent (entry point) → filters false positives
    - Investigation Agent → gathers evidence (conditional)
    - RCA Agent → root cause analysis
    - Supervisor Agent → comprehensive synthesis

    Args:
        checkpointer: Optional checkpointer for state persistence (default: None)
        start_from: Entry point node (default: "monitoring", can be "investigation" if alert exists)

    Returns:
        Compiled StateGraph ready for execution

    Example:
        >>> workflow = create_alert_workflow()
        >>> initial_state = create_initial_state(alert_id="alert_123", ...)
        >>> result = await workflow.ainvoke(initial_state)
    """
    logger.info(f"🔧 [LANGGRAPH] Creating alert analysis workflow (entry: {start_from})...")

    # Initialize StateGraph with AlertAnalysisState
    workflow = StateGraph(AlertAnalysisState)

    # Add agent nodes
    workflow.add_node("monitoring", wrapped_monitoring_agent)
    workflow.add_node("investigation", wrapped_investigation_agent)
    workflow.add_node("rca", wrapped_rca_agent)
    workflow.add_node("supervisor", wrapped_supervisor_agent)

    # Set entry point based on parameter
    workflow.set_entry_point(start_from)

    # Add conditional edge from monitoring (only if monitoring is in the workflow)
    if start_from == "monitoring":
        workflow.add_conditional_edges(
            "monitoring",
            should_continue_to_investigation,
            {
                "investigation": "investigation",
                "END": END
            }
        )

    # Add linear edges for the rest of the pipeline
    workflow.add_edge("investigation", "rca")
    workflow.add_edge("rca", "supervisor")
    workflow.add_edge("supervisor", END)

    # Compile the graph
    # Note: Checkpointer is optional. If None, workflow runs without state persistence.
    # To use checkpointing, pass a configured checkpointer with proper config (e.g., thread_id)
    if checkpointer:
        compiled_workflow = workflow.compile(checkpointer=checkpointer)
    else:
        compiled_workflow = workflow.compile()

    logger.info("✅ [LANGGRAPH] Alert analysis workflow created successfully")
    logger.info(f"   Entry: {start_from} → investigation → rca → supervisor")
    if start_from == "monitoring":
        logger.info("   Conditional routing: monitoring decision filters false positives")

    return compiled_workflow


def get_workflow_visualization():
    """
    Generate workflow visualization in multiple formats

    Returns:
        dict: Contains 'mermaid' and 'ascii' representations of the workflow graph

    Example:
        >>> viz = get_workflow_visualization()
        >>> print(viz['ascii'])
        >>> # Display Mermaid diagram in frontend
    """
    workflow = create_alert_workflow()
    graph = workflow.get_graph()

    return {
        "mermaid": graph.draw_mermaid(),
        "ascii": graph.draw_ascii(),
        "description": "4-agent alert analysis pipeline with conditional routing"
    }


if __name__ == "__main__":
    # Test workflow creation and visualization
    logger.info("Testing workflow creation...")
    workflow = create_alert_workflow()

    # Print ASCII visualization
    viz = get_workflow_visualization()
    print("\n" + "="*80)
    print("ALERT ANALYSIS WORKFLOW GRAPH")
    print("="*80)
    print(viz['ascii'])
    print("\n" + "="*80)
    print("Workflow created successfully!")
    print("="*80)
