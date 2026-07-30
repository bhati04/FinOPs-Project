# Recommendation engine

The recommendation engine is scheduled for Milestone 6 and is not implemented.

The boundary will be rule-based and versioned. Every recommendation must retain
its eligibility evidence, exclusions, evidence period, confidence calculation,
pricing assumptions, rule version, risk notes, and verification steps. Estimates
will be labeled exact, usage-based, or advisory and will never be presented as
guaranteed savings.

## On-demand AI explanation boundary

The backend includes a disabled-by-default `ai_advisor` foundation for a future
**Generate AI suggestion** action. It is not registered as an API route and is
not called by a worker, scheduler, scan, or page load.

When Milestone 6 provides persisted, tenant-scoped recommendations, the
authenticated recommendation screen may call
`AiAdvisorService.generate_on_demand` only after a user clicks that action.
The integration must enforce organization authorization before building the
context or returning a result.

The division of responsibility is fixed:

- Versioned CloudWise rules calculate costs, estimated savings, eligibility,
  evidence, and estimate type.
- The language model may explain business impact, review priority, risks, and
  verification steps.
- The model response has no financial fields. The service returns the verified
  calculation separately and rejects references to evidence it was not given.
- No Bedrock tools, AWS remediation functions, commands, or infrastructure code
  are available to the model.
- Generation is never automatic. Caching and persisted generation history are
  deferred until tenant-scoped recommendation persistence exists.

The current foundation does not make CloudWise recommendations functional; it
only establishes the safe provider contract needed by the later milestone.
