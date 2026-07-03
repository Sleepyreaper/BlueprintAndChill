############################################################
# Module: hub_networking
#
# Establishes the hub of the hub-and-spoke topology: hub VNet,
# gateway subnet, firewall subnet, and shared services subnet.
# Spoke VNets (created per vended subscription) peer into this
# hub — peering itself happens from the spoke side during
# subscription onboarding, not declared statically here.
#
# TODO: ExpressRoute/VPN gateway resource, Azure Firewall
# resource, and DNS Private Resolver are intentionally NOT
# deployed in this scaffold — only the subnets that will host
# them are reserved. Wire those in a follow-up PR once
# connectivity requirements (VPN vs ER) are confirmed with
# Landmark.
############################################################

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
  }
}

variable "location" {
  description = "Azure region for the hub deployment."
  type        = string
}

variable "environment" {
  description = "Environment name used in resource naming."
  type        = string
}

variable "project_name" {
  description = "Short project identifier used in resource naming."
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group hosting hub networking resources. TODO: should reference a pre-existing platform connectivity RG in real deployments."
  type        = string
}

variable "hub_vnet_cidr" {
  description = "CIDR block for the hub virtual network."
  type        = string
}

variable "gateway_subnet_cidr" {
  description = "CIDR block reserved for GatewaySubnet."
  type        =