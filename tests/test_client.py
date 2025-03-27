import httpx
import pytest
from pytest_httpx import HTTPXMock

from brreg_wrapper.client import BrregClient


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
    mock_response_data = {"organisasjonsnummer": org_nr, "navn": "Test Company AS"}
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
        assert enhet_data == mock_response_data

        # Verify the request was made as expected
        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "GET"
        assert str(request.url) == expected_url
        assert request.headers["Accept"] == "application/json"
    finally:
        await client.close()


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
async def test_search_enheter_success(httpx_mock: HTTPXMock):
    """Test successfully searching for entities."""
    search_params = {"navn": "Test Search", "size": 5}
    mock_response_data = {
        "_embedded": {
            "enheter": [
                {"organisasjonsnummer": "111111111", "navn": "Test Search Result 1"},
                {"organisasjonsnummer": "222222222", "navn": "Test Search Result 2"},
            ]
        },
        "page": {"number": 0, "size": 5, "totalElements": 2, "totalPages": 1},
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
        assert search_results == mock_response_data

        # Verify the request was made as expected
        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "GET"
        # Check the exact URL requested
        assert str(request.url) == str(expected_url_with_params)
        assert request.headers["Accept"] == "application/json"
    finally:
        await client.close()
