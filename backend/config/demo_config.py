"""
Demo Mode Configuration
Centralized configuration for demo mode parameters
"""

import os

# Excursion Probability - Centralized default value
# Controls the random excursion generation rate (0.0-1.0)
DEMO_EXCURSION_PROBABILITY = float(os.getenv("DEMO_EXCURSION_PROBABILITY", "0.1"))  # 10% excursion rate for realistic monitoring
