"""
Platform Constants.
"""

# File upload constraints
MAX_FILE_SIZE_MB: int = 10
ALLOWED_IMAGE_EXTENSIONS: set[str] = {"jpg", "jpeg", "png", "gif", "webp"}
ALLOWED_DOCUMENT_EXTENSIONS: set[str] = {"pdf", "doc", "docx", "xls", "xlsx", "txt"}

# Rate limiting
DEFAULT_RATE_LIMIT_LIMIT: int = 100
DEFAULT_RATE_LIMIT_WINDOW_SECONDS: int = 60

# Context Management Keys
CORRELATION_ID_HEADER: str = "X-Correlation-ID"
REQUEST_ID_HEADER: str = "X-Request-ID"
SCHOOL_ID_HEADER: str = "X-School-ID"
