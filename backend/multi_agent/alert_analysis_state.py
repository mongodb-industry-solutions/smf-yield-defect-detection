"""
Alert Analysis State Definition
Defines the shared state structure for multi-agent workflow
"""
from typing import TypedDict, Optional, Dict, Any, List, Annotated
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AlertAnalysisState(TypedDict):
    """
    Shared state for alert analysis multi-agent workflow

    This state is passed between supervisor and worker agents:
    - Monitoring Agent: filters false positives
    - Investigation Agent: correlates sensor data with defects
    - RCA Agent: generates root cause analysis
    """

    # === Input Data (from alert trigger) ===
    alert_id: str
    equipment_id: str
    excursion_type: str
    severity: str
    metrics: Dict[str, float]
    metadata: Dict[str, Any]

    # === Workflow Control ===
    workflow_stage: str  # "monitoring" | "investigation" | "rca" | "complete"

    # === Worker Agent Outputs ===
    monitoring_decision: Optional[Dict[str, Any]]  # {create_alert: bool, confidence: float, reasoning: str, statistical_context: dict}
    correlation_results: Optional[Dict[str, Any]]  # Full correlation engine output
    investigation_summary: Optional[str]  # Investigation agent summary
    key_findings: Optional[List[str]]  # Key findings from investigation
    rca_patterns: Optional[Dict[str, Any]]  # RCA generator output
    rca_validation: Optional[str]  # RCA validation summary
    validated_causes: Optional[List[str]]  # Validated root causes

    # === Supervisor Outputs ===
    supervisor_synthesis: Optional[str]  # Comprehensive QC report
    risk_level: Optional[str]  # Overall risk level assessment
    overall_confidence: Optional[float]  # Overall confidence score (0-1)
    action_items: List[Dict[str, str]]  # [{action: str, priority: str, agent: str}]

    # === LangGraph Built-in ===
    messages: Annotated[list, "Message history for supervisor and workers"]


def create_initial_state(
    alert_id: str,
    equipment_id: str,
    excursion_type: str,
    severity: str,
    metrics: Dict[str, float],
    metadata: Dict[str, Any]
) -> AlertAnalysisState:
    """
    Create initial state from sensor alert trigger

    Args:
        alert_id: Unique alert identifier
        equipment_id: Equipment that triggered alert
        excursion_type: Type of excursion (particle_excursion, rf_power_drift, etc.)
        severity: Alert severity (critical, high, medium, low)
        metrics: Sensor metrics at time of alert
        metadata: Additional context (timestamp, slurry_batch, recipe, etc.)

    Returns:
        Initial AlertAnalysisState ready for workflow
    """
    logger.info(f"🔧 Creating initial state for alert {alert_id}")
    logger.info(f"   Equipment: {equipment_id}, Type: {excursion_type}, Severity: {severity}")
    logger.debug(f"   Metrics: {metrics}")
    logger.debug(f"   Metadata: {metadata}")

    initial_state: AlertAnalysisState = {
        # Input data
        "alert_id": alert_id,
        "equipment_id": equipment_id,
        "excursion_type": excursion_type,
        "severity": severity,
        "metrics": metrics,
        "metadata": metadata,

        # Workflow control
        "workflow_stage": "monitoring",

        # Worker outputs (initialized as None)
        "monitoring_decision": None,
        "correlation_results": None,
        "investigation_summary": None,
        "key_findings": None,
        "rca_patterns": None,
        "rca_validation": None,
        "validated_causes": None,

        # Supervisor outputs
        "supervisor_synthesis": None,
        "risk_level": None,
        "overall_confidence": None,
        "action_items": [],

        # Message history
        "messages": []
    }

    logger.info(f"✅ Initial state created, starting at workflow_stage: {initial_state['workflow_stage']}")

    return initial_state


def log_state_transition(state: AlertAnalysisState, from_stage: str, to_stage: str):
    """Log state transitions for debugging"""
    logger.info(f"🔄 State transition: {from_stage} → {to_stage}")
    logger.debug(f"   Alert: {state['alert_id']}, Equipment: {state['equipment_id']}")

    # Log agent outputs if available
    if state.get('monitoring_decision'):
        decision = state['monitoring_decision']
        logger.info(f"   📊 Monitoring Decision: create_alert={decision.get('create_alert')}, confidence={decision.get('confidence')}")

    if state.get('correlation_results'):
        logger.info(f"   🔗 Correlation Results: Available")

    if state.get('rca_patterns'):
        logger.info(f"   🔍 RCA Patterns: Available")


def get_state_summary(state: AlertAnalysisState) -> str:
    """Get a human-readable summary of current state for logging"""
    summary_parts = [
        f"Alert: {state['alert_id']}",
        f"Stage: {state['workflow_stage']}",
        f"Equipment: {state['equipment_id']}",
        f"Type: {state['excursion_type']}"
    ]

    if state.get('monitoring_decision'):
        decision = state['monitoring_decision']
        summary_parts.append(f"Monitoring: {'✅ Create Alert' if decision.get('create_alert') else '❌ Filtered'}")

    if state.get('correlation_results'):
        summary_parts.append("Correlation: ✅")

    if state.get('rca_patterns'):
        summary_parts.append("RCA: ✅")

    return " | ".join(summary_parts)
