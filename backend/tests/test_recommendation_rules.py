"""Deterministic recommendation rule tests."""

from datetime import UTC, datetime
from uuid import uuid4

from cloudwise.recommendations.rules import (
    InventoryEvidence,
    UnassociatedElasticIpRule,
    UnattachedEbsVolumeRule,
)


def evidence(
    resource_type: str,
    state: str,
    details: dict[str, object],
) -> InventoryEvidence:
    return InventoryEvidence(
        id=uuid4(),
        connection_id=uuid4(),
        resource_type=resource_type,
        name="example",
        state=state,
        region="us-east-1",
        details=details,
        last_seen_at=datetime(2026, 8, 3, tzinfo=UTC),
    )


def test_unattached_ebs_rule_retains_explainable_evidence() -> None:
    """An available volume with no attachments is eligible without pricing claims."""
    result = UnattachedEbsVolumeRule().evaluate(
        evidence(
            "ebs_volume",
            "available",
            {"attachments": [], "size_gib": 250},
        )
    )

    assert result.eligible is True
    assert result.severity.value == "medium"
    assert result.estimate_type.value == "advisory"
    assert result.evidence[1]["value"] == 0
    assert "pricing is not yet attached" in result.calculation_summary


def test_attached_ebs_volume_is_not_eligible() -> None:
    """Recorded attachment evidence excludes an EBS volume."""
    result = UnattachedEbsVolumeRule().evaluate(
        evidence(
            "ebs_volume",
            "in-use",
            {"attachments": ["i-example"], "size_gib": 20},
        )
    )

    assert result.eligible is False


def test_unassociated_elastic_ip_rule_requires_no_targets() -> None:
    """Both instance and interface associations must be absent."""
    rule = UnassociatedElasticIpRule()

    eligible = rule.evaluate(
        evidence(
            "elastic_ip",
            "unassociated",
            {
                "instance_id": None,
                "network_interface_id": None,
                "public_ipv4_pool": "amazon",
            },
        )
    )
    associated = rule.evaluate(
        evidence(
            "elastic_ip",
            "associated",
            {
                "instance_id": "i-example",
                "network_interface_id": "eni-example",
                "public_ipv4_pool": "amazon",
            },
        )
    )

    assert eligible.eligible is True
    assert associated.eligible is False


def test_customer_owned_elastic_ip_is_excluded() -> None:
    """BYOIP addresses do not create an AWS public IPv4 savings claim."""
    result = UnassociatedElasticIpRule().evaluate(
        evidence(
            "elastic_ip",
            "unassociated",
            {
                "instance_id": None,
                "network_interface_id": None,
                "customer_owned_ip": "198.51.100.10",
            },
        )
    )

    assert result.eligible is False
    assert result.exclusions
