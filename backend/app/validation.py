"""
Validation functions for event data integrity and API input validation.
"""
import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from .schemas import EventCategory, SeverityLevel, ParsedEvent


def validate_log_content(content: str) -> Tuple[bool, Optional[str]]:
    """
    Validate raw log content for basic format and safety.
    
    Args:
        content: Raw log content string
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not content or not isinstance(content, str):
        return False, "Log content must be a non-empty string"
    
    # Check minimum length
    if len(content.strip()) < 10:
        return False, "Log content too short to be meaningful"
    
    # Check maximum length (1MB limit)
    if len(content) > 1000000:
        return False, "Log content exceeds maximum size limit (1MB)"
    
    # Check for null bytes or excessive control characters
    if '\x00' in content:
        return False, "Log content contains null bytes"
    
    # Count control characters (excluding newlines, tabs, carriage returns)
    control_chars = sum(1 for c in content if ord(c) < 32 and c not in '\n\t\r')
    if control_chars > len(content) * 0.1:  # More than 10% control characters
        return False, "Log content contains excessive control characters"
    
    return True, None


def validate_event_timestamp(timestamp: datetime) -> Tuple[bool, Optional[str]]:
    """
    Validate event timestamp for reasonable bounds.
    
    Args:
        timestamp: Event timestamp to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(timestamp, datetime):
        return False, "Timestamp must be a datetime object"
    
    # Check if timestamp is not too far in the future (allow 1 hour for clock skew)
    future_limit = datetime.now() + timedelta(hours=1)
    if timestamp > future_limit:
        return False, "Event timestamp is too far in the future"
    
    # Check if timestamp is not too far in the past (10 years)
    past_limit = datetime.now() - timedelta(days=3650)
    if timestamp < past_limit:
        return False, "Event timestamp is too far in the past"
    
    return True, None


def validate_event_category(category: str) -> Tuple[bool, Optional[str]]:
    """
    Validate event category against allowed values.
    
    Args:
        category: Event category string
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(category, str):
        return False, "Category must be a string"
    
    try:
        EventCategory(category.lower())
        return True, None
    except ValueError:
        valid_categories = [cat.value for cat in EventCategory]
        return False, f"Invalid category. Must be one of: {', '.join(valid_categories)}"


def validate_severity_score(score: int) -> Tuple[bool, Optional[str]]:
    """
    Validate AI analysis severity score.
    
    Args:
        score: Severity score to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(score, int):
        return False, "Severity score must be an integer"
    
    if score < 1 or score > 10:
        return False, "Severity score must be between 1 and 10"
    
    return True, None


def validate_recommendations_list(recommendations: List[str]) -> Tuple[bool, Optional[str]]:
    """
    Validate AI analysis recommendations list.
    
    Args:
        recommendations: List of recommendation strings
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(recommendations, list):
        return False, "Recommendations must be a list"
    
    if len(recommendations) == 0:
        return False, "At least one recommendation is required"
    
    if len(recommendations) > 10:
        return False, "Too many recommendations (maximum 10)"
    
    for i, rec in enumerate(recommendations):
        if not isinstance(rec, str):
            return False, f"Recommendation {i+1} must be a string"
        
        if not rec.strip():
            return False, f"Recommendation {i+1} cannot be empty"
        
        if len(rec.strip()) < 5:
            return False, f"Recommendation {i+1} is too short (minimum 5 characters)"
        
        if len(rec) > 500:
            return False, f"Recommendation {i+1} is too long (maximum 500 characters)"
    
    return True, None


def validate_source_identifier(source: str) -> Tuple[bool, Optional[str]]:
    """
    Validate source identifier format.
    
    Args:
        source: Source identifier string
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(source, str):
        return False, "Source must be a string"
    
    if not source.strip():
        return False, "Source cannot be empty"
    
    if len(source) > 255:
        return False, "Source identifier too long (maximum 255 characters)"
    
    # Allow alphanumeric, underscores, hyphens, dots, and colons
    if not re.match(r'^[a-zA-Z0-9_\-\.:]+$', source):
        return False, "Source must contain only alphanumeric characters, underscores, hyphens, dots, and colons"
    
    return True, None


