"""
PDF report generation module for ThreatLens security analysis reports.
"""
import io
import json
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.platypus.flowables import HRFlowable
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.lib.colors import HexColor
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.models import Event, AIAnalysis, Report
from app.schemas import EventCategory, SeverityLevel


class ReportGenerator:
    """PDF report generator for security events and analysis."""
    
    def __init__(self):
        """Initialize the report generator with styles and configuration."""
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        self.severity_colors = {
            1: '#2E8B57',  # Sea Green
            2: '#32CD32',  # Lime Green
            3: '#9ACD32',  # Yellow Green
            4: '#FFD700',  # Gold
            5: '#FFA500',  # Orange
            6: '#FF8C00',  # Dark Orange
            7: '#FF6347',  # Tomato
            8: '#FF4500',  # Orange Red
            9: '#DC143C',  # Crimson
            10: '#8B0000'  # Dark Red
        }
    
    def _setup_custom_styles(self):
        """Set up custom paragraph styles for the report."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Title'],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.darkblue,
            alignment=1  # Center alignment
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading1'],
            fontSize=16,
            spaceBefore=20,
            spaceAfter=12,
            textColor=colors.darkblue,
            borderWidth=1,
            borderColor=colors.darkblue,
            borderPadding=5
        ))
        
        # Subsection header style
        self.styles.add(ParagraphStyle(
            name='SubsectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceBefore=15,
            spaceAfter=8,
            textColor=colors.darkslategray
        ))
        
        # Event detail style
        self.styles.add(ParagraphStyle(
            name='EventDetail',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceBefore=5,
            spaceAfter=5,
            leftIndent=20
        ))
        
        # Summary style
        self.styles.add(ParagraphStyle(
            name='Summary',
            parent=self.styles['Normal'],
            fontSize=12,
            spaceBefore=10,
            spaceAfter=10,
            textColor=colors.darkslategray,
            backColor=colors.lightgrey,
            borderWidth=1,
            borderColor=colors.grey,
            borderPadding=10
        ))
    
    def generate_daily_report(self, report_date: date, output_path: Optional[str] = None) -> Tuple[str, bytes]:
        """
        Generate a comprehensive daily security report.
        
        Args:
            report_date: Date for which to generate the report
            output_path: Optional custom output path for the PDF file
            
        Returns:
            Tuple of (file_path, pdf_bytes)
        """
        # Set up output path
        if output_path is None:
            reports_dir = Path("data/reports")
            reports_dir.mkdir(parents=True, exist_ok=True)
            output_path = reports_dir / f"security_report_{report_date.strftime('%Y%m%d')}.pdf"
        
        # Create PDF buffer
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Build report content
        story = []
        
        # Get events for the specified date
        with get_db_session() as db:
            events_data = self._get_events_for_date(db, report_date)
        
        # Add title and header
        story.extend(self._create_report_header(report_date, len(events_data)))
        
        # Add executive summary
        story.extend(self._create_executive_summary(events_data))
        
        # Add severity distribution chart
        if events_data:
            chart_image = self._create_severity_chart(events_data)
            if chart_image:
                story.append(Paragraph("Severity Distribution", self.styles['SectionHeader']))
                story.append(chart_image)
                story.append(Spacer(1, 12))
        
        # Add event details
        story.extend(self._create_event_details_section(events_data))
        
        # Add recommendations
        story.extend(self._create_recommendations_section(events_data))
        
        # Build PDF
        doc.build(story)
        
        # Get PDF bytes
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        # Write to file if path provided
        if isinstance(output_path, (str, Path)):
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
        
        return str(output_path), pdf_bytes
    
    def _get_events_for_date(self, db: Session, report_date: date) -> List[Dict[str, Any]]:
        """Retrieve events and their AI analysis for a specific date."""
        start_datetime = datetime.combine(report_date, datetime.min.time())
        end_datetime = datetime.combine(report_date, datetime.max.time())
        
        events = db.query(Event).filter(
            Event.timestamp >= start_datetime,
            Event.timestamp <= end_datetime
        ).all()
        
        events_data = []
        for event in events:
            event_dict = {
                'id': event.id,
                'timestamp': event.timestamp,
                'source': event.source,
                'message': event.message,
                'category': event.category,
                'ai_analysis': None
            }
            
            if event.ai_analysis:
                event_dict['ai_analysis'] = {
                    'severity_score': event.ai_analysis.severity_score,
                    'explanation': event.ai_analysis.explanation,
                    'recommendations': json.loads(event.ai_analysis.recommendations)
                }
            
            events_data.append(event_dict)
        
        return events_data
    
    def _create_report_header(self, report_date: date, event_count: int) -> List:
        """Create the report header section."""
        story = []
        
        # Title
        title = f"ThreatLens Security Report"
        story.append(Paragraph(title, self.styles['ReportTitle']))
        
        # Date and summary info
        date_str = report_date.strftime("%B %d, %Y")
        summary_text = f"""
        <b>Report Date:</b> {date_str}<br/>
        <b>Events Analyzed:</b> {event_count}<br/>
        <b>Generated:</b> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        """
        story.append(Paragraph(summary_text, self.styles['Normal']))
        story.append(Spacer(1, 20))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.darkblue))
        story.append(Spacer(1, 20))
        
        return story
    
    def _create_executive_summary(self, events_data: List[Dict[str, Any]]) -> List:
        """Create the executive summary section."""
        story = []
        story.append(Paragraph("Executive Summary", self.styles['SectionHeader']))
        
        if not events_data:
            story.append(Paragraph(
                "No security events were recorded for this date.",
                self.styles['Summary']
            ))
            return story
        
        # Calculate summary statistics
        total_events = len(events_data)
        events_with_analysis = sum(1 for e in events_data if e['ai_analysis'])
        
        severity_counts = {}
        category_counts = {}
        high_severity_events = []
        
        for event in events_data:
            # Count categories
            category = event['category']
            category_counts[category] = category_counts.get(category, 0) + 1
            
            if event['ai_analysis']:
                severity = event['ai_analysis']['severity_score']
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
                
                # Track high severity events (7+)
                if severity >= 7:
                    high_severity_events.append(event)
        
        # Create summary text
        avg_severity = 0
        if severity_counts:
            total_severity = sum(sev * count for sev, count in severity_counts.items())
            avg_severity = total_severity / sum(severity_counts.values())
        
        high_severity_count = len(high_severity_events)
        
        summary_text = f"""
        <b>Total Events:</b> {total_events}<br/>
        <b>Events with AI Analysis:</b> {events_with_analysis}<br/>
        <b>Average Severity Score:</b> {avg_severity:.1f}/10<br/>
        <b>High Severity Events (7+):</b> {high_severity_count}<br/>
        <b>Most Common Category:</b> {max(category_counts, key=category_counts.get) if category_counts else 'N/A'}
        """
        
        story.append(Paragraph(summary_text, self.styles['Summary']))
        story.append(Spacer(1, 15))
        
        return story
    
    def _create_severity_chart(self, events_data: List[Dict[str, Any]]) -> Optional[Image]:
        """Create a severity distribution chart."""
        # Count events by severity
        severity_counts = {}
        for event in events_data:
            if event['ai_analysis']:
                severity = event['ai_analysis']['severity_score']
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        if not severity_counts:
            return None
        
        # Create matplotlib figure
        fig, ax = plt.subplots(figsize=(10, 6))
        
        severities = list(range(1, 11))
        counts = [severity_counts.get(sev, 0) for sev in severities]
        colors_list = [self.severity_colors[sev] for sev in severities]
        
        bars = ax.bar(severities, counts, color=colors_list, alpha=0.8, edgecolor='black', linewidth=0.5)
        
        ax.set_xlabel('Severity Score', fontsize=12)
        ax.set_ylabel('Number of Events', fontsize=12)
        ax.set_title('Event Distribution by Severity Score', fontsize=14, fontweight='bold')
        ax.set_xticks(severities)
        ax.grid(axis='y', alpha=0.3)
        
        # Add value labels on bars
        for bar, count in zip(bars, counts):
            if count > 0:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                       str(count), ha='center', va='bottom', fontsize=10)
        
        plt.tight_layout()
        
        # Save to buffer
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
        img_buffer.seek(0)
        plt.close(fig)
        
        # Create ReportLab Image
        return Image(img_buffer, width=6*inch, height=3.6*inch)
    
    def _create_event_details_section(self, events_data: List[Dict[str, Any]]) -> List:
        """Create the detailed events section."""
        story = []
        story.append(Paragraph("Event Details", self.styles['SectionHeader']))
        
        if not events_data:
            story.append(Paragraph("No events to display.", self.styles['Normal']))
            return story
        
        # Sort events by severity (highest first), then by timestamp
        sorted_events = sorted(
            events_data,
            key=lambda x: (
                -(x['ai_analysis']['severity_score'] if x['ai_analysis'] else 0),
                x['timestamp']
            )
        )
        
        # Show top 20 events to keep report manageable
        top_events = sorted_events[:20]
        
        if len(sorted_events) > 20:
            story.append(Paragraph(
                f"Showing top 20 events (out of {len(sorted_events)} total)",
                self.styles['Normal']
            ))
            story.append(Spacer(1, 10))
        
        for i, event in enumerate(top_events, 1):
            story.extend(self._create_event_detail(event, i))
            if i < len(top_events):
                story.append(Spacer(1, 10))
        
        return story
    
    def _create_event_detail(self, event: Dict[str, Any], index: int) -> List:
        """Create a detailed view of a single event."""
        story = []
        
        # Event header
        timestamp_str = event['timestamp'].strftime("%H:%M:%S")
        severity_str = ""
        if event['ai_analysis']:
            severity = event['ai_analysis']['severity_score']
            severity_str = f" (Severity: {severity}/10)"
        
        header_text = f"<b>Event #{index}</b> - {timestamp_str}{severity_str}"
        story.append(Paragraph(header_text, self.styles['SubsectionHeader']))
        
        # Event details table
        data = [
            ['Source:', event['source']],
            ['Category:', event['category'].title()],
            ['Message:', event['message'][:200] + ('...' if len(event['message']) > 200 else '')]
        ]
        
        if event['ai_analysis']:
            analysis = event['ai_analysis']
            data.extend([
                ['AI Explanation:', analysis['explanation'][:300] + ('...' if len(analysis['explanation']) > 300 else '')],
                ['Recommendations:', '; '.join(analysis['recommendations'][:3])]  # Show first 3 recommendations
            ])
        
        table = Table(data, colWidths=[1.5*inch, 4.5*inch])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ]))
        
        story.append(table)
        
        return story
    
    def _create_recommendations_section(self, events_data: List[Dict[str, Any]]) -> List:
        """Create the recommendations section."""
        story = []
        story.append(Paragraph("Security Recommendations", self.styles['SectionHeader']))
        
        # Collect all recommendations
        all_recommendations = []
        high_severity_count = 0
        
        for event in events_data:
            if event['ai_analysis']:
                severity = event['ai_analysis']['severity_score']
                if severity >= 7:
                    high_severity_count += 1
                
                recommendations = event['ai_analysis']['recommendations']
                all_recommendations.extend(recommendations)
        
        # Generate general recommendations based on analysis
        general_recommendations = []
        
        if high_severity_count > 0:
            general_recommendations.append(
                f"Immediate attention required: {high_severity_count} high-severity events detected."
            )
        
        if len(events_data) > 50:
            general_recommendations.append(
                "High volume of security events detected. Consider reviewing log sources and filtering rules."
            )
        
        # Get unique specific recommendations (top 10)
        unique_recommendations = list(set(all_recommendations))[:10]
        
        # Combine recommendations
        final_recommendations = general_recommendations + unique_recommendations
        
        if not final_recommendations:
            story.append(Paragraph(
                "No specific recommendations available. Continue monitoring security events.",
                self.styles['Normal']
            ))
        else:
            for i, rec in enumerate(final_recommendations, 1):
                story.append(Paragraph(f"{i}. {rec}", self.styles['Normal']))
                story.append(Spacer(1, 5))
        
        return story


def generate_daily_report(report_date: date, output_path: Optional[str] = None) -> Tuple[str, bytes]:
    """
    Convenience function to generate a daily report.
    
    Args:
        report_date: Date for which to generate the report
        output_path: Optional custom output path for the PDF file
        
    Returns:
        Tuple of (file_path, pdf_bytes)
    """
    generator = ReportGenerator()
    return generator.generate_daily_report(report_date, output_path)


def save_report_record(db: Session, report_date: date, file_path: str) -> str:
    """
    Save a report record to the database.
    
    Args:
        db: Database session
        report_date: Date of the report
        file_path: Path to the generated PDF file
        
    Returns:
        Report ID
    """
    import uuid
    
    report_id = str(uuid.uuid4())
    report = Report(
        id=report_id,
        report_date=report_date,
        file_path=file_path
    )
    
    db.add(report)
    db.commit()
    
    return report_id