# BlueprintAndChill

Version: 0.1.0  
Last updated: July 3, 2026

BlueprintAndChill is a production-oriented framework and scaffold for Landmark's Azure Landing Zone (ALZ) and subscription-vending accelerator. The goal is to make new Azure subscriptions predictable, governed, and fast to provision within a repeatable landing-zone model, while also providing a demo web application that lets operators choose what should be deployed into the regional landing zone and into each new workload subscription.

This first pull request intentionally delivers the foundational framework, repository shape, and local-development path only. Live Azure control-plane calls, production event wiring, and tenant-specific deployment automation are stubbed by design in this phase. For the architecture baseline, governing assumptions, and source-backed Microsoft guidance, read `docs/architecture.md`.

## Why this exists

Landmark needs a hub-and-spoke cloud operating model per region:

- A central landing zone per region acts as the hub.
- Multiple workload subscriptions are created as spokes.
- Every new spoke subscription should be provisioned through one governed automation path.
- Billing, identity, policy, and placement should be handled consistently instead of through ad hoc portal work.
- Platform teams need a simple operator experience to select what gets deployed centrally versus per subscription.

BlueprintAndChill exists to provide that accelerator.

At a high level, the target system combines:
- Azure Landing Zone governance and management-group alignment
- Subscription vending for new workload subscriptions
- Least-privilege identity and role assignment for billing and provisioning steps
- A Python-based control plane and demo web application
- Future event-driven automation so new billing constructs can trigger subscription creation workflows automatically

## What good looks like

Microsoft's Cloud Adoption Framework (CAF) and Azure Landing Zones guidance establish the target shape for this solution: a governed management group hierarchy, centralized platform capabilities, workload subscriptions created through a standardized vending path, and policy/RBAC inheritance applied consistently. `docs/architecture.md` captures that baseline and the repo builds from it.

In practical terms, excellence for Landmark means:

- New subscriptions are never created manually as one-off exceptions.
- Regional hub resources are separated from workload spoke subscriptions.
- Governance is inherited from management groups instead of recreated for each subscription.
- Billing and identity steps are explicit, automatable, and auditable.
- Secrets are not committed to source control and are supplied through environment variables, managed identity, or secure secret storage.
- The system can evolve from CLI-driven scaffolding to event-driven automation without changing the core architecture.

See `docs/architecture.md` for the detailed rationale, framework notes, and the subscription-vending architecture baseline.

## Scope of this first PR

This repository state is a scaffold, not a finished Azure provisioning product.

Included in this first PR:

- Top-level project framework and documentation scaffold
- Python packaging and dependency groups in `pyproject.toml`
- Repository hygiene and ignore rules in `.gitignore`
- Architecture baseline in `docs/architecture.md`
- A documented path for local development, testing, CLI execution, and future web app work
- Clear boundaries describing what is intentionally stubbed for now

Intentionally not included in this first PR:

- Live Azure billing API execution
- Live Microsoft Graph or Entra ID application/service principal creation
- Live role assignment against billing scopes
- Live subscription creation and polling
- Real management group attachment or policy assignment operations
- Production webhook, Event Grid, Azure Functions, or invoice-section-trigger plumbing
- Tenant-specific identifiers, subscription IDs, billing account IDs, management group IDs, secrets, or certificates

If you are looking for working tenant automation, that is a future increment. This PR establishes the framework that future tasks will fill in.

## Landmark target vision

The target operating model is one hub-and-spoke landing zone per region.

### Regional model

For each region Landmark supports:

- One central landing-zone or platform hub subscription hosts shared capabilities such as connectivity, shared services, and platform-level controls.
- Multiple workload subscriptions are vended as spokes for individual environments, teams, or application groupings.
- New spoke subscriptions inherit organizational placement and governance rather than being hand-configured from scratch.
- The vending workflow attaches the new subscription to the correct landing-zone structure and prepares it for downstream deployment.

This keeps shared platform responsibilities centralized while allowing workload teams to operate within dedicated subscriptions.

## High-level subscription-vending flow

The end-to-end target flow for BlueprintAndChill is:

1. A new vending request is created.
2. In the future-state design, that request may originate automatically when a new Microsoft Customer Agreement (MCA) invoice section is created.
3. The system prepares or looks up the workload identity needed for provisioning.
4. The system grants the minimum required billing permissions for subscription creation.
5. The system creates the new subscription through the approved vending path.
6. The system attaches or aligns the new subscription with the Landmark landing-zone structure.
7. The system applies the initial governance and deployment selections for that subscription.
8. The system records status so operators can verify what happened and what remains to be completed.

