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
- **Pydantic Models:** Uses Pydantic models for robust data validation and easy object access (where applicable).
- **Context Management:** Supports `async with` for automatic HTTP client cleanup.
- **Comprehensive API Coverage:** Wraps numerous endpoints from the official Brreg API.
- **Minimal Dependencies:** Relies primarily on `httpx` and `pydantic`.

## 🚀 Installation

Get started in seconds:

```bash
pip install brreg-wrapper
# Or using uv:
uv add brreg-wrapper
```

## 💡 Usage Example

Here's a taste of how easy it is to fetch data:

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

            # Similarly for sub-entities (get_underenhet returns Underenhet or SlettetUnderenhet)
            # sub_entity_model = await client.get_underenhet("some_sub_org_nr")
            # sub_entity_dict = sub_entity_model.model_dump(mode='json', by_alias=True, exclude_none=True)
            # print(json.dumps(sub_entity_dict, indent=2, ensure_ascii=False))

        except Exception as e:
            print(f"\n💥 Oops! An error occurred: {e}")

    # Note: Methods like get_enhet and get_underenhet return Pydantic models.
    # Use the .model_dump(mode='json', ...) method on the returned object to get a
    # dictionary with JSON-compatible types (like dates converted to strings)
    # if you need to serialize the data.

        print("\n✅ Done!")

if __name__ == "__main__":
    asyncio.run(main())
```

## 🤝 Contributing

Contributions are welcome! If you have ideas for improvements or find a bug, please open an issue or submit a pull request on the [GitHub repository](https://github.com/sondreal/brreg-wrapper).

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Issues?

Having trouble? Found a bug? Feel free to open an issue on the [GitHub repository](https://github.com/sondreal/brreg-wrapper/issues).
