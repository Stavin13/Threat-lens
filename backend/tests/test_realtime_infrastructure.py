"""
Tests for real-time infrastructure and base components.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.realtime.base import RealtimeComponent, AsyncEventHandler, HealthMonitorMixin
from app.realtime.event_loop import RealtimeManager, AsyncTaskManager
from app.realtime.exceptions import RealtimeError, MonitoringError, ProcessingError


class MockRealtimeComponent(RealtimeComponent):
    """Mock implementation of RealtimeComponent for testing."""
    
    def __init__(self, name: str, should_fail_start: bool = False, should_fail_stop: bool = False):
        super().__init__(name)
        self.should_fail_start = should_fail_start
        self.should_fail_stop = should_fail_stop
        self.start_called = False
        self.stop_called = False
    
    async def _start_impl(self) -> None:
        self.start_called = True
        if self.should_fail_start:
            raise RuntimeError("Mock start failure")
    
    async def _stop_impl(self) -> None:
        self.stop_called = True
        if self.should_fail_stop:
            raise RuntimeError("Mock stop failure")


class TestRealtimeComponent:
    """Test cases for RealtimeComponent base class."""
    
    @pytest.mark.asyncio
    async def test_component_lifecycle(self):
        """Test component start and stop lifecycle."""
        component = MockRealtimeComponent("test_component")
        
        # Initial state
        assert not component.is_running
        assert component.start_time is None
        assert component.error_count == 0
        
        # Start component
        await component.start()
        assert component.is_running
        assert component.start_time is not None
        assert component.start_called
        
        # Stop component
        await component.stop()
        assert not component.is_running
        assert component.stop_called
    
    @pytest.mark.asyncio
    async def test_component_start_failure(self):
        """Test component start failure handling."""
        component = MockRealtimeComponent("test_component", should_fail_start=True)
        
        with pytest.raises(RuntimeError, match="Mock start failure"):
            await component.start()
        
        assert not component.is_running
        assert component.error_count == 1
        assert component.last_error is not None
    
    @pytest.mark.asyncio
    async def test_component_stop_failure(self):
        """Test component stop failure handling."""
        component = MockRealtimeComponent("test_component", should_fail_stop=True)
        
        # Start successfully first
        await component.start()
        assert component.is_running
        
        # Stop with failure
        with pytest.raises(RuntimeError, match="Mock stop failure"):
            await component.stop()
        
        assert not component.is_running  # Should still be marked as stopped
        assert component.error_count == 1
    
    def test_health_status(self):
        """Test health status reporting."""
        component = MockRealtimeComponent("test_component")
        
        health = component.get_health_status()
        assert health["name"] == "test_component"
        assert health["is_running"] is False
        assert health["start_time"] is None
        assert health["uptime_seconds"] is None
        assert health["error_count"] == 0
        assert health["last_error"] is None


class TestRealtimeManager:
    """Test cases for RealtimeManager."""
    
    @pytest.mark.asyncio
    async def test_manager_lifecycle(self):
        """Test manager start and stop lifecycle."""
        manager = RealtimeManager()
        component1 = MockRealtimeComponent("component1")
        component2 = MockRealtimeComponent("component2")
        
        manager.register_component(component1)
        manager.register_component(component2)
        
        # Start all components
        await manager.start_all()
        assert manager.is_running
        assert component1.is_running
        assert component2.is_running
        
        # Stop all components
        await manager.stop_all()
        assert not manager.is_running
        assert not component1.is_running
        assert not component2.is_running
    
    @pytest.mark.asyncio
    async def test_manager_partial_failure(self):
        """Test manager handling of partial component failures."""
        manager = RealtimeManager()
        good_component = MockRealtimeComponent("good_component")
        bad_component = MockRealtimeComponent("bad_component", should_fail_start=True)
        
        manager.register_component(good_component)
        manager.register_component(bad_component)
        
        # Start all - should continue despite one failure
        await manager.start_all()
        assert manager.is_running
        assert good_component.is_running
        assert not bad_component.is_running
    
    def test_component_registration(self):
        """Test component registration and unregistration."""
        manager = RealtimeManager()
        component = MockRealtimeComponent("test_component")
        
        # Register component
        manager.register_component(component)
        assert "test_component" in manager.components
        
        # Unregister component
        manager.unregister_component("test_component")
        assert "test_component" not in manager.components
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test manager health check functionality."""
        manager = RealtimeManager()
        component = MockRealtimeComponent("test_component")
        manager.register_component(component)
        
        await manager.start_all()
        
        health = await manager.health_check()
        assert health["overall_status"] == "healthy"
        assert health["manager_running"] is True
        assert "test_component" in health["components"]


