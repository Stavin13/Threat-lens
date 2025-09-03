# ThreatLens Integration Tests

This directory contains comprehensive end-to-end integration tests for the ThreatLens security log analysis system.

## Test Structure

### Test Files

- **`test_e2e_integration.py`** - Complete workflow tests from log ingestion to dashboard display
- **`test_performance_integration.py`** - Performance and load testing under various conditions
- **`test_ai_analysis_integration.py`** - AI analysis integration with mocked responses
- **`test_cleanup_utilities.py`** - Test utilities for data cleanup and environment management
- **`run_e2e_tests.py`** - Comprehensive test runner with reporting

### Test Fixtures

- **`fixtures/test_data.py`** - Realistic test data including various log formats and edge cases

## Running Tests

### Prerequisites

1. Install test dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure the ThreatLens application is properly configured:
```bash
python setup_env.py
```

### Quick Start

Run all integration tests:
```bash
python tests/run_e2e_tests.py
```

### Test Categories

#### 1. End-to-End Integration Tests
Tests complete workflows from log ingestion to dashboard display:
```bash
python tests/run_e2e_tests.py --category e2e
```

**Test Coverage:**
- Complete macOS system.log workflow
- Complete macOS auth.log workflow  
- Mixed log format processing
- File upload workflow
- Large log file processing
- Concurrent ingestion
- Error recovery
- Real-time dashboard updates
- Report generation
- API error handling
- System health monitoring
- Edge case log formats
- Data consistency validation

#### 2. Performance Integration Tests
Tests system performance under load:
```bash
python tests/run_e2e_tests.py --category performance
```

**Test Coverage:**
- Large file processing performance
- Concurrent processing performance
- API response time performance
- Database query performance
- Memory usage stability
- Stress testing limits
- Throughput measurement
- Resource cleanup and management

#### 3. AI Analysis Integration Tests
Tests AI analysis with mocked responses:
```bash
python tests/run_e2e_tests.py --category ai
```

**Test Coverage:**
- Realistic security scenarios
- Error handling and fallback mechanisms
- Batch processing
- Partial failures
- Response validation
- Performance monitoring
- Retry logic
- Context preservation
- Concurrent processing

### Specialized Test Runs

#### Smoke Tests
Quick validation of core functionality:
```bash
python tests/run_e2e_tests.py --smoke
```

#### Stress Tests
System behavior under extreme conditions:
```bash
python tests/run_e2e_tests.py --stress
```

#### Environment Validation
Verify test environment setup:
```bash
python tests/run_e2e_tests.py --validate
```

### Using Pytest Directly

Run specific test files:
```bash
pytest tests/test_e2e_integration.py -v
```

Run specific test methods:
```bash
pytest tests/test_e2e_integration.py::TestE2EIntegration::test_complete_macos_system_log_workflow -v
```

Run with coverage:
```bash
pytest tests/ --cov=app --cov-report=html
```

Run performance tests only:
```bash
pytest tests/test_performance_integration.py -v -m performance
```

## Test Data

### Realistic Log Formats

The test fixtures provide realistic log data including:

- **macOS system.log format**: Standard macOS system logs
- **macOS auth.log format**: Authentication and authorization logs
- **Mixed formats**: Various log formats in single ingestion
- **Edge cases**: Unicode, special characters, malformed entries
- **Large datasets**: Performance testing with 1000+ entries

### AI Analysis Scenarios

Tests include realistic security scenarios:

- **High severity**: Failed authentication attempts, security violations
- **Medium severity**: Suspicious network activity, certificate issues
- **Low severity**: Normal system operations, successful logins

## Performance Benchmarks

### Expected Performance Metrics

- **Ingestion**: < 2 seconds for 100 log entries
- **Processing**: < 30 seconds for 500 log entries with AI analysis
- **API Response**: < 500ms average, < 2s maximum
- **Memory Usage**: < 1GB increase during large batch processing
- **Throughput**: > 10 events per second sustained

### Load Testing Scenarios

- **Small batch**: 100 entries, 10s processing time
- **Medium batch**: 500 entries, 30s processing time  
- **Large batch**: 1000 entries, 60s processing time
- **Concurrent**: 10 simultaneous ingestions
- **Stress**: Memory pressure, invalid data, API failures

## Error Scenarios

### Tested Error Conditions

- **Parsing errors**: Invalid log formats, malformed timestamps
- **AI analysis failures**: API timeouts, rate limits, invalid responses
- **Database errors**: Connection failures, constraint violations
- **File system errors**: Permission issues, disk space
- **Network errors**: Connection timeouts, DNS failures

### Recovery Mechanisms

- **Graceful degradation**: Continue processing valid entries
- **Retry logic**: Automatic retry for transient failures
- **Fallback analysis**: Rule-based scoring when AI fails
- **Error logging**: Comprehensive error tracking and reporting

## Test Environment

### Database Isolation

Each test uses an isolated SQLite database to prevent interference:
- Temporary databases created per test
- Automatic cleanup after test completion
- Data integrity verification

### Mock Integration

AI analysis is mocked for consistent testing:
- Realistic severity scoring based on content
- Deterministic responses for reproducible tests
- Error simulation for failure scenarios
- Performance timing simulation

### Resource Management

Comprehensive cleanup utilities:
- Temporary file management
- Database cleanup
- Memory monitoring
- Resource leak detection

## Continuous Integration

### GitHub Actions Integration

```yaml
name: Integration Tests
on: [push, pull_request]
jobs:
  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run integration tests
        run: python tests/run_e2e_tests.py --category all
```

### Test Reporting

- **HTML Coverage Reports**: Generated in `htmlcov/`
- **JSON Test Reports**: Timestamped results with metrics
- **Performance Logs**: Execution times and resource usage
- **Error Analysis**: Detailed failure information

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Ensure SQLite is available
   - Check file permissions
   - Verify database initialization

2. **Import Errors**
   - Verify all dependencies installed
   - Check Python path configuration
   - Ensure app modules are importable

3. **Test Timeouts**
   - Increase timeout values for slow systems
   - Check system resource availability
   - Monitor background processes

4. **Memory Issues**
   - Reduce test dataset sizes
   - Enable garbage collection
   - Monitor system memory usage

### Debug Mode

Run tests with detailed debugging:
```bash
pytest tests/ -v -s --tb=long --log-cli-level=DEBUG
```

### Performance Profiling

Profile test execution:
```bash
pytest tests/test_performance_integration.py --profile
```

## Contributing

### Adding New Tests

1. Follow existing test patterns
2. Use appropriate test fixtures
3. Include proper cleanup
4. Add performance assertions
5. Document test purpose

### Test Guidelines

- **Isolation**: Each test should be independent
- **Cleanup**: Always clean up resources
- **Assertions**: Include meaningful assertions
- **Documentation**: Document complex test scenarios
- **Performance**: Include performance expectations

### Code Coverage

Maintain high test coverage:
- Aim for 80%+ coverage
- Test both success and failure paths
- Include edge cases and error conditions
- Verify integration points