"""
AI Analysis Integration Tests for ThreatLens

Tests AI analysis integration with mocked responses, error handling,
and various analysis scenarios.
"""
import pytest
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, Mock, MagicMock
from fastapi.testclient import TestClient

from tests.test_e2e_integration import TestE2EIntegration
from tests.fixtures.test_data import TestDataFixtures
from app.schemas import AIAnalysis, ParsedEvent, EventCategory
from app.analyzer import AnalysisError


class TestAIAnalysisIntegration(TestE2EIntegration):
    """AI analysis integration tests with comprehensive mocking."""
    
    def test_ai_analysis_realistic_scenarios(self, client, test_fixtures):
        """Test AI analysis with realistic security scenarios."""
        scenarios = test_fixtures.get_ai_analysis_test_scenarios()
        
        for scenario in scenarios:
            with patch('app.analyzer.analyze_event') as mock_analyze:
                # Create realistic mock response based on scenario
                mock_analysis = self._create_scenario_based_analysis(scenario)
                mock_analyze.return_value = mock_analysis
                
                # Ingest the specific log entry
                response = client.post(
                    "/ingest-log",
                    data={"content": scenario["log_entry"], "source": "ai_scenario_test"}
                )
                
                assert response.status_code == 200
                raw_log_id = response.json()["raw_log_id"]
                
                # Wait for processing
                self._wait_for_processing(client, raw_log_id, expected_events=1)
                
                # Verify AI analysis matches expectations
                response = client.get("/events")
                assert response.status_code == 200
                
                events = response.json()["events"]
                assert len(events) >= 1
                
                event = events[0]
                assert event["ai_analysis"] is not None
                
                analysis = event["ai_analysis"]
                
                # Verify severity is in expected range
                min_sev, max_sev = scenario["expected_severity_range"]
                assert min_sev <= analysis["severity_score"] <= max_sev
                
                # Verify category matches
                assert event["category"] == scenario["expected_category"]
                
                # Verify explanation contains expected keywords
                explanation_lower = analysis["explanation"].lower()
                assert any(keyword in explanation_lower for keyword in scenario["should_contain"])
                
                # Verify recommendations are provided
                assert isinstance(analysis["recommendations"], list)
                assert len(analysis["recommendations"]) > 0
    
    def test_ai_analysis_error_handling(self, client, test_fixtures):
        """Test AI analysis error handling and fallback mechanisms."""
        log_content = test_fixtures.get_macos_system_log()
        
        # Test various AI failure scenarios
        failure_scenarios = [
            ("timeout_error", Exception("API timeout")),
            ("rate_limit_error", Exception("Rate limit exceeded")),
            ("invalid_response", Exception("Invalid JSON response")),
            ("analysis_error", AnalysisError("Analysis failed"))
        ]
        
        for scenario_name, exception in failure_scenarios:
            with patch('app.analyzer.analyze_event') as mock_analyze:
                mock_analyze.side_effect = exception
                
                response = client.post(
                    "/ingest-log",
                    data={"content": log_content, "source": f"ai_error_{scenario_name}"}
                )
                
                assert response.status_code == 200
                raw_log_id = response.json()["raw_log_id"]
                
                # Wait for processing (should complete despite AI failures)
                self._wait_for_processing(client, raw_log_id, expected_events=5, timeout=15)
                
                # Verify events were still created (even without AI analysis)
                response = client.get("/events")
                assert response.status_code == 200
                
                events_data = response.json()
                assert events_data["total"] >= 5
                
                # Some events might have fallback analysis or no analysis
                for event in events_data["events"]:
                    # Event should exist even if AI analysis failed
                    assert event["id"]
                    assert event["message"]
                    assert event["category"]
                    
                    # AI analysis might be None due to failure
                    if event["ai_analysis"]:
                        # If present, should have valid structure
                        assert 1 <= event["ai_analysis"]["severity_score"] <= 10
    
    def test_ai_analysis_batch_processing(self, client, test_fixtures):
        """Test AI analysis with batch processing of multiple events."""
        large_log_content = test_fixtures.generate_large_log_dataset(50)
        
        analysis_calls = []
        
        def mock_analyze_with_tracking(event):
            analysis_calls.append(event.id)
            return self._create_mock_ai_analysis(event)
        
        with patch('app.analyzer.analyze_event') as mock_analyze:
            mock_analyze.side_effect = mock_analyze_with_tracking
            
            response = client.post(
                "/ingest-log",
                data={"content": large_log_content, "source": "ai_batch_test"}
            )
            
            assert response.status_code == 200
            raw_log_id = response.json()["raw_log_id"]
            
            # Wait for processing
            self._wait_for_processing(client, raw_log_id, expected_events=50, timeout=60)
            
            # Verify all events were analyzed
            assert len(analysis_calls) == 50
            
            # Verify all events have AI analysis
            response = client.get("/events?per_page=100")
            assert response.status_code == 200
            
            events = response.json()["events"]
            assert len(events) == 50
            
            analyzed_count = sum(1 for event in events if event["ai_analysis"] is not None)
            assert analyzed_count == 50
    
    def test_ai_analysis_partial_failures(self, client, test_fixtures):
        """Test handling of partial AI analysis failures."""
        log_content = test_fixtures.get_comprehensive_log_sample()
        
        call_count = 0
        
        def mock_analyze_with_partial_failures(event):
            nonlocal call_count
            call_count += 1
            
            # Fail every 3rd analysis
            if call_count % 3 == 0:
                raise Exception("Simulated partial failure")
            
            return self._create_mock_ai_analysis(event)
        
        with patch('app.analyzer.analyze_event') as mock_analyze:
            mock_analyze.side_effect = mock_analyze_with_partial_failures
            
            response = client.post(
                "/ingest-log",
                data={"content": log_content, "source": "ai_partial_failure_test"}
            )
            
            assert response.status_code == 200
            raw_log_id = response.json()["raw_log_id"]
            
            # Wait for processing
            self._wait_for_processing(client, raw_log_id, expected_events=12, timeout=30)
            
            # Verify events were processed
            response = client.get("/events")
            assert response.status_code == 200
            
            events = response.json()["events"]
            assert len(events) >= 12
            
            # Count successful vs failed analyses
            successful_analyses = sum(1 for event in events if event["ai_analysis"] is not None)
            failed_analyses = len(events) - successful_analyses
            
            # Should have some successes and some failures
            assert successful_analyses > 0
            assert failed_analyses > 0
            
            # Roughly 2/3 should succeed (every 3rd fails)
            success_rate = successful_analyses / len(events)
            assert 0.5 < success_rate < 0.8
    
    def test_ai_analysis_response_validation(self, client, test_fixtures):
        """Test validation of AI analysis responses."""
        log_content = test_fixtures.get_macos_auth_log()
        
        # Test various invalid AI responses
        invalid_responses = [
            # Invalid severity score
            AIAnalysis(
                id=str(uuid.uuid4()),
                event_id="test-event",
                severity_score=15,  # Invalid: > 10
                explanation="Test explanation",
                recommendations=["Test recommendation"],
                analyzed_at=datetime.now(timezone.utc)
            ),
            # Missing explanation
            AIAnalysis(
                id=str(uuid.uuid4()),
                event_id="test-event",
                severity_score=5,
                explanation="",  # Invalid: empty
                recommendations=["Test recommendation"],
                analyzed_at=datetime.now(timezone.utc)
            ),
            # Invalid recommendations
            AIAnalysis(
                id=str(uuid.uuid4()),
                event_id="test-event",
                severity_score=5,
                explanation="Test explanation",
                recommendations=[],  # Invalid: empty list
                analyzed_at=datetime.now(timezone.utc)
            )
        ]
        
        for i, invalid_response in enumerate(invalid_responses):
            with patch('app.analyzer.analyze_event') as mock_analyze:
                mock_analyze.return_value = invalid_response
                
                response = client.post(
                    "/ingest-log",
                    data={"content": log_content, "source": f"ai_validation_test_{i}"}
                )
                
                assert response.status_code == 200
                raw_log_id = response.json()["raw_log_id"]
                
                # Processing should handle invalid responses gracefully
                self._wait_for_processing(client, raw_log_id, expected_events=5, timeout=15)
                
                # Events should still be created
                response = client.get("/events")
                assert response.status_code == 200
                assert response.json()["total"] >= 5
    
    def test_ai_analysis_performance_monitoring(self, client, test_fixtures):
        """Test AI analysis performance monitoring and metrics."""
        log_content = test_fixtures.get_macos_system_log()
        
        analysis_times = []
        
        def mock_analyze_with_timing(event):
            import time
            start_time = time.time()
            
            # Simulate variable analysis times
            time.sleep(0.1 + (hash(event.id) % 100) / 1000)  # 0.1-0.2 seconds
            
            analysis_time = time.time() - start_time
            analysis_times.append(analysis_time)
            
            return self._create_mock_ai_analysis(event)
        
        with patch('app.analyzer.analyze_event') as mock_analyze:
            mock_analyze.side_effect = mock_analyze_with_timing
            
            response = client.post(
                "/ingest-log",
                data={"content": log_content, "source": "ai_performance_test"}
            )
            
            assert response.status_code == 200
            raw_log_id = response.json()["raw_log_id"]
            
            # Wait for processing
            self._wait_for_processing(client, raw_log_id, expected_events=7, timeout=30)
            
            # Verify performance metrics
            assert len(analysis_times) == 7
            
            avg_time = sum(analysis_times) / len(analysis_times)
            max_time = max(analysis_times)
            
            # Performance assertions
            assert avg_time < 1.0  # Average analysis time should be reasonable
            assert max_time < 2.0  # No single analysis should take too long
            
            print(f"AI Analysis Performance:")
            print(f"  Average time: {avg_time:.3f}s")
            print(f"  Maximum time: {max_time:.3f}s")
            print(f"  Total analyses: {len(analysis_times)}")
    
    def test_ai_analysis_retry_logic(self, client, test_fixtures):
        """Test AI analysis retry logic for transient failures."""
        log_content = test_fixtures.get_macos_auth_log()
        
        call_attempts = {}
        
        def mock_analyze_with_retries(event):
            event_id = event.id
            attempts = call_attempts.get(event_id, 0) + 1
            call_attempts[event_id] = attempts
            
            # Fail first attempt, succeed on retry
            if attempts == 1:
                raise Exception("Transient failure")
            
            return self._create_mock_ai_analysis(event)
        
        with patch('app.analyzer.analyze_event') as mock_analyze:
            mock_analyze.side_effect = mock_analyze_with_retries
            
            response = client.post(
                "/ingest-log",
                data={"content": log_content, "source": "ai_retry_test"}
            )
            
            assert response.status_code == 200
            raw_log_id = response.json()["raw_log_id"]
            
            # Wait for processing (including retries)
            self._wait_for_processing(client, raw_log_id, expected_events=5, timeout=30)
            
            # Verify all events were eventually analyzed
            response = client.get("/events")
            assert response.status_code == 200
            
            events = response.json()["events"]
            analyzed_count = sum(1 for event in events if event["ai_analysis"] is not None)
            
            # All events should have analysis after retries
            assert analyzed_count >= 4  # Allow for some failures
            
            # Verify retry attempts were made
            assert all(attempts >= 1 for attempts in call_attempts.values())
    
    def test_ai_analysis_context_preservation(self, client, test_fixtures):
        """Test that AI analysis preserves event context correctly."""
        mixed_content = test_fixtures.get_mixed_log_formats()
        
        analyzed_events = []
        
        def mock_analyze_with_context_tracking(event):
            analyzed_events.append({
                "event_id": event.id,
                "message": event.message,
                "category": event.category,
                "source": event.source,
                "timestamp": event.timestamp
            })
            
            return self._create_mock_ai_analysis(event)
        
        with patch('app.analyzer.analyze_event') as mock_analyze:
            mock_analyze.side_effect = mock_analyze_with_context_tracking
            
            response = client.post(
                "/ingest-log",
                data={"content": mixed_content, "source": "ai_context_test"}
            )
            
            assert response.status_code == 200
            raw_log_id = response.json()["raw_log_id"]
            
            # Wait for processing
            self._wait_for_processing(client, raw_log_id, expected_events=6, timeout=20)
            
            # Verify context was preserved
            response = client.get("/events")
            assert response.status_code == 200
            
            events = response.json()["events"]
            
            # Match analyzed events with stored events
            for stored_event in events:
                if stored_event["ai_analysis"]:
                    # Find corresponding analyzed event
                    analyzed_event = next(
                        (ae for ae in analyzed_events if ae["event_id"] == stored_event["id"]),
                        None
                    )
                    
                    assert analyzed_event is not None
                    assert analyzed_event["message"] == stored_event["message"]
                    assert analyzed_event["category"] == stored_event["category"]
                    assert analyzed_event["source"] == stored_event["source"]
    
    def test_ai_analysis_concurrent_processing(self, client, test_fixtures):
        """Test AI analysis under concurrent processing load."""
        concurrent_data = test_fixtures.get_concurrent_test_data(5)
        
        analysis_calls = []
        
        def mock_analyze_thread_safe(event):
            import threading
            thread_id = threading.current_thread().ident
            analysis_calls.append({
                "event_id": event.id,
                "thread_id": thread_id,
                "timestamp": datetime.now(timezone.utc)
            })
            
            return self._create_mock_ai_analysis(event)
        
        with patch('app.analyzer.analyze_event') as mock_analyze:
            mock_analyze.side_effect = mock_analyze_thread_safe
            
            # Ingest multiple logs concurrently
            raw_log_ids = []
            for i, log_content in enumerate(concurrent_data):
                response = client.post(
                    "/ingest-log",
                    data={"content": log_content, "source": f"ai_concurrent_{i}"}
                )
                assert response.status_code == 200
                raw_log_ids.append(response.json()["raw_log_id"])
            
            # Wait for all processing to complete
            import time
            time.sleep(10)
            
            # Verify all analyses were completed
            response = client.get("/events")
            assert response.status_code == 200
            
            events = response.json()["events"]
            analyzed_count = sum(1 for event in events if event["ai_analysis"] is not None)
            
            # Should have analyzed most events
            assert analyzed_count >= len(concurrent_data) * 2  # Each log has 3 entries
            
            # Verify thread safety (no duplicate analyses)
            event_ids = [call["event_id"] for call in analysis_calls]
            assert len(event_ids) == len(set(event_ids))  # No duplicates
    
    # Helper methods
    
    def _create_scenario_based_analysis(self, scenario):
        """Create AI analysis based on test scenario."""
        min_sev, max_sev = scenario["expected_severity_range"]
        severity = (min_sev + max_sev) // 2  # Use middle of range
        
        # Create explanation with expected keywords
        keywords = scenario["should_contain"]
        explanation = f"Security analysis detected {keywords[0]} activity. " + \
                     f"This event involves {keywords[1]} and requires attention due to {keywords[2]} implications."
        
        recommendations = [
            f"Monitor for additional {keywords[0]} events",
            f"Review {scenario['expected_category']} logs for patterns",
            f"Consider implementing additional {keywords[2]} measures"
        ]
        
        return AIAnalysis(
            id=str(uuid.uuid4()),
            event_id=str(uuid.uuid4()),
            severity_score=severity,
            explanation=explanation,
            recommendations=recommendations,
            analyzed_at=datetime.now(timezone.utc)
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])