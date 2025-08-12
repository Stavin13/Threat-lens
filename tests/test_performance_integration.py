"""
Performance Integration Tests for ThreatLens

Tests system performance under various load conditions including
large log files, concurrent processing, and stress testing.
"""
import pytest
import time
import threading
import queue
import psutil
import os
from datetime import datetime, timezone
from unittest.mock import patch
from fastapi.testclient import TestClient

from tests.test_e2e_integration import TestE2EIntegration
from tests.fixtures.test_data import TestDataFixtures


class TestPerformanceIntegration(TestE2EIntegration):
    """Performance-focused integration tests."""
    
    def test_large_file_processing_performance(self, client, test_fixtures):
        """Test performance with large log files."""
        scenarios = test_fixtures.get_performance_test_scenarios()
        
        for scenario_name, config in scenarios.items():
            with patch('app.analyzer.analyze_event') as mock_analyze:
                mock_analyze.side_effect = self._create_mock_ai_analysis
                
                # Generate test data
                log_content = test_fixtures.generate_large_log_dataset(config["entries"])
                
                # Measure memory before processing
                process = psutil.Process(os.getpid())
                memory_before = process.memory_info().rss / 1024 / 1024  # MB
                
                # Measure ingestion time
                start_time = time.time()
                
                response = client.post(
                    "/ingest-log",
                    data={"content": log_content, "source": f"perf_test_{scenario_name}"}
                )
                
                ingestion_time = time.time() - start_time
                
                assert response.status_code == 200
                assert ingestion_time < config["expected_ingestion_time"]
                
                raw_log_id = response.json()["raw_log_id"]
                
                # Measure processing time
                processing_start = time.time()
                self._wait_for_processing(
                    client, 
                    raw_log_id, 
                    expected_events=config["entries"],
                    timeout=config["expected_processing_time"] + 30
                )
                processing_time = time.time() - processing_start
                
                # Measure memory after processing
                memory_after = process.memory_info().rss / 1024 / 1024  # MB
                memory_increase = memory_after - memory_before
                
                # Performance assertions
                assert processing_time < config["expected_processing_time"]
                assert memory_increase < 500  # Should not increase by more than 500MB
                
                # Verify all events were processed
                response = client.get("/events")
                assert response.status_code == 200
                assert response.json()["total"] >= config["entries"]
                
                print(f"Scenario {scenario_name}:")
                print(f"  Entries: {config['entries']}")
                print(f"  Ingestion time: {ingestion_time:.2f}s")
                print(f"  Processing time: {processing_time:.2f}s")
                print(f"  Memory increase: {memory_increase:.2f}MB")
    
    def test_concurrent_processing_performance(self, client, test_fixtures):
        """Test performance under concurrent load."""
        num_threads = 10
        concurrent_data = test_fixtures.get_concurrent_test_data(num_threads)
        
        results = queue.Queue()
        
        def process_log(thread_id, log_content):
            with patch('app.analyzer.analyze_event') as mock_analyze:
                mock_analyze.side_effect = self._create_mock_ai_analysis
                
                start_time = time.time()
                
                response = client.post(
                    "/ingest-log",
                    data={"content": log_content, "source": f"concurrent_{thread_id}"}
                )
                
                processing_time = time.time() - start_time
                
                results.put({
                    "thread_id": thread_id,
                    "status_code": response.status_code,
                    "processing_time": processing_time,
                    "raw_log_id": response.json().get("raw_log_id") if response.status_code == 200 else None
                })
        
        # Start concurrent processing
        threads = []
        overall_start = time.time()
        
        for i, log_content in enumerate(concurrent_data):
            thread = threading.Thread(target=process_log, args=(i, log_content))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        overall_time = time.time() - overall_start
        
        # Collect results
        thread_results = []
        while not results.empty():
            thread_results.append(results.get())
        
        # Performance assertions
        assert len(thread_results) == num_threads
        assert all(result["status_code"] == 200 for result in thread_results)
        assert overall_time < 30  # Should complete within 30 seconds
        
        # Check individual thread performance
        avg_thread_time = sum(result["processing_time"] for result in thread_results) / num_threads
        assert avg_thread_time < 5  # Average thread should complete quickly
        
        # Wait for background processing
        time.sleep(10)
        
        # Verify all events were processed
        response = client.get("/events")
        assert response.status_code == 200
        assert response.json()["total"] >= num_threads * 3  # Each log has 3 entries
        
        print(f"Concurrent processing results:")
        print(f"  Threads: {num_threads}")
        print(f"  Overall time: {overall_time:.2f}s")
        print(f"  Average thread time: {avg_thread_time:.2f}s")
        print(f"  Max thread time: {max(result['processing_time'] for result in thread_results):.2f}s")
    
    def test_api_response_time_performance(self, client, test_fixtures):
        """Test API response time performance."""
        # Setup test data
        log_content = test_fixtures.get_comprehensive_log_sample()
        
        with patch('app.analyzer.analyze_event') as mock_analyze:
            mock_analyze.side_effect = self._create_mock_ai_analysis
            
            # Ingest data
            response = client.post(
                "/ingest-log",
                data={"content": log_content, "source": "api_perf_test"}
            )
            assert response.status_code == 200
            
            raw_log_id = response.json()["raw_log_id"]
            self._wait_for_processing(client, raw_log_id, expected_events=12)
        
        # Test various API endpoint response times
        endpoints_to_test = [
            ("/events", "GET", None),
            ("/events?page=1&per_page=10", "GET", None),
            ("/events?category=auth", "GET", None),
            ("/events?min_severity=5", "GET", None),
            ("/health", "GET", None),
            ("/stats", "GET", None)
        ]
        
        response_times = {}
        
        for endpoint, method, data in endpoints_to_test:
            times = []
            
            # Test each endpoint 10 times
            for _ in range(10):
                start_time = time.time()
                
                if method == "GET":
                    response = client.get(endpoint)
                elif method == "POST":
                    response = client.post(endpoint, json=data)
                
                response_time = time.time() - start_time
                times.append(response_time)
                
                assert response.status_code == 200
            
            avg_time = sum(times) / len(times)
            max_time = max(times)
            
            response_times[endpoint] = {
                "average": avg_time,
                "maximum": max_time
            }
            
            # Performance assertions
            assert avg_time < 0.5  # Average response time should be under 500ms
            assert max_time < 2.0  # Maximum response time should be under 2s
        
        print("API Response Time Performance:")
        for endpoint, times in response_times.items():
            print(f"  {endpoint}:")
            print(f"    Average: {times['average']*1000:.2f}ms")
            print(f"    Maximum: {times['maximum']*1000:.2f}ms")
    
    def test_database_query_performance(self, client, test_fixtures):
        """Test database query performance with large datasets."""
        # Generate large dataset
        large_log_content = test_fixtures.generate_large_log_dataset(500)
        
        with patch('app.analyzer.analyze_event') as mock_analyze:
            mock_analyze.side_effect = self._create_mock_ai_analysis
            
            # Ingest large dataset
            response = client.post(
                "/ingest-log",
                data={"content": large_log_content, "source": "db_perf_test"}
            )
            assert response.status_code == 200
            
            raw_log_id = response.json()["raw_log_id"]
            self._wait_for_processing(client, raw_log_id, expected_events=500, timeout=120)
        
        # Test various query patterns
        query_tests = [
            ("/events?page=1&per_page=50", "Pagination"),
            ("/events?category=auth", "Category filter"),
            ("/events?min_severity=7", "Severity filter"),
            ("/events?sort_by=severity&sort_order=desc", "Sorting"),
            ("/events?start_date=2024-01-15T00:00:00Z", "Date filter"),
            ("/events?source=MacBook-Pro", "Source filter")
        ]
        
        for endpoint, description in query_tests:
            start_time = time.time()
            response = client.get(endpoint)
            query_time = time.time() - start_time
            
            assert response.status_code == 200
            assert query_time < 2.0  # Queries should complete within 2 seconds
            
            print(f"{description}: {query_time*1000:.2f}ms")
    
    def test_memory_usage_stability(self, client, test_fixtures):
        """Test memory usage stability during extended processing."""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Process multiple batches to test memory stability
        for batch in range(5):
            log_content = test_fixtures.generate_large_log_dataset(100)
            
            with patch('app.analyzer.analyze_event') as mock_analyze:
                mock_analyze.side_effect = self._create_mock_ai_analysis
                
                response = client.post(
                    "/ingest-log",
                    data={"content": log_content, "source": f"memory_test_batch_{batch}"}
                )
                assert response.status_code == 200
                
                raw_log_id = response.json()["raw_log_id"]
                self._wait_for_processing(client, raw_log_id, expected_events=100)
            
            # Check memory after each batch
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = current_memory - initial_memory
            
            # Memory should not grow excessively
            assert memory_increase < 1000  # Should not increase by more than 1GB
            
            print(f"Batch {batch + 1}: Memory usage {current_memory:.2f}MB (+{memory_increase:.2f}MB)")
        
        # Final memory check
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_increase = final_memory - initial_memory
        
        print(f"Total memory increase: {total_increase:.2f}MB")
        assert total_increase < 1500  # Total increase should be reasonable
    
    def test_stress_testing_limits(self, client, test_fixtures):
        """Test system behavior under stress conditions."""
        # Test with very large single log entry
        stress_scenarios = test_fixtures.get_error_simulation_data()
        
        for scenario_name, log_content in stress_scenarios.items():
            if scenario_name == "memory_pressure":
                # Test memory pressure scenario
                start_time = time.time()
                
                response = client.post(
                    "/ingest-log",
                    data={"content": log_content, "source": f"stress_{scenario_name}"}
                )
                
                processing_time = time.time() - start_time
                
                # Should either succeed or fail gracefully
                assert response.status_code in [200, 400, 413]  # 413 = Payload Too Large
                assert processing_time < 30  # Should not hang
                
                # System should remain responsive
                health_response = client.get("/health")
                assert health_response.status_code == 200
    
    def test_throughput_measurement(self, client, test_fixtures):
        """Measure system throughput under sustained load."""
        # Test sustained throughput over time
        duration_seconds = 30
        batch_size = 50
        
        start_time = time.time()
        total_events = 0
        batches_processed = 0
        
        with patch('app.analyzer.analyze_event') as mock_analyze:
            mock_analyze.side_effect = self._create_mock_ai_analysis
            
            while time.time() - start_time < duration_seconds:
                log_content = test_fixtures.generate_large_log_dataset(batch_size)
                
                response = client.post(
                    "/ingest-log",
                    data={"content": log_content, "source": f"throughput_batch_{batches_processed}"}
                )
                
                if response.status_code == 200:
                    total_events += batch_size
                    batches_processed += 1
                
                # Small delay to prevent overwhelming the system
                time.sleep(0.1)
        
        actual_duration = time.time() - start_time
        
        # Wait for processing to complete
        time.sleep(10)
        
        # Calculate throughput metrics
        events_per_second = total_events / actual_duration
        batches_per_second = batches_processed / actual_duration
        
        print(f"Throughput Test Results:")
        print(f"  Duration: {actual_duration:.2f}s")
        print(f"  Total events: {total_events}")
        print(f"  Batches processed: {batches_processed}")
        print(f"  Events per second: {events_per_second:.2f}")
        print(f"  Batches per second: {batches_per_second:.2f}")
        
        # Performance assertions
        assert events_per_second > 10  # Should process at least 10 events per second
        assert batches_per_second > 0.5  # Should process at least 0.5 batches per second
        
        # Verify system stability
        response = client.get("/health")
        assert response.status_code == 200
    
    def test_cleanup_and_resource_management(self, client, test_fixtures):
        """Test resource cleanup and management."""
        initial_stats = client.get("/stats").json()
        
        # Process several batches
        for i in range(3):
            log_content = test_fixtures.generate_large_log_dataset(100)
            
            with patch('app.analyzer.analyze_event') as mock_analyze:
                mock_analyze.side_effect = self._create_mock_ai_analysis
                
                response = client.post(
                    "/ingest-log",
                    data={"content": log_content, "source": f"cleanup_test_{i}"}
                )
                assert response.status_code == 200
                
                raw_log_id = response.json()["raw_log_id"]
                self._wait_for_processing(client, raw_log_id, expected_events=100)
        
        # Check final stats
        final_stats = client.get("/stats").json()
        
        # Verify data was processed
        assert final_stats["database"]["events_count"] > initial_stats["database"]["events_count"]
        
        # Test that system can handle additional load after processing
        response = client.get("/events?per_page=100")
        assert response.status_code == 200
        
        # System should remain healthy
        health_response = client.get("/health")
        assert health_response.status_code == 200
        assert health_response.json()["status"] in ["healthy", "degraded"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])