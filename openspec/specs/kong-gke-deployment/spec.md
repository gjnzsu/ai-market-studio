# kong-gke-deployment Specification

## Purpose
Define the GKE deployment requirements for running Kong Gateway as an internal, independently managed route to ai-gateway-service for AI Market Studio traffic.

## Requirements
### Requirement: Kong Gateway is deployed as an independent GKE workload
The system SHALL deploy Kong Gateway as an independent workload in GKE rather than as an ai-gateway-service sidecar.

#### Scenario: Kong workload exists in the AI gateway namespace
- **WHEN** the gateway stack is deployed to GKE
- **THEN** Kong Gateway runs as its own Deployment or equivalent workload
- **THEN** Kong Gateway has its own Kubernetes Service for in-cluster consumers
- **THEN** Kong Gateway can be rolled out independently from ai-gateway-service

#### Scenario: AI Market Studio uses Kong service DNS
- **WHEN** AI Market Studio is configured for gateway-routed AI traffic in GKE
- **THEN** `OPENAI_BASE_URL` points to the Kong Gateway Kubernetes Service DNS with the `/v1` path
- **THEN** AI Market Studio does not point directly to the ai-gateway-service Kubernetes Service for normal gateway-routed operation

### Requirement: Kong routes to ai-gateway-service through Kubernetes service DNS
The system SHALL configure Kong's GKE upstream to the existing ai-gateway-service Kubernetes Service rather than Docker Compose-only hostnames.

#### Scenario: Kong routes OpenAI-compatible traffic
- **WHEN** Kong receives a request for `/v1/chat/completions` or `/v1/models`
- **THEN** Kong forwards the request to the ai-gateway-service Kubernetes Service
- **THEN** Kong preserves the `/v1` path expected by ai-gateway-service

#### Scenario: Kong routes health checks
- **WHEN** Kong receives requests for `/health` or `/readiness`
- **THEN** Kong forwards those requests to ai-gateway-service
- **THEN** callers can validate both Kong routing and ai-gateway-service health through the Kong service

#### Scenario: GKE config avoids compose-only upstreams
- **WHEN** the GKE Kong declarative config is rendered or reviewed
- **THEN** it does not use the Docker Compose-only upstream hostname `ai-gateway-service:4000`
- **THEN** it uses Kubernetes service DNS for ai-gateway-service

### Requirement: Kong deployment remains internal by default
The system SHALL expose the Kong Gateway service as an internal in-cluster endpoint by default.

#### Scenario: Kong service is created for internal consumers
- **WHEN** Kong Gateway is deployed for AI Market Studio integration
- **THEN** the Kong proxy service is reachable by in-cluster consumers
- **THEN** the service is not exposed publicly unless a separate security-reviewed exposure change is made
