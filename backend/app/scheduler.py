"""
Scheduled report generation system for ThreatLens.

This module provides automated daily report generation using APScheduler,
including file management utilities and audit logging.
"""
import logging
import os
import shutil
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.models import Report
from app.report_generator import generate_daily_report, save_report_record

# Configure logging
logger = logging.getLogger(__name__)


class ScheduledReportManager:
    """Manager for scheduled report generation and file management."""
    
    def __init__(self, reports_dir: str = "data/reports", max_reports: int = 30):
        """
        Initialize the scheduled report manager.
        
        Args:
            reports_dir: Directory to store generated reports
            max_reports: Maximum number of reports to keep (for cleanup)
        """
        self.reports_dir = Path(reports_dir)
        self.max_reports = max_reports
        self.scheduler = AsyncIOScheduler()
        self.audit_log = []
        
        # Ensure reports directory exists
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Set up scheduler event listeners
        self.scheduler.add_listener(self._job_executed_listener, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error_listener, EVENT_JOB_ERROR)
        
        logger.info(f"Scheduled report manager initialized with reports directory: {self.reports_dir}")
    
    def start_scheduler(self):
        """Start the scheduler and add the daily report generation job."""
        try:
            # Add daily report generation job at midnight
            self.scheduler.add_job(
                func=self._generate_daily_report_job,
                trigger=CronTrigger(hour=0, minute=0),  # Run at midnight
                id='daily_report_generation',
                name='Daily Security Report Generation',
                replace_existing=True,
                max_instances=1,
                coalesce=True
            )
            
            # Add weekly cleanup job on Sundays at 1 AM
            self.scheduler.add_job(
                func=self._cleanup_old_reports_job,
                trigger=CronTrigger(day_of_week=6, hour=1, minute=0),  # Sunday at 1 AM
                id='weekly_report_cleanup',
                name='Weekly Report Cleanup',
                replace_existing=True,
                max_instances=1,
                coalesce=True
            )
            
            self.scheduler.start()
            logger.info("Scheduler started successfully with daily report generation job")
            
            # Log audit entry
            self._add_audit_entry("scheduler_started", "Scheduler started with daily report job")
            
        except Exception as e:
            logger.error(f"Failed to start scheduler: {str(e)}")
            raise
    
    def stop_scheduler(self):
        """Stop the scheduler gracefully."""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)  # Don't wait in tests
                logger.info("Scheduler stopped successfully")
                
                # Log audit entry
                self._add_audit_entry("scheduler_stopped", "Scheduler stopped")
            
        except Exception as e:
            logger.error(f"Error stopping scheduler: {str(e)}")
    
    async def _generate_daily_report_job(self):
        """
        Scheduled job to generate daily reports.
        This runs at midnight to generate a report for the previous day.
        """
        try:
            # Generate report for yesterday (since this runs at midnight)
            report_date = date.today() - timedelta(days=1)
            
            logger.info(f"Starting scheduled daily report generation for {report_date}")
            
            # Generate the report
            file_path, pdf_bytes = generate_daily_report(report_date)
            
            # Save report record to database
            with get_db_session() as db:
                report_id = save_report_record(db, report_date, file_path)
            
            # Log success
            logger.info(f"Scheduled daily report generated successfully: {report_id} at {file_path}")
            
            # Add audit entry
            self._add_audit_entry(
                "daily_report_generated",
                f"Daily report generated for {report_date}",
                {
                    "report_id": report_id,
                    "report_date": report_date.isoformat(),
                    "file_path": str(file_path),
                    "file_size": len(pdf_bytes)
                }
            )
            
            return {
                "success": True,
                "report_id": report_id,
                "report_date": report_date,
                "file_path": str(file_path)
            }
            
        except Exception as e:
            error_msg = f"Failed to generate scheduled daily report: {str(e)}"
            logger.error(error_msg)
            
            # Add audit entry for failure
            self._add_audit_entry(
                "daily_report_failed",
                error_msg,
                {"error": str(e)}
            )
            
            # Re-raise to trigger retry mechanism if configured
            raise
    
    async def _cleanup_old_reports_job(self):
        """
        Scheduled job to clean up old report files.
        Keeps only the most recent reports based on max_reports setting.
        """
        try:
            logger.info(f"Starting scheduled report cleanup (keeping {self.max_reports} reports)")
            
            # Get all report files sorted by date (newest first)
            report_files = []
            for file_path in self.reports_dir.glob("security_report_*.pdf"):
                try:
                    # Extract date from filename
                    date_str = file_path.stem.split("_")[-1]  # security_report_YYYYMMDD
                    report_date = datetime.strptime(date_str, "%Y%m%d").date()
                    report_files.append((report_date, file_path))
                except (ValueError, IndexError):
                    logger.warning(f"Skipping file with invalid name format: {file_path}")
                    continue
            
            # Sort by date (newest first)
            report_files.sort(key=lambda x: x[0], reverse=True)
            
            # Remove old files
            files_removed = 0
            for i, (report_date, file_path) in enumerate(report_files):
                if i >= self.max_reports:
                    try:
                        file_path.unlink()
                        files_removed += 1
                        logger.info(f"Removed old report file: {file_path}")
                        
                        # Also remove from database
                        with get_db_session() as db:
                            db.query(Report).filter(
                                Report.report_date == report_date,
                                Report.file_path == str(file_path)
                            ).delete()
                            db.commit()
                        
                    except Exception as e:
                        logger.error(f"Failed to remove old report file {file_path}: {str(e)}")
            
            logger.info(f"Report cleanup completed: {files_removed} files removed")
            
            # Add audit entry
            self._add_audit_entry(
                "report_cleanup_completed",
                f"Report cleanup completed: {files_removed} files removed",
                {
                    "files_removed": files_removed,
                    "total_files": len(report_files),
                    "max_reports": self.max_reports
                }
            )
            
            return {
                "success": True,
                "files_removed": files_removed,
                "total_files": len(report_files)
            }
            
        except Exception as e:
            error_msg = f"Failed to cleanup old reports: {str(e)}"
            logger.error(error_msg)
            
            # Add audit entry for failure
            self._add_audit_entry(
                "report_cleanup_failed",
                error_msg,
                {"error": str(e)}
            )
            
            raise
    
    def _job_executed_listener(self, event):
        """Listener for successful job executions."""
        logger.info(f"Scheduled job '{event.job_id}' executed successfully")
    
    def _job_error_listener(self, event):
        """Listener for job execution errors."""
        logger.error(f"Scheduled job '{event.job_id}' failed: {event.exception}")
        
        # Add audit entry for job failure
        self._add_audit_entry(
            "scheduled_job_failed",
            f"Scheduled job '{event.job_id}' failed",
            {
                "job_id": event.job_id,
                "error": str(event.exception),
                "traceback": event.traceback
            }
        )
    
    def _add_audit_entry(self, action: str, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Add an entry to the audit log.
        
        Args:
            action: Action type identifier
            message: Human-readable message
            details: Optional additional details
        """
        audit_entry = {
            "timestamp": datetime.now(),
            "action": action,
            "message": message,
            "details": details or {}
        }
        
        self.audit_log.append(audit_entry)
        
        # Keep only the last 1000 audit entries to prevent memory issues
        if len(self.audit_log) > 1000:
            self.audit_log = self.audit_log[-1000:]
        
        logger.debug(f"Audit entry added: {action} - {message}")
    
    def get_audit_log(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get audit log entries.
        
        Args:
            limit: Optional limit on number of entries to return
            
        Returns:
            List of audit log entries (most recent first)
        """
        entries = list(reversed(self.audit_log))  # Most recent first
        
        if limit:
            entries = entries[:limit]
        
        return entries
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """
        Get current scheduler status and job information.
        
        Returns:
            Dictionary with scheduler status
        """
        if not self.scheduler:
            return {"status": "not_initialized"}
        
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            })
        
        return {
            "status": "running" if self.scheduler.running else "stopped",
            "jobs": jobs,
            "reports_directory": str(self.reports_dir),
            "max_reports": self.max_reports
        }
    
    def trigger_manual_report_generation(self, report_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Manually trigger report generation for a specific date.
        
        Args:
            report_date: Date for the report (defaults to yesterday)
            
        Returns:
            Dictionary with generation results
        """
        if report_date is None:
            report_date = date.today() - timedelta(days=1)
        
        try:
            logger.info(f"Manually triggering report generation for {report_date}")
            
            # Generate the report
            file_path, pdf_bytes = generate_daily_report(report_date)
            
            # Save report record to database
            with get_db_session() as db:
                report_id = save_report_record(db, report_date, file_path)
            
            # Add audit entry
            self._add_audit_entry(
                "manual_report_generated",
                f"Manual report generated for {report_date}",
                {
                    "report_id": report_id,
                    "report_date": report_date.isoformat(),
                    "file_path": str(file_path),
                    "file_size": len(pdf_bytes)
                }
            )
            
            logger.info(f"Manual report generated successfully: {report_id}")
            
            return {
                "success": True,
                "report_id": report_id,
                "report_date": report_date,
                "file_path": str(file_path),
                "file_size": len(pdf_bytes)
            }
            
        except Exception as e:
            error_msg = f"Failed to generate manual report for {report_date}: {str(e)}"
            logger.error(error_msg)
            
            # Add audit entry for failure
            self._add_audit_entry(
                "manual_report_failed",
                error_msg,
                {"error": str(e), "report_date": report_date.isoformat()}
            )
            
            return {
                "success": False,
                "error": str(e),
                "report_date": report_date
            }
    
    def get_report_files_info(self) -> List[Dict[str, Any]]:
        """
        Get information about existing report files.
        
        Returns:
            List of report file information
        """
        report_files = []
        
        for file_path in self.reports_dir.glob("security_report_*.pdf"):
            try:
                # Extract date from filename
                date_str = file_path.stem.split("_")[-1]
                report_date = datetime.strptime(date_str, "%Y%m%d").date()
                
                # Get file stats
                stat = file_path.stat()
                
                report_files.append({
                    "filename": file_path.name,
                    "file_path": str(file_path),
                    "report_date": report_date.isoformat(),
                    "file_size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_ctime),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime)
                })
                
            except (ValueError, IndexError, OSError) as e:
                logger.warning(f"Error processing report file {file_path}: {str(e)}")
                continue
        
        # Sort by report date (newest first)
        report_files.sort(key=lambda x: x["report_date"], reverse=True)
        
        return report_files


# Global scheduler manager instance
scheduler_manager = ScheduledReportManager()


def start_scheduled_reports():
    """Start the scheduled report generation system."""
    scheduler_manager.start_scheduler()


def stop_scheduled_reports():
    """Stop the scheduled report generation system."""
    scheduler_manager.stop_scheduler()


def get_scheduler_status() -> Dict[str, Any]:
    """Get current scheduler status."""
    return scheduler_manager.get_scheduler_status()


def get_audit_log(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get audit log entries."""
    return scheduler_manager.get_audit_log(limit)


def trigger_manual_report(report_date: Optional[date] = None) -> Dict[str, Any]:
    """Manually trigger report generation."""
    return scheduler_manager.trigger_manual_report_generation(report_date)


def get_report_files_info() -> List[Dict[str, Any]]:
    """Get information about existing report files."""
    return scheduler_manager.get_report_files_info()