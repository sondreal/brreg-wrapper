import time
from datetime import date, timedelta

import httpx
import pytest
from pytest_httpx import HTTPXMock

from brreg_wrapper.client import BrregClient
from brreg_wrapper.exceptions import (
    BrregAPIError,
    BrregAuthenticationError,
    BrregDataError,
    BrregForbiddenError,
    BrregGoneError,
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
    Underenhet,
)


def enhet_payload(org_nr: str, navn: str = "Test AS", **overrides) -> dict:
    """A minimal Enhet payload containing every field the model requires."""
    payload = {
        "organisasjonsnummer": org_nr,
        "navn": navn,
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
    }
    payload.update(overrides)
    return payload


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
    expected_url = f"{BrregClient.BASE_URL}/organisasjonsformer"
    # Mock response data structure matching Organisasjonsformer1
    mock_response_data = {
        "_embedded": {
            "organisasjonsformer": [
                {
                    "kode": "AS",
                    "beskrivelse": "Aksjeselskap",
                    "_links": {
                        "self": {
                            "href": (f"{BrregClient.BASE_URL}/organisasjonsformer/AS")
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
async def test_get_kommuner_success(httpx_mock: HTTPXMock):
    """Test successfully retrieving municipalities."""
    expected_url = f"{BrregClient.BASE_URL}/kommuner"
    # Mock response data - API returns a list, client wraps it
    mock_api_response_list = [
        {
            "nummer": "0301",
            "navn": "OSLO",
            "_links": {"self": {"href": f"{BrregClient.BASE_URL}/kommuner/0301"}},
        },
        {
            "nummer": "1101",
            "navn": "EIGERØY",  # Example, might not be real
            "_links": {"self": {"href": f"{BrregClient.BASE_URL}/kommuner/1101"}},
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
async def test_get_enhet_not_found(
    httpx_mock: HTTPXMock, caplog: pytest.LogCaptureFixture
):
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
        with caplog.at_level("DEBUG", logger="brreg_wrapper.client"):
            with pytest.raises(BrregResourceNotFoundError) as exc_info:
                await client.get_enhet(org_nr)

        assert exc_info.value.status_code == 404
        assert not any(record.levelname == "ERROR" for record in caplog.records)
        assert any(
            record.levelname == "DEBUG" and "HTTP error 404" in record.message
            for record in caplog.records
        )

        # Verify the request was made
        request = httpx_mock.get_request()
        assert request is not None
        assert str(request.url) == expected_url
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_get_enhet_server_error_logs_at_error(
    httpx_mock: HTTPXMock, caplog: pytest.LogCaptureFixture
):
    """5xx responses should still be logged at ERROR with exception info."""
    org_nr = "123456789"
    expected_url = f"{BrregClient.BASE_URL}/enheter/{org_nr}"

    httpx_mock.add_response(
        url=expected_url,
        method="GET",
        status_code=500,
        json={"message": "Internal Server Error"},
    )

    client = BrregClient(max_retries=0)
    try:
        with caplog.at_level("DEBUG", logger="brreg_wrapper.client"):
            with pytest.raises(BrregServerError) as exc_info:
                await client.get_enhet(org_nr)

        assert exc_info.value.status_code == 500
        error_records = [r for r in caplog.records if r.levelname == "ERROR"]
        assert error_records
        assert any("HTTP error 500" in record.message for record in error_records)
        assert any(record.exc_info is not None for record in error_records)
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
    mock_response_data = enhet_payload(org_nr, navn="Cache Test AS")
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
        assert client.clear_cache() == 1
        assert client.get_cache_info()["count"] == 0
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_rate_limiting(httpx_mock: HTTPXMock):
    """Consecutive requests are spaced by at least ``rate_limit`` seconds."""
    request_times = []

    def record(request: httpx.Request) -> httpx.Response:
        request_times.append(time.monotonic())
        return httpx.Response(200, json={})

    httpx_mock.add_callback(record, url=f"{BrregClient.BASE_URL}/", is_reusable=True)

    async with BrregClient(rate_limit=0.2) as client:
        await client.get_services()
        await client.get_services()

    assert request_times[1] - request_times[0] >= 0.2


@pytest.mark.asyncio
async def test_rate_limiting_applies_to_concurrent_requests(httpx_mock: HTTPXMock):
    """Concurrent batch requests must not all fire after the same delay."""
    request_times = []

    def record(request: httpx.Request) -> httpx.Response:
        request_times.append(time.monotonic())
        org_nr = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json=enhet_payload(org_nr))

    httpx_mock.add_callback(record, is_reusable=True)

    org_nrs = ["111111111", "222222222", "333333333"]
    async with BrregClient(rate_limit=0.1) as client:
        await client.get_multiple_enheter(org_nrs)

    request_times.sort()
    gaps = [b - a for a, b in zip(request_times, request_times[1:], strict=False)]
    assert all(gap >= 0.09 for gap in gaps), gaps


@pytest.mark.asyncio
async def test_get_multiple_enheter(httpx_mock: HTTPXMock):
    """Test the batch operation to get multiple enheter."""
    # Setup mock responses for two different orgs
    org_nr1 = "123456789"
    org_nr2 = "987654321"

    mock_response1 = enhet_payload(org_nr1, navn="Batch Test 1 AS")
    mock_response2 = enhet_payload(org_nr2, navn="Batch Test 2 AS")

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
        (410, BrregGoneError, "Resource has been removed"),
        (429, BrregRateLimitError, "Rate limit exceeded"),
        (500, BrregServerError, "HTTP error 500"),
        (503, BrregServiceUnavailableError, "Service temporarily unavailable"),
    ]

    for status_code, exception_class, error_pattern in error_mappings:
        # Reset mock for each iteration
        httpx_mock.reset()

        # Setup mock response for this status code
        httpx_mock.add_response(
            url=base_url,
            method="GET",
            json={"message": "Error message"},
            status_code=status_code,
        )

        # Test with fresh client each time; retries would only slow this down
        client = BrregClient(max_retries=0)
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


@pytest.mark.asyncio
async def test_get_underenhet_with_historiske_navn(httpx_mock: HTTPXMock):
    """Underenhet responses may include historiskeNavn from the live API."""
    org_nr = "971917407"
    mock_response_data = {
        "organisasjonsnummer": org_nr,
        "navn": "BETONMAST INNLANDET AS",
        "organisasjonsform": {
            "kode": "BEDR",
            "beskrivelse": "Underenhet til næringsdrivende og offentlig forvaltning",
            "_links": {
                "self": {"href": f"{BrregClient.BASE_URL}/organisasjonsformer/BEDR"}
            },
        },
        "historiskeNavn": [
            {
                "navn": "TOTEN BYGG OG ANLEGG AS",
                "fraDato": "1996-05-22 19:00:08",
                "tilDato": "2003-01-27 20:36:38",
            }
        ],
        "registrertIMvaregisteret": False,
        "registreringsdatoEnhetsregisteret": "1995-02-22",
        "harRegistrertAntallAnsatte": True,
        "_links": {"self": {"href": f"{BrregClient.BASE_URL}/underenheter/{org_nr}"}},
    }
    expected_url = f"{BrregClient.BASE_URL}/underenheter/{org_nr}"

    httpx_mock.add_response(
        url=expected_url,
        method="GET",
        json=mock_response_data,
        status_code=200,
        headers={"Content-Type": "application/json"},
    )

    client = BrregClient()
    try:
        underenhet = await client.get_underenhet(org_nr)
        assert isinstance(underenhet, Underenhet)
        assert underenhet.navn == "BETONMAST INNLANDET AS"
        assert underenhet.historiskeNavn is not None
        assert underenhet.historiskeNavn[0].navn == "TOTEN BYGG OG ANLEGG AS"
    finally:
        await client.close()


# --- Regression tests for robustness fixes ---

EMPTY_SEARCH_PAGE = {
    "_links": {"self": {"href": f"{BrregClient.BASE_URL}/enheter"}},
    "page": {"number": 0, "size": 20, "totalElements": 0, "totalPages": 0},
}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method, path",
    [
        ("download_enheter_json", "/enheter/lastned"),
        ("download_enheter_csv", "/enheter/lastned/csv"),
        ("download_enheter_spreadsheet", "/enheter/lastned/regneark"),
        ("download_underenheter_json", "/underenheter/lastned"),
        ("download_underenheter_csv", "/underenheter/lastned/csv"),
        ("download_underenheter_spreadsheet", "/underenheter/lastned/regneark"),
        ("download_roller_totalbestand", "/roller/totalbestand"),
    ],
)
async def test_download_methods_return_bytes(
    httpx_mock: HTTPXMock, method: str, path: str
):
    """Downloads send a wildcard Accept header (the API rejects specific ones)."""
    httpx_mock.add_response(url=f"{BrregClient.BASE_URL}{path}", content=b"\x1f\x8b")

    async with BrregClient() as client:
        content = await getattr(client, method)()

    assert content == b"\x1f\x8b"
    assert httpx_mock.get_request().headers["Accept"] == "*/*"


@pytest.mark.asyncio
async def test_download_passes_filter_params(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=httpx.URL(
            f"{BrregClient.BASE_URL}/enheter/lastned", params={"kommunenummer": "0301"}
        ),
        content=b"data",
    )

    async with BrregClient() as client:
        assert await client.download_enheter_json(kommunenummer="0301") == b"data"


@pytest.mark.asyncio
async def test_search_cache_keys_include_all_params(httpx_mock: HTTPXMock):
    """Searches differing only in an uncommon param must not share a cache entry."""
    httpx_mock.add_response(json=EMPTY_SEARCH_PAGE, is_reusable=True)

    async with BrregClient(cache_ttl=timedelta(minutes=5)) as client:
        await client.search_enheter(navn="test", konkurs="true")
        await client.search_enheter(navn="test", konkurs="false")
        await client.search_enheter(navn="test", konkurs="true")  # cache hit

    params = [dict(r.url.params) for r in httpx_mock.get_requests()]
    assert params == [
        {"navn": "test", "konkurs": "true"},
        {"navn": "test", "konkurs": "false"},
    ]


@pytest.mark.asyncio
async def test_clear_cache_by_pattern(httpx_mock: HTTPXMock):
    for org_nr in ("111111111", "222222222"):
        httpx_mock.add_response(
            url=f"{BrregClient.BASE_URL}/enheter/{org_nr}", json=enhet_payload(org_nr)
        )

    async with BrregClient(cache_ttl=timedelta(minutes=5)) as client:
        await client.get_enhet("111111111")
        await client.get_enhet("222222222")
        assert client.clear_cache(pattern="111111111") == 1
        assert client.get_cache_info()["count"] == 1


@pytest.mark.asyncio
async def test_cache_is_bounded(httpx_mock: HTTPXMock):
    httpx_mock.add_callback(
        lambda r: httpx.Response(
            200, json=enhet_payload(r.url.path.rsplit("/", 1)[-1])
        ),
        is_reusable=True,
    )

    async with BrregClient(cache_ttl=timedelta(minutes=5), cache_maxsize=2) as c:
        for org_nr in ("111111111", "222222222", "333333333"):
            await c.get_enhet(org_nr)
        assert c.get_cache_info()["count"] == 2


@pytest.mark.asyncio
async def test_search_organizations_uses_valid_param_names(httpx_mock: HTTPXMock):
    """``organisasjonsform.kode`` makes the live API return HTTP 500."""
    httpx_mock.add_response(json=EMPTY_SEARCH_PAGE)

    async with BrregClient() as client:
        await client.search_organizations(
            query="equinor", organization_form="ASA", municipality="0301"
        )

    assert dict(httpx_mock.get_request().url.params) == {
        "navn": "equinor",
        "organisasjonsform": "ASA",
        "kommunenummer": "0301",
        "page": "0",
        "size": "20",
    }


def _no_backoff(client: BrregClient) -> None:
    client._retry_wait = lambda retry_state: 0


@pytest.mark.asyncio
async def test_transient_errors_are_retried(httpx_mock: HTTPXMock):
    url = f"{BrregClient.BASE_URL}/enheter/123456789"
    httpx_mock.add_response(url=url, status_code=503)
    httpx_mock.add_response(url=url, status_code=429)
    httpx_mock.add_response(url=url, json=enhet_payload("123456789"))

    async with BrregClient(max_retries=2) as client:
        _no_backoff(client)
        enhet = await client.get_enhet("123456789")

    assert enhet.organisasjonsnummer == "123456789"
    assert len(httpx_mock.get_requests()) == 3


@pytest.mark.asyncio
async def test_max_retries_counts_retries_not_attempts(httpx_mock: HTTPXMock):
    httpx_mock.add_response(status_code=500, is_reusable=True)

    async with BrregClient(max_retries=2) as client:
        _no_backoff(client)
        with pytest.raises(BrregServerError):
            await client.get_enhet("123456789")

    assert len(httpx_mock.get_requests()) == 3


@pytest.mark.asyncio
async def test_client_errors_are_not_retried(httpx_mock: HTTPXMock):
    httpx_mock.add_response(status_code=404)

    async with BrregClient(max_retries=3) as client:
        with pytest.raises(BrregResourceNotFoundError):
            await client.get_enhet("123456789")

    assert len(httpx_mock.get_requests()) == 1


@pytest.mark.asyncio
async def test_retry_after_header_is_exposed(httpx_mock: HTTPXMock):
    httpx_mock.add_response(status_code=429, headers={"Retry-After": "7"})

    async with BrregClient(max_retries=0) as client:
        with pytest.raises(BrregRateLimitError) as exc_info:
            await client.get_enhet("123456789")

    assert exc_info.value.retry_after == 7.0


@pytest.mark.asyncio
async def test_error_includes_request_params(httpx_mock: HTTPXMock):
    httpx_mock.add_response(status_code=400)

    async with BrregClient() as client:
        with pytest.raises(BrregValidationError) as exc_info:
            await client.search_enheter(navn="x", size=99999)

    assert exc_info.value.request_params == {"navn": "x", "size": "99999"}


@pytest.mark.asyncio
async def test_network_errors_are_wrapped_and_chained(httpx_mock: HTTPXMock):
    httpx_mock.add_exception(httpx.ConnectError("boom"))

    async with BrregClient(max_retries=0) as client:
        with pytest.raises(BrregAPIError) as exc_info:
            await client.get_enhet("123456789")

    assert isinstance(exc_info.value.__cause__, httpx.ConnectError)
    assert exc_info.value.request_url.endswith("/enheter/123456789")


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["12345678", "1234567890", "12345678a", "123/roller"])
async def test_invalid_orgnr_is_rejected_locally(bad: str):
    async with BrregClient() as client:
        with pytest.raises(BrregValidationError):
            await client.get_enhet(bad)


@pytest.mark.asyncio
async def test_orgnr_whitespace_is_normalized(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=f"{BrregClient.BASE_URL}/enheter/923609016",
        json=enhet_payload("923609016"),
    )

    async with BrregClient() as client:
        enhet = await client.get_enhet("923 609 016")

    assert enhet.organisasjonsnummer == "923609016"


@pytest.mark.asyncio
async def test_unknown_response_fields_are_tolerated(httpx_mock: HTTPXMock):
    """New fields added by Brreg must not break parsing."""
    httpx_mock.add_response(
        json=enhet_payload("123456789", nyttFeltFraBrreg={"verdi": 1})
    )

    async with BrregClient() as client:
        enhet = await client.get_enhet("123456789")

    assert enhet.model_extra == {"nyttFeltFraBrreg": {"verdi": 1}}


@pytest.mark.asyncio
async def test_unparseable_response_raises_data_error(httpx_mock: HTTPXMock):
    httpx_mock.add_response(json={"organisasjonsnummer": "123456789"})

    async with BrregClient() as client:
        with pytest.raises(BrregDataError):
            await client.get_enhet("123456789")


@pytest.mark.asyncio
async def test_invalid_json_raises_data_error(httpx_mock: HTTPXMock):
    httpx_mock.add_response(content=b"<html>maintenance</html>")

    async with BrregClient() as client:
        with pytest.raises(BrregDataError):
            await client.get_enhet("123456789")


@pytest.mark.asyncio
async def test_batch_collects_errors_and_dedupes(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=f"{BrregClient.BASE_URL}/enheter/111111111",
        json=enhet_payload("111111111"),
    )
    httpx_mock.add_response(
        url=f"{BrregClient.BASE_URL}/enheter/222222222", status_code=404
    )

    async with BrregClient() as client:
        results = await client.get_multiple_enheter(
            ["111111111", "222222222", "111111111", "bad"]
        )

    assert list(results) == ["111111111", "222222222", "bad"]
    assert isinstance(results["111111111"], Enhet)
    assert isinstance(results["222222222"], BrregResourceNotFoundError)
    assert isinstance(results["bad"], BrregValidationError)
    assert len(httpx_mock.get_requests()) == 2


@pytest.mark.asyncio
async def test_external_client_is_not_closed_and_needs_no_base_url(
    httpx_mock: HTTPXMock,
):
    httpx_mock.add_response(
        url=f"{BrregClient.BASE_URL}/enheter/123456789",
        json=enhet_payload("123456789"),
    )

    async with httpx.AsyncClient() as http:
        async with BrregClient(client=http) as client:
            await client.get_enhet("123456789")
        assert not http.is_closed


@pytest.mark.asyncio
async def test_oppdateringer_are_never_cached(httpx_mock: HTTPXMock):
    """Polling a change feed must always hit the API, even with caching on."""
    httpx_mock.add_response(json=[], is_reusable=True)

    async with BrregClient(cache_ttl=timedelta(minutes=5)) as client:
        await client.get_rolle_oppdateringer(afterId=1)
        await client.get_rolle_oppdateringer(afterId=1)
        assert client.get_cache_info()["count"] == 0

    assert len(httpx_mock.get_requests()) == 2


@pytest.mark.asyncio
async def test_clear_cache_warns_when_pattern_matches_nothing(
    httpx_mock: HTTPXMock, caplog: pytest.LogCaptureFixture
):
    httpx_mock.add_response(json=enhet_payload("111111111"))

    async with BrregClient(cache_ttl=timedelta(minutes=5)) as client:
        await client.get_enhet("111111111")
        with caplog.at_level("WARNING", logger="brreg_wrapper.client"):
            assert client.clear_cache(pattern="enhet_") == 0

    assert any("matched no cache entries" in r.message for r in caplog.records)
