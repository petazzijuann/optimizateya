"""Excepciones de dominio."""


class DomainError(Exception):
    """Base de errores de dominio; el mensaje es apto para mostrar al usuario."""

    code = "DOMAIN_ERROR"


class NotFoundError(DomainError):
    code = "NOT_FOUND"


class ValidationError(DomainError):
    code = "VALIDATION_ERROR"


class DateParseError(ValidationError):
    """No se pudo interpretar la fecha/hora en lenguaje natural."""

    code = "DATE_PARSE_ERROR"


class BudgetExceededError(DomainError):
    code = "LLM_BUDGET_EXCEEDED"


class RateLimitedError(DomainError):
    code = "RATE_LIMITED"


class ExternalServiceError(DomainError):
    """Servicio externo caído; la acción puede ir al outbox."""

    code = "EXTERNAL_SERVICE_ERROR"


class CalendarNotConnectedError(DomainError):
    code = "CALENDAR_NOT_CONNECTED"
