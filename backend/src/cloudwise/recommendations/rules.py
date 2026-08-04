"""Versioned deterministic recommendation rules."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from cloudwise.recommendations.models import EstimateType, RecommendationSeverity

RULE_SET_VERSION = "1.1.0"


@dataclass(frozen=True)
class InventoryEvidence:
    """Bounded inventory facts exposed to deterministic rules."""

    id: UUID
    connection_id: UUID
    resource_type: str
    name: str
    state: str
    region: str
    details: dict[str, object]
    last_seen_at: datetime


@dataclass(frozen=True)
class RuleEvaluation:
    """Complete explainable output from one versioned rule."""

    eligible: bool
    title: str
    category: str
    severity: RecommendationSeverity
    confidence: Decimal
    evidence: list[dict[str, object]]
    exclusions: list[str]
    risk_notes: list[str]
    verification_steps: list[str]
    estimate_type: EstimateType
    calculation_summary: str


class RecommendationRule(Protocol):
    """Contract implemented by every deterministic rule."""

    rule_id: str
    version: str
    resource_type: str

    def evaluate(self, resource: InventoryEvidence) -> RuleEvaluation:
        """Evaluate one resource using only persisted evidence."""
        ...


class UnattachedEbsVolumeRule:
    """Identify active EBS volumes with no recorded attachment."""

    rule_id = "ebs.unattached_volume"
    version = "1.1.0"
    resource_type = "ebs_volume"

    def evaluate(self, resource: InventoryEvidence) -> RuleEvaluation:
        attachments = resource.details.get("attachments")
        if isinstance(attachments, list):
            evidence_complete = True
            attachment_count = len(attachments)
        else:
            evidence_complete = False
            attachment_count = None
        eligible = (
            evidence_complete and attachment_count == 0 and resource.state.lower() == "available"
        )
        size = resource.details.get("size_gib")
        severity = (
            RecommendationSeverity.MEDIUM
            if isinstance(size, int | float) and size >= 100
            else RecommendationSeverity.LOW
        )
        exclusions = [] if evidence_complete else ["Attachment evidence is unavailable"]
        return RuleEvaluation(
            eligible=eligible,
            title="Review unattached EBS volume",
            category="storage_optimization",
            severity=severity,
            confidence=Decimal("0.9900") if evidence_complete else Decimal("0.0000"),
            evidence=[
                {"reference": "volume.state", "metric": "State", "value": resource.state},
                {
                    "reference": "volume.attachments",
                    "metric": "Attachment count",
                    "value": attachment_count,
                    "unit": "count",
                },
                {
                    "reference": "volume.size",
                    "metric": "Provisioned size",
                    "value": size,
                    "unit": "GiB",
                },
            ],
            exclusions=exclusions,
            risk_notes=[
                "The volume may contain retained application or recovery data.",
                "Deletion is never automated and requires owner approval.",
            ],
            verification_steps=[
                "Confirm the volume is not intentionally retained for recovery.",
                "Check tags, snapshots, and recent attachment history.",
                "Create an approved backup before any deletion decision.",
            ],
            estimate_type=EstimateType.ADVISORY,
            calculation_summary=(
                "Eligibility is based on persisted attachment and state evidence; "
                "verified pricing is not yet attached."
            ),
        )


class UnassociatedElasticIpRule:
    """Identify active Elastic IP allocations with no association."""

    rule_id = "ec2.unassociated_elastic_ip"
    version = "1.1.0"
    resource_type = "elastic_ip"

    def evaluate(self, resource: InventoryEvidence) -> RuleEvaluation:
        instance_id = resource.details.get("instance_id")
        interface_id = resource.details.get("network_interface_id")
        public_ipv4_pool = resource.details.get("public_ipv4_pool")
        ownership_evidence = isinstance(public_ipv4_pool, str) and bool(public_ipv4_pool)
        customer_owned = bool(
            resource.details.get("customer_owned_ip")
            or resource.details.get("customer_owned_ipv4_pool")
        )
        if customer_owned:
            exclusions = ["Customer-owned IPv4 addresses are excluded from AWS public IPv4 savings"]
        elif not ownership_evidence:
            exclusions = ["Public IPv4 ownership evidence is unavailable"]
        elif public_ipv4_pool != "amazon":
            exclusions = ["Nonstandard public IPv4 pools require separate pricing validation"]
        else:
            exclusions = []
        eligible = (
            resource.state.lower() == "unassociated"
            and instance_id is None
            and interface_id is None
            and ownership_evidence
            and public_ipv4_pool == "amazon"
            and not customer_owned
        )
        return RuleEvaluation(
            eligible=eligible,
            title="Review unassociated Elastic IP",
            category="network_optimization",
            severity=RecommendationSeverity.MEDIUM,
            confidence=Decimal("0.9900"),
            evidence=[
                {"reference": "eip.state", "metric": "State", "value": resource.state},
                {
                    "reference": "eip.instance",
                    "metric": "Associated instance",
                    "value": instance_id,
                },
                {
                    "reference": "eip.interface",
                    "metric": "Associated network interface",
                    "value": interface_id,
                },
                {
                    "reference": "eip.public_ipv4_pool",
                    "metric": "Public IPv4 pool",
                    "value": public_ipv4_pool,
                },
                {
                    "reference": "eip.ownership_evidence",
                    "metric": "Ownership evidence available",
                    "value": ownership_evidence,
                },
                {
                    "reference": "eip.customer_owned",
                    "metric": "Customer-owned address",
                    "value": customer_owned,
                },
            ],
            exclusions=exclusions,
            risk_notes=[
                "The address may be allowlisted or reserved for a recovery procedure.",
                "Release is never automated and requires network-owner approval.",
            ],
            verification_steps=[
                "Confirm the address is absent from DNS and external allowlists.",
                "Check infrastructure code and incident-recovery documentation.",
                "Obtain approval before releasing the allocation.",
            ],
            estimate_type=EstimateType.ADVISORY,
            calculation_summary=(
                "Eligibility is based on persisted association evidence; verified "
                "public IPv4 pricing is not yet attached."
            ),
        )


RULES: tuple[RecommendationRule, ...] = (
    UnattachedEbsVolumeRule(),
    UnassociatedElasticIpRule(),
)
