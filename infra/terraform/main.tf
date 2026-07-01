terraform {
  required_version = ">= 1.7.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }

    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }

    azapi = {
      source  = "azure/azapi"
      version = "~> 2.0"
    }

    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }

    time = {
      source  = "hashicorp/time"
      version = "~> 0.12"
    }
  }
}

provider "azurerm" {
  features {}

  # TODO: In a later implementation PR, decide whether this root module should:
  # - authenticate with the operator's identity for local execution, or
  # - authenticate through federated workload identity in CI/CD.
  #
  # This framework scaffold intentionally does not hardcode subscription_id because
  # the platform spans tenant, management group, billing, and multi-subscription scope.
}

provider "azuread" {
  # TODO: Confirm whether Landmark will manage app registrations/service principals
  # from the same tenant as the ALZ platform deployment identity.
}

provider "azapi" {
  # TODO: The subscription alias API and some billing-scope operations are exposed via
  # ARM/management-plane endpoints that are often easier to model through azapi than
  # through azurerm resources alone.
}

locals {
  # ALZ-oriented tagging. These are merged into module-specific tags so every resource
  # created by future implementation work carries the same baseline metadata.
  common_tags = merge(
    {
      project     = var.project_name
      environment = var.environment
      owner       = var.owner
      costCenter  = var.cost_center
      managedBy   = "terraform"
      framework   = "alz"
      accelerator = "BlueprintAndChill"
    },
    var.additional_tags
  )

  # This scaffold models the exact conceptual platform split:
  # - tenant / management group hierarchy
  # - regional hub subscriptions and networking
  # - policy assignment layer
  # - subscription vending aligned to MCA invoice section + billing role + alias create
  #
  # The live REST/API calls are intentionally deferred to later tasks. The structure is
  # here now so the repo shows the intended production-grade layout without pretending
  # unsupported Terraform-native APIs already exist.
}

################################################################################
# Management group scaffold
################################################################################

# NOTE:
# Management groups are represented here as a scaffold for ALZ-aligned hierarchy.
# We only model the hierarchy and intended placement metadata. We do not attempt to
# fully implement every ALZ policy or archetype in this first PR.
#
# CAF guidance says management groups should stay relatively flat and primarily carry
# policy assignments; application-team RBAC should typically be applied at the
# subscription scope during vending, not broadly at management-group scope. See the
# repo architecture source of truth for the rationale and Microsoft references in
# docs/architecture.md. 
resource "azurerm_management_group" "platform" {
  display_name               = var.platform_management_group.display_name
  name                       = var.platform_management_group.name
  parent_management_group_id = var.platform_management_group.parent_management_group_id
}

resource "azurerm_management_group" "landing_zones" {
  display_name               = var.landing_zones_management_group.display_name
  name                       = var.landing_zones_management_group.name
  parent_management_group_id = azurerm_management_group.platform.id
}

resource "azurerm_management_group" "platform_hubs" {
  display_name               = var.platform_hubs_management_group.display_name
  name                       = var.platform_hubs_management_group.name
  parent_management_group_id = azurerm_management_group.platform.id
}

resource "azurerm_management_group" "sandbox" {
  count = var.create_sandbox_management_group ? 1 : 0

  display_name               = var.sandbox_management_group.display_name
  name                       = var.sandbox_management_group.name
  parent_management_group_id = azurerm_management_group.platform.id
}

################################################################################
# Hub networking scaffold
################################################################################

# One module instance per region. Each regional hub subscription is expected to host
# shared connectivity services for its spokes in an ALZ hub-and-spoke model.
#
# This is intentionally scaffold-level:
# - network resources are created only in the hub subscription context supplied
# - peerings, firewall, DNS, ER/VPN, and private resolver details are left as TODOs
# - no unsupported cross-subscription magic is implied
module "hub_networking" {
  source = "./modules/hub_networking"

  for_each = var.hub_regions

  location            = each.value.location
  region_key          = each.key
  region_display_name = each.value.display_name

  subscription_id = each.value.hub_subscription_id
  tenant_id       = var.tenant_id

  resource_group_name = each.value.resource_group_name
  vnet_name           = each.value.vnet_name
  address_space       = each.value.address_space

  gateway_subnet_prefixes          = each.value.gateway_subnet_prefixes
  azure_firewall_subnet_prefixes   = each.value.azure_firewall_subnet_prefixes
  bastion_subnet_prefixes          = each.value.bastion_subnet_prefixes
  shared_services_subnet_prefixes  = each.value.shared_services_subnet_prefixes
  private_endpoints_subnet_prefixes = each.value.private_endpoints_subnet_prefixes
  dns_resolver_subnet_prefixes     = each.value.dns_resolver_subnet_prefixes

