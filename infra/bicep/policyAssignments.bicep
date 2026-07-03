targetScope = 'tenant'

@description('Management group ID or resource ID of the root scope where baseline policy assignments should begin. Pass a full management group resource ID for clarity.')
param rootPolicyScopeId string

@description('Management group ID or resource ID for platform/shared services policy assignments.')
param platformPolicyScopeId string = ''

@description('Management group ID or resource ID for landing zone/workload policy assignments.')
param landingZonesPolicyScopeId string = ''

@description('Location used for policy assignments that require a managed identity or location-bound deployment metadata.')
param location string = 'eastus'

@description('Common tags/metadata object used to populate assignment parameters where appropriate.')
param metadata object = {
  environment: 'platform'
  project: 'BlueprintAndChill'
  owner: 'sleepyreaper'
  costCenter: 'tbd'
}

@description('Optional map of policy or initiative definition IDs. Leave defaults as placeholders in scaffold mode and replace during implementation.')
param policyDefinitionIds object = {
  allowedLocations: ''
  requireTags: ''
  diagnosticsInitiative: ''
  privateEndpointsInitiative: ''
}

@description('Optional list of allowed Azure regions for workload deployment.')
param allowedLocations array = [
  'eastus'
  'westus'
]

@description('Required tag names for landing zone resources. This scaffold does not enforce values yet.')
param requiredTagNames array = [
  'environment'
  'project'
  'owner'
  'costCenter'
]

@description('When true, emit safe scaffold artifacts only. Empty definition IDs will skip live assignments.')
param scaffoldMode bool = true

/*
  Policy scaffold notes:
  - ALZ uses policy heavily, but this first PR should NOT pretend to deliver a complete enterprise policy estate.
  - This file demonstrates assignment shape, parameter conventions, and scope separation.
  - Definition IDs are intentionally parameters so the repo stays tenant-neutral and reusable.
  - Use initiatives/assignments approved by the platform governance team in later increments.
*/

resource allowedLocationsAssignment 'Microsoft.Authorization/policyAssignments@2024-04-01' = if (!empty(policyDefinitionIds.allowedLocations)) {
  name: 'alz-allowed-locations'
  scope: tenant()
  properties: {
    description: 'Scaffold assignment for restricting deployments to approved regions at the root platform scope.'
    displayName: 'ALZ Allowed Locations'
    policyDefinitionId: policyDefinitionIds.allowedLocations
    enforcementMode: scaffoldMode ? 'DoNotEnforce' : 'Default'
    scope: rootPolicyScopeId
    parameters: {
      listOfAllowedLocations: {
        value: allowedLocations
      }
    }
    metadata: {
      category: 'General'
      assignedBy: 'BlueprintAndChill'
      framework: 'ALZ'
    }
  }
  location: location
}

resource requireTagsAssignment 'Microsoft.Authorization/policyAssignments@2024-04-01' = if (!empty(policyDefinitionIds.requireTags) && !empty(landingZonesPolicyScopeId)) {
  name: 'alz-required-tags'
  scope: tenant()
  properties: {
    description: 'Scaffold assignment for requiring platform-standard tags in landing zone subscriptions.'
    displayName: 'ALZ Required Tags'
    policyDefinitionId: policyDefinitionIds.requireTags
    enforcementMode: scaffoldMode ? 'DoNotEnforce' : 'Default'
    scope: landingZonesPolicyScopeId
    parameters: {
      tagNames: {
        value: requiredTagNames
      }
    }
    metadata: {
      category: 'Tags'
      assignedBy: 'BlueprintAndChill'
      framework: 'ALZ'
    }
  }
  location: location
}

resource diagnosticsInitiativeAssignment 'Microsoft.Authorization/policyAssignments@2024-04-01' = if (!empty(policyDefinitionIds.diagnosticsInitiative) && !empty(platformPolicyScopeId)) {
  name: 'alz-platform-diagnostics'
  scope: tenant()
  properties: {
    description: 'Scaffold assignment for platform diagnostics and monitoring baseline.'
    displayName: 'ALZ Platform Diagnostics'
    policyDefinitionId: policyDefinitionIds.diagnosticsInitiative
    enforcementMode: scaffoldMode ? 'DoNotEnforce' : 'Default'
    scope: platformPolicyScopeId
    parameters: {}
    metadata: {
      category: 'Monitoring'
      assignedBy: 'BlueprintAndChill'
      framework: 'ALZ'
    }
  }
  location: location
}

resource privateEndpointsInitiativeAssignment 'Microsoft.Authorization/policyAssignments@2024-04-01' = if (!empty(policyDefinitionIds.privateEndpointsInitiative) && !empty(landingZonesPolicyScopeId)) {
  name: 'alz-private-endpoints'
  scope: tenant()
  properties: {
    description: 'Scaffold assignment for encouraging or enforcing private connectivity patterns in workload subscriptions.'
    displayName: 'ALZ Private Connectivity'
    policyDefinitionId: policyDefinitionIds.privateEndpointsInitiative
    enforcementMode: scaffoldMode ? 'DoNotEnforce' : 'Default'
    scope: landingZonesPolicyScopeId
    parameters: {}
    metadata: {
      category: 'Network'
      assignedBy: 'BlueprintAndChill'
      framework: 'ALZ'
    }
  }
  location: location
}

/*
  TODO(policy definitions):
  - Wire in initiative/definition IDs from approved ALZ or custom definitions.
  - Consider separate modules for definitions, set definitions, and assignments if this repo starts owning custom policy artifacts.
*/

/*
  TODO(exemptions):
  - Model exemptions in a dedicated artifact with expiration, justification, and approver metadata.
  - Do not co-locate exemptions with broad assignments in the foundational scaffold.
*/

/*
  TODO(vending integration):
  - The subscription-vending workflow should ensure newly created subscriptions land beneath the correct management group
    so they inherit these assignments automatically.
  - If additional subscription-scope assignments are needed, create a separate post-vending deployment step.
*/

output evaluatedScopes object = {
  root: rootPolicyScopeId
  platform: platformPolicyScopeId
  landingZones: landingZonesPolicyScopeId
}

output assignmentPlan object = {
  allowedLocations: {
    definitionId: policyDefinitionIds.allowedLocations
    enabled: !empty(policyDefinitionIds.allowedLocations)
    scope: rootPolicyScopeId
    enforcementMode: scaffoldMode ? 'DoNotEnforce' : 'Default'
  }
  requiredTags: {
    definitionId: policyDefinitionIds.requireTags
    enabled: !empty(policyDefinitionIds.requireTags) && !empty(landingZonesPolicyScopeId)
    scope: landingZonesPolicyScopeId
    enforcementMode: scaffoldMode ? 'DoNotEnforce' : 'Default'
  }
  diagnostics: {
    definitionId: policyDefinitionIds.diagnosticsInitiative
    enabled: !empty(policyDefinitionIds.diagnosticsInitiative) && !empty(platformPolicyScopeId)
    scope: platformPolicyScopeId
    enforcementMode: scaffoldMode ? 'DoNotEnforce' : 'Default'
  }
  privateConnectivity: {
    definitionId: policyDefinitionIds.privateEndpointsInitiative
    enabled: !empty(policyDefinitionIds.privateEndpointsInitiative) && !empty(landingZonesPolicyScopeId)
    scope: landingZonesPolicyScopeId
    enforcementMode: scaffoldMode ? 'DoNotEnforce' : 'Default'
  }
}