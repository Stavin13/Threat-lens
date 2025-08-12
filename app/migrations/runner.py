"""
Migration runner for ThreatLens database migrations.
Handles execution of migration scripts with proper error handling and logging.
"""
import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any
import importlib.util

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.migrations.migration_manager import MigrationManager

logger = logging.getLogger(__name__)


class MigrationRunner:
    """Runs database migrations in order with proper error handling."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.manager = MigrationManager(database_url)
        self.migrations_dir = Path(__file__).parent
    
    def discover_migrations(self) -> List[Dict[str, Any]]:
        """Discover all migration files in the migrations directory."""
        migrations = []
        
        # Look for migration files (pattern: NNN_*.py)
        for file_path in self.migrations_dir.glob("[0-9][0-9][0-9]_*.py"):
            if file_path.name == "__init__.py":
                continue
                
            try:
                # Import the migration module
                spec = importlib.util.spec_from_file_location(
                    file_path.stem, file_path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Extract migration info
                migration_info = {
                    "file": file_path.name,
                    "version": getattr(module, "VERSION", file_path.stem),
                    "description": getattr(module, "DESCRIPTION", "No description"),
                    "forward_sql": getattr(module, "FORWARD_SQL", ""),
                    "rollback_sql": getattr(module, "ROLLBACK_SQL", ""),
                    "module": module
                }
                
                migrations.append(migration_info)
                
            except Exception as e:
                logger.error(f"Failed to load migration {file_path}: {e}")
                continue
        
        # Sort by version/filename
        migrations.sort(key=lambda x: x["version"])
        return migrations
    
    def run_migrations(self, target_version: str = None) -> bool:
        """Run all pending migrations up to target version."""
        logger.info("Starting migration run...")
        
        try:
            migrations = self.discover_migrations()
            applied = self.manager.get_applied_migrations()
            
            logger.info(f"Found {len(migrations)} migration files")
            logger.info(f"Currently applied: {len(applied)} migrations")
            
            success_count = 0
            
            for migration in migrations:
                version = migration["version"]
                
                # Stop if we've reached the target version
                if target_version and version > target_version:
                    break
                
                # Skip if already applied
                if version in applied:
                    logger.info(f"Migration {version} already applied, skipping")
                    continue
                
                # Handle special cases for SQLite column additions
                if version == "002_add_realtime_fields":
                    success = self._apply_realtime_fields_migration(migration)
                else:
                    success = self.manager.apply_migration(
                        version=version,
                        description=migration["description"],
                        forward_sql=migration["forward_sql"],
                        rollback_sql=migration["rollback_sql"]
                    )
                
                if success:
                    success_count += 1
                    logger.info(f"Successfully applied migration {version}")
                else:
                    logger.error(f"Failed to apply migration {version}")
                    return False
            
            logger.info(f"Migration run completed. Applied {success_count} new migrations.")
            return True
            
        except Exception as e:
            logger.error(f"Migration run failed: {e}")
            return False
    
    def _apply_realtime_fields_migration(self, migration: Dict[str, Any]) -> bool:
        """Special handling for adding columns to existing tables."""
        version = migration["version"]
        description = migration["description"]
        
        try:
            # Check which columns need to be added
            columns_to_add = []
            
            if not self.manager.column_exists("events", "processing_time"):
                columns_to_add.append("ALTER TABLE events ADD COLUMN processing_time VARCHAR(50) NULL")
            
            if not self.manager.column_exists("events", "realtime_processed"):
                columns_to_add.append("ALTER TABLE events ADD COLUMN realtime_processed INTEGER DEFAULT 0")
            
            if not self.manager.column_exists("events", "notification_sent"):
                columns_to_add.append("ALTER TABLE events ADD COLUMN notification_sent INTEGER DEFAULT 0")
            
            # Build the SQL to execute
            sql_parts = columns_to_add + [
                # Always create indexes (IF NOT EXISTS handles duplicates)
                "CREATE INDEX IF NOT EXISTS idx_events_realtime_processed ON events(realtime_processed)",
                "CREATE INDEX IF NOT EXISTS idx_events_notification_sent ON events(notification_sent)",
                "CREATE INDEX IF NOT EXISTS idx_events_processing_time ON events(processing_time)",
                "CREATE INDEX IF NOT EXISTS idx_events_timestamp_realtime ON events(timestamp, realtime_processed)",
                "CREATE INDEX IF NOT EXISTS idx_events_category_realtime ON events(category, realtime_processed)"
            ]
            
            forward_sql = ";\n".join(sql_parts)
            
            return self.manager.apply_migration(
                version=version,
                description=description,
                forward_sql=forward_sql,
                rollback_sql=migration["rollback_sql"]
            )
            
        except Exception as e:
            logger.error(f"Failed to apply realtime fields migration: {e}")
            return False
    
    def rollback_migration(self, version: str) -> bool:
        """Rollback a specific migration."""
        logger.info(f"Rolling back migration {version}...")
        return self.manager.rollback_migration(version)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current migration status."""
        return self.manager.get_migration_status()
    
    def validate_database_schema(self) -> Dict[str, Any]:
        """Validate that all expected tables and columns exist."""
        validation_results = {
            "valid": True,
            "missing_tables": [],
            "missing_columns": [],
            "errors": []
        }
        
        try:
            # Expected tables
            expected_tables = [
                "raw_logs", "events", "ai_analysis", "reports",
                "monitoring_config", "log_sources", "processing_metrics", "notification_history"
            ]
            
            for table in expected_tables:
                if not self.manager.table_exists(table):
                    validation_results["missing_tables"].append(table)
                    validation_results["valid"] = False
            
            # Expected columns in events table
            expected_event_columns = [
                "processing_time", "realtime_processed", "notification_sent"
            ]
            
            if self.manager.table_exists("events"):
                for column in expected_event_columns:
                    if not self.manager.column_exists("events", column):
                        validation_results["missing_columns"].append(f"events.{column}")
                        validation_results["valid"] = False
            
        except Exception as e:
            validation_results["errors"].append(str(e))
            validation_results["valid"] = False
        
        return validation_results


def main():
    """Main function for running migrations from command line."""
    import argparse
    
    parser = argparse.ArgumentParser(description="ThreatLens Database Migration Runner")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", "sqlite:///./data/threatlens.db"),
                       help="Database URL")
    parser.add_argument("--target", help="Target migration version")
    parser.add_argument("--rollback", help="Rollback specific migration version")
    parser.add_argument("--status", action="store_true", help="Show migration status")
    parser.add_argument("--validate", action="store_true", help="Validate database schema")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    runner = MigrationRunner(args.database_url)
    
    try:
        if args.status:
            status = runner.get_status()
            print(f"Migration Status: {status}")
            return 0
        
        elif args.validate:
            validation = runner.validate_database_schema()
            print(f"Schema Validation: {validation}")
            return 0 if validation["valid"] else 1
        
        elif args.rollback:
            success = runner.rollback_migration(args.rollback)
            return 0 if success else 1
        
        else:
            success = runner.run_migrations(args.target)
            return 0 if success else 1
    
    except Exception as e:
        logger.error(f"Migration runner failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())