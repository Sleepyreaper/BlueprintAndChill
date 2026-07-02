# BlueprintAndChill Implementation Notes

Document Type: Implementation Notes / Security and TODO Ledger
Audience: Builders continuing the BlueprintAndChill framework, platform engineers, security reviewers
Version: 0.1.0
Last updated: 2026-07-02
Applies to: Framework scaffold PR for Sleepyreaper/BlueprintAndChill

## Purpose

This document records the honest boundaries of the current BlueprintAndChill scaffold. It exists to prevent future builders from mistaking framework shape for completed Azure automation.

Current status:

- The repository contains a production-grade framework and composition surface for Azure Landing Zone (ALZ) and subscription-vending workflows.
- The repository does not yet perform end-to-end live tenant automation.
- Several modules intentionally stop at safe, testable seams and mark required follow-up implementation work with explicit TODOs.

Do not represent this repository as a finished Landing Zone deployment engine, finished Microsoft Customer Agreement (MCA) subscription-vending platform, or completed spoke-onboarding system in its current state.

## Framework boundary statement

The current scaffold provides:

- A documented Azure Landing Zone-oriented infrastructure shape in Bicep and Terraform.
- Python modules that model the core subscription-vending sequence:
  - create or reference a service principal
  - assign the billing-scope subscription-creator role
  - create a subscription alias and poll provisioning
  - compose those steps in an orchestrator
- An event-handler skeleton showing where invoice-section-triggered automation would attach.
- A demo web application flow that simulates catalog ordering and provisioning results.

The current scaffold does not yet provide:

- Verified live Microsoft Graph app registration and service principal creation in a customer tenant.
- Verified live MCA invoice-section event ingestion from an Azure-native event source.
- Verified live billing-scope role assignment execution in Landmark's production billing hierarchy.
- Verified live subscription alias creation against Landmark's tenant and billing account.
- Verified post-create spoke onboarding into management groups, policy, networking, DNS, or shared services.
- Verified secure secret retrieval from Azure Key Vault in runtime paths.
- Verified production observability, retry, audit, approval, and break-glass controls.

## What "implemented" means in this PR

For this PR, "implemented" means the following:

- Contract surfaces, module boundaries, and orchestration order are present.
- Request and response shapes are documented in code.
- Modules are structured for dependency injection and unit testing.
- Live Azure calls are either absent, stubbed, or isolated behind clear extension points.
- Infrastructure-as-code expresses scaffold intent without pretending unsupported or tenant-specific values are already wired.

For this PR, "implemented" does not mean:

- Production credentials are configured.
- A customer tenant has been integrated.
- Billing, Graph, Azure Resource Manager (ARM), and eventing permissions have been approved.
- Every required API nuance has been validated against Landmark's exact tenant and enrollment structure.
- Security hardening is complete.

## Least-privilege assumptions

The framework assumes future implementation will preserve the narrowest workable privileges at every layer.

### Billing permissions

- The service principal used to create subscriptions should receive only the billing-scope role required for subscription creation at the target MCA invoice section.
- Billing-scope role assignment is distinct from Azure Role-Based Access Control (Azure RBAC). Do not substitute Owner or Contributor at subscription or management group scope for billing permissions.
- Billing permissions must be scoped as narrowly as possible:
  - prefer invoice section scope over billing profile scope
  - prefer billing profile scope over billing account scope
- No module in this scaffold should be expanded to grant broad billing rights by convenience.

### Azure RBAC

- Separate identities should be considered for:
  - billing actions
  - Azure deployment actions
  - web application runtime
  - event-processing runtime
- The post-vending onboarding identity should receive only the minimum Azure RBAC needed to:
  - move a subscription into the correct management group
  - apply approved policy assignments
  - create approved baseline resources
  - attach approved networking constructs
- Do not grant subscription Owner broadly to application identities unless an explicit, reviewed requirement exists.

### Microsoft Graph

- Microsoft Graph permissions for application registration and service principal creation must be explicitly reviewed before implementation.
- Future builders must identify the exact Microsoft Graph application permissions or delegated permissions needed for:
  - application registration
  - service principal creation
  - optional credential creation
  - optional ownership assignment
