"""
Centralized Threshold Configuration for SMF Yield Defect Detection

This module provides a single source of truth for all alert thresholds across
demo mode, monitoring service, and alert manager. Includes feature flag support
for gradual rollout of new threshold values.

Feature Flag: USE_CENTRALIZED_THRESHOLDS (environment variable)
- "true" or "1": Use new centralized thresholds
- "false" or "0" or unset: Use legacy thresholds for backward compatibility
"""

import os
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# NEW CENTRALIZED THRESHOLDS (Business-aligned values)
# ============================================================================

ALERT_THRESHOLDS = {
    "particle_count": {
        "critical": 2000,  # Aligned with business rules
        "high": 1500,
        "medium": 1000
    },
    "rf_power_drift": {
        # Equipment-specific baselines and drift thresholds
        "CMP": {
            "baseline": 1450,  # Watts
            "threshold": 100   # Drift > 100W triggers alert
        },
        "ETCH": {
            "baseline": 1200,
            "threshold": 100
        },
        "LITHO": {
            "baseline": 800,
            "threshold": 100
        },
        # Severity levels for absolute drift values
        "critical": 150,
        "high": 120,
        "medium": 100
    },
    "temperature_drift": {
        # Equipment-specific baselines and drift thresholds
        "CMP": {
            "baseline": 65,    # Celsius
            "threshold": 5     # Drift >= 5°C triggers alert
        },
        "ETCH": {
            "baseline": 70,
            "threshold": 5
        },
        "LITHO": {
            "baseline": 22,
            "threshold": 3
        },
        # Severity levels for absolute drift values
        "critical": 5,
        "high": 3,
        "medium": 2
    },
    "yield_threshold": {
        "critical": 0.80,  # < 80% yield
        "high": 0.85,      # < 85% yield
        "medium": 0.92     # < 92% yield
    }
}

# ============================================================================
# LEGACY THRESHOLDS (Backward compatibility - exact current behavior)
# ============================================================================

LEGACY_THRESHOLDS = {
    "particle_count": {
        # monitoring_service.py:114 uses > 1000 for CRITICAL
        "critical": 1000,
        # monitoring_service.py:116 uses > 800 for HIGH
        "high": 800,
        "medium": 500
    },
    "rf_power_drift": {
        # monitoring_service.py:333-347 uses these baselines
        "CMP": {
            "baseline": 1450,
            "threshold": 100
        },
        "ETCH": {
            "baseline": 1200,
            "threshold": 100
        },
        "LITHO": {
            "baseline": 800,
            "threshold": 100
        },
        # monitoring_service.py:121 uses > 100 for CRITICAL
        "critical": 100,
        # monitoring_service.py:123 uses > 80 for HIGH
        "high": 80,
        "medium": 60
    },
    "temperature_drift": {
        # monitoring_service.py:351 only checks CMP with baseline=65, threshold > 5
        "CMP": {
            "baseline": 65,
            "threshold": 5
        },
        "ETCH": {
            "baseline": 70,
            "threshold": 5
        },
        "LITHO": {
            "baseline": 22,
            "threshold": 3
        },
        # Severity levels (not used in legacy code but included for completeness)
        "critical": 5,
        "high": 3,
        "medium": 2
    },
    "yield_threshold": {
        "critical": 0.80,
        "high": 0.85,
        "medium": 0.92
    }
}


# ============================================================================
# Feature Flag and Accessor Functions
# ============================================================================

def is_centralized_thresholds_enabled() -> bool:
    """
    Check if centralized thresholds feature flag is enabled.
    
    Returns:
        bool: True if USE_CENTRALIZED_THRESHOLDS is "true" or "1", False otherwise
    """
    flag = os.getenv("USE_CENTRALIZED_THRESHOLDS", "false").lower()
    return flag in ("true", "1", "yes")


def get_thresholds() -> dict:
    """
    Get the active threshold configuration based on feature flag.
    
    Returns:
        dict: Either ALERT_THRESHOLDS or LEGACY_THRESHOLDS depending on flag
    """
    if is_centralized_thresholds_enabled():
        logger.debug("Using centralized thresholds (new business-aligned values)")
        return ALERT_THRESHOLDS
    else:
        logger.debug("Using legacy thresholds (backward compatibility mode)")
        return LEGACY_THRESHOLDS


def get_active_threshold_mode() -> str:
    """
    Get a human-readable description of the active threshold mode.
    
    Returns:
        str: Description of active mode for logging
    """
    if is_centralized_thresholds_enabled():
        return "CENTRALIZED (New Business Rules)"
    else:
        return "LEGACY (Backward Compatible)"


def get_particle_count_thresholds() -> dict:
    """
    Get particle count thresholds.
    
    Returns:
        dict: Particle count severity thresholds
    """
    return get_thresholds()["particle_count"]


def get_rf_power_thresholds() -> dict:
    """
    Get RF power drift thresholds.
    
    Returns:
        dict: RF power drift configuration with baselines and severity levels
    """
    return get_thresholds()["rf_power_drift"]


def get_temperature_thresholds() -> dict:
    """
    Get temperature drift thresholds.
    
    Returns:
        dict: Temperature drift configuration with baselines and severity levels
    """
    return get_thresholds()["temperature_drift"]


def get_yield_thresholds() -> dict:
    """
    Get yield thresholds.
    
    Returns:
        dict: Yield severity thresholds
    """
    return get_thresholds()["yield_threshold"]


# ============================================================================
# Logging and Validation
# ============================================================================

def log_threshold_configuration():
    """
    Log the current threshold configuration for debugging.
    Should be called at application startup.
    """
    mode = get_active_threshold_mode()
    thresholds = get_thresholds()
    
    logger.info("=" * 60)
    logger.info(f"🎯 Threshold Configuration Mode: {mode}")
    logger.info("=" * 60)
    logger.info(f"Particle Count CRITICAL: {thresholds['particle_count']['critical']}")
    logger.info(f"Particle Count HIGH: {thresholds['particle_count']['high']}")
    logger.info(f"RF Power CRITICAL drift: {thresholds['rf_power_drift']['critical']}W")
    logger.info(f"Temperature CRITICAL drift: {thresholds['temperature_drift']['critical']}°C")
    logger.info(f"CMP RF Power baseline: {thresholds['rf_power_drift']['CMP']['baseline']}W")
    logger.info(f"CMP Temperature baseline: {thresholds['temperature_drift']['CMP']['baseline']}°C")
    logger.info("=" * 60)


# ============================================================================
# Module Initialization
# ============================================================================

# Log configuration when module is imported
if __name__ != "__main__":
    # Only log in non-test environments
    logger.info(f"Threshold configuration loaded: {get_active_threshold_mode()}")

