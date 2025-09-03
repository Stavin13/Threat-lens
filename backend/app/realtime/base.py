"""
Base classes and interfaces for real-time components.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class RealtimeComponent(ABC):
    """
    Abstract base class for all real-time components.
    
    Provides common functionality for lifecycle management,
    health monitoring, and error handling.
    """
    
    def __init__(self, name: str):
        self.name = name
        self.is_running = False
        self.start_time: Optional[datetime] = None
        self.error_count = 0
        self.last_error: Optional[Exception] = None
        self._shutdown_event = asyncio.Event()
        
    async def start(self) -> None:
        """Start the component."""
        if self.is_running:
            logger.warning(f"Component {self.name} is already running")
            return
            
        try:
            logger.info(f"Starting component: {self.name}")
            await self._start_impl()
            self.is_running = True
            self.start_time = datetime.now(timezone.utc)
            logger.info(f"Component {self.name} started successfully")
        except Exception as e:
            self.last_error = e
            self.error_count += 1
            logger.error(f"Failed to start component {self.name}: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the component."""
        if not self.is_running:
            logger.warning(f"Component {self.name} is not running")
            return
            
        try:
            logger.info(f"Stopping component: {self.name}")
            self._shutdown_event.set()
            await self._stop_impl()
            logger.info(f"Component {self.name} stopped successfully")
        except Exception as e:
            self.last_error = e
            self.error_count += 1
            logger.error(f"Error stopping component {self.name}: {e}")
            raise
        finally:
            # Always mark as stopped, even if stop implementation fails
            self.is_running = False
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get the health status of the component."""
        uptime = None
        if self.start_time and self.is_running:
            uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
            
        return {
            "name": self.name,
            "is_running": self.is_running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "uptime_seconds": uptime,
            "error_count": self.error_count,
            "last_error": str(self.last_error) if self.last_error else None
        }
    
    @abstractmethod
    async def _start_impl(self) -> None:
        """Implementation-specific start logic."""
        pass
    
    @abstractmethod
    async def _stop_impl(self) -> None:
        """Implementation-specific stop logic."""
        pass
    
    def _handle_error(self, error: Exception, context: str = "") -> None:
        """Handle errors consistently across components."""
        self.last_error = error
        self.error_count += 1
        logger.error(f"Error in {self.name} {context}: {error}")


class AsyncEventHandler(ABC):
    """
    Abstract base class for async event handlers.
    """
    
    @abstractmethod
    async def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Handle an async event."""
        pass


class HealthMonitorMixin:
    """
    Mixin class to add health monitoring capabilities.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._health_metrics: Dict[str, Any] = {}
        self._last_health_check = datetime.now(timezone.utc)
    
    def update_health_metric(self, metric_name: str, value: Any) -> None:
        """Update a health metric."""
        self._health_metrics[metric_name] = {
            "value": value,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def get_health_metrics(self) -> Dict[str, Any]:
        """Get all health metrics."""
        return {
            "metrics": self._health_metrics,
            "last_check": self._last_health_check.isoformat()
        }