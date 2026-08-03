# Resource metrics

CloudWise synchronizes 14 days of hourly CloudWatch datapoints by default. A
request may select 7 through 30 days. Collection is read-only, on demand, and
uses `GetMetricData` batches of no more than 500 queries with token pagination.

Supported inventory mappings are:

| Resource | Namespace | Metrics |
| --- | --- | --- |
| EC2 instance | `AWS/EC2` | CPUUtilization, NetworkIn, NetworkOut |
| EBS volume | `AWS/EBS` | VolumeReadOps, VolumeWriteOps, VolumeIdleTime |
| NAT gateway | `AWS/NATGateway` | ActiveConnectionCount, BytesInFromSource, BytesOutToDestination |
| RDS instance | `AWS/RDS` | CPUUtilization, DatabaseConnections, FreeStorageSpace |
| Lambda function | `AWS/Lambda` | Invocations, Errors, Duration |
| Application Load Balancer | `AWS/ApplicationELB` | RequestCount, TargetResponseTime, HTTPCode_Target_5XX_Count |

Network and gateway byte counters, invocation and operation counters, and HTTP
counts use `Sum`. Utilization, connection, duration, response-time, and free
storage metrics use `Average`. Missing datapoints remain missing rather than
being converted to zero.

The dashboard displays the latest, arithmetic average, maximum, and time series
for one selected resource metric. These observations are evidence inputs for
the future recommendation engine; they are not recommendations by themselves.

`GetMetricData` has AWS API charges. CloudWise therefore does not synchronize
metrics on page load or on an automatic schedule in this milestone.
