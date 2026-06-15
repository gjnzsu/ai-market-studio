## ADDED Requirements

### Requirement: Tool traffic routing boundaries are explicit
The system SHALL distinguish gateway-routed MCP/tool traffic from locally executed connector traffic.

#### Scenario: Gateway-routed tool call is identified
- **WHEN** a tool or MCP call is routed through Kong or ai-gateway-service
- **THEN** the system records that the call used the gateway path
- **THEN** the system records the tool or connector name and completion status

#### Scenario: Local connector call is identified
- **WHEN** a workflow tool uses a local connector for market rates, news, FRED, or RAG
- **THEN** the system records that the call used a local connector path
- **THEN** the system does not represent the call as gateway-routed

### Requirement: Gateway migration does not silently reroute all connectors
The system SHALL NOT imply that all external connector traffic is routed through Kong unless each connector is explicitly implemented and configured for gateway routing.

#### Scenario: Connector remains local after migration
- **WHEN** a connector remains implemented as a local outbound call after the gateway migration
- **THEN** the connector remains documented as local
- **THEN** gateway failure handling does not mask connector-specific failures

### Requirement: MCP connector compatibility is preserved
The system SHALL preserve MCP connector behavior when MCP/tool traffic is configured to route through the gateway.

#### Scenario: MCP tool invocation through gateway
- **WHEN** a workflow invokes an MCP-backed tool through the configured gateway path
- **THEN** the tool result is returned in the workflow response data
- **THEN** gateway routing metadata is available for diagnosis

#### Scenario: MCP gateway failure
- **WHEN** a gateway-routed MCP tool call fails
- **THEN** the workflow records a clear tool failure
- **THEN** the workflow does not silently substitute an unrelated local tool result

