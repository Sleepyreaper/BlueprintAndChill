targetScope = 'tenant'

@description('Name of the platform root management group for this scaffold. This should represent the customer-owned platform root beneath the tenant root management group, not the tenant root itself.')
param rootManagementGroupName string = 'lmk-platform'

@description('Display name for the platform root management group.')
param rootManagementGroupDisplayName string = 'Landmark Platform'

@description('Name of the management group that will hold platform/shared services subscriptions, including regional hub subscriptions.')
param platformManagementGroupName string = 'platform'

@description('Display name for the platform/shared services management group.')
param platformManagementGroupDisplayName string = 'Platform'

@description('Name of the management group that will hold landing zone workload subscriptions.')
param landingZonesManagementGroupName string = 'landingzones'

@description('Display name for the landing zones management group.')
param landingZonesManagementGroupDisplayName string = 'Landing Zones'

@description('Name of the management group for sandbox or experimentation subscriptions. Keep this optional in early framework stages.')
param sandboxManagementGroupName string = 'sandbox'

@description('Display name for the sandbox management group.')
param sandboxManagementGroupDisplayName string = 'Sandbox'

@description('Optional region-aligned management groups that can be used to organize vended subscriptions by geography or operating model. This is scaffold-only and does not imply a required CAF hierarchy depth.')
param regionalManagementGroups array = [
  {
    name: 'connectivity-eastus'
    displayName: 'Connectivity East US'
    parentKey: 'platform'
  }
  {
    name: 'connectivity-westus'
    displayName: 'Connectivity West US'
    parentKey: 'platform'
  }
  {
    name: 'landingzones-eastus'
    displayName: 'Landing Zones East US'
    parentKey: 'landingzones'
  }
  {
    name: 'landingzones-westus'
    displayName: 'Landing Zones West US'
    parentKey: 'landingzones'
  }
]

@description('Tags-like metadata for documentation and generated exports. Management groups do not support ARM tags, so this object is informational for downstream modules and deployment records.')
param metadata object = {
  environment: 'platform'
  project: 'BlueprintAndChill'
  owner: 'sleepyreaper'
  costCenter: 'tbd'
}

@description('When true, emit only scaffold outputs and declarations intended for later ALZ composition. This template is intentionally safe and non-destructive.')
param scaffoldMode bool = true

/*
  ALZ / CAF scaffold notes:
  - Keep management group hierarchy relatively flat.
  - Use management groups primarily for policy assignment and governance inheritance.
  - Avoid hardcoding tenant-specific IDs or billing constructs here.
  - Subscription placement is intentionally deferred to the vending workflow/module.
  - This file establishes the hierarchy SHAPE only; it is not a complete enterprise enrollment deployment.
*/

var rootManagementGroupId = tenantResourceId('Microsoft.Management/managementGroups', rootManagementGroupName)
var platformManagementGroupId = tenantResourceId('Microsoft.Management/managementGroups', platformManagementGroupName)
var landingZonesManagementGroupId = tenantResourceId('Microsoft.Management/managementGroups', landingZonesManagementGroupName)
var sandboxManagementGroupId = tenantResourceId('Microsoft.Management/managementGroups', sandboxManagementGroupName)

resource rootManagementGroup 'Microsoft.Management/managementGroups@2023-04-01' = {
  name: rootManagementGroupName
  properties: {
    displayName: rootManagementGroupDisplayName
    details: {
      /*
        The parent for this customer platform root is intentionally set to the tenant root.
        Do not replace '/' with a tenant-specific hardcoded management group ID.
        If a different customer-owned parent MG is required, promote that to a parameter in a later increment.
      */
      parent: {
        id: tenantResourceId('Microsoft.Management/managementGroups', tenant().tenantId)
      }
    }
  }
}

resource platformManagementGroup 'Microsoft.Management/managementGroups@2023-04-01' = {
  name: platformManagementGroupName
  properties: {
    displayName: platformManagementGroupDisplayName
    details: {
      parent: {
        id: rootManagementGroupId
      }
    }
  }
  dependsOn: [
    rootManagementGroup
  ]
}

resource landingZonesManagementGroup 'Microsoft.Management/managementGroups@2023-04-01' = {
  name: landingZonesManagementGroupName
  properties: {
    displayName: landingZonesManagementGroupDisplayName
    details: {
      parent: {
        id: rootManagementGroupId
      }
    }
  }
  dependsOn: [
    rootManagementGroup
  ]
}

resource sandboxManagementGroup 'Microsoft.Management/managementGroups@2023-04-01' = {
  name: sandboxManagementGroupName
  properties: {
    displayName: sandboxManagementGroupDisplayName
    details: {
      parent: {
        id: rootManagementGroupId
      }
    }
  }
  dependsOn: [
    rootManagementGroup
  ]
}

resource regionalManagementGroupResources 'Microsoft.Management/managementGroups@2023-04-01' = [for mg in regionalManagementGroups: {
  name: mg.name
  properties: {
    displayName: mg.displayName
    details: {
      parent: {
        id: mg.parentKey == 'platform'
          ? platformManagementGroupId
          : mg.parentKey == 'landingzones'
            ? landingZonesManagementGroupId
            : mg.parentKey == 'sandbox'
              ? sandboxManagementGroupId
              : rootManagementGroupId
      }
    }
  }
  dependsOn: [
    platformManagementGroup
    landingZonesManagementGroup
    sandboxManagementGroup
  ]
}]

/*
  TODO(subscription-vending integration):
  - The vending workflow should determine the target landing zone management group per request.
  - After alias-based subscription creation completes, a follow-up deployment or automation step should
    associate the subscription to the correct management group.
  - Keep that subscription association out of this scaffold to avoid accidental moves during framework bootstrap.
*/

/*
  TODO(policy integration):
  - Assign ALZ-aligned policy initiatives at root/platform/landingzones scopes from policyAssignments.bicep.
  - Keep policy definitions and assignments decoupled from hierarchy creation to support staged rollout and what-if review.
*/

output scaffoldModeEnabled bool = scaffoldMode
output metadata object = metadata
output managementGroupHierarchy object = {
  root: {
    name: rootManagementGroupName
    id: rootManagementGroupId
    displayName: rootManagementGroupDisplayName
  }
  platform: {
    name: platformManagementGroupName
    id: platformManagementGroupId
    displayName: platformManagementGroupDisplayName
  }
  landingZones: {
    name: landingZonesManagementGroupName
    id: landingZonesManagementGroupId
    displayName: landingZonesManagementGroupDisplayName
  }
  sandbox: {
    name: sandboxManagementGroupName
    id: sandboxManagementGroupId
    displayName: sandboxManagementGroupDisplayName
  }
  regional: [for mg in regionalManagementGroups: {
    name: mg.name
    displayName: mg.displayName
    parentKey: mg.parentKey
    id: tenantResourceId('Microsoft.Management/managementGroups', mg.name)
  }]
}