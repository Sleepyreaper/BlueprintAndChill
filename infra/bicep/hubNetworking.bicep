targetScope = 'subscription'

@description('Azure region for the regional landing zone hub.')
param location string

@description('Logical prefix used in resource naming. Keep this generic and environment-safe.')
param namingPrefix string = 'lmk'

@description('Environment stamp used in names and tags, for example dev, test, prod, or platform.')
param environmentName string = 'platform'

@description('Virtual network name for the regional hub.')
param hubVnetName string = '${namingPrefix}-${environmentName}-${location}-hub-vnet'

@description('Address space assigned to the hub virtual network.')
param hubAddressPrefixes array = [
  '10.0.0.0/16'
]

@description('Subnet definitions for the hub virtual network. This scaffold includes representative ALZ-style shared services subnets only.')
param hubSubnets array = [
  {
    name: 'AzureFirewallSubnet'
    addressPrefix: '10.0.0.0/24'
    networkSecurityGroupResourceId: ''
    routeTableResourceId: ''
    serviceEndpoints: []
    privateEndpointNetworkPolicies: 'Disabled'
    privateLinkServiceNetworkPolicies: 'Enabled'
    delegationServiceName: ''
  }
  {
    name: 'GatewaySubnet'
    addressPrefix: '10.0.1.0/24'
    networkSecurityGroupResourceId: ''
    routeTableResourceId: ''
    serviceEndpoints: []
    privateEndpointNetworkPolicies: 'Disabled'
    privateLinkServiceNetworkPolicies: 'Enabled'
    delegationServiceName: ''
  }
  {
    name: 'SharedServices'
    addressPrefix: '10.0.10.0/24'
    networkSecurityGroupResourceId: ''
    routeTableResourceId: ''
    serviceEndpoints: [
      'Microsoft.Storage'
      'Microsoft.KeyVault'
    ]
    privateEndpointNetworkPolicies: 'Disabled'
    privateLinkServiceNetworkPolicies: 'Enabled'
    delegationServiceName: ''
  }
  {
    name: 'PrivateEndpoints'
    addressPrefix: '10.0.20.0/24'
    networkSecurityGroupResourceId: ''
    routeTableResourceId: ''
    serviceEndpoints: []
    privateEndpointNetworkPolicies: 'Disabled'
    privateLinkServiceNetworkPolicies: 'Enabled'
    delegationServiceName: ''
  }
]

@description('Optional DDoS Network Protection plan resource ID. Leave empty in scaffold mode.')
param ddosProtectionPlanResourceId string = ''

@description('Optional DNS servers for the hub VNet. Empty array uses Azure-provided DNS.')
param dnsServers array = []

@description('Resource ID of a Log Analytics workspace for flow logs / diagnostics. Empty in scaffold mode unless already available.')
param logAnalyticsWorkspaceResourceId string = ''

@description('Enable creation of a placeholder NSG for the shared services subnet. Rules are intentionally minimal in this scaffold.')
param createSharedServicesNsg bool = false

@description('Enable virtual network peering placeholders. The scaffold will only emit outputs/TODOs and will not create cross-subscription peerings by default.')
param enableSpokePeeringScaffold bool = true

@description('Optional spoke peering intents used by downstream automation. This scaffold does not create the spoke VNets; it documents the target shape.')
param spokeLinkIntents array = [
  /*
    Example:
    {
      subscriptionId: '00000000-0000-0000-0000-000000000000'
      spokeVnetResourceGroupName: 'rg-app-eastus-network'
      spokeVnetName: 'lmk-prod-eastus-app-vnet'
      allowForwardedTraffic: true
      useRemoteGateways: false
      allowGatewayTransitFromHub: true
    }
  */
]

@description('Tags applied to supported resources.')
param tags object = {
  environment: environmentName
  project: 'BlueprintAndChill'
  owner: 'sleepyreaper'
  costCenter: 'tbd'
}

@description('When true, prefer safe scaffold behavior and avoid destructive or cross-subscription operations.')
param scaffoldMode bool = true

/*
  Hub networking scaffold notes:
  - This file represents the SHAPE of a regional ALZ hub, not a complete connectivity implementation.
  - Firewall, VPN/ER gateways, DNS resolvers, and cross-subscription peering are intentionally TODO items.
  - Subnet address ranges are examples and must be reviewed against the enterprise IP plan before live use.
  - The goal of this increment is to give the repo clean Bicep conventions and extension points.
*/

resource hubVnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: hubVnetName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: hubAddressPrefixes
    }
    dhcpOptions: empty(dnsServers) ? null : {
      dnsServers: dnsServers
    }
    enableDdosProtection: !empty(ddosProtectionPlanResourceId)
    ddosProtectionPlan: empty(ddosProtectionPlanResourceId) ? null : {
      id: ddosProtectionPlanResourceId
    }
    subnets: [for subnet in hubSubnets: {
      name: subnet.name
      properties: {
        addressPrefix: subnet.addressPrefix
        networkSecurityGroup: empty(subnet.networkSecurityGroupResourceId) ? null : {
          id: subnet.networkSecurityGroupResourceId
        }
        routeTable: empty(subnet.routeTableResourceId) ? null : {
          id: subnet.routeTableResourceId
        }
        serviceEndpoints: [for endpoint in subnet.serviceEndpoints: {
          service: endpoint
        }]
        privateEndpointNetworkPolicies: subnet.privateEndpointNetworkPolicies
        privateLinkServiceNetworkPolicies: subnet.privateLinkServiceNetworkPolicies
        delegations: empty(subnet.delegationServiceName) ? [] : [
          {
            name: 'delegation'
            properties: {
              serviceName: subnet.delegationServiceName
            }
          }
        ]
      }
    }]
  }
}

resource sharedServicesNsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = if (createSharedServicesNsg) {
  name: '${namingPrefix}-${environmentName}-${location}-shared-nsg'
  location: location
  tags: tags
  properties: {
    securityRules: [
      /*
        TODO: Replace with organization-approved baseline rules.
        The scaffold avoids asserting a fake-secure rule set.
      */
    ]
  }
}

resource vnetDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (!empty(logAnalyticsWorkspaceResourceId)) {
  name: '${hubVnetName}-diagnostics'
  scope: hubVnet
  properties: {
    workspaceId: logAnalyticsWorkspaceResourceId
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
    logs: []
  }
}

/*
  TODO(connectivity):
  - Add Azure Firewall / Firewall Policy modules when the enterprise security baseline is agreed.
  - Add VPN Gateway or ExpressRoute Gateway module if Landmark requires hybrid connectivity.
  - Add Private DNS Resolver and zone-linking pattern for centralized private name resolution.
*/

/*
  TODO(spoke linkage):
  - The subscription vending workflow should supply spoke VNet IDs or a deployment contract after subscription creation.
  - Cross-subscription peering typically requires deployments at both hub and spoke scopes.
  - Keep those operations in a later orchestrated stage to avoid destructive or partially-authorized behavior here.
*/

/*
  TODO(policy alignment):
  - Pair this module with policy that enforces approved regions, diagnostic settings, and private endpoint usage.
  - Do not silently create policy exemptions here.
*/

output hubVnetResourceId string = hubVnet.id
output hubVnetNameOut string = hubVnet.name
output spokeLinkScaffold object = {
  enabled: enableSpokePeeringScaffold
  hubVnetResourceId: hubVnet.id
  intendedSpokes: spokeLinkIntents
  notes: [
    'Spoke peerings are intentionally not created by default in this scaffold.'
    'Use a later orchestrated stage after subscription creation and RBAC are complete.'
  ]
}