# Design

Construct existing request/business attribution once per `run_agent` invocation, extend it with a stable agent ID and fresh UUID v4, and pass a copy as `extra_headers` in both completion loops. This keeps execution identity local to the coroutine and preserves SDK defaults on injected/shared clients. Optional step IDs are omitted.

Tests exercise two tool/final rounds with observability enabled and disabled, sequential/repeated request IDs, three overlapping runs sharing a client, and the internally constructed client's gateway configuration. The repository gate accepts an explicit Python interpreter, fails on lint/test exit codes, and covers an offline orchestration fixture.
