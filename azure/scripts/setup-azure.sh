#!/bin/bash

# Create Resource Group
az group create \
  --name $AZURE_RESOURCE_GROUP \
  --location $AZURE_LOCATION

# Create Virtual Network
az network vnet create \
  --resource-group $AZURE_RESOURCE_GROUP \
  --name $AZURE_VNET_NAME \
  --address-prefix 10.0.0.0/16 \
  --subnet-name $AZURE_SUBNET_NAME \
  --subnet-prefix 10.0.1.0/24

# Create Storage Account
az storage account create \
  --name $AZURE_STORAGE_ACCOUNT \
  --resource-group $AZURE_RESOURCE_GROUP \
  --location $AZURE_LOCATION \
  --sku Standard_LRS

# Create Storage Container
az storage container create \
  --name $AZURE_STORAGE_CONTAINER \
  --account-name $AZURE_STORAGE_ACCOUNT

# Create Service Principal
az ad sp create-for-rbac \
  --name "bacalhau-spot-sp" \
  --role="Contributor" \
  --scopes="/subscriptions/$ARM_SUBSCRIPTION_ID/resourceGroups/$AZURE_RESOURCE_GROUP"
