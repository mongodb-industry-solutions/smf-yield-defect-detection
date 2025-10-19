"""
Multi-Agent Tools Module

Reusable tool functions for agent workflows.
Each module contains pure, stateless functions focused on specific domains.
"""

from multi_agent.tools.mongodb_tools import (
    get_multifacet_statistics,
    get_rolling_window_analysis,
    detect_trend,
    get_comparative_windows
)

from multi_agent.tools.alert_tools import (
    check_existing_scenario_alert,
    create_scenario_alert
)

from multi_agent.tools.scenario_tools import (
    load_scenario_metadata,
    perform_comprehensive_analysis
)

__all__ = [
    # MongoDB tools
    'get_multifacet_statistics',
    'get_rolling_window_analysis',
    'detect_trend',
    'get_comparative_windows',
    # Alert tools
    'check_existing_scenario_alert',
    'create_scenario_alert',
    # Scenario tools
    'load_scenario_metadata',
    'perform_comprehensive_analysis',
]

