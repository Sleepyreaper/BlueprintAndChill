// =============================================================================
// Module: managementGroups.bicep
// Purpose: ALZ-style management group hierarchy for Landmark.
// Scope:   tenant (Microsoft.Management/managementGroups is a tenant resource)
// =============================================================================
// STATUS: SCAFFOLD.
//   Creates the top-level Landmark group and the conventional ALZ child
//   groups (platform, landing-zones, sandbox, decommissioned) plus the
//   platform sub-groups (connectivity, identity, management) and the
//   landing-zone sub-groups (corp, online). Follows the standard ALZ
//   reference hierarchy:
//   https://learn.microsoft.com/azure/cloud-adoption-framework/ready/landing-zone/design-area/resource-org-management-groups
//
// TODO before production use:
//   - Confirm Landmark's actual desired child-group names/count with Hank +
//     Landmark stakeholders (this scaffold uses the CAF reference defaults).
//   - Decide whether "sandbox" is in scope for Landmark's governance model.
//   - Wire real Azure Policy assignments per group via policyAssignments.bicep
//     once this hierarchy is confirmed and deployed.
// =============================================================================

targetScope = 'tenant'

// -----------------------------------------------------------------------------
// PARAMETERS
// -----------------------------------------------------------------------------

@description('ID (also used as the resource name) for the top-level Landmark management group. Must be globally unique within the tenant.')
param topLevelManagementGroupId string

@description('Display name shown in the Azure portal for the top-level management group.')
param topLevelManagementGroupDisplayName string = 'Landmark'

@description('Optional parent management group ID. Empty string means attach directly under the Tenant Root Group.')
param parentManagementGroupId string = ''

@description('Child management group IDs/display-names under the platform group. TODO: confirm naming convention with Landmark (e.g. prefix per environment).')
param platformChildGroups array = [
  {
    id: '${topLevelManagementGroupId}-connectivity'
    displayName: 'Connectivity'
  }
  {
    id: '${topLevelManagementGroupId}-identity'
    displayName: 'Identity'
  }
  {
    id: '${topLevelManagementGroupId}-management'
    displayName: 'Management'
  }
]

@description('Child management group IDs/display-names under the landing-zones group. These are the parents that vended workload subscriptions will land under.')
param landingZoneChildGroups array = [
  {
    id: '${topLevelManagementGroupId}-corp'
    displayName: 'Corp'
  }
  {
    id: '${topLevelManagementGroupId}-online'
    displayName: 'Online'
  }
]

// -----------------------------------------------------------------------------
// RESOURCES — Top-level group
// -----------------------------------------------------------------------------

resource topLevelManagementGroup 'Microsoft.Management/managementGroups@2023-04-01' = {
  name: topLevelManagementGroupId
  properties: {
    displayName: topLevelManagementGroupDisplayName
    details: empty(parentManagementGroupId) ? null : {
      parent: {
        id: tenantResourceId('Microsoft.Management/managementGroups', parentManagementGroupId)
      }
    }
  }
}

// -----------------------------------------------------------------------------
// RESOURCES — Second-level standard ALZ groups
// -----------------------------------------------------------------------------

resource platformManagementGroup 'Microsoft.Management/managementGroups@2023-04-01' = {
  name: '${topLevelManagementGroupId}-platform'
  properties: {
    displayName: 'Platform'
    details: {
      parent: {
        id: topLevelManagementGroup.id
      }
    }
  }
}

resource landingZonesManagementGroup 'Microsoft.Management/managementGroups@2023-04-01' = {
  name: '${topLevelManagementGroupId}-landingzones'
  properties: {
    displayName: 'Landing Zones'
    details: {
      parent: {
        id: topLevelManagementGroup.id
      }
    }
  }
}

resource sandboxManagementGroup 'Microsoft.Management/managementGroups@2023-04-01' = {
  name: '${topLevelManagementGroupId}-sandbox'
  properties: {
    displayName: 'Sandbox'
    details: {
      parent: {
        id: topLevelManagementGroup.id
      }
    }
  }
}

resource decommissionedManagementGroup 'Microsoft.Management/managementGroups@2023-04-01' = {
  name: '${topLevelManagementGroupId}-decommissioned'
  properties: {
    displayName: 'Decommissioned'
    details: {
      parent: {
        id: topLevelManagementGroup.id
      }
    }
  }
}

// -----------------------------------------------------------------------------
// RESOURCES — Platform child groups (connectivity / identity / management)
// -----------------------------------------------------------------------------
// TODO: once the hub subscription is placed under "connectivity", grant the
// subscription-vending service principal Owner/Contributor at THIS group
// scope (not tenant root) to keep least-privilege intact.

resource platformChildManagementGroups 'Microsoft.Management/managementGroups@2023-04-01' = [for group in platformChildGroups: {
  name: group.id
  properties: {
    displayName: group.displayName
    details: {
      parent: {
        id: platformManagementGroup.id
      }
    }
  }
}]

// -----------------------------------------------------------------------------
// RESOURCES — Landing zone child groups (corp / online)
// -----------------------------------------------------------------------------
// These are the parent groups that vended Landmark workload subscriptions
// will be assigned into by subscriptionVending.bicep.

res