"""
Unit tests for the report generation module.
"""
import pytest
import tempfile
import json
from datetime import datetime, date, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from app.report_generator import ReportGenerator, generate_daily_report, save_report_record
from app.models import Event, AIAnalysis, Report
from app.schemas import EventCategory


class TestReportGenerator:
    """Test cases for the ReportGenerator class."""
    
    @pytest.fixture
    def report_generator(self):
        """Create a ReportGenerator instance for testing."""
        return ReportGenerator()
    
    @pytest.fixture
    def sample_events_data(self):
        """Create sample events data for testing."""
        return [
            {
                'id': 'event-1',
                'timestamp': datetime(2024, 1, 15, 10, 30, 0),
                'source': 'system.log',
                'message': 'Failed login attempt from 192.168.1.100',
                'category': 'auth',
                'ai_analysis': {
                    'severity_score': 8,
                    'explanation': 'Multiple failed login attempts detected from external IP address',
                    'recommendations': ['Block IP address', 'Review authentication logs', 'Enable MFA']
                }
            },
            {
                'id': 'event-2',
                'timestamp': datetime(2024, 1, 15, 11, 15, 0),
                'source': 'kernel.log',
                'message': 'System process terminated unexpectedly',
                'category': 'system',
                'ai_analysis': {
                    'severity_score': 5,
                    'explanation': 'System process crash may indicate stability issues',
                    'recommendations': ['Check system logs', 'Monitor system resources']
                }
            },
            {
                'id': 'event-3',
                'timestamp': datetime(2024, 1, 15, 12, 0, 0),
                'source': 'network.log',
                'message': 'Unusual network traffic detected',
                'category': 'network',
                'ai_analysis': {
                    'severity_score': 6,
                    'explanation': 'Abnormal network patterns may indicate security threat',
                    'recommendations': ['Analyze network traffic', 'Check firewall rules']
                }
            },
            {
                'id': 'event-4',
                'timestamp': datetime(2024, 1, 15, 13, 30, 0),
                'source': 'app.log',
                'message': 'Application started successfully',
                'category': 'application',
                'ai_analysis': None  # No AI analysis
            }
        ]
    
    def test_report_generator_initialization(self, report_generator):
        """Test ReportGenerator initialization."""
        assert report_generator is not None
        assert hasattr(report_generator, 'styles')
        assert hasattr(report_generator, 'severity_colors')
        assert len(report_generator.severity_colors) == 10
        
        # Check custom styles are created
        assert 'ReportTitle' in report_generator.styles
        assert 'SectionHeader' in report_generator.styles
        assert 'SubsectionHeader' in report_generator.styles
        assert 'EventDetail' in report_generator.styles
        assert 'Summary' in report_generator.styles
    
    def test_severity_colors_mapping(self, report_generator):
        """Test severity color mapping."""
        colors = report_generator.severity_colors
        
        # Check all severity levels have colors
        for severity in range(1, 11):
            assert severity in colors
            assert colors[severity].startswith('#')  # Hex color format
        
        # Check color progression (lower severity = greener, higher = redder)
        assert colors[1] == '#2E8B57'  # Sea Green
        assert colors[10] == '#8B0000'  # Dark Red
    
    @patch('app.report_generator.get_db_session')
    def test_get_events_for_date(self, mock_db_session, report_generator, sample_events_data):
        """Test retrieving events for a specific date."""
        # Mock database session and query
        mock_db = Mock(spec=Session)
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        # Create mock events
        mock_events = []
        for event_data in sample_events_data[:3]:  # Only events with AI analysis
            mock_event = Mock()
            mock_event.id = event_data['id']
            mock_event.timestamp = event_data['timestamp']
            mock_event.source = event_data['source']
            mock_event.message = event_data['message']
            mock_event.category = event_data['category']
            
            if event_data['ai_analysis']:
                mock_analysis = Mock()
                mock_analysis.severity_score = event_data['ai_analysis']['severity_score']
                mock_analysis.explanation = event_data['ai_analysis']['explanation']
                mock_analysis.recommendations = json.dumps(event_data['ai_analysis']['recommendations'])
                mock_event.ai_analysis = mock_analysis
            else:
                mock_event.ai_analysis = None
            
            mock_events.append(mock_event)
        
        mock_db.query.return_value.filter.return_value.all.return_value = mock_events
        
        # Test the method
        test_date = date(2024, 1, 15)
        result = report_generator._get_events_for_date(mock_db, test_date)
        
        assert len(result) == 3
        assert result[0]['id'] == 'event-1'
        assert result[0]['ai_analysis']['severity_score'] == 8
        assert len(result[0]['ai_analysis']['recommendations']) == 3
    
    def test_create_report_header(self, report_generator):
        """Test report header creation."""
        test_date = date(2024, 1, 15)
        event_count = 5
        
        header_elements = report_generator._create_report_header(test_date, event_count)
        
        assert len(header_elements) > 0
        # Should contain title, date info, and separator elements
        assert any('ThreatLens Security Report' in str(elem) for elem in header_elements)
    
    def test_create_executive_summary_with_events(self, report_generator, sample_events_data):
        """Test executive summary creation with events."""
        summary_elements = report_generator._create_executive_summary(sample_events_data)
        
        assert len(summary_elements) > 0
        # Should contain summary statistics - check the paragraph content
        summary_text = str(summary_elements)
        assert 'Total Events:</b> 4' in summary_text
        assert 'Events with AI Analysis:</b> 3' in summary_text
    
    def test_create_executive_summary_no_events(self, report_generator):
        """Test executive summary creation with no events."""
        summary_elements = report_generator._create_executive_summary([])
        
        assert len(summary_elements) > 0
        summary_text = str(summary_elements)
        assert 'No security events were recorded' in summary_text
    
    def test_create_severity_chart_with_data(self, report_generator, sample_events_data):
        """Test severity chart creation with event data."""
        # Filter events with AI analysis
        events_with_analysis = [e for e in sample_events_data if e['ai_analysis']]
        
        chart_image = report_generator._create_severity_chart(events_with_analysis)
        
        assert chart_image is not None
        # Should be a ReportLab Image object
        assert hasattr(chart_image, 'drawWidth')
        assert hasattr(chart_image, 'drawHeight')
    
    def test_create_severity_chart_no_data(self, report_generator):
        """Test severity chart creation with no AI analysis data."""
        events_no_analysis = [
            {
                'id': 'event-1',
                'timestamp': datetime.now(),
                'source': 'test',
                'message': 'test message',
                'category': 'system',
                'ai_analysis': None
            }
        ]
        
        chart_image = report_generator._create_severity_chart(events_no_analysis)
        
        assert chart_image is None
    
    def test_create_event_details_section(self, report_generator, sample_events_data):
        """Test event details section creation."""
        details_elements = report_generator._create_event_details_section(sample_events_data)
        
        assert len(details_elements) > 0
        # Should contain event details
        details_text = str(details_elements)
        assert 'Event Details' in details_text
    
    def test_create_event_details_section_empty(self, report_generator):
        """Test event details section with no events."""
        details_elements = report_generator._create_event_details_section([])
        
        assert len(details_elements) > 0
        details_text = str(details_elements)
        assert 'No events to display' in details_text
    
    def test_create_event_detail(self, report_generator, sample_events_data):
        """Test individual event detail creation."""
        event = sample_events_data[0]  # Event with AI analysis
        
        detail_elements = report_generator._create_event_detail(event, 1)
        
        assert len(detail_elements) > 0
        # Should contain event information
        detail_text = str(detail_elements)
        assert 'Event #1' in detail_text
        assert 'Severity: 8/10' in detail_text
    
    def test_create_recommendations_section(self, report_generator, sample_events_data):
        """Test recommendations section creation."""
        recommendations_elements = report_generator._create_recommendations_section(sample_events_data)
        
        assert len(recommendations_elements) > 0
        # Should contain recommendations
        recommendations_text = str(recommendations_elements)
        assert 'Security Recommendations' in recommendations_text
    
    def test_create_recommendations_section_no_analysis(self, report_generator):
        """Test recommendations section with no AI analysis."""
        events_no_analysis = [
            {
                'id': 'event-1',
                'timestamp': datetime.now(),
                'source': 'test',
                'message': 'test message',
                'category': 'system',
                'ai_analysis': None
            }
        ]
        
        recommendations_elements = report_generator._create_recommendations_section(events_no_analysis)
        
        assert len(recommendations_elements) > 0
        recommendations_text = str(recommendations_elements)
        assert 'No specific recommendations available' in recommendations_text
    
    @patch('app.report_generator.get_db_session')
    def test_generate_daily_report_success(self, mock_db_session, report_generator, sample_events_data):
        """Test successful daily report generation."""
        # Mock database session
        mock_db = Mock(spec=Session)
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        # Mock events query
        mock_events = []
        for event_data in sample_events_data:
            mock_event = Mock()
            mock_event.id = event_data['id']
            mock_event.timestamp = event_data['timestamp']
            mock_event.source = event_data['source']
            mock_event.message = event_data['message']
            mock_event.category = event_data['category']
            
            if event_data['ai_analysis']:
                mock_analysis = Mock()
                mock_analysis.severity_score = event_data['ai_analysis']['severity_score']
                mock_analysis.explanation = event_data['ai_analysis']['explanation']
                mock_analysis.recommendations = json.dumps(event_data['ai_analysis']['recommendations'])
                mock_event.ai_analysis = mock_analysis
            else:
                mock_event.ai_analysis = None
            
            mock_events.append(mock_event)
        
        mock_db.query.return_value.filter.return_value.all.return_value = mock_events
        
        # Test report generation
        test_date = date(2024, 1, 15)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_report.pdf"
            
            file_path, pdf_bytes = report_generator.generate_daily_report(test_date, str(output_path))
            
            assert file_path == str(output_path)
            assert isinstance(pdf_bytes, bytes)
            assert len(pdf_bytes) > 0
            assert Path(output_path).exists()
            
            # Check PDF header
            assert pdf_bytes.startswith(b'%PDF')


