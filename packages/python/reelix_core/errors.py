class DomainError(Exception):
    code: str = "domain_error"
    status: int = 400

    def __init__(self, message: str = "", *, code: str | None = None, status: int | None = None):
        super().__init__(message or self.__class__.__name__)
        if code: self.code = code
        if status: self.status = status

class NotFound(DomainError):
    code = "not_found"
    status = 404

class Conflict(DomainError):
    code = "conflict"
    status = 409

class Forbidden(DomainError):
    code = "forbidden"
    status = 403

class RuleViolation(DomainError):
    code = "rule_violation"
    status = 422
