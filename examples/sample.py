#!/usr/bin/env python3
"""
Sample script to demonstrate the Brreg API wrapper.

This script shows how to use the BrregClient with various configurations to access
Norwegian business registry data from Brønnøysund Register Centre (Brreg).

Usage:
    python examples/sample.py

Requirements:
    pip install -e .  # Install the package in development mode
    # or
    uv pip install -e .  # Using UV installer
"""

import asyncio
import json
import logging
from datetime import timedelta

from brreg_wrapper import (
    BrregAPIError,
    BrregClient,
    BrregRateLimitError,
    BrregResourceNotFoundError,
)

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("brreg_sample")


async def main():
    """Main function to demonstrate BrregClient features."""
    # Example organization numbers
    org_numbers = [
        "923609016",  # Equinor ASA
        "914594685",  # KPMG AS
        "982463718",  # Microsoft Norge AS
        "999999999",  # Invalid/non-existent
    ]

    # Create a client with caching, rate limiting, and retry logic
    logger.info("Initializing BrregClient with caching and rate limiting")
    client = BrregClient(
        timeout=15.0,
        cache_ttl=timedelta(minutes=5),
        rate_limit=1.0,  # 1 request per second
        max_retries=2,
        logger=logger,
    )

    try:
        # 1. Basic usage - Get a single entity
        logger.info("\n1. Getting information for a single entity (Equinor ASA)")
        try:
            equinor = await client.get_enhet(org_numbers[0])
            print(f"Company Name: {equinor.navn}")
            print(f"Organization Number: {equinor.organisasjonsnummer}")
            print(f"Business Type: {equinor.organisasjonsform.beskrivelse}")
            print(f"Registration Date: {equinor.registreringsdatoEnhetsregisteret}")

            # Optional: serialize to JSON
            print("\nJSON representation:")
            equinor_dict = equinor.model_dump(
                mode="json", by_alias=True, exclude_none=True
            )
            print(
                json.dumps(equinor_dict, indent=2, ensure_ascii=False)[:500] + "...\n"
            )
        except BrregAPIError as e:
            print(f"Error fetching Equinor data: {e}")
            if e.response_json:
                print(f"API response: {e.response_json}")

        # 2. Caching demonstration
        logger.info("\n2. Demonstrating caching")
        logger.info("First request (will hit API):")
        start_time = asyncio.get_event_loop().time()
        await client.get_enhet(
            org_numbers[1]
        )  # Just make the request, don't need to store result
        first_request_time = asyncio.get_event_loop().time() - start_time
        print(f"First request took {first_request_time:.4f} seconds")

        logger.info("Second request (should use cache):")
        start_time = asyncio.get_event_loop().time()
        await client.get_enhet(
            org_numbers[1]
        )  # Just make the request, don't need to store result
        second_request_time = asyncio.get_event_loop().time() - start_time
        print(f"Second request took {second_request_time:.4f} seconds")
        print(f"Cache info: {client.get_cache_info()}")

        # 3. Batch operations
        logger.info("\n3. Getting multiple entities in parallel")
        results = await client.get_multiple_enheter(
            [org_numbers[0], org_numbers[1], org_numbers[2]]
        )
        for org_nr, entity in results.items():
            if isinstance(entity, Exception):
                print(f"❌ {org_nr}: Error - {entity}")
            else:
                print(f"✅ {org_nr}: {entity.navn}")

        # 4. Error handling
        logger.info("\n4. Error handling demonstration")
        try:
            await client.get_enhet(org_numbers[3])  # Invalid org number
        except BrregResourceNotFoundError as e:
            print(f"✅ Correct exception raised: {type(e).__name__}")
            print(f"  Message: {e}")
            print(f"  Status code: {e.status_code}")
            print(f"  Request URL: {e.request_url}")
        except BrregAPIError as e:
            print(f"❌ Wrong exception type: {type(e).__name__}")

        # 5. Searching
        logger.info("\n5. Searching for organizations")
        search_results = await client.search_enheter(navn="Microsoft")
        print(
            f"Found {search_results.page.totalElements}\
                  organizations matching 'Microsoft'"
        )
        for i, org in enumerate(search_results.field_embedded.enheter[:3], 1):
            print(f"  {i}. {org.navn} ({org.organisasjonsnummer})")

        # 6. Looking up code lists
        logger.info("\n6. Getting organization forms")
        org_forms = await client.get_organisasjonsformer()
        org_forms_sample = list(org_forms.field_embedded.organisasjonsformer)[:3]
        print(
            f"Found {len(org_forms.field_embedded.organisasjonsformer)}\
                organization forms"
        )
        for form in org_forms_sample:
            print(f"  • {form.kode}: {form.beskrivelse}")

    except BrregRateLimitError as e:
        print(f"Rate limit exceeded: {e}")
    except BrregAPIError as e:
        print(f"API error: {e} (Status code: {e.status_code})")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        # Always close the client to clean up resources
        await client.close()
        print("\nClient closed successfully")


if __name__ == "__main__":
    print("Brreg API Wrapper Demo")
    print("======================\n")
    asyncio.run(main())
