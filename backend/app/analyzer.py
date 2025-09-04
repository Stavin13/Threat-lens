"""
AI-powered security event analysis using Groq API.

This module provides functionality to analyze parsed security events using
Groq's fast inference API with Llama models. It generates severity scores,
explanations, and recommendations for security events.
"""
import json
import os
import uuid
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import re

from groq import Groq
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv is optional
    pass

from app.schemas import ParsedEvent, AIAnalysis, EventCategory

# Configure logging
logger = logging.getLogger(__name__)


class AnalysisError(Exception):
    """Custom exception for analysis errors."""
    pass


class GroqAnalyzer:
    """Main analyzer class using Groq API for security event analysis."""
    
    # Available Groq models
    MODELS = {
        "llama-3.1-70b-versatile": "llama-3.1-70b-versatile",
        "llama-3.1-8b-instant": "llama-3.1-8b-instant", 
        "mixtral-8x7b-32768": "mixtral-8x7b-32768",
        "gemma2-9b-it": "gemma2-9b-it"
    }
    
    # Rule-based severity scoring for fallback
    SEVERITY_RULES = {
        EventCategory.SECURITY: {
            'keywords': ['attack', 'breach', 'malware', 'virus', 'intrusion', 'exploit', 'vulnerability'],
            'base_score': 8,
            'multiplier': 1.2
        },
        EventCategory.AUTH: {
            'keywords': ['failed', 'denied', 'unauthorized', 'invalid', 'blocked'],
            'base_score': 6,
            'multiplier': 1.1
        },
        EventCategory.NETWORK: {
            'keywords': ['blocked', 'denied', 'suspicious', 'anomaly', 'flood'],
            'base_score': 5,
            'multiplier': 1.0
        },
        EventCategory.SYSTEM: {
            'keywords': ['error', 'failure', 'crash', 'panic', 'critical'],
            'base_score': 4,
            'multiplier': 0.9
        },
        EventCategory.APPLICATION: {
            'keywords': ['error', 'exception', 'crash', 'fatal'],
            'base_score': 3,
            'multiplier': 0.8
        },
        EventCategory.KERNEL: {
            'keywords': ['panic', 'oops', 'fault', 'error'],
            'base_score': 7,
            'multiplier': 1.1
        },
        EventCategory.UNKNOWN: {
            'keywords': [],
            'base_score': 2,
            'multiplier': 0.7
        }
    }
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the Groq analyzer.
        
        Args:
            api_key: Groq API key (if None, will try to get from environment)
            model: Model to use for analysis (if None, will try to get from environment)
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            logger.warning("No Groq API key provided. Falling back to rule-based analysis only.")
            self.client = None
        else:
            self.client = Groq(api_key=self.api_key)
        
        # Get model from parameter, environment, or use default
        model = model or os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        self.model = model if model in self.MODELS else "llama-3.1-8b-instant"
        
        # Statistics tracking
        self.stats = {
            'total_analyses': 0,
            'ai_analyses': 0,
            'fallback_analyses': 0,
            'errors': 0
        }
    
    def analyze_event(self, event: ParsedEvent) -> AIAnalysis:
        """
        Analyze a security event and generate AI insights.
        
        Args:
            event: Parsed security event to analyze
            
        Returns:
            AIAnalysis object with severity, explanation, and recommendations
            
        Raises:
            AnalysisError: If analysis fails completely
        """
        self.stats['total_analyses'] += 1
        
        try:
            if self.client:
                # Try AI analysis first
                analysis = self._analyze_with_groq(event)
                if analysis:
                    self.stats['ai_analyses'] += 1
                    return analysis
            
            # Fallback to rule-based analysis
            logger.info(f"Using fallback analysis for event {event.id}")
            analysis = self._analyze_with_rules(event)
            self.stats['fallback_analyses'] += 1
            return analysis
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Analysis failed for event {event.id}: {str(e)}")
            
            # Last resort: minimal analysis
            return AIAnalysis(
                id=str(uuid.uuid4()),
                event_id=event.id,
                severity_score=1,
                explanation="Analysis failed. Manual review recommended.",
                recommendations=["Review this event manually", "Check system logs for context"],
                analyzed_at=datetime.now(timezone.utc)
            )
    
    def _analyze_with_groq(self, event: ParsedEvent) -> Optional[AIAnalysis]:
        """
        Analyze event using Groq API.
        
        Args:
            event: Event to analyze
            
        Returns:
            AIAnalysis object or None if API call fails
        """
        try:
            prompt = self._create_analysis_prompt(event)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for consistent analysis
                max_tokens=1000,
                response_format={"type": "json_object"}
            )
            
            # Parse the JSON response
            result = json.loads(response.choices[0].message.content)
            
            # Validate and create AIAnalysis object
            return self._create_analysis_from_response(event, result)
            
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "rate limit" in error_msg.lower():
                logger.warning(f"Groq API rate limit exceeded, falling back to rule-based analysis")
            else:
                logger.error(f"Groq API call failed: {error_msg}")
            return None
    
    def _analyze_with_rules(self, event: ParsedEvent) -> AIAnalysis:
        """
        Analyze event using rule-based scoring.
        
        Args:
            event: Event to analyze
            
        Returns:
            AIAnalysis object
        """
        category_rules = self.SEVERITY_RULES.get(event.category, self.SEVERITY_RULES[EventCategory.UNKNOWN])
        
        # Calculate base severity
        severity = category_rules['base_score']
        
        # Adjust based on keywords in message
        message_lower = event.message.lower()
        keyword_matches = 0
        
        for keyword in category_rules['keywords']:
            if keyword in message_lower:
                keyword_matches += 1
        
        # Apply keyword multiplier
        if keyword_matches > 0:
            severity = min(10, int(severity * category_rules['multiplier'] * (1 + keyword_matches * 0.1)))
        
        # Generate explanation
        explanation = self._generate_rule_based_explanation(event, severity, keyword_matches)
        
        # Generate recommendations
        recommendations = self._generate_rule_based_recommendations(event, severity)
        
        return AIAnalysis(
            id=str(uuid.uuid4()),
            event_id=event.id,
            severity_score=max(1, min(10, severity)),
            explanation=explanation,
            recommendations=recommendations,
            analyzed_at=datetime.now(timezone.utc)
        )
    
    def _create_analysis_prompt(self, event: ParsedEvent) -> str:
        """
        Create analysis prompt for Groq API.
        
        Args:
            event: Event to analyze
            
        Returns:
            Formatted prompt string
        """
        return f"""Analyze this security log event and provide a JSON response with severity assessment:

Event Details:
- Timestamp: {event.timestamp.isoformat()}
- Source: {event.source}
- Category: {event.category.value}
- Message: {event.message}

Please analyze this event and respond with a JSON object containing:
1. "severity_score": Integer from 1-10 (1=informational, 10=critical)
2. "explanation": Brief explanation of why this event has this severity level
3. "recommendations": Array of 2-4 specific actionable recommendations

Consider:
- Authentication failures, system errors, network anomalies
- Potential security implications
- Context from source and message content
- Urgency of response needed

Respond only with valid JSON."""
    
    def _get_system_prompt(self) -> str:
        """
        Get system prompt for Groq API.
        
        Returns:
            System prompt string
        """
        return """You are a cybersecurity expert analyzing system logs for potential security threats. 

Your role is to:
1. Assess the security severity of log events on a scale of 1-10
2. Provide clear, concise explanations of potential risks
3. Suggest specific, actionable remediation steps

Severity Scale:
- 1-2: Informational, routine operations
- 3-4: Low priority, minor issues
- 5-6: Medium priority, potential concerns
- 7-8: High priority, likely security issues
- 9-10: Critical, immediate attention required

Always respond with valid JSON containing severity_score, explanation, and recommendations fields."""
    
    def _create_analysis_from_response(self, event: ParsedEvent, response: Dict[str, Any]) -> AIAnalysis:
        """
        Create AIAnalysis object from Groq API response.
        
        Args:
            event: Original event
            response: Parsed JSON response from Groq
            
        Returns:
            AIAnalysis object
            
        Raises:
            AnalysisError: If response format is invalid
        """
        try:
            # Handle nested response format (e.g., {"security_log_event": {...}})
            if 'security_log_event' in response:
                response = response['security_log_event']
            elif len(response) == 1 and isinstance(list(response.values())[0], dict):
                # Handle any single-key nested format
                response = list(response.values())[0]
            
            severity = response.get('severity_score', 1)
            explanation = response.get('explanation', 'No explanation provided')
            recommendations = response.get('recommendations', ['Review manually'])
            
            # Validate severity score
            if not isinstance(severity, int) or severity < 1 or severity > 10:
                severity = 5  # Default to medium severity
            
            # Validate explanation
            if not isinstance(explanation, str) or len(explanation.strip()) < 10:
                explanation = f"AI analysis completed for {event.category.value} event"
            
            # Validate recommendations
            if not isinstance(recommendations, list) or len(recommendations) == 0:
                recommendations = ["Review this event manually", "Monitor for similar events"]
            elif len(recommendations) == 1:
                recommendations.append("Monitor for similar events")
            
            # Ensure recommendations are strings
            recommendations = [str(rec) for rec in recommendations if str(rec).strip()]
            
            return AIAnalysis(
                id=str(uuid.uuid4()),
                event_id=event.id,
                severity_score=severity,
                explanation=explanation.strip(),
                recommendations=recommendations,
                analyzed_at=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            raise AnalysisError(f"Failed to parse Groq response: {str(e)}")
    
    def _generate_rule_based_explanation(self, event: ParsedEvent, severity: int, keyword_matches: int) -> str:
        """
        Generate explanation for rule-based analysis.
        
        Args:
            event: Event being analyzed
            severity: Calculated severity score
            keyword_matches: Number of keywords matched
            
        Returns:
            Explanation string
        """
        category_name = event.category.value.title()
        
        if severity >= 8:
            risk_level = "high risk"
        elif severity >= 6:
            risk_level = "medium risk"
        elif severity >= 4:
            risk_level = "low risk"
        else:
            risk_level = "informational"
        
        explanation = f"{category_name} event classified as {risk_level} (severity {severity}/10). "
        
        if keyword_matches > 0:
            explanation += f"Contains {keyword_matches} security-relevant keyword(s). "
        
        # Add category-specific context
        if event.category == EventCategory.AUTH:
            explanation += "Authentication events require monitoring for potential unauthorized access attempts."
        elif event.category == EventCategory.SECURITY:
            explanation += "Security events indicate potential threats that need immediate attention."
        elif event.category == EventCategory.NETWORK:
            explanation += "Network events may indicate connectivity issues or potential intrusion attempts."
        elif event.category == EventCategory.SYSTEM:
            explanation += "System events may indicate operational issues or potential system compromise."
        elif event.category == EventCategory.KERNEL:
            explanation += "Kernel events may indicate serious system stability or security issues."
        else:
            explanation += "Event requires review to determine appropriate response."
        
        return explanation
    
    def _generate_rule_based_recommendations(self, event: ParsedEvent, severity: int) -> List[str]:
        """
        Generate recommendations for rule-based analysis.
        
        Args:
            event: Event being analyzed
            severity: Calculated severity score
            
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        # Severity-based recommendations
        if severity >= 8:
            recommendations.extend([
                "Investigate immediately",
                "Review related system logs",
                "Consider isolating affected systems"
            ])
        elif severity >= 6:
            recommendations.extend([
                "Review within 24 hours",
                "Monitor for similar events",
                "Check system status"
            ])
        elif severity >= 4:
            recommendations.extend([
                "Review during next maintenance window",
                "Document for trend analysis"
            ])
        else:
            recommendations.append("Log for informational purposes")
        
        # Category-specific recommendations
        if event.category == EventCategory.AUTH:
            recommendations.append("Review user account activity")
            if "failed" in event.message.lower():
                recommendations.append("Consider account lockout policies")
        elif event.category == EventCategory.SECURITY:
            recommendations.extend([
                "Run security scans",
                "Update security policies"
            ])
        elif event.category == EventCategory.NETWORK:
            recommendations.append("Check network configuration")
        elif event.category == EventCategory.SYSTEM:
            recommendations.append("Verify system health")
        elif event.category == EventCategory.KERNEL:
            recommendations.extend([
                "Check system stability",
                "Review hardware status"
            ])
        
        # Ensure we have at least 2 recommendations
        if len(recommendations) < 2:
            recommendations.extend([
                "Monitor for recurring patterns",
                "Document in security log"
            ])
        
        return recommendations[:4]  # Limit to 4 recommendations
    
    def get_analysis_stats(self) -> Dict[str, Any]:
        """
        Get analysis statistics.
        
        Returns:
            Dictionary containing analysis statistics
        """
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset analysis statistics."""
        self.stats = {
            'total_analyses': 0,
            'ai_analyses': 0,
            'fallback_analyses': 0,
            'errors': 0
        }


# Convenience functions for external use
def analyze_event(event: ParsedEvent, api_key: Optional[str] = None, model: Optional[str] = None) -> AIAnalysis:
    """
    Analyze a single event using Groq API.
    
    Args:
        event: Event to analyze
        api_key: Groq API key (optional, will use environment variable if not provided)
        model: Model to use for analysis (optional, will use environment variable if not provided)
        
    Returns:
        AIAnalysis object
    """
    analyzer = GroqAnalyzer(api_key=api_key, model=model)
    return analyzer.analyze_event(event)


def analyze_events_batch(events: List[ParsedEvent], api_key: Optional[str] = None, model: Optional[str] = None) -> List[AIAnalysis]:
    """
    Analyze multiple events in batch.
    
    Args:
        events: List of events to analyze
        api_key: Groq API key (optional, will use environment variable if not provided)
        model: Model to use for analysis (optional, will use environment variable if not provided)
        
    Returns:
        List of AIAnalysis objects
    """
    analyzer = GroqAnalyzer(api_key=api_key, model=model)
    results = []
    
    for event in events:
        try:
            analysis = analyzer.analyze_event(event)
            results.append(analysis)
        except Exception as e:
            logger.error(f"Failed to analyze event {event.id}: {str(e)}")
            # Continue with other events
            continue
    
    return results


def calculate_severity_score(event: ParsedEvent) -> int:
    """
    Calculate severity score using rule-based approach only.
    
    Args:
        event: Event to score
        
    Returns:
        Severity score (1-10)
    """
    analyzer = GroqAnalyzer(api_key=None)  # Force rule-based analysis
    analysis = analyzer._analyze_with_rules(event)
    return analysis.severity_score