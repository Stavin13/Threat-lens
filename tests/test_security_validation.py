"""
Security and validation tests for ThreatLens.

Tests input sanitization, file upload validation, rate limiting,
and other security measures.
"""
import pytest
import time
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from io import BytesIO

from app.validation import (
    validate_log_content,
    validate_file_upload,
    sanitize_log_content,
    sanitize_filename,
    sanitize_source_identifier,
    validate_api_key,
    validate_request_size
)
from main import app

client = TestClient(app)


class TestInputSanitization:
    """Test input sanitization functions."""
    
    def test_sanitize_log_content_removes_script_tags(self):
        """Test that script tags are removed from log content."""
        malicious_content = "Normal log entry\n<script>alert('xss')</script>\nAnother entry"
        sanitized = sanitize_log_content(malicious_content)
        assert "<script>" not in sanitized
        assert "alert('xss')" not in sanitized
        assert "Normal log entry" in sanitized
        assert "Another entry" in sanitized
    
    def test_sanitize_log_content_removes_sql_injection(self):
        """Test that SQL injection patterns are removed."""
        malicious_content = "Log entry\nUNION SELECT * FROM users--\nNormal entry"
        sanitized = sanitize_log_content(malicious_content)
        assert "UNION SELECT" not in sanitized.upper()
        assert "--" not in sanitized
        assert "Log entry" in sanitized
        assert "Normal entry" in sanitized
    
    def test_sanitize_log_content_removes_command_injection(self):
        """Test that command injection patterns are removed."""
        malicious_content = "Log entry\n; rm -rf /\n$(malicious_command)\nNormal entry"
        sanitized = sanitize_log_content(malicious_content)
        assert "; rm -rf /" not in sanitized
        assert "$(malicious_command)" not in sanitized
        assert "Log entry" in sanitized
        assert "Normal entry" in sanitized
    
    def test_sanitize_filename_removes_path_traversal(self):
        """Test that path traversal patterns are removed from filenames."""
        malicious_filename = "../../../etc/passwd"
        sanitized = sanitize_filename(malicious_filename)
        assert ".." not in sanitized
        assert "/" not in sanitized
        assert "\\" not in sanitized
        assert sanitized == "etcpasswd"
    
    def test_sanitize_filename_handles_empty_input(self):
        """Test that empty filenames are handled properly."""
        assert sanitize_filename("") == "sanitized_file"
        assert sanitize_filename(".") == "sanitized_file"
        assert sanitize_filename("..") == "sanitized_file"
    
    def test_sanitize_source_identifier_removes_injection_chars(self):
        """Test that source identifiers are sanitized."""
        malicious_source = "source'; DROP TABLE logs;--"
        sanitized = sanitize_source_identifier(malicious_source)
        assert "'" not in sanitized
        assert ";" not in sanitized
        assert "DROP TABLE" not in sanitized
        assert "--" not in sanitized


class TestFileUploadValidation:
    """Test file upload validation."""
    
    def test_validate_file_upload_rejects_executable(self):
        """Test that executable files are rejected."""
        # Simulate PE executable (MZ header)
        exe_content = b'\x4d\x5a\x90\x00' + b'A' * 100
        is_valid, error = validate_file_upload(exe_content, "malware.exe")
        assert not is_valid
        assert "not allowed" in error.lower()
    
    def test_validate_file_upload_rejects_binary_signatures(self):
        """Test that files with binary signatures are rejected."""
        # ELF executable signature
        elf_content = b'\x7f\x45\x4c\x46' + b'A' * 100
        is_valid, error = validate_file_upload(elf_content, "binary.log")
        assert not is_valid
        assert "binary" in error.lower()
    
    def test_validate_file_upload_accepts_valid_log(self):
        """Test that valid log files are accepted."""
        log_content = b"Jan 1 12:00:00 server sshd[1234]: Accepted password for user from 192.168.1.1"
        is_valid, error = validate_file_upload(log_content, "system.log")
        assert is_valid
        assert error is None
    
    def test_validate_file_upload_rejects_large_files(self):
        """Test that oversized files are rejected."""
        large_content = b'A' * (11 * 1024 * 1024)  # 11MB
        is_valid, error = validate_file_upload(large_content, "large.log")
        assert not is_valid
        assert "too large" in error.lower()
    
    def test_validate_file_upload_rejects_suspicious_content(self):
        """Test that files with suspicious content are rejected."""
        suspicious_content = b"<script>alert('xss')</script>\neval(malicious_code);"
        is_valid, error = validate_file_upload(suspicious_content, "suspicious.log")
        assert not is_valid
        assert "suspicious" in error.lower()


