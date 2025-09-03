"""
Async event loop integration for real-time components.

This module provides utilities for integrating real-time components
with FastAPI's async event loop and managing component lifecycles.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from .base import RealtimeComponent
from .exceptions import RealtimeError
from .websocket_server import WebSocketManager
from .event_broadcaster import EventBroadcaster
from .websocket_api import WebSocketAPI

logger = logging.getLogger(__name__)


class RealtimeManager:
    """
    Manager for real-time components and their lifecycle.
    
    Handles starting, stopping, and monitoring of all real-time components
    within the FastAPI application lifecycle.
    """
    
    def __init__(self):
        self.components: Dict[str, RealtimeComponent] = {}
        self.is_running = False
        self._background_tasks: List[asyncio.Task] = []
        
        # WebSocket components
        self.websocket_manager: Optional[WebSocketManager] = None
        self.event_broadcaster: Optional[EventBroadcaster] = None
        self.websocket_api: Optional[WebSocketAPI] = None
        
    def register_component(self, component: RealtimeComponent) -> None:
        """Register a real-time component for management."""
        if component.name in self.components:
            logger.warning(f"Component {component.name} is already registered")
            return
            
        self.components[component.name] = component
        logger.info(f"Registered real-time component: {component.name}")
    
    def unregister_component(self, component_name: str) -> None:
        """Unregister a real-time component."""
        if component_name in self.components:
            del self.components[component_name]
            logger.info(f"Unregistered real-time component: {component_name}")
    
    async def start_all(self) -> None:
        """Start all registered components."""
        if self.is_running:
            logger.warning("RealtimeManager is already running")
            return
            
        logger.info("Starting all real-time components...")
        
        # Initialize WebSocket components first
        try:
            await self._initialize_websocket_components()
        except Exception as e:
            logger.error(f"Failed to initialize WebSocket components: {e}")
            # Continue with other components
        
        failed_components = []
        
        for name, component in self.components.items():
            try:
                await component.start()
                logger.info(f"Started component: {name}")
            except Exception as e:
                logger.error(f"Failed to start component {name}: {e}")
                failed_components.append(name)
        
        if failed_components:
            logger.warning(f"Failed to start components: {failed_components}")
            # Continue running with successful components
        
        self.is_running = True
        logger.info("Real-time manager started")
    
    async def stop_all(self) -> None:
        """Stop all registered components."""
        if not self.is_running:
            logger.warning("RealtimeManager is not running")
            return
            
        logger.info("Stopping all real-time components...")
        
        # Cancel background tasks
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        self._background_tasks.clear()
        
        # Stop WebSocket components first
        try:
            await self._shutdown_websocket_components()
        except Exception as e:
            logger.error(f"Error stopping WebSocket components: {e}")
        
        # Stop all other components
        for name, component in self.components.items():
            try:
                await component.stop()
                logger.info(f"Stopped component: {name}")
            except Exception as e:
                logger.error(f"Error stopping component {name}: {e}")
        
        self.is_running = False
        logger.info("Real-time manager stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all components."""
        return {
            "manager_running": self.is_running,
            "component_count": len(self.components),
            "components": {
                name: component.get_health_status()
                for name, component in self.components.items()
            },
            "background_tasks": len(self._background_tasks)
        }
    
    def add_background_task(self, coro) -> asyncio.Task:
        """Add a background task to be managed by the event loop."""
        task = asyncio.create_task(coro)
        self._background_tasks.append(task)
        
        # Clean up completed tasks
        self._background_tasks = [t for t in self._background_tasks if not t.done()]
        
        return task
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all components."""
        health_status = {
            "overall_status": "healthy",
            "manager_running": self.is_running,
            "components": {}
        }
        
        unhealthy_components = []
        
        for name, component in self.components.items():
            component_health = component.get_health_status()
            health_status["components"][name] = component_health
            
            if not component_health["is_running"] or component_health["error_count"] > 0:
                unhealthy_components.append(name)
        
        if unhealthy_components:
            health_status["overall_status"] = "degraded"
            health_status["unhealthy_components"] = unhealthy_components
        
        return health_status
    
    async def _initialize_websocket_components(self) -> None:
        """Initialize WebSocket components."""
        logger.info("Initializing WebSocket components...")
        
        try:
            # Create WebSocket manager
            max_connections = 100  # TODO: Get from config
            self.websocket_manager = WebSocketManager(max_connections=max_connections)
            
            # Create event broadcaster
            self.event_broadcaster = EventBroadcaster(
                websocket_manager=self.websocket_manager,
                max_queue_size=1000  # TODO: Get from config
            )
            
            # Create WebSocket API
            self.websocket_api = WebSocketAPI(
                websocket_manager=self.websocket_manager,
                event_broadcaster=self.event_broadcaster
            )
            
            # Register components for lifecycle management
            self.register_component(self.websocket_manager)
            self.register_component(self.event_broadcaster)
            
            logger.info("WebSocket components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize WebSocket components: {e}")
            raise
    
    async def _shutdown_websocket_components(self) -> None:
        """Shutdown WebSocket components."""
        logger.info("Shutting down WebSocket components...")
        
        try:
            # Stop event broadcaster first
            if self.event_broadcaster and self.event_broadcaster.is_running:
                await self.event_broadcaster.stop()
            
            # Stop WebSocket manager
            if self.websocket_manager and self.websocket_manager.is_running:
                await self.websocket_manager.stop()
            
            # Clear references
            self.websocket_api = None
            self.event_broadcaster = None
            self.websocket_manager = None
            
            logger.info("WebSocket components shut down successfully")
            
        except Exception as e:
            logger.error(f"Error shutting down WebSocket components: {e}")
            raise
    
    def get_websocket_manager(self) -> Optional[WebSocketManager]:
        """Get the WebSocket manager instance."""
        return self.websocket_manager
    
    def get_event_broadcaster(self) -> Optional[EventBroadcaster]:
        """Get the event broadcaster instance."""
        return self.event_broadcaster
    
    def get_websocket_api(self) -> Optional[WebSocketAPI]:
        """Get the WebSocket API instance."""
        return self.websocket_api


# Global instance
realtime_manager = RealtimeManager()


@asynccontextmanager
async def realtime_lifespan():
    """
    Context manager for real-time component lifecycle.
    
    This can be used within FastAPI's lifespan context manager
    to properly start and stop real-time components.
    """
    try:
        # Startup
        await realtime_manager.start_all()
        yield realtime_manager
    finally:
        # Shutdown
        await realtime_manager.stop_all()


def get_realtime_manager() -> RealtimeManager:
    """Get the global realtime manager instance."""
    return realtime_manager


class AsyncTaskManager:
    """
    Utility class for managing async tasks in real-time components.
    """
    
    def __init__(self):
        self.tasks: Dict[str, asyncio.Task] = {}
    
    def create_task(self, name: str, coro, replace_existing: bool = False) -> asyncio.Task:
        """Create and track a named async task."""
        if name in self.tasks and not replace_existing:
            if not self.tasks[name].done():
                raise RealtimeError(f"Task {name} already exists and is running")
        
        # Cancel existing task if replacing
        if name in self.tasks and not self.tasks[name].done():
            self.tasks[name].cancel()
        
        task = asyncio.create_task(coro)
        self.tasks[name] = task
        
        # Add cleanup callback
        task.add_done_callback(lambda t: self._cleanup_task(name, t))
        
        return task
    
    def cancel_task(self, name: str) -> bool:
        """Cancel a named task."""
        if name in self.tasks and not self.tasks[name].done():
            self.tasks[name].cancel()
            return True
        return False
    
    def cancel_all(self) -> None:
        """Cancel all tracked tasks."""
        for task in self.tasks.values():
            if not task.done():
                task.cancel()
    
    async def wait_for_all(self, timeout: Optional[float] = None) -> None:
        """Wait for all tasks to complete."""
        if not self.tasks:
            return
        
        running_tasks = [task for task in self.tasks.values() if not task.done()]
        if running_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*running_tasks, return_exceptions=True),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for tasks to complete")
    
    def get_task_status(self) -> Dict[str, str]:
        """Get status of all tracked tasks."""
        status = {}
        for name, task in self.tasks.items():
            if task.done():
                if task.cancelled():
                    status[name] = "cancelled"
                elif task.exception():
                    status[name] = f"failed: {task.exception()}"
                else:
                    status[name] = "completed"
            else:
                status[name] = "running"
        return status
    
    def _cleanup_task(self, name: str, task: asyncio.Task) -> None:
        """Clean up completed task."""
        if task.cancelled():
            logger.debug(f"Task {name} was cancelled")
        elif task.exception():
            logger.error(f"Task {name} failed: {task.exception()}")
        else:
            logger.debug(f"Task {name} completed successfully")