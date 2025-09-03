"""
End-to-End Integration Test Runner for ThreatLens

Comprehensive test runner that executes all integration tests with
proper setup, teardown, and reporting.
"""
import pytest
import sys
import os
import time
import json
from datetime import datetime, timezone
from typing import List, Dict, Any
import argparse

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_cleanup_utilities import TestCleanupUtilities


class E2ETestRunner:
    """Comprehensive end-to-end test runner."""
    
    def __init__(self):
        self.cleanup_utils = TestCleanupUtilities()
        self.test_results = {}
        self.start_time = None
        self.end_time = None
    
    def run_all_tests(self, verbose: bool = True, fail_fast: bool = False, 
                     test_pattern: str = None) -> Dict[str, Any]:
        """Run all end-to-end integration tests."""
        print("=" * 80)
        print("ThreatLens End-to-End Integration Test Suite")
        print("=" * 80)
        
        self.start_time = time.time()
        
        # Define test modules to run
        test_modules = [
            "tests/test_e2e_integration.py",
            "tests/test_performance_integration.py", 
            "tests/test_ai_analysis_integration.py"
        ]
        
        # Filter tests if pattern provided
        if test_pattern:
            test_modules = [module for module in test_modules if test_pattern in module]
        
        # Prepare pytest arguments
        pytest_args = []
        
        if verbose:
            pytest_args.append("-v")
        
        if fail_fast:
            pytest_args.append("-x")
        
        # Add coverage reporting
        pytest_args.extend([
            "--cov=app",
            "--cov-report=html:htmlcov",
            "--cov-report=term-missing"
        ])
        
        # Add test modules
        pytest_args.extend(test_modules)
        
        try:
            # Run tests
            print(f"Running tests: {', '.join(test_modules)}")
            print(f"Arguments: {' '.join(pytest_args)}")
            print("-" * 80)
            
            exit_code = pytest.main(pytest_args)
            
            self.end_time = time.time()
            
            # Generate test report
            self._generate_test_report(exit_code)
            
            return {
                "exit_code": exit_code,
                "duration": self.end_time - self.start_time,
                "test_results": self.test_results
            }
            
        except Exception as e:
            print(f"Error running tests: {e}")
            return {
                "exit_code": 1,
                "error": str(e),
                "duration": time.time() - self.start_time if self.start_time else 0
            }
        
        finally:
            # Cleanup
            self.cleanup_utils.cleanup_temp_files()
    
    def run_specific_test_category(self, category: str) -> Dict[str, Any]:
        """Run specific category of tests."""
        category_mapping = {
            "e2e": ["tests/test_e2e_integration.py"],
            "performance": ["tests/test_performance_integration.py"],
            "ai": ["tests/test_ai_analysis_integration.py"],
            "all": [
                "tests/test_e2e_integration.py",
                "tests/test_performance_integration.py",
                "tests/test_ai_analysis_integration.py"
            ]
        }
        
        if category not in category_mapping:
            raise ValueError(f"Unknown test category: {category}")
        
        test_modules = category_mapping[category]
        
        print(f"Running {category} tests...")
        
        pytest_args = ["-v"] + test_modules
        exit_code = pytest.main(pytest_args)
        
        return {"exit_code": exit_code, "category": category}
    
    def run_smoke_tests(self) -> Dict[str, Any]:
        """Run quick smoke tests to verify basic functionality."""
        print("Running smoke tests...")
        
        smoke_tests = [
            "tests/test_e2e_integration.py::TestE2EIntegration::test_complete_macos_system_log_workflow",
            "tests/test_e2e_integration.py::TestE2EIntegration::test_api_error_handling_workflow",
            "tests/test_performance_integration.py::TestPerformanceIntegration::test_api_response_time_performance"
        ]
        
        pytest_args = ["-v", "--tb=short"] + smoke_tests
        exit_code = pytest.main(pytest_args)
        
        return {"exit_code": exit_code, "test_type": "smoke"}
    
    def run_stress_tests(self) -> Dict[str, Any]:
        """Run stress tests for system limits."""
        print("Running stress tests...")
        
        stress_tests = [
            "tests/test_performance_integration.py::TestPerformanceIntegration::test_large_file_processing_performance",
            "tests/test_performance_integration.py::TestPerformanceIntegration::test_concurrent_processing_performance",
            "tests/test_performance_integration.py::TestPerformanceIntegration::test_stress_testing_limits"
        ]
        
        pytest_args = ["-v", "--tb=short"] + stress_tests
        exit_code = pytest.main(pytest_args)
        
        return {"exit_code": exit_code, "test_type": "stress"}
    
    def validate_test_environment(self) -> Dict[str, Any]:
        """Validate that the test environment is properly set up."""
        print("Validating test environment...")
        
        validation_results = {
            "environment_valid": True,
            "issues": []
        }
        
        # Check required modules
        required_modules = [
            "fastapi", "sqlalchemy", "pytest", "psutil", 
            "app.database", "app.models", "app.schemas"
        ]
        
        for module in required_modules:
            try:
                __import__(module)
            except ImportError as e:
                validation_results["issues"].append(f"Missing module: {module} - {e}")
                validation_results["environment_valid"] = False
        
        # Check database connectivity
        try:
            from app.database import init_database, check_database_health
            
            if not init_database():
                validation_results["issues"].append("Database initialization failed")
                validation_results["environment_valid"] = False
            
            health = check_database_health()
            if health.get("status") != "healthy":
                validation_results["issues"].append(f"Database health check failed: {health}")
                validation_results["environment_valid"] = False
                
        except Exception as e:
            validation_results["issues"].append(f"Database validation error: {e}")
            validation_results["environment_valid"] = False
        
        # Check file system permissions
        try:
            import tempfile
            test_file = tempfile.NamedTemporaryFile(delete=False)
            test_file.write(b"test")
            test_file.close()
            os.unlink(test_file.name)
        except Exception as e:
            validation_results["issues"].append(f"File system permission error: {e}")
            validation_results["environment_valid"] = False
        
        if validation_results["environment_valid"]:
            print("✓ Test environment validation passed")
        else:
            print("✗ Test environment validation failed:")
            for issue in validation_results["issues"]:
                print(f"  - {issue}")
        
        return validation_results
    
    def _generate_test_report(self, exit_code: int):
        """Generate comprehensive test report."""
        duration = self.end_time - self.start_time
        
        report = {
            "test_run": {
                "start_time": datetime.fromtimestamp(self.start_time, timezone.utc).isoformat(),
                "end_time": datetime.fromtimestamp(self.end_time, timezone.utc).isoformat(),
                "duration_seconds": duration,
                "exit_code": exit_code,
                "status": "PASSED" if exit_code == 0 else "FAILED"
            },
            "environment": {
                "python_version": sys.version,
                "platform": sys.platform,
                "working_directory": os.getcwd()
            },
            "summary": {
                "total_duration": f"{duration:.2f} seconds",
                "result": "All tests passed" if exit_code == 0 else "Some tests failed"
            }
        }
        
        # Save report to file
        report_file = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            
            print(f"\nTest report saved to: {report_file}")
            
        except Exception as e:
            print(f"Error saving test report: {e}")
        
        # Print summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"Status: {report['test_run']['status']}")
        print(f"Duration: {report['summary']['total_duration']}")
        print(f"Exit Code: {exit_code}")
        
        if exit_code == 0:
            print("🎉 All integration tests passed!")
        else:
            print("❌ Some integration tests failed. Check the output above for details.")
        
        print("=" * 80)


