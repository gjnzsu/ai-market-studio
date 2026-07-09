## ADDED Requirements

### Requirement: Chat requests accept optional cost attribution context
The system SHALL allow `/api/chat` clients to provide optional cost attribution context without requiring existing clients to change their request shape.

#### Scenario: Existing chat request remains valid
- **WHEN** a client sends a valid `/api/chat` request without cost attribution context
- **THEN** the system accepts the request
- **THEN** the system uses backend defaults for application, project, team, use case, feature, and request correlation

#### Scenario: Client provides attribution context
- **WHEN** a client sends a valid `/api/chat` request with attribution context
- **THEN** the system preserves supported business attribution fields for the chat execution
- **THEN** unsupported or absent fields do not break chat execution

### Requirement: Chat execution has stable request correlation
The system SHALL attach a stable request correlation identifier to each chat execution and to downstream AI gateway traffic.

#### Scenario: Request ID is generated
- **WHEN** a chat request does not include a request identifier
- **THEN** the backend generates a request identifier for the chat execution
- **THEN** the generated identifier is available to downstream attribution and gateway traffic

#### Scenario: Request ID is propagated to AI gateway
- **WHEN** the backend sends OpenAI-compatible chat completion traffic for a chat execution
- **THEN** the request includes the same request identifier as `X-Request-ID`
- **THEN** the request includes `X-Consumer-Service` identifying AI Market Studio

### Requirement: MVP AI use cases are classified for cost attribution
The system SHALL classify AI Market Studio chat executions into MVP cost attribution use cases and features.

#### Scenario: FX data query is classified
- **WHEN** a workflow chat execution collects or analyzes FX market context without generating a full briefing
- **THEN** the attribution use case is `fx-data-query`
- **THEN** the attribution feature is `query-result-generation`

#### Scenario: Advisory report is classified
- **WHEN** a workflow chat execution generates a market briefing
- **THEN** the attribution use case is `fx-advisory-report`
- **THEN** the attribution feature is `advisory-report-generation`

#### Scenario: Conversational dashboard is classified
- **WHEN** a workflow chat execution returns dashboard data or the user intent asks to chart, plot, visualize, show a trend, or generate a dashboard
- **THEN** the attribution use case is `chat-dashboard-generation`
- **THEN** the attribution feature is `dashboard-generation`

### Requirement: Business attribution metrics are emitted without double-counting token cost
The system SHALL emit business attribution metrics through the existing observability path without treating them as an additional token-cost source.

#### Scenario: Successful chat emits business metric
- **WHEN** a chat execution completes successfully
- **THEN** the system emits a business attribution metric with low-cardinality labels for application, project, team, use case, feature, model, status, and tool used
- **THEN** the system does not emit a duplicate token-cost metric for the same chat execution from the business attribution path

#### Scenario: Observability is unavailable
- **WHEN** the observability SDK is not initialized or metric submission fails
- **THEN** chat execution continues without failing the user request
- **THEN** the system logs that business attribution metrics were skipped

### Requirement: Cost attribution avoids high-cardinality Prometheus labels
The system SHALL avoid placing raw user, session, conversation, prompt, or currency-pair values in Prometheus metric labels.

#### Scenario: User and session identifiers are present
- **WHEN** a chat request includes user, session, or conversation identifiers
- **THEN** those identifiers are available for request correlation
- **THEN** those identifiers are not emitted as Prometheus labels

### Requirement: Cost attribution dashboard is provisioned
The system SHALL provide a Grafana dashboard that visualizes AI Market Studio cost and business attribution metrics from Prometheus.

#### Scenario: Dashboard configuration is loaded
- **WHEN** Grafana loads dashboards from the Kubernetes dashboard ConfigMap
- **THEN** an AI Market Studio cost attribution dashboard is available
- **THEN** the dashboard contains panels for token cost, token volume, attributed requests, use cases, features, model usage, and status

#### Scenario: Dashboard queries avoid double-counting
- **WHEN** the dashboard displays cost and attribution data
- **THEN** cost panels use `llm_token_cost_usd_total`
- **THEN** attribution panels use `business_metric_total`
- **THEN** no panel sums `business_metric_total` as cost
- **THEN** app-specific cost panels use gateway-sourced LLM metrics filtered by `consumer`

### Requirement: Gateway LLM metrics preserve AI application ownership
The system SHALL label gateway-sourced LLM usage and cost metrics with low-cardinality AI application ownership fields.

#### Scenario: Gateway receives AI Market Studio traffic
- **WHEN** AI Market Studio sends chat completion traffic through ai-gateway-service
- **THEN** the gateway LLM metric includes `consumer="ai-market-studio"`
- **THEN** the gateway LLM metric includes application, project, team, use case, and feature labels when those headers are present

#### Scenario: Gateway receives unattributed traffic
- **WHEN** ai-gateway-service receives chat completion traffic without attribution headers
- **THEN** the gateway LLM metric uses `consumer="unknown"` and safe `unknown` defaults for optional ownership labels

### Requirement: Dashboards identify duplicate metric sources
The system SHALL provide dashboard panels that help operators identify whether backend and gateway are both emitting technical LLM usage for the same application traffic.

#### Scenario: Duplicate source review
- **WHEN** operators review AI Market Studio cost dashboards
- **THEN** the dashboard shows technical LLM token or cost metrics grouped by `service`
- **THEN** app-specific cost totals do not sum backend and gateway technical LLM metrics together
