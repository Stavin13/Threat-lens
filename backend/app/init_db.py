#!/usr/bin/env python3
"""
Database initialization script for ThreatLens.
This script can be run independently to set up the database.
"""
import sys
import logging
from pathlib import Path

# Add the parent directory to the path so we can import app modules
sys.path.append(str(Path(__file__).parent.parent))

from app.database import init_database, check_database_health, get_database_stats

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main function to initialize the database."""
    logger.info("Starting ThreatLens database initialization...")
    
    # Initialize the database
    success = init_database()
    
    if success:
        logger.info("Database initialization completed successfully")
        
        # Perform health check
        health = check_database_health()
        logger.info(f"Database health check: {health['status']}")
        
        if health["status"] == "healthy":
            # Get initial stats
            stats = get_database_stats()
            logger.info(f"Database statistics: {stats}")
            logger.info("Database is ready for use!")
            return 0
        else:
            logger.error(f"Database health check failed: {health.get('error', 'Unknown error')}")
            return 1
    else:
        logger.error("Database initialization failed")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)