"""
Tests for diagnostic utilities and troubleshooting system.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, AsyncMock

from app.realtime.diagnostics import (
    DiagnosticManager, DiagnosticResult, SystemDiagnostics,
    diagnostic_manager, run_system_diagnostics, run_quick_health_check
)
from app.realtime.error_handler import ErrorHandler, ErrorRecord, ErrorSeverity, ErrorCategory
from app.realtime.health_monitor import HealthMonitor, SystemMetrics


class TestDiagnosticManager:
    """Test diagnostic manager functionality."""
    
    @pytest.fixture
    def mock_health_monitor(self):
        """Create mock health monitor."""
        monitor = Mock(spec=HealthMonitor)
        monitor.monitoring_active = True
        monitor.start_time = datetime.now() - timedelta(hours=1)
        monitor.health_checks = {'test_component': Mock()}
        monitor.system_metrics_history = [
            SystemMetrics(
                cpu_percent=50.0,
                memory_percent=60.0,
                memory_used_mb=1024.0,
                memory_total_mb=2048.0,
                disk_percent=30.0,
                disk_used_gb=10.0,
                disk_total_gb=100.0,
                load_average=[1.0, 1.2, 1.1],
                timestamp=datetime.now(timezone.utc)
            )
        ]
        return monitor
    
    @pytest.fixture
    def mock_error_handler(self):
        """Create mock error handler."""
        handler = Mock(spec=ErrorHandler)
        handler.get_error_statistics.return_value = {
            'total_errors': 10,
            'recovery_success_rate': 0.8,
            'critical_error_rate': 0.1,
            'errors_by_severity': {'critical': 1, 'high': 2, 'medium': 4, 'low': 3},
            'errors_by_category': {'parsing_error': 5, 'database_error': 3, 'websocket_error': 2},
            'recent_errors': [],
            'error_patterns': {}
        }
        return handler
    
    @pytest.fixture
    def diagnostic_manager_instance(self, mock_health_monitor, mock_error_handler):
        """Create diagnostic manager with mocked components."""
        return DiagnosticManager(
            health_monitor=mock_health_monitor,
            error_handler=mock_error_handler
        )
    
    @pytest.mark.asyncio
    async def test_collect_system_info(self, diagnostic_manager_instance):
        """Test system information collection."""
        system_info = await diagnostic_manager_instance._collect_system_info()
        
        assert isinstance(system_info, dict)
        assert 'cpu_count' in system_info
        assert 'memory_total_gb' in system_info
        assert 'disk_total_gb' in system_info
    
    @pytest.mark.asyncio
    async def test_diagnose_health_monitor_active(self, diagnostic_manager_instance):
        """Test health monitor diagnostics when active."""
        result = await diagnostic_manager_instance._diagnose_health_monitor()
        
        assert isinstance(result, DiagnosticResult)
        assert result.check_name == 'health_monitor'
        assert result.status == 'pass'
        assert result.details['monitoring_active'] is True
        assert result.details['health_checks_count'] == 1
    
    @pytest.mark.asyncio
    async def test_diagnose_health_monitor_inactive(self, diagnostic_manager_instance):
        """Test health monitor diagnostics when inactive."""
        diagnostic_manager_instance.health_monitor.monitoring_active = False
        
        result = await diagnostic_manager_instance._diagnose_health_monitor()
        
        assert result.status == 'fail'
        assert result.severity == 'error'
        assert 'not active' in result.message
    
    @pytest.mark.asyncio
    async def test_diagnose_error_handler_normal(self, diagnostic_manager_instance):
        """Test error handler diagnostics under normal conditions."""
        result = await diagnostic_manager_instance._diagnose_error_handler()
        
        assert isinstance(result, DiagnosticResult)
        assert result.check_name == 'error_handler'
        assert result.status == 'pass'
        assert result.details['total_errors'] == 10
        assert result.details['recovery_success_rate'] == 0.8
    
    @pytest.mark.asyncio
    async def test_diagnose_error_handler_high_critical_rate(self, diagnostic_manager_instance):
        """Test error handler diagnostics with high critical error rate."""
        diagnostic_manager_instance.error_handler.get_error_statistics.return_value.update({
            'critical_error_rate': 0.15  # 15% critical errors
        })
        
        result = await diagnostic_manager_instance._diagnose_error_handler()
        
        assert result.status == 'fail'
        assert result.severity == 'critical'
        assert 'High critical error rate' in result.message
    
    @pytest.mark.asyncio
    async def test_diagnose_error_handler_low_recovery_rate(self, diagnostic_manager_instance):
        """Test error handler diagnostics with low recovery success rate."""
        diagnostic_manager_instance.error_handler.get_error_statistics.return_value.update({
            'recovery_success_rate': 0.7,  # 70% recovery success
            'critical_error_rate': 0.05
        })
        
        result = await diagnostic_manager_instance._diagnose_error_handler()
        
        assert result.status == 'warning'
        assert result.severity == 'warning'
        assert 'Low recovery success rate' in result.message
    
    @pytest.mark.asyncio
    async def test_analyze_performance_metrics(self, diagnostic_manager_instance):
        """Test performance metrics analysis."""
        # Add more metrics to history
        for i in range(10):
            diagnostic_manager_instance.health_monitor.system_metrics_history.append(
                SystemMetrics(
                    cpu_percent=50.0 + i,
                    memory_percent=60.0 + i,
                    memory_used_mb=1024.0,
                    memory_total_mb=2048.0,
                    disk_percent=30.0,
                    disk_used_gb=10.0,
                    disk_total_gb=100.0,
                    load_average=[1.0, 1.2, 1.1],
                    timestamp=datetime.now(timezone.utc) + timedelta(minutes=i)
                )
            )
        
        metrics = await diagnostic_manager_instance._analyze_performance_metrics()
        
        assert isinstance(metrics, dict)
        assert 'average_cpu_percent' in metrics
        assert 'average_memory_percent' in metrics
        assert 'cpu_trend' in metrics
        assert 'memory_trend' in metrics
        assert metrics['samples_count'] == 10  # Last 10 samples
    
    @pytest.mark.asyncio
    async def test_analyze_error_patterns(self, diagnostic_manager_instance):
        """Test error pattern analysis."""
        error_analysis = await diagnostic_manager_instance._analyze_error_patterns()
        
        assert isinstance(error_analysis, dict)
        assert 'total_errors' in error_analysis
        assert 'recovery_success_rate' in error_analysis
        assert 'critical_errors' in error_analysis
        assert error_analysis['total_errors'] == 10
    
    @pytest.mark.asyncio
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    async def test_check_resource_usage(self, mock_disk, mock_memory, mock_cpu, diagnostic_manager_instance):
        """Test resource usage checking."""
        # Mock system resource calls
        mock_cpu.return_value = 75.0
        mock_memory.return_value = Mock(percent=80.0, available=1024**3)
        mock_disk.return_value = Mock(used=50*1024**3, total=100*1024**3, free=50*1024**3)
        
        resource_usage = await diagnostic_manager_instance._check_resource_usage()
        
        assert isinstance(resource_usage, dict)
        assert 'cpu_percent' in resource_usage
        assert 'memory_percent' in resource_usage
        assert 'disk_percent' in resource_usage
        assert 'resource_issues' in resource_usage
        assert resource_usage['cpu_percent'] == 75.0
        assert resource_usage['memory_percent'] == 80.0
    
    @pytest.mark.asyncio
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    async def test_check_resource_usage_high_usage(self, mock_disk, mock_memory, mock_cpu, diagnostic_manager_instance):
        """Test resource usage checking with high usage."""
        # Mock high resource usage
        mock_cpu.return_value = 95.0  # Above threshold
        mock_memory.return_value = Mock(percent=95.0, available=1024**3)  # Above threshold
        mock_disk.return_value = Mock(used=95*1024**3, total=100*1024**3, free=5*1024**3)  # Above threshold
        
        resource_usage = await diagnostic_manager_instance._check_resource_usage()
        
        assert 'high_cpu_usage' in resource_usage['resource_issues']
        assert 'high_memory_usage' in resource_usage['resource_issues']
        assert 'disk_space_low' in resource_usage['resource_issues']
    
    def test_calculate_trend_increasing(self, diagnostic_manager_instance):
        """Test trend calculation for increasing values."""
        values = [10, 15, 20, 25, 30]
        trend = diagnostic_manager_instance._calculate_trend(values)
        assert trend == 'increasing'
    
    def test_calculate_trend_decreasing(self, diagnostic_manager_instance):
        """Test trend calculation for decreasing values."""
        values = [30, 25, 20, 15, 10]
        trend = diagnostic_manager_instance._calculate_trend(values)
        assert trend == 'decreasing'
    
    def test_calculate_trend_stable(self, diagnostic_manager_instance):
        """Test trend calculation for stable values."""
        values = [20, 21, 19, 20, 21]
        trend = diagnostic_manager_instance._calculate_trend(values)
        assert trend == 'stable'
    
    def test_generate_recommendations(self, diagnostic_manager_instance):
        """Test recommendation generation."""
        # Create mock diagnostic results
        component_diagnostics = {
            'test_component': DiagnosticResult(
                check_name='test_component',
                status='warning',
                message='Test warning',
                details={},
                timestamp=datetime.now(timezone.utc),
                recommendations=['Fix test issue'],
                severity='warning'
            )
        }
        
        performance_metrics = {
            'average_cpu_percent': 85.0,  # High CPU
            'average_memory_percent': 90.0  # High memory
        }
        
        error_analysis = {
            'critical_errors': 2,
            'recovery_success_rate': 0.7
        }
        
        resource_usage = {
            'resource_issues': ['high_memory_usage']
        }
        
        recommendations = diagnostic_manager_instance._generate_recommendations(
            component_diagnostics, performance_metrics, error_analysis, resource_usage
        )
        
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        assert 'Fix test issue' in recommendations
        assert any('CPU usage' in rec for rec in recommendations)
        assert any('memory' in rec for rec in recommendations)
    
    def test_determine_overall_status(self, diagnostic_manager_instance):
        """Test overall status determination."""
        # Test with all passing components
        passing_diagnostics = {
            'comp1': DiagnosticResult('comp1', 'pass', 'OK', {}, datetime.now(timezone.utc), []),
            'comp2': DiagnosticResult('comp2', 'pass', 'OK', {}, datetime.now(timezone.utc), [])
        }
        status = diagnostic_manager_instance._determine_overall_status(passing_diagnostics)
        assert status == 'healthy'
        
        # Test with warning component
        warning_diagnostics = {
            'comp1': DiagnosticResult('comp1', 'pass', 'OK', {}, datetime.now(timezone.utc), []),
            'comp2': DiagnosticResult('comp2', 'warning', 'Warning', {}, datetime.now(timezone.utc), [])
        }
        status = diagnostic_manager_instance._determine_overall_status(warning_diagnostics)
        assert status == 'warning'
        
        # Test with failed component
        failed_diagnostics = {
            'comp1': DiagnosticResult('comp1', 'pass', 'OK', {}, datetime.now(timezone.utc), []),
            'comp2': DiagnosticResult('comp2', 'fail', 'Failed', {}, datetime.now(timezone.utc), [])
        }
        status = diagnostic_manager_instance._determine_overall_status(failed_diagnostics)
        assert status == 'critical'
    
    @pytest.mark.asyncio
    async def test_run_full_diagnostics(self, diagnostic_manager_instance):
        """Test full diagnostic run."""
        with patch.multiple(
            diagnostic_manager_instance,
            _collect_system_info=AsyncMock(return_value={'test': 'info'}),
            _run_component_diagnostics=AsyncMock(return_value={}),
            _analyze_performance_metrics=AsyncMock(return_value={'test': 'metrics'}),
            _analyze_error_patterns=AsyncMock(return_value={'test': 'errors'}),
            _check_resource_usage=AsyncMock(return_value={'test': 'resources'})
        ):
            diagnostics = await diagnostic_manager_instance.run_full_diagnostics()
            
            assert isinstance(diagnostics, SystemDiagnostics)
            assert diagnostics.system_info == {'test': 'info'}
            assert diagnostics.performance_metrics == {'test': 'metrics'}
            assert diagnostics.error_analysis == {'test': 'errors'}
            assert diagnostics.resource_usage == {'test': 'resources'}
    
    @pytest.mark.asyncio
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('time.time')
    @patch('psutil.boot_time')
    async def test_run_quick_health_check(self, mock_boot_time, mock_time, mock_memory, mock_cpu, diagnostic_manager_instance):
        """Test quick health check."""
        # Mock system calls
        mock_cpu.return_value = 50.0
        mock_memory.return_value = Mock(percent=60.0)
        mock_time.return_value = 1000000
        mock_boot_time.return_value = 999000
        
        result = await diagnostic_manager_instance.run_quick_health_check()
        
        assert isinstance(result, dict)
        assert 'status' in result
        assert 'cpu_percent' in result
        assert 'memory_percent' in result
        assert 'timestamp' in result
        assert result['status'] == 'healthy'
    
    @pytest.mark.asyncio
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    async def test_run_quick_health_check_critical(self, mock_memory, mock_cpu, diagnostic_manager_instance):
        """Test quick health check with critical resource usage."""
        # Mock critical resource usage
        mock_cpu.return_value = 95.0  # Critical CPU
        mock_memory.return_value = Mock(percent=95.0)  # Critical memory
        
        result = await diagnostic_manager_instance.run_quick_health_check()
        
        assert result['status'] == 'critical'
        assert 'Critical memory usage' in result['issues']
        assert 'Critical CPU usage' in result['issues']
    
    def test_get_diagnostic_history(self, diagnostic_manager_instance):
        """Test diagnostic history retrieval."""
        # Add some diagnostic history
        for i in range(5):
            diagnostics = SystemDiagnostics(
                timestamp=datetime.now(timezone.utc) + timedelta(minutes=i),
                overall_status='healthy',
                system_info={},
                component_diagnostics={},
                performance_metrics={},
                error_analysis={},
                resource_usage={},
                recommendations=[]
            )
            diagnostic_manager_instance.diagnostic_history.append(diagnostics)
        
        history = diagnostic_manager_instance.get_diagnostic_history(limit=3)
        
        assert isinstance(history, list)
        assert len(history) == 3
        assert all('timestamp' in entry for entry in history)
        assert all('overall_status' in entry for entry in history)


class TestDiagnosticIntegration:
    """Test diagnostic system integration."""
    
    @pytest.mark.asyncio
    async def test_run_system_diagnostics_function(self):
        """Test global diagnostic function."""
        with patch('app.realtime.diagnostics.diagnostic_manager') as mock_manager:
            mock_manager.run_full_diagnostics = AsyncMock(return_value=Mock())
            
            result = await run_system_diagnostics()
            
            mock_manager.run_full_diagnostics.assert_called_once()
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_run_quick_health_check_function(self):
        """Test global quick health check function."""
        with patch('app.realtime.diagnostics.diagnostic_manager') as mock_manager:
            mock_manager.run_quick_health_check = AsyncMock(return_value={'status': 'healthy'})
            
            result = await run_quick_health_check()
            
            mock_manager.run_quick_health_check.assert_called_once()
            assert result['status'] == 'healthy'


if __name__ == '__main__':
    pytest.main([__file__])