- Do not request broad Graph permissions such as directory-wide write access unless the exact API flow requires them and the security review approves them.
- If Graph permissions exceed what the runtime should hold continuously, move privileged setup into a separate administrative bootstrap path.

### Demo web app

- The demo web app must not hold billing or tenant-wide administrative privileges directly.
- The web layer should submit vetted requests into a controlled backend workflow rather than calling privileged APIs from request handlers.
- Authentication with Microsoft Entra ID is expected for the demo app, but authorization rules for who may request which catalog items still need explicit implementation.

## Secret handling rules

These rules are mandatory for follow-up PRs.

- Never commit client secrets, certificate private keys, tenant-specific billing identifiers that are considered sensitive, or production app registration details into the repository.
- Never store secrets in source files, Terraform variables files committed to git, Bicep parameter files committed to git, or sample environment files with real values.
- Prefer managed identity over client secret wherever the Azure hosting model supports it.
- If a confidential client is unavoidable, store the secret or certificate reference in Azure Key Vault and load it at runtime.
- Environment variables may carry only Key Vault reference names, secret URIs, or non-secret configuration where possible.
- Local development secrets must be stored outside the repository using developer-local secret stores or uncommitted environment files.
- Rotation requirements, expiry dates, and ownership for every secret or certificate must be documented before production release.

## Key Vault expectations

Azure Key Vault integration is not complete in this scaffold. Before production use, future PRs must implement and document:

- the Key Vault instance or per-environment vault strategy
- naming conventions for secrets, certificates, and keys
- managed identity access model for the web app, event processor, and background workers
- separation of duties between secret readers, secret writers, and Key Vault administrators
- network access model:
  - public access with restrictions, or
  - private endpoint and private DNS integration
- logging and alerting for secret access anomalies
- break-glass recovery procedures for lost or expired credentials

Expected secret/config categories include:

- Entra ID application identifiers
- confidential client credential material if managed identity is not used
- tenant ID and authority configuration if not derived dynamically
- billing hierarchy identifiers where externalized from static configuration
- session, cookie, or application signing material
- downstream API configuration requiring protected values

## Stub and simulation boundaries

The following boundaries are intentionally not live-complete.

### Event source hookup

The invoice-section event handler is a skeleton boundary, not a completed event integration.

Known boundary:

- No confirmed production event source is wired for MCA invoice section creation.
- If native Event Grid events are unavailable or insufficient in the target tenant, polling or workflow mediation may be required.

Required follow-up:

- confirm whether Landmark's MCA invoice-section lifecycle can emit the needed event
- choose the production trigger model:
  - Event Grid system topic
  - Logic App
  - scheduled poller
  - other reviewed integration
- add durable idempotency storage for processed event IDs
- add dead-lettering and operator-visible failure handling

### Microsoft Graph specifics

Service-principal creation is part of the intended workflow, but the live tenant wiring details are not complete.

Known boundary:

- Exact Microsoft Graph endpoints, payload details, consent model, and ownership model are not fully locked down in this scaffold.
- The repository should not imply that app registration, service principal creation, or credential issuance has been validated in Landmark's tenant.

Required follow-up:

- document the exact Graph API sequence
- define whether applications are:
  - created dynamically per vended subscription
  - reused from a managed identity or broker pattern
  - provisioned from an approved application template
- define owner assignment, display-name convention, and lifecycle cleanup behavior
- define whether credentials are created at all, or whether federated/workload identity removes that need

### Billing role assignment specifics

The billing role assignment slice exists, but production readiness still depends on tenant validation.

Known boundary:

- The code models the billing-scope role assignment path and treats billing scope as caller-supplied.
- Landmark-specific billing account, billing profile, and invoice section path validation is still required.

Required follow-up:

- verify the exact invoice-section billing scope format in the target MCA hierarchy
- verify the billing role definition identifier and assignment behavior in Landmark's tenant
- confirm idempotency and replay behavior under production retry conditions
- define operator-facing remediation for failed or partial billing-role assignment

### Subscription alias and provisioning

The alias creation module expresses the correct workflow boundary, but production use still requires live integration work.

Known boundary:

- The module models alias PUT/GET behavior and polling semantics.
- Real timeout, retry, long-running operation handling, and production error taxonomy need validation in Landmark's environment.

Required follow-up:

- validate alias naming rules and collision strategy
- validate polling backoff and maximum wait budgets
- define how asynchronous failures are surfaced to operators and requesters
- record correlation IDs for every ARM request in production logging

### Spoke linking and post-create landing-zone attachment

Spoke onboarding is not implemented.

Known boundary:

- The scaffold explicitly stops short of management group move, hub-and-spoke peering, policy baseline attachment, route propagation, DNS integration, and workload bootstrap.
- Infrastructure files expose the intended shape but do not complete cross-subscription networking orchestration.

Required follow-up:

- move newly created subscriptions into the correct management group
- bootstrap subscription-level provider registrations as needed
- establish spoke virtual network deployment pattern
- implement hub-and-spoke peering or approved connectivity pattern
- integrate private DNS and name-resolution strategy
- apply baseline policy assignments and exemptions
- assign approved RBAC roles for workload operators
- define region-specific hub selection and routing rules
- define rollback or quarantine behavior if onboarding partially fails

### Demo web app behavior

The current demo app is a storefront scaffold, not a production control plane.

Known boundary:

- Order submission uses simulated provisioning behavior.
- The result page displays placeholder workflow output.
- No durable order store, approval workflow, or privileged backend execution path is complete.

Required follow-up:

- replace local provisioning stub with a controlled backend workflow
- persist order requests and execution state
- enforce request validation against allowed catalog archetypes
- integrate Entra ID login and authorization policy
- add approver workflow if Landmark requires separation of duties
- prevent users from selecting unsupported combinations of landing-zone components

## Security posture ledger

The table below records the current security truthfulness of the scaffold.

| Area | Current posture | Risk if left as-is | Required before production |
|---|---|---|---|
| Identity separation | Intended but not fully implemented | Privilege creep and unclear blast radius | Split runtime identities by function and document each permission set |
| Secret storage | Expected to use Key Vault, not wired | Secret leakage or ad hoc local storage | Implement Key Vault-backed secret retrieval and rotation procedures |
| Microsoft Graph permissions | Not finalized | Over-privileged directory access | Approve exact Graph permission model and bootstrap path |
| Billing role assignment | Framework code exists, tenant validation pending | Failed vending or excessive billing scope | Validate role scope and behavior in Landmark tenant |
| Event ingestion | Skeleton only | Missed or duplicated vending requests | Implement durable event source, idempotency, and dead-letter handling |
| Web app authz | Login intent exists, policy incomplete | Unauthorized requests for privileged actions | Enforce Entra ID authentication and role-based authorization |
| Audit logging | Not complete | Weak forensic traceability | Add structured logs, correlation IDs, and immutable audit trail |
| Error handling | Partial and scaffold-level | Silent partial failure | Add retries, compensating actions, alerts, and operator runbooks |
| Network hardening | ALZ intent documented, not fully wired | Inconsistent spoke security posture | Implement approved hub/spoke, DNS, firewall, and private access controls |
| Policy governance | Assignment scaffold exists | Drift from governance baseline | Bind approved policy/initiative IDs and validate exemptions flow |

## Environment and configuration expectations

Future builders should keep configuration partitioned by responsibility.

### Non-secret configuration

Expected examples:

- tenant ID
- authority host
- region catalog
- management group IDs
- approved archetype names
- billing scope mapping metadata
- Key Vault URI
- app base URLs
- feature flags for scaffold versus live paths

### Secret or protected configuration

Expected examples:

- client secret or certificate reference if managed identity is not used
- session-signing secrets
- credential material used for any brokered Graph or billing action
- any sensitive callback verification or integration token
- any production-only override that can alter tenancy or billing behavior

### Configuration rules

- Production and non-production environments must use separate app registrations, identities, and Key Vault secret sets.
- Test tenants and production tenants must not share credentials.
- Sample configuration files must use obviously fake values.
- Fail closed when required secure configuration is missing.

## Production hardening checklist for follow-up PRs

The scaffold must not be promoted to production use until the following are complete.

### Identity and access