def main():
    """Main entry point for test runner."""
    parser = argparse.ArgumentParser(description="ThreatLens E2E Integration Test Runner")
    
    parser.add_argument(
        "--category", 
        choices=["e2e", "performance", "ai", "all"],
        default="all",
        help="Test category to run"
    )
    
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run smoke tests only"
    )
    
    parser.add_argument(
        "--stress",
        action="store_true", 
        help="Run stress tests only"
    )
    
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate test environment only"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Verbose output"
    )
    
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first failure"
    )
    
    parser.add_argument(
        "--pattern",
        help="Test file pattern to filter"
    )
    
    args = parser.parse_args()
    
    runner = E2ETestRunner()
    
    try:
        if args.validate:
            result = runner.validate_test_environment()
            sys.exit(0 if result["environment_valid"] else 1)
        
        elif args.smoke:
            result = runner.run_smoke_tests()
            sys.exit(result["exit_code"])
        
        elif args.stress:
            result = runner.run_stress_tests()
            sys.exit(result["exit_code"])
        
        else:
            if args.category != "all":
                result = runner.run_specific_test_category(args.category)
            else:
                result = runner.run_all_tests(
                    verbose=args.verbose,
                    fail_fast=args.fail_fast,
                    test_pattern=args.pattern
                )
            
            sys.exit(result["exit_code"])
    
    except KeyboardInterrupt:
        print("\nTest run interrupted by user")
        sys.exit(130)
    
    except Exception as e:
        print(f"Error running tests: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()