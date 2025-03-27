from datetime import date

import httpx
import pytest
from pytest_httpx import HTTPXMock

from brreg_wrapper.client import BrregClient
from brreg_wrapper.models import (
    Enhet,
    Enheter1,
    FieldEmbedded,
    FieldLinks3,
    Organisasjonsformer1,  # Added for kodeverk test
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
                            "href": f"{BrregClient.BASE_URL}/kodeverk/organisasjonsformer/AS"
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
                            "href": f"{BrregClient.BASE_URL}/kodeverk/naeringskoder/01.110"
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