def validate_parsed_event(event_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Comprehensive validation of parsed event data.
    
    Args:
        event_data: Dictionary containing event data
        
    Returns:
        Tuple of (is_valid, list_of_error_messages)
    """
    errors = []
    
    # Required fields
    required_fields = ['id', 'raw_log_id', 'timestamp', 'source', 'message', 'category']
    for field in required_fields:
        if field not in event_data:
            errors.append(f"Missing required field: {field}")
    
    if errors:  # Don't continue if required fields are missing
        return False, errors
    
    # Validate individual fields
    if not isinstance(event_data['id'], str) or not event_data['id'].strip():
        errors.append("Event ID must be a non-empty string")
    
    if not isinstance(event_data['raw_log_id'], str) or not event_data['raw_log_id'].strip():
        errors.append("Raw log ID must be a non-empty string")
    
    # Validate timestamp
    try:
        if isinstance(event_data['timestamp'], str):
            timestamp = datetime.fromisoformat(event_data['timestamp'].replace('Z', '+00:00'))
        else:
            timestamp = event_data['timestamp']
        
        is_valid, error = validate_event_timestamp(timestamp)
        if not is_valid:
            errors.append(f"Invalid timestamp: {error}")
    except (ValueError, TypeError) as e:
        errors.append(f"Invalid timestamp format: {str(e)}")
    
    # Validate source
    is_valid, error = validate_source_identifier(event_data['source'])
    if not is_valid:
        errors.append(f"Invalid source: {error}")
    
    # Validate message
    if not isinstance(event_data['message'], str) or not event_data['message'].strip():
        errors.append("Event message must be a non-empty string")
    elif len(event_data['message']) > 10000:
        errors.append("Event message too long (maximum 10000 characters)")
    
    # Validate category
    is_valid, error = validate_event_category(event_data['category'])
    if not is_valid:
        errors.append(f"Invalid category: {error}")
    
    return len(errors) == 0, errors


def validate_ai_analysis_data(analysis_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Comprehensive validation of AI analysis data.
    
    Args:
        analysis_data: Dictionary containing AI analysis data
        
    Returns:
        Tuple of (is_valid, list_of_error_messages)
    """
    errors = []
    
    # Required fields
    required_fields = ['id', 'event_id', 'severity_score', 'explanation', 'recommendations']
    for field in required_fields:
        if field not in analysis_data:
            errors.append(f"Missing required field: {field}")
    
    if errors:  # Don't continue if required fields are missing
        return False, errors
    
    # Validate individual fields
    if not isinstance(analysis_data['id'], str) or not analysis_data['id'].strip():
        errors.append("Analysis ID must be a non-empty string")
    
    if not isinstance(analysis_data['event_id'], str) or not analysis_data['event_id'].strip():
        errors.append("Event ID must be a non-empty string")
    
    # Validate severity score
    is_valid, error = validate_severity_score(analysis_data['severity_score'])
    if not is_valid:
        errors.append(f"Invalid severity score: {error}")
    
    # Validate explanation
    if not isinstance(analysis_data['explanation'], str):
        errors.append("Explanation must be a string")
    elif not analysis_data['explanation'].strip():
        errors.append("Explanation cannot be empty")
    elif len(analysis_data['explanation'].strip()) < 10:
        errors.append("Explanation too short (minimum 10 characters)")
    elif len(analysis_data['explanation']) > 5000:
        errors.append("Explanation too long (maximum 5000 characters)")
    
    # Validate recommendations
    recommendations = analysis_data['recommendations']
    if isinstance(recommendations, str):
        # Handle JSON string format
        try:
            recommendations = json.loads(recommendations)
        except json.JSONDecodeError:
            errors.append("Invalid recommendations format (must be JSON array or list)")
            return len(errors) == 0, errors
    
    is_valid, error = validate_recommendations_list(recommendations)
    if not is_valid:
        errors.append(f"Invalid recommendations: {error}")
    
    return len(errors) == 0, errors


def sanitize_log_content(content: str) -> str:
    """
    Sanitize log content by removing or replacing potentially harmful characters.
    
    Args:
        content: Raw log content
        
    Returns:
        Sanitized log content
    """
    if not isinstance(content, str):
        return ""
    
    # Remove null bytes
    content = content.replace('\x00', '')
    
    # Remove other control characters except newlines, tabs, and carriage returns
    sanitized = re.sub(r'[\x01-\x08\x0B\x0C\x0E-\x1F\x7F]', '', content)
    
    # Remove potential script injection patterns
    # Remove HTML/XML tags
    sanitized = re.sub(r'<[^>]*>', '', sanitized)
    
    # Remove JavaScript-like patterns
    sanitized = re.sub(r'javascript:', '', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'on\w+\s*=', '', sanitized, flags=re.IGNORECASE)
    
    # Remove SQL injection patterns
    sql_patterns = [
        r'(\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b)',
        r'(--|#|/\*|\*/)',
        r'(\bor\b\s+\d+\s*=\s*\d+)',
        r'(\band\b\s+\d+\s*=\s*\d+)'
    ]
    for pattern in sql_patterns:
        sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
    
    # Remove potential command injection patterns
    cmd_patterns = [
        r'[;&|`$(){}[\]\\]',  # Shell metacharacters
        r'\$\([^)]*\)',       # Command substitution
        r'`[^`]*`'            # Backtick command substitution
    ]
    for pattern in cmd_patterns:
        sanitized = re.sub(pattern, '', sanitized)
    
    # Normalize line endings
    sanitized = re.sub(r'\r\n|\r', '\n', sanitized)
    
    # Remove excessive whitespace but preserve log structure
    lines = sanitized.split('\n')
    cleaned_lines = []
    for line in lines:
        # Keep the line structure but trim excessive spaces
        cleaned_line = re.sub(r'[ \t]+', ' ', line.strip())
        if cleaned_line:  # Only keep non-empty lines
            cleaned_lines.append(cleaned_line)
    
    return '\n'.join(cleaned_lines)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal and other attacks.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    if not isinstance(filename, str):
        return "unknown_file"
    
    # Remove directory traversal patterns
    filename = filename.replace('..', '')
    filename = filename.replace('/', '')
    filename = filename.replace('\\', '')
    
    # Remove null bytes and control characters
    filename = re.sub(r'[\x00-\x1F\x7F]', '', filename)
    
    # Keep only alphanumeric, dots, hyphens, and underscores
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    
    # Ensure filename is not empty and not too long
    if not filename or filename == '.' or filename == '..':
        filename = "sanitized_file"
    
    if len(filename) > 255:
        filename = filename[:255]
    
    return filename


def sanitize_source_identifier(source: str) -> str:
    """
    Sanitize source identifier to prevent injection attacks.
    
    Args:
        source: Original source identifier
        
    Returns:
        Sanitized source identifier
    """
    if not isinstance(source, str):
        return "unknown_source"
    
    # Remove null bytes and control characters
    source = re.sub(r'[\x00-\x1F\x7F]', '', source)
    
    # Remove potential injection patterns
    source = re.sub(r'[<>"\';\\]', '', source)
    
    # Remove SQL keywords and patterns
    sql_keywords = [
        r'\bDROP\b', r'\bTABLE\b', r'\bSELECT\b', r'\bINSERT\b', r'\bUPDATE\b',
        r'\bDELETE\b', r'\bUNION\b', r'\bWHERE\b', r'\bFROM\b', r'\bINTO\b',
        r'\bVALUES\b', r'\bCREATE\b', r'\bALTER\b', r'\bEXEC\b', r'\bEXECUTE\b'
    ]
    for keyword in sql_keywords:
        source = re.sub(keyword, '', source, flags=re.IGNORECASE)
    
    # Remove comment patterns
    source = re.sub(r'--.*$', '', source, flags=re.MULTILINE)
    source = re.sub(r'/\*.*?\*/', '', source, flags=re.DOTALL)
    
    # Limit length
    if len(source) > 255:
        source = source[:255]
    
    # Clean up extra spaces
    source = re.sub(r'\s+', ' ', source).strip()
    
    # Ensure not empty
    if not source:
        source = "sanitized_source"
    
    return source


def validate_file_upload(file_content: bytes, filename: str) -> Tuple[bool, Optional[str]]:
    """
    Validate uploaded file for security and format requirements.
    
    Args:
        file_content: Raw file content as bytes
        filename: Original filename
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check file size (max 10MB)
    max_size = 10 * 1024 * 1024  # 10MB
    if len(file_content) > max_size:
        return False, f"File too large (maximum {max_size // (1024*1024)}MB)"
    
    # Check if file is empty
    if len(file_content) == 0:
        return False, "File is empty"
    
    # Validate filename
    if not filename or not isinstance(filename, str):
        return False, "Invalid filename"
    
    # Sanitize filename
    sanitized_filename = sanitize_filename(filename)
    
    # Check for potentially dangerous file extensions
    dangerous_extensions = [
        '.exe', '.bat', '.cmd', '.com', '.scr', '.pif', '.vbs', '.js', '.jar',
        '.msi', '.deb', '.rpm', '.dmg', '.app', '.ps1', '.sh', '.php', '.asp',
        '.aspx', '.jsp', '.py', '.rb', '.pl', '.cgi'
    ]
    file_ext = sanitized_filename.lower().split('.')[-1] if '.' in sanitized_filename else ''
    if f'.{file_ext}' in dangerous_extensions:
        return False, f"File type not allowed: .{file_ext}"
    
    # Check for allowed extensions
    allowed_extensions = ['.log', '.txt', '.out', '.csv', '.json']
    if f'.{file_ext}' not in allowed_extensions:
        return False, f"File type not supported. Allowed types: {', '.join(allowed_extensions)}"
    
    # Check for binary file signatures (magic bytes)
    if len(file_content) >= 4:
        # Check for common executable signatures
        magic_bytes = file_content[:4]
        dangerous_signatures = [
            b'\x4d\x5a',  # PE executable (MZ)
            b'\x7f\x45\x4c\x46',  # ELF executable
            b'\xca\xfe\xba\xbe',  # Java class file
            b'\x50\x4b\x03\x04',  # ZIP file (could contain executables)
            b'\x1f\x8b\x08',  # GZIP file
            b'\x42\x5a\x68',  # BZIP2 file
        ]
        
        for signature in dangerous_signatures:
            if file_content.startswith(signature):
                return False, "Binary or compressed files are not allowed"
    
    # Check for suspicious patterns in file content
    try:
        # Try to decode as text with multiple encodings
        content_str = None
        encodings = ['utf-8', 'latin-1', 'ascii', 'utf-16']
        
        for encoding in encodings:
            try:
                content_str = file_content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        
        if content_str is None:
            return False, "File encoding not supported"
        
        # Check for suspicious patterns
        suspicious_patterns = [
            r'<script[^>]*>',  # JavaScript
            r'eval\s*\(',      # Code evaluation
            r'exec\s*\(',      # Code execution
            r'system\s*\(',    # System calls
            r'shell_exec\s*\(',  # Shell execution
            r'passthru\s*\(',  # Command execution
            r'base64_decode\s*\(',  # Base64 decoding (often used in attacks)
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, content_str, re.IGNORECASE):
                return False, f"File contains suspicious content pattern: {pattern}"
        
        # Validate as log content
        return validate_log_content(content_str)
        
    except Exception as e:
        return False, f"Failed to process file content: {str(e)}"


def validate_api_key(api_key: str) -> Tuple[bool, Optional[str]]:
    """
    Validate API key format and structure.
    
    Args:
        api_key: API key to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(api_key, str):
        return False, "API key must be a string"
    
    if not api_key.strip():
        return False, "API key cannot be empty"
    
    # Check length (typical API keys are 32-128 characters)
    if len(api_key) < 16 or len(api_key) > 256:
        return False, "API key length invalid"
    
    # Check for valid characters (alphanumeric and common symbols)
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', api_key):
        return False, "API key contains invalid characters"
    
    return True, None


def validate_request_size(content_length: Optional[int], max_size: int = 50 * 1024 * 1024) -> Tuple[bool, Optional[str]]:
    """
    Validate request content size.
    
    Args:
        content_length: Content length from request headers
        max_size: Maximum allowed size in bytes
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if content_length is None:
        return True, None  # Allow requests without content-length header
    
    if content_length > max_size:
        return False, f"Request too large: {content_length} bytes (max: {max_size} bytes)"
    
    if content_length < 0:
        return False, "Invalid content length"
    
    return True, None