"""Versioned AWS list-price retrieval and deterministic savings calculations."""

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, Protocol

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from cloudwise.aws_accounts.provider import AWS_CLIENT_CONFIG
from cloudwise.core.config import Settings
from cloudwise.recommendations.rules import InventoryEvidence

MONTHLY_HOURS = Decimal("730")
PricingComponentName = Literal["storage", "iops", "throughput", "address"]


class PricingProviderError(RuntimeError):
    """Safe pricing failure that can be persisted without provider details."""

    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code


@dataclass(frozen=True)
class PriceTier:
    """One AWS on-demand price dimension."""

    begin: Decimal
    end: Decimal | None
    rate: Decimal
    rate_code: str


@dataclass(frozen=True)
class PriceComponent:
    """Tiered price for one billable resource component."""

    name: PricingComponentName
    unit: str
    tiers: tuple[PriceTier, ...]


@dataclass(frozen=True)
class PriceQuote:
    """Normalized, versioned catalog quote for one resource configuration."""

    source: str
    version: str
    currency: str
    effective_at: datetime
    retrieved_at: datetime
    components: tuple[PriceComponent, ...]


@dataclass(frozen=True)
class PriceCalculation:
    """Inspectable monthly list-price calculation."""

    monthly_cost: Decimal
    inputs: list[dict[str, object]]
    summary: str


class RecommendationPricingProvider(Protocol):
    """Pricing boundary used by recommendation evaluation."""

    async def quote(self, resource: InventoryEvidence) -> PriceQuote:
        """Return a verified quote for one eligible resource."""
        ...


class MockRecommendationPricingProvider:
    """Clearly labelled deterministic catalog for local development and tests."""

    _EBS_RATES: dict[str, dict[PricingComponentName, tuple[str, Decimal]]] = {
        "standard": {"storage": ("GB-Mo", Decimal("0.050"))},
        "gp2": {"storage": ("GB-Mo", Decimal("0.100"))},
        "gp3": {
            "storage": ("GB-Mo", Decimal("0.080")),
            "iops": ("IOPS-Mo", Decimal("0.005")),
            "throughput": ("MBps-Mo", Decimal("0.040")),
        },
        "io1": {
            "storage": ("GB-Mo", Decimal("0.125")),
            "iops": ("IOPS-Mo", Decimal("0.065")),
        },
        "io2": {
            "storage": ("GB-Mo", Decimal("0.125")),
            "iops": ("IOPS-Mo", Decimal("0.065")),
        },
        "st1": {"storage": ("GB-Mo", Decimal("0.045"))},
        "sc1": {"storage": ("GB-Mo", Decimal("0.015"))},
    }

    async def quote(self, resource: InventoryEvidence) -> PriceQuote:
        """Return a non-production quote with explicit mock provenance."""
        retrieved_at = datetime.now(UTC)
        if resource.resource_type == "elastic_ip":
            rates: dict[PricingComponentName, tuple[str, Decimal]] = {
                "address": ("Hrs", Decimal("0.005"))
            }
        elif resource.resource_type == "ebs_volume":
            volume_type = resource.details.get("volume_type")
            if not isinstance(volume_type, str) or volume_type not in self._EBS_RATES:
                raise PricingProviderError("unsupported_volume_type")
            rates = self._EBS_RATES[volume_type]
        else:
            raise PricingProviderError("unsupported_resource_type")
        components = tuple(
            PriceComponent(
                name=name,
                unit=unit,
                tiers=(
                    PriceTier(
                        begin=Decimal("0"),
                        end=None,
                        rate=rate,
                        rate_code=f"mock-{name}",
                    ),
                ),
            )
            for name, (unit, rate) in rates.items()
        )
        return PriceQuote(
            source="mock_catalog",
            version="development-v1",
            currency="USD",
            effective_at=datetime(2026, 1, 1, tzinfo=UTC),
            retrieved_at=retrieved_at,
            components=components,
        )


