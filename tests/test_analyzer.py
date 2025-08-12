"""
Unit tests for the AI analyzer module.

Tests cover Groq API integration, rule-based fallback analysis,
error handling, and edge cases for the analyzer module.
"""
import pytest
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
from typing import List

from app.analyzer import (
    GroqAnalyzer,
    analyze_event,
    analyze_events_batch,
    calculate_severity_score,
    AnalysisError
)
from app.schemas import ParsedEvent, AIAnalysis, EventCategory


class TestGroqAnalyzer:
    """Test cases for the GroqAnalyzer class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.sample_event = ParsedEvent(
            id=str(uuid.uuid4()),
            raw_log_id=str(uuid.uuid4()),
            timestamp=datetime(2024, 1, 15, 10, 30, 45, tzinfo=timezone.utc),
            source="MacBook-Pro:sshd[123]",
            message="Failed password for user from 192.168.1.100 port 22 ssh2",
            category=EventCategory.AUTH,
            parsed_at=datetime.now(timezone.utc)
        )
    
    def test_init_with_api_key(self):
        """Test analyzer initialization with API key."""
        analyzer = GroqAnalyzer(api_key="test-key", model="llama-3.1-8b-instant")
        
        assert analyzer.api_key == "test-key"
        assert analyzer.model == "llama-3.1-8b-instant"
        assert analyzer.client is not None
        assert analyzer.stats['total_analyses'] == 0
    
    def test_init_without_api_key(self):
        """Test analyzer initialization without API key."""
        with patch.dict('os.environ', {}, clear=True):
            analyzer = GroqAnalyzer()
            
            assert analyzer.api_key is None
            assert analyzer.client is None
            assert analyzer.model == "llama-3.1-8b-instant"
    
    def test_init_with_env_api_key(self):
        """Test analyzer initialization with environment API key."""
        with patch.dict('os.environ', {'GROQ_API_KEY': 'env-test-key'}):
            analyzer = GroqAnalyzer()
            
            assert analyzer.api_key == "env-test-key"
            assert analyzer.client is not None
    
    def test_init_with_invalid_model(self):
        """Test analyzer initialization with invalid model."""
        analyzer = GroqAnalyzer(api_key="test-key", model="invalid-model")
        
        assert analyzer.model == "llama-3.1-8b-instant"  # Should fallback to default
    
    @patch('app.analyzer.Groq')
    def test_analyze_event_with_groq_success(self, mock_groq_class):
        """Test successful event analysis with Groq API."""
        # Mock Groq client and response
        mock_client = Mock()
        mock_groq_class.return_value = mock_client
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "severity_score": 7,
            "explanation": "Authentication failure detected from external IP",
            "recommendations": [
                "Review user account activity",
                "Check for brute force patterns",
                "Consider IP blocking"
            ]
        })
        
        mock_client.chat.completions.create.return_value = mock_response
        
        analyzer = GroqAnalyzer(api_key="test-key")
        result = analyzer.analyze_event(self.sample_event)
        
        assert isinstance(result, AIAnalysis)
        assert result.event_id == self.sample_event.id
        assert result.severity_score == 7
        assert "Authentication failure" in result.explanation
        assert len(result.recommendations) == 3
        assert analyzer.stats['ai_analyses'] == 1
        assert analyzer.stats['total_analyses'] == 1
    
    @patch('app.analyzer.Groq')
    def test_analyze_event_with_groq_api_error(self, mock_groq_class):
        """Test event analysis when Groq API fails."""
        # Mock Groq client to raise an exception
        mock_client = Mock()
        mock_groq_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        analyzer = GroqAnalyzer(api_key="test-key")
        result = analyzer.analyze_event(self.sample_event)
        
        # Should fallback to rule-based analysis
        assert isinstance(result, AIAnalysis)
        assert result.event_id == self.sample_event.id
        assert 1 <= result.severity_score <= 10
        assert len(result.recommendations) >= 2
        assert analyzer.stats['fallback_analyses'] == 1
        assert analyzer.stats['total_analyses'] == 1
    
    @patch.dict('os.environ', {'GROQ_API_KEY': ''}, clear=False)
    def test_analyze_event_without_api_key(self):
        """Test event analysis without API key (rule-based only)."""
        analyzer = GroqAnalyzer(api_key=None)
        result = analyzer.analyze_event(self.sample_event)
        
        assert isinstance(result, AIAnalysis)
        assert result.event_id == self.sample_event.id
        assert 1 <= result.severity_score <= 10
        assert len(result.recommendations) >= 2
        assert analyzer.stats['fallback_analyses'] == 1
        assert analyzer.stats['total_analyses'] == 1
    
    @patch('app.analyzer.Groq')
    def test_analyze_event_with_invalid_json_response(self, mock_groq_class):
        """Test handling of invalid JSON response from Groq."""
        mock_client = Mock()
        mock_groq_class.return_value = mock_client
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Invalid JSON response"
        
        mock_client.chat.completions.create.return_value = mock_response
        
        analyzer = GroqAnalyzer(api_key="test-key")
        result = analyzer.analyze_event(self.sample_event)
        
        # Should fallback to rule-based analysis
        assert isinstance(result, AIAnalysis)
        assert analyzer.stats['fallback_analyses'] == 1
    
    def test_rule_based_analysis_auth_event(self):
        """Test rule-based analysis for authentication events."""
        analyzer = GroqAnalyzer(api_key=None)
        result = analyzer._analyze_with_rules(self.sample_event)
        
        assert isinstance(result, AIAnalysis)
        assert result.severity_score >= 6  # Auth events should have medium-high severity
        assert "authentication" in result.explanation.lower() or "auth" in result.explanation.lower()
        assert any("account" in rec.lower() for rec in result.recommendations)
    
    def test_rule_based_analysis_security_event(self):
        """Test rule-based analysis for security events."""
        security_event = ParsedEvent(
            id=str(uuid.uuid4()),
            raw_log_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            source="security-scanner",
            message="Malware detected and quarantined",
            category=EventCategory.SECURITY,
            parsed_at=datetime.now(timezone.utc)
        )
        
        analyzer = GroqAnalyzer(api_key=None)
        result = analyzer._analyze_with_rules(security_event)
        
        assert result.severity_score >= 8  # Security events should have high severity
        assert "security" in result.explanation.lower()
        assert any("security" in rec.lower() for rec in result.recommendations)
    
    def test_rule_based_analysis_system_event(self):
        """Test rule-based analysis for system events."""
        system_event = ParsedEvent(
            id=str(uuid.uuid4()),
            raw_log_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            source="systemd",
            message="Service started successfully",
            category=EventCategory.SYSTEM,
            parsed_at=datetime.now(timezone.utc)
        )
        
        analyzer = GroqAnalyzer(api_key=None)
        result = analyzer._analyze_with_rules(system_event)
        
        assert 1 <= result.severity_score <= 10
        assert "system" in result.explanation.lower()
        assert len(result.recommendations) >= 2
    
    def test_rule_based_analysis_kernel_event(self):
        """Test rule-based analysis for kernel events."""
        kernel_event = ParsedEvent(
            id=str(uuid.uuid4()),
            raw_log_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            source="kernel[0]",
            message="Kernel panic - not syncing",
            category=EventCategory.KERNEL,
            parsed_at=datetime.now(timezone.utc)
        )
        
        analyzer = GroqAnalyzer(api_key=None)
        result = analyzer._analyze_with_rules(kernel_event)
        
        assert result.severity_score >= 7  # Kernel events should have high severity
        assert "kernel" in result.explanation.lower()
        assert any("system" in rec.lower() for rec in result.recommendations)
    
    def test_rule_based_analysis_unknown_event(self):
        """Test rule-based analysis for unknown events."""
        unknown_event = ParsedEvent(
            id=str(uuid.uuid4()),
            raw_log_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            source="unknown",
            message="Some random log message",
            category=EventCategory.UNKNOWN,
            parsed_at=datetime.now(timezone.utc)
        )
        
        analyzer = GroqAnalyzer(api_key=None)
        result = analyzer._analyze_with_rules(unknown_event)
        
        assert 1 <= result.severity_score <= 5  # Unknown events should have low severity
        assert len(result.recommendations) >= 2
    
    def test_create_analysis_prompt(self):
        """Test analysis prompt creation."""
        analyzer = GroqAnalyzer(api_key="test-key")
        prompt = analyzer._create_analysis_prompt(self.sample_event)
        
        assert "Failed password" in prompt
        assert "MacBook-Pro:sshd[123]" in prompt
        assert "auth" in prompt
        assert "JSON" in prompt
        assert "severity_score" in prompt
    
    def test_get_system_prompt(self):
        """Test system prompt generation."""
        analyzer = GroqAnalyzer(api_key="test-key")
        system_prompt = analyzer._get_system_prompt()
        
        assert "cybersecurity expert" in system_prompt
        assert "1-10" in system_prompt
        assert "JSON" in system_prompt
    
    @patch('app.analyzer.Groq')
    def test_create_analysis_from_response_valid(self, mock_groq_class):
        """Test creating analysis from valid Groq response."""
        analyzer = GroqAnalyzer(api_key="test-key")
        
        response = {
            "severity_score": 8,
            "explanation": "High severity authentication failure",
            "recommendations": ["Review logs", "Check user account", "Monitor IP"]
        }
        
        result = analyzer._create_analysis_from_response(self.sample_event, response)
        
        assert result.severity_score == 8
        assert result.explanation == "High severity authentication failure"
        assert len(result.recommendations) == 3
        assert result.event_id == self.sample_event.id
    
    @patch('app.analyzer.Groq')
    def test_create_analysis_from_response_invalid_severity(self, mock_groq_class):
        """Test creating analysis from response with invalid severity."""
        analyzer = GroqAnalyzer(api_key="test-key")
        
        response = {
            "severity_score": 15,  # Invalid (> 10)
            "explanation": "Test explanation",
            "recommendations": ["Test recommendation"]
        }
        
        result = analyzer._create_analysis_from_response(self.sample_event, response)
        
        assert result.severity_score == 5  # Should default to 5
    
    @patch('app.analyzer.Groq')
    def test_create_analysis_from_response_missing_fields(self, mock_groq_class):
        """Test creating analysis from response with missing fields."""
        analyzer = GroqAnalyzer(api_key="test-key")
        
        response = {}  # Empty response
        
        result = analyzer._create_analysis_from_response(self.sample_event, response)
        
        assert result.severity_score == 1  # Default
        assert len(result.explanation) >= 10  # Should have default explanation
        assert len(result.recommendations) >= 2  # Should have default recommendations
    
    def test_generate_rule_based_explanation(self):
        """Test rule-based explanation generation."""
        analyzer = GroqAnalyzer(api_key=None)
        
        explanation = analyzer._generate_rule_based_explanation(self.sample_event, 7, 2)
        
        assert "Auth event" in explanation
        assert "medium risk" in explanation or "high risk" in explanation
        assert "severity 7" in explanation
        assert "2 security-relevant keyword" in explanation
    
    def test_generate_rule_based_recommendations(self):
        """Test rule-based recommendation generation."""
        analyzer = GroqAnalyzer(api_key=None)
        
        recommendations = analyzer._generate_rule_based_recommendations(self.sample_event, 8)
        
        assert len(recommendations) >= 2
        assert len(recommendations) <= 4
        assert any("investigate" in rec.lower() for rec in recommendations)
        assert any("account" in rec.lower() for rec in recommendations)
    
    @patch.dict('os.environ', {'GROQ_API_KEY': ''}, clear=False)
    def test_get_analysis_stats(self):
        """Test getting analysis statistics."""
        analyzer = GroqAnalyzer(api_key=None)
        
        # Perform some analyses
        analyzer.analyze_event(self.sample_event)
        analyzer.analyze_event(self.sample_event)
        
        stats = analyzer.get_analysis_stats()
        
        assert stats['total_analyses'] == 2
        assert stats['fallback_analyses'] == 2
        assert stats['ai_analyses'] == 0
        assert stats['errors'] == 0
    
    def test_reset_stats(self):
        """Test resetting analysis statistics."""
        analyzer = GroqAnalyzer(api_key=None)
        
        # Perform analysis to generate stats
        analyzer.analyze_event(self.sample_event)
        assert analyzer.stats['total_analyses'] == 1
        
        # Reset stats
        analyzer.reset_stats()
        assert analyzer.stats['total_analyses'] == 0
        assert analyzer.stats['fallback_analyses'] == 0


class TestConvenienceFunctions:
    """Test cases for convenience functions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.sample_event = ParsedEvent(
            id=str(uuid.uuid4()),
            raw_log_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            source="test-source",
            message="Test message",
            category=EventCategory.SYSTEM,
            parsed_at=datetime.now(timezone.utc)
        )
    
    def test_analyze_event_function(self):
        """Test the analyze_event convenience function."""
        result = analyze_event(self.sample_event, api_key=None)
        
        assert isinstance(result, AIAnalysis)
        assert result.event_id == self.sample_event.id
        assert 1 <= result.severity_score <= 10
    
    def test_analyze_events_batch_function(self):
        """Test the analyze_events_batch convenience function."""
        events = [self.sample_event, self.sample_event]
        
        results = analyze_events_batch(events, api_key=None)
        
        assert len(results) == 2
        assert all(isinstance(result, AIAnalysis) for result in results)
        assert all(result.event_id == self.sample_event.id for result in results)
    
    def test_analyze_events_batch_with_error(self):
        """Test batch analysis with some events causing errors."""
        # Create an event that might cause issues during analysis
        problematic_event = ParsedEvent(
            id=str(uuid.uuid4()),
            raw_log_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            source="problematic-source",
            message="x",  # Minimal message
            category=EventCategory.UNKNOWN,
            parsed_at=datetime.now(timezone.utc)
        )
        
        events = [self.sample_event, problematic_event]
        
        results = analyze_events_batch(events, api_key=None)
        
        # Should process both events
        assert len(results) == 2
        assert all(isinstance(result, AIAnalysis) for result in results)
    
    def test_calculate_severity_score_function(self):
        """Test the calculate_severity_score convenience function."""
        score = calculate_severity_score(self.sample_event)
        
        assert isinstance(score, int)
        assert 1 <= score <= 10


