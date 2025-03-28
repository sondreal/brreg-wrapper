"""
Custom exceptions for the Brreg API wrapper.

This module provides a comprehensive set of exception classes for handling
errors that may occur when interacting with the Brønnøysund Register Centre API.
"""

import json
from typing import Any, Dict, Optional


class BrregAPIError(Exception):
    """Base exception for all Brreg API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_text: Optional[str] = None,
        request_url: Optional[str] = None,
        request_params: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a new Brreg API error.

        Args:
            message: Human-readable error message.
            status_code: HTTP status code, if applicable.
            response_text: Raw response text from the API, if available.
            request_url: The URL that was requested when the error occurred.
            request_params: The parameters that were sent with the request.
        """
        self.status_code = status_code
        self.response_text = response_text
        self.request_url = request_url
        self.request_params = request_params
        super().__init__(message)

    @property
    def response_json(self) -> Optional[Dict[str, Any]]:
        """
        Try to parse the response text as JSON and return it as a dictionary.

        Returns:
            The parsed JSON response as a dictionary, or None if parsing fails
            or if no response text is available.
        """
        if not self.response_text:
            return None

        try:
            return json.loads(self.response_text)
        except (json.JSONDecodeError, TypeError):
            return None


class BrregValidationError(BrregAPIError):
    """
    Raised when input validation fails.

    This exception is typically raised when the API rejects the request due to
    invalid parameters or data format, usually resulting in a 400 Bad Request
    status code.
    """

    pass


class BrregRateLimitError(BrregAPIError):
    """
    Raised when API rate limit is exceeded.

    This exception is typically raised when the API returns a 429 Too Many
    Requests status code, indicating that you've exceeded the allowed number
    of requests in a given time period.
    """

    pass


class BrregResourceNotFoundError(BrregAPIError):
    """
    Raised when requested resource is not found.

    This exception is typically raised when the API returns a 404 Not Found
    status code, indicating that the requested entity, role, or other resource
    does not exist.
    """

    pass


class BrregServerError(BrregAPIError):
    """
    Raised when server error occurs (5xx status codes).

    This exception is typically raised when the API returns a 5xx status code,
    indicating an error on the server side. These errors are generally not
    caused by the client and may require retrying the request.
    """

    pass


class BrregClientError(BrregAPIError):
    """
    Raised for client errors (4xx status codes, excluding 404 and 429).

    This exception is typically raised when the API returns a 4xx status code
    other than 404 (Not Found) or 429 (Too Many Requests), indicating an error
    with the client request.
    """

    pass


class BrregConnectionError(BrregAPIError):
    """
    Raised when a connection error occurs.

    This exception is typically raised when there is a problem establishing a
    connection to the API server, such as network issues, DNS failures, or
    connection refused errors.
    """

    pass


class BrregTimeoutError(BrregAPIError):
    """
    Raised when a request times out.

    This exception is typically raised when a request to the API takes too long
    to complete, exceeding the configured timeout value.
    """

    pass


class BrregAuthenticationError(BrregAPIError):
    """
    Raised when authentication fails.

    This exception is typically raised when the API returns a 401 Unauthorized
    status code, indicating that authentication is required or the provided
    credentials are invalid.
    """

    pass


class BrregForbiddenError(BrregAPIError):
    """
    Raised when access is forbidden.

    This exception is typically raised when the API returns a 403 Forbidden
    status code, indicating that the authenticated user does not have
    permission to access the requested resource.
    """

    pass


class BrregDataError(BrregAPIError):
    """
    Raised when there is an issue with the data received from the API.

    This exception is typically raised when the API returns data that cannot
    be properly parsed or validated, even though the HTTP status code may
    indicate success.
    """

    pass


class BrregServiceUnavailableError(BrregServerError):
    """
    Raised when the API service is unavailable.

    This exception is typically raised when the API returns a 503 Service
    Unavailable status code, indicating that the server is temporarily
    unavailable, possibly due to maintenance or overload.
    """

    pass
