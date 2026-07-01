terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
}

# This module is a scaffold for a single ALZ regional hub network.
# It is intentionally opinionated toward hub-and-spoke, but stops short of
# pretending the full production network has already been implemented.
#
# Expected future scope in implementation PRs:
# - hub VNet and reserved subnets
# - DDoS plan (optional)
# - Azure Firewall / Bastion / VPN / ER placeholders promoted to real resources
# - private DNS zones and resolver
# - peering/onboarding workflow for vended spoke subscriptions
#
# For now, the module establishes the foundational structure and the correct
# parameter surface so the repo demonstrates production-grade intent.

variable "location" {
  description = "Azure region for the hub."
  type        = string
}

variable "region_key" {
  description = "Short key for the region, used for metadata and composition."
  type        = string
}

variable "region_display_name" {
  description = "Human-friendly display name for the region."
  type        = string
}

variable "subscription_id" {
  description = "Hub subscription ID for this region. Included for documentation/composition even though provider aliasing is deferred to a later PR."
  type        = string
}

variable "tenant_id" {
  description = "Tenant ID for informational and future composition use."
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group that will host hub networking resources."
  type        = string
}

variable "vnet_name" {
  description = "Name of the hub virtual network."
  type        = string
}

variable "address_space" {
  description = "Address prefixes for the hub VNet."
  type        = list(string)
}

variable "gateway_subnet_prefixes" {
  description = "Address prefixes reserved for GatewaySubnet."
  type        = list(string)
  default     = []
}

variable "azure_firewall_subnet_prefixes" {
  description = "Address prefixes reserved for AzureFirewallSubnet."
  type        = list(string)
  default     = []
}

variable "bastion_subnet_prefixes" {
  description = "Address prefixes reserved for AzureBastionSubnet."
  type        = list(string)
  default     = []
}

variable "shared_services_subnet_prefixes" {
  description = "Address prefixes for shared services subnet(s) in the hub."
  type        = list(string)
  default     = []
}

variable "private_endpoints_subnet_prefixes" {
  description = "Address prefixes for hub private endpoint subnet(s)."
  type        = list(string)
  default     = []
}

variable "dns_resolver_subnet_prefixes" {
  description = "Address prefixes reserved for DNS resolver inbound/outbound endpoints."
  type        = list(string)
  default     = []
}

variable "create_ddos_plan" {
  description = "Whether to create a DDoS network protection plan placeholder resource."
  type        = bool
  default     = false
}

variable "ddos_plan_name" {
  description = "Optional DDoS plan name if create_ddos_plan is true."
  type        = string
  default     = null
}

variable "enable_bastion_placeholder" {
  description = "Whether to annotate that Azure Bastion is planned for this hub."
  type        = bool
  default     = false
}

variable "enable_firewall_placeholder" {
  description = "Whether to annotate that Azure Firewall is planned for this hub."
  type        = bool
  default     = false
}

variable "enable_private_dns_placeholder" {
  description = "Whether to annotate that Private DNS / DNS Resolver resources are planned for this hub."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags to apply to all supported resources."
  type        = map(string)
  default     = {}
}

locals {
  base_tags = merge(
    var.tags,
    {
      region              = var.region_key
      regionDisplayName   = var.region_display_name
      landingZoneRole     = "hub"
      subscriptionContext = var.subscription_id
    }
  )
}

# Resource group for the hub network foundation.
resource "azurerm_resource_group" "hub" {
  name     = var.resource_group_name
  location = var.location
  tags     = local.base_tags
}

# Core hub VNet.
resource "azurerm_virtual_network" "hub" {
  name                = var.vnet_name
  location            = azurerm_resource_group.hub.location
  resource_group_name = azurerm_resource_group.hub.name
  address_space       = var.address_space
  tags                = local.base_tags
}

# Reserved subnet names follow Azure conventions where applicable.
# Each subnet is optional because different Landmark regions may mature at different speeds.
resource "azurerm_subnet" "gateway" {
  count = length(var.gateway_subnet_prefixes) > 0 ? 1 : 0

  name                 = "GatewaySubnet"
  resource_group_name  = azurerm_resource_group.hub.name
  virtual_network_name = azurerm_virtual_network.hub.name
  address_prefixes     = var.gateway_subnet_prefixes
}

resource "azurerm_subnet" "firewall" {
  count = length(var.azure_firewall_subnet_prefixes) > 0 ? 1 : 0

  name                 = "AzureFirewallSubnet"
  resource_group_name  = azurerm_resource_group.hub.name
  virtual_network_name = azurerm_virtual_network.hub.name
  address_prefixes     = var.azure_firewall_subnet_prefixes
}

