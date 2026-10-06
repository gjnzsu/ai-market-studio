# Agent run FinOps attribution

Market Studio's bounded, async, non-streaming workflow needs a stable agent identity and a fresh execution identity so the gateway can aggregate all completion calls for one run independently from HTTP request correlation.

Every invocation of `run_agent` generates a UUID v4 run ID. Every completion round sends `X-AI-Agent-ID: market-briefing-agent` and the same `X-AI-Run-ID` using per-call `extra_headers`, including injected clients and both observability paths. Existing request and business attribution are preserved. Shared client defaults are never mutated. Reused request IDs and overlapping runs remain distinct executions.

Scope excludes streaming, additional model calls, client lifecycle changes, and adding run IDs to Prometheus labels.

For the local gateway pilot, explicitly set `OPENAI_BASE_URL=http://localhost:8000/v1` and `OPENAI_MODEL=gpt-5.4` (or the model configured by that gateway). Existing application defaults remain unchanged. Header propagation tests use injected clients and establish the outgoing call contract; they do not establish actual network traversal or gateway billing aggregation.
