import time
from datetime import date, timedelta

import httpx
import pytest
from pytest_httpx import HTTPXMock

from brreg_wrapper.client import BrregClient
from brreg_wrapper.exceptions import (
    BrregAPIError,
    BrregAuthenticationError,
    BrregForbiddenError,
    BrregRateLimitError,
    BrregResourceNotFoundError,
    BrregServerError,
    BrregServiceUnavailableError,
    BrregValidationError,
)
from brreg_wrapper.models import (
    Enhet,
    Enheter1,
    FieldEmbedded,
    FieldLinks3,
    Kommuner1,  # Added import
    Page,
    SlettetEnhet,
)


@pytest.mark.asyncio
async def test_client_instantiation():
    """Test that the BrregClient can be instantiated."""
    client = BrregClient()
    assert client is not None
    # Compare string representations to handle potential trailing slashes
    assert str(client._client.base_url) == BrregClient.BASE_URL + "/"
    # Ensure the client is closed to avoid resource warnings
    await client.close()


@pytest.mark.asyncio
async def test_get_enhet_success(httpx_mock: HTTPXMock):
    """Test successfully retrieving an entity."""
    org_nr = "987654321"
    # More complete mock data matching the Enhet model structure
    mock_response_data = {
        "organisasjonsnummer": org_nr,
        "navn": "Test Company AS",
        "organisasjonsform": {
            "kode": "AS",
            "beskrivelse": "Aksjeselskap",
            "_links": {
                "self": {"href": f"{BrregClient.BASE_URL}/organisasjonsformer/AS"}
            },
        },
        "registrertIMvaregisteret": True,
        "maalform": "Bokmål",
        "registrertIForetaksregisteret": True,
        "registrertIStiftelsesregisteret": False,
        "registrertIFrivillighetsregisteret": False,
        "konkurs": False,
        "underAvvikling": False,
        "underTvangsavviklingEllerTvangsopplosning": False,
        "registreringsdatoEnhetsregisteret": "2023-01-01",
        "harRegistrertAntallAnsatte": False,
        "_links": {"self": {"href": f"{BrregClient.BASE_URL}/enheter/{org_nr}"}},
        # Add other required fields if necessary based on the model
    }
    expected_url = f"{BrregClient.BASE_URL}/enheter/{org_nr}"

    httpx_mock.add_response(
        url=expected_url,
        method="GET",
        json=mock_response_data,
        status_code=200,
        headers={"Content-Type": "application/json"},
    )

    client = BrregClient()
    try:
        enhet_data = await client.get_enhet(org_nr)

        # Assert the type and specific attributes
        assert isinstance(enhet_data, Enhet)
        assert enhet_data.organisasjonsnummer == org_nr
        assert enhet_data.navn == "Test Company AS"
        assert enhet_data.organisasjonsform.kode == "AS"
        assert enhet_data.registrertIMvaregisteret is True
        assert enhet_data.registreringsdatoEnhetsregisteret == date(2023, 1, 1)

        # Verify the request was made as expected
        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "GET"
        assert str(request.url) == expected_url
        assert request.headers["Accept"] == "application/json"
    finally:
        await client.close()


# --- Tests for Kodeverk Endpoints ---


@pytest.mark.asyncio
async def test_get_organisasjonsformer_url(httpx_mock: HTTPXMock):
    """Test that get_organisasjonsformer calls the correct URL."""
    expected_url = f"{BrregClient.BASE_URL}/kodeverk/organisasjonsformer"
    # Mock response data structure matching Organisasjonsformer1
    mock_response_data = {
        "_embedded": {
            "organisasjonsformer": [
                {
                    "kode": "AS",
                    "beskrivelse": "Aksjeselskap",
                    "_links": {
                        "self": {
                            "href": (
                                f"{BrregClient.BASE_URL}/kodeverk/organisasjonsformer/AS"
                            )
                        }
                    },
                }
            ]
        },
        "_links": {"self": {"href": expected_url}},
    }

    httpx_mock.add_response(
        url=expected_url,
        method="GET",
        json=mock_response_data,
        status_code=200,
        headers={"Content-Type": "application/json"},
    )

    async with BrregClient() as client:
        await client.get_organisasjonsformer()  # Call the method

        # Verify the request URL
        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "GET"
        assert str(request.url) == expected_url