  create_ddos_plan               = each.value.create_ddos_plan
  ddos_plan_name                 = each.value.ddos_plan_name
  enable_bastion_placeholder     = each.value.enable_bastion_placeholder
  enable_firewall_placeholder    = each.value.enable_firewall_placeholder
  enable_private_dns_placeholder = each.value.enable_private_dns_placeholder

  tags = local.common_tags
}

################################################################################
# Policy assignment scaffold
################################################################################

# This scaffold represents the policy layer conceptually without claiming the repo
# already implements Landmark's full initiative catalog.
#
# The intent is:
# - assign platform-level policy at the correct management groups
# - inherit guardrails into hub and vended subscriptions
# - keep policy authoring separate from the vending workflow
#
# TODO in later PRs:
# - replace placeholder policy definition IDs with a curated ALZ/CAF-aligned set
# - model initiatives/assignments/exemptions in dedicated module files
# - parameterize region-, environment-, and workload-specific policy values
resource "azurerm_management_group_policy_assignment" "platform" {
  for_each = var.policy_assignments

  name                 = each.value.name
  display_name         = each.value.display_name
  description          = each.value.description
  management_group_id  = each.value.scope == "platform" ? azurerm_management_group.platform.id : azurerm_management_group.landing_zones.id
  policy_definition_id = each.value.policy_definition_id

  # Policy parameters remain JSON because many built-in and custom definitions still
  # expect ARM-style parameter payloads.
  parameters = jsonencode(each.value.parameters)

  # TODO: If Landmark needs managed identity-backed deployIfNotExists/modify policies,
  # add identity and location handling here in the implementation PR.
}

################################################################################
# Subscription vending scaffold
################################################################################

# This module captures the exact vending mechanism conceptually:
# 1. A request is associated to an MCA invoice section / billing scope.
# 2. A service principal is created or referenced.
# 3. The billing role required for subscription creation is granted at billing scope.
# 4. A subscription alias create call is made.
# 5. The new subscription is placed into the correct management group.
# 6. Post-vend landing zone attachment steps connect it back to the proper regional hub.
#
# The live billing role assignment and alias creation calls are intentionally stubbed.
# That is by design for this framework PR: show the structure, avoid inventing
# unsupported provider behavior, and leave explicit TODOs for the later implementation.
module "subscription_vending" {
  source = "./modules/subscription_vending"

  for_each = var.subscription_vending_requests

  request_name        = each.key
  workload_name       = each.value.workload_name
  environment         = each.value.environment
  region_key          = each.value.region_key
  alias_name          = each.value.alias_name
  subscription_name   = each.value.subscription_name
  billing_scope       = each.value.billing_scope
  invoice_section_id  = each.value.invoice_section_id
  enrollment_type     = each.value.enrollment_type

  target_management_group_id = azurerm_management_group.landing_zones.id
  hub_subscription_id        = var.hub_regions[each.value.region_key].hub_subscription_id
  hub_vnet_resource_id       = module.hub_networking[each.value.region_key].hub_vnet_resource_id

  create_application_registration = each.value.create_application_registration
  existing_application_object_id  = each.value.existing_application_object_id
  existing_service_principal_id   = each.value.existing_service_principal_id

  billing_role_definition_id = var.billing_role_definition_id
  tenant_id                  = var.tenant_id
  tags                       = local.common_tags
}

################################################################################
# Helpful outputs for future composition
################################################################################

output "management_group_ids" {
  description = "Management group identifiers created by the scaffold."
  value = {
    platform      = azurerm_management_group.platform.id
    landing_zones = azurerm_management_group.landing_zones.id
    platform_hubs = azurerm_management_group.platform_hubs.id
    sandbox       = try(azurerm_management_group.sandbox[0].id, null)
  }
}

output "hub_network_ids" {
  description = "Hub VNet resource IDs keyed by region."
  value = {
    for region, module_instance in module.hub_networking :
    region => module_instance.hub_vnet_resource_id
  }
}

output "subscription_vending_requests" {
  description = "Echo of subscription vending request metadata and placeholder outputs."
  value = {
    for request, module_instance in module.subscription_vending :
    request => {
      alias_name                 = module_instance.alias_name
      requested_subscription_name = module_instance.subscription_name
      service_principal_object_id = module_instance.service_principal_object_id
      subscription_resource_id    = module_instance.subscription_resource_id
      implementation_status       = module_instance.implementation_status
    }
  }
}