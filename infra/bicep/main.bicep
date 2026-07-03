// =============================================================================
// BlueprintAndChill — Landing Zone Orchestrator (SCAFFOLD)
// =============================================================================
// Purpose:
//   Tenant-scoped entry point that wires together the ALZ-style building
//   blocks for Landmark: management group hierarchy, hub networking, policy
//   assignments, and the subscription-vending placeholder.
//
// STATUS: FRAMEWORK / SCAFFOLD ONLY.
//   This file demonstrates module wiring and scope binding. It is NOT yet a
//   deployable production environment. Modules contain commented-out
//   resources and TODOs where live implementation is required.
//
// Aligns with:
//   - CAF Landing Zones: https://learn.microsoft.com/azure/cloud-adoption-framework/ready/landing-zone/
//   - CAF Management Groups: https://learn.microsoft.com/azure/cloud-adoption-framework/ready/landing-zone/design-area/resource-org-management-groups
//   - ALZ Subscription Vending: https://learn.microsoft.com/azure/architecture/landing-zones/subscription-vending
//
// Deploy with (see infra/bicep/README-style deployment notes in PR description):
//   az deployment tenant create \
//     --name blueprintandchill-lz \
//     --location <location> \
//     --template-file infra/bicep/main.bicep \
//     --parameters @main.parameters.json
// =============================================================================

targetScope = 'tenant'

// -----------------------------------------------------------------------------
// PARAMETERS — Management Group Hierarchy
// -----------------------------------------------------------------------------

@description('Top-level (intermediate root) management group ID for Landmark, directly under Tenant Root Group. No default — must be supplied per environment.')
param topLevelManagementGroupId string

@description('Display name for the top-level Landmark management group.')
param topLevelManagementGroupDisplayName string = 'Landmark'

@description('Optional parent management group ID to attach the top-level group under. Leave empty to attach directly under Tenant Root Group. TODO: confirm Landmark tenant root policy before go-live.')
param parentManagementGroupId string = ''

// -----------------------------------------------------------------------------
// PARAMETERS — Hub Networking
// -----------------------------------------------------------------------------

@description('Subscription ID of the platform connectivity (hub) subscription. TODO: this is environment-specific and MUST be supplied via a non-committed parameter file or pipeline variable — never hardcode in source.')
param hubSubscriptionId string

@description('Azure region for the hub landing zone resources.')
param location string = 'eastus2'

@description('Address prefix for the hub virtual network. TODO: confirm Landmark IP address plan / avoid overlap with spokes.')
param hubVnetAddressPrefix string = '10.0.0.0/22'

// -----------------------------------------------------------------------------
// PARAMETERS — Governance / Tagging
// -----------------------------------------------------------------------------

@description('Deployment environment identifier (e.g. dev, test, prod). Drives naming and policy scoping decisions.')
@allowed([
  'dev'
  'test'
  'prod'
])
param environment string = 'prod'

@description('Common resource tags applied across all landing zone modules. Extend as needed; do not include secrets.')
param tags object = {
  project: 'BlueprintAndChill'
  customer: 'Landmark'
  environment: environment
  managedBy: 'bicep'
}

// -----------------------------------------------------------------------------
// PARAMETERS — Subscription Vending Placeholder
// -----------------------------------------------------------------------------

@description('MCA billing account/profile/invoice-section scope used for subscription vending, in the form /billingAccounts/{id}/billingProfiles/{id}/invoiceSections/{id}. TODO: sourced dynamically per invoice-section-created event in the vending automation, not hardcoded here.')
param defaultBillingScope string = ''

@description('Management group ID that newly vended subscriptions should land under (typically a landing-zones child group, e.g. corp or online). Resolved from managementGroups module output when wired end-to-end.')
param subscriptionVendingTargetManagementGroupId string = ''

// -----------------------------------------------------------------------------
// MODULE — Management Group Hierarchy (tenant scope)
// -----------------------------------------------------------------------------

module managementGroups 'modules/managementGroups.bicep' = {
  name: 'deploy-management-groups'
  params: {
    topLevelManagementGroupId: topLevelManagementGroupId
    topLevelManagementGroupDisplayName: topLevelManagementGroupDisplayName
    parentManagementGroupId: parentManagementGroupId
  }
}

// -----------------------------------------------------------------------------
// MODULE — Hub Networking (subscription scope: the platform connectivity sub)
// -----------------------------------------------------------------------------
// NOTE: module scope binds to the hub subscription explicitly. This lets a
// tenant-scoped orchestrator deploy subscription-scoped resources without
// requiring the caller to re-target the whole file.

module hubNetworking 'modules/hubNetworking.bicep' = {
  name: 'deploy-hub-networking'
  scope: subscription(hubSubscriptionId)
  params: {
    location: location
    hubVnetAddressPrefix: hubVnetAddressPrefix
    tags: tags
    environment: environment
  }
}

// -----------------------------------------------------------------------------
// MODULE — Policy Assignments (management group scope: platform child group)
// -----------------------------------------------------------------------------
// TODO: once managementGroups.bicep exposes a real "platform" child MG id,
// bind scope to that instead of the top-level group. Placeholder wiring below
// targets the top-level group to keep this scaffold self-contained.

module platformPolicyAssignments 'modules/policyAssignments.bicep' = {
  name: 'deploy-platform-policy-assignments'
  scope: managementGroup(topLevelManagementGroupId)
  params: {
    environment: environment
    tags: tags
  }
  dependsOn: [
    managementGroups
  ]
}

// -----------------------------------------------------------------------------
// MODULE — Subscription Vending Placeholder (tenant scope)
// -----------------------------------------------------------------------------
// NOT a live automation path yet. See docs/architecture.md for the intended
// MCA invoice-section-created -> vending trigger flow. This module documents
// the shape of the request without pretending to fully automate it.

module subscriptionVending 'modules/subscriptionVending.bicep' = {
  name: 'deploy-subscription-vending-placeholder'
  params: {
    billingScope: defaultBillingScope
    targetManagementGroupId: subscriptionVendingTargetManagementGroupId
    environment: environment
    tags: tags
  }
  dependsOn: [
    managementGroups
  ]
}

// -----------------------------------------------------------------------------
// OUTPUTS
// -----------------------------------------------------------------------------

@description('Top-level Landmark management group resource ID.')
output topLevelManagementGroupResourceId string = managementGroups.outputs.topLevelManagementGroupResourceId

@description('Hub networking resource group name (subscription-scoped module output).')
output hubResourceGroupName string = hubNetworking.outputs.resourceGroupName

@description('Placeholder subscription-vending alias name for tracking/log correlation. TODO: real ID only available post-alias-acceptance; see subscriptionVending.bicep.')
output subscriptionVendingAliasNamePlaceholder string = subscriptionVending.outputs.aliasNamePlaceholder