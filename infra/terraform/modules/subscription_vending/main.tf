terraform {
  required_providers {
    azuread = {
      source = "hashicorp/azuread"
    }

    azapi = {
      source = "azure/azapi"
    }

    random = {
      source = "hashicorp/random"
    }

    time = {
      source = "hashicorp/time"
    }
  }
}

# This module is the Terraform scaffold for Landmark's subscription-vending pattern.
#
# It mirrors the architecture brief exactly at a conceptual level:
# - vending originates from an MCA invoice section / billing scope
# - a service principal is created or referenced
# - the principal receives the exact billing role required to create subscriptions
# - a subscription alias request is made
# - the new subscription is attached to the landing zone and hub architecture
#
# IMPORTANT:
# This is intentionally NOT a finished live implementation. We do not invent
# unsupported provider resources. Instead, we:
# - expose the right inputs
# - create safe identity scaffolding where Terraform supports it
# - leave explicit TODO markers for billing role assignment and alias creation
# - output placeholders so future orchestration code can plug in cleanly

variable "request_name" {
  description = "Unique key for this vending request."
  type        = string
}

variable "workload_name" {
  description = "Workload or team name requesting the subscription."
  type        = string
}

variable "environment" {
  description = "Environment name for the vended subscription, for example dev, test, or prod."
  type        = string
}

variable "region_key" {
  description = "Region key whose hub this subscription should attach to."
  type        = string
}

variable "alias_name" {
  description = "Subscription alias name that will be used for the create request."
  type        = string
}

variable "subscription_name" {
  description = "Display name for the new Azure subscription."
  type        = string
}

variable "billing_scope" {
  description = "Full MCA billing scope string at the invoice section level used for subscription creation."
  type        = string
}

variable "invoice_section_id" {
  description = "Invoice section identifier associated with the billing scope."
  type        = string
}

variable "enrollment_type" {
  description = "Commercial enrollment type, expected to be MCA for the Landmark design."
  type        = string
}

variable "target_management_group_id" {
  description = "Management group ID where the vended subscription should be placed after creation."
  type        = string
}

variable "hub_subscription_id" {
  description = "Regional hub subscription ID that this new spoke will align to."
  type        = string
}

variable "hub_vnet_resource_id" {
  description = "Hub VNet resource ID for later spoke connectivity onboarding."
  type        = string
}

variable "create_application_registration" {
  description = "Whether this module should create a new Entra application registration for the vending principal."
  type        = bool
  default     = true
}

variable "existing_application_object_id" {
  description = "Existing Entra application object ID to use instead of creating one."
  type        = string
  default     = null
}

variable "existing_service_principal_id" {
  description = "Existing service principal object ID to use instead of creating one."
  type        = string
  default     = null
}

variable "billing_role_definition_id" {
  description = "The exact billing role definition ID required to grant subscription creation rights at the invoice section billing scope."
  type        = string
}

variable "tenant_id" {
  description = "Tenant ID for the Entra objects and later subscription alias request context."
  type        = string
}

variable "tags" {
  description = "Common tags from the root module."
  type        = map(string)
  default     = {}
}

locals {
  base_tags = merge(
    var.tags,
    {
      landingZoneRole = "spoke-request"
      region          = var.region_key
      workload        = var.workload_name
      requestName     = var.request_name
    }
  )

  using_existing_identity = !var.create_application_registration
}

# Create a deterministic suffix only when we are creating a fresh identity so
# repeated test requests can avoid display-name collisions.
resource "random_string" "identity_suffix" {
  count = var.create_application_registration ? 1 : 0

  length  = 4
  upper   = false
  lower   = true
  numeric = true
  special = false
}

# Optional app registration scaffold.
resource "azuread_application" "vending" {
  count = var.create_application_registration ? 1 : 0

  display_name = "bpac-${var.workload_name}-${var.environment}-${random_string.identity_suffix[0].result}"

  # TODO: Add app roles / federated credentials / redirect URIs if the vending
  # orchestration service or demo web app will operate this principal directly.
  #
  # For this framework PR, we only prove the place in the design where the
  # application identity belongs.
}

# Optional service principal scaffold corresponding to the application registration.
resource "azuread_service_principal" "vending" {
  count = var.create_application_registration ? 1 : 0

  client_id = azuread_application.vending[0].client_id

  # TODO: If Landmark requires app-role assignments or directory role grants for
  # non-billing operations, model them in a later identity-focused PR.
}

# A tiny wait can be practical in real Entra automation due to eventual consistency.
# Here it acts as a documented reminder without forcing any unsupported billing call.
resource "time_sleep" "wait_for_service_principal" {
  count = var.create_application_registration ? 1 : 0

  depends_on = [
    azuread_service_principal.vending
  ]

  create_duration = "15s"
}

