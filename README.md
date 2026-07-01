# BlueprintAndChill

BlueprintAndChill is the application scaffold for a Landmark Azure Landing Zone deployment accelerator. This repository starts with a production-structured Python FastAPI demo app that will sit alongside the infrastructure and documentation tracks for hub-and-spoke landing zones, subscription vending, and governed workload onboarding.

## Current scope

This foundational scaffold delivers the **demo app lane**:

- FastAPI application package layout
- configuration module with environment-based settings
- Azure AD / Microsoft Entra ID auth framework stubs
- subscription shopping catalog endpoints
- request submission endpoints for future vending automation
- clear boundaries between routes, models, services, and automation hooks
- safe placeholders only for Azure SDK and billing/subscription integration

It intentionally does **not** include live tenant wiring, real credentials, or active subscription creation.

## App structure

```text
src/blueprintandchill/
├── __init__.py
├── main.py
├── config.py
├── auth/
│   ├── __init__.py
│   ├── dependencies.py
│   └── entra.py
├── api/
│   ├── __init__.py
│   ├── catalog.py
│   ├── health.py
│   └── subscriptions.py
├── models/
│   ├── __init__.py
│   ├── catalog.py
│   └── subscription_request.py
├── services/
│   ├── __init__.py
│   ├── catalog_service.py
│   ├── request_store.py
│   └── vending_service.py
└── web/
    ├── __init__.py
    ├── routes.py
    ├── static/
    │   └── app.css
    └── templates/
        ├── base.html
        ├── index.html
        └── subscription_shop.html
```

## Quick start

### Requirements

- Python 3.11+

### Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
```

### Run tests

```bash
pytest
```

### Run the app

```bash
uvicorn blueprintandchill.main:app --reload
```

Or:

```bash
./uvicorn_start.sh
```

## Key endpoints

- `GET /healthz` - health probe
- `GET /api/v1/catalog/subscription-options` - returns deployable subscription options
- `POST /api/v1/subscriptions/requests` - accepts a subscription vending request payload
- `GET /api/v1/subscriptions/requests` - lists locally stored requests
- `GET /` - landing page
- `GET /shop` - minimal demo shopping experience

## Environment configuration

All configuration is environment-driven. See `.env.example` for placeholders.

Important design rule: **do not commit real tenant IDs, client secrets, subscription IDs, or billing identifiers**.

## Future integration points

The scaffold deliberately leaves TODO seams for:

- OpenID Connect login against Microsoft Entra ID
- token validation and session management
- Graph/app-role/group authorization checks
- Azure subscription vending workflows
- Terraform/Bicep/ARM orchestration hooks
- durable persistence beyond local JSON files

Glavin! This is the runway, not the fully fueled rocket.