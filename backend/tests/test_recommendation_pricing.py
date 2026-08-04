"""Verified recommendation pricing provider and calculation tests."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from cloudwise.recommendations.pricing import (
    AWSPriceListPricingProvider,
    MockRecommendationPricingProvider,
    PriceComponent,
    PriceQuote,
    PriceTier,
    PricingProviderError,
    calculate_monthly_price,
)
from cloudwise.recommendations.rules import InventoryEvidence


def evidence(
    resource_type: str,
    details: dict[str, object],
    *,
    region: str = "us-east-1",
) -> InventoryEvidence:
    return InventoryEvidence(
        id=uuid4(),
        connection_id=uuid4(),
        resource_type=resource_type,
        name="priced-resource",
        state="available",
        region=region,
        details=details,
        last_seen_at=datetime(2026, 8, 4, tzinfo=UTC),
    )


async def test_mock_gp3_quote_prices_storage_and_extra_performance() -> None:
    """gp3 includes its baseline IOPS and throughput before paid quantities."""
    resource = evidence(
        "ebs_volume",
        {
            "volume_type": "gp3",
            "size_gib": 100,
            "iops": 4000,
            "throughput_mibps": 200,
        },
    )

    quote = await MockRecommendationPricingProvider().quote(resource)
    calculation = calculate_monthly_price(resource, quote)

    assert calculation.monthly_cost == Decimal("16.00000000")
    assert [item["component"] for item in calculation.inputs] == [
        "storage",
        "iops",
        "throughput",
    ]
    assert quote.source == "mock_catalog"


async def test_idle_elastic_ip_uses_730_hour_month() -> None:
    """The usage-based public IPv4 estimate retains its monthly-hour assumption."""
    resource = evidence("elastic_ip", {})

    quote = await MockRecommendationPricingProvider().quote(resource)
    calculation = calculate_monthly_price(resource, quote)

    assert calculation.monthly_cost == Decimal("3.65000000")
    assert calculation.inputs[0]["quantity"] == "730"


def test_tiered_iops_are_calculated_without_double_counting() -> None:
    """Every IOPS price tier applies only to its intersecting quantity."""
    quote = PriceQuote(
        source="aws_price_list",
        version="fixture-v1",
        currency="USD",
        effective_at=datetime(2026, 1, 1, tzinfo=UTC),
        retrieved_at=datetime(2026, 8, 4, tzinfo=UTC),
        components=(
            PriceComponent(
                name="storage",
                unit="GB-Mo",
                tiers=(PriceTier(Decimal("0"), None, Decimal("0.125"), "storage"),),
            ),
            PriceComponent(
                name="iops",
                unit="IOPS-Mo",
                tiers=(
                    PriceTier(Decimal("0"), Decimal("32000"), Decimal("0.065"), "iops-1"),
                    PriceTier(Decimal("32000"), None, Decimal("0.046"), "iops-2"),
                ),
            ),
        ),
    )
    resource = evidence(
        "ebs_volume",
        {"volume_type": "io2", "size_gib": 100, "iops": 40000},
    )

    calculation = calculate_monthly_price(resource, quote)

    assert calculation.monthly_cost == Decimal("2460.50000000")
    applied_tiers = calculation.inputs[1]["tiers"]
    assert isinstance(applied_tiers, list)
    assert len(applied_tiers) == 2


def test_gp3_requires_current_throughput_inventory() -> None:
    """Old inventory cannot produce a potentially understated gp3 estimate."""
    resource = evidence(
        "ebs_volume",
        {"volume_type": "gp3", "size_gib": 100, "iops": 3000},
    )
    quote = PriceQuote(
        source="aws_price_list",
        version="fixture-v1",
        currency="USD",
        effective_at=datetime(2026, 1, 1, tzinfo=UTC),
        retrieved_at=datetime(2026, 8, 4, tzinfo=UTC),
        components=(
            PriceComponent(
                name="storage",
                unit="GB-Mo",
                tiers=(PriceTier(Decimal("0"), None, Decimal("0.08"), "storage"),),
            ),
        ),
    )

    with pytest.raises(PricingProviderError, match="incomplete_inventory"):
        calculate_monthly_price(resource, quote)


def test_aws_catalog_parser_selects_idle_ipv4_dimension() -> None:
    """In-use public IPv4 products cannot price an idle-address recommendation."""

    def product(group: str, rate: str, rate_code: str) -> dict[str, object]:
        return {
            "product": {
                "attributes": {
                    "group": group,
                    "usagetype": f"USE1-{group}",
                }
            },
            "terms": {
                "OnDemand": {
                    "term": {
                        "effectiveDate": "2026-01-01T00:00:00Z",
                        "priceDimensions": {
                            "dimension": {
                                "unit": "Hrs",
                                "beginRange": "0",
                                "endRange": "Inf",
                                "rateCode": rate_code,
                                "pricePerUnit": {"USD": rate},
                            }
                        },
                    }
                }
            },
        }

    quote = AWSPriceListPricingProvider._normalize_products(
        "elastic_ip",
        [
            product("PublicIPv4:InUseAddress", "0.004", "in-use"),
            product("PublicIPv4:IdleAddress", "0.005", "idle"),
        ],
    )

    assert quote.components[0].name == "address"
    assert quote.components[0].tiers[0].rate == Decimal("0.005")


def test_elastic_ip_queries_the_vpc_catalog() -> None:
    """Public IPv4 prices come from AmazonVPC rather than the EC2 catalog."""
    client = MagicMock()
    client.get_products.return_value = {
        "PriceList": [
            json.dumps(
                {
                    "product": {
                        "attributes": {
                            "group": "PublicIPv4:IdleAddress",
                            "regionCode": "us-east-1",
                        }
                    },
                    "terms": {
                        "OnDemand": {
                            "term": {
                                "effectiveDate": "2026-01-01T00:00:00Z",
                                "priceDimensions": {
                                    "dimension": {
                                        "unit": "Hrs",
                                        "beginRange": "0",
                                        "endRange": "Inf",
                                        "rateCode": "idle-ipv4",
                                        "pricePerUnit": {"USD": "0.005"},
                                    }
                                },
                            }
                        }
                    },
                }
            )
        ]
    }
    session = MagicMock()
    session.client.return_value = client
    provider = AWSPriceListPricingProvider("us-east-1", session=session)

    quote = provider._quote_sync(evidence("elastic_ip", {}), "")

    assert quote.components[0].tiers[0].rate == Decimal("0.005")
    assert client.get_products.call_args.kwargs["ServiceCode"] == "AmazonVPC"
