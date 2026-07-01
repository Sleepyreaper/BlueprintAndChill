variable "project_name" {
  description = "Short project identifier used for naming and tagging."
  type        = string
  default     = "blueprintandchill"
}

variable "environment" {
  description = "Deployment environment label for tags and naming, for example platform, dev, test, or prod."
  type        = string
  default     = "platform"
}

variable "owner" {
  description = "Owner tag value for operational ownership."
  type        = string
  default     = "sleepyreaper"
}

variable "cost_center" {
  description = "Cost center tag value for chargeback/showback."
  type        = string
  default     = "TBD"
}

variable "additional_tags" {
  description = "Additional tags merged into the standard ALZ scaffold tags."
  type        = map(string)
  default     = {}
}

variable "tenant_id" {
  description = "Microsoft Entra tenant ID that owns the ALZ platform."
  type        = string
}

variable "billing_role_definition_id" {
  description = "The exact MCA billing role definition identifier used to grant subscription creation rights at the invoice section billing scope. Keep this as an input so the scaffold mirrors the architecture brief and does not hardcode billing semantics."
  type        = string
}

variable "platform_management_group" {
  description = "Definition for the top-level platform management group used by this scaffold."
  type = object({
    name                       = string
    display_name               = string
    parent_management_group_id = optional(string)
  })
}

variable "landing_zones_management_group" {
  description = "Definition for the landing zones management group where vended subscriptions are placed."
  type = object({
    name         = string
    display_name = string
  })
}

variable "platform_hubs_management_group" {
  description = "Definition for the management group that contains regional hub subscriptions."
  type = object({
    name         = string
    display_name = string
  })
}

variable "create_sandbox_management_group" {
  description = "Whether to create an optional sandbox management group in this scaffold."
  type        = bool
  default     = false
}

variable "sandbox_management_group" {
  description = "Definition for an optional sandbox management group."
  type = object({
    name         = string
    display_name = string
  })
  default = {
    name         = "sandbox"
    display_name = "Sandbox"
  }
}

variable "hub_regions" {
  description = "Map of regional hub definitions. Each key is a region alias, such as eastus2 or westeurope."
  type = map(object({
    display_name         = string
    location             = string
    hub_subscription_id  = string
    resource_group_name  = string
    vnet_name            = string
    address_space        = list(string)

    gateway_subnet_prefixes           = optional(list(string), [])
    azure_firewall_subnet_prefixes    = optional(list(string), [])
    bastion_subnet_prefixes           = optional(list(string), [])
    shared_services_subnet_prefixes   = optional(list(string), [])
    private_endpoints_subnet_prefixes = optional(list(string), [])
    dns_resolver_subnet_prefixes      = optional(list(string), [])

    create_ddos_plan               = optional(bool, false)
    ddos_plan_name                 = optional(string, null)
    enable_bastion_placeholder     = optional(bool, false)
    enable_firewall_placeholder    = optional(bool, false)
    enable_private_dns_placeholder = optional(bool, false)
  }))
  default = {}
}

variable "policy_assignments" {
  description = "Map of placeholder policy assignments to apply at platform or landing-zones scope."
  type = map(object({
    name                 = string
    display_name         = string
    description          = string
    scope                = string
    policy_definition_id = string
    parameters           = map(any)
  }))
  default = {}
}

variable "subscription_vending_requests" {
  description = "Map of requested subscription-vending operations. These are scaffold inputs representing the future vending queue or workflow output."
  type = map(object({
    workload_name                   = string
    environment                     = string
    region_key                      = string
    alias_name                      = string
    subscription_name               = string
    billing_scope                   = string
    invoice_section_id              = string
    enrollment_type                 = string
    create_application_registration = optional(bool, true)
    existing_application_object_id  = optional(string, null)
    existing_service_principal_id   = optional(string, null)
  }))
  default = {}
}