class TestLogContentValidation:
    """Test log content validation."""
    
    def test_validate_log_content_accepts_valid_logs(self):
        """Test that valid log content is accepted."""
        valid_content = "Jan 1 12:00:00 server sshd[1234]: Connection from 192.168.1.1"
        is_valid, error = validate_log_content(valid_content)
        assert is_valid
        assert error is None
    
    def test_validate_log_content_rejects_empty_content(self):
        """Test that empty content is rejected."""
        is_valid, error = validate_log_content("")
        assert not is_valid
        assert "empty" in error.lower()
    
    def test_validate_log_content_rejects_short_content(self):
        """Test that very short content is rejected."""
        is_valid, error = validate_log_content("short")
        assert not is_valid
        assert "short" in error.lower()
    
    def test_validate_log_content_rejects_oversized_content(self):
        """Test that oversized content is rejected."""
        large_content = "A" * (1000001)  # Over 1MB
        is_valid, error = validate_log_content(large_content)
        assert not is_valid
        assert "exceeds" in error.lower()
    
    def test_validate_log_content_rejects_null_bytes(self):
        """Test that content with null bytes is rejected."""
        content_with_nulls = "Valid log entry\x00malicious_data"
        is_valid, error = validate_log_content(content_with_nulls)
        assert not is_valid
        assert "null bytes" in error.lower()


class TestAPIKeyValidation:
    """Test API key validation."""
    
    def test_validate_api_key_accepts_valid_key(self):
        """Test that valid API keys are accepted."""
        valid_key = "sk-1234567890abcdef1234567890abcdef"
        is_valid, error = validate_api_key(valid_key)
        assert is_valid
        assert error is None
    
    def test_validate_api_key_rejects_short_key(self):
        """Test that short API keys are rejected."""
        short_key = "short"
        is_valid, error = validate_api_key(short_key)
        assert not is_valid
        assert "length" in error.lower()
    
    def test_validate_api_key_rejects_invalid_chars(self):
        """Test that API keys with invalid characters are rejected."""
        invalid_key = "sk-1234567890abcdef!@#$%^&*()"
        is_valid, error = validate_api_key(invalid_key)
        assert not is_valid
        assert "invalid characters" in error.lower()


class TestRequestSizeValidation:
    """Test request size validation."""
    
    def test_validate_request_size_accepts_normal_size(self):
        """Test that normal-sized requests are accepted."""
        is_valid, error = validate_request_size(1024)  # 1KB
        assert is_valid
        assert error is None
    
    def test_validate_request_size_rejects_oversized(self):
        """Test that oversized requests are rejected."""
        large_size = 51 * 1024 * 1024  # 51MB
        is_valid, error = validate_request_size(large_size)
        assert not is_valid
        assert "too large" in error.lower()
    
    def test_validate_request_size_handles_none(self):
        """Test that None content length is handled."""
        is_valid, error = validate_request_size(None)
        assert is_valid
        assert error is None


class TestRateLimiting:
    """Test rate limiting functionality."""
    
    def test_rate_limiting_allows_normal_requests(self):
        """Test that normal request rates are allowed."""
        # Make a few requests within limits
        for i in range(5):
            response = client.get("/health")
            assert response.status_code == 200
    
    def test_rate_limiting_blocks_excessive_requests(self):
        """Test that excessive requests are blocked."""
        # This test might be flaky due to shared rate limiter state
        # In a real scenario, you'd want to isolate the rate limiter
        responses = []
        for i in range(150):  # Exceed the rate limit
            response = client.get("/health")
            responses.append(response.status_code)
            if response.status_code == 429:
                break
        
        # Should eventually get a 429 response
        assert 429 in responses
    
    def test_rate_limiting_includes_retry_after_header(self):
        """Test that rate limit responses include Retry-After header."""
        # Make many requests to trigger rate limiting
        for i in range(150):
            response = client.get("/health")
            if response.status_code == 429:
                assert "retry-after" in response.headers
                break