@pytest.mark.asyncio
async def test_get_naeringskoder_url(httpx_mock: HTTPXMock):
    """Test that get_naeringskoder calls the correct URL."""
    expected_url = f"{BrregClient.BASE_URL}/kodeverk/naeringskoder"
    # Mock response data (simple dict is fine as return type is dict)
    mock_response_data = {
        "_embedded": {
            "naeringskoder": [
                {
                    "kode": "01.110",
                    "beskrivelse": "Dyrking av korn...",
                    "_links": {
                        "self": {
                            "href": (
                                f"{BrregClient.BASE_URL}/kodeverk/naeringskoder/01.110"
                            )
                        }
                    },
                }
            ]
        },
        "_links": {"self": {"href": expected_url}},
    }

    httpx_mock.add_response(
        url=expected_url,
        method="GET",
        json=mock_response_data,
        status_code=200,
        headers={"Content-Type": "application/json"},
    )

    async with BrregClient() as client:
        await client.get_naeringskoder()  # Call the method

        # Verify the request URL
        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "GET"
        assert str(request.url) == expected_url


@pytest.mark.asyncio
async def test_get_sektorkoder_url(httpx_mock: HTTPXMock):
    """Test that get_sektorkoder calls the correct URL."""
    expected_url = f"{BrregClient.BASE_URL}/kodeverk/sektorkoder"
    # Mock response data (simple dict is fine as return type is dict)
    mock_response_data = {
        "_embedded": {
            "sektorkoder": [
                {
                    "kode": "6100",
                    "beskrivelse": "Statsforvaltningen",
                    "_links": {
                        "self": {
                            "href": f"{BrregClient.BASE_URL}/kodeverk/sektorkoder/6100"
                        }
                    },
                }
            ]
        },
        "_links": {"self": {"href": expected_url}},
    }

    httpx_mock.add_response(
        url=expected_url,
        method="GET",
        json=mock_response_data,
        status_code=200,
        headers={"Content-Type": "application/json"},
    )

    async with BrregClient() as client:
        await client.get_sektorkoder()  # Call the method

        # Verify the request URL
        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "GET"
        assert str(request.url) == expected_url


@pytest.mark.asyncio
async def test_get_kommuner_success(httpx_mock: HTTPXMock):
    """Test successfully retrieving municipalities."""
    expected_url = f"{BrregClient.BASE_URL}/kodeverk/kommuner"
    # Mock response data - API returns a list, client wraps it
    mock_api_response_list = [
        {
            "nummer": "0301",
            "navn": "OSLO",
            "_links": {
                "self": {"href": f"{BrregClient.BASE_URL}/kodeverk/kommuner/0301"}
            },
        },
        {
            "nummer": "1101",
            "navn": "EIGERØY",  # Example, might not be real
            "_links": {
                "self": {"href": f"{BrregClient.BASE_URL}/kodeverk/kommuner/1101"}
            },
        },
    ]
    # The client wraps this list into the structure expected by Kommuner1 model

    httpx_mock.add_response(
        url=expected_url,
        method="GET",
        json=mock_api_response_list,  # Mock the raw API list response
        status_code=200,
        headers={"Content-Type": "application/json"},
    )

    async with BrregClient() as client:
        kommuner_data = await client.get_kommuner()

        # Assert the type and specific attributes
        assert isinstance(kommuner_data, Kommuner1)
        assert kommuner_data.field_embedded is not None
        assert len(kommuner_data.field_embedded.kommuner) == 2
        assert kommuner_data.field_embedded.kommuner[0].nummer == "0301"
        assert kommuner_data.field_embedded.kommuner[0].navn == "OSLO"
        assert kommuner_data.field_embedded.kommuner[1].nummer == "1101"

        # Verify the request was made as expected
        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "GET"
        assert str(request.url) == expected_url
        assert request.headers["Accept"] == "application/json"


@pytest.mark.asyncio
async def test_async_context_manager():
    """Test that the client works correctly as an async context manager."""
    async with BrregClient() as client:
        assert client is not None
        # Check if the underlying httpx client is created
        assert isinstance(client._client, httpx.AsyncClient)
        # No explicit close needed here, __aexit__ handles it.

    # Optional: Add more checks after the context manager exits if needed,
    # e.g., mocking aclose to ensure it was called.


