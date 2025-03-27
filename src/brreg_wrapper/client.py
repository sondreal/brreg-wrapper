import httpx

from .models import (
    Enhet,
    Enheter1,
    OppdateringerEnheter1,
    OppdateringerUnderenheter1,
    Organisasjonsformer1,
    Roller,
    RolleRollegruppetyper,
    RolleRolletyper,
    SlettetEnhet,
    SlettetUnderenhet,
    Underenhet,
    Underenheter1,
)


class BrregClient:
    """
    A client for interacting with the Brønnøysund Register Centre (Brreg) API.
    API Documentation: https://data.brreg.no/enhetsregisteret/api/dokumentasjon/no/index.html
    """

    BASE_URL = "https://data.brreg.no/enhetsregisteret/api"

    def __init__(self, timeout: float = 10.0, client: httpx.AsyncClient | None = None):
        """
        Initializes the BrregClient.

        Args:
            timeout: The timeout for HTTP requests in seconds. Defaults to 10.0.
            client: An optional httpx.AsyncClient instance. If not provided,
                    a new one is created.
        """
        self._client = client or httpx.AsyncClient(
            base_url=self.BASE_URL, timeout=timeout
        )

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json: dict | None = None,
    ) -> httpx.Response:
        """
        Makes an asynchronous HTTP request to the Brreg API.

        Args:
            method: The HTTP method (e.g., "GET", "POST").
            endpoint: The API endpoint path (e.g., "/enheter").
            params: Optional query parameters.
            json: Optional JSON body for POST/PUT requests.

        Returns:
            The httpx.Response object.

            Raises:
            httpx.HTTPStatusError: If the API returns an error status code.
        """
        headers = {"Accept": "application/json"}
        try:
            response = await self._client.request(
                method, endpoint, params=params, json=json, headers=headers
            )
            # Raise an exception for 4xx or 5xx status codes
            response.raise_for_status()
            return response
        except httpx.RequestError as exc:
            print(f"An error occurred while requesting {exc.request.url!r}: {exc}")
            raise  # Re-raise or handle specific errors as needed
        except httpx.HTTPStatusError as exc:
            error_message = (
                f"Error response {exc.response.status_code} "
                f"while requesting {exc.request.url!r}: {exc.response.text}"
            )
            print(error_message)
            raise  # Re-raise or handle specific errors as needed

    async def __aenter__(self):
        """Enter the async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context manager and close the client."""
        await self.close()

    async def close(self):
        """Closes the underlying httpx client."""
        await self._client.aclose()

    async def get_enhet(self, organisasjonsnummer: str) -> Enhet | SlettetEnhet:
        """
        Retrieves information about a specific entity (enhet) by its
        organization number. Can also return a SlettetEnhet if the entity is deleted.
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-enheter-detalj

        Args:
            organisasjonsnummer: The 9-digit organization number.

        Returns:
            An Enhet or SlettetEnhet object containing the entity's information.
        """
        endpoint = f"/enheter/{organisasjonsnummer}"
        response = await self._request("GET", endpoint)
        data = response.json()
        # Check if it's a deleted entity
        # (schema indicates 'slettedato'/'respons_klasse')
        if data.get("respons_klasse") == "SlettetEnhet" or "slettedato" in data:
            try:
                # Attempt parsing as SlettetEnhet first
                return SlettetEnhet.model_validate(data)
            except Exception:
                # Fallback if parsing SlettetEnhet fails unexpectedly
                pass
        # Default to parsing as Enhet
        return Enhet.model_validate(data)

    async def search_enheter(self, **kwargs) -> Enheter1:
        """
        Searches for entities (enheter) based on various criteria.
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-enheter-oppslag

        Args:
            **kwargs: Search parameters as defined in the API documentation.
                      Examples: navn, organisasjonsform, postadresse.postnummer, etc.

        Returns:
            An Enheter1 object containing the search results.
        """
        endpoint = "/enheter"
        params = {
            k: v for k, v in kwargs.items() if v is not None
        }  # Filter out None values
        response = await self._request("GET", endpoint, params=params)
        return Enheter1.model_validate(response.json())

    async def get_underenhet(
        self, organisasjonsnummer: str
    ) -> Underenhet | SlettetUnderenhet:
        """
        Retrieves information about a specific sub-entity (underenhet) by its
        organization number. Can also return a SlettetUnderenhet if the entity
        is deleted.
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-underenheter-detalj

        Args:
            organisasjonsnummer: The 9-digit organization number of the sub-entity.

        Returns:
            A Underenhet or SlettetUnderenhet object containing the
            sub-entity's information.
        """
        endpoint = f"/underenheter/{organisasjonsnummer}"
        response = await self._request("GET", endpoint)
        data = response.json()
        # Check if it's a deleted entity
        if data.get("respons_klasse") == "SlettetEnhet" or "slettedato" in data:
            try:
                # Attempt parsing as SlettetUnderenhet first
                return SlettetUnderenhet.model_validate(data)
            except Exception:
                # Fallback if parsing SlettetUnderenhet fails unexpectedly
                pass
        # Default to parsing as Underenhet
        return Underenhet.model_validate(data)

    async def search_underenheter(self, **kwargs) -> Underenheter1:
        """
        Searches for sub-entities (underenheter) based on various criteria.
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-underenheter-oppslag

        Args:
            **kwargs: Search parameters as defined in the API documentation.

        Returns:
            A Underenheter1 object containing the search results.
        """
        endpoint = "/underenheter"
        params = {
            k: v for k, v in kwargs.items() if v is not None
        }  # Filter out None values
        response = await self._request("GET", endpoint, params=params)
        return Underenheter1.model_validate(response.json())

    async def get_rollegrupper(self) -> RolleRollegruppetyper:
        """
        Retrieves all role groups types.
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-roller-rollegrupper

        Returns:
            A RolleRollegruppetyper object containing the list of role group types.
        """
        endpoint = "/roller/rollegrupper"
        response = await self._request("GET", endpoint)
        return RolleRollegruppetyper.model_validate(response.json())

    async def get_roller(self) -> RolleRolletyper:
        """
        Retrieves all role types.
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-roller-roller

        Returns:
            A RolleRolletyper object containing the list of role types.
        """
        endpoint = "/roller/roller"
        response = await self._request("GET", endpoint)
        return RolleRolletyper.model_validate(response.json())

    async def get_enhet_roller(self, organisasjonsnummer: str) -> Roller:
        """
        Retrieves roles associated with a specific entity (enhet).
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-roller-roller-for-enhet

        Args:
            organisasjonsnummer: The 9-digit organization number of the entity.

        Returns:
            A Roller object containing the roles for the entity.
        """
        endpoint = f"/enheter/{organisasjonsnummer}/roller"
        response = await self._request("GET", endpoint)
        return Roller.model_validate(response.json())

    async def get_underenhet_roller(self, organisasjonsnummer: str) -> Roller:
        """
        Retrieves roles associated with a specific sub-entity (underenhet).
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-roller-roller-for-underenhet

        Args:
            organisasjonsnummer: The 9-digit organization number of the sub-entity.

        Returns:
            A Roller object containing the roles for the sub-entity.
        """
        endpoint = f"/underenheter/{organisasjonsnummer}/roller"
        response = await self._request("GET", endpoint)
        return Roller.model_validate(response.json())

    async def get_grunndata_enhet(self, organisasjonsnummer: str) -> dict:
        """
        Retrieves basic data (grunndata) for a specific entity (enhet).
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-grunndata-enhet

        Args:
            organisasjonsnummer: The 9-digit organization number of the entity.

        Returns:
            A dictionary containing the basic data for the entity.
        """
        endpoint = f"/grunndata/enheter/{organisasjonsnummer}"
        response = await self._request("GET", endpoint)
        return response.json()

    async def get_grunndata_underenhet(self, organisasjonsnummer: str) -> dict:
        """
        Retrieves basic data (grunndata) for a specific sub-entity (underenhet).
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-grunndata-underenhet

        Args:
            organisasjonsnummer: The 9-digit organization number of the sub-entity.

        Returns:
            A dictionary containing the basic data for the sub-entity.
        """
        endpoint = f"/grunndata/underenheter/{organisasjonsnummer}"
        response = await self._request("GET", endpoint)
        return response.json()

    async def get_organisasjonsformer(self) -> Organisasjonsformer1:
        """
        Retrieves all organization forms.
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-kodeverk-organisasjonsformer

        Returns:
            An Organisasjonsformer1 object containing the list of organization forms.
        """
        endpoint = "/kodeverk/organisasjonsformer"
        response = await self._request("GET", endpoint)
        return Organisasjonsformer1.model_validate(response.json())

    async def get_naeringskoder(
        self,
    ) -> dict:
        """
        Retrieves all industry codes (Næringskoder - NACE).
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-kodeverk-naeringskoder

        Returns:
            A dictionary containing the list of industry codes.
        """
        endpoint = "/kodeverk/naeringskoder"
        response = await self._request("GET", endpoint)
        return response.json()

    async def get_sektorkoder(
        self,
    ) -> dict:
        """
        Retrieves all sector codes.
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-kodeverk-sektorkoder

        Returns:
            A dictionary containing the list of sector codes.
        """
        endpoint = "/kodeverk/sektorkoder"
        response = await self._request("GET", endpoint)
        return response.json()

    async def get_enhet_oppdateringer(self, **kwargs) -> OppdateringerEnheter1:
        """
        Retrieves updates for entities (enheter).
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-oppdateringer-enheter

        Args:
            **kwargs: Optional query parameters like oppdateringsid, dato,
                      fraAntallDoegn, status, oppdateringstype, page, size.

        Returns:
            An OppdateringerEnheter1 object containing the entity updates.
        """
        endpoint = "/oppdateringer/enheter"
        params = {
            k: v for k, v in kwargs.items() if v is not None
        }  # Filter out None values
        response = await self._request("GET", endpoint, params=params)
        return OppdateringerEnheter1.model_validate(response.json())

    async def get_underenhet_oppdateringer(
        self, **kwargs
    ) -> OppdateringerUnderenheter1:
        """
        Retrieves updates for sub-entities (underenheter).
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-oppdateringer-underenheter

        Args:
            **kwargs: Optional query parameters like oppdateringsid, dato,
                      fraAntallDoegn, status, oppdateringstype, page, size.

        Returns:
            An OppdateringerUnderenheter1 object containing the sub-entity updates.
        """
        endpoint = "/oppdateringer/underenheter"
        params = {
            k: v for k, v in kwargs.items() if v is not None
        }  # Filter out None values
        response = await self._request("GET", endpoint, params=params)
        return OppdateringerUnderenheter1.model_validate(response.json())

    async def get_enhet_historikk(self, organisasjonsnummer: str) -> dict:
        """
        Retrieves historical data for a specific entity (enhet).
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-historikk-enhet

        Args:
            organisasjonsnummer: The 9-digit organization number of the entity.

        Returns:
            A dictionary containing the historical data for the entity.
        """
        endpoint = f"/enheter/{organisasjonsnummer}/historikk"
        response = await self._request("GET", endpoint)
        return response.json()

    async def get_underenhet_historikk(self, organisasjonsnummer: str) -> dict:
        """
        Retrieves historical data for a specific sub-entity (underenhet).
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-historikk-underenhet

        Args:
            organisasjonsnummer: The 9-digit organization number of the sub-entity.

        Returns:
            A dictionary containing the historical data for the sub-entity.
        """
        endpoint = f"/underenheter/{organisasjonsnummer}/historikk"
        response = await self._request("GET", endpoint)
        return response.json()
