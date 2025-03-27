import httpx


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
            # Re-raise or handle specific errors as needed
            raise
        except httpx.HTTPStatusError as exc:
            error_message = (
                f"Error response {exc.response.status_code} "
                f"while requesting {exc.request.url!r}: {exc.response.text}"
            )
            print(error_message)
            # Re-raise or handle specific errors as needed
            raise

    async def close(self):
        """Closes the underlying httpx client."""
        await self._client.aclose()

    # --- API Methods will be added below ---

    async def get_enhet(self, organisasjonsnummer: str) -> dict:
        """
        Retrieves information about a specific entity (enhet) by its
        organization number.
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-enheter-detalj

        Args:
            organisasjonsnummer: The 9-digit organization number.

        Returns:
            A dictionary containing the entity's information.
        """
        endpoint = f"/enheter/{organisasjonsnummer}"
        response = await self._request("GET", endpoint)
        return response.json()

    async def search_enheter(self, **kwargs) -> dict:
        """
        Searches for entities (enheter) based on various criteria.
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-enheter-oppslag

        Args:
            **kwargs: Search parameters as defined in the API documentation.
                      Examples: navn, organisasjonsform, postadresse.postnummer, etc.

        Returns:
            A dictionary containing the search results.
        """
        endpoint = "/enheter"
        # Filter out None values from kwargs
        params = {k: v for k, v in kwargs.items() if v is not None}
        response = await self._request("GET", endpoint, params=params)
        return response.json()

    async def get_underenhet(self, organisasjonsnummer: str) -> dict:
        """
        Retrieves information about a specific sub-entity (underenhet) by its
        organization number.
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-underenheter-detalj

        Args:
            organisasjonsnummer: The 9-digit organization number of the sub-entity.

        Returns:
            A dictionary containing the sub-entity's information.
        """
        endpoint = f"/underenheter/{organisasjonsnummer}"
        response = await self._request("GET", endpoint)
        return response.json()

    async def search_underenheter(self, **kwargs) -> dict:
        """
        Searches for sub-entities (underenheter) based on various criteria.
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-underenheter-oppslag

        Args:
            **kwargs: Search parameters as defined in the API documentation.

        Returns:
            A dictionary containing the search results.
        """
        endpoint = "/underenheter"
        # Filter out None values from kwargs
        params = {k: v for k, v in kwargs.items() if v is not None}
        response = await self._request("GET", endpoint, params=params)
        return response.json()

    # --- Roles Endpoints ---

    async def get_rollegrupper(self) -> dict:
        """
        Retrieves all role groups.
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-roller-rollegrupper

        Returns:
            A dictionary containing the list of role groups.
        """
        endpoint = "/roller/rollegrupper"
        response = await self._request("GET", endpoint)
        return response.json()

    async def get_roller(self) -> dict:
        """
        Retrieves all roles.
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-roller-roller

        Returns:
            A dictionary containing the list of roles.
        """
        endpoint = "/roller/roller"
        response = await self._request("GET", endpoint)
        return response.json()

    async def get_enhet_roller(self, organisasjonsnummer: str) -> dict:
        """
        Retrieves roles associated with a specific entity (enhet).
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-roller-roller-for-enhet

        Args:
            organisasjonsnummer: The 9-digit organization number of the entity.

        Returns:
            A dictionary containing the roles for the entity.
        """
        endpoint = f"/enheter/{organisasjonsnummer}/roller"
        response = await self._request("GET", endpoint)
        return response.json()

    async def get_underenhet_roller(self, organisasjonsnummer: str) -> dict:
        """
        Retrieves roles associated with a specific sub-entity (underenhet).
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-roller-roller-for-underenhet

        Args:
            organisasjonsnummer: The 9-digit organization number of the sub-entity.

        Returns:
            A dictionary containing the roles for the sub-entity.
        """
        endpoint = f"/underenheter/{organisasjonsnummer}/roller"
        response = await self._request("GET", endpoint)
        return response.json()

    # --- Grunndata Endpoints ---

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

    # --- Code List Endpoints ---

    async def get_organisasjonsformer(self) -> dict:
        """
        Retrieves all organization forms.
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-kodeverk-organisasjonsformer

        Returns:
            A dictionary containing the list of organization forms.
        """
        endpoint = "/organisasjonsformer"
        response = await self._request("GET", endpoint)
        return response.json()

    async def get_naeringskoder(self) -> dict:
        """
        Retrieves all industry codes (Næringskoder - NACE).
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-kodeverk-naeringskoder

        Returns:
            A dictionary containing the list of industry codes.
        """
        endpoint = "/naeringskoder"
        response = await self._request("GET", endpoint)
        return response.json()

    async def get_sektorkoder(self) -> dict:
        """
        Retrieves all sector codes.
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-kodeverk-sektorkoder

        Returns:
            A dictionary containing the list of sector codes.
        """
        endpoint = "/sektorkoder"
        response = await self._request("GET", endpoint)
        return response.json()

    # --- Update Endpoints ---

    async def get_enhet_oppdateringer(self, **kwargs) -> dict:
        """
        Retrieves updates for entities (enheter).
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-oppdateringer-enheter

        Args:
            **kwargs: Optional query parameters like oppdateringsid, dato,
                      fraAntallDoegn, status, oppdateringstype, page, size.

        Returns:
            A dictionary containing the entity updates.
        """
        endpoint = "/oppdateringer/enheter"
        params = {k: v for k, v in kwargs.items() if v is not None}
        response = await self._request("GET", endpoint, params=params)
        return response.json()

    async def get_underenhet_oppdateringer(self, **kwargs) -> dict:
        """
        Retrieves updates for sub-entities (underenheter).
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-oppdateringer-underenheter

        Args:
            **kwargs: Optional query parameters like oppdateringsid, dato,
                      fraAntallDoegn, status, oppdateringstype, page, size.

        Returns:
            A dictionary containing the sub-entity updates.
        """
        endpoint = "/oppdateringer/underenheter"
        params = {k: v for k, v in kwargs.items() if v is not None}
        response = await self._request("GET", endpoint, params=params)
        return response.json()

    # --- History Endpoints ---

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
