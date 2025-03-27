# 🔥 Brreg Wrapper

[![PyPI version](https://img.shields.io/pypi/v/brreg-wrapper.svg)](https://pypi.org/project/brreg-wrapper/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/pypi/pyversions/brreg-wrapper.svg)](https://pypi.org/project/brreg-wrapper/)

<!-- Optional: Add build status badge if you set up CI beyond publishing -->
<!-- [![Build Status](https://github.com/sondreal/brreg-wrapper/actions/workflows/your-ci-workflow.yml/badge.svg)](https://github.com/sondreal/brreg-wrapper/actions/workflows/your-ci-workflow.yml) -->

Tired of wrestling with raw API calls to the Brønnøysund Register Centre (Brreg)? **`brreg-wrapper`** is here to simplify your life! This sleek, asynchronous Python library provides an intuitive interface to access crucial Norwegian business information with ease.

Get details on main entities (`enheter`) and sub-entities (`underenheter`), perform searches, and integrate Norwegian business data into your applications effortlessly.

## ✨ Features

- **Asynchronous:** Built with `asyncio` and `httpx` for modern, non-blocking I/O.
- **Simple Interface:** Clean methods like `get_enhet`, `get_underenhet`, `search_enheter`, `search_underenheter`.
- **Type Hinted:** Fully type-hinted for better developer experience and static analysis.
- **Minimal Dependencies:** Relies only on the excellent `httpx` library.
- **PyPI Ready:** Easy to install and integrate.

## 🚀 Installation

Get started in seconds:

```bash
pip install brreg-wrapper
# Or using uv:
# uv pip install brreg-wrapper
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
        org_nr = "982038576" # Example: Google Norway AS

        print(f"🔍 Fetching details for organization number: {org_nr}")
        try:
            entity_info = await client.get_enhet(org_nr)
            print("\n--- Entity Details ---")
            # Pretty print the JSON response
            print(json.dumps(entity_info, indent=2, ensure_ascii=False))

            # Want to find sub-entities?
            # sub_entity_info = await client.get_underenhet("some_sub_org_nr")
            # print(json.dumps(sub_entity_info, indent=2, ensure_ascii=False))

        except Exception as e:
            print(f"\n💥 Oops! An error occurred: {e}")

        print("\n✅ Done!")

if __name__ == "__main__":
    asyncio.run(main())
```

## 🤝 Contributing

Contributions are welcome! If you have ideas for improvements or find a bug, please open an issue or submit a pull request on the [GitHub repository](https://github.com/sondreal/brreg-wrapper).

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. Remember to replace `[year]` and `[fullname]` in the file!

## ⚠️ Issues?

Having trouble? Found a bug? Feel free to open an issue on the [GitHub repository](https://github.com/sondreal/brreg-wrapper/issues).