In this first PR, that flow is represented as framework and scaffold only. Live Azure calls are intentionally stubbed, and future event integration remains a TODO.

## Demo web app purpose

BlueprintAndChill includes a planned demo web app for operators and stakeholders.

The web app is intended to show how an authenticated Landmark operator could:

- Sign in with Microsoft Entra ID
- Review available deployment options
- Choose what should be deployed into the regional landing zone
- Choose what should be deployed into each newly vended subscription
- Submit a governed request instead of performing manual Azure configuration
- Inspect scaffolded status and workflow results

For this first PR, the web app is a skeleton concern only. The README documents how the app layer is expected to run locally once the application files are present, but live Entra ID integration and live deployment actions are intentionally out of scope in this phase.

## Repository structure

Current repository framework:

    .
    ├── LICENSE
    ├── README.md
    ├── pyproject.toml
    ├── .gitignore
    └── docs/
        └── architecture.md

Expected scaffold growth over subsequent tasks:

    .
    ├── src/
    │   └── blueprintandchill/
    │       ├── cli/
    │       ├── core/
    │       ├── app/
    │       ├── events/
    │       └── config/
    ├── tests/
    ├── docs/
    │   └── architecture.md
    └── scripts/

Directory intent:

- `docs/architecture.md` — source-backed architecture baseline and Azure framework notes
- `src/blueprintandchill/cli/` — command-line entry points for local operator workflows
- `src/blueprintandchill/core/` — subscription-vending orchestration, Azure adapters, and domain logic
- `src/blueprintandchill/app/` — demo web app, templates, request handling, and Entra ID auth integration
- `src/blueprintandchill/events/` — future event-trigger handlers for invoice-section and related automation
- `src/blueprintandchill/config/` — environment-driven settings and validation
- `tests/` — unit and integration tests for scaffolded behavior

## Security and configuration principles

This repository follows a few non-negotiable operational rules from day one:

- Use least privilege for every identity involved in billing, subscription creation, and deployment.
- Keep secrets out of source control.
- Use environment variables for local development configuration.
- Prefer managed identity and secure secret stores in deployed environments.
- Do not hardcode tenant IDs, billing scope IDs, application secrets, subscription IDs, or customer identifiers in committed files.
- Treat production Azure operations as explicit adapters so they can be tested safely and stubbed locally.

For this first PR, environment variables are the only supported configuration contract. If a later phase introduces Key Vault or managed identity bootstrap, the code should still preserve environment-driven local development.

## Getting started

### Prerequisites

Install the following locally:

- Python 3.11 or newer
- `git`
- A virtual environment tool such as `venv`
- Optional: Azure CLI for later tasks that validate deployed auth and resource access
- Optional: `make` if you prefer task wrappers in future phases

Clone the repository and preserve the existing `LICENSE` file exactly as-is.

### Local setup

Create and activate a virtual environment:

    python -m venv .venv

On macOS or Linux:

    source .venv/bin/activate

On Windows PowerShell:

    .venv\Scripts\Activate.ps1

Install the package in editable mode with development dependencies:

    python -m pip install --upgrade pip
    python -m pip install -e ".[dev]"

If you want the future web-app stack available as well:

    python -m pip install -e ".[dev,app]"

If you want the future Azure automation libraries available for scaffold validation:

    python -m pip install -e ".[dev,core]"

If you want everything available in one environment:

    python -m pip install -e ".[dev,app,core,events]"

### Environment variables

All runtime configuration must come from environment variables.

Create a local `.env` file for development only if your future task implementation supports loading it through `python-dotenv`. Do not commit `.env` files. Do not place secrets in tracked files.

Suggested categories of environment variables for future tasks:

- Application environment name
- Azure tenant ID
- Azure client ID
- Azure client secret or certificate reference for local-only dev usage
- Billing account identifiers
- Billing profile identifiers
- Invoice section identifiers
- Management group identifiers
- Regional landing-zone defaults
- Web app session/auth settings
- Feature flags to switch between stub and live Azure adapters

Example shape only, with intentionally fake values:

    BLUEPRINTANDCHILL_ENV=local
    BLUEPRINTANDCHILL_USE_STUBS=true
    AZURE_TENANT_ID=00000000-0000-0000-0000-000000000000
    LANDMARK_DEFAULT_REGION=eastus
    LANDMARK_HUB_MANAGEMENT_GROUP_ID=mg-landingzones
    LANDMARK_WORKLOAD_MANAGEMENT_GROUP_ID=mg-platform-apps

