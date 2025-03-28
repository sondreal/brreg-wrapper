import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .exceptions import (
    BrregAPIError,
    BrregAuthenticationError,
    BrregClientError,
    BrregConnectionError,
    BrregForbiddenError,
    BrregRateLimitError,
    BrregResourceNotFoundError,
    BrregServerError,
    BrregServiceUnavailableError,
    BrregTimeoutError,
    BrregValidationError,
)
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
    API Documentation:
    https://data.brreg.no/enhetsregisteret/api/dokumentasjon/no/index.html
    """

    BASE_URL = "https://data.brreg.no/enhetsregisteret/api"

    def __init__(
        self,
        timeout: float = 10.0,
        client: httpx.AsyncClient | None = None,
        rate_limit: Optional[float] = None,
        cache_ttl: Optional[timedelta] = None,
        logger: Optional[logging.Logger] = None,
        max_retries: int = 3,
    ):
        """
        Initializes the BrregClient.

        Args:
            timeout: The timeout for HTTP requests in seconds. Defaults to 10.0.
            client: An optional httpx.AsyncClient instance. If not provided,
                    a new one is created.
            rate_limit: Optional rate limit in seconds between API calls.
            cache_ttl: Optional time-to-live for cached responses.
                       Defaults to 1 hour if caching is enabled.
            logger: Optional logger instance. If not provided, a default one is created.
            max_retries: Maximum number of retries for failed requests. Defaults to 3.
        """
        self._client = client or httpx.AsyncClient(
            base_url=self.BASE_URL, timeout=timeout
        )
        self._rate_limit = rate_limit
        self._last_request_time = 0
        self._cache_enabled = cache_ttl is not None
        self._cache_ttl = cache_ttl or timedelta(hours=1)
        self._cache = {}
        self._logger = logger or logging.getLogger(__name__)
        self._max_retries = max_retries

    async def _handle_rate_limit(self):
        """
        Handles rate limiting by sleeping if necessary.
        """
        if self._rate_limit:
            current_time = time.time()
            time_since_last = current_time - self._last_request_time
            if time_since_last < self._rate_limit:
                delay = self._rate_limit - time_since_last
                self._logger.debug(f"Rate limiting: sleeping for {delay:.2f} seconds")
                await asyncio.sleep(delay)
            self._last_request_time = time.time()

    def _map_http_error(self, exc: httpx.HTTPStatusError) -> BrregAPIError:
        """
        Maps HTTP exceptions to specific Brreg exceptions.

        Args:
            exc: The original httpx.HTTPStatusError.

        Returns:
            An appropriate BrregAPIError subclass.
        """
        status_code = exc.response.status_code
        message = f"HTTP error {status_code} while accessing {exc.request.url}"
        response_text = exc.response.text
        request_url = str(exc.request.url)
        request_params = getattr(exc.request, "params", None)

        if status_code == 404:
            return BrregResourceNotFoundError(
                message=f"Resource not found: {exc.request.url}",
                status_code=status_code,
                response_text=response_text,
                request_url=request_url,
                request_params=request_params,
            )
        elif status_code == 429:
            return BrregRateLimitError(
                message="Rate limit exceeded. Please slow down your requests.",
                status_code=status_code,
                response_text=response_text,
                request_url=request_url,
                request_params=request_params,
            )
        elif status_code == 400:
            return BrregValidationError(
                message=f"Invalid request parameters: {exc.request.url}",
                status_code=status_code,
                response_text=response_text,
                request_url=request_url,
                request_params=request_params,
            )
        elif status_code == 401:
            return BrregAuthenticationError(
                message="Authentication required or invalid credentials",
                status_code=status_code,
                response_text=response_text,
                request_url=request_url,
                request_params=request_params,
            )
        elif status_code == 403:
            return BrregForbiddenError(
                message=(
                    "Access forbidden. You don't have permission "
                    "to access this resource."
                ),
                status_code=status_code,
                response_text=response_text,
                request_url=request_url,
                request_params=request_params,
            )
        elif status_code == 503:
            return BrregServiceUnavailableError(
                message="Service temporarily unavailable. Please try again later.",
                status_code=status_code,
                response_text=response_text,
                request_url=request_url,
                request_params=request_params,
            )
        elif 400 <= status_code < 500:
            return BrregClientError(
                message=message,
                status_code=status_code,
                response_text=response_text,
                request_url=request_url,
                request_params=request_params,
            )
        elif 500 <= status_code < 600:
            return BrregServerError(
                message=message,
                status_code=status_code,
                response_text=response_text,
                request_url=request_url,
                request_params=request_params,
            )
        else:
            return BrregAPIError(
                message=message,
                status_code=status_code,
                response_text=response_text,
                request_url=request_url,
                request_params=request_params,
            )

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json: dict | None = None,
        cache_key: str | None = None,
        retry_enabled: bool = True,
    ) -> httpx.Response:
        """
        Makes an asynchronous HTTP request to the Brreg API with retry logic,
        rate limiting, and caching.

        Args:
            method: The HTTP method (e.g., "GET", "POST").
            endpoint: The API endpoint path (e.g., "/enheter").
            params: Optional query parameters.
            json: Optional JSON body for POST/PUT requests.
            cache_key: Optional cache key for caching responses.
                      If provided, and caching is enabled,
                      the response will be cached for the configured TTL.
            retry_enabled: Whether to enable retry logic for this request.
                          Defaults to True.

        Returns:
            The httpx.Response object.

        Raises:
            BrregAPIError: If the API returns an error or request fails.
        """
        # Check cache if enabled and it's a GET request
        if self._cache_enabled and method.upper() == "GET" and cache_key:
            cached_item = self._cache.get(cache_key)
            if cached_item:
                data, timestamp = cached_item
                if datetime.now() - timestamp < self._cache_ttl:
                    self._logger.debug(f"Cache hit for {cache_key}")
                    return data
                else:
                    self._logger.debug(f"Cache expired for {cache_key}")

        headers = {"Accept": "application/json"}
        self._logger.debug(f"Making {method} request to {endpoint}")

        # Define the actual request function
        async def make_request():
            await self._handle_rate_limit()
            try:
                response = await self._client.request(
                    method, endpoint, params=params, json=json, headers=headers
                )
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                error = self._map_http_error(exc)
                self._logger.error(
                    f"HTTP error {exc.response.status_code} for {exc.request.url}: "
                    f"{exc.response.text}",
                    exc_info=True,
                )
                raise error
            except httpx.TimeoutException as exc:
                self._logger.error(f"Request timed out: {exc}", exc_info=True)
                raise BrregTimeoutError(f"Request timed out: {exc}")
            except httpx.ConnectError as exc:
                self._logger.error(f"Connection error: {exc}", exc_info=True)
                raise BrregConnectionError(f"Connection error: {exc}")
            except httpx.RequestError as exc:
                self._logger.error(f"Request error: {exc}", exc_info=True)
                raise BrregAPIError(f"Request error: {exc}")

        # Execute with retry if enabled
        if retry_enabled and self._max_retries > 0:
            # Define retry decorator dynamically to use instance attributes
            retry_decorator = retry(
                stop=stop_after_attempt(self._max_retries),
                wait=wait_exponential(multiplier=1, min=4, max=10),
                retry=retry_if_exception_type(
                    (BrregServerError, BrregConnectionError, BrregTimeoutError)
                ),
                reraise=True,
            )

            # Apply retry decorator
            make_request_with_retry = retry_decorator(make_request)
            response = await make_request_with_retry()
        else:
            response = await make_request()

        # Cache the response if appropriate
        if self._cache_enabled and method.upper() == "GET" and cache_key:
            self._logger.debug(f"Caching response for {cache_key}")
            self._cache[cache_key] = (response, datetime.now())

        return response

    async def _download_request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        retry_enabled: bool = True,
    ) -> bytes:
        """
        Makes an asynchronous HTTP request intended for downloading files
        with retry logic and rate limiting.

        Args:
            method: The HTTP method (e.g., "GET", "POST").
            endpoint: The API endpoint path (e.g., "/enheter").
            params: Optional query parameters.
            retry_enabled: Whether to enable retry logic for this request.
                          Defaults to True.

        Returns:
            The response content as bytes.

        Raises:
            BrregAPIError: If the API returns an error or request fails.
        """
        headers = {"Accept": "*/*"}
        self._logger.debug(f"Making download request to {endpoint}")

        # Define the actual request function
        async def make_request():
            await self._handle_rate_limit()
            try:
                # Use stream=True if you anticipate large files and want to
                # handle streaming
                response = await self._client.request(
                    method, endpoint, params=params, headers=headers
                )
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                error = self._map_http_error(exc)
                self._logger.error(
                    f"HTTP error {exc.response.status_code} for {exc.request.url}: "
                    f"{exc.response.text}",
                    exc_info=True,
                )
                raise error
            except httpx.TimeoutException as exc:
                self._logger.error(f"Request timed out: {exc}", exc_info=True)
                raise BrregTimeoutError(f"Request timed out: {exc}")
            except httpx.ConnectError as exc:
                self._logger.error(f"Connection error: {exc}", exc_info=True)
                raise BrregConnectionError(f"Connection error: {exc}")
            except httpx.RequestError as exc:
                self._logger.error(f"Request error: {exc}", exc_info=True)
                raise BrregAPIError(f"Request error: {exc}")

        # Execute with retry if enabled
        if retry_enabled and self._max_retries > 0:
            # Define retry decorator dynamically to use instance attributes
            retry_decorator = retry(
                stop=stop_after_attempt(self._max_retries),
                wait=wait_exponential(multiplier=1, min=4, max=10),
                retry=retry_if_exception_type(
                    (BrregServerError, BrregConnectionError, BrregTimeoutError)
                ),
                reraise=True,
            )

            # Apply retry decorator
            make_request_with_retry = retry_decorator(make_request)
            response = await make_request_with_retry()
        else:
            response = await make_request()

        return response.content

    async def __aenter__(self):
        """Enter the async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context manager and close the client."""
        await self.close()

    async def close(self):
        """Closes the underlying httpx client."""
        await self._client.aclose()

    def clear_cache(self, pattern: str | None = None) -> int:
        """
        Clears the cache.

        Args:
            pattern: Optional pattern to selectively clear cache entries.
                    If provided, only cache entries with keys containing this pattern
                    will be cleared.

        Returns:
            The number of cache entries that were cleared.
        """
        if not self._cache_enabled:
            self._logger.warning("Cache is not enabled, nothing to clear")
            return 0

        if pattern is None:
            # Clear all cache
            before_count = len(self._cache)
            self._cache.clear()
            self._logger.info(f"Cleared entire cache ({before_count} entries)")
        else:
            # Clear only entries matching pattern
            keys_to_remove = [k for k in self._cache.keys() if pattern in k]
            for k in keys_to_remove:
                del self._cache[k]
            self._logger.info(
                f"Cleared {len(keys_to_remove)} cache entries matching "
                f"pattern '{pattern}'"
            )

        return len(keys_to_remove)

    def get_cache_info(self) -> Dict[str, Any]:
        """
        Returns information about the current cache state.

        Returns:
            A dictionary containing cache statistics.
        """
        if not self._cache_enabled:
            return {"enabled": False, "count": 0, "oldest": None, "newest": None}

        entries = len(self._cache)
        if entries == 0:
            return {"enabled": True, "count": 0, "oldest": None, "newest": None}

        # Get cache entry timestamps
        timestamps = [ts for _, (_, ts) in enumerate(self._cache.values())]
        oldest = min(timestamps)
        newest = max(timestamps)

        # Get cache key categories
        categories = {}
        for key in self._cache.keys():
            category = key.split("_")[0] if "_" in key else "other"
            categories[category] = categories.get(category, 0) + 1

        return {
            "enabled": True,
            "count": entries,
            "oldest": oldest,
            "newest": newest,
            "ttl_seconds": self._cache_ttl.total_seconds(),
            "categories": categories,
        }

    def set_cache_ttl(self, ttl: timedelta):
        """
        Sets a new time-to-live for the cache.

        Args:
            ttl: The new cache TTL as a timedelta.
        """
        self._cache_ttl = ttl
        self._logger.info(f"Cache TTL set to {ttl.total_seconds()} seconds")

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
        cache_key = f"enhet_{organisasjonsnummer}"

        response = await self._request("GET", endpoint, cache_key=cache_key)
        data = response.json()

        # Check if it's a deleted entity
        # (schema indicates 'slettedato'/'respons_klasse')
        if data.get("respons_klasse") == "SlettetEnhet" or "slettedato" in data:
            try:
                # Attempt parsing as SlettetEnhet first
                return SlettetEnhet.model_validate(data)
            except Exception as e:
                self._logger.error(f"Error parsing SlettetEnhet: {e}", exc_info=True)
                # Fallback if parsing SlettetEnhet fails unexpectedly
                pass
        # Default to parsing as Enhet
        return Enhet.model_validate(data)

    async def get_multiple_enheter(
        self, organisasjonsnumre: List[str]
    ) -> Dict[str, Union[Enhet, SlettetEnhet]]:
        """
        Retrieves information about multiple entities (enheter) in parallel.

        Args:
            organisasjonsnumre: A list of 9-digit organization numbers.

        Returns:
            A dictionary mapping organization numbers to their respective Enhet or
            SlettetEnhet objects.
        """
        self._logger.debug(f"Fetching data for {len(organisasjonsnumre)} entities")

        # Create tasks for each organization number
        tasks = {
            org_nr: asyncio.create_task(self.get_enhet(org_nr))
            for org_nr in organisasjonsnumre
        }

        # Wait for all tasks to complete
        results = {}
        for org_nr, task in tasks.items():
            try:
                results[org_nr] = await task
            except Exception as e:
                self._logger.error(
                    f"Error fetching entity {org_nr}: {e}", exc_info=True
                )
                # Store the error in the results
                results[org_nr] = e

        return results

    async def search_enheter(self, **kwargs) -> Enheter1:
        """
        Searches for entities (enheter) based on various criteria.
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-enheter-oppslag

        Args:
            **kwargs: Search parameters as defined in the API documentation.
                      Examples: navn, organisasjonsform, postadresse.postnummer, etc.

        Returns:
            An Enheter1 object containing the search results and metadata.
        """
        endpoint = "/enheter"
        cache_key = None
        if self._cache_enabled:
            sorted_items = sorted(
                [
                    (k, v)
                    for k, v in {
                        "query": kwargs.get("navn"),
                        "organization_form": kwargs.get("organisasjonsform"),
                        "municipality": kwargs.get("kommunenummer"),
                        "page": kwargs.get("page"),
                        "size": kwargs.get("size"),
                    }.items()
                    if v is not None
                ],
                key=lambda x: x[0],
            )
            param_str = "&".join(f"{k}={v}" for k, v in sorted_items)
            cache_key = f"search_enheter_{param_str}"

        response = await self._request(
            "GET", endpoint, params=kwargs, cache_key=cache_key
        )
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
        Ref:
        https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-underenheter-detalj

        Args:
            organisasjonsnummer: The 9-digit organization number.

        Returns:
            A Underenhet or SlettetUnderenhet object containing the entity's
            information.
        """
        endpoint = f"/underenheter/{organisasjonsnummer}"
        cache_key = f"underenhet_{organisasjonsnummer}"

        response = await self._request("GET", endpoint, cache_key=cache_key)
        data = response.json()

        # Check if it's a deleted entity
        if data.get("respons_klasse") == "SlettetUnderenhet" or "slettedato" in data:
            try:
                return SlettetUnderenhet.model_validate(data)
            except Exception as e:
                self._logger.error(
                    f"Error parsing SlettetUnderenhet: {e}", exc_info=True
                )
                # Fallback if parsing SlettetUnderenhet fails unexpectedly
                pass
        # Default to parsing as Underenhet
        return Underenhet.model_validate(data)

    async def get_multiple_underenheter(
        self, organisasjonsnumre: List[str]
    ) -> Dict[str, Union[Underenhet, SlettetUnderenhet]]:
        """
        Retrieves information about multiple sub-entities (underenheter) in parallel.

        Args:
            organisasjonsnumre: A list of 9-digit organization numbers.

        Returns:
            A dictionary mapping organization numbers to their respective Underenhet
            or SlettetUnderenhet objects.
        """
        self._logger.debug(f"Fetching data for {len(organisasjonsnumre)} sub-entities")

        # Create tasks for each organization number
        tasks = {
            org_nr: asyncio.create_task(self.get_underenhet(org_nr))
            for org_nr in organisasjonsnumre
        }

        # Wait for all tasks to complete
        results = {}
        for org_nr, task in tasks.items():
            try:
                results[org_nr] = await task
            except Exception as e:
                self._logger.error(
                    f"Error fetching sub-entity {org_nr}: {e}", exc_info=True
                )
                # Store the error in the results
                results[org_nr] = e

        return results

    async def search_underenheter(self, **kwargs) -> Underenheter1:
        """
        Searches for sub-entities (underenheter) based on various criteria.
        Ref:
        https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-underenheter-oppslag

        Args:
            **kwargs: Search parameters as defined in the API documentation.
                      Examples: navn, organisasjonsform, postadresse.postnummer, etc.

        Returns:
            A Underenheter1 object containing the search results and metadata.
        """
        endpoint = "/underenheter"
        # Create cache key from sorted parameters
        cache_key = None
        if self._cache_enabled:
            sorted_items = sorted(kwargs.items(), key=lambda x: x[0])
            param_str = "&".join(f"{k}={v}" for k, v in sorted_items)
            cache_key = f"search_underenheter_{param_str}"

        response = await self._request(
            "GET", endpoint, params=kwargs, cache_key=cache_key
        )
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
        Ref:
        https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-roller-rollegrupper
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
        Ref:
        https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-roller-roller

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
        Ref:
        https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-roller-roller-for-enhet

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
        Ref:
        https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-kodeverk-kommuner

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
        Ref:
        https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-kodeverk-organisasjonsformer

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
        Ref:
        https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-oppdateringer-enheter

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
        Ref:
        https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-oppdateringer-underenheter

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

    async def get_organization(self, org_number: str) -> Union[Enhet, SlettetEnhet]:
        """
        Fetches detailed information about a specific organization.

        Args:
            org_number: The organization number to look up.

        Returns:
            An Enhet or SlettetEnhet object containing the organization's information.

        Raises:
            BrregResourceNotFoundError: If the organization is not found.
            BrregAPIError: If the API returns an error.

        Ref:
        https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-enheter-detalj
        """
        endpoint = f"/enheter/{org_number}"
        cache_key = f"enhet_{org_number}"

        response = await self._request("GET", endpoint, cache_key=cache_key)
        data = response.json()

        # Check if it's a deleted entity
        # (schema indicates 'slettedato'/'respons_klasse')
        if data.get("respons_klasse") == "SlettetEnhet" or "slettedato" in data:
            try:
                # Attempt parsing as SlettetEnhet first
                return SlettetEnhet.model_validate(data)
            except Exception as e:
                self._logger.error(f"Error parsing SlettetEnhet: {e}", exc_info=True)
                # Fallback if parsing SlettetEnhet fails unexpectedly
                pass
        # Default to parsing as Enhet
        return Enhet.model_validate(data)

    async def get_organizations_batch(
        self, org_numbers: List[str]
    ) -> Dict[str, Union[Enhet, SlettetEnhet]]:
        """
        Fetches detailed information about multiple organizations in a batch.

        Args:
            org_numbers: A list of organization numbers to look up.

        Returns:
            A dictionary mapping organization numbers to their respective Enhet
            or SlettetEnhet objects.

        Raises:
            BrregAPIError: If the API returns an error.
        """
        self._logger.debug(f"Fetching data for {len(org_numbers)} entities")

        # Create tasks for each organization number
        tasks = {
            org_nr: asyncio.create_task(self.get_organization(org_nr))
            for org_nr in org_numbers
        }

        # Wait for all tasks to complete
        results = {}
        for org_nr, task in tasks.items():
            try:
                results[org_nr] = await task
            except Exception as e:
                self._logger.error(
                    f"Error fetching entity {org_nr}: {e}", exc_info=True
                )
                # Store the error in the results
                results[org_nr] = e

        return results

    async def search_organizations(
        self,
        query: str | None = None,
        organization_form: str | None = None,
        municipality: str | None = None,
        page: int = 0,
        size: int = 20,
    ) -> Enheter1:
        """
        Searches for organizations based on various criteria.

        Args:
            query: Free text search query.
            organization_form: Organization form code.
            municipality: Municipality code.
            page: Page number for pagination, starting from 0.
            size: Number of results per page, default 20.

        Returns:
            An Enheter1 object containing the search results.

        Raises:
            BrregAPIError: If the API returns an error.

        Ref:
        https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-enheter-oppslag
        """
        endpoint = "/enheter"
        cache_key = None
        if self._cache_enabled:
            sorted_items = sorted(
                [
                    (k, v)
                    for k, v in {
                        "query": query,
                        "organization_form": organization_form,
                        "municipality": municipality,
                        "page": page,
                        "size": size,
                    }.items()
                    if v is not None
                ],
                key=lambda x: x[0],
            )
            param_str = "&".join(f"{k}={v}" for k, v in sorted_items)
            cache_key = f"search_enheter_{param_str}"

        # Create params dictionary
        params = {
            "navn": query,
            "organisasjonsform.kode": organization_form,
            "kommunenummer": municipality,
            "page": page,
            "size": size,
        }
        params = {k: v for k, v in params.items() if v is not None}

        response = await self._request(
            "GET", endpoint, params=params, cache_key=cache_key
        )
        return Enheter1.model_validate(response.json())
