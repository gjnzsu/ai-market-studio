## ADDED Requirements

### Requirement: Workflow execution identity
Each `run_agent` invocation MUST generate a fresh UUID v4 independent of its request ID and forward `X-AI-Agent-ID: market-briefing-agent` and that `X-AI-Run-ID` on every completion call.

#### Scenario: Multiple rounds with injected client
- **WHEN** an injected client performs a tool round and a final response round
- **THEN** both calls carry identical agent and run headers and retain request and business attribution, with or without observability

#### Scenario: Repeated request correlation and concurrency
- **WHEN** sequential or overlapping invocations reuse the same client and request ID
- **THEN** each invocation carries a distinct run ID, the request ID is preserved, and client defaults remain unchanged