- Finalize runtime identity model.
- Approve least-privilege Azure RBAC roles.
- Approve least-privilege billing role scope.
- Approve least-privilege Microsoft Graph permission model.
- Document emergency access and credential rotation procedures.

### Tenant wiring

- Validate Landmark tenant IDs, billing hierarchy, management groups, and hub subscription ownership boundaries.
- Test live Graph flows in a non-production tenant first.
- Test live billing-role assignment in a controlled invoice section.
- Test live alias creation with rollback and replay scenarios.

### Eventing and workflow safety

- Implement the chosen event source.
- Add durable idempotency.
- Add queueing or workflow orchestration where needed for long-running operations.
- Add dead-letter and replay procedures.
- Add approval gates if required by governance.

### Security controls

- Implement Key Vault integration.
- Use managed identity where feasible.
- Add structured audit logs and correlation IDs.
- Add alerting on provisioning failure, repeated retries, and authorization denials.
- Add dependency and container/package scanning to the build pipeline.

### Operational readiness

- Create runbooks for:
  - failed vending request
  - duplicate event handling
  - failed billing role assignment
  - failed alias provisioning
  - partial spoke onboarding
  - credential rotation
- Define service-level objectives for vending latency and operator response.
- Add integration tests against a sandbox tenant and MCA hierarchy.
- Add disaster recovery expectations for order state and audit evidence.

## Known TODO ledger

This ledger is intentionally repetitive. Repetition is useful when the alternative is someone claiming the scaffold is done.

### Live tenant wiring

- TODO: supply real tenant-specific configuration for Entra ID, MCA billing hierarchy, management groups, and regional hub subscriptions
- TODO: validate every API path and identifier format against Landmark's tenant
- TODO: separate sandbox, pre-production, and production tenant wiring

### Microsoft Graph specifics

- TODO: define exact Graph endpoints and permission scopes
- TODO: define app registration naming and ownership conventions
- TODO: define whether credentials are secret-based, certificate-based, or eliminated through managed identity/federation
- TODO: document cleanup and deprovisioning for stale service principals

### Event source hookup

- TODO: confirm whether MCA invoice-section creation can be consumed directly from Event Grid in Landmark's environment
- TODO: implement the chosen event ingestion mechanism
- TODO: persist idempotency keys
- TODO: add dead-letter and replay support
- TODO: authenticate the event-processing component with a reviewed runtime identity

### Spoke linking

- TODO: move new subscriptions into the correct management group
- TODO: deploy spoke baseline resources into the new subscription
- TODO: connect spokes to the regional hub using the approved connectivity model
- TODO: integrate DNS, firewall, route, and private endpoint patterns
- TODO: define and implement rollback behavior for partial onboarding

### Key Vault integration

- TODO: create or reference environment-specific Key Vault instances
- TODO: implement managed identity access to secrets
- TODO: externalize all secret material from runtime configuration
- TODO: document naming, rotation, and access-review cadence
- TODO: define private networking requirements for Key Vault access

### Production hardening

- TODO: add approval workflow or policy gate if required by Landmark governance
- TODO: add structured observability and audit trail
- TODO: add retry/backoff policy with bounded failure handling
- TODO: add integration and end-to-end tests in a sandbox tenant
- TODO: add security review for Graph, billing, and ARM permission bundles
- TODO: add deployment pipeline controls for environment separation and secret injection
- TODO: write operational runbooks before go-live

## Truth-in-advertising statement

This repository currently demonstrates a credible implementation path for:

- Azure Landing Zone scaffold structure
- subscription-vending orchestration boundaries
- event-driven integration shape
- demo storefront interaction model

It does not yet demonstrate completed, approved, and production-safe automation for Landmark's tenant.

Any README, demo, stakeholder briefing, or engineering handoff should preserve that distinction exactly.

## Exit criteria before removing this note from the repo

Keep this document in place until all of the following are true:

- live tenant wiring is implemented and validated
- Graph, billing, ARM, and event-source flows are tested end to end
- Key Vault-backed secret handling is in place
- post-create spoke onboarding is implemented
- production hardening controls and runbooks exist
- security review signs off on the final permission model

When those are complete, replace this document with an updated production-readiness record rather than silently deleting the cautions.