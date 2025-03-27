from typing import Any, Dict

import httpx

from .models import (
    Enhet,
    Enheter1,
    Kommune,
    Kommuner1,
    Matrikkelenheter,
    OppdateringerEnheter1,
    OppdateringerUnderenheter1,
    Organisasjonsform,
    Organisasjonsformer1,
    OrganisasjonsformerEnheter,
    OrganisasjonsformerUnderenheter,
    RolleOppdateringer,
    Roller,
    RolleRepresentanter,
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

    async def _download_request(
        self,
        method: str,
        endpoint: str,
        accept_header: str,
        params: dict | None = None,
    ) -> httpx.Response:
        """
        Makes an asynchronous HTTP request intended for downloading files.

        Args:
            method: The HTTP method (usually "GET").
            endpoint: The API endpoint path.
            accept_header: The value for the 'Accept' header (e.g., 'text/csv').
            params: Optional query parameters.

        Returns:
            The raw httpx.Response object, allowing access to content, headers, etc.

        Raises:
            httpx.HTTPStatusError: If the API returns an error status code.
        """
        headers = {"Accept": accept_header}
        try:
            # Use stream=True if you anticipate large files and want to handle streaming
            response = await self._client.request(
                method, endpoint, params=params, headers=headers
            )
            response.raise_for_status()
            return response
        except httpx.RequestError as exc:
            print(f"An error occurred while requesting {exc.request.url!r}: {exc}")
            raise
        except httpx.HTTPStatusError as exc:
            error_message = (
                f"Error response {exc.response.status_code} "
                f"while requesting {exc.request.url!r}: {exc.response.text}"
            )
            print(error_message)
            raise

    async def __aenter__(self):
        """Enter the async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context manager and close the client."""
        await self.close()

    async def close(self):
        """Closes the underlying httpx client."""
        await self._client.aclose()

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Generelt Endpoints
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~

    async def get_services(self) -> Dict[str, Any]:
        """
        Retrieves the list of available services/endpoints from the root API endpoint.
        Ref: Provided Swagger (GET /enhetsregisteret/api)

        Returns:
            A dictionary representing the available services, likely containing links.
        """
        endpoint = "/"
        response = await self._request("GET", endpoint)
        return response.json()

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Enhet Endpoints
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~

    async def get_enhet(self, organisasjonsnummer: str) -> Enhet | SlettetEnhet:
        """
        Retrieves information about a specific entity (enhet) by its
        organization number. Can also return a SlettetEnhet if the entity is deleted.
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-enheter-detalj

        Args:
            organisasjonsnummer: The 9-digit organization number.

        Returns:
            An Enhet or SlettetEnhet object containing the entity's information.
            Note: Use `.model_dump(mode="json")` for JSON serialization to handle
                  types like dates correctly.
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
            Note: Use `.model_dump(mode="json")` on the contained models for
                  JSON serialization if needed.
        """
        endpoint = "/enheter"
        params = {
            k: v for k, v in kwargs.items() if v is not None
        }  # Filter out None values
        response = await self._request("GET", endpoint, params=params)
        return Enheter1.model_validate(response.json())

    async def download_enheter_json(self, **kwargs) -> httpx.Response:
        """
        Downloads entities (enheter) as a JSON file.
        Ref: Provided Swagger (GET /enhetsregisteret/api/enheter/lastned)

        Args:
            **kwargs: Optional filter parameters similar to search_enheter.

        Returns:
            An httpx.Response object containing the JSON file content.
            Use response.content or response.text to access the data.
        """
        endpoint = "/enheter/lastned"
        params = {k: v for k, v in kwargs.items() if v is not None}
        # Assuming standard JSON MIME type
        accept_header = "application/json"
        return await self._download_request(
            "GET", endpoint, accept_header, params=params
        )

    async def download_enheter_csv(self, **kwargs) -> httpx.Response:
        """
        Downloads entities (enheter) as a CSV file.
        Ref: Provided Swagger (GET /enhetsregisteret/api/enheter/lastned/csv)

        Args:
            **kwargs: Optional filter parameters. Check API docs for specifics.
                      Often includes parameters like 'levertEtter'.

        Returns:
            An httpx.Response object containing the CSV file content.
            Use response.content or response.text to access the data.
        """
        endpoint = "/enheter/lastned/csv"
        params = {k: v for k, v in kwargs.items() if v is not None}
        accept_header = "text/csv"  # Standard CSV MIME type
        return await self._download_request(
            "GET", endpoint, accept_header, params=params
        )

    async def download_enheter_spreadsheet(self, **kwargs) -> httpx.Response:
        """
        Downloads entities (enheter) as a spreadsheet file (likely Excel).
        Ref: Provided Swagger (GET /enhetsregisteret/api/enheter/lastned/regneark)

        Args:
            **kwargs: Optional filter parameters. Check API docs for specifics.

        Returns:
            An httpx.Response object containing the spreadsheet file content.
            Use response.content to access the binary data.
        """
        endpoint = "/enheter/lastned/regneark"
        params = {k: v for k, v in kwargs.items() if v is not None}
        # Common MIME type for Excel files
        accept_header = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        # Alternative might be 'application/vnd.ms-excel' for older formats
        return await self._download_request(
            "GET", endpoint, accept_header, params=params
        )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Underenhet Endpoints
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~

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
            Note: Use `.model_dump(mode="json")` for JSON serialization to handle
                  types like dates correctly.
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
            Note: Use `.model_dump(mode="json")` on the contained models for
                  JSON serialization if needed.
        """
        endpoint = "/underenheter"
        params = {
            k: v for k, v in kwargs.items() if v is not None
        }  # Filter out None values
        response = await self._request("GET", endpoint, params=params)
        return Underenheter1.model_validate(response.json())

    async def download_underenheter_json(self, **kwargs) -> httpx.Response:
        """
        Downloads sub-entities (underenheter) as a JSON file.
        Ref: Provided Swagger (GET /enhetsregisteret/api/underenheter/lastned)

        Args:
            **kwargs: Optional filter parameters similar to search_underenheter.

        Returns:
            An httpx.Response object containing the JSON file content.
            Use response.content or response.text to access the data.
        """
        endpoint = "/underenheter/lastned"
        params = {k: v for k, v in kwargs.items() if v is not None}
        accept_header = "application/json"
        return await self._download_request(
            "GET", endpoint, accept_header, params=params
        )

    async def download_underenheter_csv(self, **kwargs) -> httpx.Response:
        """
        Downloads sub-entities (underenheter) as a CSV file.
        Ref: Provided Swagger (GET /enhetsregisteret/api/underenheter/lastned/csv)

        Args:
            **kwargs: Optional filter parameters. Check API docs for specifics.

        Returns:
            An httpx.Response object containing the CSV file content.
            Use response.content or response.text to access the data.
        """
        endpoint = "/underenheter/lastned/csv"
        params = {k: v for k, v in kwargs.items() if v is not None}
        accept_header = "text/csv"
        return await self._download_request(
            "GET", endpoint, accept_header, params=params
        )

    async def download_underenheter_spreadsheet(self, **kwargs) -> httpx.Response:
        """
        Downloads sub-entities (underenheter) as a spreadsheet file (likely Excel).
        Ref: Provided Swagger (GET /enhetsregisteret/api/underenheter/lastned/regneark)

        Args:
            **kwargs: Optional filter parameters. Check API docs for specifics.

        Returns:
            An httpx.Response object containing the spreadsheet file content.
            Use response.content to access the binary data.
        """
        endpoint = "/underenheter/lastned/regneark"
        params = {k: v for k, v in kwargs.items() if v is not None}
        accept_header = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        return await self._download_request(
            "GET", endpoint, accept_header, params=params
        )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Roller Endpoints
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~

    async def get_rollegrupper(self) -> RolleRollegruppetyper:
        """
        Retrieves all role groups types.
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-roller-rollegrupper
             (Old link, endpoint confirmed from user)

        Returns:
            A RolleRollegruppetyper object containing the list of role group types.
            Note: This method fetches all defined role group types, not roles for a
                  specific entity. Use `get_enhet_roller` or `get_underenhet_roller`
                  for entity-specific roles.
                  Use `.model_dump(mode="json")` for JSON serialization if needed.
        """
        endpoint = (
            "/roller/rollegruppetyper"  # Corrected endpoint based on user provided docs
        )
        response = await self._request("GET", endpoint)
        # The API returns the list directly, not nested under a key.
        data = response.json()
        if isinstance(data, list):
            # Wrap the list response to match the RolleRollegruppetyper model structure
            # which expects {"_embedded": {"rollegruppetyper": [...]}}
            wrapped_data = {"_embedded": {"rollegruppetyper": data}}
            return RolleRollegruppetyper.model_validate(wrapped_data)
        else:
            # If the response is already structured (unexpected for this endpoint),
            # validate directly, though this path is unlikely for /kodeverk endpoints.
            return RolleRollegruppetyper.model_validate(data)

    async def get_roller(self) -> RolleRolletyper:
        """
        Retrieves all role types.
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-roller-roller

        Returns:
            A RolleRolletyper object containing the list of role types.
            Note: This method fetches all defined role types.
                  Use `.model_dump(mode="json")` for JSON serialization if needed.
        """
        endpoint = (
            "/roller/rolletyper"  # Corrected endpoint based on user provided docs
        )
        response = await self._request("GET", endpoint)
        # The API returns the list directly, not nested under a key.
        data = response.json()
        if isinstance(data, list):
            # Wrap the list response to match the RolleRolletyper model structure
            # which expects {"_embedded": {"rolletyper": [...]}}
            wrapped_data = {"_embedded": {"rolletyper": data}}
            return RolleRolletyper.model_validate(wrapped_data)
        else:
            # If the response is already structured (unexpected for this endpoint),
            # validate directly, though this path is unlikely for /kodeverk endpoints.
            return RolleRolletyper.model_validate(data)

    async def get_enhet_roller(self, organisasjonsnummer: str) -> Roller:
        """
        Retrieves roles associated with a specific entity (enhet).
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-roller-roller-for-enhet

        Args:
            organisasjonsnummer: The 9-digit organization number of the entity.

        Returns:
            A Roller object containing the roles for the entity.
            Note: Use `.model_dump(mode="json")` for JSON serialization if needed.
        """
        endpoint = f"/enheter/{organisasjonsnummer}/roller"
        response = await self._request("GET", endpoint)
        return Roller.model_validate(response.json())

    async def download_roller_totalbestand(self) -> httpx.Response:
        """
        Downloads the total inventory of roles as a zipped JSON file.
        Ref: Provided Swagger (GET /enhetsregisteret/api/roller/totalbestand)

        Returns:
            An httpx.Response object containing the zipped JSON file content.
            Use response.content to access the binary data.
        """
        endpoint = "/roller/totalbestand"
        # MIME type for zip files
        accept_header = "application/zip"
        return await self._download_request("GET", endpoint, accept_header)

    async def get_rolle_representanter(self) -> RolleRepresentanter:
        """
        Retrieves all role representatives.
        Ref: Provided Swagger (GET /enhetsregisteret/api/roller/representanter)

        Returns:
            A RolleRepresentanter object containing the list of role representatives.
            Note: Use `.model_dump(mode="json")` on the contained models for
                  JSON serialization if needed.
        """
        endpoint = "/roller/representanter"
        response = await self._request("GET", endpoint)
        # Model expects data directly (likely with _embedded)
        return RolleRepresentanter.model_validate(response.json())

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Kommuner Endpoints
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~

    async def get_kommuner(self) -> Kommuner1:
        """
        Retrieves all municipalities (kommuner).
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-kodeverk-kommuner

        Returns:
            A Kommuner1 object containing the list of municipalities.
            Note: Use `.model_dump(mode="json")` on the contained models for
                  JSON serialization if needed.
        """
        endpoint = "/kommuner"  # Corrected endpoint based on user provided docs
        response = await self._request("GET", endpoint)
        # The API returns the list directly, not nested under a key.
        data = response.json()
        if isinstance(data, list):
            # Wrap the list response to match the Kommuner1 model structure
            wrapped_data = {"_embedded": {"kommuner": data}}
            return Kommuner1.model_validate(wrapped_data)
        else:
            # If the response is already structured, validate directly
            return Kommuner1.model_validate(data)

    async def get_kommune(self, kommunenummer: str) -> Kommune:
        """
        Retrieves information about a specific municipality (kommune) by its number.
        Ref: Provided Swagger (GET /enhetsregisteret/api/kommuner/{kommunenr})

        Args:
            kommunenummer: The municipality number.

        Returns:
            A Kommune object containing the municipality's information.
            Note: Use `.model_dump(mode="json")` for JSON serialization if needed.
        """
        endpoint = f"/kommuner/{kommunenummer}"
        response = await self._request("GET", endpoint)
        # The Kommune model expects the data directly
        return Kommune.model_validate(response.json())

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Organisasjonsformer Endpoints
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~

    async def get_organisasjonsformer(self) -> Organisasjonsformer1:
        """
        Retrieves all organization forms.
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-kodeverk-organisasjonsformer

        Returns:
            An Organisasjonsformer1 object containing the list of organization forms.
            Note: Use `.model_dump(mode="json")` on the contained models for
                  JSON serialization if needed.
        """
        endpoint = (
            "/organisasjonsformer"  # Corrected endpoint based on user provided docs
        )
        response = await self._request("GET", endpoint)
        # Assuming the response structure might be a direct list like kommuner or nested
        data = response.json()
        # Check if the response is a list and wrap if necessary, similar to kommuner
        # This assumes the model Organisasjonsformer1 expects a structure like
        # {"_embedded": {"organisasjonsformer": [...]}} if the API returns a list.
        # If the API returns the nested structure directly, this check isn't needed.
        # Adjust based on actual API behavior or model definition if validation fails.
        if isinstance(data, list):
            # Wrap the list response if the model expects it
            # Adjust the key "organisasjonsformer" if the model expects something else
            wrapped_data = {"_embedded": {"organisasjonsformer": data}}
            return Organisasjonsformer1.model_validate(wrapped_data)
        else:
            # If the response is already structured as the model expects
            return Organisasjonsformer1.model_validate(data)

    async def get_organisasjonsformer_enheter(self) -> OrganisasjonsformerEnheter:
        """
        Retrieves organization forms applicable to main entities (enheter).
        Ref: Provided Swagger (GET /enhetsregisteret/api/organisasjonsformer/enheter)

        Returns:
            An OrganisasjonsformerEnheter object containing the list of organization
            forms for entities.
            Note: Use `.model_dump(mode="json")` on contained models for JSON
                  serialization if needed.
        """
        endpoint = "/organisasjonsformer/enheter"
        response = await self._request("GET", endpoint)
        # Model expects data directly (likely with _embedded)
        return OrganisasjonsformerEnheter.model_validate(response.json())

    async def get_organisasjonsformer_underenheter(
        self,
    ) -> OrganisasjonsformerUnderenheter:
        """
        Retrieves organization forms applicable to sub-entities (underenheter).
        Ref: GET /enhetsregisteret/api/organisasjonsformer/underenheter (Swagger)

        Returns:
            An OrganisasjonsformerUnderenheter object containing the list of
            organization forms for sub-entities.
            Note: Use `.model_dump(mode="json")` on contained models for JSON
                  serialization if needed.
        """
        endpoint = "/organisasjonsformer/underenheter"
        response = await self._request("GET", endpoint)
        # Model expects data directly (likely with _embedded)
        return OrganisasjonsformerUnderenheter.model_validate(response.json())

    async def get_organisasjonsform(self, organisasjonskode: str) -> Organisasjonsform:
        """
        Retrieves the description of a specific organization form by its code.
        Ref: GET /enhetsregisteret/api/organisasjonsformer/{organisasjonskode} (Swagger)

        Args:
            organisasjonskode: The code of the organization form.

        Returns:
            An Organisasjonsform object containing the organization form's description.
            Note: Use `.model_dump(mode="json")` for JSON serialization if needed.
        """
        endpoint = f"/organisasjonsformer/{organisasjonskode}"
        response = await self._request("GET", endpoint)
        # The Organisasjonsform model expects the data directly
        return Organisasjonsform.model_validate(response.json())

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Matrikkelenhet Endpoints
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~

    async def get_matrikkelenheter(self, **kwargs) -> Matrikkelenheter:
        """
        Retrieves cadastral units (matrikkelenheter).
        Ref: Provided Swagger (GET /enhetsregisteret/api/matrikkelenhet)

        Args:
            **kwargs: Optional query parameters (check API docs for specifics).

        Returns:
            A Matrikkelenheter object (RootModel wrapping a list) containing the
            cadastral units.
            Note: Use `.model_dump(mode="json")` on contained models for JSON
                  serialization if needed.
        """
        endpoint = "/matrikkelenhet"
        params = {k: v for k, v in kwargs.items() if v is not None}
        response = await self._request("GET", endpoint, params=params)
        # Matrikkelenheter is a RootModel expecting a list directly
        return Matrikkelenheter.model_validate(response.json())

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Oppdateringer Endpoints
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~

    async def get_enhet_oppdateringer(self, **kwargs) -> OppdateringerEnheter1:
        """
        Retrieves updates for entities (enheter).
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-oppdateringer-enheter

        Args:
            **kwargs: Optional query parameters like oppdateringsid, dato,
                      fraAntallDoegn, status, oppdateringstype, page, size.

        Returns:
            An OppdateringerEnheter1 object containing the entity updates.
            Note: Use `.model_dump(mode="json")` on the contained models for
                  JSON serialization if needed.
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
            Note: Use `.model_dump(mode="json")` on the contained models for
                  JSON serialization if needed.
        """
        endpoint = "/oppdateringer/underenheter"
        params = {
            k: v for k, v in kwargs.items() if v is not None
        }  # Filter out None values
        response = await self._request("GET", endpoint, params=params)
        return OppdateringerUnderenheter1.model_validate(response.json())

    async def get_rolle_oppdateringer(self, **kwargs) -> RolleOppdateringer:
        """
        Retrieves updates for roles.
        Ref: Provided Swagger (GET /enhetsregisteret/api/oppdateringer/roller)

        Args:
            **kwargs: Optional query parameters like oppdateringsid, dato, etc.
                      (Check API docs for specifics).

        Returns:
            A RolleOppdateringer object (RootModel wrapping a list) containing the
            role updates.
            Note: Use `.model_dump(mode="json")` on contained models for JSON
                  serialization if needed.
        """
        endpoint = "/oppdateringer/roller"
        params = {k: v for k, v in kwargs.items() if v is not None}
        response = await self._request("GET", endpoint, params=params)
        # RolleOppdateringer is a RootModel expecting a list directly
        return RolleOppdateringer.model_validate(response.json())
