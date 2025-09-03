"""
Database utility functions for ThreatLens.
Provides helper functions for database maintenance and real-time processing.
"""
import logging
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_db_session
from app.migrations.cleanup import DatabaseCleanup

logger = logging.getLogger(__name__)


class DatabaseUtils:
    """Utility functions for database operations and maintenance."""
    
    def __init__(self):
        self.cleanup = DatabaseCleanup()
    
    def get_realtime_processing_stats(self) -> Dict[str, Any]:
        """
        Get statistics about real-time processing performance.
        
        Returns:
            Dictionary with processing statistics
        """
        stats = {
            "total_events": 0,
            "realtime_processed": 0,
            "pending_notifications": 0,
            "processing_rate": 0.0,
            "avg_processing_time": 0.0,
            "error": None
        }
        
        try:
            with get_db_session() as db:
                # Total events
                result = db.execute(text("SELECT COUNT(*) FROM events"))
                stats["total_events"] = result.scalar() or 0
                
                # Real-time processed events
                result = db.execute(text("""
                    SELECT COUNT(*) FROM events WHERE realtime_processed = 1
                """))
                stats["realtime_processed"] = result.scalar() or 0
                
                # Pending notifications
                result = db.execute(text("""
                    SELECT COUNT(*) FROM events 
                    WHERE realtime_processed = 1 AND notification_sent = 0
                """))
                stats["pending_notifications"] = result.scalar() or 0
                
                # Processing rate (events per hour in last 24 hours)
                result = db.execute(text("""
                    SELECT COUNT(*) FROM events 
                    WHERE realtime_processed = 1 
                    AND parsed_at > datetime('now', '-24 hours')
                """))
                recent_processed = result.scalar() or 0
                stats["processing_rate"] = recent_processed / 24.0  # per hour
                
                # Average processing time (for events with processing_time)
                result = db.execute(text("""
                    SELECT AVG(CAST(processing_time AS REAL)) 
                    FROM events 
                    WHERE processing_time IS NOT NULL 
                    AND processing_time != ''
                    AND realtime_processed = 1
                """))
                avg_time = result.scalar()
                stats["avg_processing_time"] = float(avg_time) if avg_time else 0.0
                
        except SQLAlchemyError as e:
            stats["error"] = str(e)
            logger.error(f"Failed to get real-time processing stats: {e}")
        
        return stats
    
    def get_log_source_status(self) -> List[Dict[str, Any]]:
        """
        Get status of all configured log sources.
        
        Returns:
            List of log source status dictionaries
        """
        sources = []
        
        try:
            with get_db_session() as db:
                result = db.execute(text("""
                    SELECT source_name, path, enabled, status, last_monitored, 
                           file_size, last_offset, error_message, updated_at
                    FROM log_sources
                    ORDER BY source_name
                """))
                
                for row in result:
                    sources.append({
                        "source_name": row[0],
                        "path": row[1],
                        "enabled": bool(row[2]),
                        "status": row[3],
                        "last_monitored": row[4],
                        "file_size": row[5],
                        "last_offset": row[6],
                        "error_message": row[7],
                        "updated_at": row[8]
                    })
                    
        except SQLAlchemyError as e:
            logger.error(f"Failed to get log source status: {e}")
        
        return sources
    
    def get_notification_metrics(self, days: int = 7) -> Dict[str, Any]:
        """
        Get notification delivery metrics for the specified period.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with notification metrics
        """
        metrics = {
            "total_sent": 0,
            "successful": 0,
            "failed": 0,
            "pending": 0,
            "success_rate": 0.0,
            "by_channel": {},
            "by_type": {},
            "error": None
        }
        
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with get_db_session() as db:
                # Total notifications
                result = db.execute(text("""
                    SELECT COUNT(*) FROM notification_history 
                    WHERE sent_at > :cutoff_date
                """), {"cutoff_date": cutoff_date})
                metrics["total_sent"] = result.scalar() or 0
                
                # By status
                result = db.execute(text("""
                    SELECT status, COUNT(*) FROM notification_history 
                    WHERE sent_at > :cutoff_date
                    GROUP BY status
                """), {"cutoff_date": cutoff_date})
                
                for row in result:
                    status, count = row
                    if status == "sent":
                        metrics["successful"] = count
                    elif status == "failed":
                        metrics["failed"] = count
                    elif status == "pending":
                        metrics["pending"] = count
                
                # Success rate
                if metrics["total_sent"] > 0:
                    metrics["success_rate"] = metrics["successful"] / metrics["total_sent"]
                
                # By channel
                result = db.execute(text("""
                    SELECT channel, COUNT(*) FROM notification_history 
                    WHERE sent_at > :cutoff_date
                    GROUP BY channel
                """), {"cutoff_date": cutoff_date})
                
                metrics["by_channel"] = {row[0]: row[1] for row in result}
                
                # By type
                result = db.execute(text("""
                    SELECT notification_type, COUNT(*) FROM notification_history 
                    WHERE sent_at > :cutoff_date
                    GROUP BY notification_type
                """), {"cutoff_date": cutoff_date})
                
                metrics["by_type"] = {row[0]: row[1] for row in result}
                
        except SQLAlchemyError as e:
            metrics["error"] = str(e)
            logger.error(f"Failed to get notification metrics: {e}")
        
        return metrics
    
    def get_processing_metrics_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get summary of processing metrics for the specified period.
        
        Args:
            hours: Number of hours to analyze
            
        Returns:
            Dictionary with processing metrics summary
        """
        summary = {
            "total_metrics": 0,
            "by_source": {},
            "by_type": {},
            "latest_metrics": [],
            "error": None
        }
        
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            with get_db_session() as db:
                # Total metrics
                result = db.execute(text("""
                    SELECT COUNT(*) FROM processing_metrics 
                    WHERE timestamp > :cutoff_time
                """), {"cutoff_time": cutoff_time})
                summary["total_metrics"] = result.scalar() or 0
                
                # By source
                result = db.execute(text("""
                    SELECT source_name, COUNT(*) FROM processing_metrics 
                    WHERE timestamp > :cutoff_time
                    GROUP BY source_name
                """), {"cutoff_time": cutoff_time})
                
                summary["by_source"] = {row[0]: row[1] for row in result}
                
                # By type
                result = db.execute(text("""
                    SELECT metric_type, COUNT(*) FROM processing_metrics 
                    WHERE timestamp > :cutoff_time
                    GROUP BY metric_type
                """), {"cutoff_time": cutoff_time})
                
                summary["by_type"] = {row[0]: row[1] for row in result}
                
                # Latest metrics (last 10)
                result = db.execute(text("""
                    SELECT source_name, metric_type, metric_value, timestamp 
                    FROM processing_metrics 
                    WHERE timestamp > :cutoff_time
                    ORDER BY timestamp DESC 
                    LIMIT 10
                """), {"cutoff_time": cutoff_time})
                
                summary["latest_metrics"] = [
                    {
                        "source_name": row[0],
                        "metric_type": row[1],
                        "metric_value": row[2],
                        "timestamp": row[3]
                    }
                    for row in result
                ]
                
        except SQLAlchemyError as e:
            summary["error"] = str(e)
            logger.error(f"Failed to get processing metrics summary: {e}")
        
        return summary
    
    def optimize_database_performance(self) -> Dict[str, Any]:
        """
        Run database optimization operations.
        
        Returns:
            Dictionary with optimization results
        """
        results = {
            "vacuum_success": False,
            "analyze_success": False,
            "cleanup_stats": {},
            "error": None
        }
        
        try:
            # Run VACUUM
            results["vacuum_success"] = self.cleanup.vacuum_database()
            
            # Run ANALYZE
            results["analyze_success"] = self.cleanup.analyze_database()
            
            # Run cleanup
            results["cleanup_stats"] = self.cleanup.run_full_cleanup(
                metrics_days=30,
                notification_days=90,
                events_days=365,
                vacuum=False,  # Already done above
                analyze=False  # Already done above
            )
            
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"Database optimization failed: {e}")
        
        return results
    
    def get_database_health_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive database health report.
        
        Returns:
            Dictionary with health report data
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "overall_health": "unknown",
            "database_stats": {},
            "realtime_stats": {},
            "log_sources": [],
            "notification_metrics": {},
            "processing_metrics": {},
            "size_info": {},
            "recommendations": [],
            "errors": []
        }
        
        try:
            # Get basic database stats
            from app.database import get_database_stats
            report["database_stats"] = get_database_stats()
            
            # Get real-time processing stats
            report["realtime_stats"] = self.get_realtime_processing_stats()
            
            # Get log source status
            report["log_sources"] = self.get_log_source_status()
            
            # Get notification metrics
            report["notification_metrics"] = self.get_notification_metrics()
            
            # Get processing metrics
            report["processing_metrics"] = self.get_processing_metrics_summary()
            
            # Get size info
            report["size_info"] = self.cleanup.get_database_size_info()
            
            # Generate recommendations
            recommendations = []
            
            # Check for high error rates
            if report["notification_metrics"].get("success_rate", 1.0) < 0.9:
                recommendations.append("Notification success rate is below 90%. Check notification configuration.")
            
            # Check for large database size
            size_mb = report["size_info"].get("total_size_bytes", 0) / (1024 * 1024)
            if size_mb > 1000:  # 1GB
                recommendations.append(f"Database size is {size_mb:.1f}MB. Consider running cleanup operations.")
            
            # Check for inactive log sources
            inactive_sources = [s for s in report["log_sources"] if not s["enabled"] or s["status"] != "active"]
            if inactive_sources:
                recommendations.append(f"Found {len(inactive_sources)} inactive log sources. Review configuration.")
            
            # Check processing rate
            processing_rate = report["realtime_stats"].get("processing_rate", 0)
            if processing_rate > 1000:  # More than 1000 events per hour
                recommendations.append("High processing rate detected. Monitor system resources.")
            
            report["recommendations"] = recommendations
            
            # Determine overall health
            error_count = len([r for r in [
                report["database_stats"].get("error"),
                report["realtime_stats"].get("error"),
                report["notification_metrics"].get("error"),
                report["processing_metrics"].get("error"),
                report["size_info"].get("error")
            ] if r])
            
            if error_count == 0 and len(recommendations) == 0:
                report["overall_health"] = "excellent"
            elif error_count == 0 and len(recommendations) <= 2:
                report["overall_health"] = "good"
            elif error_count <= 1:
                report["overall_health"] = "fair"
            else:
                report["overall_health"] = "poor"
            
        except Exception as e:
            report["errors"].append(str(e))
            report["overall_health"] = "error"
            logger.error(f"Failed to generate health report: {e}")
        
        return report


def main():
    """Command line interface for database utilities."""
    import argparse
    import json
    import sys
    
    parser = argparse.ArgumentParser(description="ThreatLens Database Utilities")
    parser.add_argument("--realtime-stats", action="store_true",
                       help="Show real-time processing statistics")
    parser.add_argument("--log-sources", action="store_true",
                       help="Show log source status")
    parser.add_argument("--notification-metrics", type=int, default=7,
                       help="Show notification metrics for N days (default: 7)")
    parser.add_argument("--processing-metrics", type=int, default=24,
                       help="Show processing metrics for N hours (default: 24)")
    parser.add_argument("--health-report", action="store_true",
                       help="Generate comprehensive health report")
    parser.add_argument("--optimize", action="store_true",
                       help="Run database optimization")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    utils = DatabaseUtils()
    
    try:
        if args.health_report:
            report = utils.get_database_health_report()
            print(json.dumps(report, indent=2, default=str))
        elif args.realtime_stats:
            stats = utils.get_realtime_processing_stats()
            print(json.dumps(stats, indent=2, default=str))
        elif args.log_sources:
            sources = utils.get_log_source_status()
            print(json.dumps(sources, indent=2, default=str))
        elif args.optimize:
            results = utils.optimize_database_performance()
            print(json.dumps(results, indent=2, default=str))
        else:
            # Default to showing help
            parser.print_help()
            return 1
        
        return 0
        
    except Exception as e:
        logger.error(f"Database utilities failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())