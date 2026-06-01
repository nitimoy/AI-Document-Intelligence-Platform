"""Custom application exception hierarchy."""


class ApplicationError(Exception):
    """Base class for application-specific exceptions."""


class ConfigurationError(ApplicationError):
    """Raised when required configuration is invalid or missing."""


class ExternalServiceError(ApplicationError):
    """Raised when an external dependency call fails."""


class GoogleDriveError(ExternalServiceError):
    """Base class for Google Drive integration errors."""


class AuthenticationError(GoogleDriveError):
    """Raised when Google Drive authentication fails."""


class FileDownloadError(GoogleDriveError):
    """Raised when a Google Drive file download fails."""


class DocumentParsingError(ApplicationError):
    """Raised when document content extraction fails."""


class UnsupportedFileTypeError(DocumentParsingError):
    """Raised when a file type has no parser implementation."""


class EmptyDocumentError(DocumentParsingError):
    """Raised when extracted content fails validation rules."""


class SummarizationError(ApplicationError):
    """Raised when AI summarization workflow fails."""


class OpenAIServiceError(SummarizationError):
    """Raised when OpenAI API calls fail."""


class CacheError(SummarizationError):
    """Raised when summary cache read/write operations fail."""
