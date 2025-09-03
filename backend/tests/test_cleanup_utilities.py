"""
Test Cleanup Utilities for ThreatLens Integration Tests

Provides utilities for test data cleanup, database management,
and test environment setup/teardown.
"""
import os
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

from app.database import get_database_session
from app.models import Base, RawLog, Event, AIAnalysis as AIAnalysisModel, Report


class TestCleanupUtilities:
    """Utilities for managing test data and cleanup."""
    
    def __init__(self):
        self.temp_files = []
        self.temp_dirs = []
        self.test_databases = []
    
    def create_temp_database(self, db_name: str = None) -> str:
        """Create a temporary database for testing."""
        if db_name is None:
            db_name = f"test_db_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        db_fd, db_path = tempfile.mkstemp(suffix='.db', prefix=f'{db_name}_')
        os.close(db_fd)
        
        self.test_databases.append(db_path)
        return db_path
    
    def create_temp_file(self, content: str, suffix: str = '.log') -> str:
        """Create a temporary file with specified content."""
        fd, path = tempfile.mkstemp(suffix=suffix)
        
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        
        self.temp_files.append(path)
        return path
    
    def create_temp_directory(self, prefix: str = 'test_') -> str:
        """Create a temporary directory."""
        temp_dir = tempfile.mkdtemp(prefix=prefix)
        self.temp_dirs.append(temp_dir)
        return temp_dir
    
    @contextmanager
    def isolated_database(self):
        """Context manager for isolated database testing."""
        db_path = self.create_temp_database()
        
        # Create engine and session
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        # Create tables
        Base.metadata.create_all(bind=engine)
        
        try:
            yield TestingSessionLocal
        finally:
            # Cleanup
            engine.dispose()
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    def cleanup_test_data(self, db_session, older_than_hours: int = 1):
        """Clean up test data older than specified hours."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
        
        try:
            # Clean up AI analyses
            db_session.query(AIAnalysisModel).filter(
                AIAnalysisModel.analyzed_at < cutoff_time
            ).delete()
            
            # Clean up events
            db_session.query(Event).filter(
                Event.parsed_at < cutoff_time
            ).delete()
            
            # Clean up raw logs
            db_session.query(RawLog).filter(
                RawLog.ingested_at < cutoff_time
            ).delete()
            
            # Clean up reports
            db_session.query(Report).filter(
                Report.generated_at < cutoff_time
            ).delete()
            
            db_session.commit()
            
        except Exception as e:
            db_session.rollback()
            raise e
    
    def reset_database(self, db_session):
        """Reset database to clean state."""
        try:
            # Delete all data in reverse dependency order
            db_session.query(AIAnalysisModel).delete()
            db_session.query(Event).delete()
            db_session.query(RawLog).delete()
            db_session.query(Report).delete()
            
            db_session.commit()
            
        except Exception as e:
            db_session.rollback()
            raise e
    
    def get_database_stats(self, db_session) -> Dict[str, int]:
        """Get current database statistics."""
        stats = {}
        
        try:
            stats['raw_logs'] = db_session.query(RawLog).count()
            stats['events'] = db_session.query(Event).count()
            stats['ai_analyses'] = db_session.query(AIAnalysisModel).count()
            stats['reports'] = db_session.query(Report).count()
            
        except Exception as e:
            print(f"Error getting database stats: {e}")
            stats = {'error': str(e)}
        
        return stats
    
    def verify_data_integrity(self, db_session) -> List[str]:
        """Verify data integrity and return list of issues found."""
        issues = []
        
        try:
            # Check for orphaned events (events without raw logs)
            orphaned_events = db_session.query(Event).outerjoin(RawLog).filter(
                RawLog.id.is_(None)
            ).count()
            
            if orphaned_events > 0:
                issues.append(f"Found {orphaned_events} orphaned events")
            
            # Check for orphaned AI analyses (analyses without events)
            orphaned_analyses = db_session.query(AIAnalysisModel).outerjoin(Event).filter(
                Event.id.is_(None)
            ).count()
            
            if orphaned_analyses > 0:
                issues.append(f"Found {orphaned_analyses} orphaned AI analyses")
            
            # Check for events without AI analysis (might be expected in some cases)
            events_without_analysis = db_session.query(Event).outerjoin(AIAnalysisModel).filter(
                AIAnalysisModel.id.is_(None)
            ).count()
            
            if events_without_analysis > 0:
                issues.append(f"Found {events_without_analysis} events without AI analysis")
            
            # Check for invalid severity scores
            invalid_severity = db_session.query(AIAnalysisModel).filter(
                (AIAnalysisModel.severity_score < 1) | (AIAnalysisModel.severity_score > 10)
            ).count()
            
            if invalid_severity > 0:
                issues.append(f"Found {invalid_severity} AI analyses with invalid severity scores")
            
        except Exception as e:
            issues.append(f"Error during integrity check: {e}")
        
        return issues
    
    def cleanup_temp_files(self):
        """Clean up all temporary files and directories."""
        # Clean up temporary files
        for file_path in self.temp_files:
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(f"Error cleaning up temp file {file_path}: {e}")
        
        # Clean up temporary directories
        for dir_path in self.temp_dirs:
            try:
                if os.path.exists(dir_path):
                    shutil.rmtree(dir_path)
            except Exception as e:
                print(f"Error cleaning up temp directory {dir_path}: {e}")
        
        # Clean up test databases
        for db_path in self.test_databases:
            try:
                if os.path.exists(db_path):
                    os.unlink(db_path)
            except Exception as e:
                print(f"Error cleaning up test database {db_path}: {e}")
        
        # Clear lists
        self.temp_files.clear()
        self.temp_dirs.clear()
        self.test_databases.clear()
    
    def create_test_data_snapshot(self, db_session, snapshot_name: str) -> str:
        """Create a snapshot of current test data."""
        snapshot_dir = self.create_temp_directory(f'snapshot_{snapshot_name}_')
        
        try:
            # Export raw logs
            raw_logs = db_session.query(RawLog).all()
            raw_logs_data = [
                {
                    'id': log.id,
                    'content': log.content,
                    'source': log.source,
                    'ingested_at': log.ingested_at.isoformat()
                }
                for log in raw_logs
            ]
            
            with open(os.path.join(snapshot_dir, 'raw_logs.json'), 'w') as f:
                import json
                json.dump(raw_logs_data, f, indent=2)
            
            # Export events
            events = db_session.query(Event).all()
            events_data = [
                {
                    'id': event.id,
                    'raw_log_id': event.raw_log_id,
                    'timestamp': event.timestamp.isoformat(),
                    'source': event.source,
                    'message': event.message,
                    'category': event.category,
                    'parsed_at': event.parsed_at.isoformat()
                }
                for event in events
            ]
            
            with open(os.path.join(snapshot_dir, 'events.json'), 'w') as f:
                json.dump(events_data, f, indent=2)
            
            # Export AI analyses
            analyses = db_session.query(AIAnalysisModel).all()
            analyses_data = [
                {
                    'id': analysis.id,
                    'event_id': analysis.event_id,
                    'severity_score': analysis.severity_score,
                    'explanation': analysis.explanation,
                    'recommendations': analysis.recommendations,
                    'analyzed_at': analysis.analyzed_at.isoformat()
                }
                for analysis in analyses
            ]
            
            with open(os.path.join(snapshot_dir, 'ai_analyses.json'), 'w') as f:
                json.dump(analyses_data, f, indent=2)
            
            return snapshot_dir
            
        except Exception as e:
            print(f"Error creating snapshot: {e}")
            return None
    
    def load_test_data_snapshot(self, db_session, snapshot_dir: str):
        """Load test data from a snapshot."""
        import json
        from datetime import datetime
        
        try:
            # Load raw logs
            raw_logs_file = os.path.join(snapshot_dir, 'raw_logs.json')
            if os.path.exists(raw_logs_file):
                with open(raw_logs_file, 'r') as f:
                    raw_logs_data = json.load(f)
                
                for log_data in raw_logs_data:
                    raw_log = RawLog(
                        id=log_data['id'],
                        content=log_data['content'],
                        source=log_data['source'],
                        ingested_at=datetime.fromisoformat(log_data['ingested_at'])
                    )
                    db_session.add(raw_log)
            
            # Load events
            events_file = os.path.join(snapshot_dir, 'events.json')
            if os.path.exists(events_file):
                with open(events_file, 'r') as f:
                    events_data = json.load(f)
                
                for event_data in events_data:
                    event = Event(
                        id=event_data['id'],
                        raw_log_id=event_data['raw_log_id'],
                        timestamp=datetime.fromisoformat(event_data['timestamp']),
                        source=event_data['source'],
                        message=event_data['message'],
                        category=event_data['category'],
                        parsed_at=datetime.fromisoformat(event_data['parsed_at'])
                    )
                    db_session.add(event)
            
            # Load AI analyses
            analyses_file = os.path.join(snapshot_dir, 'ai_analyses.json')
            if os.path.exists(analyses_file):
                with open(analyses_file, 'r') as f:
                    analyses_data = json.load(f)
                
                for analysis_data in analyses_data:
                    analysis = AIAnalysisModel(
                        id=analysis_data['id'],
                        event_id=analysis_data['event_id'],
                        severity_score=analysis_data['severity_score'],
                        explanation=analysis_data['explanation'],
                        recommendations=analysis_data['recommendations'],
                        analyzed_at=datetime.fromisoformat(analysis_data['analyzed_at'])
                    )
                    db_session.add(analysis)
            
            db_session.commit()
            
        except Exception as e:
            db_session.rollback()
            raise e
    
    def measure_test_performance(self, test_name: str, start_time: float, end_time: float, 
                                additional_metrics: Dict[str, Any] = None):
        """Record test performance metrics."""
        duration = end_time - start_time
        
        metrics = {
            'test_name': test_name,
            'duration_seconds': duration,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        if additional_metrics:
            metrics.update(additional_metrics)
        
        # Write to performance log file
        performance_log = os.path.join(tempfile.gettempdir(), 'threatlens_test_performance.log')
        
        try:
            with open(performance_log, 'a') as f:
                import json
                f.write(json.dumps(metrics) + '\n')
        except Exception as e:
            print(f"Error writing performance metrics: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup_temp_files()


# Global cleanup utility instance
cleanup_utils = TestCleanupUtilities()


def pytest_configure(config):
    """Pytest configuration hook."""
    # Setup test environment
    pass


def pytest_unconfigure(config):
    """Pytest cleanup hook."""
    # Clean up after all tests
    cleanup_utils.cleanup_temp_files()


def pytest_runtest_teardown(item, nextitem):
    """Clean up after each test."""
    # Clean up any temporary files created during the test
    if hasattr(item, 'temp_files'):
        for temp_file in item.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except Exception:
                pass