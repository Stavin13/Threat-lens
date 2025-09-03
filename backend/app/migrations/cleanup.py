"""
Database cleanup utilities for ThreatLens.
Handles cleanup of old metrics, logs, and maintenance tasks.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_db_session

logger = logging.getLogger(__name__)


class DatabaseCleanup:
    """Handles database cleanup and maintenance operations."""
    
    def __init__(self):
        self.cleanup_stats = {
            "processing_metrics_deleted": 0,
            "notification_history_deleted": 0,
            "old_events_deleted": 0,
            "errors": []
        }
    
    def cleanup_old_processing_metrics(self, days_to_keep: int = 30) -> int:
        """
        Clean up processing metrics older than specified days.
        
        Args:
            days_to_keep: Number of days of metrics to retain
            
        Returns:
            Number of records deleted
        """
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        deleted_count = 0
        
        try:
            with get_db_session() as db:
                result = db.execute(text("""
                    DELETE FROM processing_metrics 
                    WHERE timestamp < :cutoff_date
                """), {"cutoff_date": cutoff_date})
                
                deleted_count = result.rowcount
                self.cleanup_stats["processing_metrics_deleted"] = deleted_count
                
                logger.info(f"Deleted {deleted_count} old processing metrics records")
                
        except SQLAlchemyError as e:
            error_msg = f"Failed to cleanup processing metrics: {e}"
            logger.error(error_msg)
            self.cleanup_stats["errors"].append(error_msg)
        
        return deleted_count
    
    def cleanup_old_notification_history(self, days_to_keep: int = 90) -> int:
        """
        Clean up notification history older than specified days.
        
        Args:
            days_to_keep: Number of days of notification history to retain
            
        Returns:
            Number of records deleted
        """
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        deleted_count = 0
        
        try:
            with get_db_session() as db:
                result = db.execute(text("""
                    DELETE FROM notification_history 
                    WHERE sent_at < :cutoff_date
                """), {"cutoff_date": cutoff_date})
                
                deleted_count = result.rowcount
                self.cleanup_stats["notification_history_deleted"] = deleted_count
                
                logger.info(f"Deleted {deleted_count} old notification history records")
                
        except SQLAlchemyError as e:
            error_msg = f"Failed to cleanup notification history: {e}"
            logger.error(error_msg)
            self.cleanup_stats["errors"].append(error_msg)
        
        return deleted_count
    
    def cleanup_old_events(self, days_to_keep: int = 365) -> int:
        """
        Clean up old events and related data.
        
        Args:
            days_to_keep: Number of days of events to retain
            
        Returns:
            Number of records deleted
        """
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        deleted_count = 0
        
        try:
            with get_db_session() as db:
                # First delete AI analysis records (foreign key constraint)
                db.execute(text("""
                    DELETE FROM ai_analysis 
                    WHERE event_id IN (
                        SELECT id FROM events WHERE timestamp < :cutoff_date
                    )
                """), {"cutoff_date": cutoff_date})
                
                # Then delete events
                result = db.execute(text("""
                    DELETE FROM events WHERE timestamp < :cutoff_date
                """), {"cutoff_date": cutoff_date})
                
                deleted_count = result.rowcount
                self.cleanup_stats["old_events_deleted"] = deleted_count
                
                logger.info(f"Deleted {deleted_count} old event records")
                
        except SQLAlchemyError as e:
            error_msg = f"Failed to cleanup old events: {e}"
            logger.error(error_msg)
            self.cleanup_stats["errors"].append(error_msg)
        
        return deleted_count
    
    def vacuum_database(self) -> bool:
        """
        Run VACUUM on SQLite database to reclaim space and optimize.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with get_db_session() as db:
                # SQLite VACUUM command
                db.execute(text("VACUUM"))
                logger.info("Database VACUUM completed successfully")
                return True
                
        except SQLAlchemyError as e:
            error_msg = f"Failed to vacuum database: {e}"
            logger.error(error_msg)
            self.cleanup_stats["errors"].append(error_msg)
            return False
    
    def analyze_database(self) -> bool:
        """
        Run ANALYZE on SQLite database to update query planner statistics.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with get_db_session() as db:
                # SQLite ANALYZE command
                db.execute(text("ANALYZE"))
                logger.info("Database ANALYZE completed successfully")
                return True
                
        except SQLAlchemyError as e:
            error_msg = f"Failed to analyze database: {e}"
            logger.error(error_msg)
            self.cleanup_stats["errors"].append(error_msg)
            return False
    
    def cleanup_orphaned_records(self) -> Dict[str, int]:
        """
        Clean up orphaned records that reference non-existent parent records.
        
        Returns:
            Dictionary with counts of cleaned up records
        """
        cleanup_counts = {
            "orphaned_ai_analysis": 0,
            "orphaned_notification_history": 0
        }
        
        try:
            with get_db_session() as db:
                # Clean up AI analysis records with no corresponding event
                result = db.execute(text("""
                    DELETE FROM ai_analysis 
                    WHERE event_id NOT IN (SELECT id FROM events)
                """))
                cleanup_counts["orphaned_ai_analysis"] = result.rowcount
                
                # Clean up notification history with no corresponding event
                result = db.execute(text("""
                    DELETE FROM notification_history 
                    WHERE event_id NOT IN (SELECT id FROM events)
                """))
                cleanup_counts["orphaned_notification_history"] = result.rowcount
                
                logger.info(f"Cleaned up orphaned records: {cleanup_counts}")
                
        except SQLAlchemyError as e:
            error_msg = f"Failed to cleanup orphaned records: {e}"
            logger.error(error_msg)
            self.cleanup_stats["errors"].append(error_msg)
        
        return cleanup_counts
    
    def get_database_size_info(self) -> Dict[str, Any]:
        """
        Get information about database size and table sizes.
        
        Returns:
            Dictionary with size information
        """
        size_info = {
            "total_pages": 0,
            "page_size": 0,
            "total_size_bytes": 0,
            "table_sizes": {},
            "error": None
        }
        
        try:
            with get_db_session() as db:
                # Get page count and page size
                result = db.execute(text("PRAGMA page_count"))
                size_info["total_pages"] = result.scalar() or 0
                
                result = db.execute(text("PRAGMA page_size"))
                size_info["page_size"] = result.scalar() or 0
                
                size_info["total_size_bytes"] = size_info["total_pages"] * size_info["page_size"]
                
                # Get table sizes (approximate)
                tables = ["raw_logs", "events", "ai_analysis", "reports", 
                         "monitoring_config", "log_sources", "processing_metrics", "notification_history"]
                
                for table in tables:
                    try:
                        result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                        count = result.scalar() or 0
                        size_info["table_sizes"][table] = count
                    except SQLAlchemyError:
                        size_info["table_sizes"][table] = 0
                
        except SQLAlchemyError as e:
            size_info["error"] = str(e)
            logger.error(f"Failed to get database size info: {e}")
        
        return size_info
    
    def run_full_cleanup(self, 
                        metrics_days: int = 30,
                        notification_days: int = 90,
                        events_days: int = 365,
                        vacuum: bool = True,
                        analyze: bool = True) -> Dict[str, Any]:
        """
        Run a full cleanup operation with all cleanup tasks.
        
        Args:
            metrics_days: Days of processing metrics to keep
            notification_days: Days of notification history to keep
            events_days: Days of events to keep
            vacuum: Whether to run VACUUM
            analyze: Whether to run ANALYZE
            
        Returns:
            Dictionary with cleanup results
        """
        logger.info("Starting full database cleanup...")
        
        # Reset stats
        self.cleanup_stats = {
            "processing_metrics_deleted": 0,
            "notification_history_deleted": 0,
            "old_events_deleted": 0,
            "errors": []
        }
        
        # Run cleanup operations
        self.cleanup_old_processing_metrics(metrics_days)
        self.cleanup_old_notification_history(notification_days)
        self.cleanup_old_events(events_days)
        
        # Clean up orphaned records
        orphaned_counts = self.cleanup_orphaned_records()
        self.cleanup_stats.update(orphaned_counts)
        
        # Run maintenance operations
        if vacuum:
            vacuum_success = self.vacuum_database()
            self.cleanup_stats["vacuum_success"] = vacuum_success
        
        if analyze:
            analyze_success = self.analyze_database()
            self.cleanup_stats["analyze_success"] = analyze_success
        
        # Get final size info
        size_info = self.get_database_size_info()
        self.cleanup_stats["final_size_info"] = size_info
        
        logger.info(f"Full cleanup completed: {self.cleanup_stats}")
        return self.cleanup_stats


def main():
    """Command line interface for database cleanup."""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="ThreatLens Database Cleanup Utility")
    parser.add_argument("--metrics-days", type=int, default=30,
                       help="Days of processing metrics to keep (default: 30)")
    parser.add_argument("--notification-days", type=int, default=90,
                       help="Days of notification history to keep (default: 90)")
    parser.add_argument("--events-days", type=int, default=365,
                       help="Days of events to keep (default: 365)")
    parser.add_argument("--no-vacuum", action="store_true",
                       help="Skip database VACUUM operation")
    parser.add_argument("--no-analyze", action="store_true",
                       help="Skip database ANALYZE operation")
    parser.add_argument("--size-info", action="store_true",
                       help="Show database size information only")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    cleanup = DatabaseCleanup()
    
    try:
        if args.size_info:
            size_info = cleanup.get_database_size_info()
            print(f"Database Size Information: {size_info}")
            return 0
        
        results = cleanup.run_full_cleanup(
            metrics_days=args.metrics_days,
            notification_days=args.notification_days,
            events_days=args.events_days,
            vacuum=not args.no_vacuum,
            analyze=not args.no_analyze
        )
        
        print(f"Cleanup Results: {results}")
        
        # Return error code if there were errors
        return 1 if results.get("errors") else 0
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())