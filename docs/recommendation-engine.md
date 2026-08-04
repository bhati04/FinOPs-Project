# Recommendation engine

Milestone 6 is implemented. CloudWise evaluates versioned,
deterministic rules against active inventory already persisted by CloudWise. It
does not call customer AWS APIs during evaluation and never changes customer
resources.

Rule set `1.1.0` contains:

- `ebs.unattached_volume` version `1.1.0`, which identifies an EBS volume whose
  persisted state is `available` and whose attachment list is present and empty.
- `ec2.unassociated_elastic_ip` version `1.1.0`, which identifies an Elastic IP
  whose persisted state is `unassociated` and has neither an instance nor a
  network-interface association. BYOIP and customer-owned addresses are
  excluded because AWS does not charge the standard public IPv4 rate for them.

Every persisted finding retains its eligibility evidence, exclusions, evidence
period, confidence, estimate type, rule version, risk notes, and verification
steps.

## Versioned list pricing

Milestone 6.1 attaches regional AWS on-demand list prices to eligible findings.
Production uses the AWS Price List Query API through the CloudWise platform
execution role. Recommendation evaluation still makes no calls to a customer
account and never changes customer resources.

EBS estimates include storage and, when applicable, provisioned IOPS and gp3
throughput. Elastic IP estimates use a transparent 730-hour month. The
calculation persists the catalog source, version fingerprint, effective and
retrieval timestamps, component quantities, tier rates, currency, and amounts.
The result is labeled `usage_based` because discounts, credits, taxes,
free-tier benefits, and partial-month usage are excluded.

Pricing has three explicit states:

- `available`: a current quote was retrieved and calculated;
- `stale`: a previous estimate was retained because refresh failed or its
  retrieval timestamp exceeded the configured threshold;
- `unavailable`: no complete, unambiguous price can be shown.

Incomplete gp3 performance inventory, unsupported products, ambiguous catalog
results, and provider failures produce a safe unavailable reason rather than an
understated estimate. Local development defaults to a visibly labelled mock
catalog. Production configuration rejects the mock provider.

References: [AWS Price List Query API](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/using-price-list-query-api.html)
and [Amazon VPC public IPv4 pricing](https://aws.amazon.com/vpc/pricing/).

Evaluation is idempotent by organization, resource, and rule. Findings that no
longer qualify become resolved. A resolved finding reopens if it qualifies in a
later evaluation, while acknowledged and dismissed findings keep their human
review state while they remain eligible.

Owners, administrators, and analysts can evaluate inventory and move findings
through `open`, `acknowledged`, `dismissed`, and `resolved` states. Status
changes and comments create append-only activity records. All reads and writes
are organization scoped.

## On-demand AI explanation boundary

The backend includes a disabled-by-default `ai_advisor` foundation for a future
**Generate AI suggestion** action. It is not registered as an API route and is
not called by a worker, scheduler, scan, or page load.

The AI provider remains disabled and unexposed. A later reviewed increment may
connect the authenticated recommendation screen to
`AiAdvisorService.generate_on_demand`, but only after a user clicks an explicit
action and organization authorization is rechecked.

The division of responsibility is fixed:

- Versioned CloudWise rules calculate costs, estimated savings, eligibility,
  evidence, and estimate type.
- The language model may explain business impact, review priority, risks, and
  verification steps.
- The model response has no financial fields. The service returns the verified
  calculation separately and rejects references to evidence it was not given.
- No Bedrock tools, AWS remediation functions, commands, or infrastructure code
  are available to the model.
- Generation is never automatic. Caching, budgets, throttling, and persisted
  generation history are still required before an endpoint can be exposed.

## AWS-native source imports and deduplication

Owners, administrators, and analysts can queue a read-only source sync for one
verified AWS connection and Region. Cost Optimization Hub is the primary
source and is called with includeAllRecommendations disabled, so AWS returns
one recommendation per resource. Regional EC2 and EBS Compute Optimizer calls
provide a fallback and can complete partially.

CloudWise normalizes supported findings, matches them only to active
tenant-scoped inventory, and deduplicates by organization, inventory resource,
and canonical action. A single finding can therefore show CloudWise, Cost
Optimization Hub, and Compute Optimizer provenance without double-counting the
opportunity. Source observations have refresh timestamps and disappear only
after a successful refresh proves that the source no longer reports them.

Cost Optimization Hub recommendation IDs are retained only as source metadata
because AWS refreshes them daily. The stable CloudWise identity is the
resource/action key. Unmatched AWS findings are counted in sync history but
are not persisted as recommendations without inventory evidence.

Future advanced rules and the optional AI explanation remain separately
reviewed enhancements; they are not required by the completed Milestone 6
contract and cannot execute customer changes.

References: [Cost Optimization Hub ListRecommendations](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_CostOptimizationHub_ListRecommendations.html)
and [Compute Optimizer GetEC2InstanceRecommendations](https://docs.aws.amazon.com/compute-optimizer/latest/APIReference/API_GetEC2InstanceRecommendations.html).
