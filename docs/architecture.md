# BlueprintAndChill architecture foundation

## Purpose

This document defines the **foundational architecture** for BlueprintAndChill as a production-grade framework and scaffold for customer **Landmark**. The goal of this first increment is not to finish the full system; it is to establish the correct target architecture, governance model, and source-backed API contract for a subscription-vending accelerator aligned to Microsoft guidance.

The design is grounded in:

- **Microsoft Cloud Adoption Framework (CAF)**
- **Azure Landing Zones (ALZ)**
- Microsoft guidance for **subscription vending**
- Microsoft guidance for **management groups**
- Microsoft guidance for **identity and access management in landing zones**
- Official Microsoft REST API references for **billing role assignment** and **subscription alias creation**

## CAF and ALZ grounding

Microsoft positions an **Azure landing zone** as the standardized, recommended foundation for Azure environments at scale. The reference architecture is modular, repeatable, and aligned to eight design areas including billing and tenant, identity and access management, management group and subscription organization, networking, security, governance, and platform automation. Azure Landing Zones explicitly support a **hub-and-spoke** topology and a **management-group-hierarchy-only** view as first-class patterns.[^alz-overview]

CAF guidance for **subscription vending** is directly applicable here: the platform team establishes an official front door for requesting subscriptions, then creates and configures subscriptions under governance so application teams can deploy safely and quickly.[^caf-sub-vending] CAF also makes the key design move explicit: in a democratized Azure operating model, **subscriptions are the primary unit of workload management and scale**, not resource groups.[^caf-sub-vending]

CAF guidance for **management groups** is equally clear: keep the hierarchy relatively flat, use management groups primarily for **policy assignment**, and avoid using management group scope as the normal place to grant application-team RBAC. Application access should instead be assigned during the vending process at the subscription or resource-group scope that the team actually needs.[^caf-mg]

CAF guidance for **identity and access management** establishes the operating model for this framework: the platform team provisions and governs subscriptions, while application owners manage their workloads inside policy guardrails. Access should follow **just-enough access (JEA)**, and privileged elevation should use **PIM/JIT** where needed.[^caf-iam]

### What this means for BlueprintAndChill

Here's what we're gonna do.

BlueprintAndChill will implement a **platform-led, policy-driven subscription vending product line** for Landmark:

1. A **regional hub landing zone** provides shared connectivity and platform controls.
2. A vending workflow creates or accepts a billing request tied to an **MCA invoice section**.
3. Automation creates a **service principal** for the new spoke workload/team.
4. Automation grants that principal only the **billing permission required to create the subscription** at the invoice-section scope.
5. Automation creates the subscription via the **Microsoft.Subscription alias API**.
6. The new subscription is attached to the correct **management group**, inherits policy guardrails, and is connected back to the correct **regional hub**.
7. A demo web app provides the request and selection path for what gets deployed into the hub and each new spoke.

That is squarely consistent with CAF/ALZ: centralized platform governance, decentralized workload ownership, subscription-based isolation, and repeatable automation.[^caf-sub-vending] [^caf-iam] [^alz-overview]

## Landmark target state: hub-and-spoke per region

Landmark's required target state is:

- **One central landing zone hub per region**
- **Many vended spoke subscriptions per region**
- Each spoke is **connected back to its regional hub**
- Subscription creation is **fully automated**
- Ideal trigger is **new MCA invoice section created**
- Automation uses **least privilege** at **billing scope**
- A **demo web app** allows authorized users to choose what platform/app baseline gets deployed

This framework therefore defines the following target model.

### Regional platform pattern

For each onboarded Azure region:

- A **hub subscription** hosts regional shared services:
 - hub virtual network
 - shared ingress/egress controls
 - DNS forwarding/private DNS integration
 - firewall/NVA/WAF integration as required
 - shared observability and platform agents as needed
- A **subscription-vending automation component** operates from a controlled platform subscription
- New **spoke subscriptions** are vended into the correct application landing zone management group for that region/environment
- Each new spoke is linked back to the hub by approved connectivity patterns

### Spoke subscription pattern

Each vended spoke subscription is expected to receive, at minimum:

- correct **billing scope**
- correct **management group placement**
- inherited **Azure Policy** assignments and initiatives
- baseline **RBAC**
- baseline **diagnostics/monitoring hooks**
- approved **network connectivity** to the hub
- optional workload template selections from the demo app

### Demo app interaction path

The demo app is an **Azure Web App** running **Python** with **Microsoft Entra ID** sign-in. In this first framework PR, the app is a contract and scaffold, not the final implementation.

Expected interaction path:

1. Authorized user signs in with Entra ID.
2. User selects:
 - region
 - landing zone/spoke product line
 - environment
 - optional baseline modules
3. User either:
 - links to an already-created MCA invoice section, or
 - starts a request tied to an expected invoice section event
4. Backend orchestration performs:
 - service principal creation
 - billing role assignment at invoice-section scope
 - subscription alias creation
 - management group placement
 - spoke-to-hub connectivity workflow
5. App returns request status, created subscription identifiers, and next-step handoff data.

## Management group hierarchy

CAF recommends a reasonably flat hierarchy and using management groups for governance, not as a convenience layer for broad RBAC delegation.[^caf-mg]

For Landmark, the foundational hierarchy should be: