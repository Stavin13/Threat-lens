#!/usr/bin/env python3
"""
ThreatLens Demo Setup Script

This script sets up the demo environment and loads sample data for ThreatLens.
It provides an easy way to get started with the demo without manual configuration.
"""

import os
import sys
import subprocess
import asyncio
from pathlib import Path
from typing import Dict, Any


class DemoSetup:
    """Handles demo environment setup and configuration."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.data_dir = self.project_root / "data"
        self.sample_logs_dir = self.data_dir / "sample_logs"
        self.reports_dir = self.data_dir / "reports"
        
    def check_prerequisites(self) -> Dict[str, bool]:
        """Check if all prerequisites are met."""
        checks = {}
        
        # Check Python version
        checks["python_version"] = sys.version_info >= (3, 8)
        
        # Check if virtual environment is active
        checks["virtual_env"] = hasattr(sys, 'real_prefix') or (
            hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
        )
        
        # Check if requirements are installed
        try:
            import fastapi
            import groq
            import sqlalchemy
            checks["dependencies"] = True
        except ImportError:
            checks["dependencies"] = False
        
        # Check if .env file exists
        checks["env_file"] = (self.project_root / ".env").exists()
        
        # Check if sample log files exist
        checks["sample_logs"] = (
            (self.sample_logs_dir / "macos_system.log").exists() and
            (self.sample_logs_dir / "macos_auth.log").exists()
        )
        
        return checks
    
    def setup_directories(self):
        """Create necessary directories."""
        print("Setting up directories...")
        
        directories = [
            self.data_dir,
            self.sample_logs_dir,
            self.reports_dir
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"  ✓ Created {directory}")
    
    def setup_environment(self):
        """Set up environment configuration."""
        print("Setting up environment configuration...")
        
        env_file = self.project_root / ".env"
        env_example = self.project_root / ".env.example"
        
        if not env_file.exists() and env_example.exists():
            # Copy .env.example to .env
            with open(env_example, 'r') as src, open(env_file, 'w') as dst:
                dst.write(src.read())
            print("  ✓ Created .env file from .env.example")
            print("  ⚠️  Please edit .env file and add your Groq API key")
        elif env_file.exists():
            print("  ✓ .env file already exists")
        else:
            print("  ⚠️  No .env.example file found")
    
    def initialize_database(self):
        """Initialize the database."""
        print("Initializing database...")
        
        try:
            # Import and run database initialization
            sys.path.append(str(self.project_root))
            from app.init_db import main as init_db_main
            
            init_db_main()
            print("  ✓ Database initialized successfully")
            
        except Exception as e:
            print(f"  ❌ Database initialization failed: {e}")
            return False
        
        return True
    
    async def load_demo_data(self, clear_existing: bool = False):
        """Load demo data using the demo data loader."""
        print("Loading demo data...")
        
        try:
            # Import and run demo data loader
            sys.path.append(str(self.project_root))
            from demo_data_loader import DemoDataLoader
            
            loader = DemoDataLoader()
            results = await loader.process_demo_data(clear_existing=clear_existing)
            
            if "error" in results:
                print(f"  ❌ Demo data loading failed: {results['error']}")
                return False
            
            print(f"  ✓ Loaded {results['total_events']} events")
            print(f"  ✓ Analyzed {results['analyzed_events']} events")
            print(f"  ✓ Success rate: {(results['analyzed_events']/results['total_events']*100):.1f}%")
            
            return True
            
        except Exception as e:
            print(f"  ❌ Demo data loading failed: {e}")
            return False
    
    def print_setup_summary(self, checks: Dict[str, bool]):
        """Print setup summary and next steps."""
        print("\n" + "="*60)
        print("DEMO SETUP SUMMARY")
        print("="*60)
        
        print("\nPrerequisite Checks:")
        for check, status in checks.items():
            status_icon = "✓" if status else "❌"
            check_name = check.replace("_", " ").title()
            print(f"  {status_icon} {check_name}")
        
        all_good = all(checks.values())
        
        if all_good:
            print("\n🎉 Demo setup completed successfully!")
            print("\nNext Steps:")
            print("1. Start the FastAPI server:")
            print("   python main.py")
            print("\n2. Start the React frontend (in another terminal):")
            print("   cd frontend")
            print("   npm install")
            print("   npm start")
            print("\n3. Open the demo:")
            print("   Backend API: http://localhost:8000")
            print("   Frontend Dashboard: http://localhost:3000")
            print("   API Documentation: http://localhost:8000/docs")
            print("\n4. View demo walkthrough:")
            print("   cat DEMO_WALKTHROUGH.md")
        else:
            print("\n⚠️  Setup completed with issues. Please address the failed checks above.")
            
            if not checks["dependencies"]:
                print("\nTo install dependencies:")
                print("   pip install -r requirements.txt")
            
            if not checks["env_file"]:
                print("\nTo set up environment:")
                print("   cp .env.example .env")
                print("   # Edit .env and add your Groq API key")
            
            if not checks["virtual_env"]:
                print("\nRecommended: Use a virtual environment:")
                print("   python -m venv venv")
                print("   source venv/bin/activate  # On Windows: venv\\Scripts\\activate")
        
        print("="*60)
    
    def run_interactive_setup(self):
        """Run interactive setup with user prompts."""
        print("ThreatLens Demo Setup")
        print("="*30)
        
        # Check prerequisites
        print("\nChecking prerequisites...")
        checks = self.check_prerequisites()
        
        # Setup directories
        self.setup_directories()
        
        # Setup environment
        self.setup_environment()
        
        # Initialize database
        if not self.initialize_database():
            print("❌ Database initialization failed. Please check your configuration.")
            return
        
        # Ask about demo data
        if checks["sample_logs"]:
            clear_existing = input("\nDemo data already exists. Clear existing data? (y/N): ").lower().startswith('y')
        else:
            clear_existing = False
            print("\nNo existing demo data found. Loading fresh demo data...")
        
        # Load demo data
        success = asyncio.run(self.load_demo_data(clear_existing=clear_existing))
        
        if success:
            # Update checks
            checks["demo_data"] = True
        
        # Print summary
        self.print_setup_summary(checks)


def main():
    """Main function to run demo setup."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Set up ThreatLens demo environment")
    parser.add_argument("--auto", action="store_true", 
                       help="Run setup automatically without prompts")
    parser.add_argument("--clear-data", action="store_true",
                       help="Clear existing demo data")
    
    args = parser.parse_args()
    
    setup = DemoSetup()
    
    if args.auto:
        # Automated setup
        print("Running automated demo setup...")
        
        checks = setup.check_prerequisites()
        setup.setup_directories()
        setup.setup_environment()
        
        if setup.initialize_database():
            success = asyncio.run(setup.load_demo_data(clear_existing=args.clear_data))
            if success:
                checks["demo_data"] = True
        
        setup.print_setup_summary(checks)
    else:
        # Interactive setup
        setup.run_interactive_setup()


if __name__ == "__main__":
    main()