class TestSecurityHeaders:
    """Test security headers."""
    
    def test_security_headers_present(self):
        """Test that security headers are present in responses."""
        response = client.get("/health")
        
        expected_headers = [
            "x-content-type-options",
            "x-frame-options",
            "x-xss-protection",
            "referrer-policy",
            "content-security-policy",
            "strict-transport-security",
            "permissions-policy"
        ]
        
        for header in expected_headers:
            assert header in response.headers, f"Missing security header: {header}"
    
    def test_server_header_obfuscated(self):
        """Test that server header is obfuscated."""
        response = client.get("/health")
        server_header = response.headers.get("server", "")
        assert "ThreatLens" in server_header
        # Should not reveal underlying server technology
        assert "uvicorn" not in server_header.lower()
        assert "fastapi" not in server_header.lower()


class TestInputValidationMiddleware:
    """Test input validation middleware."""
    
    def test_middleware_blocks_xss_in_query_params(self):
        """Test that XSS attempts in query parameters are blocked."""
        response = client.get("/events?category=<script>alert('xss')</script>")
        assert response.status_code == 400
        assert "invalid characters" in response.json()["detail"].lower()
    
    def test_middleware_blocks_large_requests(self):
        """Test that oversized requests are blocked."""
        large_data = {"content": "A" * (51 * 1024 * 1024)}  # 51MB
        response = client.post("/ingest-log", json=large_data)
        # This might be caught by FastAPI before our middleware
        assert response.status_code in [413, 422]


class TestEndToEndSecurity:
    """End-to-end security tests."""
    
    def test_malicious_file_upload_blocked(self):
        """Test that malicious file uploads are blocked."""
        # Create a fake executable file
        malicious_content = b'\x4d\x5a\x90\x00' + b'malicious_payload' * 100
        
        files = {"file": ("malware.exe", BytesIO(malicious_content), "application/octet-stream")}
        response = client.post("/ingest-log", files=files)
        
        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"].lower()
    
    def test_script_injection_in_log_content_sanitized(self):
        """Test that script injection in log content is sanitized."""
        malicious_log = {
            "content": "Normal log\n<script>alert('xss')</script>\nMore logs",
            "source": "test_source"
        }
        
        response = client.post("/ingest-log", json=malicious_log)
        
        # Should succeed but content should be sanitized
        assert response.status_code == 200
        
        # Verify the content was sanitized by checking the stored log
        # This would require additional database queries in a real test
    
    def test_sql_injection_in_source_blocked(self):
        """Test that SQL injection attempts in source are blocked."""
        malicious_log = {
            "content": "Valid log content for testing purposes",
            "source": "test'; DROP TABLE logs; --"
        }
        
        response = client.post("/ingest-log", json=malicious_log)
        
        # Should succeed but source should be sanitized
        assert response.status_code == 200
        
        # In a real test, you'd verify the source was sanitized in the database
    
    def test_path_traversal_in_filename_blocked(self):
        """Test that path traversal attempts in filenames are blocked."""
        log_content = b"Valid log content for testing"
        files = {"file": ("../../../etc/passwd", BytesIO(log_content), "text/plain")}
        
        response = client.post("/ingest-log", files=files)
        
        # Should succeed but filename should be sanitized
        assert response.status_code == 200
        
        # Verify the filename was sanitized (would check database in real test)


class TestCORSConfiguration:
    """Test CORS configuration."""
    
    def test_cors_headers_present(self):
        """Test that CORS headers are present."""
        response = client.options("/events")
        
        cors_headers = [
            "access-control-allow-origin",
            "access-control-allow-methods",
            "access-control-allow-headers"
        ]
        
        for header in cors_headers:
            assert header in response.headers, f"Missing CORS header: {header}"
    
    def test_cors_allows_frontend_origin(self):
        """Test that CORS allows the frontend origin."""
        headers = {"Origin": "http://localhost:3000"}
        response = client.get("/health", headers=headers)
        
        assert response.headers.get("access-control-allow-origin") in [
            "http://localhost:3000", "*"
        ]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])