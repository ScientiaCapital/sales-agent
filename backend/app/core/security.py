"""
Security Validation Module

Provides security utilities for the Sales Agent platform:
- Environment validation (API keys, database connections)
- Filename sanitization (path traversal prevention)
- CSV validation (structure, size, format)
- Input validation (SQL injection prevention)

Usage:
    >>> from app.core.security import SecurityValidator
    >>>
    >>> # Validate environment on startup
    >>> SecurityValidator.validate_environment()
    >>>
    >>> # Sanitize user-uploaded filename
    >>> safe_filename = SecurityValidator.sanitize_filename("../../etc/passwd.csv")
    >>> # Returns: "etcpasswd.csv"
    >>>
    >>> # Validate CSV file
    >>> SecurityValidator.validate_csv_file(file_path, max_size_mb=10)
"""

import os
import re
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from app.core.exceptions import (
    MissingAPIKeyError,
    InvalidInputError,
    InvalidFileFormatError,
    FileSizeExceededError,
    ConfigurationError,
)

logger = logging.getLogger(__name__)


class SecurityValidator:
    """
    Central security validation utilities.

    All methods are static to allow usage without instantiation.
    """

    # ========================================================================
    # ENVIRONMENT VALIDATION
    # ========================================================================

    # Critical API keys that MUST be present for the app to function
    REQUIRED_API_KEYS = [
        "DATABASE_URL",
        "REDIS_URL",
    ]

    # Optional API keys that should generate warnings but not block startup
    OPTIONAL_API_KEYS = [
        "CEREBRAS_API_KEY",
        "OPENROUTER_API_KEY",
        "CLOSE_API_KEY",
        "APOLLO_API_KEY",
        "ANTHROPIC_API_KEY",
    ]

    @staticmethod
    def validate_environment() -> None:
        """
        Validate that required environment variables are set.

        Raises:
            MissingAPIKeyError: If critical API keys are missing

        Logs:
            WARNING: For missing optional API keys
            INFO: For successful validation
        """
        missing_required = []
        missing_optional = []

        # Check required keys
        for key in SecurityValidator.REQUIRED_API_KEYS:
            value = os.getenv(key)
            if not value or value.strip() == "":
                missing_required.append(key)

        # Check optional keys
        for key in SecurityValidator.OPTIONAL_API_KEYS:
            value = os.getenv(key)
            if not value or value.strip() == "":
                missing_optional.append(key)

        # Fail fast on missing required keys
        if missing_required:
            error_msg = (
                f"Missing required environment variables: {', '.join(missing_required)}. "
                f"Please check your .env file."
            )
            logger.error(error_msg)
            raise MissingAPIKeyError(
                error_msg,
                context={"missing_keys": missing_required}
            )

        # Warn on missing optional keys
        if missing_optional:
            logger.warning(
                f"Missing optional API keys: {', '.join(missing_optional)}. "
                f"Some features may be unavailable."
            )

        # Success
        logger.info(
            f"Environment validation passed. "
            f"{len(SecurityValidator.REQUIRED_API_KEYS)} required keys found, "
            f"{len(SecurityValidator.OPTIONAL_API_KEYS) - len(missing_optional)} optional keys found."
        )

    # ========================================================================
    # FILENAME SANITIZATION
    # ========================================================================

    # Maximum filename length (standard filesystem limit)
    MAX_FILENAME_LENGTH = 255

    # Allowed characters: alphanumeric, hyphens, underscores, periods
    # This regex removes everything else
    FILENAME_PATTERN = re.compile(r'[^a-zA-Z0-9._-]')

    # Path traversal patterns to detect
    PATH_TRAVERSAL_PATTERNS = [
        "..",
        "/",
        "\\",
        "~",
    ]

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize filename to prevent path traversal and injection attacks.

        Security measures:
        1. Remove path traversal sequences (../, ..\, ~)
        2. Remove directory separators (/, \)
        3. Allow only alphanumeric, hyphens, underscores, periods
        4. Truncate to MAX_FILENAME_LENGTH
        5. Ensure extension is preserved

        Args:
            filename: Raw filename from user input

        Returns:
            Sanitized filename safe for filesystem operations

        Raises:
            InvalidInputError: If filename is empty or becomes empty after sanitization

        Example:
            >>> SecurityValidator.sanitize_filename("../../etc/passwd.csv")
            'etcpasswd.csv'
            >>> SecurityValidator.sanitize_filename("my leads (2024).csv")
            'myleads2024.csv'
        """
        if not filename or not filename.strip():
            raise InvalidInputError(
                "Filename cannot be empty",
                context={"filename": filename}
            )

        # Get the filename only (strip any directory path)
        filename = os.path.basename(filename)

        # Split filename and extension
        name_parts = filename.rsplit(".", 1)
        name = name_parts[0]
        extension = name_parts[1] if len(name_parts) > 1 else ""

        # Remove all non-alphanumeric characters except . - _
        name = SecurityValidator.FILENAME_PATTERN.sub('', name)
        extension = SecurityValidator.FILENAME_PATTERN.sub('', extension)

        # Ensure we still have a valid filename
        if not name:
            raise InvalidInputError(
                "Filename becomes empty after sanitization",
                context={"original_filename": filename}
            )

        # Reconstruct filename
        sanitized = f"{name}.{extension}" if extension else name

        # Truncate if too long
        if len(sanitized) > SecurityValidator.MAX_FILENAME_LENGTH:
            # Keep extension, truncate name
            if extension:
                max_name_length = SecurityValidator.MAX_FILENAME_LENGTH - len(extension) - 1
                sanitized = f"{name[:max_name_length]}.{extension}"
            else:
                sanitized = sanitized[:SecurityValidator.MAX_FILENAME_LENGTH]

        logger.debug(f"Sanitized filename: '{filename}' → '{sanitized}'")
        return sanitized

    @staticmethod
    def detect_path_traversal(filepath: str) -> bool:
        """
        Detect potential path traversal attempts in filepath.

        Args:
            filepath: File path to check

        Returns:
            True if path traversal detected, False otherwise
        """
        for pattern in SecurityValidator.PATH_TRAVERSAL_PATTERNS:
            if pattern in filepath:
                logger.warning(
                    f"Path traversal attempt detected: '{filepath}' contains '{pattern}'"
                )
                return True
        return False

    # ========================================================================
    # CSV FILE VALIDATION
    # ========================================================================

    # Default max file size: 10 MB
    DEFAULT_MAX_FILE_SIZE_MB = 10

    # Allowed CSV extensions
    ALLOWED_CSV_EXTENSIONS = [".csv", ".CSV"]

    # Expected CSV columns (case-insensitive)
    EXPECTED_CSV_COLUMNS = [
        "company_name",
        "industry",
        "website",
    ]

    @staticmethod
    def validate_csv_file(
        file_path: str,
        max_size_mb: Optional[float] = None,
        check_columns: bool = False,
        expected_columns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Validate CSV file before processing.

        Checks:
        1. File exists
        2. File extension is .csv
        3. File size is under max_size_mb
        4. (Optional) CSV has expected columns

        Args:
            file_path: Path to CSV file
            max_size_mb: Maximum file size in MB (default: 10 MB)
            check_columns: Whether to validate column headers
            expected_columns: List of expected column names (case-insensitive)

        Returns:
            Dict with validation results:
            {
                "valid": True,
                "file_size_mb": 2.5,
                "row_count": 150,
                "columns": ["company_name", "industry", "website"]
            }

        Raises:
            InvalidFileFormatError: If file extension is not .csv
            FileSizeExceededError: If file exceeds max_size_mb
            InvalidInputError: If file doesn't exist or columns don't match
        """
        max_size_mb = max_size_mb or SecurityValidator.DEFAULT_MAX_FILE_SIZE_MB
        expected_columns = expected_columns or SecurityValidator.EXPECTED_CSV_COLUMNS

        # Check file exists
        path = Path(file_path)
        if not path.exists():
            raise InvalidInputError(
                f"File not found: {file_path}",
                context={"file_path": file_path}
            )

        # Check file extension
        if path.suffix not in SecurityValidator.ALLOWED_CSV_EXTENSIONS:
            raise InvalidFileFormatError(
                f"Invalid file extension: {path.suffix}. Expected .csv",
                context={"file_path": file_path, "extension": path.suffix}
            )

        # Check file size
        file_size_bytes = path.stat().st_size
        file_size_mb = file_size_bytes / (1024 * 1024)

        if file_size_mb > max_size_mb:
            raise FileSizeExceededError(
                f"File size {file_size_mb:.2f} MB exceeds maximum {max_size_mb} MB",
                context={
                    "file_path": file_path,
                    "file_size_mb": file_size_mb,
                    "max_size_mb": max_size_mb
                }
            )

        # Optional: Check CSV columns
        row_count = 0
        columns = []

        if check_columns:
            import csv

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    columns = [col.lower().strip() for col in reader.fieldnames or []]

                    # Count rows
                    row_count = sum(1 for _ in reader)

                    # Validate columns
                    missing_columns = [
                        col for col in expected_columns
                        if col.lower() not in columns
                    ]

                    if missing_columns:
                        raise InvalidInputError(
                            f"CSV missing required columns: {', '.join(missing_columns)}",
                            context={
                                "file_path": file_path,
                                "expected_columns": expected_columns,
                                "actual_columns": columns,
                                "missing_columns": missing_columns
                            }
                        )
            except csv.Error as e:
                raise InvalidFileFormatError(
                    f"Invalid CSV format: {str(e)}",
                    context={"file_path": file_path, "error": str(e)}
                )

        logger.info(
            f"CSV validation passed: {file_path} "
            f"({file_size_mb:.2f} MB, {row_count} rows)"
        )

        return {
            "valid": True,
            "file_size_mb": round(file_size_mb, 2),
            "row_count": row_count,
            "columns": columns
        }

    # ========================================================================
    # SQL INJECTION PREVENTION
    # ========================================================================

    # SQL injection patterns (basic detection)
    SQL_INJECTION_PATTERNS = [
        r"(\bOR\b\s+\d+\s*=\s*\d+)",  # OR 1=1
        r"(\bAND\b\s+\d+\s*=\s*\d+)",  # AND 1=1
        r"(--)",  # SQL comment
        r"(;.*DROP\b)",  # DROP table
        r"(;.*DELETE\b)",  # DELETE statement
        r"(UNION\s+SELECT)",  # UNION SELECT
    ]

    @staticmethod
    def detect_sql_injection(input_string: str) -> bool:
        """
        Detect potential SQL injection attempts in user input.

        NOTE: This is a basic check. The primary defense is parameterized queries.

        Args:
            input_string: User input to check

        Returns:
            True if potential SQL injection detected, False otherwise
        """
        if not input_string:
            return False

        for pattern in SecurityValidator.SQL_INJECTION_PATTERNS:
            if re.search(pattern, input_string, re.IGNORECASE):
                logger.warning(
                    f"Potential SQL injection detected: pattern '{pattern}' in input"
                )
                return True

        return False


# ============================================================================
# STARTUP VALIDATION
# ============================================================================

def validate_security_on_startup() -> None:
    """
    Run all security validations on application startup.

    Call this from app initialization (main.py or __init__.py).

    Raises:
        MissingAPIKeyError: If required environment variables are missing
        ConfigurationError: If security checks fail
    """
    logger.info("Running security validation checks...")

    try:
        # Validate environment
        SecurityValidator.validate_environment()

        # Validate CSV directories exist
        csv_base_path = Path(__file__).parent.parent.parent / "data" / "csv"
        required_dirs = ["inbox", "processing", "completed", "failed", "archive"]

        for dir_name in required_dirs:
            dir_path = csv_base_path / dir_name
            if not dir_path.exists():
                logger.warning(f"CSV directory missing: {dir_path}. Creating it now.")
                dir_path.mkdir(parents=True, exist_ok=True)

        logger.info("Security validation completed successfully.")

    except Exception as e:
        logger.error(f"Security validation failed: {e}")
        raise ConfigurationError(
            "Security validation failed on startup",
            context={"error": str(e)}
        )