class TestReportGeneratorFunctions:
    """Test cases for standalone report generator functions."""
    
    @patch('app.report_generator.ReportGenerator')
    def test_generate_daily_report_function(self, mock_generator_class):
        """Test the generate_daily_report convenience function."""
        # Mock the generator instance
        mock_generator = Mock()
        mock_generator.generate_daily_report.return_value = ("/path/to/report.pdf", b"pdf_content")
        mock_generator_class.return_value = mock_generator
        
        test_date = date(2024, 1, 15)
        result = generate_daily_report(test_date)
        
        assert result == ("/path/to/report.pdf", b"pdf_content")
        mock_generator.generate_daily_report.assert_called_once_with(test_date, None)
    
    def test_save_report_record(self):
        """Test saving report record to database."""
        # Mock database session
        mock_db = Mock(spec=Session)
        
        test_date = date(2024, 1, 15)
        test_path = "/path/to/report.pdf"
        
        with patch('uuid.uuid4') as mock_uuid:
            mock_uuid.return_value = Mock()
            mock_uuid.return_value.__str__ = Mock(return_value="test-report-id")
            
            report_id = save_report_record(mock_db, test_date, test_path)
            
            assert report_id == "test-report-id"
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()


class TestReportGeneratorIntegration:
    """Integration tests for report generation."""
    
    @patch('app.report_generator.get_db_session')
    def test_full_report_generation_workflow(self, mock_db_session):
        """Test the complete report generation workflow."""
        # Mock database with realistic data
        mock_db = Mock(spec=Session)
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        # Create mock events with various severities
        mock_events = []
        severities = [1, 3, 5, 7, 9, 10]
        categories = ['auth', 'system', 'network', 'security', 'application']
        
        for i, severity in enumerate(severities):
            mock_event = Mock()
            mock_event.id = f"event-{i+1}"
            mock_event.timestamp = datetime(2024, 1, 15, 10 + i, 0, 0)
            mock_event.source = f"source-{i+1}"
            mock_event.message = f"Test security event {i+1}"
            mock_event.category = categories[i % len(categories)]
            
            mock_analysis = Mock()
            mock_analysis.severity_score = severity
            mock_analysis.explanation = f"AI analysis for event {i+1}"
            mock_analysis.recommendations = json.dumps([f"Recommendation {i+1}"])
            mock_event.ai_analysis = mock_analysis
            
            mock_events.append(mock_event)
        
        mock_db.query.return_value.filter.return_value.all.return_value = mock_events
        
        # Generate report
        generator = ReportGenerator()
        test_date = date(2024, 1, 15)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "integration_test_report.pdf"
            
            file_path, pdf_bytes = generator.generate_daily_report(test_date, str(output_path))
            
            # Verify results
            assert Path(file_path).exists()
            assert len(pdf_bytes) > 1000  # Should be a substantial PDF
            assert pdf_bytes.startswith(b'%PDF')
            
            # Verify file was written
            with open(output_path, 'rb') as f:
                file_content = f.read()
                assert file_content == pdf_bytes
    
    def test_report_generation_error_handling(self):
        """Test error handling in report generation."""
        generator = ReportGenerator()
        
        # Test with invalid date (future date should work in generator, validation is in API)
        future_date = date.today() + timedelta(days=1)
        
        with patch('app.report_generator.get_db_session') as mock_db_session:
            mock_db = Mock(spec=Session)
            mock_db_session.return_value.__enter__.return_value = mock_db
            mock_db.query.return_value.filter.return_value.all.return_value = []
            
            # Should not raise an error, just generate empty report
            file_path, pdf_bytes = generator.generate_daily_report(future_date)
            
            assert isinstance(file_path, str)
            assert isinstance(pdf_bytes, bytes)
            assert len(pdf_bytes) > 0


if __name__ == "__main__":
    pytest.main([__file__])