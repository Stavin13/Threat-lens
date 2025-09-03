"""
Real-time log detection and processing module.

This module provides real-time monitoring, processing, and notification
capabilities for ThreatLens security log analysis.
"""

from .base import RealtimeComponent
from .exceptions import RealtimeError, MonitoringError, ProcessingError

__all__ = [
    "RealtimeComponent",
    "RealtimeError", 
    "MonitoringError",
    "ProcessingError"
]