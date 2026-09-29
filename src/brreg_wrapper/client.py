import asyncio
import copy
import logging
import re
import time
from collections import OrderedDict
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, TypeVar
from urllib.parse import quote, urlencode

import httpx
from pydantic import BaseModel, ValidationError
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .exceptions import (
    BrregAPIError,
    BrregAuthenticationError,
    BrregClientError,
    BrregConnectionError,
    BrregDataError,
    BrregForbiddenError,
    BrregGoneError,
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

ModelT = TypeVar("ModelT", bound=BaseModel)

_ORGNR_PATTERN = re.compile(r"^\d{9}$")

# Status codes with a dedicated exception type. Anything else falls back to
# BrregClientError / BrregServerError / BrregAPIError based on its range.
_STATUS_ERRORS: dict[int, tuple[type[BrregAPIError], str]] = {
    400: (BrregValidationError, "Invalid request parameters: {url}"),
    401: (BrregAuthenticationError, "Authentication required or invalid credentials"),
    403: (
        BrregForbiddenError,
        "Access forbidden. You don't have permission to access this resource.",
    ),
    404: (BrregResourceNotFoundError, "Resource not found: {url}"),
    410: (BrregGoneError, "Resource has been removed: {url}"),
    429: (BrregRateLimitError, "Rate limit exceeded. Please slow down your requests."),
    503: (
        BrregServiceUnavailableError,
        "Service temporarily unavailable. Please try again later.",
    ),
}

# Transient failures that are worth another attempt. All endpoints are GETs,
# so retrying is always safe.
_RETRYABLE_ERRORS = (
    BrregServerError,
    BrregRateLimitError,
    BrregConnectionError,
    BrregTimeoutError,
)

# Upper bound for honouring a server-provided Retry-After header, so a
# misbehaving server can't stall the caller indefinitely.
_MAX_RETRY_AFTER_SECONDS = 60.0

# Download endpoints reject specific Accept values (400/401/406) and only
# answer to a wildcard.
_DOWNLOAD_ACCEPT = "*/*"

# Change feeds are polled for fresh data, so caching them would hide updates.
_UNCACHED_PREFIXES = ("/oppdateringer/",)

_DEFAULT_CACHE_MAXSIZE = 1024
_DEFAULT_MAX_CONCURRENCY = 10


def _normalize_orgnr(organisasjonsnummer: str) -> str:
    """Strip whitespace and validate a 9-digit organization number.

    Validating locally avoids a pointless round-trip and prevents values like
    ``"123/roller"`` from silently hitting a different endpoint.
    """
    normalized = re.sub(r"\s+", "", str(organisasjonsnummer))
    if not _ORGNR_PATTERN.fullmatch(normalized):
        raise BrregValidationError(
            f"Invalid organisasjonsnummer {organisasjonsnummer!r}: "
            "expected exactly 9 digits"
        )
    return normalized


def _path_segment(value: str) -> str:
    """Percent-encode a value for safe use as a single URL path segment."""
    return quote(str(value), safe="")


def _drop_none(params: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in params.items() if v is not None}


def _is_deleted(data: Any) -> bool:
    """Deleted (sub)entities are returned with a ``slettedato`` field."""
    return isinstance(data, dict) and "slettedato" in data


def _parse_retry_after(response: httpx.Response) -> float | None:
    """Return the Retry-After delay in seconds, if the header is present."""
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        seconds = (retry_at - datetime.now(retry_at.tzinfo)).total_seconds()
    return max(0.0, min(seconds, _MAX_RETRY_AFTER_SECONDS))


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
        rate_limit: float | None = None,
        cache_ttl: timedelta | None = None,
        logger: logging.Logger | None = None,
        max_retries: int = 3,
        cache_maxsize: int = _DEFAULT_CACHE_MAXSIZE,
    ):
        """
        Initializes the BrregClient.

        Args:
            timeout: The timeout for HTTP requests in seconds. Defaults to 10.0.
                     Ignored when ``client`` is provided.
            client: An optional httpx.AsyncClient instance. If provided, the caller
                    owns it and is responsible for closing it; ``close()`` will
                    leave it open.
            rate_limit: Optional minimum number of seconds between API calls.
                        Enforced across concurrent requests.
            cache_ttl: Optional time-to-live for cached GET responses. Caching is
                       disabled unless this is set. The /oppdateringer change
                       feeds are never cached.
            logger: Optional logger instance. If not provided, a default one is
                    created.
            max_retries: Maximum number of retries for transient failures
                         (5xx, 429, timeouts, connection errors). Defaults to 3,
                         i.e. up to 4 attempts in total. Set to 0 to disable.
            cache_maxsize: Maximum number of cached responses. The least recently
                           used entries are evicted first. Defaults to 1024.
        """
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if cache_maxsize < 1:
            raise ValueError("cache_maxsize must be >= 1")

        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self.BASE_URL, timeout=timeout
        )
        # A caller-supplied client may not have a base_url; fall back to
        # absolute URLs so every endpoint still resolves correctly.
        self._url_prefix = "" if str(self._client.base_url) else self.BASE_URL

        self._rate_limit = rate_limit
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_time: float | None = None

        self._cache_enabled = cache_ttl is not None
        self._cache_ttl = cache_ttl or timedelta(hours=1)
        self._cache_maxsize = cache_maxsize
        # key -> (json payload, monotonic timestamp, wall-clock timestamp)
        self._cache: OrderedDict[str, tuple[Any, float, datetime]] = OrderedDict()

        self._logger = logger or logging.getLogger(__name__)
        self._max_retries = max_retries

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Lifecycle
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~

    async def __aenter__(self):
        """Enter the async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context manager and close the client."""
        await self.close()

    async def close(self):
        """Closes the underlying httpx client if this instance created it."""
        if self._owns_client:
            await self._client.aclose()

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Transport
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~

    async def _handle_rate_limit(self) -> None:
        """Waits until the next request is allowed under ``rate_limit``.

        The lock serializes concurrent callers so that batch methods respect
        the configured spacing instead of all firing after the same delay.
        """
        if not self._rate_limit:
            return
        async with self._rate_limit_lock:
            if self._last_request_time is not None:
                elapsed = time.monotonic() - self._last_request_time
                delay = self._rate_limit - elapsed
                if delay > 0:
                    self._logger.debug(
                        "Rate limiting: sleeping for %.2f seconds", delay
                    )
                    await asyncio.sleep(delay)
            self._last_request_time = time.monotonic()

    def _map_http_error(self, exc: httpx.HTTPStatusError) -> BrregAPIError:
        """
        Maps HTTP exceptions to specific Brreg exceptions.

        Args:
            exc: The original httpx.HTTPStatusError.

        Returns:
            An appropriate BrregAPIError subclass.
        """
        status_code = exc.response.status_code
        url = exc.request.url

        if status_code in _STATUS_ERRORS:
            error_cls, template = _STATUS_ERRORS[status_code]
            message = template.format(url=url)
        else:
            if 400 <= status_code < 500:
                error_cls = BrregClientError
            elif 500 <= status_code < 600:
                error_cls = BrregServerError
            else:
                error_cls = BrregAPIError
            message = f"HTTP error {status_code} while accessing {url}"

        return error_cls(
            message=message,
            status_code=status_code,
            response_text=exc.response.text,
            request_url=str(url),
            request_params=dict(url.params),
            retry_after=_parse_retry_after(exc.response),
        )

    def _log_error(self, error: BrregAPIError) -> None:
        """Log a final (post-retry) error at a level matching its severity.

        404 is an expected miss (callers often try enhet, then underenhet),
        so it is logged at DEBUG without exception info. Other errors stay
        at ERROR with traceback.
        """
        if error.status_code is not None:
            message = (
                f"HTTP error {error.status_code} for {error.request_url}: "
                f"{error.response_text}"
            )
        else:
            message = str(error)

        if error.status_code == 404:
            self._logger.debug(message)
        else:
            self._logger.error(message, exc_info=error)

    async def _send(
        self,
        endpoint: str,
        params: Mapping[str, Any] | None,
        accept: str,
    ) -> httpx.Response:
        """Performs a single GET request, translating failures to Brreg errors."""
        await self._handle_rate_limit()
        url = f"{self._url_prefix}{endpoint}"
        try:
            response = await self._client.get(
                url, params=params, headers={"Accept": accept}
            )
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            raise self._map_http_error(exc) from exc
        except httpx.TimeoutException as exc:
            raise BrregTimeoutError(
                f"Request timed out: {exc}", request_url=url, request_params=params
            ) from exc
        except httpx.ConnectError as exc:
            raise BrregConnectionError(
                f"Connection error: {exc}", request_url=url, request_params=params
            ) from exc
        except httpx.RequestError as exc:
            raise BrregAPIError(
                f"Request error: {exc}", request_url=url, request_params=params
            ) from exc

    def _retry_wait(self, retry_state: RetryCallState) -> float:
        """Exponential backoff with jitter, deferring to Retry-After if sent."""
        backoff = wait_exponential_jitter(initial=1, max=10)(retry_state)
        outcome = retry_state.outcome
        error = outcome.exception() if outcome else None
        if isinstance(error, BrregAPIError) and error.retry_after is not None:
            return max(backoff, error.retry_after)
        return backoff

    def _log_retry(self, retry_state: RetryCallState) -> None:
        error = retry_state.outcome.exception() if retry_state.outcome else None
        delay = retry_state.next_action.sleep if retry_state.next_action else 0
        self._logger.warning(
            "Attempt %d failed (%s); retrying in %.1f seconds",
            retry_state.attempt_number,
            error,
            delay,
        )

    async def _request(
        self,
        endpoint: str,
        params: Mapping[str, Any] | None = None,
        accept: str = "application/json",
    ) -> httpx.Response:
        """
        Makes a GET request to the Brreg API with rate limiting and retries.

        Args:
            endpoint: The API endpoint path (e.g., "/enheter").
            params: Optional query parameters. ``None`` values are dropped.
            accept: The Accept header to send.

        Returns:
            The successful httpx.Response.

        Raises:
            BrregAPIError: If the API returns an error or the request fails.
        """
        params = _drop_none(params) if params else None
        self._logger.debug("Making GET request to %s", endpoint)
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._max_retries + 1),
                wait=self._retry_wait,
                retry=retry_if_exception_type(_RETRYABLE_ERRORS),
                before_sleep=self._log_retry,
                reraise=True,
            ):
                with attempt:
                    return await self._send(endpoint, params, accept)
        except BrregAPIError as error:
            self._log_error(error)
            raise
        raise AssertionError("unreachable")  # pragma: no cover

    async def _get_json(
        self, endpoint: str, params: Mapping[str, Any] | None = None
    ) -> Any:
        """GETs an endpoint and returns the decoded JSON body, using the cache."""
        params = _drop_none(params) if params else {}
        use_cache = not endpoint.startswith(_UNCACHED_PREFIXES)
        cache_key = self._cache_key(endpoint, params)

        cached = self._cache_get(cache_key) if use_cache else None
        if cached is not None:
            return cached

        response = await self._request(endpoint, params)
        try:
            data = response.json()
        except ValueError as exc:
            raise BrregDataError(
                f"Invalid JSON in response from {response.request.url}",
                status_code=response.status_code,
                response_text=response.text,
                request_url=str(response.request.url),
                request_params=params or None,
            ) from exc

        if use_cache:
            self._cache_set(cache_key, data)
        return data

    async def _get_model(
        self,
        model: type[ModelT],
        endpoint: str,
        params: Mapping[str, Any] | None = None,
    ) -> ModelT:
        data = await self._get_json(endpoint, params)
        return self._validate(model, data, endpoint)

    def _validate(self, model: type[ModelT], data: Any, endpoint: str) -> ModelT:
        """Validates API data into a model, raising BrregDataError on mismatch."""
        try:
            return model.model_validate(data)
        except ValidationError as exc:
            raise BrregDataError(
                f"Unexpected response from {endpoint}; could not parse as "
                f"{model.__name__}: {exc}",
                request_url=f"{self.BASE_URL}{endpoint}",
            ) from exc

    async def _download(
        self, endpoint: str, params: Mapping[str, Any] | None = None
    ) -> bytes:
        """Downloads a bulk file and returns its raw (usually gzipped) bytes."""
        self._logger.debug("Making download request to %s", endpoint)
        response = await self._request(endpoint, params, accept=_DOWNLOAD_ACCEPT)
        return response.content

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Cache
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~

    @staticmethod
    def _cache_key(endpoint: str, params: Mapping[str, Any]) -> str:
        if not params:
            return endpoint
        return f"{endpoint}?{urlencode(sorted(params.items()), doseq=True)}"

    def _cache_get(self, key: str) -> Any | None:
        if not self._cache_enabled:
            return None
        entry = self._cache.get(key)
        if entry is None:
            return None
        data, stored_at, _ = entry
        if time.monotonic() - stored_at >= self._cache_ttl.total_seconds():
            self._logger.debug("Cache expired for %s", key)
            del self._cache[key]
            return None
        self._logger.debug("Cache hit for %s", key)
        self._cache.move_to_end(key)
        return data

    def _cache_set(self, key: str, data: Any) -> None:
        if not self._cache_enabled:
            return
        self._logger.debug("Caching response for %s", key)
        self._cache[key] = (data, time.monotonic(), datetime.now())
        self._cache.move_to_end(key)
        while len(self._cache) > self._cache_maxsize:
            self._cache.popitem(last=False)

    def clear_cache(self, pattern: str | None = None) -> int:
        """
        Clears the cache.

        Cache keys are the request path plus sorted query string, for example
        ``/enheter/923609016`` or ``/enheter?navn=equinor&page=0``.

        Args:
            pattern: Optional substring to selectively clear cache entries.
                     If provided, only entries whose keys contain it are cleared.

        Returns:
            The number of cache entries that were cleared.
        """
        if not self._cache_enabled:
            self._logger.warning("Cache is not enabled, nothing to clear")
            return 0

        if pattern is None:
            removed = len(self._cache)
            self._cache.clear()
            self._logger.info("Cleared entire cache (%d entries)", removed)
            return removed

        keys_to_remove = [k for k in self._cache if pattern in k]
        if not keys_to_remove and self._cache:
            # Most likely a pattern written for the pre-0.3.0 key format
            # (e.g. "enhet_"), which would otherwise fail silently.
            self._logger.warning(
                "Pattern '%s' matched no cache entries; keys look like '%s'",
                pattern,
                next(iter(self._cache)),
            )
        for k in keys_to_remove:
            del self._cache[k]
        self._logger.info(
            "Cleared %d cache entries matching pattern '%s'",
            len(keys_to_remove),
            pattern,
        )
        return len(keys_to_remove)

    def get_cache_info(self) -> dict[str, Any]:
        """
        Returns information about the current cache state.

        Returns:
            A dictionary containing cache statistics. ``categories`` counts
            entries per top-level resource (e.g. ``enheter``, ``kommuner``).
        """
        if not self._cache_enabled:
            return {"enabled": False, "count": 0, "oldest": None, "newest": None}

        if not self._cache:
            return {"enabled": True, "count": 0, "oldest": None, "newest": None}

        timestamps = [stored_at for _, _, stored_at in self._cache.values()]
        categories: dict[str, int] = {}
        for key in self._cache:
            category = key.lstrip("/").split("/")[0].split("?")[0] or "other"
            categories[category] = categories.get(category, 0) + 1

        return {
            "enabled": True,
            "count": len(self._cache),
            "oldest": min(timestamps),
            "newest": max(timestamps),
            "ttl_seconds": self._cache_ttl.total_seconds(),
            "maxsize": self._cache_maxsize,
            "categories": categories,
        }

    def set_cache_ttl(self, ttl: timedelta):
        """
        Sets a new time-to-live for the cache.

        Args:
            ttl: The new cache TTL as a timedelta.
        """
        self._cache_ttl = ttl
        self._logger.info("Cache TTL set to %s seconds", ttl.total_seconds())

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Helpers
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~

    @staticmethod
    def _wrap_embedded(data: Any, key: str) -> Any:
        """Wraps a bare list response into the HAL ``_embedded`` shape."""
        if isinstance(data, list):
            return {"_embedded": {key: data}}
        return data

    async def _gather_by_key(
        self,
        keys: Iterable[str],
        fetch,
        max_concurrency: int,
    ) -> dict[str, Any]:
        """Runs ``fetch(key)`` concurrently, collecting results or API errors.

        Only BrregAPIError is captured per key; anything else (programming
        errors, cancellation) propagates to the caller.
        """
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")
        semaphore = asyncio.Semaphore(max_concurrency)

        async def run(key: str):
            async with semaphore:
                try:
                    return await fetch(key)
                except BrregAPIError as error:
                    return error

        unique_keys = list(dict.fromkeys(keys))
        results = await asyncio.gather(*(run(k) for k in unique_keys))
        return dict(zip(unique_keys, results, strict=True))

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Generelt Endpoints
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~

    async def get_services(self) -> dict[str, Any]:
        """
        Retrieves the list of available services/endpoints from the root API endpoint.
        Ref: Provided Swagger (GET /enhetsregisteret/api)

        Returns:
            A dictionary representing the available services, likely containing links.
        """
        # Copy so callers can't mutate the cached payload.
        return copy.deepcopy(await self._get_json("/"))

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Enhet Endpoints
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~

    async def get_enhet(self, organisasjonsnummer: str) -> Enhet | SlettetEnhet:
        """
        Retrieves information about a specific entity (enhet) by its
        organization number. Can also return a SlettetEnhet if the entity is deleted.
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-enheter-detalj

        Args:
            organisasjonsnummer: The 9-digit organization number. Whitespace is
                                 ignored, so "923 609 016" is accepted.

        Returns:
            An Enhet or SlettetEnhet object containing the entity's information.
            Note: Use `.model_dump(mode="json")` for JSON serialization to handle
                  types like dates correctly.

        Raises:
            BrregValidationError: If the organization number is malformed.
            BrregResourceNotFoundError: If the entity does not exist.
            BrregDataError: If the response can't be parsed.
        """
        orgnr = _normalize_orgnr(organisasjonsnummer)
        endpoint = f"/enheter/{orgnr}"
        data = await self._get_json(endpoint)
        model = SlettetEnhet if _is_deleted(data) else Enhet
        return self._validate(model, data, endpoint)

    async def get_multiple_enheter(
        self,
        organisasjonsnumre: Iterable[str],
        max_concurrency: int = _DEFAULT_MAX_CONCURRENCY,
    ) -> dict[str, Enhet | SlettetEnhet | BrregAPIError]:
        """
        Retrieves information about multiple entities (enheter) concurrently.

        Args:
            organisasjonsnumre: The 9-digit organization numbers. Duplicates are
                                fetched once.
            max_concurrency: Maximum number of requests in flight at once.

        Returns:
            A dictionary mapping each organization number to its Enhet or
            SlettetEnhet, or to the BrregAPIError raised while fetching it.
        """
        return await self._gather_by_key(
            organisasjonsnumre, self.get_enhet, max_concurrency
        )

    async def search_enheter(self, **params: Any) -> Enheter1:
        """
        Searches for entities (enheter) based on various criteria.
        Ref: https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-enheter-oppslag

        Args:
            **params: Search parameters as defined in the API documentation.
                      Examples: navn, organisasjonsform, kommunenummer, page, size.
                      Dotted names can be passed via dict unpacking, e.g.
                      ``**{"postadresse.postnummer": "0150"}``.

        Returns:
            An Enheter1 object containing the search results and metadata.
        """
        return await self._get_model(Enheter1, "/enheter", params)

    async def download_enheter_json(self, **params: Any) -> bytes:
        """
        Downloads all entities (enheter) as a gzipped JSON file.
        Ref: Provided Swagger (GET /enhetsregisteret/api/enheter/lastned)

        Args:
            **params: Optional filter parameters. Check API docs for specifics.

        Returns:
            The gzip-compressed file content. Decompress with ``gzip.decompress``.
        """
        return await self._download("/enheter/lastned", params)

    async def download_enheter_csv(self, **params: Any) -> bytes:
        """
        Downloads all entities (enheter) as a gzipped CSV file.
        Ref: Provided Swagger (GET /enhetsregisteret/api/enheter/lastned/csv)

        Args:
            **params: Optional filter parameters. Check API docs for specifics.

        Returns:
            The gzip-compressed file content. Decompress with ``gzip.decompress``.
        """
        return await self._download("/enheter/lastned/csv", params)

    async def download_enheter_spreadsheet(self, **params: Any) -> bytes:
        """
        Downloads all entities (enheter) as an Excel (.xlsx) spreadsheet.
        Ref: Provided Swagger (GET /enhetsregisteret/api/enheter/lastned/regneark)

        Args:
            **params: Optional filter parameters. Check API docs for specifics.

        Returns:
            The spreadsheet file content.
        """
        return await self._download("/enheter/lastned/regneark", params)

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
            organisasjonsnummer: The 9-digit organization number. Whitespace is
                                 ignored.

        Returns:
            A Underenhet or SlettetUnderenhet object containing the entity's
            information.

        Raises:
            BrregValidationError: If the organization number is malformed.
            BrregResourceNotFoundError: If the sub-entity does not exist.
            BrregDataError: If the response can't be parsed.
        """
        orgnr = _normalize_orgnr(organisasjonsnummer)
        endpoint = f"/underenheter/{orgnr}"
        data = await self._get_json(endpoint)
        model = SlettetUnderenhet if _is_deleted(data) else Underenhet
        return self._validate(model, data, endpoint)

    async def get_multiple_underenheter(
        self,
        organisasjonsnumre: Iterable[str],
        max_concurrency: int = _DEFAULT_MAX_CONCURRENCY,
    ) -> dict[str, Underenhet | SlettetUnderenhet | BrregAPIError]:
        """
        Retrieves information about multiple sub-entities (underenheter)
        concurrently.

        Args:
            organisasjonsnumre: The 9-digit organization numbers. Duplicates are
                                fetched once.
            max_concurrency: Maximum number of requests in flight at once.

        Returns:
            A dictionary mapping each organization number to its Underenhet or
            SlettetUnderenhet, or to the BrregAPIError raised while fetching it.
        """
        return await self._gather_by_key(
            organisasjonsnumre, self.get_underenhet, max_concurrency
        )

    async def search_underenheter(self, **params: Any) -> Underenheter1:
        """
        Searches for sub-entities (underenheter) based on various criteria.
        Ref:
        https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-underenheter-oppslag

        Args:
            **params: Search parameters as defined in the API documentation.
                      Examples: navn, organisasjonsform, overordnetEnhet, page, size.

        Returns:
            A Underenheter1 object containing the search results and metadata.
        """
        return await self._get_model(Underenheter1, "/underenheter", params)

    async def download_underenheter_json(self, **params: Any) -> bytes:
        """
        Downloads all sub-entities (underenheter) as a gzipped JSON file.
        Ref: Provided Swagger (GET /enhetsregisteret/api/underenheter/lastned)

        Args:
            **params: Optional filter parameters. Check API docs for specifics.

        Returns:
            The gzip-compressed file content. Decompress with ``gzip.decompress``.
        """
        return await self._download("/underenheter/lastned", params)

    async def download_underenheter_csv(self, **params: Any) -> bytes:
        """
        Downloads all sub-entities (underenheter) as a gzipped CSV file.
        Ref: Provided Swagger (GET /enhetsregisteret/api/underenheter/lastned/csv)

        Args:
            **params: Optional filter parameters. Check API docs for specifics.

        Returns:
            The gzip-compressed file content. Decompress with ``gzip.decompress``.
        """
        return await self._download("/underenheter/lastned/csv", params)

    async def download_underenheter_spreadsheet(self, **params: Any) -> bytes:
        """
        Downloads all sub-entities (underenheter) as an Excel (.xlsx) spreadsheet.
        Ref: Provided Swagger (GET /enhetsregisteret/api/underenheter/lastned/regneark)

        Args:
            **params: Optional filter parameters. Check API docs for specifics.

        Returns:
            The spreadsheet file content.
        """
        return await self._download("/underenheter/lastned/regneark", params)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Roller Endpoints
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~

    async def get_rollegrupper(self) -> RolleRollegruppetyper:
        """
        Retrieves all role group types.
        Ref: GET /enhetsregisteret/api/roller/rollegruppetyper

        Returns:
            A RolleRollegruppetyper object containing the list of role group types.
            Note: This method fetches all defined role group types, not roles for a
                  specific entity. Use `get_enhet_roller` for entity-specific roles.
        """
        endpoint = "/roller/rollegruppetyper"
        data = await self._get_json(endpoint)
        wrapped = self._wrap_embedded(data, "rollegruppetyper")
        return self._validate(RolleRollegruppetyper, wrapped, endpoint)

    async def get_roller(self) -> RolleRolletyper:
        """
        Retrieves all role types.
        Ref: GET /enhetsregisteret/api/roller/rolletyper

        Returns:
            A RolleRolletyper object containing the list of role types.
        """
        endpoint = "/roller/rolletyper"
        data = await self._get_json(endpoint)
        wrapped = self._wrap_embedded(data, "rolletyper")
        return self._validate(RolleRolletyper, wrapped, endpoint)

    async def get_enhet_roller(self, organisasjonsnummer: str) -> Roller:
        """
        Retrieves roles associated with a specific entity (enhet).
        Ref:
        https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-roller-roller-for-enhet

        Args:
            organisasjonsnummer: The 9-digit organization number of the entity.

        Returns:
            A Roller object containing the roles for the entity.
        """
        orgnr = _normalize_orgnr(organisasjonsnummer)
        return await self._get_model(Roller, f"/enheter/{orgnr}/roller")

    async def download_roller_totalbestand(self) -> bytes:
        """
        Downloads the total inventory of roles as a gzipped JSON file.
        Ref: Provided Swagger (GET /enhetsregisteret/api/roller/totalbestand)

        Returns:
            The gzip-compressed file content. Decompress with ``gzip.decompress``.
        """
        return await self._download("/roller/totalbestand")

    async def get_rolle_representanter(self) -> RolleRepresentanter:
        """
        Retrieves all role representatives.
        Ref: Provided Swagger (GET /enhetsregisteret/api/roller/representanter)

        Returns:
            A RolleRepresentanter object containing the list of role representatives.
        """
        return await self._get_model(RolleRepresentanter, "/roller/representanter")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Kommuner Endpoints
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~

    async def get_kommuner(self, **params: Any) -> Kommuner1:
        """
        Retrieves municipalities (kommuner).
        Ref:
        https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-kodeverk-kommuner

        This endpoint is paginated (20 per page by default). Pass ``page`` and
        ``size`` to fetch more, e.g. ``get_kommuner(size=1000)``.

        Args:
            **params: Optional query parameters such as page and size.

        Returns:
            A Kommuner1 object containing the municipalities and page metadata.
        """
        endpoint = "/kommuner"
        data = await self._get_json(endpoint, params)
        wrapped = self._wrap_embedded(data, "kommuner")
        return self._validate(Kommuner1, wrapped, endpoint)

    async def get_kommune(self, kommunenummer: str) -> Kommune:
        """
        Retrieves information about a specific municipality (kommune) by its number.
        Ref: Provided Swagger (GET /enhetsregisteret/api/kommuner/{kommunenr})

        Args:
            kommunenummer: The municipality number.

        Returns:
            A Kommune object containing the municipality's information.
        """
        return await self._get_model(
            Kommune, f"/kommuner/{_path_segment(kommunenummer)}"
        )

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
        """
        endpoint = "/organisasjonsformer"
        data = await self._get_json(endpoint)
        wrapped = self._wrap_embedded(data, "organisasjonsformer")
        return self._validate(Organisasjonsformer1, wrapped, endpoint)

    async def get_organisasjonsformer_enheter(self) -> OrganisasjonsformerEnheter:
        """
        Retrieves organization forms applicable to main entities (enheter).
        Ref: Provided Swagger (GET /enhetsregisteret/api/organisasjonsformer/enheter)

        Returns:
            An OrganisasjonsformerEnheter object containing the list of organization
            forms for entities.
        """
        return await self._get_model(
            OrganisasjonsformerEnheter, "/organisasjonsformer/enheter"
        )

    async def get_organisasjonsformer_underenheter(
        self,
    ) -> OrganisasjonsformerUnderenheter:
        """
        Retrieves organization forms applicable to sub-entities (underenheter).
        Ref: GET /enhetsregisteret/api/organisasjonsformer/underenheter (Swagger)

        Returns:
            An OrganisasjonsformerUnderenheter object containing the list of
            organization forms for sub-entities.
        """
        return await self._get_model(
            OrganisasjonsformerUnderenheter, "/organisasjonsformer/underenheter"
        )

    async def get_organisasjonsform(self, organisasjonskode: str) -> Organisasjonsform:
        """
        Retrieves the description of a specific organization form by its code.
        Ref: GET /enhetsregisteret/api/organisasjonsformer/{organisasjonskode} (Swagger)

        Args:
            organisasjonskode: The code of the organization form.

        Returns:
            An Organisasjonsform object containing the organization form's description.
        """
        return await self._get_model(
            Organisasjonsform,
            f"/organisasjonsformer/{_path_segment(organisasjonskode)}",
        )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Matrikkelenhet Endpoints
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~

    async def get_matrikkelenheter(self, **params: Any) -> Matrikkelenheter:
        """
        Retrieves cadastral units (matrikkelenheter).
        Ref: Provided Swagger (GET /enhetsregisteret/api/matrikkelenhet)

        Args:
            **params: Optional query parameters (check API docs for specifics).

        Returns:
            A Matrikkelenheter object (RootModel wrapping a list) containing the
            cadastral units.
        """
        return await self._get_model(Matrikkelenheter, "/matrikkelenhet", params)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Oppdateringer Endpoints
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~

    async def get_enhet_oppdateringer(self, **params: Any) -> OppdateringerEnheter1:
        """
        Retrieves updates for entities (enheter).
        Ref:
        https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-oppdateringer-enheter

        Args:
            **params: Optional query parameters like oppdateringsid, dato,
                      page, size.

        Returns:
            An OppdateringerEnheter1 object containing the entity updates.
        """
        return await self._get_model(
            OppdateringerEnheter1, "/oppdateringer/enheter", params
        )

    async def get_underenhet_oppdateringer(
        self, **params: Any
    ) -> OppdateringerUnderenheter1:
        """
        Retrieves updates for sub-entities (underenheter).
        Ref:
        https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-oppdateringer-underenheter

        Args:
            **params: Optional query parameters like oppdateringsid, dato,
                      page, size.

        Returns:
            An OppdateringerUnderenheter1 object containing the sub-entity updates.
        """
        return await self._get_model(
            OppdateringerUnderenheter1, "/oppdateringer/underenheter", params
        )

    async def get_rolle_oppdateringer(self, **params: Any) -> RolleOppdateringer:
        """
        Retrieves updates for roles.
        Ref: Provided Swagger (GET /enhetsregisteret/api/oppdateringer/roller)

        Args:
            **params: Optional query parameters like afterId, afterTime, size.

        Returns:
            A RolleOppdateringer object (RootModel wrapping a list) containing the
            role updates.
        """
        return await self._get_model(
            RolleOppdateringer, "/oppdateringer/roller", params
        )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~
    # English-named convenience aliases
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~

    async def get_organization(self, org_number: str) -> Enhet | SlettetEnhet:
        """Alias for :meth:`get_enhet`."""
        return await self.get_enhet(org_number)

    async def get_organizations_batch(
        self,
        org_numbers: Iterable[str],
        max_concurrency: int = _DEFAULT_MAX_CONCURRENCY,
    ) -> dict[str, Enhet | SlettetEnhet | BrregAPIError]:
        """Alias for :meth:`get_multiple_enheter`."""
        return await self.get_multiple_enheter(org_numbers, max_concurrency)

    async def search_organizations(
        self,
        query: str | None = None,
        organization_form: str | None = None,
        municipality: str | None = None,
        page: int = 0,
        size: int = 20,
    ) -> Enheter1:
        """
        Searches for organizations based on common criteria.

        Args:
            query: Name search (``navn``).
            organization_form: Organization form code(s), e.g. "AS" or "AS,ASA".
            municipality: Municipality number, e.g. "0301".
            page: Page number for pagination, starting from 0.
            size: Number of results per page, default 20.

        Returns:
            An Enheter1 object containing the search results.

        Ref:
        https://data.brreg.no/enhetsregisteret/api/docs/index.html#rest-api-enheter-oppslag
        """
        return await self.search_enheter(
            navn=query,
            organisasjonsform=organization_form,
            kommunenummer=municipality,
            page=page,
            size=size,
        )