class AWSPriceListPricingProvider:
    """Query regional on-demand rates from the AWS Price List API."""

    def __init__(self, endpoint_region: str, session: Any | None = None) -> None:
        self._session: Any = session or boto3.Session(region_name=endpoint_region)
        self._endpoint_region = endpoint_region
        self._client: Any | None = None
        self._cache: dict[tuple[str, str, str], PriceQuote] = {}

    async def quote(self, resource: InventoryEvidence) -> PriceQuote:
        """Retrieve and normalize a resource quote without blocking the event loop."""
        discriminator = ""
        if resource.resource_type == "ebs_volume":
            volume_type = resource.details.get("volume_type")
            if not isinstance(volume_type, str) or not volume_type:
                raise PricingProviderError("incomplete_inventory")
            discriminator = volume_type
        elif resource.resource_type != "elastic_ip":
            raise PricingProviderError("unsupported_resource_type")
        key = (resource.resource_type, resource.region, discriminator)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        quote = await asyncio.to_thread(self._quote_sync, resource, discriminator)
        self._cache[key] = quote
        return quote

    def _quote_sync(self, resource: InventoryEvidence, discriminator: str) -> PriceQuote:
        service_code = "AmazonEC2"
        filters = [
            {"Type": "TERM_MATCH", "Field": "regionCode", "Value": resource.region},
        ]
        if resource.resource_type == "ebs_volume":
            filters.append(
                {
                    "Type": "TERM_MATCH",
                    "Field": "volumeApiName",
                    "Value": discriminator,
                }
            )
        else:
            service_code = "AmazonVPC"
        try:
            products = self._get_products(service_code, filters)
            return self._normalize_products(resource.resource_type, products)
        except PricingProviderError:
            raise
        except (
            BotoCoreError,
            ClientError,
            InvalidOperation,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PricingProviderError("pricing_provider_unavailable") from exc

    def _get_products(
        self,
        service_code: str,
        filters: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        if self._client is None:
            self._client = self._session.client(
                "pricing",
                region_name=self._endpoint_region,
                config=AWS_CLIENT_CONFIG,
            )
        request: dict[str, Any] = {
            "ServiceCode": service_code,
            "Filters": filters,
            "FormatVersion": "aws_v1",
            "MaxResults": 100,
        }
        products: list[dict[str, Any]] = []
        while True:
            response = self._client.get_products(**request)
            products.extend(json.loads(item) for item in response.get("PriceList", []))
            token = response.get("NextToken")
            if not token:
                return products
            request["NextToken"] = token

    @classmethod
    def _normalize_products(
        cls,
        resource_type: str,
        products: list[dict[str, Any]],
    ) -> PriceQuote:
        tiers: dict[tuple[PricingComponentName, str, Decimal, Decimal | None], PriceTier] = {}
        currencies: set[str] = set()
        effective_dates: list[datetime] = []
        for item in products:
            product = item.get("product", {})
            attributes = product.get("attributes", {})
            if resource_type == "elastic_ip" and not cls._is_idle_public_ipv4(attributes):
                continue
            for term in item.get("terms", {}).get("OnDemand", {}).values():
                effective_dates.append(cls._datetime(term["effectiveDate"]))
                for dimension in term.get("priceDimensions", {}).values():
                    unit = str(dimension["unit"])
                    component_name = cls._component_name(resource_type, unit)
                    if component_name is None:
                        continue
                    price_per_unit = dimension["pricePerUnit"]
                    currency, raw_rate = cls._currency_rate(price_per_unit)
                    currencies.add(currency)
                    begin = Decimal(str(dimension.get("beginRange", "0")))
                    raw_end = str(dimension.get("endRange", "Inf"))
                    end = None if raw_end.lower() in {"inf", "infinity"} else Decimal(raw_end)
                    tier = PriceTier(
                        begin=begin,
                        end=end,
                        rate=Decimal(raw_rate),
                        rate_code=str(dimension["rateCode"]),
                    )
                    key = (component_name, unit, begin, end)
                    previous = tiers.get(key)
                    if previous is not None and previous.rate != tier.rate:
                        raise PricingProviderError("ambiguous_catalog_price")
                    tiers[key] = tier
        if not tiers or not effective_dates:
            raise PricingProviderError("catalog_price_not_found")
        if len(currencies) != 1:
            raise PricingProviderError("ambiguous_catalog_currency")
        grouped: dict[tuple[PricingComponentName, str], list[PriceTier]] = {}
        for (name, unit, _, _), tier in tiers.items():
            grouped.setdefault((name, unit), []).append(tier)
        components = tuple(
            PriceComponent(
                name=name,
                unit=unit,
                tiers=tuple(sorted(component_tiers, key=lambda item: item.begin)),
            )
            for (name, unit), component_tiers in sorted(grouped.items(), key=lambda item: item[0])
        )
        version_material = "|".join(
            sorted(
                f"{tier.rate_code}:{tier.rate}"
                for component in components
                for tier in component.tiers
            )
        )
        version = hashlib.sha256(version_material.encode()).hexdigest()[:20]
        return PriceQuote(
            source="aws_price_list",
            version=version,
            currency=currencies.pop(),
            effective_at=max(effective_dates),
            retrieved_at=datetime.now(UTC),
            components=components,
        )

    @staticmethod
    def _is_idle_public_ipv4(attributes: dict[str, Any]) -> bool:
        group = str(attributes.get("group", ""))
        usage_type = str(attributes.get("usagetype", ""))
        return group == "PublicIPv4:IdleAddress" or usage_type.endswith("PublicIPv4:IdleAddress")

    @staticmethod
    def _component_name(
        resource_type: str,
        unit: str,
    ) -> PricingComponentName | None:
        normalized = unit.lower()
        if resource_type == "elastic_ip":
            return "address" if normalized in {"hrs", "hours", "hour"} else None
        if normalized in {"gb-mo", "gib-mo", "gb-month", "gib-month"}:
            return "storage"
        if normalized in {"iops-mo", "iops-month"}:
            return "iops"
        if normalized in {"mbps-mo", "mbps-month"}:
            return "throughput"
        return None

    @staticmethod
    def _currency_rate(price_per_unit: dict[str, Any]) -> tuple[str, str]:
        if "USD" in price_per_unit:
            return "USD", str(price_per_unit["USD"])
        if len(price_per_unit) != 1:
            raise PricingProviderError("ambiguous_catalog_currency")
        currency, rate = next(iter(price_per_unit.items()))
        return str(currency), str(rate)

    @staticmethod
    def _datetime(value: str) -> datetime:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def build_recommendation_pricing_provider(
    settings: Settings,
) -> RecommendationPricingProvider:
    """Build the configured pricing provider."""
    if settings.recommendation_pricing_provider == "aws":
        return AWSPriceListPricingProvider(settings.recommendation_pricing_endpoint_region)
    return MockRecommendationPricingProvider()


def calculate_monthly_price(
    resource: InventoryEvidence,
    quote: PriceQuote,
) -> PriceCalculation:
    """Calculate a full-month list-price estimate from verified quote components."""
    components = {component.name: component for component in quote.components}
    requested: list[tuple[PricingComponentName, Decimal]] = []
    if resource.resource_type == "elastic_ip":
        requested.append(("address", MONTHLY_HOURS))
        subject = "one idle public IPv4 address for 730 hours"
    elif resource.resource_type == "ebs_volume":
        size = _positive_decimal(resource.details.get("size_gib"), "incomplete_inventory")
        volume_type = resource.details.get("volume_type")
        if not isinstance(volume_type, str) or not volume_type:
            raise PricingProviderError("incomplete_inventory")
        requested.append(("storage", size))
        if volume_type == "gp3":
            iops = _nonnegative_decimal(resource.details.get("iops"), "incomplete_inventory")
            throughput = _nonnegative_decimal(
                resource.details.get("throughput_mibps"), "incomplete_inventory"
            )
            if iops > 3000:
                requested.append(("iops", iops - Decimal("3000")))
            if throughput > 125:
                requested.append(("throughput", throughput - Decimal("125")))
        elif volume_type in {"io1", "io2"}:
            iops = _positive_decimal(resource.details.get("iops"), "incomplete_inventory")
            requested.append(("iops", iops))
        subject = f"{size} GiB {volume_type} volume provisioned for a full month"
    else:
        raise PricingProviderError("unsupported_resource_type")

    total = Decimal("0")
    inputs: list[dict[str, object]] = []
    for component_name, quantity in requested:
        component = components.get(component_name)
        if component is None:
            raise PricingProviderError("catalog_component_not_found")
        amount, applied_tiers = _tiered_amount(quantity, component)
        total += amount
        inputs.append(
            {
                "component": component.name,
                "quantity": str(quantity),
                "unit": component.unit,
                "amount": str(amount.quantize(Decimal("0.00000001"))),
                "tiers": applied_tiers,
            }
        )
    monthly_cost = total.quantize(Decimal("0.00000001"))
    return PriceCalculation(
        monthly_cost=monthly_cost,
        inputs=inputs,
        summary=(
            f"Estimated from {quote.source} on-demand rates for {subject}; "
            "discounts, credits, taxes, and partial-month usage are excluded."
        ),
    )


def _tiered_amount(
    quantity: Decimal,
    component: PriceComponent,
) -> tuple[Decimal, list[dict[str, object]]]:
    amount = Decimal("0")
    applied: list[dict[str, object]] = []
    for tier in component.tiers:
        upper = quantity if tier.end is None else min(quantity, tier.end)
        billable = max(upper - tier.begin, Decimal("0"))
        if billable == 0:
            continue
        tier_amount = billable * tier.rate
        amount += tier_amount
        applied.append(
            {
                "begin": str(tier.begin),
                "end": str(tier.end) if tier.end is not None else None,
                "rate": str(tier.rate),
                "rate_code": tier.rate_code,
                "billable_quantity": str(billable),
            }
        )
    if not applied:
        raise PricingProviderError("catalog_tier_not_found")
    return amount, applied


def _positive_decimal(value: object, error_code: str) -> Decimal:
    result = _decimal(value, error_code)
    if result <= 0:
        raise PricingProviderError(error_code)
    return result


def _nonnegative_decimal(value: object, error_code: str) -> Decimal:
    result = _decimal(value, error_code)
    if result < 0:
        raise PricingProviderError(error_code)
    return result


def _decimal(value: object, error_code: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, int | float | str | Decimal):
        raise PricingProviderError(error_code)
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise PricingProviderError(error_code) from exc
