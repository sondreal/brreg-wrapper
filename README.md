# 🔥 Brreg Wrapper

[![PyPI version](https://img.shields.io/pypi/v/brreg-wrapper.svg)](https://pypi.org/project/brreg-wrapper/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/pypi/pyversions/brreg-wrapper.svg)](https://pypi.org/project/brreg-wrapper/)

<!-- Optional: Add build status badge if you set up CI beyond publishing -->
<!-- [![Build Status](https://github.com/sondreal/brreg-wrapper/actions/workflows/your-ci-workflow.yml/badge.svg)](https://github.com/sondreal/brreg-wrapper/actions/workflows/your-ci-workflow.yml) -->

Tired of wrestling with raw API calls to the Brønnøysund Register Centre (Brreg)? **`brreg-wrapper`** is here to simplify your life! This sleek, asynchronous Python library provides an intuitive interface to access crucial Norwegian business information with ease.

Get details on main entities (`enheter`) and sub-entities (`underenheter`), perform searches, and integrate Norwegian business data into your applications effortlessly.

## ✨ Core Features

- **Asynchronous:** Built with `asyncio` and `httpx` for modern, non-blocking I/O.
- **Type Hinted:** Fully type-hinted for better developer experience and static analysis.
- **Pydantic Models:** Uses Pydantic models for robust data validation and easy object access.
- **Context Management:** Supports `async with` for automatic HTTP client cleanup.
- **Comprehensive API Coverage:** Wraps numerous endpoints from the official Brreg API.
- **Advanced Features:**
  - **Error Handling:** Custom exception types for different API errors.
  - **Caching:** Built-in response caching for frequent requests.
  - **Retry Logic:** Automatic retries for transient failures.
  - **Rate Limiting:** Configurable rate limiting to stay within API constraints.
  - **Batch Operations:** Efficiently fetch multiple items in parallel.
- **Minimal Dependencies:** Relies primarily on `httpx`, `pydantic`, and `tenacity`.

## 🚀 Installation

Get started in seconds:

```bash
pip install brreg-wrapper
# Or using uv (recommended for speed):
uv pip install brreg-wrapper

# For HTTP/2 support:
pip install brreg-wrapper[http2]
# Or with uv:
uv pip install "brreg-wrapper[http2]"
```

## 💡 Basic Usage

```python
import asyncio
import json
from brreg_wrapper import BrregClient

async def main():
    # The client automatically handles HTTP sessions
    async with BrregClient() as client:
        org_nr = "923609016" # Example: Equinor ASA

        print(f"🔍 Fetching details for organization number: {org_nr}")
        try:
            # get_enhet returns a Pydantic model (Enhet or SlettetEnhet)
            entity_model = await client.get_enhet(org_nr)
            print("\n--- Entity Details (as Pydantic Model) ---")
            print(entity_model) # You can work with the model object directly

            # To serialize to JSON, convert the model to a JSON-compatible dictionary first
            # using mode='json'. This handles types like dates correctly.
            print("\n--- Entity Details (as JSON) ---")
            entity_dict = entity_model.model_dump(mode='json', by_alias=True, exclude_none=True)
            print(json.dumps(entity_dict, indent=2, ensure_ascii=False))

        except Exception as e:
            print(f"\n💥 Oops! An error occurred: {e}")

        print("\n✅ Done!")

if __name__ == "__main__":
    asyncio.run(main())
```

## 🚀 Advanced Features

### Caching & Rate Limiting

```python
from datetime import timedelta
from brreg_wrapper import BrregClient

async def main():
    # Enable caching with 1-hour TTL and rate limiting (1 request per second)
    client = BrregClient(
        cache_ttl=timedelta(hours=1),
        rate_limit=1.0  # seconds between requests
    )
    
    # First request fetches from API
    entity1 = await client.get_enhet("923609016")
    
    # Second request uses cache
    entity2 = await client.get_enhet("923609016")
    
    # Clear specific cache entries
    client.clear_cache(pattern="enhet_")
    
    # Get cache statistics
    cache_info = client.get_cache_info()
    print(f"Cache entries: {cache_info['count']}")
```

### Error Handling & Retry Logic

```python
from brreg_wrapper import BrregClient, BrregAPIError, BrregRateLimitError

async def main():
    # Configure with automatic retries for transient errors
    client = BrregClient(max_retries=3)
    
    try:
        entity = await client.get_enhet("invalid_org_nr")  # Will raise exception
    except BrregRateLimitError:
        # Handle rate limit specifically
        print("Rate limit exceeded, try again later")
    except BrregAPIError as e:
        # Handle all API-related errors
        print(f"API error: {e} (status code: {e.status_code})")
```

### Batch Operations

```python
from brreg_wrapper import BrregClient

async def main():
    client = BrregClient()
    
    # Fetch multiple entities in parallel
    org_numbers = ["923609016", "998463718", "913492978"]
    results = await client.get_multiple_enheter(org_numbers)
    
    for org_nr, entity in results.items():
        if isinstance(entity, Exception):
            print(f"Error fetching {org_nr}: {entity}")
        else:
            print(f"{org_nr}: {entity.navn}")
```

## 📂 Project Structure

- **`src/brreg_wrapper`**: Main package source code
  - `client.py`: The API client implementation
  - `exceptions.py`: Custom exception classes
  - `models/`: Pydantic models for API responses
- **`examples/`**: Example scripts showing how to use the package
  - `sample.py`: Comprehensive example demonstrating key features
- **`scripts/`**: Development utility scripts
  - `test_install.sh` & `test_install.bat`: Scripts to test installation
- **`tests/`**: Unit and integration tests

## 🧪 Testing

We use pytest for testing. To run the tests:

```bash
# Using pip
pip install -e ".[dev]"
pytest

# Using UV (recommended)
uv pip install -e ".[dev]"
pytest
```

To test the package installation locally before publishing:

```bash
# On Unix/Linux/macOS
chmod +x scripts/test_install.sh
./scripts/test_install.sh

# On Windows
scripts\test_install.bat
```

## 🤝 Contributing

Contributions are welcome! If you have ideas for improvements or find a bug, please open an issue or submit a pull request on the [GitHub repository](https://github.com/sondreal/brreg-wrapper).

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Issues?

Having trouble? Found a bug? Feel free to open an issue on the [GitHub repository](https://github.com/sondreal/brreg-wrapper/issues).
