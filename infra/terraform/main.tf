############################################################
# BlueprintAndChill — Terraform Root Entrypoint
# Landmark Azure Landing Zone + Subscription Vending
#
# This is a FRAMEWORK/SCAFFOLD, mirroring infra/bicep/main.bicep.
# It composes the platform landing zone modules:
#   - management_groups   (CAF management group hierarchy)
#   - hub_networking      (hub-and-spoke connectivity)
#   - policy_assignments  (Azure Policy governance)
#   - subscription_vending (programmatic subscription issuance)
#
# TODO: Live subscription creation, MCA billing wiring, and
# event-driven triggers (new invoice section -> vending) are
# stubbed with TODOs throughout. Do NOT treat this as a
# finished, deployable production system yet.
############################################################

terraform {
  required_version = ">= 1.7.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.53"
    }
    # azapi is required because subscription creation (Microsoft.Subscription/aliases)
    # and some management-group-scoped policy operations are not yet fully modeled
    # in azurerm. TODO: revisit once azurerm subscription resources reach parity.
    azapi = {
      source  = "azure/azapi"
      version = "~> 1.13"
    }
  }

  # TODO: Configure remote state backend before any real deployment.
  # Landmark should use an azurerm backend pointed at a locked-down
  # storage account in the platform management subscription, e.g.:
  #
  # backend "azurerm" {
  #   resource_group_name  = "rg-landmark-tfstate"
  #   storage_account_name = "REPLACE_ME"
  #   container_name       = "tfstate"
  #   key                  = "blueprintandchill.landingzone.tfstate"
  #   use_azuread_auth     = true
  # }
  #
  # Intentionally left as local backend / no backend block here so this
  # scaffold does not silently write real state anywhere. Configure via
  # `terraform init -backend-config=...` per environment.
}

provider "azurerm" {
  features {}

  # TODO: Pin to a specific subscription_id per environment via
  # ARM_SUBSCRIPTION_ID env var or -var, never hardcode here.
  # subscription_id = var.platform_subscription_id
}

provider "azuread" {
  # TODO: tenant_id should come from ARM_TENANT_ID / var, not hardcoded.
}

provider "azapi" {
}

# ------------------------------------------------------------------
# Management group hierarchy — CAF-aligned platform/landing-zone/
# sandbox/decommissioned structure under the Landmark tenant root.
# ------------------------------------------------------------------
module "management_groups" {
  source = "./modules/management_groups"

  root_management_group_display_name = var.root_management_group_display_name
  management_group_prefix            = var.management_group_prefix
  # TODO: parent_management_group_id should be the tenant root group id
  # (or an existing intermediate root) — never hardcode a real tenant GUID.
  parent_management_group_id = var.parent_management_group_id
  tags                       = var.tags
}

# ------------------------------------------------------------------
# Hub networking — the connectivity spoke of the platform landing
# zone. One hub per region, spokes peer into it.
# ------------------------------------------------------------------
module "hub_networking" {
  source = "./modules/hub_networking"

  location            = var.location
  environment         = var.environment
  project_name        = var.project_name
  hub_vnet_cidr       = var.hub_vnet_cidr
  gateway_subnet_cidr = var.gateway_subnet_cidr
  firewall_subnet_cidr = var.firewall_subnet_cidr
  shared_services_subnet_cidr = var.shared_services_subnet_cidr
  tags                = var.tags

  # TODO: resource_group_name here is scaffold-only. In a real deploy this
  # should reference an existing platform-connectivity resource group
  # created earlier in the pipeline, not implicitly created inline.
  resource_group_name = "${var.resource_group_prefix}-connectivity-${var.environment}"
}

# ------------------------------------------------------------------
# Policy assignments — Azure Policy applied at the management group
# scope so spokes inherit governance automatically.
# ------------------------------------------------------------------
module "policy_assignments" {
  source = "./modules/policy_assignments"

  management_group_id = module.management_groups.landing_zones_management_group_id
  environment          = var.environment
  enable_deny_public_ip = var.enable_deny_public_ip
  enable_require_tags   = var.enable_require_tags
  allowed_locations     = var.allowed_locations
}

# ------------------------------------------------------------------
# Subscription vending — the automated, governed path for issuing
# a new spoke subscription. Intended trigger: creation of a new MCA
# invoice section (event-driven), landing here as an apply.
# ------------------------------------------------------------------
module "subscription_vending" {
  source = "./modules/subscription_vending"

  subscription_display_name  = var.new_subscription_display_name
  billing_account_id         = var.billing_account_id
  billing_profile_id         = var.billing_profile_id
  invoice_section_id         = var.invoice_section_id
  management_group_id        = module.management_groups.landing_zones_management_group_id
  service_principal_display_name = var.vending_service_principal_display_name
  environment                = var.environment
  tags                       = var.tags
}