Those values are illustrative, not production-ready. This first PR does not ship live Azure execution.

## Running the project locally

Because this PR is a framework-first scaffold, local execution depends on which later task files exist in your working tree.

### Run the CLI

The package metadata defines a `blueprintandchill` console entry point. Once the CLI module is implemented in a later task, you should be able to run:

    blueprintandchill --help

A likely future pattern is:

    blueprintandchill doctor
    blueprintandchill plan --region eastus
    blueprintandchill vend-subscription --request sample-request.json --dry-run

In this first PR, treat CLI behavior as scaffold intent. If the module is not present yet, that is expected at this phase.

### Run the web app skeleton

Once the app package is added in a later task, a typical local command will look like:

    uvicorn blueprintandchill.app.main:app --reload

Expected future local URL:

    http://127.0.0.1:8000

Expected future demo experience:

- Sign in through a development-safe Entra ID configuration
- Browse landing-zone and subscription deployment options
- Submit a stubbed vending request
- View a dry-run or scaffolded result state

In this first PR, the web app is not yet implemented. The purpose here is to establish the documented framework and dependency shape for that work.

## Testing

Install development dependencies first:

    python -m pip install -e ".[dev]"

Then run tests with:

    pytest

A stricter future local quality loop should look like:

    pytest
    ruff check .
    black --check .
    mypy src

At this stage, some commands may become actionable only after the corresponding source files are added by later tasks. That is normal for this scaffold PR.

## Development workflow

Recommended workflow for contributors:

1. Read `docs/architecture.md` before writing code.
2. Keep all configuration environment-driven.
3. Default to stub adapters for Azure and billing operations during local development.
4. Add tests alongside each new module.
5. Do not replace or modify `LICENSE` as part of unrelated work.
6. Document every new live Azure integration boundary before enabling it.

When implementing future work, prefer a clear separation between:
- domain logic
- Azure SDK or REST adapters
- web handlers
- event handlers
- configuration models

That separation will make it easier to test dry-run paths and preserve safe local development.

## Current scaffold status

Current status of the repository:

- Architecture baseline exists in `docs/architecture.md`
- Packaging exists in `pyproject.toml`
- Ignore rules exist in `.gitignore`
- This README defines the framework, scope, and development path
- Live Azure operations are intentionally stubbed
- Event-driven billing triggers are intentionally deferred
- Demo web app behavior is intentionally scaffolded, not complete

This is deliberate. The project is setting strong boundaries before implementation begins.

## TODO boundaries for future PRs

The following items are expected in future increments, not this one:

- Implement Azure adapter interfaces for subscription vending
- Add stub and live implementations behind a clean abstraction boundary
- Create service principal or app-registration workflow with explicit least-privilege review
- Assign the required billing role through a validated and auditable path
- Create the new subscription and wait for provisioning completion
- Attach the subscription to the correct management group hierarchy
- Apply landing-zone bootstrap resources and policies
- Implement the demo web app skeleton and Entra ID sign-in
- Add request persistence, status tracking, and audit history
- Add event integration so MCA invoice-section creation can trigger or pre-stage vending
- Add deployment packaging for Azure Web App and related infrastructure
- Add integration tests for dry-run and stubbed orchestration paths

## What this README should be read with

Read this file together with:

- `docs/architecture.md` — architecture baseline, Microsoft guidance alignment, and subscription-vending target design

If implementation files are added later, this README should remain the top-level orientation document while deeper operational details move into dedicated docs.

## Non-goals of this PR

To avoid ambiguity, this PR does not claim to deliver:

- a production-ready Azure provisioning engine
- a fully working web portal
- automated MCA event ingestion
- tenant-ready secrets or identities
- finalized infrastructure-as-code templates
- end-to-end deployment into a live Landmark tenant

It delivers the framework for those things.

## Notes for reviewers

Review this PR as foundational documentation and scaffold, not as a complete cloud automation system.

The key acceptance point is whether the repository now clearly explains:

- what BlueprintAndChill is
- how Landmark's regional hub-and-spoke model works
- what the subscription-vending flow is at a high level
- how contributors set up local development
- how configuration stays environment-driven
- where the architecture baseline lives
- which live Azure and event integrations are intentionally stubbed for now

If those are clear, this first framework PR has done its job.

## License

This repository retains the existing `LICENSE` file in the repository root. This README does not alter or replace it.