locals {
  application_object_id = var.create_application_registration ? azuread_application.vending[0].object_id : var.existing_application_object_id
  service_principal_id  = var.create_application_registration ? azuread_service_principal.vending[0].object_id : var.existing_service_principal_id
}

################################################################################
# Billing-role assignment placeholder
################################################################################

# TODO: LIVE IMPLEMENTATION REQUIRED
#
# The Landmark design depends on granting the exact required billing role at the MCA
# invoice section billing scope before attempting subscription creation.
#
# We intentionally do NOT fake this with an unsupported Terraform resource.
# Depending on final tool choice, the live implementation may use:
# - azapi against the billing role-assignment endpoint,
# - an external orchestrator step,
# - or a deployment script invoked outside Terraform.
#
# The architecture brief already captures the verified role semantics and sequence.
# This scaffold simply marks the insertion point.
resource "azapi_resource" "billing_role_assignment_placeholder" {
  type      = "Microsoft.Resources/tags@2021-04-01"
  name      = "placeholder-billing-role-${var.request_name}"
  parent_id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/placeholder-do-not-deploy"

  body = {
    properties = {
      tags = merge(
        local.base_tags,
        {
          scaffoldPurpose         = "billing-role-assignment-placeholder"
          billingScope            = var.billing_scope
          billingRoleDefinitionId = var.billing_role_definition_id
          servicePrincipalObjectId = coalesce(local.service_principal_id, "TODO")
          implementationStatus    = "TODO-live-billing-role-assignment"
        }
      )
    }
  }

  lifecycle {
    ignore_changes = all
  }

  # This placeholder is intentionally non-functional and should be replaced or
  # removed in the implementation PR before any real apply in Azure.
  #
  # We leave it here because this module's purpose is to make the vending flow
  # explicit in the Terraform structure.
}

################################################################################
# Subscription alias placeholder
################################################################################

# TODO: LIVE IMPLEMENTATION REQUIRED
#
# Subscription alias creation for MCA-backed vending is the core control-plane call.
# We do not claim azurerm natively handles the exact Landmark flow yet in this PR.
# The future implementation should issue the alias create request with:
# - alias name
# - subscription display name
# - billing scope / invoice section
# - workload ownership metadata
# - management group placement / follow-up steps as required
resource "azapi_resource" "subscription_alias_placeholder" {
  type      = "Microsoft.Resources/tags@2021-04-01"
  name      = "placeholder-subscription-alias-${var.request_name}"
  parent_id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/placeholder-do-not-deploy"

  body = {
    properties = {
      tags = merge(
        local.base_tags,
        {
          scaffoldPurpose          = "subscription-alias-placeholder"
          aliasName                = var.alias_name
          subscriptionName         = var.subscription_name
          enrollmentType           = var.enrollment_type
          targetManagementGroupId  = var.target_management_group_id
          hubSubscriptionId        = var.hub_subscription_id
          hubVnetResourceId        = var.hub_vnet_resource_id
          invoiceSectionId         = var.invoice_section_id
          implementationStatus     = "TODO-live-subscription-alias-create"
        }
      )
    }
  }

  lifecycle {
    ignore_changes = all
  }
}

################################################################################
# Post-vend landing zone attachment notes
################################################################################

# TODO in later PRs after real alias creation exists:
# - management group association for the new subscription
# - spoke resource group bootstrap
# - hub VNet peering request or network attachment workflow
# - baseline role assignments for workload owners
# - policy remediation hooks
#
# We keep those as documented next steps instead of pretending the subscription
# already exists inside Terraform state.

output "alias_name" {
  description = "Requested subscription alias name."
  value       = var.alias_name
}

output "subscription_name" {
  description = "Requested Azure subscription display name."
  value       = var.subscription_name
}

output "service_principal_object_id" {
  description = "Service principal object ID created or referenced for vending."
  value       = local.service_principal_id
}

output "application_object_id" {
  description = "Application object ID created or referenced for vending."
  value       = local.application_object_id
}

output "subscription_resource_id" {
  description = "Placeholder subscription resource ID until live alias creation is implemented."
  value       = "TODO://subscription-created-via-alias/${var.alias_name}"
}

output "implementation_status" {
  description = "Explicit marker that this module is scaffold-only in the current PR."
  value = {
    billing_role_assignment = "TODO: implement exact MCA billing role assignment at invoice section scope"
    subscription_alias      = "TODO: implement subscription alias create call"
    management_group_move   = "TODO: attach newly created subscription to landing zones management group"
    hub_connectivity        = "TODO: onboard vended spoke to regional hub connectivity model"
    guardrail_note          = "Scaffold intentionally avoids inventing unsupported Terraform APIs"
  }
}