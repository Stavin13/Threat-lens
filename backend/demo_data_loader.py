#!/usr/bin/env python3
"""
Demo Data Loader for ThreatLens

This script loads sample log files and processes them through the ThreatLens pipeline
to demonstrate the system's capabilities with realistic security events.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.database import get_db_session, init_database
from app.ingestion import store_raw_log
from app.parser import parse_log_entries
from app.analyzer import analyze_event
from app.models import RawLog, Event, AIAnalysis


class DemoDataLoader:
    """Loads demo data and processes it through the ThreatLens pipeline."""
    
    def __init__(self):
        self.sample_logs_dir = Path("data/sample_logs")
        self.db_path = "data/threatlens.db"
        
    async def load_sample_logs(self) -> List[Dict[str, Any]]:
        """Load sample log files and return their content."""
        sample_files = [
            {
                "file": "macos_system.log",
                "source": "macOS System Log",
                "description": "System-level events including kernel messages, sandbox violations, and security events"
            },
            {
                "file": "macos_auth.log", 
                "source": "macOS Auth Log",
                "description": "Authentication events including SSH attempts, sudo usage, and authorization failures"
            }
        ]
        
        loaded_logs = []
        
        for sample_file in sample_files:
            file_path = self.sample_logs_dir / sample_file["file"]
            
            if not file_path.exists():
                print(f"Warning: Sample file {file_path} not found, skipping...")
                continue
                
            with open(file_path, 'r') as f:
                content = f.read()
                
            loaded_logs.append({
                "content": content,
                "source": sample_file["source"],
                "description": sample_file["description"],
                "filename": sample_file["file"]
            })
            
        return loaded_logs
    
    async def process_demo_data(self, clear_existing: bool = False) -> Dict[str, Any]:
        """Process demo data through the complete ThreatLens pipeline."""
        
        # Initialize database
        print("Initializing database...")
        init_database()
        
        # Clear existing data if requested
        if clear_existing:
            print("Clearing existing demo data...")
            await self._clear_demo_data()
        
        # Load sample logs
        print("Loading sample log files...")
        sample_logs = await self.load_sample_logs()
        
        if not sample_logs:
            print("No sample logs found to process!")
            return {"error": "No sample logs available"}
        
        results = {
            "processed_logs": [],
            "total_events": 0,
            "analyzed_events": 0,
            "categories": {},
            "severity_distribution": {i: 0 for i in range(1, 11)}
        }
        
        # Process each sample log file
        for log_data in sample_logs:
            print(f"\nProcessing {log_data['filename']}...")
            
            # Step 1: Ingest raw log
            raw_log_id = await self._ingest_raw_log(
                log_data["content"], 
                log_data["source"]
            )
            
            # Step 2: Parse log entries
            parsed_events = await self._parse_log_entries(
                raw_log_id, 
                log_data["content"]
            )
            
            # Step 3: Analyze events with AI
            analyzed_events = await self._analyze_events(parsed_events)
            
            # Update results
            log_result = {
                "filename": log_data["filename"],
                "source": log_data["source"],
                "description": log_data["description"],
                "raw_log_id": raw_log_id,
                "events_count": len(parsed_events),
                "analyzed_count": len(analyzed_events)
            }
            
            results["processed_logs"].append(log_result)
            results["total_events"] += len(parsed_events)
            results["analyzed_events"] += len(analyzed_events)
            
            # Update category and severity statistics
            for event in analyzed_events:
                category = event.get("category", "unknown")
                severity = event.get("severity_score", 0)
                
                results["categories"][category] = results["categories"].get(category, 0) + 1
                if 1 <= severity <= 10:
                    results["severity_distribution"][severity] += 1
            
            print(f"  - Ingested raw log: {raw_log_id}")
            print(f"  - Parsed {len(parsed_events)} events")
            print(f"  - Analyzed {len(analyzed_events)} events")
        
        return results
    
    async def _ingest_raw_log(self, content: str, source: str) -> str:
        """Ingest raw log content into the database."""
        return store_raw_log(content, source)
    
    async def _parse_log_entries(self, raw_log_id: str, content: str) -> List[Dict[str, Any]]:
        """Parse raw log content into structured events."""
        parsed_events = parse_log_entries(content)
        
        # Store parsed events in database
        stored_events = []
        with get_db_session() as db:
            from app.models import Event as EventModel
            
            for event in parsed_events:
                db_event = EventModel(
                    id=event.id,
                    raw_log_id=raw_log_id,
                    timestamp=event.timestamp,
                    source=event.source,
                    message=event.message,
                    category=event.category
                )
                db.add(db_event)
                
                stored_events.append({
                    "id": event.id,
                    "timestamp": event.timestamp,
                    "source": event.source,
                    "message": event.message,
                    "category": event.category
                })
            
            db.commit()
        
        return stored_events
    
    async def _analyze_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze events using AI and store results."""
        analyzed_events = []
        
        with get_db_session() as db:
            from app.models import AIAnalysis as AIAnalysisModel
            import json
            
            for event in events:
                try:
                    # Create a ParsedEvent-like object for analysis
                    from app.schemas import ParsedEvent
                    from datetime import datetime
                    
                    parsed_event = ParsedEvent(
                        id=event["id"],
                        timestamp=datetime.fromisoformat(event["timestamp"].replace('Z', '+00:00')) if isinstance(event["timestamp"], str) else event["timestamp"],
                        source=event["source"],
                        message=event["message"],
                        category=event["category"]
                    )
                    
                    # Analyze the event
                    analysis = analyze_event(parsed_event)
                    
                    # Store analysis in database
                    db_analysis = AIAnalysisModel(
                        id=f"analysis_{event['id']}",
                        event_id=event["id"],
                        severity_score=analysis.severity_score,
                        explanation=analysis.explanation,
                        recommendations=json.dumps(analysis.recommendations)
                    )
                    db.add(db_analysis)
                    
                    analyzed_events.append({
                        **event,
                        "severity_score": analysis.severity_score,
                        "explanation": analysis.explanation,
                        "recommendations": analysis.recommendations
                    })
                    
                except Exception as e:
                    print(f"Warning: Failed to analyze event {event['id']}: {e}")
                    # Add event without analysis
                    analyzed_events.append({
                        **event,
                        "severity_score": 5,  # Default severity
                        "explanation": "Analysis failed - manual review required",
                        "recommendations": ["Review event manually"]
                    })
            
            db.commit()
        
        return analyzed_events
    
    async def _clear_demo_data(self):
        """Clear existing demo data from the database."""
        with get_db_session() as db:
            from app.models import AIAnalysis as AIAnalysisModel, Event as EventModel, RawLog, Report
            
            # Clear in reverse dependency order
            db.query(AIAnalysisModel).delete()
            db.query(EventModel).delete()
            db.query(RawLog).delete()
            db.query(Report).delete()
            
            db.commit()
    
    def print_demo_summary(self, results: Dict[str, Any]):
        """Print a summary of the demo data loading results."""
        print("\n" + "="*60)
        print("DEMO DATA LOADING SUMMARY")
        print("="*60)
        
        if "error" in results:
            print(f"Error: {results['error']}")
            return
        
        print(f"Total Events Processed: {results['total_events']}")
        print(f"Events with AI Analysis: {results['analyzed_events']}")
        print(f"Success Rate: {(results['analyzed_events']/results['total_events']*100):.1f}%")
        
        print("\nProcessed Log Files:")
        for log in results["processed_logs"]:
            print(f"  • {log['filename']}")
            print(f"    Source: {log['source']}")
            print(f"    Events: {log['events_count']} parsed, {log['analyzed_count']} analyzed")
            print(f"    Description: {log['description']}")
        
        print("\nEvent Categories:")
        for category, count in results["categories"].items():
            print(f"  • {category}: {count} events")
        
        print("\nSeverity Distribution:")
        for severity, count in results["severity_distribution"].items():
            if count > 0:
                bar = "█" * min(count, 20)
                print(f"  • Severity {severity}: {count:2d} events {bar}")
        
        print("\n" + "="*60)
        print("Demo data loading complete!")
        print("You can now:")
        print("1. Start the FastAPI server: python main.py")
        print("2. View events in the web dashboard")
        print("3. Generate reports with the loaded demo data")
        print("="*60)


async def main():
    """Main function to run the demo data loader."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Load demo data for ThreatLens")
    parser.add_argument("--clear", action="store_true", 
                       help="Clear existing data before loading demo data")
    parser.add_argument("--quiet", action="store_true",
                       help="Suppress detailed output")
    
    args = parser.parse_args()
    
    loader = DemoDataLoader()
    
    try:
        results = await loader.process_demo_data(clear_existing=args.clear)
        
        if not args.quiet:
            loader.print_demo_summary(results)
        
        return 0
        
    except Exception as e:
        print(f"Error loading demo data: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)