"""
Stress testing script for the real-time log detection system.

This script performs comprehensive stress testing to validate system
performance under high load conditions and extreme scenarios.
"""

import asyncio
import logging
import tempfile
import time
import random
import string
import json
import psutil
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
import threading

# Import real-time components
from app.realtime.performance_integration import get_performance_integration_manager
from app.realtime.optimized_file_monitor import OptimizedLogFileMonitor
from app.realtime.optimized_ingestion_queue import OptimizedRealtimeIngestionQueue
from app.realtime.performance_optimizer import get_performance_optimizer
from app.realtime.models import LogSourceConfig, LogSourceType
from app.realtime.ingestion_queue import LogEntry, LogEntryPriority

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StressTestRunner:
    """Runs comprehensive stress tests on the real-time system."""
    
    def __init__(self):
        self.test_results = {}
        self.temp_dir = None
        self.log_files = []
        self.components = {}
        self.processed_entries = []
        self.stress_test_active = False
        
        # Test configuration
        self.test_duration = 60  # seconds
        self.high_volume_entries_per_second = 1000
        self.concurrent_sources = 10
        self.large_entry_size = 10000  # bytes
        
    async def setup_stress_test_environment(self):
        """Set up environment for stress testing."""
        logger.info("Setting up stress test environment...")
        
        # Create temporary directory and multiple log files
        self.temp_dir = tempfile.mkdtemp()
        
        for i in range(self.concurrent_sources):
            log_file = Path(self.temp_dir) / f"stress_test_log_{i}.log"
            log_file.write_text(f"Initial content for stress test log {i}\n")
            self.log_files.append(str(log_file))
        
        # Initialize components with stress test configurations
        self.components['optimizer'] = get_performance_optimizer()
        await self.components['optimizer'].start()
        
        self.components['file_monitor'] = OptimizedLogFileMonitor("StressTestMonitor")
        await self.components['file_monitor'].start()
        
        # Configure queue for high throughput
        self.components['ingestion_queue'] = OptimizedRealtimeIngestionQueue(
            max_queue_size=50000,  # Large queue for stress testing
            batch_size=100,        # Larger batches
            batch_timeout=1.0,     # Shorter timeout
            max_concurrent_batches=10,  # More concurrent processing
            memory_optimization=True,
            adaptive_batching=True
        )
        await self.components['ingestion_queue'].start()
        
        self.components['integration_manager'] = get_performance_integration_manager()
        await self.components['integration_manager'].start()
        
        # Register components
        self.components['integration_manager'].register_file_monitor(self.components['file_monitor'])
        self.components['integration_manager'].register_ingestion_queue(self.components['ingestion_queue'])
        
        # Set up high-performance processing pipeline
        self.processed_entries = []
        self.processing_times = []
        
        async def stress_batch_processor(batch: List[LogEntry]):
            """High-performance batch processor for stress testing."""
            start_time = time.time()
            
            # Simulate processing with minimal overhead
            self.processed_entries.extend(batch)
            
            # Record processing time
            processing_time = time.time() - start_time
            self.processing_times.append(processing_time)
            
            # Minimal delay to simulate real processing
            await asyncio.sleep(0.001)
        
        self.components['ingestion_queue'].set_batch_processor(stress_batch_processor)
        
        # Connect file monitor to queue with high-performance callback
        async def high_performance_queue_callback(entry: LogEntry):
            await self.components['ingestion_queue'].enqueue_log_entry(entry)
        
        self.components['file_monitor'].add_log_entry_callback(high_performance_queue_callback)
        
        # Configure log sources
        for i, log_file in enumerate(self.log_files):
            source_config = LogSourceConfig(
                source_name=f"stress_source_{i}",
                path=log_file,
                source_type=LogSourceType.FILE,
                enabled=True,
                priority=LogEntryPriority.MEDIUM
            )
            self.components['file_monitor'].add_log_source(source_config)
        
        logger.info(f"Stress test environment setup complete with {len(self.log_files)} log sources")
    
    async def cleanup_stress_test_environment(self):
        """Clean up stress test environment."""
        logger.info("Cleaning up stress test environment...")
        
        self.stress_test_active = False
        
        # Stop components
        for component in self.components.values():
            if hasattr(component, 'stop'):
                await component.stop()
        
        # Clean up temporary files
        if self.temp_dir:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        
        logger.info("Stress test environment cleanup complete")
    
    def generate_test_log_entry(self, entry_id: int, source_id: int, size: int = 100) -> str:
        """Generate a test log entry of specified size."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
        
        # Generate random content to reach desired size
        base_entry = f"{timestamp} INFO [Source-{source_id}] Test entry {entry_id}"
        
        if size > len(base_entry):
            padding_size = size - len(base_entry) - 10  # Leave room for ending
            padding = ''.join(random.choices(string.ascii_letters + string.digits, k=padding_size))
            return f"{base_entry} {padding} [END]"
        
        return base_entry
    
    async def stress_test_high_volume_ingestion(self) -> Dict[str, Any]:
        """Test system under high volume log ingestion."""
        logger.info("Starting high volume ingestion stress test...")
        
        test_start_time = time.time()
        initial_processed_count = len(self.processed_entries)
        
        # Generate high volume of log entries
        entries_generated = 0
        target_entries = self.high_volume_entries_per_second * self.test_duration
        
        async def generate_entries():
            nonlocal entries_generated
            
            while entries_generated < target_entries and time.time() - test_start_time < self.test_duration:
                # Write entries to multiple files concurrently
                for i, log_file in enumerate(self.log_files):
                    if entries_generated >= target_entries:
                        break
                    
                    entry = self.generate_test_log_entry(entries_generated, i)
                    
                    with open(log_file, 'a') as f:
                        f.write(f"{entry}\n")
                    
                    entries_generated += 1
                
                # Small delay to control rate
                await asyncio.sleep(1.0 / self.high_volume_entries_per_second)
        
        # Run entry generation
        await generate_entries()
        
        # Wait for processing to complete
        await asyncio.sleep(5.0)
        
        test_end_time = time.time()
        test_duration = test_end_time - test_start_time
        
        # Calculate results
        processed_count = len(self.processed_entries) - initial_processed_count
        throughput = processed_count / test_duration
        
        # Get system performance during test
        integration_manager = self.components['integration_manager']
        performance_report = await integration_manager.generate_performance_report()
        
        results = {
            'test_name': 'High Volume Ingestion',
            'duration_seconds': test_duration,
            'entries_generated': entries_generated,
            'entries_processed': processed_count,
            'throughput_per_second': throughput,
            'processing_efficiency': processed_count / entries_generated if entries_generated > 0 else 0,
            'system_health_score': performance_report.system_health_score,
            'cpu_utilization': performance_report.cpu_utilization,
            'memory_utilization': performance_report.memory_utilization,
            'avg_processing_time': sum(self.processing_times) / len(self.processing_times) if self.processing_times else 0,
            'status': 'PASS' if throughput > 100 else 'FAIL'  # Expect at least 100 entries/sec
        }
        
        logger.info(f"High volume test completed: {throughput:.2f} entries/sec processed")
        return results
    
    async def stress_test_memory_pressure(self) -> Dict[str, Any]:
        """Test system under memory pressure conditions."""
        logger.info("Starting memory pressure stress test...")
        
        test_start_time = time.time()
        initial_memory = psutil.virtual_memory().percent
        
        # Generate large log entries to create memory pressure
        large_entries_count = 1000
        entries_generated = 0
        
        for i in range(large_entries_count):
            # Create very large log entries
            large_entry = self.generate_test_log_entry(i, 0, self.large_entry_size)
            
            log_file = self.log_files[i % len(self.log_files)]
            with open(log_file, 'a') as f:
                f.write(f"{large_entry}\n")
            
            entries_generated += 1
            
            # Check memory usage periodically
            if i % 100 == 0:
                current_memory = psutil.virtual_memory().percent
                if current_memory > 90:  # Stop if memory usage gets too high
                    logger.warning(f"Memory usage reached {current_memory}%, stopping generation")
                    break
        
        # Wait for processing
        await asyncio.sleep(10.0)
        
        test_end_time = time.time()
        test_duration = test_end_time - test_start_time
        final_memory = psutil.virtual_memory().percent
        
        # Get performance report
        integration_manager = self.components['integration_manager']
        performance_report = await integration_manager.generate_performance_report()
        
        # Check if memory optimization was triggered
        optimizer = self.components['optimizer']
        memory_stats = optimizer.memory_manager.get_memory_stats()
        
        results = {
            'test_name': 'Memory Pressure',
            'duration_seconds': test_duration,
            'large_entries_generated': entries_generated,
            'entry_size_bytes': self.large_entry_size,
            'initial_memory_percent': initial_memory,
            'final_memory_percent': final_memory,
            'memory_increase_percent': final_memory - initial_memory,
            'system_health_score': performance_report.system_health_score,
            'memory_optimization_triggered': memory_stats.get('last_gc', 0) > test_start_time,
            'status': 'PASS' if final_memory < 95 else 'FAIL'  # System should handle memory pressure
        }
        
        logger.info(f"Memory pressure test completed: {final_memory:.1f}% memory usage")
        return results
    
    async def stress_test_concurrent_sources(self) -> Dict[str, Any]:
        """Test system with many concurrent log sources."""
        logger.info("Starting concurrent sources stress test...")
        
        test_start_time = time.time()
        
        # Create additional log sources for this test
        additional_sources = 50
        additional_log_files = []
        
        for i in range(additional_sources):
            log_file = Path(self.temp_dir) / f"concurrent_test_log_{i}.log"
            log_file.write_text(f"Concurrent test log {i}\n")
            additional_log_files.append(str(log_file))
            
            # Add to file monitor
            source_config = LogSourceConfig(
                source_name=f"concurrent_source_{i}",
                path=str(log_file),
                source_type=LogSourceType.FILE,
                enabled=True,
                priority=LogEntryPriority.LOW
            )
            self.components['file_monitor'].add_log_source(source_config)
        
        # Write to all sources concurrently
        async def write_to_sources():
            tasks = []
            
            async def write_to_source(log_file, source_id):
                for i in range(100):  # 100 entries per source
                    entry = self.generate_test_log_entry(i, source_id)
                    with open(log_file, 'a') as f:
                        f.write(f"{entry}\n")
                    await asyncio.sleep(0.01)  # Small delay
            
            # Create tasks for all sources
            all_sources = self.log_files + additional_log_files
            for i, log_file in enumerate(all_sources):
                task = asyncio.create_task(write_to_source(log_file, i))
                tasks.append(task)
            
            # Wait for all tasks to complete
            await asyncio.gather(*tasks)
        
        # Execute concurrent writes
        await write_to_sources()
        
        # Wait for processing
        await asyncio.sleep(10.0)
        
        test_end_time = time.time()
        test_duration = test_end_time - test_start_time
        
        # Get monitoring status
        file_monitor = self.components['file_monitor']
        monitoring_status = file_monitor.get_monitoring_status()
        
        # Get performance report
        integration_manager = self.components['integration_manager']
        performance_report = await integration_manager.generate_performance_report()
        
        total_sources = len(self.log_files) + additional_sources
        
        results = {
            'test_name': 'Concurrent Sources',
            'duration_seconds': test_duration,
            'total_sources': total_sources,
            'active_sources': monitoring_status['active_sources'],
            'error_sources': monitoring_status['error_sources'],
            'entries_per_source': 100,
            'expected_total_entries': total_sources * 100,
            'system_health_score': performance_report.system_health_score,
            'file_handle_utilization': file_monitor.get_optimization_stats()['file_handles']['handle_utilization'],
            'status': 'PASS' if monitoring_status['active_sources'] >= total_sources * 0.9 else 'FAIL'
        }
        
        logger.info(f"Concurrent sources test completed: {monitoring_status['active_sources']}/{total_sources} sources active")
        return results
    
    async def stress_test_error_recovery(self) -> Dict[str, Any]:
        """Test system error recovery under stress conditions."""
        logger.info("Starting error recovery stress test...")
        
        test_start_time = time.time()
        
        # Create error conditions
        error_count = 0
        recovery_count = 0
        
        # Set up error-prone batch processor
        original_processor = self.components['ingestion_queue']._batch_processor
        
        async def error_prone_processor(batch: List[LogEntry]):
            nonlocal error_count, recovery_count
            
            # Randomly fail some batches
            if random.random() < 0.3:  # 30% failure rate
                error_count += 1
                raise Exception(f"Simulated processing error {error_count}")
            else:
                recovery_count += 1
                # Process normally
                self.processed_entries.extend(batch)
        
        self.components['ingestion_queue'].set_batch_processor(error_prone_processor)
        
        # Generate entries that will trigger errors
        entries_generated = 0
        for i in range(500):
            entry = self.generate_test_log_entry(i, 0)
            log_file = self.log_files[i % len(self.log_files)]
            
            with open(log_file, 'a') as f:
                f.write(f"{entry}\n")
            
            entries_generated += 1
        
        # Wait for processing and recovery
        await asyncio.sleep(15.0)
        
        # Restore original processor
        self.components['ingestion_queue'].set_batch_processor(original_processor)
        
        test_end_time = time.time()
        test_duration = test_end_time - test_start_time
        
        # Get queue statistics
        queue_stats = await self.components['ingestion_queue'].get_queue_stats()
        
        results = {
            'test_name': 'Error Recovery',
            'duration_seconds': test_duration,
            'entries_generated': entries_generated,
            'simulated_errors': error_count,
            'successful_recoveries': recovery_count,
            'total_queue_errors': queue_stats.total_errors,
            'retry_attempts': queue_stats.retry_count,
            'error_rate': queue_stats.error_rate,
            'recovery_rate': recovery_count / (error_count + recovery_count) if (error_count + recovery_count) > 0 else 0,
            'status': 'PASS' if recovery_count > error_count else 'FAIL'
        }
        
        logger.info(f"Error recovery test completed: {recovery_count} recoveries, {error_count} errors")
        return results
    
    async def stress_test_adaptive_performance(self) -> Dict[str, Any]:
        """Test adaptive performance optimization under varying loads."""
        logger.info("Starting adaptive performance stress test...")
        
        test_start_time = time.time()
        
        # Record initial batch size
        queue = self.components['ingestion_queue']
        initial_batch_size = queue._optimal_batch_size
        batch_size_history = [initial_batch_size]
        
        # Phase 1: Low load
        logger.info("Phase 1: Low load")
        for i in range(50):
            entry = self.generate_test_log_entry(i, 0)
            with open(self.log_files[0], 'a') as f:
                f.write(f"{entry}\n")
            await asyncio.sleep(0.1)  # Slow rate
        
        await asyncio.sleep(3.0)
        batch_size_history.append(queue._optimal_batch_size)
        
        # Phase 2: High load
        logger.info("Phase 2: High load")
        for i in range(500):
            entry = self.generate_test_log_entry(i + 50, 0)
            with open(self.log_files[0], 'a') as f:
                f.write(f"{entry}\n")
            if i % 10 == 0:
                await asyncio.sleep(0.001)  # Very fast rate
        
        await asyncio.sleep(5.0)
        batch_size_history.append(queue._optimal_batch_size)
        
        # Phase 3: Variable load
        logger.info("Phase 3: Variable load")
        for i in range(200):
            entry = self.generate_test_log_entry(i + 550, 0)
            with open(self.log_files[0], 'a') as f:
                f.write(f"{entry}\n")
            
            # Variable delay
            delay = random.uniform(0.001, 0.1)
            await asyncio.sleep(delay)
        
        await asyncio.sleep(3.0)
        final_batch_size = queue._optimal_batch_size
        batch_size_history.append(final_batch_size)
        
        test_end_time = time.time()
        test_duration = test_end_time - test_start_time
        
        # Get optimization stats
        optimization_stats = queue.get_optimization_stats()
        
        # Check if batch size adapted
        batch_size_changed = len(set(batch_size_history)) > 1
        adaptation_range = max(batch_size_history) - min(batch_size_history)
        
        results = {
            'test_name': 'Adaptive Performance',
            'duration_seconds': test_duration,
            'initial_batch_size': initial_batch_size,
            'final_batch_size': final_batch_size,
            'batch_size_history': batch_size_history,
            'batch_size_adapted': batch_size_changed,
            'adaptation_range': adaptation_range,
            'adaptive_batching_enabled': optimization_stats['adaptive_batching']['enabled'],
            'performance_history_size': optimization_stats['adaptive_batching']['performance_history_size'],
            'status': 'PASS' if batch_size_changed else 'FAIL'
        }
        
        logger.info(f"Adaptive performance test completed: batch size {initial_batch_size} -> {final_batch_size}")
        return results
    
    async def run_comprehensive_stress_test(self) -> Dict[str, Any]:
        """Run all stress tests and compile results."""
        logger.info("Starting comprehensive stress test suite...")
        
        try:
            await self.setup_stress_test_environment()
            
            # Run all stress tests
            stress_tests = [
                self.stress_test_high_volume_ingestion(),
                self.stress_test_memory_pressure(),
                self.stress_test_concurrent_sources(),
                self.stress_test_error_recovery(),
                self.stress_test_adaptive_performance()
            ]
            
            test_results = await asyncio.gather(*stress_tests, return_exceptions=True)
            
            # Process results
            compiled_results = {
                'test_suite': 'Comprehensive Stress Test',
                'start_time': datetime.now(timezone.utc).isoformat(),
                'total_tests': len(stress_tests),
                'passed_tests': 0,
                'failed_tests': 0,
                'test_results': {},
                'overall_status': 'PASS',
                'system_summary': {}
            }
            
            for i, result in enumerate(test_results):
                if isinstance(result, Exception):
                    logger.error(f"Stress test {i} failed with exception: {result}")
                    compiled_results['failed_tests'] += 1
                    compiled_results['test_results'][f'test_{i}'] = {
                        'status': 'ERROR',
                        'error': str(result)
                    }
                else:
                    compiled_results['test_results'][result['test_name']] = result
                    if result['status'] == 'PASS':
                        compiled_results['passed_tests'] += 1
                    else:
                        compiled_results['failed_tests'] += 1
            
            # Generate system summary
            integration_manager = self.components['integration_manager']
            final_performance_report = await integration_manager.generate_performance_report()
            
            compiled_results['system_summary'] = {
                'final_health_score': final_performance_report.system_health_score,
                'final_performance_grade': final_performance_report.performance_grade,
                'total_entries_processed': len(self.processed_entries),
                'avg_cpu_utilization': final_performance_report.cpu_utilization,
                'avg_memory_utilization': final_performance_report.memory_utilization,
                'system_recommendations': final_performance_report.recommendations
            }
            
            # Determine overall status
            if compiled_results['failed_tests'] > 0:
                compiled_results['overall_status'] = 'FAIL'
            
            return compiled_results
        
        finally:
            await self.cleanup_stress_test_environment()
    
    def generate_stress_test_report(self, results: Dict[str, Any]) -> str:
        """Generate a comprehensive stress test report."""
        report = []
        report.append("=" * 100)
        report.append("REAL-TIME LOG DETECTION SYSTEM - COMPREHENSIVE STRESS TEST REPORT")
        report.append("=" * 100)
        report.append(f"Test Suite: {results['test_suite']}")
        report.append(f"Start Time: {results['start_time']}")
        report.append(f"Overall Status: {results['overall_status']}")
        report.append(f"Tests Passed: {results['passed_tests']}/{results['total_tests']}")
        report.append("")
        
        # Individual test results
        report.append("INDIVIDUAL TEST RESULTS")
        report.append("-" * 50)
        
        for test_name, test_result in results['test_results'].items():
            if test_result.get('status') == 'ERROR':
                report.append(f"❌ {test_name}: ERROR")
                report.append(f"   Error: {test_result['error']}")
            else:
                status_symbol = "✅" if test_result['status'] == 'PASS' else "❌"
                report.append(f"{status_symbol} {test_result['test_name']}: {test_result['status']}")
                
                # Add key metrics for each test
                if 'throughput_per_second' in test_result:
                    report.append(f"   Throughput: {test_result['throughput_per_second']:.2f} entries/sec")
                if 'duration_seconds' in test_result:
                    report.append(f"   Duration: {test_result['duration_seconds']:.2f} seconds")
                if 'system_health_score' in test_result:
                    report.append(f"   Health Score: {test_result['system_health_score']:.2f}")
        
        report.append("")
        
        # System summary
        report.append("SYSTEM PERFORMANCE SUMMARY")
        report.append("-" * 50)
        summary = results['system_summary']
        report.append(f"Final Health Score: {summary['final_health_score']:.2f}")
        report.append(f"Performance Grade: {summary['final_performance_grade']}")
        report.append(f"Total Entries Processed: {summary['total_entries_processed']:,}")
        report.append(f"Average CPU Utilization: {summary['avg_cpu_utilization']:.1%}")
        report.append(f"Average Memory Utilization: {summary['avg_memory_utilization']:.1%}")
        
        if summary['system_recommendations']:
            report.append("\nSystem Recommendations:")
            for rec in summary['system_recommendations']:
                report.append(f"  • {rec}")
        
        report.append("")
        report.append("=" * 100)
        
        if results['overall_status'] == 'PASS':
            report.append("🎉 ALL STRESS TESTS PASSED!")
            report.append("The system demonstrates excellent performance under stress conditions.")
        else:
            report.append("⚠️  SOME STRESS TESTS FAILED")
            report.append("The system may need optimization for high-load scenarios.")
        
        report.append("=" * 100)
        
        return "\n".join(report)


async def main():
    """Main stress testing function."""
    stress_tester = StressTestRunner()
    
    try:
        # Run comprehensive stress tests
        logger.info("Starting comprehensive stress test suite...")
        results = await stress_tester.run_comprehensive_stress_test()
        
        # Generate and display report
        report = stress_tester.generate_stress_test_report(results)
        print(report)
        
        # Save results to files
        results_file = Path("stress_test_results.json")
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        report_file = Path("stress_test_report.txt")
        with open(report_file, 'w') as f:
            f.write(report)
        
        logger.info(f"Stress test results saved to {results_file}")
        logger.info(f"Stress test report saved to {report_file}")
        
        # Return exit code based on test results
        return 0 if results['overall_status'] == 'PASS' else 1
    
    except Exception as e:
        logger.error(f"Stress testing failed with error: {e}")
        return 1


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)