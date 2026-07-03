############################################################
# Module: management_groups
#
# Establishes the CAF-aligned management group hierarchy for
# Landmark under a parent scope (typically tenant root):
#
#   <parent>
#     └── Landmark (root)
#           ├── Platform
#           │     ├── Connectivity
#           │     ├── Identity
#           │     └── Management
#           ├── LandingZones
#           │     ├── Corp
#           │     └── Online
#           ├── Sandbox
#           └── Decommissioned
#
# TODO: Subscription-to-management-group associations are
# intentionally NOT wired here — they belong to the
# subscription_vending flow, which moves a subscription into
# the correct landing zone MG once vended. Hardcoding
# associations here would defeat the vending pattern.
############################################################

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
  }
}

variable "root_management_group_display_name" {
  description = "Display name for the Landmark root management group."
  type        = string
}

variable "management_group_prefix" {
  description = "Prefix applied to child management group IDs to keep them globally unique in the tenant."
  type        = string
}

variable "parent_management_group_id" {
  description = "Fully qualified resource ID of the parent scope (tenant root or an existing intermediate group). TODO: must be supplied per tenant."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags to apply where the resource type supports them (management groups do not natively support tags, kept for interface parity with other modules)."
  type        = map(string)
  default     = {}
}

# Root management group for Landmark
resource "azurerm_management_group" "root" {
  display_name               = var.root_management_group_display_name
  name                        = "${var.management_group_prefix}-root"
  parent_management_group_id = var.parent_management_group_id != "" ? var.parent_management_group_id : null

  # TODO: subscription_ids left empty by design — subscriptions are
  # associated dynamically via the subscription_vending module output,
  # not statically declared in the hierarchy definition.
}

# Platform management group — houses connectivity/identity/management subscriptions
resource "azurerm_management_group" "platform" {
  display_name               = "Platform"
  name                        = "${var.management_group_prefix}-platform"
  parent_management_group_id = azurerm_management_group.root.id
}

resource "azurerm_management_group" "platform_connectivity" {
  display_name               = "Connectivity"
  name                        = "${var.management_group_prefix}-platform-connectivity"
  parent_management_group_id = azurerm_management_group.platform.id
}

resource "azurerm_management_group" "platform_identity" {
  display_name               = "Identity"
  name                        = "${var.management_group_prefix}-platform-identity"
  parent_management_group_id = azurerm_management_group.platform.id
}

resource "azurerm_management_group" "platform_management" {
  display_name               = "Management"
  name                        = "${var.management_group_prefix}-platform-management"
  parent_management_group_id = azurerm_management_group.platform.id
}

# Landing zones management group — where vended spoke subscriptions land
resource "azurerm_management_group" "landing_zones" {
  display_name               = "LandingZones"
  name                        = "${var.management_group_prefix}-landingzones"
  parent_management_group_id = azurerm_management_group.root.id
}

resource "azurerm_management_group" "landing_zones_corp" {
  display_name               = "Corp"
  name                        = "${var.management_group_prefix}-landingzones-corp"
  parent_management_group_id = azurerm_management_group.landing_zones.id
}

resource "azurerm_management_group" "landing_zones_online" {
  display_name               = "Online"
  name                        = "${var.management_group_prefix}-landingzones-online"
  parent_management_group_id = azurerm_management_group.landing_zones.id
}

# Sandbox — for exploratory workloads with looser policy
resource "azurerm_management_group" "sandbox" {
  display_name               = "Sandbox"
  name                        = "${var.management_group_prefix}-sandbox"
  parent_management_group_id = azurerm_management_group.root.id
}

# Decommissioned — holding pen for subscriptions being retired
resource "azurerm_management_group" "decommissioned" {
  display_name               = "Decommissioned"
  name                        = "${var.management_group_prefix}-decommissioned"
  parent_management_group_id = azurerm_management_group.root.id
}

output "root_management_group_id" {
  description = "Resource ID of the Landmark root management group."
  value       = azurerm_management_group.root.id
}

output "platform_management_group_id" {
  description = "Resource ID of the Platform management group."
  value       = azurerm_management_group.platform.id
}

output "landing_zones_management_group_id" {
  description = "Resource ID of the LandingZones management group — the default vending target."
  value       = azurerm_management_group.landing_zones.id
}

output "sandbox_management_group_id" {
  description = "Resource ID of the Sandbox management group."
  value       = azurerm_management_group.sandbox.id
}

output "decommissioned_management_group_id" {
  description = "Resource ID of the Decommissioned management group."
  value       = azurerm_management_group.decommissioned.id
}