class TestAsyncTaskManager:
    """Test cases for AsyncTaskManager."""
    
    @pytest.mark.asyncio
    async def test_task_creation(self):
        """Test async task creation and tracking."""
        manager = AsyncTaskManager()
        
        async def dummy_task():
            await asyncio.sleep(0.1)
            return "completed"
        
        # Create task
        task = manager.create_task("test_task", dummy_task())
        assert "test_task" in manager.tasks
        assert not task.done()
        
        # Wait for completion
        result = await task
        assert result == "completed"
        assert task.done()
    
    @pytest.mark.asyncio
    async def test_task_cancellation(self):
        """Test task cancellation."""
        manager = AsyncTaskManager()
        
        async def long_running_task():
            await asyncio.sleep(10)  # Long running task
        
        # Create and cancel task
        task = manager.create_task("long_task", long_running_task())
        assert manager.cancel_task("long_task")
        
        # Task should be cancelled
        with pytest.raises(asyncio.CancelledError):
            await task
    
    @pytest.mark.asyncio
    async def test_task_replacement(self):
        """Test task replacement functionality."""
        manager = AsyncTaskManager()
        
        async def task1():
            await asyncio.sleep(0.1)
            return "task1"
        
        async def task2():
            await asyncio.sleep(0.1)
            return "task2"
        
        # Create first task
        first_task = manager.create_task("replaceable_task", task1())
        
        # Replace with second task
        second_task = manager.create_task("replaceable_task", task2(), replace_existing=True)
        
        # First task should be cancelled, second should complete
        with pytest.raises(asyncio.CancelledError):
            await first_task
        
        result = await second_task
        assert result == "task2"
    
    @pytest.mark.asyncio
    async def test_task_status(self):
        """Test task status reporting."""
        manager = AsyncTaskManager()
        
        async def dummy_task():
            await asyncio.sleep(0.01)  # Small delay to ensure we can check status
            return "done"
        
        task = manager.create_task("status_task", dummy_task())
        status = manager.get_task_status()
        
        assert "status_task" in status
        # Status should be either "running" or "completed" depending on timing
        
        # Wait for completion and check final status
        await task
        final_status = manager.get_task_status()
        assert final_status["status_task"] == "completed"


class TestHealthMonitorMixin:
    """Test cases for HealthMonitorMixin."""
    
    def test_health_metrics(self):
        """Test health metrics functionality."""
        
        class TestComponent(HealthMonitorMixin):
            def __init__(self):
                super().__init__()
        
        component = TestComponent()
        
        # Update metrics
        component.update_health_metric("cpu_usage", 75.5)
        component.update_health_metric("memory_usage", 60.2)
        
        # Get metrics
        metrics = component.get_health_metrics()
        assert "metrics" in metrics
        assert "last_check" in metrics
        assert "cpu_usage" in metrics["metrics"]
        assert "memory_usage" in metrics["metrics"]
        assert metrics["metrics"]["cpu_usage"]["value"] == 75.5


class TestExceptions:
    """Test cases for custom exceptions."""
    
    def test_exception_hierarchy(self):
        """Test exception inheritance hierarchy."""
        # Test base exception
        base_error = RealtimeError("Base error")
        assert str(base_error) == "Base error"
        assert isinstance(base_error, Exception)
        
        # Test derived exceptions
        monitoring_error = MonitoringError("Monitoring error")
        assert isinstance(monitoring_error, RealtimeError)
        
        processing_error = ProcessingError("Processing error")
        assert isinstance(processing_error, RealtimeError)