@pytest.mark.asyncio
async def test_get_enhet_not_found(httpx_mock: HTTPXMock):
    """Test handling of a 404 Not Found error when retrieving an entity."""
    org_nr = "123456789"
    expected_url = f"{BrregClient.BASE_URL}/enheter/{org_nr}"

    httpx_mock.add_response(
        url=expected_url,
        method="GET",
        status_code=404,
        json={"message": "Not Found"},  # Example error response
    )

    client = BrregClient()
    try:
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await client.get_enhet(org_nr)

        assert exc_info.value.response.status_code == 404

        # Verify the request was made
        request = httpx_mock.get_request()
        assert request is not None
        assert str(request.url) == expected_url
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_get_enhet_deleted(httpx_mock: HTTPXMock):
    """Test retrieving a deleted entity."""
    org_nr = "123456780"
    mock_response_data = {
        "respons_klasse": "SlettetEnhet",
        "organisasjonsnummer": org_nr,
        "navn": "Deleted Company AS",
        "organisasjonsform": {
            "kode": "AS",
            "beskrivelse": "Aksjeselskap",
            "_links": {
                "self": {"href": f"{BrregClient.BASE_URL}/organisasjonsformer/AS"}
            },
        },
        "slettedato": "2024-02-15",
        "_links": {"self": {"href": f"{BrregClient.BASE_URL}/enheter/{org_nr}"}},
    }
    expected_url = f"{BrregClient.BASE_URL}/enheter/{org_nr}"

    httpx_mock.add_response(
        url=expected_url,
        method="GET",
        json=mock_response_data,
        status_code=200,  # API might return 200 even for deleted entities
        headers={"Content-Type": "application/json"},
    )

    client = BrregClient()
    try:
        enhet_data = await client.get_enhet(org_nr)
        assert isinstance(enhet_data, SlettetEnhet)
        assert enhet_data.organisasjonsnummer == org_nr
        assert enhet_data.slettedato == "2024-02-15"  # Keep as string as per model

        request = httpx_mock.get_request()
        assert request is not None
        assert str(request.url) == expected_url
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_search_enheter_success(httpx_mock: HTTPXMock):
    """Test successfully searching for entities."""
    search_params = {"navn": "Test Search", "size": 5}
    # More complete mock data matching the Enheter1 and embedded Enhet structure
    mock_response_data = {
        "_embedded": {
            "enheter": [
                {
                    "organisasjonsnummer": "111111111",
                    "navn": "Test Search Result 1",
                    "organisasjonsform": {"kode": "AS", "beskrivelse": "Aksjeselskap"},
                    "registrertIMvaregisteret": True,
                    "maalform": "Bokmål",
                    "registrertIForetaksregisteret": True,
                    "registrertIStiftelsesregisteret": False,
                    "registrertIFrivillighetsregisteret": False,
                    "konkurs": False,
                    "underAvvikling": False,
                    "underTvangsavviklingEllerTvangsopplosning": False,
                    "registreringsdatoEnhetsregisteret": "2023-01-01",
                    "harRegistrertAntallAnsatte": False,
                    "_links": {
                        "self": {"href": f"{BrregClient.BASE_URL}/enheter/111111111"}
                    },
                },
                {
                    "organisasjonsnummer": "222222222",
                    "navn": "Test Search Result 2",
                    "organisasjonsform": {
                        "kode": "ENK",
                        "beskrivelse": "Enkeltpersonforetak",
                    },
                    "registrertIMvaregisteret": False,
                    "maalform": "Nynorsk",
                    "registrertIForetaksregisteret": False,
                    "registrertIStiftelsesregisteret": False,
                    "registrertIFrivillighetsregisteret": False,
                    "konkurs": False,
                    "underAvvikling": False,
                    "underTvangsavviklingEllerTvangsopplosning": False,
                    "registreringsdatoEnhetsregisteret": "2023-02-01",
                    "harRegistrertAntallAnsatte": True,
                    "antallAnsatte": 1,
                    "_links": {
                        "self": {"href": f"{BrregClient.BASE_URL}/enheter/222222222"}
                    },
                },
            ]
        },
        "page": {"number": 0, "size": 5, "totalElements": 2, "totalPages": 1},
        "_links": {
            "self": {"href": f"{BrregClient.BASE_URL}/enheter?navn=Test+Search&size=5"},
            "first": {
                "href": f"{BrregClient.BASE_URL}/enheter?navn=Test+Search&size=5&page=0"
            },
            "last": {
                "href": f"{BrregClient.BASE_URL}/enheter?navn=Test+Search&size=5&page=0"
            },
        },
    }
    # Construct the expected URL with query parameters
    expected_url_with_params = httpx.URL(
        f"{BrregClient.BASE_URL}/enheter", params=search_params
    )

    httpx_mock.add_response(
        url=expected_url_with_params,  # Use the URL object with params
        method="GET",
        json=mock_response_data,
        status_code=200,
        headers={"Content-Type": "application/json"},
    )

    client = BrregClient()
    try:
        search_results = await client.search_enheter(**search_params)

        # Assert the type and specific attributes
        assert isinstance(search_results, Enheter1)
        assert isinstance(search_results.page, Page)
        assert search_results.page.totalElements == 2
        assert search_results.page.size == 5
        assert isinstance(search_results.field_embedded, FieldEmbedded)
        assert len(search_results.field_embedded.enheter) == 2
        assert isinstance(search_results.field_embedded.enheter[0], Enhet)
        assert (
            search_results.field_embedded.enheter[0].organisasjonsnummer == "111111111"
        )
        assert search_results.field_embedded.enheter[0].organisasjonsform.kode == "AS"
        assert (
            search_results.field_embedded.enheter[1].organisasjonsnummer == "222222222"
        )
        assert search_results.field_embedded.enheter[1].organisasjonsform.kode == "ENK"
        assert isinstance(search_results.field_links, FieldLinks3)
        assert search_results.field_links.self.href == str(expected_url_with_params)

        # Verify the request was made as expected
        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "GET"
        # Check the exact URL requested
        assert str(request.url) == str(expected_url_with_params)
        assert request.headers["Accept"] == "application/json"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_caching(httpx_mock: HTTPXMock):
    """Test that responses are cached properly."""
    org_nr = "123456789"
    mock_response_data = {
        "organisasjonsnummer": org_nr,
        "navn": "Cache Test AS",
        "organisasjonsform": {
            "kode": "AS",
            "beskrivelse": "Aksjeselskap",
            "_links": {
                "self": {"href": f"{BrregClient.BASE_URL}/organisasjonsformer/AS"}
            },
        },
        "registreringsdatoEnhetsregisteret": "2023-01-01",
        "_links": {"self": {"href": f"{BrregClient.BASE_URL}/enheter/{org_nr}"}},
    }
    expected_url = f"{BrregClient.BASE_URL}/enheter/{org_nr}"

    # Add the mock response - it will only be used once
    # If the second call tries to hit the API, an error will be raised
    httpx_mock.add_response(
        url=expected_url,
        method="GET",
        json=mock_response_data,
        status_code=200,
    )

    # Create client with caching enabled
    client = BrregClient(cache_ttl=timedelta(minutes=10))
    try:
        # First call should hit the API
        enhet1 = await client.get_enhet(org_nr)
        assert enhet1.navn == "Cache Test AS"

        # Second call should use the cache
        enhet2 = await client.get_enhet(org_nr)
        assert enhet2.navn == "Cache Test AS"

        # Verify cache info
        cache_info = client.get_cache_info()
        assert cache_info["count"] == 1
        assert "enhet" in str(cache_info["categories"])

        # Clear the cache
        client.clear_cache()
        assert client.get_cache_info()["count"] == 0
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_rate_limiting():
    """Test that rate limiting works correctly."""
    # Create a client with rate limiting of 0.2 seconds
    client = BrregClient(rate_limit=0.2)
    try:
        # Record timing for two API calls that would hit rate limits
        # We'll mock the _request method to avoid actual API calls

        original_request = client._request
        request_times = []

        # Replace _request with a mock that just records times
        async def mock_request(*args, **kwargs):
            request_times.append(time.time())
            return httpx.Response(200, json={})

        client._request = mock_request

        # Make two quick requests
        await client.get_services()
        await client.get_services()

        # Restore original method
        client._request = original_request

        # Calculate time difference
        time_diff = request_times[1] - request_times[0]

        # Assert that the second request was delayed by at least the rate limit
        assert time_diff >= 0.2
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_get_multiple_enheter(httpx_mock: HTTPXMock):
    """Test the batch operation to get multiple enheter."""
    # Setup mock responses for two different orgs
    org_nr1 = "123456789"
    org_nr2 = "987654321"

    mock_response1 = {
        "organisasjonsnummer": org_nr1,
        "navn": "Batch Test 1 AS",
        "organisasjonsform": {
            "kode": "AS",
            "beskrivelse": "Aksjeselskap",
            "_links": {
                "self": {"href": f"{BrregClient.BASE_URL}/organisasjonsformer/AS"}
            },
        },
        "registreringsdatoEnhetsregisteret": "2023-01-01",
        "_links": {"self": {"href": f"{BrregClient.BASE_URL}/enheter/{org_nr1}"}},
    }

    mock_response2 = {
        "organisasjonsnummer": org_nr2,
        "navn": "Batch Test 2 AS",
        "organisasjonsform": {
            "kode": "AS",
            "beskrivelse": "Aksjeselskap",
            "_links": {
                "self": {"href": f"{BrregClient.BASE_URL}/organisasjonsformer/AS"}
            },
        },
        "registreringsdatoEnhetsregisteret": "2023-02-01",
        "_links": {"self": {"href": f"{BrregClient.BASE_URL}/enheter/{org_nr2}"}},
    }

    # Add mock responses
    httpx_mock.add_response(
        url=f"{BrregClient.BASE_URL}/enheter/{org_nr1}",
        method="GET",
        json=mock_response1,
        status_code=200,
    )

    httpx_mock.add_response(
        url=f"{BrregClient.BASE_URL}/enheter/{org_nr2}",
        method="GET",
        json=mock_response2,
        status_code=200,
    )

    # Create client and test batch operation
    client = BrregClient()
    try:
        results = await client.get_multiple_enheter([org_nr1, org_nr2])

        # Verify results
        assert len(results) == 2
        assert results[org_nr1].navn == "Batch Test 1 AS"
        assert results[org_nr2].navn == "Batch Test 2 AS"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_error_handling(httpx_mock: HTTPXMock):
    """Test that different HTTP errors map to the correct exception types."""
    org_nr = "123456789"
    base_url = f"{BrregClient.BASE_URL}/enheter/{org_nr}"

    error_mappings = [
        # (status_code, exception_class, error_message_pattern)
        (400, BrregValidationError, "Invalid request"),
        (401, BrregAuthenticationError, "Authentication required"),
        (403, BrregForbiddenError, "Access forbidden"),
        (404, BrregResourceNotFoundError, "Resource not found"),
        (429, BrregRateLimitError, "Rate limit exceeded"),
        (500, BrregServerError, "HTTP error 500"),
        (503, BrregServiceUnavailableError, "Service temporarily unavailable"),
    ]

    for status_code, exception_class, error_pattern in error_mappings:
        # Reset mock for each iteration
        httpx_mock.reset(assert_all_responses_were_requested=False)

        # Setup mock response for this status code
        httpx_mock.add_response(
            url=base_url,
            method="GET",
            json={"message": "Error message"},
            status_code=status_code,
        )

        # Test with fresh client each time
        client = BrregClient()
        try:
            with pytest.raises(exception_class) as excinfo:
                await client.get_enhet(org_nr)

            # Verify exception attributes
            assert excinfo.value.status_code == status_code
            assert error_pattern in str(excinfo.value)
            assert excinfo.value.request_url == base_url
        finally:
            await client.close()


@pytest.mark.asyncio
async def test_response_json_property():
    """Test that the response_json property on exceptions works correctly."""
    # Create an exception with valid JSON
    error = BrregAPIError(
        message="Test error",
        response_text='{"error": "test", "code": 123}',
        status_code=400,
    )

    # Test response_json property
    json_data = error.response_json
    assert json_data is not None
    assert json_data["error"] == "test"
    assert json_data["code"] == 123

    # Test with invalid JSON
    error = BrregAPIError(
        message="Test error", response_text='{"error": invalid json', status_code=400
    )
    assert error.response_json is None

    # Test with no response text
    error = BrregAPIError(message="Test error", status_code=400)
    assert error.response_json is None
