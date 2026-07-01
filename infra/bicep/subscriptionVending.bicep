targetScope = 'tenant'

@description('Friendly request name for the subscription vending operation. Used for outputs and naming only in this scaffold.')
param requestName string

@description('Display name to use for the requested subscription alias or eventual subscription.')
param subscriptionDisplayName string

@description('Azure billing account identifier for MCA-based subscription creation. Leave blank in scaffold mode when no live call should occur.')
param billingAccountName string = ''

@description('Azure billing profile identifier for MCA-based subscription creation. Leave blank in scaffold mode when no live call should occur.')
param billingProfileName string = ''

@description('Azure invoice section identifier for MCA-based subscription creation. Leave blank in scaffold mode when no live call should occur.')
param invoiceSectionName string = ''

@description('Target management group resource ID where the new subscription should be associated after creation.')
param targetManagementGroupId string = ''

@description('Primary Azure region associated with the vended subscription workload intent.')
param location string = 'eastus'

@description('Alias name to use for Microsoft.Subscription/aliases. Must be unique in the tenant if live alias creation is enabled.')
param subscriptionAliasName string = ''

@description('Optional workload owner object ID that will receive subscription-scope RBAC in a later orchestration stage.')
param workloadOwnerObjectId string = ''

@description('Optional service principal display name requested by the vending process. Actual principal creation is intentionally externalized from Bicep in this scaffold.')
param servicePrincipalDisplayName string = ''

@description('Optional deployment archetype or catalog item selected by the requester. This is a contract placeholder for the demo web app and orchestration layer.')
param archetype string = 'baseline-app'

@description('Metadata describing the vending request. Stored in outputs only in this scaffold.')
param requestMetadata object = {
  environment: 'dev'
  project: 'BlueprintAndChill'
  owner: 'sleepyreaper'
  costCenter: 'tbd'
  businessUnit: 'tbd'
}

@description('When true, skip any live alias creation and emit a safe contract for the orchestrator instead.')
param scaffoldMode bool = true

/*
  Subscription vending scaffold notes:
  - Bicep is NOT responsible for creating Entra applications/service principals directly.
  - Billing role assignment and subscription alias creation often require orchestration with REST/CLI/SDK calls.
  - This file captures the intended contract shape and the Azure resources that MAY eventually be driven from it.
  - In scaffold mode, this template intentionally performs no live subscription creation.
*/

var hasBillingScope = !empty(billingAccountName) && !empty(billingProfileName) && !empty(invoiceSectionName)
var canAttemptAliasCreation = !scaffoldMode && hasBillingScope && !empty(subscriptionAliasName)

var billingScope = hasBillingScope
  ? '/providers/Microsoft.Billing/billingAccounts/${billingAccountName}/billingProfiles/${billingProfileName}/invoiceSections/${invoiceSectionName}'
  : ''

var plannedRoleAssignments = [
  {
    stage: 'pre-vending'
    actor: 'orchestrator-service-principal'
    scope: billingScope
    purpose: 'Grant the documented MCA billing role required to create subscriptions from the invoice section.'
    todo: 'Perform with Graph/ARM-capable automation outside this Bicep scaffold.'
  }
  {
    stage: 'post-vending'
    actor: 'workload-owner'
    scope: 'subscription'
    purpose: 'Grant least-privilege RBAC after subscription creation and management group association.'
    todo: 'Implement in orchestrator once subscription ID is known.'
  }
]

resource subscriptionAlias 'Microsoft.Subscription/aliases@2024-08-01-preview' = if (canAttemptAliasCreation) {
  name: subscriptionAliasName
  properties: {
    displayName: subscriptionDisplayName
    workload: 'Production'
    billingScope: billingScope
    additionalProperties: {
      /*
        TODO:
        - Confirm exact alias payload fields against the version chosen for implementation.
        - Add subscriptionOwnerId / managementGroupId / tags only after validating live API behavior.
        - Keep this minimal in the scaffold to avoid signaling false completeness.
      */
    }
  }
}

/*
  TODO(orchestration contract):
  - Create Entra application/service principal externally.
  - Grant the exact documented MCA invoice-section billing role externally.
  - Call subscription alias API externally if not using Bicep for the live create.
  - Wait for subscription provisioning completion.
  - Associate the new subscription to the target management group.
  - Deploy spoke bootstrap into the new subscription.
  - Initiate hub/spoke connectivity stage after network contract is available.
*/

/*
  TODO(spoke linkage):
  - Accept a spoke bootstrap package from the web app or workflow engine.
  - Pass hub VNet resource ID, DNS model, and policy archetype to downstream subscription-scope modules.
  - Avoid performing cross-subscription networking from the tenant-scope vending module itself.
*/

/*
  TODO(security):
  - Do not store client secrets, certificates, or tenant-specific identifiers in source.
  - Prefer managed identity for the orchestrator when it runs inside Azure.
  - Keep all privileged billing operations auditable and explicit.
*/

output vendingRequest object = {
  requestName: requestName
  subscriptionDisplayName: subscriptionDisplayName
  aliasName: subscriptionAliasName
  billingScope: billingScope
  targetManagementGroupId: targetManagementGroupId
  location: location
  archetype: archetype
  requestMetadata: requestMetadata
  scaffoldMode: scaffoldMode
}

output orchestratorContract object = {
  prerequisites: [
    'Create or locate orchestrator identity.'
    'Grant documented MCA invoice-section billing role at the billing scope.'
    'Create subscription alias and wait for provisioning completion.'
    'Associate subscription with target management group.'
    'Trigger subscription-scope bootstrap and hub/spoke linkage workflow.'
  ]
  inputs: {
    billingAccountName: billingAccountName
    billingProfileName: billingProfileName
    invoiceSectionName: invoiceSectionName
    targetManagementGroupId: targetManagementGroupId
    workloadOwnerObjectId: workloadOwnerObjectId
    servicePrincipalDisplayName: servicePrincipalDisplayName
    archetype: archetype
  }
  plannedRoleAssignments: plannedRoleAssignments
  notes: [
    'This scaffold intentionally avoids fake-complete subscription vending.'
    'Use this module as the contract boundary between IaC and orchestration code.'
  ]
}

output aliasCreationPlanned bool = canAttemptAliasCreation