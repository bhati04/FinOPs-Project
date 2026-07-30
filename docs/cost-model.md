# Cost model

Customer AWS cost collection and savings calculation are not implemented.

The future platform will initially store aggregated UnblendedCost results with
their currency and grouping dimensions. Pricing logic will live behind a cached
provider abstraction. Each recommendation will persist pricing inputs, Region,
currency, assumption version, and evidence period so estimates remain
explainable. Estimates are not guarantees.

The platform's own production cost model will cover ECS, ALB, RDS, Redis,
NAT/networking, logs, metrics, backups, and data transfer before Milestone 8.

