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

Savings calculation is not implemented. Future pricing logic will live behind
a cached provider abstraction. Each recommendation will persist pricing inputs,
Region, currency, assumption version, and evidence period so estimates remain
explainable.

The platform's own production cost model will cover ECS, ALB, RDS, Redis,
NAT/networking, logs, metrics, backups, and data transfer before Milestone 8.
