# Brreg Wrapper Examples

This directory contains example scripts that demonstrate how to use the `brreg-wrapper` package to interact with the Brønnøysund Register Centre API.

## Available Examples

- `sample.py`: A comprehensive example demonstrating basic usage, caching, batch operations, error handling, and search functionality.

## Running the Examples

Before running the examples, ensure you have installed the package:

```bash
# Using pip
pip install -e ..

# Using UV (recommended)
uv pip install -e ..
```

Then run an example with:

```bash
# Using Python
python sample.py

# Or with UV's Python (if installed)
uv python sample.py
```

## Creating Your Own Examples

Feel free to add your own examples to this directory. Here's a simple template to get started:

```python
#!/usr/bin/env python3
import asyncio
from brreg_wrapper import BrregClient

async def main():
    # Create a client
    async with BrregClient() as client:
        # Your code here
        # For example:
        org_nr = "923609016"  # Equinor ASA
        entity = await client.get_enhet(org_nr)
        print(f"Company name: {entity.navn}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Notes

- The examples assume you're running them from within the `examples` directory.
- Remember to always close the client using `await client.close()` or use it as an async context manager with `async with BrregClient() as client:`
- The Brreg API has rate limits, so be mindful when making many requests in quick succession. 