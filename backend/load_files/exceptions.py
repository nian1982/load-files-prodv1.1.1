class DomainException(Exception):
    def __init__(self, message: str, code: str = "DOMAIN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)

class NotFoundException(DomainException):
    def __init__(self, entity: str, identifier: str):
        super().__init__(message=f"{entity} not found: {identifier}", code="NOT_FOUND")

class ValidationException(DomainException):
    def __init__(self, message: str):
        super().__init__(message=message, code="VALIDATION_ERROR")

class UploadException(DomainException):
    def __init__(self, message: str, original: Exception | None = None):
        super().__init__(message=f"Upload error: {message}", code="UPLOAD_ERROR")
        self.original = original

class SFTPConnectionException(DomainException):
    def __init__(self, message: str, original: Exception | None = None):
        super().__init__(message=f"SFTP connection error: {message}", code="SFTP_CONNECTION_ERROR")
        self.original = original

class FileTypeNotAllowedException(ValidationException):
    def __init__(self, file_type: str, allowed: list[str]):
        super().__init__(message=f"File type '{file_type}' not allowed. Allowed: {', '.join(allowed)}")
        self.file_type = file_type
        self.allowed = allowed

class AuthorizationException(DomainException):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message=message, code="FORBIDDEN")