class TestErrorHandling:
    """Test cases for error handling and edge cases."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.sample_event = ParsedEvent(
            id=str(uuid.uuid4()),
            raw_log_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            source="test-source",
            message="Test message",
            category=EventCategory.SYSTEM,
            parsed_at=datetime.now(timezone.utc)
        )
    
    @patch('app.analyzer.GroqAnalyzer._analyze_with_groq')
    @patch('app.analyzer.GroqAnalyzer._analyze_with_rules')
    def test_complete_analysis_failure(self, mock_rule_analysis, mock_groq_analysis):
        """Test handling when both AI and rule-based analysis fail."""
        # Mock both analysis methods to raise exceptions
        mock_groq_analysis.return_value = None  # Simulate AI failure
        mock_rule_analysis.side_effect = Exception("Rule analysis failed")
        
        analyzer = GroqAnalyzer(api_key="test-key")  # Use API key to trigger AI path
        result = analyzer.analyze_event(self.sample_event)
        
        # Should return minimal analysis
        assert isinstance(result, AIAnalysis)
        assert result.severity_score == 1
        assert "Analysis failed" in result.explanation
        assert len(result.recommendations) >= 2
        assert analyzer.stats['errors'] == 1
    
    def test_minimal_message_event(self):
        """Test analysis of event with minimal message."""
        minimal_event = ParsedEvent(
            id=str(uuid.uuid4()),
            raw_log_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            source="test-source",
            message="x",  # Minimal valid message
            category=EventCategory.UNKNOWN,
            parsed_at=datetime.now(timezone.utc)
        )
        
        analyzer = GroqAnalyzer(api_key=None)
        result = analyzer.analyze_event(minimal_event)
        
        assert isinstance(result, AIAnalysis)
        assert 1 <= result.severity_score <= 10
    
    def test_very_long_message_event(self):
        """Test analysis of event with very long message."""
        long_message = "A" * 10000
        long_event = ParsedEvent(
            id=str(uuid.uuid4()),
            raw_log_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            source="test-source",
            message=long_message,
            category=EventCategory.SYSTEM,
            parsed_at=datetime.now(timezone.utc)
        )
        
        analyzer = GroqAnalyzer(api_key=None)
        result = analyzer.analyze_event(long_event)
        
        assert isinstance(result, AIAnalysis)
        assert 1 <= result.severity_score <= 10
    
    def test_special_characters_in_message(self):
        """Test analysis of event with special characters."""
        special_event = ParsedEvent(
            id=str(uuid.uuid4()),
            raw_log_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            source="test-source",
            message="Message with special chars: !@#$%^&*()[]{}|\\:;\"'<>?,./ and unicode: 你好世界 🌍",
            category=EventCategory.SYSTEM,
            parsed_at=datetime.now(timezone.utc)
        )
        
        analyzer = GroqAnalyzer(api_key=None)
        result = analyzer.analyze_event(special_event)
        
        assert isinstance(result, AIAnalysis)
        assert 1 <= result.severity_score <= 10


class TestModelSelection:
    """Test cases for different Groq models."""
    
    def test_valid_model_selection(self):
        """Test initialization with valid models."""
        valid_models = [
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
            "gemma2-9b-it"
        ]
        
        for model in valid_models:
            analyzer = GroqAnalyzer(api_key="test-key", model=model)
            assert analyzer.model == model
    
    def test_invalid_model_fallback(self):
        """Test fallback to default model with invalid model name."""
        analyzer = GroqAnalyzer(api_key="test-key", model="invalid-model-name")
        assert analyzer.model == "llama-3.1-8b-instant"


class TestSeverityRules:
    """Test cases for severity rule configuration."""
    
    def test_all_categories_have_rules(self):
        """Test that all event categories have severity rules."""
        analyzer = GroqAnalyzer(api_key=None)
        
        for category in EventCategory:
            assert category in analyzer.SEVERITY_RULES
            rules = analyzer.SEVERITY_RULES[category]
            assert 'keywords' in rules
            assert 'base_score' in rules
            assert 'multiplier' in rules
            assert isinstance(rules['keywords'], list)
            assert isinstance(rules['base_score'], int)
            assert isinstance(rules['multiplier'], (int, float))
    
    def test_severity_rule_scoring(self):
        """Test severity rule scoring logic."""
        analyzer = GroqAnalyzer(api_key=None)
        
        # Test high-severity security event
        security_event = ParsedEvent(
            id=str(uuid.uuid4()),
            raw_log_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            source="security",
            message="Attack detected malware virus intrusion",
            category=EventCategory.SECURITY,
            parsed_at=datetime.now(timezone.utc)
        )
        
        result = analyzer._analyze_with_rules(security_event)
        assert result.severity_score >= 8  # Should be high due to multiple keywords
        
        # Test low-severity system event
        system_event = ParsedEvent(
            id=str(uuid.uuid4()),
            raw_log_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            source="system",
            message="Service started normally",
            category=EventCategory.SYSTEM,
            parsed_at=datetime.now(timezone.utc)
        )
        
        result = analyzer._analyze_with_rules(system_event)
        assert result.severity_score <= 5  # Should be low due to no keywords