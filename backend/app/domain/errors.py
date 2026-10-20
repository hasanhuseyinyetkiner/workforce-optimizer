"""Domain errors that the API maps to HTTP 422 responses."""

from __future__ import annotations


class DomainError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
