"""Common error definitions for the API."""


class ServiceError(Exception):
    """Base exception for service layer errors."""

    pass


class ValidationError(Exception):
    """Exception for data validation errors."""

    pass


class NotFoundError(Exception):
    """Exception for resource not found errors."""

    pass


class DatabaseError(Exception):
    """Exception for database operation errors."""

    pass
