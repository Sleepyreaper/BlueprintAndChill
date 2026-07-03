############################################################
# BlueprintAndChill — Root Variables
# All values are environment-driven. No tenant-specific,
# customer-specific, or secret values are defaulted here.
############################################################

variable "environment" {
  description = "Deployment environment name (e.g. dev, test, prod). Drives naming and tagging."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "test", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, test, staging, prod."
  }
}

variable "project_name" {
  description = "Short project identifier used in resource naming (e.g. bpac)."
  type        = string
  default     = "bpac"
}

variable "location" {
  description = "Primary Azure region for this hub deployment (e.g. eastus2, westeurope)."
  type        = string
  default     = "eastus2"
}

variable "resource_group_prefix" {
  description = "Prefix used when composing platform resource group names."
  type        = string
  default     = "rg-landmark"
}

variable "tags" {
  description = "Common resource tags applied across all modules (environment, project, owner, costCenter)."
  type        = map(string)
  default = {
    project     = "BlueprintAndChill"
    owner       = "REPLACE_ME"
    costCenter  = "REPLACE_ME"
    environment = "dev"
  }
}

# ---------------- Management Groups ----------------

variable "root_management_group_display_name" {
  description = "Display name for the Landmark root management group under the tenant root."
  type        = string
  default     = "Landmark"
}

variable "management_group_prefix" {
  description = "Prefix applied to all child management group IDs to avoid collisions in the tenant."
  type        = string
  default     = "landmark"
}

variable "parent_management_group_id" {
  description = "Fully qualified ID of the parent management group (typically tenant root). TODO: must be supplied per tenant, never hardcoded."
  type        = string
  default     = ""
}

# ---------------- Hub Networking ----------------

variable "hub_vnet_cidr" {
  description = "CIDR block for the hub virtual network."
  type        = string
  default     = "10.0.0.0/16"
}

variable "gateway_subnet_cidr" {
  description = "CIDR block for the GatewaySubnet (VPN/ExpressRoute gateway)."
  type        = string
  default     = "10.0.0.0/27"
}

variable "firewall_subnet_cidr" {
  description = "CIDR block for AzureFirewallSubnet."
  type        = string
  default     = "10.0.1.0/26"
}

variable "shared_services_subnet_cidr" {
  description = "CIDR block for shared platform services (DNS resolvers, bastion, etc.)."
  type        = string
  default     = "10.0.2.0/24"
}

# ---------------- Policy Assignments ----------------

variable "enable_deny_public_ip" {
  description = "Whether to assign a policy denying public IP creation in spoke subscriptions."
  type        = bool
  default     = true
}

variable "enable_require_tags" {
  description = "Whether to assign a policy requiring mandatory tags on all resources."
  type        = bool
  default     = true
}

variable "allowed_locations" {
  description = "List of Azure regions permitted for resource deployment via policy."
  type        = list(string)
  default     = ["eastus2", "westus2"]
}

# ---------------- Subscription Vending ----------------

variable "new_subscription_display_name" {
  description = "Display name for the new spoke subscription to be vended. TODO: normally supplied per vending request, not a static default."
  type        = string
  default     = "landmark-spoke-subscription"
}

variable "billing_account_id" {
  description = "MCA billing account ID scope for subscription creation. TODO: must be sourced from the customer's real MCA enrollment, never hardcoded here."
  type        = string
  default     = ""
  sensitive   = true
}

variable "billing_profile_id" {
  description = "MCA billing profile ID under the billing account."
  type        = string
  default     = ""
  sensitive   = true
}

variable "invoice_section_id" {
  description = "MCA invoice section ID that scopes the new subscription. TODO: in production this is passed in by the event trigger (new invoice section created), not statically configured."
  type        = string
  default     = ""
  sensitive   = true
}

variable "vending_service_principal_display_name" {
  description = "Display name for the service principal created to perform subscription vending operations."
  type        = string
  default     = "sp-landmark-subscription-vending"
}