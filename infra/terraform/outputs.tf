############################################################
# BlueprintAndChill — Root Outputs
############################################################

output "landing_zones_management_group_id" {
  description = "Resource ID of the landing zones management group, used as the default vending target."
  value       = module.management_groups.landing_zones_management_group_id
}

output "platform_management_group_id" {
  description = "Resource ID of the platform management group (connectivity/identity/management)."
  value       = module.management_groups.platform_management_group_id
}

output "hub_vnet_id" {
  description = "Resource ID of the hub virtual network."
  value       = module.hub_networking.hub_vnet_id
}

output "hub_vnet_name" {
  description = "Name of the hub virtual network, for spoke peering configuration."
  value       = module.hub_networking.hub_vnet_name
}

output "firewall_subnet_id" {
  description = "Resource ID of AzureFirewallSubnet in the hub, for downstream firewall deployment."
  value       = module.hub_networking.firewall_subnet_id
}

output "policy_assignment_ids" {
  description = "Map of policy assignment names to their resource IDs applied at the landing zone scope."
  value       = module.policy_assignments.assignment_ids
}

output "vending_service_principal_app_id" {
  description = "Application (client) ID of the service principal created for subscription vending. TODO: pair with Key Vault-stored credential, never output secrets here."
  value       = module.subscription_vending.service_principal_app_id
}

output "vended_subscription_alias_name" {
  description = "Name of the subscription alias resource created (or planned) for the new spoke subscription."
  value       = module.subscription_vending.subscription_alias_name
}