resource "azurerm_subnet" "bastion" {
  count = length(var.bastion_subnet_prefixes) > 0 ? 1 : 0

  name                 = "AzureBastionSubnet"
  resource_group_name  = azurerm_resource_group.hub.name
  virtual_network_name = azurerm_virtual_network.hub.name
  address_prefixes     = var.bastion_subnet_prefixes
}

resource "azurerm_subnet" "shared_services" {
  count = length(var.shared_services_subnet_prefixes) > 0 ? 1 : 0

  name                 = "snet-shared-services"
  resource_group_name  = azurerm_resource_group.hub.name
  virtual_network_name = azurerm_virtual_network.hub.name
  address_prefixes     = var.shared_services_subnet_prefixes
}

resource "azurerm_subnet" "private_endpoints" {
  count = length(var.private_endpoints_subnet_prefixes) > 0 ? 1 : 0

  name                                          = "snet-private-endpoints"
  resource_group_name                           = azurerm_resource_group.hub.name
  virtual_network_name                          = azurerm_virtual_network.hub.name
  address_prefixes                              = var.private_endpoints_subnet_prefixes
  private_endpoint_network_policies             = "Disabled"
  private_link_service_network_policies_enabled = false
}

resource "azurerm_subnet" "dns_resolver" {
  count = length(var.dns_resolver_subnet_prefixes) > 0 ? 1 : 0

  name                 = "snet-dns-resolver"
  resource_group_name  = azurerm_resource_group.hub.name
  virtual_network_name = azurerm_virtual_network.hub.name
  address_prefixes     = var.dns_resolver_subnet_prefixes
}

# Optional DDoS plan placeholder. This is one of the few shared-network resources
# we can safely scaffold without overcommitting to a final network security design.
resource "azurerm_network_ddos_protection_plan" "hub" {
  count = var.create_ddos_plan ? 1 : 0

  name                = coalesce(var.ddos_plan_name, "ddos-${var.region_key}-${var.vnet_name}")
  location            = azurerm_resource_group.hub.location
  resource_group_name = azurerm_resource_group.hub.name
  tags                = local.base_tags
}

# TODO: In the implementation PR, attach the DDoS plan to the VNet if enabled.
# That attachment is omitted here to keep the scaffold conservative and avoid
# implying a final security posture before Landmark confirms hub controls.

# These outputs intentionally expose the composition points the rest of the ALZ
# framework will need, especially spoke onboarding and subscription vending.
output "hub_resource_group_name" {
  description = "Name of the hub networking resource group."
  value       = azurerm_resource_group.hub.name
}

output "hub_vnet_name" {
  description = "Name of the hub virtual network."
  value       = azurerm_virtual_network.hub.name
}

output "hub_vnet_resource_id" {
  description = "Resource ID of the hub virtual network."
  value       = azurerm_virtual_network.hub.id
}

output "reserved_subnet_ids" {
  description = "IDs of reserved hub subnets created by the scaffold."
  value = {
    gateway           = try(azurerm_subnet.gateway[0].id, null)
    firewall          = try(azurerm_subnet.firewall[0].id, null)
    bastion           = try(azurerm_subnet.bastion[0].id, null)
    shared_services   = try(azurerm_subnet.shared_services[0].id, null)
    private_endpoints = try(azurerm_subnet.private_endpoints[0].id, null)
    dns_resolver      = try(azurerm_subnet.dns_resolver[0].id, null)
  }
}

output "implementation_notes" {
  description = "Human-readable TODO markers for future networking implementation."
  value = {
    spoke_peering              = "TODO: add cross-subscription spoke-to-hub peering/onboarding workflow"
    private_dns                = var.enable_private_dns_placeholder ? "TODO: add private DNS zones and resolver rulesets" : "not requested in this scaffold input"
    firewall                   = var.enable_firewall_placeholder ? "TODO: add Azure Firewall policy, route tables, and forced tunneling decisions" : "not requested in this scaffold input"
    bastion                    = var.enable_bastion_placeholder ? "TODO: add Azure Bastion public IP, host, and RBAC model" : "not requested in this scaffold input"
    provider_aliasing          = "TODO: wire provider aliases per hub subscription in the root module when multi-subscription implementation starts"
    connectivity_documentation = "TODO: document ER/VPN/private WAN decisions per region"
  }
}