"""
Tests for the exceptions module.
"""

import pytest

from brreg_wrapper.exceptions import (
    BrregAPIError,
    BrregAuthenticationError,
    BrregClientError,
    BrregConnectionError,
    BrregDataError,
    BrregForbiddenError,
    BrregRateLimitError,
    BrregResourceNotFoundError,
    BrregServerError,
    BrregServiceUnavailableError,
    BrregTimeoutError,
    BrregValidationError,
)


class TestBrregAPIError:
    def test_init(self):
        """Test that BrregAPIError can be initialized with various parameters."""
        error = BrregAPIError(
            message="Test error",
            status_code=500,
            response_text='{"error": "test"}',
            request_url="https://example.com",
            request_params={"param": "value"},
        )

        assert str(error) == "Test error"
        assert error.status_code == 500
        assert error.response_text == '{"error": "test"}'
        assert error.request_url == "https://example.com"
        assert error.request_params == {"param": "value"}

    def test_response_json(self):
        """Test that response_json property works correctly."""
        # With valid JSON
        error = BrregAPIError(message="Test error", response_text='{"error": "test"}')
        assert error.response_json == {"error": "test"}

        # With invalid JSON
        error = BrregAPIError(message="Test error", response_text='{"error": invalid}')
        assert error.response_json is None

        # With no response text
        error = BrregAPIError(message="Test error")
        assert error.response_json is None


@pytest.mark.parametrize(
    "exception_class",
    [
        BrregValidationError,
        BrregRateLimitError,
        BrregResourceNotFoundError,
        BrregServerError,
        BrregClientError,
        BrregConnectionError,
        BrregTimeoutError,
        BrregAuthenticationError,
        BrregForbiddenError,
        BrregDataError,
        BrregServiceUnavailableError,
    ],
)
def test_exception_inheritance(exception_class):
    """Test that all exception classes inherit from BrregAPIError."""
    assert issubclass(exception_class, BrregAPIError)

    # Instantiate the exception to ensure it works
    exc = exception_class("Test message")
    assert isinstance(exc, BrregAPIError)
    assert str(exc) == "Test message"


def test_service_unavailable_inheritance():
    """Test that BrregServiceUnavailableError inherits from BrregServerError."""
    assert issubclass(BrregServiceUnavailableError, BrregServerError)
