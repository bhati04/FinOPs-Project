# Cost model

CloudWise synchronizes AWS Cost Explorer UnblendedCost actuals for each
verified customer connection. The worker requests daily data for the trailing
30 days and monthly data from the start of the same month in the prior year.
Actuals are stored separately by connection, period, granularity, currency, and
one of these views:

- AWS service and Region;
- usage type;
- one configured cost-allocation tag.

The optional tag view is enabled with `CLOUDWISE_COST_ALLOCATION_TAG_KEY`. The
tag must also be activated as a cost-allocation tag in the customer's AWS
billing configuration. Empty tag values are presented as `Untagged`.

AWS Cost Explorer forecasts are stored over 30-day and 90-day horizons at daily
and monthly granularity, respectively. CloudWise retains the mean and the 80%
prediction interval bounds returned by AWS. Forecasts and current billing data
can change as AWS finalizes usage; they are estimates, not guarantees.

CloudWise never converts currencies. The API and dashboard keep each source
currency separate. Synchronization upserts the same dimensional periods, so a
repeat run refreshes values without creating duplicate aggregates.

The dashboard presents a stacked service view for the seven calendar days
ending with the latest synchronized daily period. Region-level rows are summed
under their AWS service, the six largest services are displayed separately,
and remaining services are combined as `Other services`.

The estimated monthly cost is a transparent run-rate projection, not the AWS
forecast: month-to-date daily actuals are divided by the latest synchronized
day number and multiplied by the number of calendar days in that month. The
dashboard shows the actual-data cutoff used by the calculation. No estimate is
shown until current-month daily data exists.

Recommendation savings use a versioned pricing-provider abstraction. Production
queries regional AWS Price List on-demand rates; local development uses a
visibly labelled mock catalog. Each recommendation persists pricing source,
version, effective and retrieval timestamps, component quantities, tier rates,
currency, and evidence period.

Unattached EBS estimates include storage, provisioned IOPS for io1/io2, and gp3
IOPS and throughput above the included baselines. Unassociated Elastic IP
estimates use 730 hours per month. Current monthly cost and estimated monthly
savings are equal for these release/delete opportunities. They are
usage-based list-price estimates, not billed actuals, and exclude discounts,
credits, taxes, free-tier benefits, and partial-month usage. Missing or
ambiguous pricing remains unavailable; a failed refresh retains an earlier
estimate as stale.

The platform's own production cost model must cover ECS, ALB, RDS, Redis,
NAT/networking, logs, metrics, backups, and data transfer before production
traffic is enabled during Milestone 8.
