# BlueprintAndChill

BlueprintAndChill is the foundational framework for an **Azure Landing Zone + subscription-vending accelerator** for customer **Landmark**.

This repo's first increment is intentionally a **production-grade framework and scaffold**, not a finished system. It establishes the architecture, governance model, API contracts, and implementation notes needed to build a fully automated Azure subscription-vending platform around Landmark's regional landing zones.

## Architecture summary

Here's what we're gonna do.

BlueprintAndChill will implement a **CAF- and ALZ-aligned** platform pattern where Landmark operates:

- a **central landing zone hub per region**
- **vended spoke subscriptions** connected to that hub
- **policy-driven governance** through management groups and Azure Policy
- **least-privilege billing-scope automation** for MCA-backed subscription creation
- a **demo Python web app on Azure Web App with Entra ID login** to request and shape deployments

The architectural source of truth for this framework is:

- [`docs/architecture.md`](docs/architecture.md)

## Research grounding

This framework is explicitly grounded in Microsoft guidance for:

- **Azure Landing Zones** as the standardized operating model for Azure at scale
- **Cloud Adoption Framework subscription vending**
- **management group hierarchy and policy inheritance**
- **landing zone identity and access management**
- **hub-and-spoke networking**
- **Microsoft Customer Agreement billing-role-based subscription creation**

Key Microsoft concepts carried into this repo:

- subscriptions are the primary unit of workload management
- platform teams vend subscriptions under governance
- management groups are used primarily for policy assignment
- application teams receive access at the subscription scope they need
- least privilege applies to both Azure RBAC and billing-scope automation

See the detailed brief in [`docs/architecture.md`](docs/architecture.md).

## Landmark target state

Landmark's target operating model in this framework is:

- **regional hub subscriptions** for shared connectivity/platform services
- **spoke subscriptions** vended per team/workload/environment
- each spoke **placed into the correct management group**
- each spoke **linked back to the appropriate regional hub**
- subscription creation triggered from an **MCA invoice section** workflow
- automation that creates a **service principal**, grants the exact **billing role** required, creates the subscription by **alias API**, then completes governance and connectivity steps
- a **demo storefront-style app** that lets users choose what gets deployed into the landing zone and each new subscription

## Management model

The intended management group shape is: